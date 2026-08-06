# fnAudio 0.1.24

## USB DAC real-device format coverage

- Added WMA / WMA Lossless to the indexed music-library formats.
- Bumped the metadata index version so existing WMA files are discovered by the next background scan.
- Verified on the real TEAC UD-301 USB DAC through the app-private MPD output:
  - AIFF and WAV: 44.1 kHz PCM.
  - WMA Lossless: 96 kHz PCM.
  - FLAC: the 384 kHz / 24-bit test source is delivered at 352.8 kHz PCM, which is the maximum rate exposed by this Linux ALSA driver.
  - DFF and DSF: native DSD64 (`DSD_U32_BE`, 88.2 kHz transport rate).
- Verified that Stop closes the ALSA playback handle after each test.
