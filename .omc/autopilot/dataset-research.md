# Web Research: Public Datasets for RT60 Prediction Validation (roomestim)

_Research date: 2026-05-06 | Facets: 5 | Datasets evaluated: 10_

---

## Executive Summary

No single publicly available dataset satisfies all of roomestim's requirements simultaneously. **BUT Speech@FIT ReverbDB** is the strongest match for multi-room coverage (9 rooms, diverse types, CC-BY 4.0, 8.7 GB RIR-only subset, measured RT60 derivable from RIRs) despite lacking explicit material labels or per-octave-band absorption coefficients. **ACE Challenge corpus** (Zenodo mirror, CC-BY 4.0, ~24.5 GB, 7 rooms) provides T60 per ISO-266 octave band out of the box, making it the easiest drop-in for octave-band validation even though material labels are informal descriptions only. **dEchorate** offers the only dataset with a controlled single-room geometry (6 m × 6 m × 2.4 m), 11 acoustic conditions, and RT60 in 4 octave bands (500–4 kHz), but it is one room and 84 GB total (357 MB processed-RIR subset is usable). A practical E2E workstream should use ACE for octave-band spot checks, BUT ReverbDB for multi-room generalization, and dEchorate's processed-RIR subset for geometry-controlled regression testing.

---

## Detailed Findings

### Facet 1 — dEchorate

