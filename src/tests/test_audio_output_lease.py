import sys
import unittest

sys.path.insert(0, "app/server")

from services.audio_output_lease import AudioOutputLease


class AudioOutputLeaseTests(unittest.TestCase):
    def test_conflicting_backend_cannot_own_same_device(self):
        lease = AudioOutputLease()
        self.assertTrue(lease.acquire("mpd", "usb:test")["ok"])
        blocked = lease.acquire("alsa-direct", "usb:test")
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["owner"], "mpd")
        self.assertTrue(lease.release("mpd"))
        self.assertTrue(lease.acquire("alsa-direct", "usb:test")["ok"])


if __name__ == "__main__":
    unittest.main()
