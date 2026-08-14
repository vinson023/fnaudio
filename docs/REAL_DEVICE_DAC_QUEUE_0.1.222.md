# USB DAC queue acceptance: 0.1.222

Date: 2026-08-11

## Device and output

- NAS: `vinson023.eu.org`, fnAudio `0.1.222`.
- Output target: `mpd:usb:0644:804a:00160000386ca1d14e45282720120016:dev0`.
- DAC: TEAC UD-301, `hw:CARD=UD301,DEV=0`.
- Native DSD capability remained verified. DoP is not available on this DAC.

## Queue run

- Generated 20 isolated three-second WAV tracks under
  `/vol1/1000/music/fnaudio-acceptance-20260811` at 44.1, 48, 88.2, 96,
  176.4, 192 and 352.8 kHz.
- Refreshed both fnAudio and MPD library state, then ran
  `tools/real_device_dac_queue_run.sh` with a 0.5-second sample interval.
- Samples: 95. Distinct MPD song IDs: 20. Natural song changes: 19.
- `observed_queue_positions=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]`.
- `queue_traversal_verified=1`, `restore_verified=1`, and maximum underrun
  count was zero.
- The test restored the original 19-item queue, original current item,
  `repeat=off`, `shuffle=false`, and `transport=STOPPED`.

## Cleanup and limits

- The isolated fixture directory was deleted and a library refresh was started.
- Evidence: `artifacts/0.1.222/real-device/fnaudio-dac-queue-0.1.222.log`.
- This proves automated queue traversal and cross-rate PCM switching only. It
  does not prove physical DAC reconnect, background/screen-off continuity,
  DoP-only DSD, DLNA Renderer, AirPlay, or Android acceptance.
