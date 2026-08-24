#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

VENUES = {"新潟", "中京", "札幌"}
DATES = {"2026-08-29", "2026-08-30"}


def b(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y"}


def f(v: str) -> float:
    return float(str(v).strip())


def evaluate(row: dict) -> dict:
    reasons = []
    try:
        field_size = int(row["field_size"])
        hist = f(row["strict_history_coverage"])
        feat = f(row["safe_feature_coverage"])
        first = f(row["first_time_starter_share"])
    except Exception as e:
        raise ValueError(f"invalid numeric fields for race {row.get('race_id')}") from e

    if row.get("race_date_jst") not in DATES:
        reasons.append("OUTSIDE_WEEK1_DATES")
    if row.get("venue") not in VENUES:
        reasons.append("OUTSIDE_WEEK1_VENUES")
    if not b(row.get("safe_pre_race_odds_available")):
        reasons.append("NO_SAFE_PRE_RACE_ODDS")
    if hist < 0.80:
        reasons.append("STRICT_HISTORY_COVERAGE_LT_0_80")
    if feat < 0.95:
        reasons.append("SAFE_FEATURE_COVERAGE_LT_0_95")
    if not (8 <= field_size <= 18):
        reasons.append("FIELD_SIZE_OUTSIDE_8_18")
    if first > 0.30:
        reasons.append("FIRST_TIME_STARTER_SHARE_GT_0_30")
    if b(row.get("timestamp_sensitive_current_features_used")):
        reasons.append("UNLOCKED_CURRENT_FEATURE_USED")

    score = 0.50 * hist + 0.30 * feat + 0.20 * (1.0 - first)
    return {
        **row,
        "data_quality_score": score,
        "eligible": not reasons,
        "rejection_reasons": reasons,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("race_candidates_csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-races", type=int, default=5)
    args = ap.parse_args()
    if args.max_races < 1 or args.max_races > 5:
        raise SystemExit("--max-races must be 1..5")

    with Path(args.race_candidates_csv).open(encoding="utf-8-sig", newline="") as fh:
        rows = [evaluate(r) for r in csv.DictReader(fh)]

    eligible = [r for r in rows if r["eligible"]]
    eligible.sort(key=lambda r: (-float(r["data_quality_score"]), str(r.get("race_id") or "")))
    selected = eligible[: args.max_races]

    out = {
        "selector_id": "OREPRO-WEEK1-CANDIDATE-SELECTOR-V1",
        "selection_rule": "data quality only; no outcome/payout/final odds inputs",
        "candidate_count": len(rows),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selected": selected,
        "rejected": [r for r in rows if not r["eligible"]],
        "ranking_requirement_forced": False,
        "real_money_bet": False,
        "validation_oos_opened": False,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
