# fnAudio 0.1.33

- Stabilized the playback-target dialog: device discovery refreshes in the
  background and only redraws the list when its contents change.
- Made "search again" explicitly trigger a background discovery pass without
  clearing the devices already shown.
- Kept target ordering stable: browser playback, USB DAC, then UPnP/DLNA
  renderers.
- Removed redundant "set as current" and "current" text. The selected target
  is indicated by the checkmark at the left of its row.
- Selecting a target now updates the checkmark immediately; a failed switch
  restores the previous selection.
