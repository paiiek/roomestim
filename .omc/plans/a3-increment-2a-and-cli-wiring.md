# A3 increment 2a (blind-rt60 sim benchmark) + measure-rt60 CLI wiring — v0.51.0

RESUME POINTER. Baseline before: 767p/7s @ v0.50.1 (pushed). Target: v0.51.0 MINOR additive.

## Context (verified this session)
- v0.49.0 shipped `[audio]` extra + `roomestim/reconstruct/measured_rt60.py` (library-only; CLI
  DEFERRED because cli.py had concurrent-session contention). That contention is RESOLVED (multiview
  committed in v0.50.x; `git status` shows cli.py clean).
- `tests/eval/blind_rt60_benchmark.py` (untracked) is COMPLETE and verified-working:
  controlled pyroomacoustics sim, impulsive-clap excitation, GT = Schroeder RT60 of the sim RIR.
  Result (n=5): **MAPE 8.7%, bias -8.5%, MAE 135 ms, max |err| 17.8%**; negative control
  (steady noise, no decay tail) diverges to **39.5 s** — caveat confirmed. Writes to
  `.omc/research/_data/blind_rt60_benchmark_results.md` (gitignored).
- ADR 0055 §Reverse-criterion already names this work: increment 2 = ACE bench + Acta + CLI wiring.
  This session ships **2a (controlled-SIM bench, no external download) + CLI wiring**.
  **2b = ACE measured-corpus (CC-BY-ND, Zenodo 6257551) + Acta Acustica closed-form correction
  stays DEFERRED** (external download; measured-room end-to-end error).

## Deliverables (all additive, MINOR → v0.51.0)
1. **Commit the benchmark** `tests/eval/blind_rt60_benchmark.py` as-is (out-of-gate: no `test_*`
   functions, `__main__` entrypoint only — NOT collected by the default gate).
2. **CLI wiring — new `measure-rt60` subcommand** in `roomestim/cli.py`:
   - parser `_add_measure_rt60_parser(sub)`: `--audio PATH` (required; wav/flac/ogg),
     `--json` (optional flag; emit machine-readable JSON instead of human text).
     Register in `_build_parser()` (after `_add_structure_parser`).
   - handler `_cmd_measure_rt60(args)`:
     - `from roomestim.reconstruct.measured_rt60 import measure_rt60_from_audio`
     - call it; on success: human mode prints `RT60 (broadband, measured): <x> s`, method, source,
       sample_rate_hz, n_samples to stdout, and the disclosure NOTE to stderr (prefix `NOTE: `,
       same convention as other disclosure notes). `--json` mode: `json.dumps` of the dataclass
       fields (rt60_s, sample_rate_hz, n_samples, source, method, note) to stdout.
     - catch `ImportError` IN-HANDLER → print friendly hint (the module already raises with the
       install hint) to stderr, return 1. Do NOT widen main()'s shared except tuple.
     - Let `FileNotFoundError` (subclass of OSError) and `ValueError` (empty/non-finite/bad fs)
       propagate to main()'s existing `except (ValueError, OSError, RuntimeError, IndexError)` →
       friendly `error: ...` + exit 1.
   - dispatch in `main()`: `if args.command == "measure-rt60": return _cmd_measure_rt60(args)`.
3. **`MEASURED_RT60_NOTE`** (`roomestim/reconstruct/_disclosure.py`, single source of truth):
   update the "NOT yet quantified in-repo (ACE deferred)" clause to reflect that a CONTROLLED-SIM
   benchmark now BOUNDS the estimator's decay-fit accuracy (~9% MAPE / max ~18% under clean
   impulsive excitation), while the END-TO-END measured-corpus (ACE) benchmark stays deferred.
   Keep it one coherent string. `tests/test_measured_rt60.py` asserts `res.note == MEASURED_RT60_NOTE`
   (equality — stays green). Verify no OTHER test asserts a now-removed substring of the note.
4. **New CLI test** `tests/test_measure_rt60_cli.py` (importorskip blind_rt60 + soundfile):
   synth a decaying-noise wav to a tmp path via soundfile, then:
   - `main(["measure-rt60","--audio",wav]) == 0`, stdout has "RT60", note emitted.
   - `--json` → stdout parses as JSON, has `rt60_s` key, value > 0.
   - missing file → `main(["measure-rt60","--audio","/no/such.wav"]) == 1`.
   NO accuracy assertions (honesty pattern — wrapper/CLI plumbing only).
5. **Version bump** 0.50.1 → 0.51.0 in `pyproject.toml` (line 7) and `roomestim/__init__.py`.
6. **README.md** new v0.51.0 row in the version table (Korean style, matching v0.49.0 row) +
   document `measure-rt60` usage + the increment-2a sim-benchmark summary (honest: sim-only bound,
   impulsive-only, steady-noise negative control). Mark v0.49.0's "★CLI 미배선" as now wired.
7. **ADR 0055** `docs/adr/0055-measured-blind-rt60-audio-extra.md`: add a §Status-update (2026-06-26,
   v0.51.0) recording increment 2a numbers + CLI wiring; narrow the Reverse-criterion remaining work
   to 2b (ACE measured-corpus + Acta closed-form).

## Verification gate (canonical env)
`/home/seung/miniforge3/bin/python` — default suite, web suite, ruff (roomestim/ + new test),
mypy --strict roomestim. Baseline default 767p/7s — new CLI test adds skip-guarded tests
(default count +N where N = collected when audio extra present). Benchmark is OUT-OF-GATE (no test_).
No byte-equal regressions (additive subcommand; existing handlers untouched).
