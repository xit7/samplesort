# samplesam — CLAUDE.md

## What this project is

`samplesam` is a single-file macOS CLI tool that recursively scans a folder for `.wav` files, classifies each by dominant frequency band, and copies them into numbered output sub-folders. The input folder is never modified.

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
  0-sub/       20 – 80 Hz      sub bass, rumble
  1-low/       80 – 250 Hz     bass, kick body
  2-mid/       250 – 4 000 Hz  vocals, guitar, snare
  3-highmid/   4 – 8 kHz       bite, presence
  4-high/      8 – 20 kHz      air, cymbals
  5-mixed/     —               no single dominant band (top band < 33% of octave-normalised energy)
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
4. Sum power in each of the 5 frequency bands across all time frames
5. Normalise each band's energy by its octave width `log2(hi/lo)` — this removes the bias where wider linear bands (e.g. `high` = 12 000 Hz) accumulate more STFT bins and more raw energy than narrow ones (e.g. `highmid` = 4 000 Hz)
6. The band with the highest octave-normalised energy wins
7. If the winner holds < 33 % of normalised energy → `5-mixed` (33 % sits just above the ~32 % a flat broadband signal scores, so real instrument characters always clear the bar)

Spectral centroid was tried and rejected — brief transients skew it badly (a hi-hat click pulls the centroid into highmid even when the sustained shimmer is clearly high).

## Key constants (`samplesam.py`)

| Symbol            | Value  | Purpose                                            |
|-------------------|--------|----------------------------------------------------|
| `BANDS`           | list   | Defines all 5 bands: key, folder, prefix, lo/hi Hz |
| `FOLDERS`         | dict   | `band_key → output folder name`                    |
| `PREFIXES`        | dict   | `band_key → filename prefix`                       |
| `MIXED_FOLDER`    | string | `"5-mixed"`                                        |
| `MIXED_PREFIX`    | string | `"5_"`                                             |
| `MIXED_THRESHOLD` | float  | `0.33` — minimum octave-normalised share to win    |
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
