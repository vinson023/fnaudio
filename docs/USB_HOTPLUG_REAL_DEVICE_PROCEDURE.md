# Physical USB DAC hot-plug acceptance procedure

This procedure is for P0 target 2. It captures only a real cable/device action;
do not use sysfs `unbind`/`bind` as a substitute.

1. Start a known PCM track through the selected USB DAC.
2. Upload and run `tools/real_device_usb_hotplug_capture.sh` on the NAS.
3. Physically unplug the DAC cable and wait until the log records that the ALSA
   card disappeared and fnAudio/MPD entered its protected state.
4. Reconnect the same DAC and wait for its stable USB identity and ALSA device
   to reappear. Verify queue, current track, transport and underrun behaviour.
5. Download `/vol1/1000/fnaudio-usb-hotplug-0.1.205.log` and summarize it with
   `tools/analyze_real_device_playback_log.py` where applicable.

The acceptance evidence must include actual absence and reappearance, not merely
an MPD restart or a simulated kernel event.
