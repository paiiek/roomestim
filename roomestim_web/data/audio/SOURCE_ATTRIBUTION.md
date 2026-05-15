# Source audio attribution

## Clip: `source.wav`

- Format: 30.0 s mono, 48 kHz, 16-bit PCM RIFF/WAV (~2.88 MB).
- Source: LibriVox.org (public-domain audiobook reading).
- License: Public Domain (LibriVox dedication).
- Specific clip URL: TBD — pending data-bundle commit.
- Trim command:
  ```
  ffmpeg -i <upstream_clip>.mp3 -ss 0 -t 30 -ar 48000 -ac 1 \
         -sample_fmt s16 source.wav
  ```
- SHA-256: TBD-recorded-at-data-bundle-commit

## Populating this file

The 30-second clip is NOT bundled in this repository commit. Run
`python scripts/fetch_web_data.py` for the download protocol.
