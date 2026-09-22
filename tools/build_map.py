"""Build the offline Leaflet map from RainingChain's Silksong dataset.

Based on Hollow Tracker's source -> markers/icons/tiles pipeline. Source
positions pass through unchanged. The upstream tiles use reversed zoom:
Leaflet z=4 uses source 3, at 16 image pixels per CRS.Simple unit.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source' / 'silksong_map_data.json'
OUT = ROOT / 'data' / 'map'
BASE = 'https://raw.githubusercontent.com/RainingChain/silksong-map-data/main/'


def interior_groups(markers, labels):
    """Find rooms collapsed to one doorway on the in-game sketch map."""
    groups = defaultdict(list)
    for marker in markers:
        pos2 = marker.get('pos2')
        if isinstance(pos2, list) and len(pos2) == 2:
            groups[tuple(pos2)].append(marker)
    interiors = []
    for pos2, members in groups.items():
        positions = {tuple(m['pos']) for m in members}
        if len(positions) < 2:
            continue
        spread = max(sum((a[i]-b[i])**2 for i in (0,1))**.5 for a in positions for b in positions)
        if spread < 4:
            continue
        centre = [sum(m['pos'][i] for m in members)/len(members) for i in (0,1)]
        nearest = min(labels, key=lambda l:sum((centre[i]-l['pos'][i])**2 for i in (0,1))**.5) if labels else None
        distance = sum((centre[i]-nearest['pos'][i])**2 for i in (0,1))**.5 if nearest else float('inf')
        name = nearest['name'] if distance < 35 else 'Interior'
        stable_id = hashlib.sha256(json.dumps(pos2).encode()).hexdigest()[:10]
        interiors.append({'id':f'interior-{stable_id}', 'name':name,
                          'entrance':list(pos2), 'members':[m['id'] for m in members],
                          'bounds':[[min(p[0] for p in positions),min(p[1] for p in positions)],
                                    [max(p[0] for p in positions),max(p[1] for p in positions)]]})
    return interiors


def map_connections(raw):
    links = raw.get('interactiveMap',{}).get('mapLinks',{})
    return [{'kind':kind, 'from':line[0], 'to':line[1]}
            for kind, lines in links.items() for line in lines
            if isinstance(line,list) and len(line)==2]

def live_config(bundle, required='categories'):
    # The same JSON.parse payload extraction used by Hollow Tracker's builder.
    text = bundle.read_text(encoding='utf-8')
    for match in re.finditer(re.escape("JSON.parse('"), text):
        chars, index = [], match.end()
        while index < len(text):
            char = text[index]
            if char == '\\':
                nxt = text[index+1]
                chars.append("'" if nxt == "'" else char+nxt)
                index += 2
                continue
            if char == "'": break
            chars.append(char)
            index += 1
        try: value = json.loads(''.join(chars))
        except ValueError: continue
        if isinstance(value, dict) and required in value: return value
    raise ValueError('No source map configuration in bundle')

def download(url, path):
    if path.exists() and path.stat().st_size > 50:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                body = response.read()
            if path.suffix == '.png' and not body.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Not a PNG: ' + url)
            path.write_bytes(body)
            return
        except Exception:
            if attempt == 2:
                raise

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-zoom', type=int, default=4, choices=range(0,7))
    parser.add_argument('--skip-assets', action='store_true')
    args = parser.parse_args()
    bundle = ROOT / 'source' / 'ssMap.js'
    download('https://scripterswar.com/compiled/hollowknight/ssMap/ssMap.js?831e557f1d68ec7915c1', bundle)
    if not args.skip_assets:
        download('https://scripterswar.com/webpackAssets/ssIconSheet@6fca861c5f6d2f56caf9.png', ROOT / 'source' / 'ssIconSheet.png')
    raw = live_config(bundle)
    source_bytes = bundle.read_bytes()
    groups = [{'id':g['id'], 'name':g['name'], 'icon':g['iconUrl'], 'visible':g.get('isVisibleByDefault', False)} for g in raw['groups']]
    categories, markers = [], []
    for cat in raw['categories']:
        categories.append({'id':cat['id'], 'name':cat['name'], 'group':cat['group'], 'icon':cat['iconUrl']})
        for item in cat['list']:
            if not isinstance(item.get('pos'), list) or len(item['pos']) != 2:
                raise ValueError('Invalid position: ' + str(item.get('uid')))
            source_id = item.get('uid', cat['id'] + '-' + hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:12])
            marker = {'id':str(source_id), 'cat':cat['id'], 'name':item.get('name', cat['name']), 'pos':item['pos'],
                      'icon':item.get('iconUrl') or cat['iconUrl'], 'flag':item.get('flag', '')}
            for key in ('pos2', 'acts', 'note', 'notes', 'href'):
                if key in item:
                    marker[key] = item[key]
            markers.append(marker)
    ids = [m['id'] for m in markers]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source marker IDs')
    valid = raw['interactiveMap']['validImages'].split(',')
    selected = [key for key in valid if 7-args.max_zoom <= int(key.split('_')[0]) <= 7]
    ext = '.webp' if '.webp' in raw['interactiveMap']['url'] else '.png'
    data = {'version':'source-tiles-v5', 'title':'Pharloom', 'groups':groups, 'categories':categories,
            'markers':markers, 'labels':raw['locations'],
            'interiors':interior_groups(markers, raw['locations']),
            'connections':map_connections(raw),
            'image':{'tileSize':1024, 'maxZoom':args.max_zoom, 'bounds':[[-944,0],[0,1280]],
                     'url':'/map/tiles/{z}/{x}_{y}' + ext},
            'validTiles':[f"{7-int(k.split('_')[0])}/{k.split('_')[1]}_{k.split('_')[2]}" for k in selected],
            'sketch':{'tileSize':1024, 'maxZoom':2, 'bounds':[[-2048,0],[0,2048]],
                      'url':'/map/sketch/{z}/{x}_{y}.webp',
                      'validTiles':[f'{z}/{x}_{y}' for z in range(3) for x in range(2**(z+1)) for y in range(2**(z+1))]},
            'source':{'url':'https://github.com/RainingChain/silksong-map-data',
                      'sha256':hashlib.sha256(source_bytes).hexdigest(),
                      'tiles':raw['interactiveMap']['url'], 'credit':'RainingChain & IdoManti · Team Cherry'}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'map.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',',':')), encoding='utf-8')
    if not args.skip_assets:
        icons = {m['icon'] for m in markers} | {g['icon'] for g in groups} | {c['icon'] for c in categories}
        sheet = ROOT / 'source' / 'ssIconSheet.png'
        if sheet.exists() and bundle.exists():
            from PIL import Image
            atlas = live_config(bundle, 'frames')
            with Image.open(sheet) as image:
                (OUT / 'icons').mkdir(parents=True, exist_ok=True)
                for frame in atlas['frames']:
                    f = frame['frame']
                    image.crop((f['x'], f['y'], f['x']+f['w'], f['y']+f['h'])).save(OUT / 'icons' / frame['filename'])
        jobs = [(BASE + 'icons/' + name, OUT / 'icons' / name) for name in sorted(icons)]
        for key in selected:
            reverse, x, y = map(int, key.split('_'))
            url = raw['interactiveMap']['url'].replace('{z}',str(reverse)).replace('{x}',str(x)).replace('{y}',str(y))
            jobs.append((url, OUT / 'tiles' / str(7-reverse) / f'{x}_{y}{ext}'))
        errors = []
        for key in data['sketch']['validTiles']:
            z, xy = key.split('/')
            jobs.append((f'https://scripterswarmap.b-cdn.net/ss_sketch_v2/{3-int(z)}_{xy}.webp?v=1', OUT / 'sketch' / (key+'.webp')))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(download,url,path):path for url,path in jobs}
            for index, future in enumerate(concurrent.futures.as_completed(futures),1):
                try: future.result()
                except Exception as exc: errors.append(f'{futures[future]}: {exc}')
                if index % 50 == 0: print(f'Assets: {index}/{len(jobs)}', flush=True)
        if errors: raise RuntimeError('\n'.join(errors))
    print(f'{len(markers)} source pins, {len(categories)} categories, {len(selected)} tiles; native zoom {args.max_zoom}.')

if __name__ == '__main__': main()
