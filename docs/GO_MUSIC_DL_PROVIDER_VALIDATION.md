# go-music-dl Provider Real-Network Validation

Date: 2026-08-11

## Scope and method

This is a live, read-only validation of the provider functions registered by the locally cached `go-music-dl` project, not a mock or a hand-written HTTP probe. The reference project is pinned to its local `music-lib` dependency commit `3c4c32fd2aff2ffb9737856e52a45fd46b7ca12d`.

The harness at `references/go-music-dl/cmd/provider-smoke/main.go` called the following exported provider registries for every source:

- `GetSearchFunc(source)` with `Hotel California Eagles`
- `GetLyricFunc(source)` using the first returned, real song ID
- `GetAlbumSearchFunc(source)` with the same query
- `GetAlbumDetailFunc(source)` using the first returned, real album ID

Raw JSONL evidence is retained at `artifacts/go-music-dl-provider-smoke-20260811.jsonl`. Each record includes the source, capability, result count or lyric byte count, latency, and any provider error. The portable Go 1.25.1 runtime used for this test is isolated under `_external/runtime/go-clean`.

An item is considered usable for a capability only when its full operation returned non-empty data. For lyrics and album details this means the request was made with an ID returned by the immediately preceding live search.

## Registered sources

`go-music-dl` registers 13 sources in total: 12 online sources plus `local`.

| Source | Search | Lyrics after search | Album search | Album detail after search | Assessment |
| --- | --- | --- | --- | --- | --- |
| NetEase | 7 | 5403 bytes | 10 | 9 | Fully usable in the final repeatable probe |
| QQ | 3 | 6225 bytes | 10 | 9 | Fully usable in this probe |
| Kugou | 10 | 9223 bytes | no albums | not reached | Search and lyrics usable; album search failed |
| Kuwo | no result | not reached | 10 | 15 | Album metadata usable; song/lyrics query failed in this network/query |
| Migu | 9 | 2663 bytes | 20 | no playable songs | Search and lyrics usable; album detail did not yield playable tracks |
| 5sing | 10 | not found | not supported | not supported | Search only for this query |
| Jamendo | 20 | empty | 20 | 6 | Album metadata usable; lyrics empty for this returned song |
| JOOX | 22 | 2589 bytes | 3 | 12 | Fully usable in this probe |
| Qianqian | 7 | 1777 bytes | 1 | 1 | Fully usable in this probe; album search was slow (4110 ms) |
| Soda | JSON parse failure | not reached | 17 | 10 | Album metadata usable; current song-search parser/API contract failed |
| Bilibili | 19 | empty | not an album source | not an album source | Search only for this query |
| Apple | dynamic token unavailable | not reached | dynamic token unavailable | not reached | Not usable without refreshing the provider token extraction |

## Summary

- Complete search-to-lyrics success: NetEase, QQ, Kugou, Migu, JOOX, Qianqian (6/12).
- Search works but the queried song produced no lyrics: 5sing, Jamendo, Bilibili (3/12). These are not suitable as an unconditional lyric fallback.
- Complete album-search-to-detail success: NetEase, QQ, Kuwo, Jamendo, JOOX, Qianqian, Soda (7/10 album sources).
- Clearly unavailable in this run: Apple (dynamic token extraction failed).
- Provider/API incompatibility observed: Soda song search returned truncated or changed JSON (`unexpected end of JSON input`).

The result is time- and network-dependent. It proves that a provider path worked at test time; it does not prove permanent availability, regional entitlement, or that an arbitrary search result is the intended recording. The current harness also does not validate downloadable audio URLs because fnAudio uses these providers for metadata recovery, not audio delivery.

## Integration recommendation

Use only sources with a positive capability result as opt-in fallback candidates and retain title/artist scoring before accepting their metadata. For the current fnAudio metadata pipeline, the most defensible next additions are Migu, JOOX and Qianqian lyrics/album adapters. NetEase, QQ and Kugou are already validated as the most reliable Chinese-music fallbacks in this probe. Do not add Apple or Soda song search until their upstream provider implementations are repaired and this test passes again.

Before promoting any new source into the packaged runtime, run this command again and preserve a new dated JSONL artifact:

```powershell
Set-Location C:\path\to\fnAudio\references\go-music-dl
$env:PATH = "C:\path\to\fnAudio\_external\runtime\go-clean\go\bin;$env:PATH"
$env:GOMODCACHE = 'C:\path\to\fnAudio\_external\runtime\gomodcache-clean'
$env:GOCACHE = 'C:\path\to\fnAudio\_external\runtime\gocache-clean'
go run .\cmd\provider-smoke | Tee-Object C:\path\to\fnAudio\artifacts\go-music-dl-provider-smoke-YYYYMMDD.jsonl
```
