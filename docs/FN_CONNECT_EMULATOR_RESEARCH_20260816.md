# FN Connect Android emulator research (2026-08-16)

## Scope

This note records dynamic and static analysis of the official fnOS Android app
`1.33.4` (`com.trim.app`) on an Android 14 emulator. It is intentionally
limited to FN Connect discovery, connection selection, login state, and the
feasibility of reusing the bundled P2P library. No fnAudio product code was
changed during this investigation.

Sensitive credentials, NAS tokens, P2P tokens, visit secrets, and complete
authentication headers are not included in this document.

## Confirmed official flow

1. The user enters an FN ID. The identity shown in login history remains the
   FN ID; it is not replaced with the selected IP address.
2. The app calls `https://fnos.net/api/v1/fn/con`.
3. The response publishes local/private addresses, public IPv4, public IPv6,
   an FN domain endpoint, and HTTP/HTTPS ports.
4. With HTTPS enabled, the app probes the HTTPS candidates rather than trying
   HTTP first.
5. The app probes multiple candidate groups concurrently or with a short
   staged delay. It does not use the first item in the response unconditionally.
6. In the captured successful run, both published IPv6 addresses accepted a
   TCP connection. The app retried the lower-latency candidate and selected it
   for NAS authentication.
7. After selecting an endpoint, the app performs normal NAS authentication and
   obtains a fresh NAS token for that endpoint.
8. The successful session was shown as `Public connection`. The app kept two
   established HTTPS connections to the selected IPv6 endpoint.
9. Public direct mode did not listen on `127.0.0.1:9018`; that listener belongs
   to the P2P/relay path.

### Captured timing

The native packet capture shows the following sequence relative to the FN ID
request:

- `+0 ms`: DNS for `fnos.net`
- `+40 ms`: TLS to the FN Connect discovery service
- `+520 ms`: probe private IPv4 on the published HTTPS port
- `+570 ms`: probe public IPv4 on the published HTTPS port
- `+1.54 s`: parallel probes to both public IPv6 addresses
- `+1.71 s`: TLS probe to `<fn-id>.fnos.net:443`
- `+1.85 s`: retry of the faster IPv6 candidate
- `+2.12 s`: NAS login over the selected IPv6 HTTPS endpoint

This is consistent with a staged Happy Eyeballs style selection process: all
official candidates remain eligible, successful endpoints are ranked, and the
winning address can change between sessions.

## Discovery response schema

The live response from `/api/v1/fn/con` contained these fields:

```text
data.ddns
data.ipv4[]
data.ipv6[]
data.publicIpv4[]
data.publicIpv6[]
data.fn[]
data.port.httpPort
data.port.httpsPort
data.checkSum
data.ver
data.forbbidPublicIpv6
```

For the tested FN ID, `data.fn` was an FN domain endpoint with explicit port
`443`, while the published NAS ports were `5666` for HTTP and `5667` for HTTPS.
The private IPv4, public IPv4, both public IPv6 addresses, and FN domain were
all observed in the native connection trace.

## Official persisted state

The official login database is:

```text
/data/user/0/com.trim.app/app_flutter/TRIM/Login/login_info_db
```

The successful FN Connect row confirms this separation:

```text
inputAddress       = <FN ID>
cleanInputAddress  = <FN ID>
host               = <selected endpoint for this session>
port               = <selected port>
loginType          = 2
fnId               = <FN ID>
https              = 1
uid                 = <NAS uid>
```

The table also contains token and secret fields, but those values must never be
logged or treated as FN Connect discovery credentials. A NAS token is endpoint
session state; the FN ID is the durable connection identity.

## Native P2P implementation

The official APK includes only an `arm64-v8a` native build:

```text
lib/arm64-v8a/libgojni.so
```

Static symbols and Go build paths identify:

```text
git.teiron-inc.cn/infra/trimp2p-sdk@v0.6.8
git.teiron-inc.cn/infra/trimconlib@v0.1.40
```

The library exposes two JNI APIs:

