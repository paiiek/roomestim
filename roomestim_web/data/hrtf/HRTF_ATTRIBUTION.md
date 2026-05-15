# HRTF dataset attribution

This directory bundles two HRTF SOFA files for the roomestim-web binaural demo.

## PRIMARY: HUTUBS HRTF database (TU Berlin)

- Subject: `pp1` (canonical first subject)
- File: `hutubs_pp1.sofa`
- License: CC BY 4.0 (attribution required)
- Citation: Brinkmann F. et al., "The HUTUBS HRTF database", TU Berlin, 2019.
  https://depositonce.tu-berlin.de/handle/11303/9429
- SHA-256: TBD-recorded-at-data-bundle-commit

## FALLBACK: MIT KEMAR

- File: `kemar.sofa`
- License: Public Domain (no attribution legally required; provided for courtesy)
- Source: Gardner W., Martin K., "HRTF Measurements of a KEMAR Dummy-Head
  Microphone", MIT Media Lab, 1994. https://sound.media.mit.edu/resources/KEMAR.html
- SHA-256: TBD-recorded-at-data-bundle-commit

## Populating these files

The SOFA files are NOT bundled in this repository commit (file-size + license-clarity gate). Run `python scripts/fetch_web_data.py` for the latest download protocol, or fetch manually from the URLs above and place at:
  - `roomestim_web/data/hrtf/hutubs_pp1.sofa`
  - `roomestim_web/data/hrtf/kemar.sofa`

After populating, record their SHA-256 hashes in this file and run `pytest -m web` to refresh the golden binaural regression.
