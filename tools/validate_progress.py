"""Read-only, spoiler-minimal save checks. Never prints item names or paths.

With no arguments, checks discovered slots. Explicit paths can be used for
locally supplied before/after or late-game saves; no save data is uploaded.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from silksongtracker.codec import find_saves,decode_save
from silksongtracker.analyzer import analyze
from silksongtracker.mapdata import build_map


def check(path):
    blob=path.read_bytes()
    raw=decode_save(blob)
    state=analyze(raw)
    mapped=build_map(raw)
    statuses=Counter(e['status'] for g in state['groups'] for e in g['entries'])
    counts=Counter(m['tracking'] for m in mapped['markers'])
    available=Counter(m['status'] for m in mapped['markers'] if m['tracking']=='save')
    return {'version':state['saveVersion'],'checklist':dict(statuses),
            'completion':state['summary'],'mapCoverage':dict(counts),'mappedStatuses':dict(available),
            'fileUnchangedDuringCheck':hashlib.sha256(blob).digest()==hashlib.sha256(path.read_bytes()).digest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saves',nargs='*',type=Path)
    args=parser.parse_args()
    paths=args.saves or [Path(s['path']) for s in find_saves()]
    if not paths:
        print('No save found. No in-game validation performed.')
        return 1
    failed=False
    for n,path in enumerate(paths,1):
        try: result=check(path)
        except Exception as exc:
            result={'error':type(exc).__name__};failed=True
        print(json.dumps({'sample':n,**result},sort_keys=True))
    return int(failed)


if __name__=='__main__':raise SystemExit(main())
