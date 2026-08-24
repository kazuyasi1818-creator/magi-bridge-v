#!/usr/bin/env python3
from __future__ import annotations
import math

LAST_START_FEATURES = [
    'days_since_last_start_rebuilt',
    'same_surface_as_last',
    'same_venue_as_last',
    'abs_distance_change_m',
    'same_class_code_as_last',
]


def is_missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return False


def validate_history_row(row: dict) -> list[str]:
    errs: list[str] = []
    try:
        n = int(row.get('horse_prior_starts'))
    except Exception:
        return ['INVALID_HORSE_PRIOR_STARTS']
    if n < 0:
        errs.append('NEGATIVE_HORSE_PRIOR_STARTS')
        return errs
    if n == 0:
        for f in LAST_START_FEATURES:
            if not is_missing(row.get(f)):
                errs.append(f'ZERO_PRIOR_HAS_FABRICATED_HISTORY:{f}')
    else:
        for f in LAST_START_FEATURES:
            if is_missing(row.get(f)):
                errs.append(f'PRIOR_EXISTS_BUT_HISTORY_MISSING:{f}')
    return sorted(set(errs))


def apply_zero_prior_residual_policy(prior_starts: list[int], raw_residual_scores: list[float]) -> list[float]:
    if len(prior_starts) != len(raw_residual_scores) or not prior_starts:
        raise ValueError('prior_starts and raw_residual_scores must have the same non-zero length')
    out: list[float] = []
    for i, (n0, r0) in enumerate(zip(prior_starts, raw_residual_scores)):
        n = int(n0)
        r = float(r0)
        if n < 0:
            raise ValueError(f'negative prior starts at index {i}')
        if not math.isfinite(r):
            raise ValueError(f'non-finite residual score at index {i}')
        out.append(0.0 if n == 0 else r)
    return out
