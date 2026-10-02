"""Synthetic regression fixtures only; never copy a player's save into tests."""
import unittest
from silksongtracker.flags import flag_status
from silksongtracker.rules import evaluate
from silksongtracker.schema import SaveView
from silksongtracker.analyzer import analyze, known_rule
from silksongtracker.mapdata import build_map
from silksongtracker.maptracking import FLAGS, supplemental_flag
from silksongtracker.database import load_map
from tools.build_live_positions import collapse_coincident_pairs, representative_object_position


class ProgressTests(unittest.TestCase):
    def test_supplements_have_real_unique_targets(self):
        pins={m['id']:m for m in load_map()['markers']}
        self.assertEqual(len(FLAGS),82)
        for marker_id in FLAGS:
            self.assertIn(marker_id,pins)
            self.assertFalse(pins[marker_id]['flag'])
        self.assertEqual(supplemental_flag({'id':'56','flag':'@,x,true'}),'')

    def test_all_new_rules_handle_true_false_and_missing(self):
        for marker_id,flag in FLAGS.items():
            parts=flag.split(',')
            if parts[0]=='@all':
                continue
            if parts[0]=='@bool':
                complete={'sceneData':{'persistentBools':{'serializedList':[{'SceneName':parts[1],'ID':parts[2],'Value':True}]}}}
                left={'sceneData':{'persistentBools':{'serializedList':[]}}}
            elif parts[0]=='@collectable':
                complete={'playerData':{'Collectables':{'savedData':[{'Name':parts[1],'Data':{'Amount':1}}]}}}
                left={'playerData':{'Collectables':{'savedData':[]}}}
            elif parts[0]=='@wish':
                complete={'playerData':{'QuestCompletionData':{'savedData':[{'Name':parts[1],'Data':{'IsCompleted':True,'WasEverCompleted':True}}]}}}
                left={'playerData':{'QuestCompletionData':{'savedData':[]}}}
            else:
                import json
                value=json.loads(parts[2])
                field=parts[1].split('.')[1]
                complete={'playerData':{field:value}}
                left={'playerData':{field:False if type(value) is bool else 0}}
            self.assertEqual(flag_status(flag,complete),'complete',marker_id)
            self.assertEqual(flag_status(flag,left),'left',marker_id)
            self.assertEqual(flag_status(flag,{}),'unknown',marker_id)

    def test_grouped_map_pickups_require_every_exact_component(self):
        cases=[
            ('1309','Shellwood_11',[
                'Shell Shard Fossil Mid','Shell Shard Fossil Tiny Egg',
                'Shell Shard Fossil Tiny Bumpy','Shell Shard Fossil Tiny Bumpy (1)',
                'Shell Shard Fossil Tiny Bumpy (2)']),
            ('331','Greymoor_17',[
                'Shell Shard Fossil Tiny Egg (3)','Shell Shard Fossil Tiny Egg (1)',
                'Shell Shard Fossil Tiny Front','Shell Shard Fossil Tiny Front (1)',
                'Shell Shard Fossil Tiny Front (2)']),
        ]
        for marker_id,scene,objects in cases:
            flag=FLAGS[marker_id]
            self.assertEqual(flag_status(flag,{}),'unknown',marker_id)
            records=[{'SceneName':scene,'ID':name,'Value':0} for name in objects]
            raw={'sceneData':{'persistentInts':{'serializedList':records}}}
            self.assertEqual(flag_status(flag,raw),'complete',marker_id)
            records[0]['Value']=1
            self.assertEqual(flag_status(flag,raw),'left',marker_id)
            records[0]['Value']=0
            records.pop()
            self.assertEqual(flag_status(flag,raw),'left',marker_id)

        flag=FLAGS['1468']
        records=[
            {'SceneName':'Dock_01','ID':'Geo Small Persistent','Value':True},
            {'SceneName':'Dock_01','ID':'Geo Small Persistent (1)','Value':True},
            {'SceneName':'Dock_01','ID':'Geo Med Persistent','Value':True},
        ]
        raw={'sceneData':{'persistentBools':{'serializedList':records}}}
        self.assertEqual(flag_status(flag,raw),'complete')
        records[1]['Value']=False
        self.assertEqual(flag_status(flag,raw),'left')
        records[1]['Value']=True
        records[1]['ID']=None
        self.assertEqual(flag_status(flag,raw),'unknown')

    def test_classification_is_independent_of_save(self):
        before=build_map(None)['markers']
        after=build_map({'playerData':{'HasMossGrottoMap':True}})['markers']
        self.assertEqual([m['tracking'] for m in before],[m['tracking'] for m in after])
        pins={m['id']:m for m in before}
        self.assertEqual(pins['0']['tracking'],'reference')
        self.assertEqual(pins['940']['tracking'],'reference')
        self.assertEqual(pins['1395']['tracking'],'save')
        self.assertEqual(pins['1401']['tracking'],'reference')
        self.assertEqual(pins['1420']['tracking'],'save')
        self.assertEqual(pins['56']['tracking'],'save')

    def test_requirement_shortcuts_are_visit_waypoints_not_access_completion(self):
        markers=load_map()['markers']
        requirements=[m for m in markers if m['cat']=='shortcut' and m['name'].startswith('Requires ')]
        self.assertEqual(len(requirements),115)
        no_save={m['id']:m for m in build_map(None)['markers']}
        raw={'playerData':{'hasDoubleJump':True,'hasWalljump':True,'hasSuperJump':True}}
        pins={m['id']:m for m in build_map(raw)['markers']}
        for source in requirements:
            pin=pins[source['id']]
            self.assertEqual(pin['tracking'],'waypoint',source['id'])
            self.assertEqual(pin['status'],'left',source['id'])
            self.assertEqual(no_save[source['id']]['status'],'left',source['id'])
        faydown=[m for m in requirements if m['name']=='Requires Faydown Cloak']
        self.assertEqual(len(faydown),18)
        self.assertTrue(all(pins[m['id']]['trackingNote'].startswith('Route waypoint.') for m in faydown))

    def test_reviewed_source_pin_correction(self):
        data=build_map({'sceneData':{'persistentBools':{'serializedList':[
            {'SceneName':'Bone_East_02b','ID':'Black_Thread_Core','Value':True},
            {'SceneName':'Bone_East_03','ID':'Black_Thread_Core','Value':False},
        ]}}})
        pins={m['id']:m for m in data['markers']}
        self.assertEqual(pins['1402']['status'],'complete')
        self.assertEqual(pins['1402']['trackingSource'],'correction')
        self.assertEqual(pins['1405']['status'],'left')

    def test_stacked_map_icons_do_not_count_as_independent_room_anchors(self):
        target=complex(5,9)
        pairs=[(complex(1,3),target),(complex(5,7),target),
               (complex(12,14),complex(20,30))]
        collapsed,coalesced=collapse_coincident_pairs(pairs)
        self.assertTrue(coalesced)
        self.assertEqual(len(collapsed),2)
        self.assertEqual(collapsed[0],(complex(3,5),target))
        self.assertEqual(collapsed[1],pairs[2])

    def test_duplicate_scene_items_collapse_only_when_physically_clustered(self):
        point,clustered=representative_object_position([[359.31,6.25],[357.2,6.2]])
        self.assertEqual(point,[358.255,6.225])
        self.assertTrue(clustered)
        point,clustered=representative_object_position([[0,0],[4,0]])
        self.assertIsNone(point)
        self.assertFalse(clustered)

    def test_aggregate_quest_not_individual_object(self):
        raw={'playerData':{'QuestCompletionData':{'savedData':[{'Name':'Destroy Thread Cores','Data':{'IsCompleted':True,'WasEverCompleted':True}}]}}}
        pin=next(m for m in build_map(raw)['markers'] if m['id']=='1395')
        self.assertEqual(pin['status'],'unknown')
        self.assertEqual(pin['tracking'],'save')

    def test_alternative_quills_not_missing(self):
        for state,owned in [(1,'1183'),(2,'911'),(3,'912')]:
            pins={m['id']:m for m in build_map({'playerData':{'QuillState':state}})['markers']}
            for key in ('1183','911','912'):
                self.assertEqual(pins[key]['status'],'complete' if key==owned else 'unavailable')
        pins={m['id']:m for m in build_map({'playerData':{'QuillState':0}})['markers']}
        self.assertEqual(pins['1183']['status'],'left')

    def test_modern_scene_collections(self):
        for head, collection, value in [('@bool','persistentBools',True),('@int','persistentInts',0),('@geo','geoRocks',0)]:
            raw={'sceneData':{collection:{'serializedList':[{'SceneName':'RoomA','ID':'Pickup','Value':value}]}}}
            expected='true' if value is True else '0'
            self.assertEqual(flag_status(f'{head},RoomA,Pickup,{expected}',raw),'complete')
            self.assertEqual(flag_status(f'{head},RoomB,Pickup,{expected}',raw),'left')
            self.assertEqual(flag_status(f'{head},RoomA,Pickup,{expected}',{}),'unknown')

    def test_false_and_zero_are_not_absence(self):
        raw={'sceneData':{'persistentBools':{'serializedList':[{'SceneName':'A','ID':'B','Value':False}]}}}
        self.assertEqual(flag_status('@bool,A,B,false',raw),'complete')
        self.assertEqual(flag_status('@bool,A,C,false',raw),'left')
        self.assertEqual(flag_status('@,x,0',{'x':0}),'complete')
        self.assertEqual(flag_status('@,x,false',{'x':False}),'complete')

    def test_named_collections(self):
        for head,collection,field in [('@tool','Tools','IsUnlocked'),('@crest','ToolEquips','IsUnlocked'),('@relic','Relics','IsCollected')]:
            raw={'playerData':{collection:{'savedData':[{'Name':'Test','Data':{field:True}}]}}}
            self.assertEqual(flag_status(head+',Test',raw),'complete')
            self.assertEqual(flag_status(head+',Other',raw),'left')
            self.assertEqual(flag_status(head+',Test',{}),'unknown')
            raw['playerData'][collection]['savedData'][0]['Data']={}
            self.assertEqual(flag_status(head+',Test',raw),'unknown')

    def test_previously_completed_quest(self):
        raw={'playerData':{'QuestCompletionData':{'savedData':[{'Name':'Test','Data':{'IsCompleted':False,'WasEverCompleted':True}}]}}}
        self.assertEqual(flag_status('@wish,Test',raw),'complete')

    def test_upgraded_tool_alias_not_shadowed(self):
        rule={'type':'list_item_bool','path':'tools','matchAny':['Old','New']}
        save=SaveView({'tools':[{'Name':'Old','Data':{'IsUnlocked':False}},{'Name':'New','Data':{'IsUnlocked':True}}]})
        self.assertEqual(evaluate(rule,save),'complete')

    def test_upgrade_thresholds(self):
        for prefix,field,base,total in [('upgrades','ToolKitUpgrades',0,4),('mask-upgrades','maxHealthBase',5,5),('silk-upgrades','silkMax',9,9),('silk-hearts','silkRegenMax',0,3)]:
            for n in range(1,total+1):
                rule=known_rule({'id':f'{prefix}-{n:02d}'})
                self.assertEqual(evaluate(rule,SaveView({'playerData':{field:base+n-1}})),'left')
                self.assertEqual(evaluate(rule,SaveView({'playerData':{field:base+n}})),'complete')
                self.assertEqual(evaluate(rule,SaveView({})),'unknown')
        rule=known_rule({'id':'upgrades-05'})
        self.assertEqual(evaluate(rule,SaveView({'playerData':{'ToolPouchUpgrades':1}})),'complete')

    def test_journal_kills_not_sightings(self):
        rule={'type':'journal','name':'Test'}
        for kills,status in [(0,'left'),(1,'complete')]:
            self.assertEqual(evaluate(rule,SaveView({'playerData':{'EnemyJournalKillData':{'list':[{'Name':'Test','Record':{'Kills':kills,'HasBeenSeen':True}}]}}})),status)
        self.assertEqual(evaluate(rule,SaveView({})),'unknown')

    def test_checklist_uses_linked_source_flags(self):
        state=analyze({'playerData':{'SavedFlea_Crawl_06':True,'Collectables':{'savedData':[]}}})
        entries={e['id']:e for g in state['groups'] for e in g['entries']}
        self.assertEqual(entries['fleas-01']['status'],'complete')
        self.assertEqual(entries['items-01']['status'],'left')

    def test_location_not_overwritten_by_checklist(self):
        data=build_map({'playerData':{'defeatedLace1':False,'defeatedLaceTower':True}})
        pins={m['id']:m for m in data['markers']}
        self.assertEqual(pins['544']['status'],'left')
        self.assertEqual(pins['1015']['status'],'complete')

    def test_unknown_is_preserved_for_unresearched_data(self):
        self.assertEqual(flag_status('@unsupported,Test',{}),'unknown')
        self.assertEqual(flag_status('',{}),'unknown')
        self.assertEqual(analyze(None)['summary']['unknown'],100)
        self.assertEqual(analyze({})['summary']['unknown'],100)

    def test_source_relic_typo_is_narrowly_corrected(self):
        raw={'playerData':{'Relics':{'savedData':[]}}}
        self.assertEqual(flag_status('@flag,Ancient Egg Abyss Middle',raw),'left')
        self.assertEqual(flag_status('@flag,Other',raw),'unknown')


if __name__ == '__main__': unittest.main()
