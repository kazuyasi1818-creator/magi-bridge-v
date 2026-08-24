#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "scripts" / "orepro_candidate_selector_v2.py"
FIELDS = [
    "race_id","race_date_jst","venue","race_no","field_size",
    "safe_pre_race_odds_available","strict_history_coverage",
    "safe_feature_coverage","first_time_starter_share",
    "timestamp_sensitive_current_features_used"
]


def run(args, expect=0):
    p = subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True)
    if p.returncode != expect:
        raise AssertionError(f"expected {expect}, got {p.returncode}\nSTDOUT={p.stdout}\nSTDERR={p.stderr}")
    return p


def row(race_id, hist, feat, first, *, odds="true", current="false", venue="札幌", date="2026-08-29", field_size=12, race_no=1):
    return {
        "race_id": race_id,
        "race_date_jst": date,
        "venue": venue,
        "race_no": str(race_no),
        "field_size": str(field_size),
        "safe_pre_race_odds_available": odds,
        "strict_history_coverage": str(hist),
        "safe_feature_coverage": str(feat),
        "first_time_starter_share": str(first),
        "timestamp_sensitive_current_features_used": current,
    }


def write_csv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        # Normal deterministic selection and tie-break.
        good = td / "good.csv"
        rows = [
            row("R3", .90, .98, .10, race_no=3),
            row("R1", .95, .99, .05, race_no=1),
            row("R2", .95, .99, .05, race_no=2),
            row("BADHIST", .79, .99, .05, race_no=4),
            row("CURRENT", .99, .99, .05, current="true", race_no=5),
        ]
        write_csv(good, FIELDS, rows)
        out = td / "out.json"
        run([SELECTOR, good, "--out", out, "--max-races", "2"], 0)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["selected_count"] == 2
        assert [x["race_id"] for x in data["selected"]] == ["R1", "R2"]
        assert any("STRICT_HISTORY_COVERAGE_LT_0_80" in x["rejection_reasons"] for x in data["rejected"] if x["race_id"] == "BADHIST")
        assert any("UNLOCKED_CURRENT_FEATURE_USED" in x["rejection_reasons"] for x in data["rejected"] if x["race_id"] == "CURRENT")
        assert all("result" not in x and "payout" not in x and "final_odds" not in x for x in data["selected"])

        # Destructive: post-race result column must fail before evaluation.
        bad = td / "bad_result.csv"
        bad_fields = FIELDS + ["result_status"]
        rr = row("LEAK1", .99, .99, .01); rr["result_status"] = "WIN"
        write_csv(bad, bad_fields, [rr])
        p = run([SELECTOR, bad, "--out", td / "x.json"], 2)
        assert "FORBIDDEN_POSTRACE_OR_FINAL_COLUMN:result_status" in p.stdout

        # Destructive: final odds column must fail.
        bad = td / "bad_final_odds.csv"
        bad_fields = FIELDS + ["final_odds"]
        rr = row("LEAK2", .99, .99, .01); rr["final_odds"] = "4.2"
        write_csv(bad, bad_fields, [rr])
        p = run([SELECTOR, bad, "--out", td / "y.json"], 2)
        assert "FORBIDDEN_POSTRACE_OR_FINAL_COLUMN:final_odds" in p.stdout

        # Destructive: even harmless unknown columns fail closed until preregistered.
        bad = td / "bad_unknown.csv"
        bad_fields = FIELDS + ["memo"]
        rr = row("UNK", .99, .99, .01); rr["memo"] = "x"
        write_csv(bad, bad_fields, [rr])
        p = run([SELECTOR, bad, "--out", td / "z.json"], 2)
        assert "UNPREREGISTERED_INPUT_COLUMN:memo" in p.stdout

        # Numeric ranges must fail eligibility rather than create boosted score.
        bad_range = td / "bad_range.csv"
        write_csv(bad_range, FIELDS, [row("RANGE", 1.5, .99, .01)])
        run([SELECTOR, bad_range, "--out", td / "range.json"], 0)
        rd = json.loads((td / "range.json").read_text(encoding="utf-8"))
        assert rd["selected_count"] == 0
        assert "STRICT_HISTORY_COVERAGE_OUTSIDE_0_1" in rd["rejected"][0]["rejection_reasons"]

        proof = {
            "test_id": "OREPRO_CANDIDATE_SELECTOR_V2_SYNTHETIC",
            "status": "PASS",
            "checks": {
                "deterministic_data_quality_selection": True,
                "race_id_tie_break": True,
                "low_history_rejected": True,
                "unlocked_current_feature_rejected": True,
                "postrace_result_column_rejected": True,
                "final_odds_column_rejected": True,
                "unknown_column_rejected_fail_closed": True,
                "numeric_range_abuse_rejected": True,
                "output_whitelist_only": True,
                "real_money_bet": False,
                "validation_oos_opened": False
            }
        }
        print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
