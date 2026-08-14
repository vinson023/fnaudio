# MPD playback error taxonomy

`src/app/server/playback/mpd_errors.py` is the authoritative, pure classifier.
It accepts captured MPD log text or a command exception and does not require a
running MPD instance.

| Category | Domain | Automatic recovery |
| --- | --- | --- |
| `source_missing`, `source_corrupt` | media | No |
| `seek_failed` | transport | No |
| `decoder_unavailable`, `decoder_failed` | decoder | No |
| `output_device_missing` | output | Device monitor handles reconnect; no blind restart |
| `output_device_busy`, `output_io_failed` | output | Throttled backend restart |
| `output_format_unsupported` | output | No |
| `buffer_underrun` | output | Throttled backend restart and legacy underrun count |
| `queue_stale` | queue | Existing database refresh/retry path |
| `database_unavailable` | database | Wait/retry |
| `backend_unavailable`, `command_failed` | backend | Caller decides from `retryable` |

`playback_errors` is the current status contract. Each item includes category,
domain, severity, retryable, action, message and occurrences. Repeated lines are
coalesced, recent unique errors win the bounded result, and `by_category`
retains occurrence counts. `decoder_errors` remains a compatibility projection
for media, seek and decoder clients.

The local Volumio and moOde references rely on MPD/ALSA logs and plugin output
boundaries but do not provide a general reusable classifier. Their seek-mute
and hardware-mixer patterns are evaluated separately from fault attribution.

Verification:

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_offline.ps1
```

The completion run passed 201 Python tests plus all JavaScript and Node UI
checks. Physical DAC behavior remains covered only by the separate hardware
acceptance list.
