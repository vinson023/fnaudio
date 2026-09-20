import unittest

from upnp_device_selection import select_upnp_device


class UpnpDeviceSelectionTests(unittest.TestCase):
    def test_selects_first_exact_id(self):
        first = {"id": "renderer-1", "name": "A"}
        self.assertIs(select_upnp_device([first, {"id": "renderer-1", "name": "B"}], "renderer-1"), first)

    def test_skips_invalid_entries_and_missing_ids(self):
        self.assertIsNone(select_upnp_device([None, "bad", {"name": "missing"}], "renderer-1"))
        self.assertIs(select_upnp_device(iter([{"id": "renderer-1"}]), "renderer-1")["id"], "renderer-1")
        self.assertIsNone(select_upnp_device({"id": "renderer-1"}, "renderer-1"))
        self.assertIsNone(select_upnp_device([{"id": "renderer-1"}], None))

    def test_broken_mapping_access_does_not_abort_selection(self):
        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken")

        valid = {"id": "renderer-2"}
        self.assertIs(select_upnp_device([Broken(), valid], "renderer-2"), valid)

    def test_device_iteration_is_bounded(self):
        devices = ({"id": f"renderer-{index}"} for index in range(1000))
        self.assertIsNone(select_upnp_device(devices, "renderer-999"))


if __name__ == "__main__":
    unittest.main()
