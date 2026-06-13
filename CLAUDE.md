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
  5-mixed/     —               no single dominant band (< 50 % energy in top band)
```

Each output file is prefixed with its band number: `kick.wav` → `1_kick.wav`. Duplicate filenames are auto-renamed: `1_kick_2.wav`, `1_kick_3.wav`, etc.

## Classification algorithm

`dominant_band()` in `samplesam.py`:

1. Load audio as mono with `librosa.load(..., sr=None)` (preserve original sample rate)
2. Compute STFT power spectrogram: `np.abs(librosa.stft(y)) ** 2`
3. Get frequency axis: `librosa.fft_frequencies(sr=sr)`
4. For each of the 5 bands, sum all power in the corresponding frequency bins across all frames
5. The band with the highest total energy wins
6. If the winning band holds < 50 % of total energy → classify as `mixed`

This "integrated band energy" approach is intentionally used instead of spectral centroid. Spectral centroid (the old approach) is skewed by brief transients — a hi-hat's stick click pulls the centroid into highmid even when most sustained energy is in high. Integrated energy is stable across the full duration.

## Key constants (`samplesam.py`)

| Symbol           | Value  | Purpose                                       |
|------------------|--------|-----------------------------------------------|
| `BANDS`          | tuple  | Defines all 5 bands: key, folder, prefix, Hz  |
| `FOLDERS`        | dict   | `band_key → output folder name`               |
| `PREFIXES`       | dict   | `band_key → filename prefix`                  |
| `MIXED_FOLDER`   | string | `"5-mixed"`                                   |
| `MIXED_PREFIX`   | string | `"5_"`                                        |
| `MIXED_THRESHOLD`| float  | `0.50` — minimum energy share for a clear win |

To change the mixed threshold or add/rename bands, edit only `BANDS` and the three `MIXED_*` constants at the top of the file.

## Dependencies

- `librosa >= 0.10` — audio loading and STFT
- `numpy >= 1.24` — array math
