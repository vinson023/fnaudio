# fnAudio 0.1.41

- Queue mutations now wait for Playback Core confirmation before the UI updates.
- Queue add, remove, single-track play and play-all/group/folder actions share
  the same server-confirmed state path.
- Repeat and shuffle state is persisted after confirmed playback commands.
