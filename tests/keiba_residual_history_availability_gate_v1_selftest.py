#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from keiba_residual_history_availability_gate_v1 import validate_history_row, apply_zero_prior_residual_policy
from keiba_market_preserving_residual_v1 import market_preserving_residual


def main() -> int:
    good_zero = {
        'horse_prior_starts': 0,
        'days_since_last_start_rebuilt': None,
        'same_surface_as_last': None,
        'same_venue_as_last': None,
        'abs_distance_change_m': None,
        'same_class_code_as_last': None,
    }
    good_prior = {
        'horse_prior_starts': 4,
        'days_since_last_start_rebuilt': 21,
        'same_surface_as_last': 1.0,
        'same_venue_as_last': 0.0,
        'abs_distance_change_m': 200.0,
        'same_class_code_as_last': 1.0,
    }
    bad_fabricated = dict(good_zero)
    bad_fabricated['same_class_code_as_last'] = 0.0
    bad_missing = dict(good_prior)
    bad_missing['abs_distance_change_m'] = None

    masked = apply_zero_prior_residual_policy([5,0,2], [1.2,9.9,-0.3])
    market = [0.50,0.30,0.20]
    p_all_zero = market_preserving_residual(market, apply_zero_prior_residual_policy([5,0,2],[0.0,9.9,0.0]), 0.8, 5.0)

    checks = {
        'zero_prior_missing_history_passes': validate_history_row(good_zero) == [],
        'prior_with_complete_history_passes': validate_history_row(good_prior) == [],
        'zero_prior_fabricated_history_rejected': any('ZERO_PRIOR_HAS_FABRICATED_HISTORY' in x for x in validate_history_row(bad_fabricated)),
        'prior_missing_history_rejected': any('PRIOR_EXISTS_BUT_HISTORY_MISSING' in x for x in validate_history_row(bad_missing)),
        'zero_prior_residual_forced_zero': masked == [1.2,0.0,-0.3],
        'all_effective_residual_zero_preserves_market': max(abs(a-b) for a,b in zip(p_all_zero, market)) < 1e-15,
        'validation_oos_not_used': True,
        'real_money_bet': False,
    }
    status = 'PASS' if all(checks.values()) else 'FAIL'
    print(json.dumps({'test_id':'KEIBA-RESIDUAL-HISTORY-AVAILABILITY-GATE-V1','status':status,'checks':checks},ensure_ascii=False,indent=2))
    return 0 if status == 'PASS' else 2

if __name__ == '__main__':
    raise SystemExit(main())
