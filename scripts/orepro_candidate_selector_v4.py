#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
import orepro_candidate_selector_v3 as v3


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
        header_errors = v3.validate_headers(reader.fieldnames)
        if header_errors:
            print(json.dumps({"status":"FAIL","selector_id":"OREPRO-WEEK1-CANDIDATE-SELECTOR-V4","violations":header_errors}, ensure_ascii=False, indent=2))
            return 2
        rows = [v3.evaluate(r) for r in reader]

    eligible = [r for r in rows if r["eligible"]]
    eligible.sort(key=lambda r: (-float(r["data_quality_score"]), str(r.get("race_id") or "")))
    selected = eligible[:args.max_races]
    out = {
        "selector_id":"OREPRO-WEEK1-CANDIDATE-SELECTOR-V4",
        "prereg_id":"OREPRO-WEEK1-CANDIDATE-SELECTION-V4",
        "required_snapshot_gate":"KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5",
        "selection_rule":"newcomer races excluded; preregistered safe data-quality score only; no race-day current feature used for Thursday ranking",
        "candidate_count":len(rows),
        "eligible_count":len(eligible),
        "selected_count":len(selected),
        "selected":selected,
        "rejected":[r for r in rows if not r["eligible"]],
        "reserve":[r for r in eligible[args.max_races:]],
        "newcomer_races_can_be_selected":False,
        "result_information_used":False,
        "ranking_requirement_forced":False,
        "real_money_bet":False,
        "validation_oos_opened":False
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