- `trimcon.Trimcon`: legacy V1 configuration using individual setters.
- `tpps.Tpps`: V2 configuration using `applyConfigJSON`, with QUIC, STUN,
  visit server, visitor name, token, and visit secret fields.

The official Flutter plugin supports `connectConfig`, `startWithPort`,
`startWithSocket`, `connectStatus`, and `stop`. A connected P2P session exposes
a loopback proxy, normally `127.0.0.1:9018`, and the app then points its normal
NAS API stack at that proxy.

The AOT code references the configuration endpoints:

```text
/api/v1/visit/info
/api/v1/visit/domain
```

These endpoints are separate from `/api/v1/fn/con`. The discovery response does
not contain the dynamic P2P token, visit secret, STUN server, and control server
configuration needed to start Tpps.

### Reuse smoke test

An isolated test APK is stored under:

```text
_external/apk-analysis/trimp2p-smoke
```

It packages the official dex bindings and `libgojni.so` under a different
application ID. On the x86_64 Android 14 emulator, the app is assigned the
`arm64-v8a` ABI through Android native translation, but initializing the Go
library outside the official process terminates with `SIGILL` inside the
translation layer. The official app itself runs the same library successfully.

This result does not prove that reuse fails on a physical arm64 device. It does
prove that copying the binary is not yet a portable implementation and that
release work must include a physical arm64 smoke test, lifecycle tests, and an
ABI fallback. It also explains why an x86 emulator cannot be the only gate for
the P2P path.

## Gaps in the current fnAudio resolver

`android-client/.../FnConnectResolver.java` currently differs from the official
behavior in several important ways:

1. It consumes `publicIpv4` and `publicIpv6`, but ignores `ipv4`, `ipv6`,
   `ddns`, `fn`, and `forbbidPublicIpv6`.
2. It probes candidates sequentially. One unreachable address can add the full
   socket timeout before the next candidate is considered.
3. It always places HTTP before HTTPS in its endpoint list. This can downgrade
   a login even when the user selected HTTPS.
4. It returns the first reachable address instead of racing successful
   candidates and selecting the best result.
5. Cancellation stops the discovery HTTP call, but it cannot immediately stop
   socket probes already running in the response callback.
6. Its fallback always uses the first public address and HTTP port, so the
   fallback can disagree with both the user preference and the live official
   result.
7. It does not represent discovery identity, candidate addresses, selected
   transport, and NAS authentication as separate lifecycle states.

## Recommended fnAudio design

The direct-connect implementation should be split into four responsibilities:

```text
FN ID
  -> FnConnectDiscoveryClient
  -> DiscoverySnapshot with all published candidates
  -> EndpointProbeCoordinator
  -> selected EndpointCandidate
  -> FnOsAuthClient obtains a fresh NAS session
  -> fnAudio WebView and playback services use that session
```

### Discovery model

Keep an immutable snapshot containing:

- original FN ID
- private IPv4/IPv6 candidates
- public IPv4/IPv6 candidates
- FN domain and DDNS candidates with explicit ports
- published HTTP and HTTPS ports
- server version/checksum flags
- discovery timestamp

Do not store a resolved IP as the durable profile identity.

### Candidate selection

- Respect the user's HTTP/HTTPS choice. HTTPS uses the published HTTPS port;
  HTTP uses the published HTTP port.
- Treat an explicit `data.fn` port as authoritative for that domain candidate.
- Probe candidates on a bounded executor with per-attempt cancellation.
- Start private/LAN candidates immediately, public candidates concurrently,
  and the FN domain after a short delay.
- Rank successful probes by route class, security preference, and measured
  latency. Do not trust response array order.
- Re-run discovery on login, history selection, network change, and recovery
  from endpoint failure.
- Generate a fresh NAS authentication session after endpoint selection. Never
  reuse a discovery result as a NAS token.

### Optional P2P/relay adapter

The existing product decision is to prefer public direct access and not depend
on relay. Keep that policy. If P2P is restored later, implement it as an
optional `FnConnectTransport` adapter behind the same NAS authentication API:

