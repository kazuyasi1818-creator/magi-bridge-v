#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from keiba_market_preserving_residual_v1 import market_preserving_residual, uncertainty_shrunk_alpha


def close(a, b, tol=1e-12):
    return abs(a-b) <= tol


def main():
    p = [0.40, 0.25, 0.15, 0.12, 0.08]
    r = [1.2, 0.4, -0.1, -0.7, -1.3]

    q0 = market_preserving_residual(p, r, alpha_eff=0.0, residual_clip=2.0)
    qc = market_preserving_residual(p, [3,3,3,3,3], alpha_eff=0.7, residual_clip=2.0)
    q = market_preserving_residual(p, r, alpha_eff=0.5, residual_clip=1.0)
    a_low = uncertainty_shrunk_alpha(0.8, normalized_uncertainty=0.2, shrink_strength=0.75)
    a_high = uncertainty_shrunk_alpha(0.8, normalized_uncertainty=0.9, shrink_strength=0.75)

    checks = {
        "alpha_zero_exact_market": all(close(a,b) for a,b in zip(q0,p)),
        "constant_residual_exact_market": all(close(a,b) for a,b in zip(qc,p)),
        "positive_probabilities": all(x > 0 and math.isfinite(x) for x in q),
        "sum_to_one": close(sum(q), 1.0),
        "higher_uncertainty_reduces_alpha": a_high < a_low,
        "alpha_nonnegative": a_high >= 0 and a_low >= 0,
    }
    out = {
        "test_id": "KEIBA-MARKET-PRESERVING-RESIDUAL-V1-SYNTHETIC",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "example": {"market":p,"candidate":q,"alpha_low_uncertainty":a_low,"alpha_high_uncertainty":a_high},
        "real_race_data_used": False,
        "validation_opened": False,
        "oos_opened": False,
        "real_money_bet": False,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out["status"] != "PASS":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
