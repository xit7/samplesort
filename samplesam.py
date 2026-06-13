#!/usr/bin/env python3
"""samplesam — sort WAV files into folders by dominant frequency."""

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np


# Each band: (internal key, output folder, filename prefix, lo Hz, hi Hz)
BANDS = [
    ("sub",     "0-sub",     "0_",  20,     80),
    ("low",     "1-low",     "1_",  80,    250),
    ("mid",     "2-mid",     "2_", 250,   4000),
    ("highmid", "3-highmid", "3_", 4000,  8000),
    ("high",    "4-high",    "4_", 8000, 20000),
]

FOLDERS  = {name: folder for name, folder, *_ in BANDS}    # key -> output subfolder name
PREFIXES = {name: prefix for name, _, prefix, *_ in BANDS}  # key -> filename prefix

MIXED_FOLDER    = "5-mixed"
MIXED_PREFIX    = "5_"
# A band wins only if it holds >= 33% of octave-normalised energy.
# 33% sits just above the ~32% a perfectly flat broadband signal would score,
# so genuine one-shots always win while loops/pads still fall through to mixed.
MIXED_THRESHOLD = 0.33

STATE_FILE = "samplesam-state.json"  # created in the output folder
MAX_RUN_ID = 999                     # supports up to 1000 import sessions (999 down to 0)


def collect_wavs(input_dir: Path) -> list[Path]:
    """Recursively find all .wav files under input_dir, sorted alphabetically."""
    # rglob catches nested subfolders; suffix check is case-insensitive (.WAV / .wav)
    return sorted(p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".wav")


def dominant_band(path: Path) -> tuple[str, dict[str, float]]:
    """Return (bucket, {band: pct_energy}). bucket may be 'mixed'."""
    y, sr = librosa.load(str(path), mono=True, sr=None)  # mono mix, keep original sample rate

    # Cap window size so very short one-shots (< 2048 samples) don't trigger a librosa warning
    n_fft = min(2048, len(y))
    power = np.abs(librosa.stft(y, n_fft=n_fft)) ** 2   # complex STFT -> real power (magnitude²)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)  # Hz value for each bin row

    # Sum all power within each band's frequency range across every time frame
    energies: dict[str, float] = {}
    for name, _, _, lo, hi in BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        energies[name] = float(power[mask].sum())

    total = sum(energies.values()) or 1.0
    pcts = {k: v / total * 100 for k, v in energies.items()}  # raw %, used for display only

    # Normalise each band's energy by its octave width log2(hi/lo) before comparing.
    # STFT bins are linearly spaced, so wider bands accumulate more bins and more raw
    # energy even from flat-spectrum signals. Octave normalisation removes that bias:
    # the mid band (4 oct) stops drowning out highmid (1 oct) on broadband sounds.
    log_normed = {
        name: energies[name] / math.log2(hi / lo)
        for name, _, _, lo, hi in BANDS
    }
    normed_total = sum(log_normed.values()) or 1.0
    normed_pcts = {k: v / normed_total for k, v in log_normed.items()}

    winner = max(normed_pcts, key=normed_pcts.__getitem__)

    if normed_pcts[winner] < MIXED_THRESHOLD:
        return "mixed", pcts
    return winner, pcts


def file_hash(path: Path) -> str:
    """Compute a fast content fingerprint: SHA-256 of file size + first 8 KB."""
    h = hashlib.sha256()
    h.update(str(path.stat().st_size).encode())  # include size so empty files differ from each other
    with open(path, "rb") as f:
        h.update(f.read(8192))
    return h.hexdigest()


def load_state(output_dir: Path) -> dict:
    """Load samplesam-state.json from output_dir, or return a blank initial state."""
    state_path = output_dir / STATE_FILE
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {"next_run_id": MAX_RUN_ID, "files": {}}  # fresh state, room for 1000 sessions


def save_state(output_dir: Path, state: dict) -> None:
    """Persist import state to samplesam-state.json inside the output folder."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_creation_time(path: Path) -> float:
    """Return file creation timestamp; falls back to mtime on non-macOS systems."""
    stat = path.stat()
    return getattr(stat, "st_birthtime", stat.st_mtime)  # st_birthtime is macOS-specific


def safe_copy(src: Path, dest_dir: Path, prefix: str) -> Path:
    """Copy src into dest_dir with prefix, auto-renaming if the filename is already taken."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{prefix}{src.name}"
    dest = dest_dir / base_name
    if not dest.exists():
        shutil.copy2(src, dest)  # copy2 preserves original file timestamps
        return dest
    # Filename already taken in this bucket — append a counter until we find a free slot
    counter = 2
    while True:
        candidate = dest_dir / f"{prefix}{src.stem}_{counter}{src.suffix}"
        if not candidate.exists():
            shutil.copy2(src, candidate)
            return candidate
        counter += 1


def prompt_path(prompt_text: str, must_exist: bool = False) -> Path:
    """Interactively prompt for a path, re-asking until a valid value is entered."""
    while True:
        raw = input(prompt_text).strip()
        if not raw:
            print("  Path cannot be empty, try again.")
            continue
        path = Path(raw).expanduser().resolve()
        if must_exist and not path.is_dir():
            print(f"  Directory not found: {path}")
            continue
        return path


