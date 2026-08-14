# Dynamic DAC Queue Run

`tools/real_device_dac_queue_run.sh` replaces the old hard-coded queue recovery procedure for new USB DAC acceptance runs.

Before changing playback it saves `/api/playback/core`, then restores that exact queue, current track, repeat mode and shuffle mode in an exit trap. It fetches the final core snapshot and records `restore_verified=1` only when every saved field, including `transport`, matches again. A failed restoration is evidence of a regression, not a pass.

Run it on the NAS only after selecting the intended MPD USB DAC target. Supply a known-valid test queue from the current library; the script deliberately has no baked-in IDs.

```sh
export FNAUDIO_DAC_TARGET='mpd:usb:<stable-device-id>'
export FNAUDIO_TEST_QUEUE='["first-track-id","second-track-id"]'
export FNAUDIO_QUEUE_SAMPLES=360
sh /path/to/real_device_dac_queue_run.sh /vol1/1000/fnaudio-dac-queue-run.log
```

The test is bounded by `FNAUDIO_QUEUE_SAMPLES * FNAUDIO_QUEUE_INTERVAL`, but exits sampling early when every required position has appeared. It passes only when every zero-based MPD queue position from `0` through the supplied queue length minus one was observed in a status sample. The end of the log must contain both `queue_traversal_verified=1` and `restore_verified=1`; if the sample budget expires before every requested track was reached, the command exits nonzero after restoring the original session. Download the log and summarize it with `tools/analyze_real_device_playback_log.py`. It does not replace the separately observed physical unplug/replug, DoP-only DSD, mobile sleep, Renderer, AirPlay, or Android acceptance cases.
