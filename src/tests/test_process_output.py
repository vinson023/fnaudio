import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from process_output import check_output_bounded


class ProcessOutputTests(unittest.TestCase):
    def test_rejects_unbounded_or_invalid_inputs(self):
        for args, max_bytes, timeout in [
            ("echo test", 1, 1),
            ([], 1, 1),
            (["echo"], 0, 1),
            (["echo"], 1, 0),
            (["echo"], 1, float("inf")),
        ]:
            with self.subTest(args=args, max_bytes=max_bytes, timeout=timeout):
                with self.assertRaises(ValueError):
                    check_output_bounded(args, max_bytes=max_bytes, timeout=timeout)

    def test_rejects_fractional_or_overflowing_output_limits(self):
        for value in (1.5, 10 ** 10000):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    check_output_bounded(["echo"], max_bytes=value, timeout=1)

    @unittest.skipIf(os.name == "nt", "process groups are verified on POSIX")
    def test_timeout_kills_process_group(self):
        process = mock.Mock()
        process.pid = 123
        process.wait.side_effect = [subprocess.TimeoutExpired("probe", 0.01), None]
        with mock.patch("process_output.subprocess.Popen", return_value=process), \
             mock.patch("process_output.os.killpg") as killpg:
            with self.assertRaises(subprocess.TimeoutExpired):
                check_output_bounded(["probe"], max_bytes=1, timeout=0.01)
        killpg.assert_called_once_with(123, mock.ANY)
        self.assertTrue(process.wait.call_count >= 2)

    def test_uses_isolated_session_for_real_probe(self):
        process = mock.Mock()
        process.wait.return_value = 0
        process.returncode = 0
        with mock.patch("process_output.subprocess.Popen", return_value=process) as popen:
            self.assertEqual(check_output_bounded(["probe"], max_bytes=1, timeout=1), b"")
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_nonzero_exit_matches_check_output_contract(self):
        process = mock.Mock()
        process.wait.return_value = 7
        process.returncode = 7
        with mock.patch("process_output.subprocess.Popen", return_value=process):
            with self.assertRaises(subprocess.CalledProcessError) as failure:
                check_output_bounded(["probe", "--version"], max_bytes=10, timeout=1)
        self.assertEqual(failure.exception.returncode, 7)
        self.assertEqual(failure.exception.cmd, ["probe", "--version"])

    def test_output_limit_is_enforced_while_process_is_running(self):
        process = mock.Mock()
        process.pid = 123
        process.poll.side_effect = [None, 0]
        process.wait.return_value = 0

        def start(_command, stdout, **_kwargs):
            stdout.write(b"x" * 2)
            stdout.flush()
            return process

        with mock.patch("process_output.subprocess.Popen", side_effect=start), \
             mock.patch("process_output._terminate_process_tree") as terminate:
            with self.assertRaisesRegex(RuntimeError, "output is too large"):
                check_output_bounded(["probe"], max_bytes=1, timeout=1)
        terminate.assert_called_once_with(process)

    @unittest.skipIf(os.name == "nt", "process groups are verified on POSIX")
    def test_unexpected_output_error_kills_process_group(self):
        process = mock.Mock()
        process.pid = 456
        process.poll.return_value = None
        process.wait.side_effect = [RuntimeError("wait failed"), None]
        with mock.patch("process_output.subprocess.Popen", return_value=process), \
             mock.patch("process_output.os.killpg") as killpg, \
             mock.patch("process_output.tempfile.TemporaryFile") as temp_file:
            output = temp_file.return_value.__enter__.return_value
            output.tell.side_effect = RuntimeError("temporary file failed")
            with self.assertRaisesRegex(RuntimeError, "temporary file failed"):
                check_output_bounded(["probe"], max_bytes=1024, timeout=1)
        killpg.assert_called_once_with(456, mock.ANY)
        self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
