import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from dlna.upmpdcli_renderer import upmpdcli_probe


class UpmpdcliRendererTests(unittest.TestCase):
    @mock.patch("dlna.upmpdcli_renderer.upmpdcli_version", return_value="upmpdcli 1.8")
    @mock.patch("dlna.upmpdcli_renderer.process_running", return_value=True)
    @mock.patch("dlna.upmpdcli_renderer.upmpdcli_binary", return_value="/usr/bin/upmpdcli")
    def test_probe_is_explicitly_non_managed_and_non_selectable(self, _binary, _running, _version):
        result = upmpdcli_probe()

        self.assertEqual(result["role"], "compatibility_probe_only")
        self.assertFalse(result["managed_by_fnaudio"])
        self.assertFalse(result["selectable_output"])
        self.assertFalse(result["owns_audio_device"])


if __name__ == "__main__":
    unittest.main()
