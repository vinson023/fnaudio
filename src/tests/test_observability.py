import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")
import file_permissions
from observability import HTTP_LATENCY_ROUTES, MAX_COUNTER_INCREMENT, MAX_COUNTER_VALUE, MAX_LATENCY_TOTAL_MS, MAX_LOG_FILE_BYTES, MAX_LOG_RECORD_BYTES, MAX_REDACT_ITEMS, MAX_REDACT_KEY, MAX_REDACT_STRING, Observability, bounded_counter_increment, bounded_log_file_bytes, bounded_counter_value, finite_nonnegative, http_latency_route, positive_threshold, redact, request_id, should_write_http_request


class ObservabilityTests(unittest.TestCase):
    def test_request_id_accepts_safe_value_and_replaces_untrusted_value(self):
        self.assertEqual(request_id("client-12345678"), "client-12345678")
        self.assertRegex(request_id("bad value\nheader"), r"^[0-9a-f]{32}$")

    def test_request_id_does_not_stringify_arbitrary_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("request ids must not coerce custom values")

        self.assertRegex(request_id(Explosive()), r"^[0-9a-f]{32}$")

    def test_redaction_removes_nested_credentials(self):
        payload = redact({"token": "one", "nested": {"password": "two", "status": "ok"}})
        self.assertEqual(payload["token"], "[REDACTED]")
        self.assertEqual(payload["nested"], {"password": "[REDACTED]", "status": "ok"})

    def test_structured_log_is_json_and_does_not_emit_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            metrics = Observability()
            metrics.write(path, "request", request_id="abc", authorization="Bearer secret", status=200)
            with open(path, encoding="utf-8") as handle:
                row = json.loads(handle.read())
            self.assertEqual(row["authorization"], "[REDACTED]")
            self.assertEqual(row["status"], 200)

    def test_structured_log_rotates_at_the_size_bound(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("old-data")
            Observability().write(path, "request", max_bytes=4, status=200)
            self.assertTrue(os.path.isfile(path + ".1"))
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.loads(handle.read())["event"], "request")

    def test_repeated_log_writes_do_not_re_harden_the_directory(self):
        # `write()` used to run the full `secure_directory` pass - about six syscalls, including
        # two symlink probes and a chmod - for every single record. The drift helper keeps the
        # same guarantees, so the only legitimate call into the full hardening is the one that
        # creates the log directory; a steady-state write must settle down to one lstat.
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "logs", "fnaudio.log")
            service = Observability()
            service.write(path, "creates the directory")
            # Count the real probes rather than a patched-out function: observability reaches
            # the helper through the module attribute, so a call-count assertion on an imported
            # name would not survive a revert back to the full pass.
            real_lstat = file_permissions.os.lstat
            probes = []
            with patch.object(file_permissions, "secure_directory",
                              wraps=file_permissions.secure_directory) as full, \
                    patch.object(file_permissions.os, "lstat",
                                 side_effect=lambda target: (probes.append(target), real_lstat(target))[1]):
                for index in range(20):
                    service.write(path, "heartbeat", index=index)
                self.assertEqual(full.call_count, 0,
                                 "a steady-state write re-ran the full directory hardening")
            # Exactly two probes per line, on two distinct paths: this is a *fingerprint* of the
            # wiring rather than a cost model. Measured here, the old `secure_directory` +
            # `secure_file` pair does not route through `os.lstat`/`os.stat` at all on Windows
            # (it counts zero), so a revert is caught because the drift helpers disappear from
            # the probe list, not because they were more expensive on this platform. The saving
            # itself is pinned by the timing measurement quoted in the drift helper's docstring
            # (200 directory passes: 6.075 ms -> 1.060 ms); on POSIX the full pass additionally
            # issues the chmod syscall per line, which this host cannot exercise because
            # `_chmod` returns early at file_permissions.py:85.
            self.assertEqual(len(probes), 40,
                             "log writes cost %d probes for 20 lines instead of 2 each" % len(probes))
            self.assertEqual(len(set(probes)), 2, "probes should alternate between two fixed paths")
            with open(path, encoding="utf-8") as handle:
                records = [json.loads(line) for line in handle if line.strip()]
            self.assertEqual(len(records), 21, "records were dropped by the new hardening path")
            self.assertEqual(records[-1]["index"], 19)
            self.assertEqual(records[0]["event"], "creates the directory")

    def test_log_write_does_not_hold_the_metrics_lock(self):
        # Every request thread records counters and latency through the same
        # lock the health/diagnostics snapshot reads, so the JSONL write must
        # not run inside it.
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("old-data")
            metrics = Observability()
            entered = threading.Event()
            release = threading.Event()

            def blocked_secure_file(_target):
                entered.set()
                release.wait(2)

            with patch("observability.secure_file", side_effect=blocked_secure_file):
                writer = threading.Thread(
                    target=lambda: metrics.write(path, "request", max_bytes=4, status=200)
                )
                writer.start()
                self.assertTrue(entered.wait(1))
                started = time.monotonic()
                metrics.count("http_requests_total")
                metrics.record_http_latency_route("library_page", 0.01)
                self.assertEqual(metrics.snapshot()["http_requests_total"], 1)
                self.assertLess(time.monotonic() - started, 0.25)
                release.set()
                writer.join(2)
            self.assertFalse(writer.is_alive())

    def test_concurrent_log_writes_stay_serialized(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            metrics = Observability()
            inside = []
            widths = []

            def tracking_secure_file(_target):
                inside.append(1)
                widths.append(len(inside))
                time.sleep(0.02)
                inside.pop()

            # Both hardening hooks are tracked: only one of them runs per line depending on
            # whether the file rotated, and the promise is that whichever one is on the write
            # path, it is held inside `_log_lock` so two threads cannot interleave a record.
            with patch("observability.secure_file", side_effect=tracking_secure_file), \
                    patch.object(file_permissions, "secure_file_on_drift",
                                 side_effect=tracking_secure_file):
                writers = [
                    threading.Thread(target=lambda index=index: metrics.write(path, "request", index=index))
                    for index in range(4)
                ]
                for writer in writers:
                    writer.start()
                for writer in writers:
                    writer.join(5)
            self.assertEqual([writer.is_alive() for writer in writers], [False] * 4)
            self.assertEqual(max(widths), 1)
            with open(path, encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle]
            self.assertEqual(sorted(row["index"] for row in rows), [0, 1, 2, 3])

    def test_http_latency_uses_fixed_routes_without_query_or_path_leaks(self):
        self.assertEqual(http_latency_route("/api/library?search=private-song"), "library_page")
        self.assertEqual(http_latency_route("/api/library/items?ids=private-track"), "library_page")
        self.assertEqual(http_latency_route("/cover/a-secret-track-id?token=hidden"), "cover")
        self.assertEqual(http_latency_route("/untrusted/custom/path"), "static")
        metrics = Observability()
        metrics.record_http_latency("/api/library?search=private-song", 0.125)
        snapshot = metrics.snapshot()["http_latency"]
        self.assertEqual(set(snapshot), set(HTTP_LATENCY_ROUTES))
        self.assertEqual(snapshot["library_page"], {"count": 1, "avg_ms": 125.0, "max_ms": 125.0, "slow": 0})
        self.assertNotIn("private-song", repr(snapshot))

    def test_http_latency_tracks_average_maximum_and_slow_requests(self):
        metrics = Observability()
        metrics.record_http_latency("/api/library/groups", 0.2)
        metrics.record_http_latency("/api/library/groups", 1.4)
        summary = metrics.snapshot()["http_latency"]["library_groups"]
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["avg_ms"], 800.0)
        self.assertEqual(summary["max_ms"], 1400.0)
        self.assertEqual(summary["slow"], 1)

    def test_latency_rejects_non_finite_and_custom_metric_values(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("metrics must not coerce custom values")

        self.assertEqual(finite_nonnegative(float("nan")), 0.0)
        self.assertEqual(finite_nonnegative(float("inf")), 0.0)
        self.assertEqual(finite_nonnegative(-2), 0.0)
        self.assertEqual(finite_nonnegative(Explosive()), 0.0)
        metrics = Observability()
        metrics.record_http_latency("/api/library", float("nan"), slow_seconds=Explosive())
        self.assertEqual(metrics.snapshot()["http_latency"]["library_page"], {"count": 1, "avg_ms": 0.0, "max_ms": 0.0, "slow": 0})

    def test_metric_normalizers_reject_huge_integer_overflow(self):
        huge = 10 ** 10000
        self.assertEqual(finite_nonnegative(huge), 0.0)
        self.assertEqual(bounded_counter_increment(huge), 1)

    def test_latency_aggregate_is_bounded(self):
        metrics = Observability()
        metrics.record_http_latency("/api/library", MAX_LATENCY_TOTAL_MS)
        metrics.record_http_latency("/api/library", 1)
        summary = metrics.snapshot()["http_latency"]["library_page"]
        self.assertLessEqual(summary["count"], MAX_COUNTER_VALUE)
        self.assertEqual(summary["max_ms"], MAX_LATENCY_TOTAL_MS)
        self.assertLessEqual(summary["avg_ms"], MAX_LATENCY_TOTAL_MS)

    def test_slow_latency_counter_is_bounded(self):
        metrics = Observability()
        metrics._http_latency["library_page"]["slow"] = MAX_COUNTER_VALUE
        metrics.record_http_latency("/api/library", 2.0)
        self.assertEqual(metrics.snapshot()["http_latency"]["library_page"]["slow"], MAX_COUNTER_VALUE)

    def test_successful_static_reads_do_not_trigger_synchronous_log_writes(self):
        self.assertFalse(should_write_http_request("GET", "/cover/private-song-id?size=160", 200))
        self.assertFalse(should_write_http_request("HEAD", "/media/private-song-id", 206))
        self.assertFalse(should_write_http_request("GET", "/api/playback/status?target_id=local", 200))
        self.assertFalse(should_write_http_request("GET", "/api/playback/events", 200))
        self.assertTrue(should_write_http_request("GET", "/api/library", 200))
        self.assertTrue(should_write_http_request("POST", "/media/private-song-id", 200))
        self.assertTrue(should_write_http_request("GET", "/cover/private-song-id", 404))

    def test_counter_vocabulary_is_bounded(self):
        metrics = Observability()
        self.assertFalse(metrics.count("untrusted-" + "x" * 10000))
        metrics.count("http_requests_total", 2)
        metrics.count("log_write_errors")
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["http_requests_total"], 2)
        self.assertEqual(snapshot["log_write_errors"], 1)
        self.assertNotIn("untrusted-" + "x" * 10000, snapshot)

    def test_counter_deltas_are_finite_bounded_and_do_not_coerce_objects(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("counter deltas must not coerce custom values")

        self.assertEqual(bounded_counter_increment(float("nan")), 1)
        self.assertEqual(bounded_counter_increment(float("inf")), 1)
        self.assertEqual(bounded_counter_increment(-4), 0)
        self.assertEqual(bounded_counter_increment(MAX_COUNTER_INCREMENT + 99), MAX_COUNTER_INCREMENT)
        self.assertEqual(bounded_counter_increment(Explosive()), 1)
        metrics = Observability()
        metrics.count("http_requests_total", Explosive())
        metrics.count("http_requests_total", MAX_COUNTER_INCREMENT + 99)
        self.assertEqual(metrics.snapshot()["http_requests_total"], MAX_COUNTER_INCREMENT + 1)

    def test_counter_total_is_capped_for_long_running_processes(self):
        metrics = Observability()
        metrics._counters["http_requests_total"] = MAX_COUNTER_VALUE
        metrics.count("http_requests_total", MAX_COUNTER_INCREMENT)
        self.assertEqual(metrics.snapshot()["http_requests_total"], MAX_COUNTER_VALUE)

    def test_corrupt_counter_total_isolated_on_increment(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("counter totals must not coerce custom values")

        self.assertEqual(bounded_counter_value(Explosive()), 0)
        metrics = Observability()
        metrics._counters["http_requests_total"] = Explosive()
        metrics.count("http_requests_total", 2)
        self.assertEqual(metrics.snapshot()["http_requests_total"], 2)

    def test_corrupt_latency_summary_isolated_on_record(self):
        metrics = Observability()
        metrics._http_latency["library_page"].update({"count": object(), "total_ms": float("nan"), "max_ms": object(), "slow": -3})
        metrics.record_http_latency("/api/library", 0.25)
        self.assertEqual(metrics.snapshot()["http_latency"]["library_page"], {"count": 1, "avg_ms": 250.0, "max_ms": 250.0, "slow": 0})

    def test_non_positive_slow_threshold_uses_default(self):
        self.assertEqual(positive_threshold(-1), 1.0)
        metrics = Observability()
        metrics.record_http_latency("/api/library", 0.25, slow_seconds=-1)
        self.assertEqual(metrics.snapshot()["http_latency"]["library_page"]["slow"], 0)

    def test_log_file_bytes_are_bounded_without_coercing_custom_values(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("log limits must not coerce custom values")

        self.assertEqual(bounded_log_file_bytes(-10), 1)
        self.assertEqual(bounded_log_file_bytes(10 ** 20), MAX_LOG_FILE_BYTES)
        self.assertEqual(bounded_log_file_bytes(float("nan")), 5 * 1024 * 1024)
        self.assertEqual(bounded_log_file_bytes(Explosive()), 5 * 1024 * 1024)

    def test_non_serializable_fields_are_isolated_from_request_path(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            metrics = Observability()
            metrics.write(path, "request", status=object())
            self.assertEqual(metrics.snapshot()["log_write_errors"], 1)
            self.assertFalse(os.path.exists(path))

    def test_broken_mapping_fields_are_isolated_from_request_path(self):
        class BrokenMapping(dict):
            def items(self):
                raise RuntimeError("mapping unavailable")

        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            metrics = Observability()
            metrics.write(path, "request", detail=BrokenMapping())
            self.assertNotIn("log_write_errors", metrics.snapshot())
            with open(path, encoding="utf-8") as handle:
                row = json.loads(handle.read())
            self.assertEqual(row["detail"], "[UNAVAILABLE_MAPPING]")

    def test_redaction_isolates_broken_mapping_access_directly(self):
        class BrokenMapping(dict):
            def items(self):
                raise RuntimeError("mapping unavailable")

        self.assertEqual(redact(BrokenMapping()), "[UNAVAILABLE_MAPPING]")

    def test_redaction_isolates_broken_sequence_access_directly(self):
        class BrokenSequence(list):
            def __iter__(self):
                raise RuntimeError("sequence unavailable")

        self.assertEqual(redact(BrokenSequence([1])), "[UNAVAILABLE_SEQUENCE]")

    def test_oversized_record_is_replaced_by_a_bounded_summary(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            Observability().write(path, "huge", detail=["x" * MAX_REDACT_STRING] * MAX_REDACT_ITEMS)
            self.assertLessEqual(os.path.getsize(path), MAX_LOG_RECORD_BYTES)
            with open(path, encoding="utf-8") as handle:
                row = json.loads(handle.read())
            self.assertTrue(row["truncated"])

    def test_redaction_bounds_nested_collections_and_strings(self):
        payload = redact({"items": list(range(MAX_REDACT_ITEMS + 4)), "text": "x" * (MAX_REDACT_STRING + 10)})
        self.assertEqual(len(payload["items"]), MAX_REDACT_ITEMS + 1)
        self.assertLessEqual(len(payload["text"]), MAX_REDACT_STRING + len("...[TRUNCATED_STRING]"))

    def test_redaction_keeps_large_mapping_iteration_bounded(self):
        class GuardedMapping(dict):
            def items(self):
                yielded = 0
                for pair in super().items():
                    yielded += 1
                    if yielded > MAX_REDACT_ITEMS + 1:
                        raise AssertionError("mapping was iterated beyond bounded prefix")
                    yield pair
        payload = redact(GuardedMapping({str(i): i for i in range(MAX_REDACT_ITEMS + 1000)}))
        self.assertEqual(len(payload), MAX_REDACT_ITEMS + 1)

    def test_redaction_and_truncation_do_not_stringify_arbitrary_keys_or_events(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("diagnostics must not stringify custom keys/events")

        payload = redact({Explosive(): "value"})
        self.assertEqual(payload["[NON_TEXT_KEY:0]"], "value")
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            Observability().write(path, "huge", detail={Explosive(): "x"})
            with open(path, encoding="utf-8") as handle:
                row = json.loads(handle.read())
            self.assertEqual(row["event"], "huge")
            self.assertEqual(row["detail"]["[NON_TEXT_KEY:0]"], "x")

    def test_redaction_bounds_text_keys(self):
        key = "token_" + "x" * (MAX_REDACT_KEY + 100)
        payload = redact({key: "secret"})
        rendered_key = next(iter(payload))
        self.assertLessEqual(len(rendered_key), MAX_REDACT_KEY + len("...[TRUNCATED_KEY]"))
        self.assertEqual(payload[rendered_key], "[REDACTED]")

    def test_redaction_does_not_lowercase_unbounded_keys(self):
        class HugeKey(str):
            def lower(self):
                raise AssertionError("oversized keys must not be lowercased")
        payload = redact({HugeKey("x" * (MAX_REDACT_KEY + 100)): "value"})
        self.assertEqual(next(iter(payload.values())), "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
