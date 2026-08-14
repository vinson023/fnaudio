# Resource limits and recovery context

This document records the completed first item of the 2026-08-11 continuous
offline engineering sequence. It is intended to survive deletion of the Codex
conversation.

## Runtime bounds

| Setting | Default | Accepted range |
| --- | ---: | ---: |
| `metadata_max_pending_jobs` | 20000 | 100-200000 |
| `metadata_cache_max_bytes` | 512 MiB | 16 MiB-8 GiB |
| `transcode_queue_max_jobs` | 64 | 1-1000 |
| `transcode_cache_max_bytes` | 2 GiB | 64 MiB-64 GiB |
| `cache_min_free_bytes` | 512 MiB | 64 MiB-16 GiB |
| `ffmpeg_max_concurrency` | 2 | 1-8 |
| `ffmpeg_job_timeout_seconds` | 900 seconds | 30-3600 seconds |
| `scan_timeout_seconds` | 3600 seconds | 60-86400 seconds |

Current-song metadata and transcode work may evict the worst pending ordinary
job when a queue is full. Running jobs are never evicted. Artwork eviction
clears its entity reference and expiry so a later lookup can fetch it again.
Scan cancellation or timeout leaves the last valid library index untouched.

The scan cancellation endpoint is `POST /api/library/scan/cancel`; it requires
the existing `settings.write` scope. `/api/health` reports only bounded counts
and limits.

## Verification

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_offline.ps1
```

The completion run passed 192 Python tests, JavaScript syntax validation, five
Node UI regressions and `git diff --check`. No fnOS, DAC, Renderer, AirPlay or
Android physical-device claim is made by this result.