def parse_args() -> tuple[Path, Path, bool]:
    """Parse CLI args or prompt interactively; return (input_dir, output_dir, sort_per_import)."""
    parser = argparse.ArgumentParser(
        prog="samplesam",
        description="Sort WAV files into frequency folders (0-sub … 5-mixed).",
        epilog="Example: samplesam ~/samples ~/sorted",
    )
    # nargs="?" makes both positional args optional so we can fall back to interactive prompts
    parser.add_argument("input_dir",  nargs="?", help="Folder to scan for .wav files")
    parser.add_argument("output_dir", nargs="?", help="Folder to write sorted output into")
    parser.add_argument(
        "--sort-per-import", "-s",
        action="store_true",
        help=(
            "Prefix output filenames with run/position counters so each new import "
            "sorts before older ones. Tracks processed files to skip re-imports."
        ),
    )
    args = parser.parse_args()

    # No positional args → show usage instead of silently entering interactive mode
    if not args.input_dir and not args.output_dir:
        parser.print_help()
        sys.exit(0)

    if args.input_dir:
        input_dir = Path(args.input_dir).expanduser().resolve()
        if not input_dir.is_dir():
            sys.exit(f"Error: input folder not found: {input_dir}")
    else:
        input_dir = prompt_path("Input folder:  ", must_exist=True)

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else prompt_path("Output folder: ")
    )

    return input_dir, output_dir, args.sort_per_import


def main() -> None:
    """Entry point: scan input, classify each file, copy to output, print summary."""
    input_dir, output_dir, sort_per_import = parse_args()

    if sort_per_import:
        state  = load_state(output_dir)
        known  = state["files"]        # hash -> previously imported file info
        run_id = state["next_run_id"]
        # Stop cleanly rather than wrapping around or crashing
        if run_id < 0:
            sys.exit(
                "Error: import counter exhausted (1000 sessions reached). "
                "Start a fresh output folder to continue."
            )
    else:
        state = known = {}
        run_id = 0

    print(f"\nScanning: {input_dir}")
    wavs = collect_wavs(input_dir)
    if not wavs:
        sys.exit("No .wav files found.")

    print(f"Found {len(wavs)} file(s). Analyzing...\n")

    # bucket -> list of (wav_path, pcts_dict, hash_or_None)
    all_keys = [name for name, *_ in BANDS] + ["mixed"]
    buckets: dict[str, list[tuple[Path, dict[str, float], str | None]]] = {k: [] for k in all_keys}
    counts:  dict[str, int] = {k: 0 for k in all_keys}
    errors:  list[str] = []

    # Pass 1: classify each file; skip files already in the state DB
    for wav in wavs:
        try:
            h = file_hash(wav) if sort_per_import else None
            if sort_per_import and h in known:
                print(f"  {wav.name:<44}  (already imported, skipping)")
                continue
            bucket, pcts = dominant_band(wav)
            buckets[bucket].append((wav, pcts, h))
        except Exception as exc:
            msg = f"  ERROR {wav.name}: {exc}"
            print(msg)
            errors.append(msg)

    # Pass 2: sort (if requested) then copy
    for bucket in all_keys:
        items = buckets[bucket]
        if not items:
            continue

        if sort_per_import:
            # newest file in the batch gets the lowest position number (sorts first)
            items.sort(key=lambda t: get_creation_time(t[0]), reverse=True)
            pos_width = len(str(len(items) - 1)) or 1  # digits needed for largest position index

        band_prefix = MIXED_PREFIX if bucket == "mixed" else PREFIXES[bucket]
        dest_base   = output_dir / (MIXED_FOLDER if bucket == "mixed" else FOLDERS[bucket])

        for pos, (wav, pcts, h) in enumerate(items):
            try:
                if sort_per_import:
                    # run_id counts down so newer imports have smaller numbers and sort first
                    full_prefix = f"{run_id:03d}-{pos:0{pos_width}d}-{band_prefix}"
                else:
                    full_prefix = band_prefix

                dest = safe_copy(wav, dest_base, full_prefix)

                if bucket == "mixed":
                    top   = max(pcts, key=pcts.__getitem__)
                    label = f"mixed (top: {top} {pcts[top]:.0f}%)"
                else:
                    label = f"{bucket:<8} {pcts[bucket]:.0f}%"
                print(f"  {wav.name:<44}  {label:<26}  ->  {dest.name}")
                counts[bucket] += 1

                if sort_per_import:
                    state["files"][h] = {
                        "bucket":      bucket,
                        "run_id":      run_id,
                        "position":    pos,
                        "output_name": dest.name,
                        "imported_at": datetime.now().isoformat(),
                    }
            except Exception as exc:
                msg = f"  ERROR {wav.name}: {exc}"
                print(msg)
                errors.append(msg)

    # Persist updated state before printing the summary
    total = sum(counts.values())
    if sort_per_import:
        if total > 0:
            # Only consume a run_id when files were actually imported this session
            state["next_run_id"] = run_id - 1
            save_state(output_dir, state)
            print(f"\n  State saved  →  {output_dir / STATE_FILE}")
        else:
            print("\n  Nothing new to import — run counter unchanged.")

    print(f"\n{'─' * 60}")
    print(f"Processed: {total} file(s)  |  Errors: {len(errors)}")
    max_count = max(counts.values()) or 1  # avoid division by zero on empty runs
    for key in all_keys:
        if counts[key]:
            bar = "█" * round(counts[key] / max_count * 40)  # scale bar to max 40 chars
            print(f"  {key:<8}  {counts[key]:>4}  {bar}")
    print(f"\nOutput: {output_dir}\n")


if __name__ == "__main__":
    main()
