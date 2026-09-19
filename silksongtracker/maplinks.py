"""Checklist-to-pin joins based on Hollow Tracker; never synthesize positions."""
import re
from functools import lru_cache
from .database import load_content, load_map

def norm(name):
    name = name.lower().replace('’', "'")
    name = re.sub(r'^(?:tool|ability|upgrade|boss|bellway|ventrica|npc)\s*-\s*', '', name)
    name = re.sub(r'\s+for\s+\d+\s+rosaries.*$', '', name)
    name = re.sub(r'\([^)]*\)', '', name)
    name = name.replace('crest of the ', '').replace('crest of ', '').replace(' crest', '')
    return re.sub(r'[^a-z0-9]+', '', name)

CATEGORIES = {'tools':['tool'], 'silk-skills':['ability'], 'abilities':['ability'],
              'crests':['crest'], 'items':['ability','misc'], 'bosses':['boss'],
              'fleas':['flea'], 'bellways':['bellway'], 'ventrica':['ventrica'],
              'silk-hearts':['heart'], 'needle-upgrades':['upgnail']}

@lru_cache(maxsize=1)
def links():
    markers = load_map()['markers']
    result = {}
    for section in load_content()['sections']:
        for entry in section['entries']:
            section_id = section['id']
            aliases = {norm(name.strip()) for name in entry['name'].split(' / ')}
            if entry['name'] == 'Pollip Pouch': aliases.add(norm('Polip Pouch'))
            if entry['name'] == 'Savage Beastfly II': aliases.add(norm('Savage Beastfly #2'))
            candidates = [m for m in markers if m['cat'] in CATEGORIES.get(section_id, []) and norm(m['name']) in aliases]
            group = None
            number = int(entry['id'].rsplit('-',1)[1])
            if section_id == 'upgrades':
                cat, index = ('kit', number) if number <= 4 else ('pouch', number-4)
                candidates = [m for m in markers if m['cat'] == cat and re.search(r'#' + str(index) + r'\b', m['name'])]
            elif section_id == 'needle-upgrades':
                candidates = [m for m in markers if m['cat'] == 'upgnail' and m['name'] == f'Nail Upgrade #{number}']
            elif section_id == 'mask-upgrades': group = 'mask'
            elif section_id == 'silk-upgrades': group = 'spool'
            elif section_id == 'fleas' and number == 11:
                candidates = [m for m in markers if m['cat'] == 'flea' and ('Kratt' in m['name'] or norm(m['name']) == norm('Lost Flea #11'))]
            if group: candidates = [m for m in markers if m['cat'] == group]
            if candidates:
                result[entry['id']] = {'ids':[m['id'] for m in candidates], 'category':group,
                    'icon':candidates[0]['icon'], 'name':entry['name'],
                    'kind':'components' if group else 'locations'}
    return result
