"""Evaluate actual source pins while preserving unknown save fields."""
from .database import load_map
from .maplinks import links
from .schema import SaveView
from .rules import evaluate
from .analyzer import known_rule

from .flags import flag_status
from .maptracking import supplemental_flag, reference_reason, route_waypoint_reason, unresolved_reason, alternative_unavailable
from .maptracking import CORRECTIONS

def build_map(raw):
    data = load_map()
    reverse = {}
    for entry_id, link in links().items():
        if link['kind'] == 'components': continue
        for marker_id in link['ids']:
            reverse.setdefault(marker_id, []).append({'id':entry_id, 'name':link['name']})
    markers = []
    save = SaveView(raw) if raw is not None else None
    for original in data['markers']:
        marker = dict(original)
        entries = reverse.get(marker['id'], [])
        flag = CORRECTIONS.get(marker['id']) or marker.get('flag') or supplemental_flag(marker)
        status = flag_status(flag, raw)
        waypoint_reason = route_waypoint_reason(marker)
        rule = None
        if status == 'unknown' and not flag and entries:
            rule = known_rule(entries[0])
            if rule and not entries[0]['id'].startswith(('upgrades-', 'silk-hearts-')):
                status = evaluate(rule, save)
        has_rule = bool(flag or (rule and not entries[0]['id'].startswith(('upgrades-', 'silk-hearts-'))))
        reason = None if has_rule else reference_reason(marker)
        tracking = 'waypoint' if waypoint_reason else 'save' if has_rule else 'reference' if reason else 'unverified'
        if tracking == 'waypoint':
            status = 'left'
            reason = waypoint_reason
        elif tracking == 'unverified': reason = unresolved_reason(marker)
        if tracking != 'waypoint' and alternative_unavailable(marker, raw):
            status = 'unavailable'
            reason = 'An alternative version is already owned. This is not a missing collectible.'
        markers.append({**marker, 'status':status, 'tracking':tracking,
                        'trackingNote':reason, 'trackingSource':'correction' if marker['id'] in CORRECTIONS else 'supplement' if supplemental_flag(marker) else 'source', 'entries':entries})
    return {**data, 'markers':markers, 'links':links(), 'hasSave':raw is not None,
            'saveStatus':'loaded' if raw is not None else 'waiting'}
