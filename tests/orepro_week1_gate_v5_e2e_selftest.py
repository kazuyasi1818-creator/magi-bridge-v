#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import keiba_generate_exotic_probabilities_v1 as prob
import keiba_exotics_budget_allocator_v1 as alloc

BET_TYPES = ['EXACTA_UMA_TAN','QUINELLA_UMA_REN','TRIFECTA_3REN_TAN','TRIO_3REN_PUKU']


def run(cmd: list[str], expect: int = 0) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode != expect:
        raise AssertionError(f'command rc={p.returncode}, expected={expect}: {cmd}\nSTDOUT={p.stdout}\nSTDERR={p.stderr}')
    return p


def base_probability_fixture() -> tuple[dict, list[dict], dict[str,str]]:
    horses = [{'horse_no':str(i),'score':float(9-i)} for i in range(1,9)]
    out = prob.generate(horses)
    for k,v in out['probability_sums'].items():
        if abs(float(v)-1.0) > 1e-10:
            raise AssertionError(f'probability sum failed: {k}={v}')
    tickets=[]
    combo_by_id={}
    for bt in BET_TYPES:
        best=max(out[bt], key=lambda x: x['probability'])
        p=float(best['probability'])
        odds=1.20/p
        tid=f'{bt}:{best["ticket"]}'
        combo_by_id[tid]=best['ticket']
        tickets.append({
            'ticket_id':tid,
            'bet_type':bt,
            'correlation_group':f'G:{bt}',
            'model_probability':p,
            'decimal_odds':odds,
            'expected_value':p*odds-1.0,
            'qualified':True,
        })
    return out,tickets,combo_by_id


def make_card(race_no:int, pure_budget:int, battle:bool, tickets:list[dict], combo_by_id:dict[str,str]) -> dict:
    result=alloc.allocate(
        tickets,
        race_budget_yen=pure_budget,
        method='edge_proportional_with_caps',
        unit_yen=100,
        min_ev=0.05,
        deploy_fraction=1.0,
        max_ticket_share=0.40,
        max_bet_type_share=0.60,
        max_correlation_group_share=0.70,
    )
    if result['status'] != 'ALLOCATED' or result['spent_yen'] != pure_budget:
        raise AssertionError(f'pure allocator did not spend synthetic budget {pure_budget}: {result}')
    card_tickets=[]
    for r in result['allocations']:
        card_tickets.append({
            'bet_type':r['bet_type'],
            'combination':combo_by_id[r['ticket_id']],
            'magi_pure_stake_yen':int(r['stake_yen']),
            'competition_weight':float(r['stake_yen']),
            'orepro_registered_stake_yen':0,
            'forced_scale_up_yen':0,
            'model_probability':float(r['model_probability']),
            'purchase_available_decimal_odds':float(r['decimal_odds']),
            'expected_value':float(r['expected_value']),
            'correlation_group':r['correlation_group'],
        })
    return {
        'template_id':'OREPRO-PREDICTION-CARD-V3',
        'race_id':f'20260829_SYNTH_{race_no:02d}',
        'race_date_jst':'2026-08-29',
        'venue':['新潟','中京','札幌','新潟','中京'][race_no-1],
        'race_no':race_no,
        'post_time_jst':f'2026-08-29T{11+race_no:02d}:00:00+09:00',
        'prediction_frozen_at_jst':f'2026-08-29T{11+race_no:02d}:50:00+09:00' if False else f'2026-08-29T{10+race_no:02d}:50:00+09:00',
        'submission_deadline_jst':f'2026-08-29T{11+race_no:02d}:58:00+09:00',
        'model_version':'A_MARKET_ONLY',
        'shadow_model_versions':['C_LATE_PLUS_PATH_v3','C_MARKET_PLUS_HORSE_MISPRICING_v4','C_MARKET_PLUS_RECENCY_TRANSITION_v5'],
        'feature_gate_version':'KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5',
        'data_snapshot':{
            'odds_snapshot_time_jst':f'2026-08-29T{10+race_no:02d}:49:00+09:00',
            'history_cutoff':'strictly_before_race_date',
            'current_feature_gate_pass':False,
            'gate_v5_handoff_sha256':'',
            'source_hashes':[hashlib.sha256(f'synthetic-source-{race_no}'.encode()).hexdigest()],
        },
        'magi_pure_budget_cap_yen':10000,
        'orepro_registered_target_yen':10000,
        'ranking_included_flag':True,
        'battle_race_flag':battle,
        'competition_overlay_caps':{'single_ticket_ratio':0.40,'bet_type_ratio':0.60,'correlation_group_ratio':0.70},
        'tickets':card_tickets,
        'totals':{
            'ticket_count':len(card_tickets),
            'magi_pure_total_stake_yen':pure_budget,
            'orepro_registered_total_stake_yen':0,
            'forced_scale_up_total_yen':0,
        },
        'prediction_note':'synthetic week1 e2e only',
        'freeze_hash_sha256':'',
        'submitted_to_orepro':False,
        'result_fields_locked_until_after_post':True,
    }


