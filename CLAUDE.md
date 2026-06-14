# samplesam — CLAUDE.md

## What this project is

`samplesam` is a single-file CLI tool (macOS/Linux; Windows via `python samplesam.py`) that recursively scans a folder for `.wav` files, classifies each by dominant frequency band, and copies them into numbered output sub-folders. The input folder is never modified.

## Single file

All logic lives in `samplesam.py`. There is no package structure, no tests directory, and no build step.

## Running the tool

```bash
pip install -r requirements.txt          # one-time setup
python samplesam.py <input> <output>     # with arguments
python samplesam.py                      # interactive prompts
```

## Output folder structure

```
<output>/
  0-sub/       20 – 80 Hz       sub bass, rumble
  1-low/       80 – 250 Hz      bass, kick body
  2-mid/       250 – 2 000 Hz   body, warmth, voice, snare/tom tone
  3-highmid/   2 – 6 kHz        presence, bite, noise, hi-hats
  4-high/      6 – 20 kHz       air, cymbals, shakers
  5-mixed/     —                no single dominant band (top band < 33% of A-weighted energy)
```

Each output file is prefixed with its band number: `kick.wav` → `1_kick.wav`. Duplicate filenames are auto-renamed: `1_kick_2.wav`, `1_kick_3.wav`, etc.

With `--sort-per-import` / `-s`, filenames additionally get a two-part counter prefix so new imports always sort first:

```text
<run_id:03d>-<position:03d>-<band_prefix><original_name>
```

`run_id` counts down from 999 (newer import = lower number = sorts first). `position` counts up within a run (000 = newest file in that batch). A `samplesam-state.json` file in the output folder tracks imported file fingerprints (SHA-256 of size + first 8 KB) so already-processed files are skipped on re-runs. Supports up to 1000 import sessions; exits with a clear error if exhausted.

## Classification algorithm

`dominant_band()` in `samplesam.py`:

1. Load audio as mono with `librosa.load(..., sr=None)` — preserve original sample rate
2. Cap `n_fft` to signal length so very short files don't trigger a librosa warning
3. Compute STFT power spectrogram: `np.abs(librosa.stft(y, n_fft)) ** 2`
4. **Apply A-weighting** (`a_weighting_power(freqs)`, the IEC 61672 loudness curve) to the power spectrum — this is the core of the design (see below)
5. Sum the A-weighted power in each of the 5 frequency bands across all time frames
6. The band holding the largest **share** of total A-weighted energy wins
7. If the winner holds < 33 % → `5-mixed` (sound is spread across the spectrum; loops/pads)

**Why A-weighting (the key decision):** the old algorithm summed raw STFT power, but bass carries far more acoustic power than treble for equal *perceived* loudness (Fletcher–Munson). A snare's ~150 Hz body out-powered its bright 7 kHz crack and landed in `low`, contradicting what the ear hears. A-weighting (−30 dB @ 50 Hz, −14 dB @ 150 Hz, ≈flat 1–6 kHz) rebalances the spectrum to match hearing. A real kick still lands low — A-weighting only rebalances competing bands, it can't invent treble.

**Two approaches deliberately rejected:**
- *Spectral centroid* — brief transients skew it, and after A-weighting it pushes kicks/bass up into `mid` (fundamentals get suppressed). ~67/78 kicks misfiled in testing.
- *Octave-width normalisation* (`energy / log2(hi/lo)`) — over-rewards narrow bands; a kick's faint click won the narrow `highmid` band. Removed entirely.

**Band boundaries are perceptual, set by ear against the `wrong/` regression folders.** The mid→highmid line sits at **2 kHz** (classic midrange ceiling), so presence/bite/noise/hi-hats land in `highmid`. An earlier `lowmid`/`mid` split at 1 kHz was reverted — the user heard no distinction between those two bands; the perceptually meaningful split is mid vs highmid at 2 kHz.

## Key constants (`samplesam.py`)

| Symbol            | Value  | Purpose                                            |
|-------------------|--------|----------------------------------------------------|
| `BANDS`           | list   | Defines all 5 bands: key, folder, prefix, lo/hi Hz |
| `FOLDERS`         | dict   | `band_key → output folder name`                    |
| `PREFIXES`        | dict   | `band_key → filename prefix`                       |
| `MIXED_FOLDER`    | string | `"5-mixed"`                                        |
| `MIXED_PREFIX`    | string | `"5_"`                                             |
| `MIXED_THRESHOLD` | float  | `0.33` — minimum A-weighted energy share to win    |
| `STATE_FILE`      | string | `"samplesam-state.json"` — DB filename in output   |
| `MAX_RUN_ID`      | int    | `999` — first run_id; supports 1000 sessions       |

To change the mixed threshold or add/rename bands, edit only `BANDS` and the three `MIXED_*` constants at the top of the file.

## Coding style

- **Every function gets a one-line docstring** — state what it returns or does in plain English. No multi-line docstrings.
- **Short inline comments explain the *why***, not the what. One line maximum. Examples: why `n_fft` is capped, why `copy2` is used, why `counts["mixed"]` is added separately.
- No comments that just restate what the code already says.

## Dependencies

- `librosa >= 0.10` — audio loading and STFT
- `numpy >= 1.24` — array math
