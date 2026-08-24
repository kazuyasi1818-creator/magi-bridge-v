#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

VENUES = {"新潟", "中京", "札幌"}
DATES = {"2026-08-29", "2026-08-30"}

REQUIRED_COLUMNS = {
    "race_id","race_date_jst","venue","race_no","field_size",
    "is_newcomer_race","safe_pre_race_odds_available","strict_history_coverage",
    "safe_feature_coverage","first_time_starter_share",
    "timestamp_sensitive_current_features_used",
}

FORBIDDEN_COLUMN_TOKENS = {
    "result","finish","winner","payout","payoff","refund","return_yen",
    "hit_flag","final_odds","closing_odds","confirmed_odds","確定オッズ",
    "払戻","着順","結果",
}

OUTPUT_COLUMNS = sorted(REQUIRED_COLUMNS)


def b(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y"}


def f(v: str) -> float:
    return float(str(v).strip())


def validate_headers(fieldnames: list[str] | None) -> list[str]:
    names = [str(x or "").strip() for x in (fieldnames or [])]
    errs: list[str] = []
    missing = sorted(REQUIRED_COLUMNS - set(names))
    errs.extend(f"MISSING_REQUIRED_COLUMN:{x}" for x in missing)
    for original in names:
        low = original.lower()
        if any(tok.lower() in low for tok in FORBIDDEN_COLUMN_TOKENS):
            errs.append(f"FORBIDDEN_POSTRACE_OR_FINAL_COLUMN:{original}")
    unknown = sorted(set(names) - set(OUTPUT_COLUMNS))
    errs.extend(f"UNPREREGISTERED_INPUT_COLUMN:{x}" for x in unknown)
    return sorted(set(errs))


def evaluate(row: dict) -> dict:
    reasons: list[str] = []
    try:
        field_size = int(row["field_size"])
        hist = f(row["strict_history_coverage"])
        feat = f(row["safe_feature_coverage"])
        first = f(row["first_time_starter_share"])
    except Exception as e:
        raise ValueError(f"invalid numeric fields for race {row.get('race_id')}") from e

    if b(row.get("is_newcomer_race")):
        reasons.append("NEWCOMER_RACE_EXCLUDED")
    if not (0.0 <= hist <= 1.0):
        reasons.append("STRICT_HISTORY_COVERAGE_OUTSIDE_0_1")
    if not (0.0 <= feat <= 1.0):
        reasons.append("SAFE_FEATURE_COVERAGE_OUTSIDE_0_1")
    if not (0.0 <= first <= 1.0):
        reasons.append("FIRST_TIME_STARTER_SHARE_OUTSIDE_0_1")
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
    safe = {k: row.get(k, "") for k in OUTPUT_COLUMNS}
    return {**safe, "data_quality_score": score, "eligible": not reasons, "rejection_reasons": reasons}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("race_candidates_csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-races", type=int, default=5)
    args = ap.parse_args()
    if args.max_races < 1 or args.max_races > 5:
        raise SystemExit("--max-races must be 1..5")

    with Path(args.race_candidates_csv).open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header_errors = validate_headers(reader.fieldnames)
        if header_errors:
            print(json.dumps({"status":"FAIL","violations":header_errors}, ensure_ascii=False, indent=2))
            return 2
        rows = [evaluate(r) for r in reader]

    eligible = [r for r in rows if r["eligible"]]
    eligible.sort(key=lambda r: (-float(r["data_quality_score"]), str(r.get("race_id") or "")))
    selected = eligible[:args.max_races]
    out = {
        "selector_id":"OREPRO-WEEK1-CANDIDATE-SELECTOR-V3",
        "selection_rule":"newcomer races excluded first; remaining races ranked by preregistered data-quality score only",
        "candidate_count":len(rows),
        "eligible_count":len(eligible),
        "selected_count":len(selected),
        "selected":selected,
        "rejected":[r for r in rows if not r["eligible"]],
        "newcomer_races_can_be_selected":False,
        "ranking_requirement_forced":False,
        "real_money_bet":False,
        "validation_oos_opened":False,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
