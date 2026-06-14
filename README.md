# samplesam

Sort WAV samples into folders by their dominant frequency band.

## Output folders

| Folder       | Range             | Typical content                          |
|--------------|-------------------|------------------------------------------|
| `0-sub/`     | 20 – 80 Hz        | sub bass, rumble                         |
| `1-low/`     | 80 – 250 Hz       | bass, kick body                          |
| `2-mid/`     | 250 – 2 000 Hz    | body, warmth, voice, snare/tom tone      |
| `3-highmid/` | 2 000 – 6 000 Hz  | presence, bite, noise, hi-hats           |
| `4-high/`    | 6 000 – 20 000 Hz | air, cymbals, shakers                    |
| `5-mixed/`   | —                 | broad-spectrum / no single dominant band |

Each copied file is prefixed with its band number: `kick.wav` → `1_kick.wav`.

A file lands in `5-mixed` when no single band holds ≥ 33 % of the file's (loudness-weighted) energy — typical for loops, pads, and full-frequency phrases.

## How classification works

samplesam sorts each sample by **where you hear it sitting** in the spectrum, not by where it carries the most raw power — those differ. Bass carries far more acoustic power than treble for equal *perceived* loudness, so on a raw meter a snare's low "body" thump can outweigh its bright "crack" even though your ear clearly hears the snare as bright.

To match your ears, the tool applies **A-weighting** — the same loudness curve used by sound-level meters — to the spectrum before measuring it. A-weighting turns the lows down a lot (≈ 30 dB at 50 Hz, ≈ 14 dB at 150 Hz) and leaves the 1–6 kHz region roughly as-is, mirroring human hearing. It then sums the A-weighted energy in each band (across the whole file, so brief transients don't dominate) and the band holding the largest **share** wins.

A real kick still lands in `0-sub`/`1-low`: A-weighting only rebalances bands that actually compete — it can't invent treble that isn't there.

## Installation

Requires **Python 3.10+**. Works on macOS and Linux; on Windows, run it via `python samplesam.py` (the `./samplesam` launcher is a Unix shell script).

```bash
# 1. Get the code
git clone <repo-url> samplesort
cd samplesort

# 2. Create and activate a virtual environment (recommended — librosa pulls in numpy/scipy)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies (librosa, numpy)
pip install -r requirements.txt

# 4. Make the launcher executable (one-time)
chmod +x samplesam
```

Then run `./samplesam` (see Usage below). If you skip the virtual environment, `pip install -r requirements.txt` installs the dependencies globally instead — the tool works either way.

## Usage

Run the launcher from the repo folder (or add it to your `PATH` to call `samplesam` from anywhere):

```bash
./samplesam <input_folder> <output_folder> [--sort-per-import]

# Examples:
./samplesam ~/samples ~/sorted
./samplesam ~/samples ~/sorted --sort-per-import
./samplesam ~/samples ~/sorted -s
```

Running `./samplesam` with no arguments prints a usage hint. You can also call the Python file directly: `python samplesam.py <input> <output>`.

## Incremental imports (`--sort-per-import` / `-s`)

When this flag is set, each import session gets a **run counter** that decrements with every run (999, 998, …), and each file within a run gets a **position counter** (000 = newest). Together they form a prefix that keeps newer imports sorted before older ones in any file browser — without renaming existing files.

```text
999-000-1_kick.wav     ← first import, newest file in that run
999-001-1_bass.wav
998-000-1_hihat.wav    ← second import, sorts before first run
998-001-1_snare.wav
```

A `samplesam-state.json` file is written to the output folder. It records a content fingerprint (SHA-256 of size + first 8 KB) for every imported file. On subsequent runs, already-imported files are recognised by fingerprint and skipped — only new files are analysed and copied.

Supports up to **1000 import sessions** per output folder. After that, start a fresh output folder.

## Behaviour

- Scans the input folder **recursively** for all `.wav` files (case-insensitive `.wav` / `.WAV`)
- **Never modifies** the input folder — output is always a copy (`shutil.copy2`)
- Duplicate filenames in the same output bucket are auto-renamed: `kick.wav` → `1_kick.wav`, `1_kick_2.wav`, …
- Prints one line per file showing the winning band, its energy share, and the output filename
- Prints a per-bucket count summary on completion
