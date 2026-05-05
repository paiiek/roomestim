This is a placeholder/sample dataset for unit testing only. Set ROOMESTIM_E2E_DATASET_DIR to your real ACE Challenge directory for actual E2E verification.

The T60 values in ace_corpus_t60.csv and ace_corpus_t60_500hz.csv are SYNTHETIC PLACEHOLDERS — they are NOT real ACE Challenge measurements. They exist solely to exercise the adapter code path in CI without requiring the actual dataset (CC-BY-ND 4.0, ~24.5 GB).

To obtain the real ACE Challenge corpus:
  zenodo_get 6257551
  # or: wget https://zenodo.org/records/6257551/files/<archive>

Then set: export ROOMESTIM_E2E_DATASET_DIR=/path/to/your/ace_corpus_dir
And run:  pytest -m e2e -s tests/test_e2e_ace_challenge_rt60.py
