#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import orepro_freeze_prediction_v4 as freeze_v4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('cards', nargs='+')
    ap.add_argument('--expected-races', type=int)
    ap.add_argument('--official-week-cap', type=int, default=50000)
    ap.add_argument('--require-full-ranking-total', action='store_true')
    args = ap.parse_args()

    errs: list[str] = []
    if not (1 <= len(args.cards) <= 5):
        errs.append('CARD_COUNT_OUTSIDE_1_5')
    if args.expected_races is not None and len(args.cards) != args.expected_races:
        errs.append('EXPECTED_RACE_COUNT_MISMATCH')

    race_ids = []
    official_total = 0
    pure_total = 0
    battle_count = 0
    ranking_count = 0
    summaries = []

    for path_text in args.cards:
        p = Path(path_text)
        c = json.loads(p.read_text(encoding='utf-8'))
        local = freeze_v4.validate(c)
        if local:
            errs.extend(f'{p.name}:{x}' for x in local)
        declared = str(c.get('freeze_hash_sha256') or '')
        actual = hashlib.sha256(freeze_v4.canonical_payload(c)).hexdigest()
        if declared != actual:
            errs.append(f'{p.name}:FROZEN_CARD_SHA_MISMATCH')

        race_id = str(c.get('race_id') or '')
        race_ids.append(race_id)
        reg = sum(int(t.get('orepro_registered_stake_yen',0)) for t in c.get('tickets',[]) if isinstance(t,dict))
        pure = sum(int(t.get('magi_pure_stake_yen',0)) for t in c.get('tickets',[]) if isinstance(t,dict))
        official_total += reg
        pure_total += pure
        if bool(c.get('battle_race_flag')):
            battle_count += 1
        if bool(c.get('ranking_included_flag')):
            ranking_count += 1
        summaries.append({'race_id':race_id,'official_stake_yen':reg,'magi_pure_stake_yen':pure,'battle':bool(c.get('battle_race_flag'))})

    if len(race_ids) != len(set(race_ids)):
        errs.append('DUPLICATE_RACE_ID')
    if battle_count > 1:
        errs.append('MORE_THAN_ONE_BATTLE_RACE')
    if official_total > args.official_week_cap:
        errs.append('OFFICIAL_WEEK_CAP_EXCEEDED')
    if args.require_full_ranking_total:
        if args.expected_races is None:
            errs.append('EXPECTED_RACES_REQUIRED_FOR_FULL_RANKING_TOTAL')
        expected_total = (args.expected_races or 0) * 10000
        if official_total != expected_total:
            errs.append('FULL_RANKING_TOTAL_NOT_REACHED')
        if ranking_count != (args.expected_races or 0):
            errs.append('NOT_ALL_CARDS_RANKING_INCLUDED')

    result = {
        'validator_id':'OREPRO-WEEK1-BUNDLE-VALIDATOR-V1',
        'status':'PASS' if not errs else 'FAIL',
        'card_count':len(args.cards),
        'official_total_stake_yen':official_total,
        'magi_pure_total_stake_yen':pure_total,
        'forced_scale_up_total_yen':official_total-pure_total,
        'battle_race_count':battle_count,
        'ranking_card_count':ranking_count,
        'cards':summaries,
        'violations':sorted(set(errs)),
        'real_money_bet':False,
        'validation_oos_opened':False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errs else 2

if __name__ == '__main__':
    raise SystemExit(main())
