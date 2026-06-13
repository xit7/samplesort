#!/usr/bin/env python3
"""samplesam — sort WAV files into folders by dominant frequency."""

import argparse
import math
import shutil
import sys
from pathlib import Path

import librosa
import numpy as np


# (internal_key, output_folder, file_prefix, lo_hz, hi_hz)
BANDS = [
    ("sub",     "0-sub",     "0_",  20,     80),
    ("low",     "1-low",     "1_",  80,    250),
    ("mid",     "2-mid",     "2_", 250,   4000),
    ("highmid", "3-highmid", "3_", 4000,  8000),
    ("high",    "4-high",    "4_", 8000, 20000),
]

FOLDERS  = {name: folder for name, folder, *_ in BANDS}
PREFIXES = {name: prefix for name, _, prefix, *_ in BANDS}

MIXED_FOLDER    = "5-mixed"
MIXED_PREFIX    = "5_"
MIXED_THRESHOLD = 0.33   # winner must hold >= 33% of log-normalised energy or -> mixed


def collect_wavs(input_dir: Path) -> list[Path]:
    return sorted(p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".wav")


def dominant_band(path: Path) -> tuple[str, dict[str, float]]:
    """Return (bucket, {band: pct_energy}). bucket may be 'mixed'."""
    y, sr = librosa.load(str(path), mono=True, sr=None)
    n_fft = min(2048, len(y))
    power = np.abs(librosa.stft(y, n_fft=n_fft)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    energies: dict[str, float] = {}
    for name, _, _, lo, hi in BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        energies[name] = float(power[mask].sum())

    total = sum(energies.values()) or 1.0
    pcts = {k: v / total * 100 for k, v in energies.items()}

    # Divide by octave bandwidth to remove linear-bin-count bias before picking winner.
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


def safe_copy(src: Path, dest_dir: Path, prefix: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{prefix}{src.name}"
    dest = dest_dir / base_name
    if not dest.exists():
        shutil.copy2(src, dest)
        return dest
    counter = 2
    while True:
        candidate = dest_dir / f"{prefix}{src.stem}_{counter}{src.suffix}"
        if not candidate.exists():
            shutil.copy2(src, candidate)
            return candidate
        counter += 1


def prompt_path(prompt_text: str, must_exist: bool = False) -> Path:
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


def parse_args() -> tuple[Path, Path]:
    parser = argparse.ArgumentParser(
        prog="samplesam",
        description="Sort WAV files into frequency folders (0-sub … 5-mixed).",
    )
    parser.add_argument("input_dir", nargs="?", help="Folder to scan for .wav files")
    parser.add_argument("output_dir", nargs="?", help="Folder to write sorted output into")
    args = parser.parse_args()

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

    return input_dir, output_dir


def main() -> None:
    input_dir, output_dir = parse_args()

    print(f"\nScanning: {input_dir}")
    wavs = collect_wavs(input_dir)
    if not wavs:
        sys.exit("No .wav files found.")

    print(f"Found {len(wavs)} file(s). Analyzing...\n")

    counts: dict[str, int] = {name: 0 for name, *_ in BANDS}
    counts["mixed"] = 0
    errors: list[str] = []

    for wav in wavs:
        try:
            bucket, pcts = dominant_band(wav)
            if bucket == "mixed":
                dest_dir = output_dir / MIXED_FOLDER
                prefix   = MIXED_PREFIX
                top      = max(pcts, key=pcts.__getitem__)
                label    = f"mixed (top: {top} {pcts[top]:.0f}%)"
            else:
                dest_dir = output_dir / FOLDERS[bucket]
                prefix   = PREFIXES[bucket]
                label    = f"{bucket:<8} {pcts[bucket]:.0f}%"
            dest = safe_copy(wav, dest_dir, prefix)
            print(f"  {wav.name:<44}  {label:<26}  ->  {dest.name}")
            counts[bucket] += 1
        except Exception as exc:
            msg = f"  ERROR {wav.name}: {exc}"
            print(msg)
            errors.append(msg)

    total = sum(counts.values())
    print(f"\n{'─' * 60}")
    print(f"Processed: {total} file(s)  |  Errors: {len(errors)}")
    all_keys = [name for name, *_ in BANDS] + ["mixed"]
    max_count = max(counts.values()) or 1
    for key in all_keys:
        if counts[key]:
            bar = "█" * round(counts[key] / max_count * 40)
            print(f"  {key:<8}  {counts[key]:>4}  {bar}")
    print(f"\nOutput: {output_dir}\n")


if __name__ == "__main__":
    main()
