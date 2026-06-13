# samplesam

Sort WAV samples into folders by their dominant frequency band.

## Output folders

| Folder       | Range             | Typical content                          |
|--------------|-------------------|------------------------------------------|
| `0-sub/`     | 20 – 80 Hz        | sub bass, rumble                         |
| `1-low/`     | 80 – 250 Hz       | bass, kick body                          |
| `2-mid/`     | 250 – 4 000 Hz    | vocals, guitar, snare                    |
| `3-highmid/` | 4 000 – 8 000 Hz  | bite, presence                           |
| `4-high/`    | 8 000 – 20 000 Hz | air, cymbals                             |
| `5-mixed/`   | —                 | broad-spectrum / no single dominant band |

Each copied file is prefixed with its band number: `kick.wav` → `1_kick.wav`.

A file lands in `5-mixed` when no single band holds ≥ 50 % of the file's total spectral energy (typical for loops, pads, and full-frequency phrases).

## How classification works

The tool computes a full **STFT power spectrogram** for each file and sums the energy within each frequency band across every frame. The band with the highest total energy wins. This "dominant band over time" approach correctly handles short percussive samples where a brief transient would otherwise skew a centroid-based estimate.

## Setup

```bash
pip install -r requirements.txt   # install Python dependencies (librosa, numpy)
chmod +x samplesam                # make the wrapper executable (one-time)
```

Requires Python 3.10+.

## Usage

```bash
samplesam <input_folder> <output_folder>

# Examples:
samplesam ~/samples ~/sorted
samplesam /Volumes/Drive/Kicks ~/sorted/kicks
```

Running `samplesam` with no arguments prints a usage hint. You can also call the Python file directly: `python samplesam.py <input> <output>`.

## Behaviour

- Scans the input folder **recursively** for all `.wav` files (case-insensitive `.wav` / `.WAV`)
- **Never modifies** the input folder — output is always a copy (`shutil.copy2`)
- Duplicate filenames in the same output bucket are auto-renamed: `kick.wav` → `1_kick.wav`, `1_kick_2.wav`, …
- Prints one line per file showing the winning band, its energy share, and the output filename
- Prints a per-bucket count summary on completion
