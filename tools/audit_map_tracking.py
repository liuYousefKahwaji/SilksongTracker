"""Write a source-only tracking audit; never reads or includes a player's save."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from silksongtracker.mapdata import build_map
from silksongtracker.maptracking import FLAGS


def main():
    data=build_map(None)
    counts=Counter(m['tracking'] for m in data['markers'])
    report={'schemaVersion':1,'counts':dict(counts),'markers':[
        {'id':m['id'],'category':m['cat'],'name':m['name'],'classification':m['tracking'],
         'reason':m['trackingNote'],'supplementalFlag':FLAGS.get(m['id'])}
        for m in data['markers'] if not m.get('flag')]}
    target=ROOT/'data/map_tracking_audit.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(dict(counts))


if __name__=='__main__':main()
