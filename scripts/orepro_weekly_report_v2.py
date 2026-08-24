#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def to_i(v):
    s=str(v or '').strip()
    return int(float(s)) if s else 0


def to_b(v):
    return str(v or '').strip().lower() in {'1','true','yes','y'}


def rr(ret, stake):
    return (ret/stake) if stake else None


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('ledger_csv')
    ap.add_argument('--week-id',required=True)
    ap.add_argument('--out',required=True)
    args=ap.parse_args()

    rows=[]
    with Path(args.ledger_csv).open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r.get('week_id')==args.week_id:
                rows.append(r)

    pure_stake=sum(to_i(r.get('magi_pure_stake_yen')) for r in rows)
    reg_stake=sum(to_i(r.get('orepro_registered_stake_yen')) for r in rows)
    forced=sum(to_i(r.get('forced_scale_up_yen')) for r in rows)
    pure_return=sum(to_i(r.get('magi_pure_return_yen')) for r in rows)
    norm_return=sum(to_i(r.get('orepro_normalized_return_yen')) for r in rows)
    official_return=sum(to_i(r.get('orepro_official_return_yen')) for r in rows)
    violations=sum(1 for r in rows if to_b(r.get('rule_violation_flag')))
    races=sorted({r.get('race_id') for r in rows if r.get('race_id')})
    pure_hit_races=sorted({r.get('race_id') for r in rows if r.get('race_id') and to_b(r.get('hit_flag')) and to_i(r.get('magi_pure_stake_yen'))>0})

    by_type=defaultdict(lambda:{'magi_pure_stake_yen':0,'orepro_registered_stake_yen':0,'magi_pure_return_yen':0,'orepro_normalized_return_yen':0,'orepro_official_return_yen':0,'tickets':0,'hits':0})
    for r in rows:
        d=by_type[r.get('bet_type') or 'UNKNOWN']
        for k in ['magi_pure_stake_yen','orepro_registered_stake_yen','magi_pure_return_yen','orepro_normalized_return_yen','orepro_official_return_yen']:
            d[k]+=to_i(r.get(k))
        d['tickets']+=1
        d['hits']+=int(to_b(r.get('hit_flag')))
    for d in by_type.values():
        d['magi_pure_return_rate']=rr(d['magi_pure_return_yen'],d['magi_pure_stake_yen'])
        d['orepro_normalized_return_rate']=rr(d['orepro_normalized_return_yen'],d['orepro_registered_stake_yen'])
        d['orepro_official_return_rate']=rr(d['orepro_official_return_yen'],d['orepro_registered_stake_yen'])

    out={
      'report_id':'OREPRO-WEEKLY-THREE-LAYER-V2',
      'week_id':args.week_id,
      'race_count':len(races),
      'ticket_rows':len(rows),
      'OREPRO_OFFICIAL':{
        'stake_yen':reg_stake,
        'return_yen':official_return,
        'return_rate':rr(official_return,reg_stake),
        'net_yen':official_return-reg_stake,
      },
      'OREPRO_NORMALIZED':{
        'stake_yen':reg_stake,
        'return_yen':norm_return,
        'return_rate':rr(norm_return,reg_stake),
        'net_yen':norm_return-reg_stake,
      },
      'MAGI_PURE':{
        'stake_yen':pure_stake,
        'return_yen':pure_return,
        'return_rate':rr(pure_return,pure_stake),
        'net_yen':pure_return-pure_stake,
        'race_hit_rate':(len(pure_hit_races)/len(races)) if races else None,
      },
      'diagnostic':{
        'forced_scale_up_yen':forced,
        'official_bonus_effect_yen':official_return-norm_return,
        'registered_minus_magi_pure_stake_yen':reg_stake-pure_stake,
        'rule_violation_count':violations,
        'rank_eligibility_target_met':len(races)>=5 and reg_stake>=50000,
      },
      'by_bet_type':dict(sorted(by_type.items())),
      'interpretation_guard':'OREPRO_OFFICIAL is competition score, OREPRO_NORMALIZED removes platform bonus effects, MAGI_PURE evaluates only pre-race MAGI-recommended stakes. Do not use one layer as a substitute for another.',
    }
    Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
