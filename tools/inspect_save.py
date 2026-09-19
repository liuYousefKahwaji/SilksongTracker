"""Print non-sensitive save structure hints for adapter development."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silksongtracker.codec import read_save


def shape(value, depth=0):
    if depth > 2: return "…"
    if isinstance(value, dict): return {k: shape(v, depth + 1) for k, v in list(value.items())[:80]}
    if isinstance(value, list): return [shape(x, depth + 1) for x in value[:3]] + ([f"… ({len(value)} items)"] if len(value) > 3 else [])
    if isinstance(value, str): return f"<string:{len(value)}>"
    return value


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("path"); args = parser.parse_args()
    print(json.dumps(shape(read_save(args.path)), indent=2, ensure_ascii=False))


if __name__ == "__main__": main()
