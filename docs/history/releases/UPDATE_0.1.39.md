# fnAudio 0.1.39

- Started Phase 4 server-side state storage.
- Favorites and playlists are now stored in the fnAudio application data
  directory and synchronized to browsers after the first migration.
- Added a standalone SQLite state database and state API, separate from the
  music-library scan index.
