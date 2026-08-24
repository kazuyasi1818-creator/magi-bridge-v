#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from copy import deepcopy
from pathlib import Path
import orepro_freeze_prediction_v3 as v3

EXPECTED_TEMPLATE = 'OREPRO-PREDICTION-CARD-V3'
ALLOWED_TOP = {
    'template_id','race_id','race_date_jst','venue','race_no','post_time_jst',
    'prediction_frozen_at_jst','submission_deadline_jst','model_version','shadow_model_versions',
    'feature_gate_version','data_snapshot','magi_pure_budget_cap_yen','orepro_registered_target_yen',
    'ranking_included_flag','battle_race_flag','competition_overlay_caps','tickets','totals',
    'prediction_note','freeze_hash_sha256','submitted_to_orepro','result_fields_locked_until_after_post'
}
ALLOWED_SNAPSHOT = {
    'odds_snapshot_time_jst','history_cutoff','current_feature_gate_pass',
    'gate_v5_handoff_sha256','source_hashes'
}
ALLOWED_TICKET = {
    'bet_type','combination','magi_pure_stake_yen','competition_weight',
    'orepro_registered_stake_yen','forced_scale_up_yen','model_probability',
    'purchase_available_decimal_odds','expected_value','correlation_group'
}
ALLOWED_TOTALS = {
    'ticket_count','magi_pure_total_stake_yen','orepro_registered_total_stake_yen',
    'forced_scale_up_total_yen'
}
ALLOWED_CAPS = {'single_ticket_ratio','bet_type_ratio','correlation_group_ratio'}
FORBIDDEN_KEY_TOKENS = (
    'finish','winner','payout','payoff','refund','hit_flag','final_odds','closing_odds',
    'confirmed_odds','return_yen','着順','払戻','結果'
)


def unknown(prefix: str, obj: object, allowed: set[str]) -> list[str]:
    if not isinstance(obj, dict):
        return []
    return [f'UNREGISTERED_FIELD:{prefix}{k}' for k in sorted(set(obj) - allowed)]


def validate(card: dict) -> list[str]:
    errs = set(v3.validate(card))
    if card.get('template_id') != EXPECTED_TEMPLATE:
        errs.add('PREDICTION_CARD_TEMPLATE_NOT_V3')
    errs.update(unknown('', card, ALLOWED_TOP))
    errs.update(unknown('data_snapshot.', card.get('data_snapshot'), ALLOWED_SNAPSHOT))
    errs.update(unknown('competition_overlay_caps.', card.get('competition_overlay_caps'), ALLOWED_CAPS))
    errs.update(unknown('totals.', card.get('totals'), ALLOWED_TOTALS))
    tickets = card.get('tickets') if isinstance(card.get('tickets'), list) else []
    for i, t in enumerate(tickets):
        errs.update(unknown(f'tickets[{i}].', t, ALLOWED_TICKET))

    def walk(x: object, path: str = '') -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                key = str(k)
                if key != 'result_fields_locked_until_after_post':
                    low = key.lower()
                    if any(tok.lower() in low for tok in FORBIDDEN_KEY_TOKENS):
                        errs.add(f'FORBIDDEN_RESULT_OR_FINAL_FIELD:{path}{key}')
                walk(v, f'{path}{key}.')
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f'{path}[{i}].')
    walk(card)
    return sorted(errs)


def canonical_payload(card: dict) -> bytes:
    return v3.canonical_payload(card)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('card_json')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    card = json.loads(Path(args.card_json).read_text(encoding='utf-8'))
    errs = validate(card)
    if errs:
        print(json.dumps({'status':'FAIL','validator':'OREPRO_FREEZE_V4_STRICT_GATE_V5','violations':errs}, ensure_ascii=False, indent=2))
        return 2
    digest = hashlib.sha256(canonical_payload(card)).hexdigest()
    frozen = deepcopy(card)
    frozen['freeze_hash_sha256'] = digest
    Path(args.out).write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status':'PASS','validator':'OREPRO_FREEZE_V4_STRICT_GATE_V5','freeze_hash_sha256':digest,'out':args.out}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