**Primary source:** [Zenodo record 5562386](https://zenodo.org/records/5562386) | [Springer paper](https://link.springer.com/article/10.1186/s13636-021-00229-0) | [arXiv 2104.13168](https://arxiv.org/abs/2104.13168)

- **Room:** Single cuboid, **6 m × 6 m × 2.4 m** (86.4 m³). Each of the 6 facets (4 walls + floor + ceiling) can be independently covered by broadband acoustic absorption panels. The floor is always reflective (hard floor, no panel). Conditions are encoded as a 6-bit bitmask (e.g., `000000` = all reflective, `011111` = all but floor absorbent).
- **Acoustic conditions:** 11 distinct panel configurations. RT60 at 1 kHz ranges from **0.14 s** (fully absorbent) to **0.73 s** (fully reflective). Per-octave-band RT60 is tabulated in the paper for **500, 1000, 2000, 4000 Hz**; 125 Hz and 250 Hz bands were excluded because the RIRs lacked sufficient SNR at those frequencies.
- **Materials:** The panels are described as "broadband acoustic absorption panels" (foam/mineral wool type) but exact absorption coefficients per band are not published in the dataset. You would need to back-calculate α from measured RT60 + Sabine, or source manufacturer data sheets.
- **RIRs:** 1 800 annotated multichannel RIRs; 6 arrays × 5 microphones × 6 sources × 11 conditions (approximate).
- **License:** CC-BY 4.0.
- **Size:** Full HDF5 = **83.9 GB**. Processed RIR file only = **357 MB**. Supporting Python scripts: 7 kB.
- **Fetch:** `wget https://zenodo.org/records/5562386/files/dechorate_rir.hdf5` (357 MB processed subset — sufficient for RT60 computation).
- **GT geometry:** Yes — single known cuboid with exact dimensions.
- **GT materials:** Partial — panel on/off binary, not absorption-coefficient table.
- **Measured RT60:** Yes, derivable from RIRs via Schroeder; paper provides estimates.

---

### Facet 2 — BUT Speech@FIT ReverbDB

**Primary source:** [BUT Speech@FIT website](https://speech.fit.vut.cz/software/but-speech-fit-reverb-database) | [arXiv 1811.06795](https://arxiv.org/abs/1811.06795) | [IEEE Xplore](https://ieeexplore.ieee.org/document/8717722/)

- **Rooms:** **9 rooms** of diverse types:

| Room | Dims (m) L×W×H | Vol (m³) | Type |
|------|----------------|-----------|------|
| Q301 | 10.7 × 6.9 × 2.6 | 192 | Office |
| L207 | 4.6 × 6.9 × 3.1 | 98 | Office |
| L212 | 7.5 × 4.6 × 3.1 | 107 | Office |
| L227 | 6.2 × 2.6 × 14.2 | 229 | Stairwell (non-block★) |
| R112 | 4.4 × 2.8 × 2.6 | ~40 | Hotel room |
| CR2 | 28.2 × 11.1 × 3.3 | 1 033 | Conference room |
| E112 | 11.5 × 20.1 × 4.8 | ~900 | Lecture room |
| D105 | 17.2 × 22.8 × 6.9 | ~2 000 | Lecture room |
| C236 | 7.0 × 4.1 × 3.6 | 102 | Meeting room |

★ L227 (stairwell) is non-cuboid — roomestim's convex-hull floor polygon would approximate it poorly.

- **Materials:** Not enumerated in the dataset documentation. Room types suggest carpet/hard floor/drywall but no explicit labels.
- **RT60:** Measured using exponential sine sweep method. Per-octave-band RT60 values are not pre-tabulated in the download but are **derivable from the included RIRs** using Schroeder integration. The arXiv paper (1811.06795) discusses RT60 statistics across rooms.
- **RIRs:** ~1 400 RIRs (31 mics × 5 loudspeaker positions per room average).
- **License:** CC-BY 4.0.
- **Size:** RIR-only package = **8.7 GB**. LibriSpeech retransmission = 117 GB (not needed for RT60 validation).
- **Fetch:** Available from Merlin server at Brno University of Technology — see download links on the BUT website above.
- **GT geometry:** Yes — all room dimensions listed (L × W × H).
- **GT materials:** No.
- **Measured RT60:** Derivable; not pre-computed per octave band.

---

### Facet 3 — ACE Challenge Corpus

**Primary source:** [Zenodo 6257551](https://zenodo.org/records/6257551) | [IEEE DataPort](https://ieee-dataport.org/documents/ace-challenge-2015) | [TASLP paper](https://dl.acm.org/doi/10.1109/TASLP.2016.2577502)

- **Rooms:** **7 rooms** in Imperial College London EEE building:
  1. Office 1 — small, carpeted, 4 chairs
  2. Office 2 — small, carpeted, bookcase
  3. Meeting Room 1 — medium, carpeted, 14 chairs
  4. Meeting Room 2 — large, carpeted, ~30 chairs
  5. Lecture Room 1 — medium, **hard floor**, ~60 chairs
  6. Lecture Room 2 — large, **hard floor**, ~35 tables
  7. Building Lobby — large irregular (coupled café/stairwell)

  Exact L × W × H and volume in Table 1 of the corpus paper (accessible via Zenodo documentation PDF).

- **Materials:** Informal descriptions (carpet vs. hard floor, furnished). No absorption-coefficient table. Carpet rooms map naturally to roomestim's `carpet`; hard-floor rooms to `wood_floor`.
- **RT60:** **Pre-tabulated T60 and DRR** in fullband and **ISO-266 octave bands** (125–8 kHz) are included in the corpus documentation files. This is the key advantage: octave-band T60 is ready to use without post-processing.
- **RIRs:** ~1 000+ RIRs; 48 kHz, 32-bit. Multiple microphone configurations (1-ch, 2-ch, 5-ch, 32-ch spherical).
- **License:** CC-BY-ND 4.0 (Attribution + **No Derivatives**). Note: ND means you cannot redistribute modified versions, but read-only research use is fine.
- **Size:** Single-channel subset = **417 MB**; full 32-ch spherical = 14.2 GB; all configs combined ~24.5 GB on Zenodo.
- **Fetch:** `zenodo_get 6257551` or `wget https://zenodo.org/records/6257551/files/<filename>`. The single-channel archive (~417 MB) is sufficient for RT60 validation.
- **GT geometry:** Yes — room dimensions in corpus docs.
- **GT materials:** Informal only.
- **Measured RT60:** Yes, **pre-tabulated per octave band** — best of all candidates for this criterion.

---

### Facet 4 — MeshRIR

**Primary source:** [Zenodo 5002817](https://zenodo.org/doi/10.5281/zenodo.5002817) | [arXiv 2106.10801](https://arxiv.org/abs/2106.10801) | [Project page](https://www.sh01.org/MeshRIR/)

- **Rooms:** **1 room** (two subdatasets, same physical space).
  - S1-M3969: 7.0 m × 6.4 m × 2.7 m, RT60 ≈ **0.38 s** (broadband).
  - S32-M441: same room, RT60 ≈ **0.19 s** (treated condition).
- **Materials:** Not documented.
- **RT60:** Single broadband estimate only; no per-octave-band table.
- **License:** CC-BY 4.0.
- **Size:** Not stated on project page; estimated hundreds of MB given ~4 000 RIRs.
- **GT geometry:** Yes — single room dimensions known.
- **GT materials:** No.
- **Verdict:** Single room, no octave-band RT60, no materials — disqualified for generalization testing.

---

### Facet 5 — MIT IR Survey (Traer & McDermott 2016)

**Primary source:** [MIT McDermott Lab](https://mcdermottlab.mit.edu/Reverb/IR_Survey.html) | [PNAS 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5137703/)

- **Rooms:** **271 locations** sampled from volunteers' daily environments (offices, restaurants, bathrooms, streets, etc.).
- **Materials:** None — locations are informally named.
- **RT60:** Not pre-tabulated. Can be estimated from RIRs.
- **GT geometry:** None — no floor plans or dimensions provided.
- **License:** CC-BY 4.0.
- **Size:** Small (~tens of MB for 271 mono WAV files).
- **Verdict:** No geometry data. **Fails roomestim's #1 requirement.** Useful only for statistical RT60 distribution studies.

---

### Facet 6 — ARNI (Aalto Variable Acoustics Room)

**Primary source:** [Zenodo 6985104](https://zenodo.org/records/6985104) | [Aalto research portal](https://research.aalto.fi/en/datasets/dataset-of-impulse-responses-from-variable-acoustics-room-arni-at/)

- **Rooms:** **1 room** (variable acoustics lab "Arni" at Aalto University, Espoo).
- **Conditions:** 5 342 configurations of 55 switchable absorption panels. 132 037 RIRs total.
- **RT60:** Estimated from RIRs; example values at 500 Hz / 1 kHz / 2 kHz ≈ 0.50 / 0.54 / 0.68 s (medium reverberance). Full per-octave tables in the companion paper "Calibrating the Sabine and Eyring formulas" (JASA).
- **Materials:** Panels in reflective or absorptive binary state — not mapped to roomestim's material enum.
- **License:** CC-BY 4.0.
- **Size:** ~50.9 GB (5 zip files by panel count).
- **Verdict:** Single room, 51 GB, no material labels. Overkill for roomestim's needs.

---

### Facet 7 — Motus (Aalto, 2021)

**Primary source:** [Zenodo 4923187](https://zenodo.org/records/4923187) | [I3DA paper](https://ieeexplore.ieee.org/document/9610933/) | [Aalto portal](https://research.aalto.fi/en/datasets/motus-a-dataset-of-higher-order-ambisonic-room-impulse-responses-)

- **Rooms:** **1 room** — seminar room at Aalto University, **4.9 m × 4.4 m × 2.9 m** (~63 m³). 830 furniture configurations × 4 source-receiver setups = 3 320 RIRs. 3D models and 360° photos included.
- **Materials:** Not labeled. Furniture placement is varied but surface materials not enumerated.
- **RT60:** Reverberation time analysis shown in paper; not pre-tabulated per octave band in dataset files.
- **License:** CC-BY 4.0.
- **Size:** 63.6 GB total (raw_rirs.zip = 22.2 GB; 3d_models.zip = 136 MB; best_of.zip sample = 461 MB).
- **GT geometry:** Single known room with 3D models — good geometry, but single room.
- **Verdict:** Single room, no material labels, 63 GB. The 3D models are attractive for geometry pipeline testing but fail the multi-room criterion.

---

### Facet 8 — OpenAIR (York University)

**Primary source:** [openair.hosted.york.ac.uk](https://www.openair.hosted.york.ac.uk/?page_id=36) | [York Research Database](https://pure.york.ac.uk/portal/en/datasets/openair--the-open-acoustic-impulse-response-library)

- **Rooms:** Many spaces (churches, cathedrals, concert halls, outdoor courtyards) — not primarily indoor rectangular rooms.
- **Materials:** Not systematically documented.
- **RT60:** Per-octave-band RT60 provided for many entries (31.25 Hz through 16 kHz).
- **GT geometry:** Absent or non-standardized. Spaces are often non-rectangular.
- **License:** Per-entry CC variants; most CC-BY 4.0, some CC-BY-SA.
- **Size:** Distributed — individual downloads per venue.
- **Verdict:** Excellent RT60 data, terrible geometry coverage. Not useful for roomestim's geometry + RT60 co-validation.

---

### Facet 9 — GIR Dataset (ETH Zurich, 2023)

**Primary source:** [Zenodo 5288744](https://zenodo.org/records/5288744) | [ScienceDirect paper](https://www.sciencedirect.com/science/article/pii/S0003682X23001317) | [ETH Research Collection](https://www.research-collection.ethz.ch/handle/20.500.11850/587342)

- **What it is:** NOT a room dataset. It is a surface-acoustics dataset: 900k+ IRs from 2 952 positions across 312 **3D-printed surface samples** (foam, wood, QRD panels) measured robotically.
- **Rooms:** N/A — anechoic/semi-anechoic measurement of surface panels.
- **RT60:** Not applicable.
- **License:** GPL v3.0.
- **Size:** ~3.7 GB.
- **Verdict:** Mismatched to roomestim's needs. Useful only as a material absorption-coefficient reference library — not for room-level RT60 validation.

---

### Facet 10 — Real Acoustic Fields / RAF (Meta CVPR 2024)

**Primary source:** [arXiv 2403.18821](https://arxiv.org/html/2403.18821v1) | [GitHub](https://github.com/facebookresearch/real-acoustic-fields) | [CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Chen_Real_Acoustic_Fields_CVPR_2024_CVPR_2024_paper.html)

- **Rooms:** **1 room** in two furniture configurations (empty + furnished). 47k RIRs (empty) + 39k (furnished) = 86k total.
- **Materials:** Explicitly absent — authors state they "remove the acoustic coefficient context due to the unavailability of material coefficient annotations."
- **RT60:** Measured; T60 distribution shown in paper but not pre-tabulated per octave band.
- **GT geometry:** High-fidelity 3D reconstruction (NeRF-quality visual + audio), but only 1 room.
- **License:** Not stated clearly in the arXiv paper; check GitHub repo license file before use.
- **Size:** Very large (86k RIRs at 48 kHz / 32-bit = estimated 50–100 GB).
- **Verdict:** Single room, no materials, uncertain license, large size. Not suitable.

---

## Comparison Table

| Dataset | Rooms | GT Geometry | GT Materials | Octave-band α | Measured RT60 | License | Size (usable subset) | Fetch URL | Last Updated |
|---------|-------|-------------|--------------|---------------|--------------|---------|----------------------|-----------|--------------|
| **BUT ReverbDB** | 9 | Yes — L×W×H all rooms | No | No | Derivable from RIRs | CC-BY 4.0 | 8.7 GB (RIR-only) | [speech.fit.vut.cz](https://speech.fit.vut.cz/software/but-speech-fit-reverb-database) | 2019 |
| **ACE Challenge** | 7 | Yes — dims in corpus docs | Informal (carpet/hard floor) | No α table; T60 per ISO octave band pre-tabulated | Yes, pre-tabulated | CC-BY-ND 4.0 | 417 MB (1-ch) – 24.5 GB (all) | [Zenodo 6257551](https://zenodo.org/records/6257551) | 2022 (Zenodo mirror) |
| **dEchorate** | 1 (11 conditions) | Yes — 6×6×2.4 m cuboid | Partial (panels on/off, no α table) | RT60 at 500/1k/2k/4k Hz | Yes, derivable; paper estimates | CC-BY 4.0 | 357 MB (processed RIRs) | [Zenodo 5562386](https://zenodo.org/records/5562386) | 2021 |
| **MeshRIR** | 1 | Yes — 7×6.4×2.7 m | No | No | Single broadband only | CC-BY 4.0 | ~hundreds MB | [Zenodo 5002817](https://zenodo.org/doi/10.5281/zenodo.5002817) | 2021 |
| **MIT IR Survey** | 271 locations | No | No | No | Derivable | CC-BY 4.0 | ~tens MB | [MIT McDermott Lab](https://mcdermottlab.mit.edu/Reverb/IR_Survey.html) | 2016 |
| **ARNI (Aalto)** | 1 | Yes (layout drawing) | No (panel on/off only) | Partial (JASA companion paper) | Yes, derivable | CC-BY 4.0 | 50.9 GB total | [Zenodo 6985104](https://zenodo.org/records/6985104) | 2022 |
| **Motus (Aalto)** | 1 | Yes — 4.9×4.4×2.9 m + 3D model | No | No | Derivable | CC-BY 4.0 | 63.6 GB (461 MB sample) | [Zenodo 4923187](https://zenodo.org/records/4923187) | 2021 |
| **OpenAIR** | Many (non-rectangular) | No | No | No | Yes, per octave band | Mixed CC | Per-venue | [openair.york.ac.uk](https://www.openair.hosted.york.ac.uk/?page_id=36) | Ongoing |
| **GIR (ETH)** | N/A (surfaces) | N/A | Yes (surface panels) | Yes (surface-level) | N/A | GPL v3.0 | 3.7 GB | [Zenodo 5288744](https://zenodo.org/records/5288744) | 2023 |
| **RAF (Meta)** | 1 (2 configs) | Partial (3D reconstruction) | No (explicitly absent) | No | Derivable | Unclear | ~50–100 GB est. | [GitHub](https://github.com/facebookresearch/real-acoustic-fields) | 2024 |

---

## Top-3 Ranked Recommendations

### Rank 1 — BUT Speech@FIT ReverbDB

**Justification against priority list:**
1. **GT 3D geometry** (Priority 1 — Required): All 9 rooms have published L × W × H dimensions, directly usable as roomestim input polygons for cuboid rooms. Non-cuboid room L227 (stairwell) should be excluded.
2. **GT material labels** (Priority 2 — Strongly preferred): NOT provided. This is the main gap. You would assign roomestim's material enum manually based on room type (offices → `wall_painted` + `wood_floor`; hotel room → `carpet`; lecture rooms → `ceiling_drywall`). This is auditable and defensible for a v0.2 validation.
3. **Octave-band α** (Priority 3 — Strongly preferred): Not provided directly. Derive α from measured RT60 + Sabine inversion; or use Vorländer Appendix A tables by material type.
4. **Measured RT60** (Priority 4 — Required): RIRs are measured via exponential sine sweep. Schroeder integration yields T20/T30 per octave band. No pre-computation required — standard `pyroomacoustics.measure_rt60()` works on the provided WAV files.
5. **Multiple rooms** (Priority 5 — Strongly preferred): **9 rooms**, the most of any candidate. Covers offices, hotel, conference, lecture, meeting — good diversity.
6. **License** (Priority 6 — Required): CC-BY 4.0. Compatible with research use and redistribution.
7. **Linux-fetchable** (Priority 7 — Required): HTTP download from Merlin server (Brno University). Direct wget-able.
8. **Size** (Priority 8 — Preferred <50 GB): **8.7 GB RIR-only** — fits comfortably. LibriSpeech retransmission (117 GB) is unnecessary.

**Gap:** No material labels means you cannot validate material inference, only geometry + RT60. Acceptable for a v0.1 E2E check.

---

### Rank 2 — ACE Challenge Corpus

**Justification against priority list:**
1. **GT 3D geometry** (Priority 1): Room dimensions in corpus documentation PDF (Table 1). 7 rooms — smaller set than BUT but still satisfies ≥3 requirement.
2. **GT material labels** (Priority 2): Informal only — carpet vs. hard floor described in text. Maps to `carpet` / `wood_floor` for floor surface; walls described as office/meeting room typical (→ `wall_painted`). Not machine-readable.
3. **Octave-band α** (Priority 3): Not provided as α values, but **octave-band T60 is pre-tabulated** in the corpus docs at ISO-266 preferred bands. This is the key advantage — you can directly compare roomestim's predicted per-band RT60 against ground truth without running Schroeder integration yourself.
4. **Measured RT60** (Priority 4): Yes — directly available.
5. **Multiple rooms** (Priority 5): 7 rooms; Building Lobby is irregular (coupled spaces) — exclude for Sabine model validation.
6. **License** (Priority 6): CC-BY-**ND** 4.0. The NoDerivatives clause means you cannot redistribute modified versions, but using the data as-is for validation is fine. **Do not redistribute preprocessed derivatives publicly without checking.**
7. **Linux-fetchable** (Priority 7): Zenodo mirror (record 6257551) is direct HTTP. Single-channel archive is 417 MB — trivially CI-fetchable.
8. **Size** (Priority 8): 417 MB for 1-ch (sufficient). All configs ~24.5 GB.

**Key advantage over Rank 1:** Pre-tabulated per-octave T60 values save post-processing work and are citable as ground truth.

---

### Rank 3 — dEchorate (processed RIR subset)

**Justification against priority list:**
1. **GT 3D geometry** (Priority 1): Single room with **exact known cuboid geometry** (6 m × 6 m × 2.4 m). Best-controlled geometry of all candidates.
2. **GT material labels** (Priority 2): Panel on/off bitmask tells you which surfaces are treated (absorbed) vs. reflective. No absorption-coefficient table. Suggests: reflective panels → `wall_painted` or `wall_concrete`; absorptive panels → approximate with high-α tiles.
3. **Octave-band α** (Priority 3): RT60 at 500/1k/2k/4k Hz — 125 and 250 Hz excluded due to low SNR. Four bands is sufficient for most Sabine validation purposes.
4. **Measured RT60** (Priority 4): Yes, derivable from RIRs; estimates in paper.
5. **Multiple rooms** (Priority 5): **Only 1 room** — fails this criterion. Useful as a regression test fixture, not for generalization.
6. **License** (Priority 6): CC-BY 4.0.
7. **Linux-fetchable** (Priority 7): Zenodo, direct HTTP. Processed RIR file = 357 MB.
8. **Size** (Priority 8): **357 MB** (processed subset) — smallest usable download of any candidate.

**Best use case:** Controlled single-room regression test where geometry is perfectly known — ideal for isolating material-model errors from geometry errors.

---

## Fetch / Setup Instructions for Rank 1 (BUT ReverbDB)

### Download (RIR-only, 8.7 GB)

```bash
# Visit the dataset page to get the current direct download URL (Merlin server):
# https://speech.fit.vut.cz/software/but-speech-fit-reverb-database
# The RIR-only archive is listed as BUT_ReverbDB_rel_19_06_RIR-Only.tgz

wget -O BUT_ReverbDB_rel_19_06_RIR-Only.tgz \
  "<URL from BUT website — requires direct copy from page>"

tar -xzf BUT_ReverbDB_rel_19_06_RIR-Only.tgz
```

> **Note:** The Merlin server URL requires copying the direct link from the BUT website; it is not a stable cited URL in this report. Visit https://speech.fit.vut.cz/software/but-speech-fit-reverb-database to retrieve it.

### Expected disk footprint

- Compressed: 8.7 GB
- Extracted: ~12–15 GB estimated (WAV files at 16/48 kHz)

### Minimal subset for CI

To test on 2 rooms only (e.g., Q301 + R112 — the most architecturally distinct):

```bash
# After extraction, RIRs are organized per room:
ls BUT_ReverbDB/Q301/  # office
ls BUT_ReverbDB/R112/  # hotel room
# Copy only those two directories for a ~1-2 GB CI subset
```

### Computing RT60 from RIRs (Schroeder integration, T20/T30 convention)

```python
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
import pyroomacoustics as pra   # pip install pyroomacoustics

def compute_rt60_per_octave(rir_path, bands=[125, 250, 500, 1000, 2000, 4000], sr=None):
    """
    Returns dict of {band_hz: T20_seconds} using Schroeder backwards integration.
    Uses pyroomacoustics measure_rt60 which implements ISO 3382 T20/T30.
    """
    rir, fs = sf.read(rir_path)
    if rir.ndim > 1:
        rir = rir[:, 0]  # take first channel
    if sr and fs != sr:
        raise ValueError(f"Sample rate mismatch: got {fs}, expected {sr}")

    rt60s = {}
    for band in bands:
        # Octave-band filter around center frequency
        rt60 = pra.experimental.measure_rt60(
            rir, fs=fs, decay_db=20,  # T20 convention
            plot=False, rt60_tgt=None
        )
        # For per-band: apply octave bandpass filter first
        from scipy.signal import butter, sosfilt
        lo, hi = band / np.sqrt(2), band * np.sqrt(2)
        sos = butter(4, [lo / (fs / 2), hi / (fs / 2)], btype='band', output='sos')
        rir_band = sosfilt(sos, rir)
        rt60_band = pra.experimental.measure_rt60(rir_band, fs=fs, decay_db=20)
        rt60s[band] = rt60_band

    return rt60s

# Example:
# rt60 = compute_rt60_per_octave("BUT_ReverbDB/Q301/MicID01/SpkID01_01.wav")
# print(rt60)  # {125: 0.42, 250: 0.38, 500: 0.35, ...}
```

**Convention note:** T20 (decay_db=20) is the most reliable for measured RIRs with moderate noise floors. T30 (decay_db=30) may be used if SNR > 45 dB. T60 by direct extrapolation (T20 × 3) is standard per ISO 3382-1.

---

## Risks and Gotchas

### BUT ReverbDB
- **No material labels.** You must manually assign roomestim material enums to each room. This is a human-introduced bias — document the assignments explicitly in your test fixtures.
- **Non-cuboid rooms.** L227 (stairwell, non-block shape) will give large Sabine errors — exclude or treat as out-of-distribution.
- **Server availability.** Download is from a university Merlin server (not Zenodo/figshare). URL stability is not guaranteed long-term; cache locally or mirror.
- **Per-octave RT60 not pre-computed.** You must run Schroeder integration yourself. At 125 Hz, RIR length may be insufficient for reliable T20 — check SNR per room.

### ACE Challenge Corpus
- **CC-BY-ND license.** You cannot publish derived/processed versions of the corpus. Keep validation scripts separate from data. Fine for internal CI.
- **Building Lobby** room has coupled spaces (café, stairwell) — Sabine model is known to underperform; exclude from main validation, use as stress test.
- **T60 values in corpus docs are fullband + 1/3-octave**, not exactly 1-octave. roomestim uses 1-octave bands; you may need to average adjacent 1/3-octave values.
- **Access via Zenodo:** The 2022 Zenodo mirror (record 6257551) is CC-BY 4.0 (the original IEEE DataPort listing is CC-BY-ND); confirm which license applies to the Zenodo files before downstream use — **verify independently**.

### dEchorate
- **84 GB full dataset.** Only download the 357 MB processed RIR file (`dechorate_rir.hdf5`) for RT60 validation. The full HDF5 is only needed for echo-arrival annotation tasks.
- **125/250 Hz bands unreliable.** The room is small (6 × 6 × 2.4 m) and the measurement SNR at low frequencies was insufficient. Do not validate roomestim's 125/250 Hz Sabine predictions against dEchorate.
- **Single room.** Cannot show generalization. Use only as a regression fixture.
- **Material absorption coefficients not published.** To validate material models, you'd need to either (a) invert RT60 + Sabine to get α, or (b) source panel manufacturer data sheets. Option (a) is circular if you're using Sabine to predict RT60.

### MeshRIR
- Single room, no octave-band RT60, no materials. **Do not use for roomestim validation.** Useful only if you want a dense spatial grid for transfer-function validation.

### MIT IR Survey
- No geometry data at all. **Disqualified** for roomestim's primary use case.

### OpenAIR
- Most spaces are non-rectangular (cathedrals, concert halls). Sabine is a poor model for these. RT60 data is per octave band which is useful, but without geometry roomestim cannot be evaluated.

### GIR Dataset
- This is a **surface-panel** acoustics dataset, not a room dataset. It could serve as a lookup table for material absorption coefficients (to cross-check roomestim's built-in α values), but it cannot be used for end-to-end RT60 validation.

### ARNI
- Single room at 51 GB. If you only need RT60 vs. geometry validation, this is excessive. If you want to study how Sabine accuracy degrades with increasing absorption, ARNI's 5 342 configurations are unique — but that is a different research question than roomestim's E2E test.

---

## Sources

**A. Official Dataset Records / Primary Papers**

- [dEchorate Zenodo record 5562386](https://zenodo.org/records/5562386) — 2021
- [dEchorate Springer EURASIP JASMP paper](https://link.springer.com/article/10.1186/s13636-021-00229-0) — 2021
- [dEchorate arXiv 2104.13168](https://arxiv.org/abs/2104.13168) — 2021
- [BUT ReverbDB website](https://speech.fit.vut.cz/software/but-speech-fit-reverb-database) — 2019
- [BUT ReverbDB arXiv 1811.06795](https://arxiv.org/abs/1811.06795) — 2018
- [BUT ReverbDB IEEE Xplore](https://ieeexplore.ieee.org/document/8717722/) — 2019
- [ACE Challenge Zenodo 6257551](https://zenodo.org/records/6257551) — 2022
- [ACE Challenge IEEE DataPort](https://ieee-dataport.org/documents/ace-challenge-2015) — 2015
- [ACE Challenge TASLP paper](https://dl.acm.org/doi/10.1109/TASLP.2016.2577502) — 2016
- [MeshRIR Zenodo 5002817](https://zenodo.org/doi/10.5281/zenodo.5002817) — 2021
- [MeshRIR arXiv 2106.10801](https://arxiv.org/abs/2106.10801) — 2021
- [MeshRIR project page](https://www.sh01.org/MeshRIR/) — 2021
- [ARNI Zenodo 6985104](https://zenodo.org/records/6985104) — 2022
- [ARNI Aalto research portal](https://research.aalto.fi/en/datasets/dataset-of-impulse-responses-from-variable-acoustics-room-arni-at/) — 2022
- [Motus Zenodo 4923187](https://zenodo.org/records/4923187) — 2021
- [Motus I3DA paper IEEE Xplore](https://ieeexplore.ieee.org/document/9610933/) — 2021
- [Motus Aalto research portal](https://research.aalto.fi/en/datasets/motus-a-dataset-of-higher-order-ambisonic-room-impulse-responses-) — 2021
- [GIR Dataset Zenodo 5288744](https://zenodo.org/records/5288744) — 2023
- [GIR Dataset ScienceDirect paper](https://www.sciencedirect.com/science/article/pii/S0003682X23001317) — 2023
- [GIR ETH Research Collection](https://www.research-collection.ethz.ch/handle/20.500.11850/587342) — 2023
- [Real Acoustic Fields arXiv 2403.18821](https://arxiv.org/html/2403.18821v1) — 2024
- [Real Acoustic Fields GitHub](https://github.com/facebookresearch/real-acoustic-fields) — 2024
- [Real Acoustic Fields CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Chen_Real_Acoustic_Fields_CVPR_2024_paper.html) — 2024
- [MIT IR Survey homepage](https://mcdermottlab.mit.edu/Reverb/IR_Survey.html) — 2016
- [MIT IR Survey PNAS paper (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5137703/) — 2016
- [OpenAIR IR Data page](https://www.openair.hosted.york.ac.uk/?page_id=36) — ongoing
- [OpenAIR York Research Database](https://pure.york.ac.uk/portal/en/datasets/openair--the-open-acoustic-impulse-response-library) — ongoing

**B. Aggregator / Reference Lists**

- [room-impulse-responses GitHub (RoyJames)](https://github.com/RoyJames/room-impulse-responses) — curated RIR dataset list
- [Aalto Acoustics Lab datasets GitHub](https://github.com/AaltoAcousticsLab/aalto-datasets) — Aalto datasets index

---

## Recommendations

1. **Use ACE corpus (Zenodo 6257551, single-channel, 417 MB) as the primary octave-band RT60 validation target.** It is the only candidate with pre-tabulated per-octave T60 values, is Linux-fetchable via `zenodo_get`, requires no post-processing to obtain ground-truth RT60, and covers 7 rooms. Exclude the Building Lobby room from Sabine-model comparison. Verify the Zenodo copy license (CC-BY 4.0 vs. CC-BY-ND) before publishing derivatives.

2. **Use BUT ReverbDB (RIR-only, 8.7 GB) for multi-room generalization testing.** Download the tgz from the BUT Merlin server. Select 6 of the 9 rooms excluding L227 (stairwell). Assign material enums manually and document the mapping. Compute RT60 per octave band using `pyroomacoustics.experimental.measure_rt60` with octave-band filtering. Validate roomestim's Sabine predictions against these computed values.

3. **Use dEchorate processed RIR subset (357 MB, Zenodo 5562386) as a geometry-controlled regression fixture.** The exact cuboid geometry eliminates one source of uncertainty. Use only 500–4 kHz bands. Lock one commit's predictions as a baseline; future commits must not regress by more than ±10% RT60 relative error.

4. **Consider GIR dataset (Zenodo 5288744, GPL v3.0) as a material absorption-coefficient reference** if roomestim's built-in α table needs cross-checking. It does not provide room-level RT60 but does provide measured surface IR → α for known panel geometries.

5. **For a future v0.3 octave-band material sweep:** Combine BUT ReverbDB geometry + manually assigned materials with Vorländer Table A absorption coefficients (standard acoustics reference) as a surrogate for measured per-band α. This gives an auditable, reproducible material model baseline without needing a dataset that provides both geometry and per-octave α simultaneously (no such public dataset was found).

---

## Additional Research Needed

- **Confirm BUT ReverbDB direct download URL stability** — the Merlin server URL is not a DOI; verify it resolves before scripting CI fetch.
- **ACE corpus Zenodo license clarification** — the original 2015 IEEE DataPort listing says CC-BY-ND 4.0, but the 2022 Zenodo mirror record states CC-BY 4.0. Confirm with dataset authors whether the Zenodo copy has a genuinely different license or if it is an error.
- **dEchorate panel absorption coefficients** — if you need per-octave α for material model validation, contact the authors (Diego Di Carlo) or search for the panel manufacturer's data sheet. The paper cites "broadband acoustic panels" without product name.
- **Newer 2023–2025 multi-room datasets with geometry + RT60 + materials** — a gap search in November 2025 found no public dataset satisfying all three simultaneously. This gap may represent a contribution opportunity for roomestim itself.
- **BUT ReverbDB RT60 at 125 Hz** — at small room volumes (R112, ~40 m³; L207, 98 m³) the RIR length may be too short for reliable 125 Hz T20. Pre-screen before including low-frequency bands in validation metrics.
