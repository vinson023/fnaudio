# FNOS-API Third-Party Reference Evaluation

> Evaluated: 2026-08-06  
> Upstream: `https://github.com/heijiangangqin/FNOS-API`  
> Cached revision: `33101767e01a7f413cac5e0ed016f6a9483df526` (`main`, 2026-07-21)  
> Cache location: `C:\path\to\fnAudio\references\FNOS-API-upstream`  
> Status: Useful as an external validation and operations reference. Not approved
> as a fnAudio runtime dependency or embedded service.

## 1. What This Repository Is

This repository is a third-party fnOS application named `fnos-api`. It runs a
Node.js/Express service on port `9932` and turns bundled `trim-cli` commands
into an HTTP REST interface. It is not an official fnOS SDK and it does not
provide a new native media, DLNA, MPD, or ffmpeg API for fnAudio.

The exposed REST groups include authentication, file management, application
center operations, downloads, logs, users, storage, Docker, and CPU/memory
monitoring. Behind those endpoints it invokes `trim-cli` through `execFile`.
It therefore offers a convenience HTTP layer over NAS management operations,
not a stable application-integration contract.

The cached upstream declares `nodejs_v22`, listens on `0.0.0.0:9932`, uses an
x86_64 `trim-cli` binary on the NAS, and claims fnOS `1.1.3107+` compatibility.
It is MIT licensed according to its README. The cache is a shallow clone and
must remain a reference-only directory; it is never part of the fnAudio FPK.

## 2. Difference From Official fnOS Documentation

The official developer documentation is centered on building a correctly
integrated fnOS application rather than exposing NAS administration through a
new HTTP gateway.

| Area | Official fnOS capability | Third-party FNOS-API | Implication for fnAudio |
| --- | --- | --- | --- |
| Application packaging | Documents `manifest`, `config/resource`, `config/privilege`, lifecycle scripts, dependency declarations, runtime variables, CGI and wizard integration. | Is itself one example FPK application using those mechanisms. | Keep fnAudio's official FPK integration as the source of truth. Do not copy its packaging blindly. |
| Application permissions | Uses declared API scopes, application users, ACL-backed authorization, a front-end JS SDK, and a backend API token. | Logs into the NAS as a configured NAS user through `trim-cli` and exposes the resulting management operations as REST. | fnAudio should retain its direct scoped authorization flow. |
| File access | Official docs require an application to declare only required scopes and still respect the current user's ACL after a folder is authorized. | Provides broad file, sharing, copy, move, delete, and ACL commands. | Useful to inspect and test a device; unsuitable for normal player UI or backend access. |
| UI and page integration | Documents `@trimjs/web-app`, page routing, platform configuration and micro-app behavior. | Serves a minimal static page; no reusable SDK abstraction beyond its REST API. | No front-end component or API layer should be adopted. |
| Device administration | Public official API navigation covers authorization/files, page capability, platform configuration and error handling. | Adds a practical wrapper for app center, logs, monitoring, downloads, users, storage and Docker by delegating to `trim-cli`. | Useful for external test automation, but these calls are operational and version-sensitive. |
| Runtime contract | Scoped and documented for applications. | Depends on bundled `trim-cli` behavior and a NAS WebSocket endpoint. | Treat as third-party tooling, not a stable production dependency. |

Official references consulted:

- `https://developer.fnnas.com/docs/core-concepts/manifest/`
- `https://developer.fnnas.com/docs/core-concepts/resource/`
- `https://developer.fnnas.com/docs/core-concepts/privilege/`
- `https://developer.fnnas.com/docs/core-concepts/environment-variables/`
- `https://developer.fnnas.com/api/calling/`
- `https://developer.fnnas.com/api/authorization/overview/`

## 3. Relationship to Existing fnAudio Implementation

fnAudio already follows the official application-facing path for its current
need: `config/resource` declares `trim.file.sharedAccess`, and
`src/app/server/fnos_api.py` sends a scoped, token-authenticated request to the
fnOS local open-gateway socket. It uses that capability only to query and
remove shared accessible music folders.

The third-party service cannot replace that design without making fnAudio
depend on a second application, a Node.js runtime, an HTTP management port,
and stored NAS credentials. It also does not improve the playback core, music
library, transcode pipeline, DLNA roles, MPD integration, or the existing CGI
proxy.

## 4. Recommended Uses

Use the cached source as a separate, opt-in development or acceptance-test
harness reference:

1. Compare app-center status, start/stop, update and manual FPK installation
   flows with the existing local `tools/trim-cli` workflow.
2. Collect device log listings/exports after a failed install, MPD startup
   failure, or lifecycle-script issue.
3. Capture system, CPU and memory data while exercising large-library scans or
   transcode load, then correlate it with fnAudio's own logs.
4. Use its documented `trim-cli` argument mappings as a cross-check when
   writing read-only device smoke tests.

For this project, invoke `C:\path\to\fnAudio\tools\trim-cli` directly for any approved
device action. It avoids adding a permanent HTTP gateway and is already the
tooling path documented under `references/SKILL.md`.

## 5. Do Not Integrate It Into fnAudio

- Do not bundle its Node.js runtime, Express dependencies, `trim-cli` binaries,
  demo scripts, or REST server into the fnAudio FPK.
- Do not call its port `9932` from the fnAudio browser UI or server.
- Do not use NAS administrator credentials as an application configuration
  mechanism.
- Do not expose storage, Docker, user, application-center, arbitrary file, or
  logger mutation endpoints through fnAudio.
- Do not run the repository's `demo/` scripts against a shared test device
  without a task-specific approval and validated targets; several perform
  deletion, storage, user and application changes.

## 6. Security and Reliability Findings

These findings explain why the repository must remain reference-only. They are
based on the cached commit, not a claim about future upstream versions.

1. The service binds to `0.0.0.0` and enables unrestricted CORS. A bearer token
   is its sole application-level protection.
2. The fallback bearer token is the predictable literal `fnosapi2024`, also
   prefilled in the installation/configuration forms.
3. `POST /api/auth/login` is outside the bearer-token middleware, while the
   process can perform NAS-management operations after login.
4. NAS username, NAS password and REST bearer token are written as plaintext
   JSON under the package variable directory. The lifecycle scripts substitute
   wizard values with `sed`, so values containing replacement metacharacters
   are not robustly JSON-escaped.
5. Many endpoints automatically append `--yes` or `-y` to destructive actions:
   application install/update/uninstall, file removal/move/copy, user changes,
   storage operations, Docker lifecycle and image removal.
6. It lacks endpoint-level roles, operation-specific confirmation, schema
   validation, request audit trails, rate limits, CSRF protection and a clear
   credential-rotation mechanism.
7. `execFile` avoids shell-string command injection in the wrapper itself, but
   broad command authority still makes a leaked token or unintended browser
   request high impact.

These issues mirror and amplify fnAudio's existing P0 concern about an
unauthenticated management surface. They are a reason to prioritize fnAudio's
own authentication and least-privilege work, not a shortcut around it.

## 7. Cache Maintenance

Before using this reference for a future decision, record the revision and
review the upstream diff. Do not use an unreviewed update as implementation
authority.

```powershell
Set-Location C:\path\to\fnAudio\references\FNOS-API-upstream
git status --short --branch
git rev-parse HEAD
git fetch --depth 1 origin main
git log --oneline HEAD..origin/main
```

Only after reviewing the diff should the cached reference be fast-forwarded.
No credentials, NAS sessions, downloaded release package, runtime config, or
generated demo output belongs in this cache.
