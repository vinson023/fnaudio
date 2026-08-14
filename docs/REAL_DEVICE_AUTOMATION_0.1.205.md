# Real-device automation handoff — 0.1.205

This run keeps the seven P0 targets active without claiming hardware evidence that is not available.

## Active jobs

- Long DAC playback runner: `/tmp/fnaudio-long-play-0.1.205.sh`, PID `110676`.
- Persistent log: `/vol1/1000/fnaudio-long-play-0.1.205.log`.
- Follow-up runner: `/tmp/real_device_short_queue_after_long.sh`.
- Follow-up log: `/vol1/1000/fnaudio-short-queue-0.1.205.log`.

The follow-up waits for the long runner to exit, then loads 20 short tracks (about 36m 28s total), samples MPD status for up to 50 minutes, finishes early once all 20 queue items have been observed, stops playback, restores the known 20-track queue with the original STOP state, and records a post-restore MPD status sample.

## Recovery after a deleted session

```sh
tail -n 20 /vol1/1000/fnaudio-long-play-0.1.205.log
tail -n 20 /vol1/1000/fnaudio-short-queue-0.1.205.log
ps -ef | grep -E 'fnaudio-long-play|real_device_short_queue' | grep -v grep
```

Do not mark targets 2–7 complete from these logs alone: physical USB removal, DoP-only hardware, an external DLNA Renderer, Android device matrices, formal signing, and the complete App Center uninstall/data-retention matrix still need their respective real environments.

To summarize a downloaded log locally:

```powershell
python C:\path\to\fnAudio\tools\analyze_real_device_playback_log.py C:\path\to\fnAudio\artifacts\0.1.205\real-device\fnaudio-long-play-0.1.205.log
```
