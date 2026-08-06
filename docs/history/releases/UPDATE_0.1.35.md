# fnAudio 0.1.35

- Prevented an older device-list response from overwriting a newly selected
  playback target.
- While backend state is catching up after a target switch, keep the selected
  marker stable and request a fresh status update in the background.