```text
DirectTransport -> selected public/private endpoint
TppsTransport   -> 127.0.0.1:<allocated local port>
```

Do not enable Tpps until all of the following are available:

- authenticated acquisition of `/api/v1/visit/info` and
  `/api/v1/visit/domain`
- secure in-memory handling of dynamic token and visit secret
- physical arm64 loading and lifecycle tests
- explicit stop/restart on network changes and app logout
- a non-arm64 fallback that returns to public direct discovery

## Implementation order

1. Add a typed discovery response model and fixture tests for every observed
   field.
2. Pass the selected HTTP/HTTPS mode into resolution; remove implicit HTTP-first
   behavior.
3. Add cancellable parallel candidate probing and deterministic ranking tests.
4. Include private, public, FN domain, and DDNS candidates.
5. Persist only the FN ID as connection identity and keep the selected endpoint
   as replaceable session state.
6. Re-resolve on network changes and invalid/expired NAS sessions.
7. Validate successful FN ID login, library loading, playback, and history
   switching on a physical arm64 Android device.
8. Treat P2P/relay as a separate later milestone, not as a condition for public
   FN Connect support.

## Evidence locations

```text
_external/apk-analysis/fnconnect-native-api34.pcap
_external/apk-analysis/fnconnect-native-api34-login.logcat.txt
_external/apk-analysis/fnconnect-success-api34.logcat.txt
_external/apk-analysis/fnconnect-emulator-api34.mitm
_external/apk-analysis/fnos-1.33.4-source
_external/apk-analysis/fnos-1.33.4-native
_external/apk-analysis/trimp2p-smoke
```

The packet capture and login logs may contain network identifiers or session
material. Keep them local and redact them before sharing.

## Relay validation and fnAudio integration

The follow-up relay test forced the official app away from every published NAS
endpoint by applying UID-scoped IPv4 and IPv6 rules for ports 5666/5667. The
official app then established Tpps V2 over QUIC and exposed the NAS at
`127.0.0.1:9018`. A fresh `user.login` through that loopback endpoint returned a
new NAS session, and the authenticated fnAudio `/api/health` request returned
the real MPD, library, metadata and transcode component state. This proves the
relay transports normal fnOS WebSocket and third-party CGI traffic, not only
the official UI.

Dynamic configuration is issued by the signed public endpoint:

```text
POST https://fnos.net/api/v1/visit/info
```

It uses the same `fn-sign` and path-bound `authx` scheme as
`/api/v1/fn/con`. The response's `applyServer` object provides the Tpps token,
visit secret, QUIC server, STUN server and protocol; `data.nasId` is the visit
server identity. Hash-only runtime interception confirmed that the returned
token and visit secret exactly match the values passed by the official app to
`Tpps.applyConfigJSON`. Neither value is a NAS short token, long token or login
database secret.

fnAudio Android now includes:

- the official ARM64 `libgojni.so` and complete gomobile `go.Seq` runtime;
- signed, cancellable `/api/v1/visit/info` acquisition;
- in-memory-only Tpps V2 configuration mapping;
- a process-scoped tunnel manager with a dynamically allocated loopback port;
- direct endpoint probing first, relay fallback second, and published-address
  fallback when the native tunnel cannot run;
- login-history and `MainActivity` recovery through the same resolver.

The x86_64 Android 14 emulator can run the official Flutter package under its
native translation layer, but a standalone Java fnAudio process executing the
same Go library reaches `SIGILL`. fnAudio therefore enables Tpps only when the
device's primary ABI and runtime are both ARM64. The emulator validates config
signing/parsing and safe fallback; final tunnel loading, login, playback and
network-change lifecycle remain an ARM64 physical-device acceptance item.

Additional local evidence:

```text
_external/apk-analysis/fnconnect-relay-forced.pcap
_external/apk-analysis/fnconnect-relay-config-20260816.mitm
_external/apk-analysis/hook_tpps_config.js
_external/apk-analysis/fnaudio-0.1.226-source
```
