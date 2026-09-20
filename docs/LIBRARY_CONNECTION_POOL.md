# Library index connection pool

`library_connection_pool` decides whether a read of the library index may reuse an
idle SQLite handle instead of opening the database again. Opening the WAL index
costs more than reading it: the first-screen breakdown recorded in `CHANGELOG_AI.md`
(2026-09-17, 100,000-track fixture) measured a cold 120-row page at 2.67ms with
1.46ms of it spent inside `library_db_connect()` alone. The pool therefore keeps up
to four idle handles per database and eight in total (see
`library_connection_pool.LibraryConnectionPool`).

## Setting

| Key | Type | Default | Where it is read |
| --- | --- | --- | --- |
| `library_connection_pool` | JSON boolean | `true` | `library._library_connection_pool_enabled()` on every read; `config.py` owns the default |

- The default is `config.DEFAULT_LIBRARY_CONNECTION_POOL` and is applied by
  `load_config()`. No startup path injects the key: an injected value would be a
  second source of truth that `save_config()` and every other configuration reader
  cannot see.
- Only a real JSON boolean changes it. Text (`"false"`, `"0"`) and numbers do not
  disable the pool; `_strict_bool()` keeps such values at the default, the same rule
  every other boolean setting follows.
- `save_config()` writes the key, so a value an operator put into `config.json`
  survives a settings save and a restart.

## Turning it off

Set `"library_connection_pool": false` in `config.json` before the next start, or
change it on a running service. Either way the value only reaches the read path
through one door: `server.commit_config_update()` is the only place that replaces
the live configuration dictionary while the service is running (`server.main()`
assigns the dictionary once, before the listener starts), and it calls
`library.apply_library_connection_pool_config()` right after that commit. That call
is the guarantee behind the switch: when the setting is off, handles already parked
in the pool are closed, so the service cannot sit in the state "the configuration
says pooling is disabled while idle handles keep `library.sqlite3` open". The drain
is scoped to the database the committed config names; a config that cannot name one
drains everything, because "off" never leaves a handle behind.

The commit-time drain is the re-poolable one. It never closes the pool for good, so
switching back on takes effect without a restart. The one-way drain
(`library.stop_library_connections()`) stays reserved for `shutdown_runtime()`, where
it runs last, after every component that can still reach the index.

## Observing it

`/api/health` and `/api/diagnostics` report `library.connection_pool` from
`library_connection_pool_status()`: `idle`, `databases`, `reuses`, `creations`,
`closures` and the two ceilings. A disabled switch is provable there, not just
asserted: `idle` stays at zero and none of the counters move, because the read path
never touches the pool while the setting is off.

## Exposing it further

There is deliberately no settings-page control for this key. It is an operations
switch, and a wrong click costs first-screen latency rather than correctness. If a
future UI toggle is wanted, it has to route through `commit_config_update()` so the
drain above stays the only place where the switch can move; anything that mutates
`server.config` directly would reintroduce the state this document describes as
forbidden.

## Verification

```powershell
Set-Location C:\path\to\fnAudio\src
python -B -m unittest tests.test_config tests.test_library_sqlite tests.test_library_connection_pool tests.test_server_lifecycle
```

The offline gate (`tools\test_offline.ps1`) runs the same suites. Nothing in this
document claims device behaviour: how long an idle handle blocks a cache-volume
unmount on fnOS is still unmeasured.
