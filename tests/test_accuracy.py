"""Adversarial, synthetic fixtures; not claims of late-game playtesting."""
import unittest
from copy import deepcopy
from silksongtracker.analyzer import analyze,known_rule,TOOL_MATCHES,SILK_SKILL_FLAGS,SILK_SKILL_TOOLS,CREST_FLAGS
from silksongtracker.flags import flag_status
from silksongtracker.rules import evaluate
from silksongtracker.schema import SaveView
from silksongtracker.mapdata import build_map
from silksongtracker.maptracking import CORE_LOCATIONS,SCENE_LOCATIONS


class AccuracyTests(unittest.TestCase):
    def test_shortcuts_and_pickup_ignore_adjacent_objects_and_other_rooms(self):
        for pin,(scene,item) in SCENE_LOCATIONS.items():
            for records,expected in [([], 'left'),
                ([{'SceneName':scene,'ID':item+' adjacent','Value':True}],'left'),
                ([{'SceneName':scene+' other','ID':item,'Value':True}],'left'),
                ([{'SceneName':scene,'ID':item,'Value':True}],'complete')]:
                raw={'sceneData':{'persistentBools':{'serializedList':records}}}
                actual=next(m for m in build_map(raw)['markers'] if m['id']==pin)
                self.assertEqual(actual['status'],expected,pin)

    def test_tool_completion_uses_visibility_and_either_skill_unlock(self):
        rule=known_rule({'id':'silk-skills-01'})
        for flag,unlocked,hidden,expected in [
            (False,True,False,'complete'),(True,False,False,'complete'),
            (False,False,False,'left'),(True,True,True,'left'),
            (True,True,'false','unknown')]:
            raw={'playerData':{'hasNeedleThrow':flag,'Tools':{'savedData':[
                {'Name':'Silk Spear','Data':{'IsUnlocked':unlocked,'IsHidden':hidden}}]}}}
            self.assertEqual(evaluate(rule,SaveView(raw)),expected)
        self.assertEqual(evaluate(rule,SaveView({'playerData':{'hasNeedleThrow':True,'Tools':{'savedData':[]}}})),'complete')
        self.assertEqual(evaluate(rule,SaveView({'playerData':{'hasNeedleThrow':True}})),'unknown')

    def test_equipment_upgrades_count_once_after_old_variant_is_hidden(self):
        rule=known_rule({'id':'tools-06'})
        for old,new,expected in [(True,False,'left'),(True,True,'complete'),(False,True,'complete')]:
            raw={'playerData':{'Tools':{'savedData':[
                {'Name':'Curve Claws','Data':{'IsUnlocked':old,'IsHidden':True}},
                {'Name':'Curve Claws Upgraded','Data':{'IsUnlocked':new,'IsHidden':False}}]}}}
            self.assertEqual(evaluate(rule,SaveView(raw)),expected)

    def test_synthetic_full_completion_and_one_point_removed(self):
        # A boundary test, not a real late-game save. Include ALL tool aliases
        # simultaneously to catch double-counting of upgraded variants.
        player={'maxHealthBase':10,'silkMax':18,'silkRegenMax':3,
                'nailUpgrades':4,'ToolKitUpgrades':4,'ToolPouchUpgrades':4,
                'hasNeedolin':True,'hasDash':True,'hasWalljump':True,
                'hasHarpoonDash':True,'hasSuperJump':True,'hasChargeSlash':True,
                'HasBoundCrestUpgrader':True,
                'Collectables':{'savedData':[{'Name':'White Flower','Data':{'Amount':1}}]},
                'Tools':{'savedData':[{'Name':name,'Data':{'IsUnlocked':True,'IsHidden':False}}
                    for name in [n for group in TOOL_MATCHES for n in group]+SILK_SKILL_TOOLS]},
                'ToolEquips':{'savedData':[{'Name':n,'Data':{'IsUnlocked':True}} for n in CREST_FLAGS.values()]}}
        player.update({field:False for field in SILK_SKILL_FLAGS})
        summary=analyze({'playerData':player})['summary']
        self.assertEqual((summary['complete'],summary['unknown']),(100,0))
        player['Tools']['savedData'].append({'Name':'Silk Snare','Data':{'IsUnlocked':True}})
        self.assertEqual(analyze({'playerData':player})['summary']['complete'],100)
        player['Tools']['savedData'][0]['Data']['IsHidden']=True
        self.assertEqual(analyze({'playerData':player})['summary']['complete'],99)

    def test_conflicting_named_records_are_order_independent(self):
        for head,collection,field,a,b in [('@tool','Tools','IsUnlocked',True,False),
                                        ('@collectable','Collectables','Amount',1,0),
                                        ('@wish','QuestCompletionData','IsCompleted',True,False)]:
            records=[{'Name':'Test','Data':{field:v}} for v in (a,b)]
            for ordered in (records,list(reversed(records))):
                raw={'playerData':{collection:{'savedData':ordered}}}
                self.assertEqual(flag_status(head+',Test',raw),'unknown')
        raw={'playerData':{'Tools':{'savedData':[
            {'Name':'Silk Spear','Data':{'IsUnlocked':True,'IsHidden':False}},
            {'Name':'Silk Spear','Data':{'IsUnlocked':False,'IsHidden':True}}]},'hasNeedleThrow':True}}
        self.assertEqual(evaluate(known_rule({'id':'silk-skills-01'}),SaveView(raw)),'unknown')

    def test_new_ability_and_upgrade_do_not_use_encounter_proxies(self):
        raw={'playerData':{'UnlockedFastTravel':True,'bellCentipedeAppeared':True,
            'UnlockedFastTravelTeleport':False,'BlueScientistDead':True,'Collectables':{'savedData':[]}}}
        pins={m['id']:m for m in build_map(raw)['markers']}
        self.assertEqual(pins['695']['status'],'left')
        self.assertEqual(pins['1038']['status'],'left')
    def test_completion_counter_progression_matches_game_formula(self):
        # Independent subset of PlayerData.CountGameCompletion: counters plus
        # eight permanent completion flags. No tool/crest points in this fixture.
        fields=['hasNeedolin','hasDash','hasWalljump','hasHarpoonDash','hasSuperJump',
                'hasChargeSlash','HasBoundCrestUpgrader','HasWhiteFlower']
        for n in range(10):
            player={'maxHealthBase':5+min(n,5),'silkMax':9+n,'silkRegenMax':min(n,3),
                    'nailUpgrades':min(n,4),'ToolKitUpgrades':min(n,4),'ToolPouchUpgrades':min(n,4),
                    'Tools':{'savedData':[]},'ToolEquips':{'savedData':[]}}
            player.update({key:n>i for i,key in enumerate(fields)})
            player['Collectables']={'savedData':[{'Name':'White Flower','Data':{'Amount':int(n>7)}}]}
            expected=min(n,5)+n+min(n,3)+3*min(n,4)+sum(n>i for i in range(8))
            self.assertEqual(analyze({'playerData':player})['summary']['complete'],expected)

    def test_related_events_do_not_award_completion(self):
        raw={'playerData':{'HasSeenEvaHeal':True,'CompletedRedMemory':True,
                          'HasBoundCrestUpgrader':False,'Collectables':{'savedData':[]}}}
        entries={e['name']:e for g in analyze(raw)['groups'] for e in g['entries']}
        self.assertEqual(entries['Sylphsong']['status'],'left')
        self.assertEqual(entries['Everbloom']['status'],'left')
        pin=next(m for m in build_map(raw)['markers'] if m['id']=='1039')
        self.assertEqual(pin['status'],'left')
        self.assertEqual(pin['trackingSource'],'correction')

    def test_real_completion_flags_award_without_story_proxy(self):
        raw={'playerData':{'HasSeenEvaHeal':False,'CompletedRedMemory':False,
                          'HasBoundCrestUpgrader':True,'Collectables':{'savedData':[{'Name':'White Flower','Data':{'Amount':1}}]}}}
        entries={e['name']:e for g in analyze(raw)['groups'] for e in g['entries']}
        self.assertEqual(entries['Sylphsong']['status'],'complete')
        self.assertEqual(entries['Everbloom']['status'],'complete')

    def test_missing_authoritative_field_never_falls_back_to_story(self):
        entries={e['name']:e for g in analyze({'playerData':{'CompletedRedMemory':True,'HasSeenEvaHeal':True}})['groups'] for e in g['entries']}
        self.assertEqual(entries['Everbloom']['status'],'unknown')
        self.assertEqual(entries['Sylphsong']['status'],'unknown')

    def test_accepting_encounter_is_not_victory(self):
        rule=known_rule({'id':'bosses-27','name':'Pinstress'})
        raw={'playerData':{'PinstressPeakBattleAccepted':True,'QuestCompletionData':{'savedData':[]}}}
        self.assertEqual(evaluate(rule,SaveView(raw)),'left')
        raw['playerData']['QuestCompletionData']['savedData']=[{'Name':'Pinstress Battle','Data':{'IsCompleted':False,'WasEverCompleted':True}}]
        self.assertEqual(evaluate(rule,SaveView(raw)),'complete')

    def test_new_locations_do_not_complete_siblings(self):
        for target,(scene,item) in CORE_LOCATIONS.items():
            raw={'sceneData':{'persistentBools':{'serializedList':[{'SceneName':scene,'ID':item,'Value':True}]}}}
            pins={m['id']:m for m in build_map(raw)['markers']}
            for pin in CORE_LOCATIONS:
                self.assertEqual(pins[pin]['status'],'complete' if pin==target else 'left',pin)

    def test_wrong_types_remain_unknown(self):
        for value in [1,0,'true','false',[],{},None]:
            self.assertEqual(evaluate({'path':'x'},SaveView({'x':value})),'unknown')
            self.assertEqual(flag_status('@,x,true',{'x':value}),'unknown')
        for value in [True,False,'2',float('nan'),float('inf')]:
            self.assertEqual(evaluate({'type':'int','path':'x'},SaveView({'x':value})),'unknown')
            self.assertEqual(flag_status('@,x,1,>=',{'x':value}),'unknown')

    def test_invalid_predicates_fail_closed(self):
        for rule in [[],{'type':'all','rules':[]},{'type':'any','rules':[]}, {'type':'int','path':'x','op':'typo'},'absent']:
            self.assertEqual(evaluate(rule,SaveView({'x':2})),'unknown')
        self.assertEqual(flag_status('@nail,invalid',{}),'unknown')

    def test_malformed_and_conflicting_scene_records(self):
        record={'SceneName':'A','ID':'B','Value':True}
        for records in [[None],[record,{**record,'Value':False}]]:
            self.assertEqual(flag_status('@bool,A,B,true',{'sceneData':{'persistentBools':{'serializedList':records}}}),'unknown')

    def test_malformed_journal_never_crashes(self):
        raw={'playerData':{'EnemyJournalKillData':{'list':[{'Name':'Test','Record':None}]}}}
        self.assertEqual(evaluate({'type':'journal','name':'Test'},SaveView(raw)),'unknown')

    def test_analysis_is_read_only_and_exposes_version(self):
        raw={'playerData':{'version':'fixture-only','HasWhiteFlower':True}}
        before=deepcopy(raw)
        self.assertEqual(analyze(raw)['saveVersion'],'fixture-only')
        build_map(raw)
        self.assertEqual(raw,before)

    def test_collectable_amount_not_seen_state_or_inventory_proxy(self):
        for amount,status in [(0,'left'),(1,'complete'),(None,'unknown'),(True,'unknown')]:
            raw={'playerData':{'Collectables':{'savedData':[{'Name':'White Flower','Data':{'Amount':amount,'IsSeenMask':255}}]}}}
            self.assertEqual(flag_status('@collectable,White Flower',raw),status)


if __name__=='__main__':unittest.main()
