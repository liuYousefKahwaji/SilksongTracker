"""Compare two decoded saves by key path without printing string payloads."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silksongtracker.codec import read_save


def flatten(v, prefix=""):
    if isinstance(v, dict):
        out={}
        for k,x in v.items(): out.update(flatten(x, f"{prefix}.{k}" if prefix else k))
        return out
    if isinstance(v, list): return {prefix: f"<list:{len(v)}>"}
    if isinstance(v, str): return {prefix: f"<string:{len(v)}>"}
    return {prefix: v}


def main():
    p=argparse.ArgumentParser(); p.add_argument("before"); p.add_argument("after"); a=p.parse_args()
    old,new=flatten(read_save(a.before)),flatten(read_save(a.after))
    for key in sorted(set(old)|set(new)):
        if old.get(key)!=new.get(key): print(f"{key}: {old.get(key)!r} -> {new.get(key)!r}")


if __name__ == "__main__": main()