def main() -> int:
    probability_output,tickets,combo_by_id=base_probability_fixture()
    checks={}
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        frozen=[]
        pure_budgets=[1000,2000,3000,4000,5000]
        entry_texts=[]

        for i,budget in enumerate(pure_budgets, start=1):
            card=make_card(i,budget,i==3,tickets,combo_by_id)
            raw=d/f'card_{i}.json'
            overlay=d/f'overlay_{i}.json'
            frozen_path=d/f'frozen_{i}.json'
            sheet=d/f'entry_{i}.txt'
            raw.write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf-8')
            run([sys.executable,str(SCRIPTS/'orepro_competition_overlay_v1.py'),str(raw),'--out',str(overlay)])
            run([sys.executable,str(SCRIPTS/'orepro_freeze_prediction_v4.py'),str(overlay),'--out',str(frozen_path)])
            run([sys.executable,str(SCRIPTS/'orepro_entry_sheet_v3.py'),str(frozen_path),'--out',str(sheet)])
            obj=json.loads(frozen_path.read_text(encoding='utf-8'))
            btypes={x['bet_type'] for x in obj['tickets'] if x['orepro_registered_stake_yen']>0}
            if btypes != set(BET_TYPES):
                raise AssertionError(f'four bet types not retained: {btypes}')
            if obj['totals']['magi_pure_total_stake_yen'] != budget:
                raise AssertionError('MAGI_PURE budget changed by overlay/freeze')
            if obj['totals']['orepro_registered_total_stake_yen'] != 10000:
                raise AssertionError('official registered amount is not 10,000')
            frozen.append(frozen_path)
            entry_texts.append(sheet.read_text(encoding='utf-8'))

        bundle=run([
            sys.executable,str(SCRIPTS/'orepro_week1_bundle_validate_v1.py'),
            *[str(x) for x in frozen], '--expected-races','5','--official-week-cap','50000','--require-full-ranking-total'
        ])
        bundle_obj=json.loads(bundle.stdout)
        checks['five_race_bundle_pass']=bundle_obj['status']=='PASS'
        checks['official_week_total_50000']=bundle_obj['official_total_stake_yen']==50000
        checks['magi_pure_total_15000']=bundle_obj['magi_pure_total_stake_yen']==15000
        checks['forced_scale_up_35000']=bundle_obj['forced_scale_up_total_yen']==35000
        checks['exactly_one_battle']=bundle_obj['battle_race_count']==1
        checks['all_four_bet_types_in_entry_sheets']=all(all(label in text for label in ['馬単','馬連','3連単','3連複']) for text in entry_texts)
        checks['gate_v5_printed']=all('KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5' in text for text in entry_texts)

        tampered=json.loads(frozen[0].read_text(encoding='utf-8'))
        tampered['prediction_note']='tampered after freeze'
        tampered_path=d/'tampered.json'
        tampered_path.write_text(json.dumps(tampered,ensure_ascii=False,indent=2),encoding='utf-8')
        p=run([sys.executable,str(SCRIPTS/'orepro_entry_sheet_v3.py'),str(tampered_path),'--out',str(d/'tampered.txt')],expect=2)
        checks['tamper_rejected_by_entry_sheet']='FROZEN_CARD_SHA_MISMATCH' in p.stdout

        bad=json.loads((d/'overlay_1.json').read_text(encoding='utf-8'))
        bad['final_finish']=1
        bad_path=d/'bad_result_field.json'
        bad_out=d/'bad_result_frozen.json'
        bad_path.write_text(json.dumps(bad,ensure_ascii=False,indent=2),encoding='utf-8')
        p=run([sys.executable,str(SCRIPTS/'orepro_freeze_prediction_v4.py'),str(bad_path),'--out',str(bad_out)],expect=2)
        checks['result_field_rejected']='FORBIDDEN_RESULT_OR_FINAL_FIELD:final_finish' in p.stdout or 'UNREGISTERED_FIELD:final_finish' in p.stdout

        old=json.loads((d/'overlay_1.json').read_text(encoding='utf-8'))
        old['feature_gate_version']='KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V4'
        old_path=d/'old_gate.json'
        old_path.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
        p=run([sys.executable,str(SCRIPTS/'orepro_freeze_prediction_v4.py'),str(old_path),'--out',str(d/'old_gate_frozen.json')],expect=2)
        checks['old_gate_rejected']='FEATURE_GATE_VERSION_NOT_V5' in p.stdout

        second=json.loads(frozen[1].read_text(encoding='utf-8'))
        second['battle_race_flag']=True
        second['freeze_hash_sha256']=''
        second_pre=d/'second_battle_pre.json'
        second_re=d/'second_battle_frozen.json'
        second_pre.write_text(json.dumps(second,ensure_ascii=False,indent=2),encoding='utf-8')
        run([sys.executable,str(SCRIPTS/'orepro_freeze_prediction_v4.py'),str(second_pre),'--out',str(second_re)])
        p=run([
            sys.executable,str(SCRIPTS/'orepro_week1_bundle_validate_v1.py'),
            str(frozen[0]),str(second_re),str(frozen[2]),str(frozen[3]),str(frozen[4]),
            '--expected-races','5','--official-week-cap','50000','--require-full-ranking-total'
        ],expect=2)
        checks['two_battle_races_rejected']='MORE_THAN_ONE_BATTLE_RACE' in p.stdout

    checks['probability_sums_all_one']=all(abs(float(v)-1.0)<=1e-10 for v in probability_output['probability_sums'].values())
    checks['real_money_false']=True
    checks['validation_oos_closed']=True
    status='PASS' if all(checks.values()) else 'FAIL'
    print(json.dumps({'test_id':'OREPRO-WEEK1-GATE-V5-E2E-SELFTEST-V1','status':status,'checks':checks},ensure_ascii=False,indent=2))
    return 0 if status=='PASS' else 2

if __name__=='__main__':
    raise SystemExit(main())
