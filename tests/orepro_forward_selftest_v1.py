#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZER = ROOT / "scripts" / "orepro_freeze_prediction_v1.py"
SHEET = ROOT / "scripts" / "orepro_entry_sheet_v1.py"
REPORT = ROOT / "scripts" / "orepro_weekly_report_v1.py"


def run(args, expect=0):
    p = subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True)
    if p.returncode != expect:
        raise AssertionError(f"expected {expect}, got {p.returncode}\nSTDOUT={p.stdout}\nSTDERR={p.stderr}")
    return p


def base_card():
    return {
        "template_id": "OREPRO-PREDICTION-CARD-V1",
        "race_id": "2026082901010101",
        "race_date_jst": "2026-08-29",
        "venue": "札幌",
        "race_no": 1,
        "post_time_jst": "2026-08-29T09:50:00+09:00",
        "prediction_frozen_at_jst": "2026-08-29T09:40:00+09:00",
        "submission_deadline_jst": "2026-08-29T09:48:00+09:00",
        "model_version": "MAGI_FORWARD_BASELINE_V1",
        "feature_gate_version": "KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V4",
        "data_snapshot": {
            "odds_snapshot_time_jst": "2026-08-29T09:39:00+09:00",
            "history_cutoff": "strictly_before_race_date",
            "current_feature_gate_pass": False,
            "source_hashes": ["a" * 64],
        },
        "race_budget_B_yen": 10000,
        "ranking_included_flag": True,
        "battle_race_flag": True,
        "tickets": [
            {"bet_type":"QUINELLA_UMA_REN","combination":"01-02","stake_yen":600,"model_probability":0.20,"purchase_available_decimal_odds":6.0,"expected_value":0.20,"correlation_group":"A"},
            {"bet_type":"TRIO_3REN_PUKU","combination":"01-02-03","stake_yen":400,"model_probability":0.08,"purchase_available_decimal_odds":15.0,"expected_value":0.20,"correlation_group":"A"},
        ],
        "totals": {"ticket_count":2,"total_stake_yen":1000,"unspent_budget_yen":9000},
        "prediction_note": "synthetic",
        "freeze_hash_sha256": "",
        "submitted_to_orepro": False,
        "result_fields_locked_until_after_post": True,
    }


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        card = base_card()
        cardp = td / "card.json"
        frozen = td / "frozen.json"
        sheet = td / "sheet.txt"
        cardp.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

        run([FREEZER, cardp, "--out", frozen], 0)
        f1 = json.loads(frozen.read_text(encoding="utf-8"))
        assert len(f1["freeze_hash_sha256"]) == 64
        first_hash = f1["freeze_hash_sha256"]
        run([FREEZER, cardp, "--out", frozen], 0)
        f2 = json.loads(frozen.read_text(encoding="utf-8"))
        assert f2["freeze_hash_sha256"] == first_hash

        run([SHEET, frozen, "--out", sheet], 0)
        st = sheet.read_text(encoding="utf-8")
        assert "馬連 01-02" in st and "3連複 01-02-03" in st and "合計: 1,000円" in st

        bad = base_card(); bad["data_snapshot"]["odds_snapshot_time_jst"] = "2026-08-29T09:41:00+09:00"
        bp = td / "bad_future.json"; bp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        p = run([FREEZER, bp, "--out", td / "x.json"], 2)
        assert "ODDS_SNAPSHOT_AFTER_FREEZE" in p.stdout

        bad = base_card(); bad["data_snapshot"]["current_feature_gate_pass"] = True
        bp = td / "bad_gate.json"; bp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        p = run([FREEZER, bp, "--out", td / "y.json"], 2)
        assert "CURRENT_FEATURE_GATE_UNPROVEN" in p.stdout

        bad = base_card(); bad["tickets"][0]["stake_yen"] = 9900; bad["totals"]={"ticket_count":2,"total_stake_yen":10300,"unspent_budget_yen":-300}
        bp = td / "bad_budget.json"; bp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        p = run([FREEZER, bp, "--out", td / "z.json"], 2)
        assert "STAKE_EXCEEDS_RACE_BUDGET" in p.stdout

        ledger = td / "ledger.csv"
        fields = "week_id,race_id,race_date_jst,venue,race_no,post_time_jst,prediction_frozen_at_jst,submitted_at_jst,model_version,feature_gate_version,race_budget_B_yen,ranking_included_flag,battle_race_flag,bet_type,combination,stake_yen,model_probability,purchase_available_decimal_odds,expected_value,correlation_group,result_status,hit_flag,normal_payout_yen,orepro_official_payout_yen,magi_pure_return_yen,official_return_yen,rule_violation_flag,notes".split(",")
        with ledger.open("w", encoding="utf-8", newline="") as fh:
            w=csv.DictWriter(fh, fieldnames=fields); w.writeheader()
            base={k:"" for k in fields}; base.update(week_id="2026-W35",race_id="R1",bet_type="QUINELLA_UMA_REN",stake_yen="600",hit_flag="true",magi_pure_return_yen="1200",official_return_yen="2400",rule_violation_flag="false"); w.writerow(base)
            base={k:"" for k in fields}; base.update(week_id="2026-W35",race_id="R1",bet_type="TRIO_3REN_PUKU",stake_yen="400",hit_flag="false",magi_pure_return_yen="0",official_return_yen="0",rule_violation_flag="false"); w.writerow(base)
        report = td / "report.json"
        run([REPORT, ledger, "--week-id", "2026-W35", "--out", report], 0)
        r=json.loads(report.read_text(encoding="utf-8"))
        assert r["stake_yen"] == 1000
        assert r["MAGI_PURE"]["return_yen"] == 1200
        assert r["OREPRO_OFFICIAL"]["return_yen"] == 2400
        assert r["official_minus_pure_return_yen"] == 1200
        assert r["rule_violation_count"] == 0

        proof = {
            "test_id":"OREPRO_FORWARD_PIPELINE_SYNTHETIC_V1",
            "status":"PASS",
            "checks":{
                "valid_card_freezes":True,
                "freeze_hash_deterministic":True,
                "entry_sheet_renders":True,
                "future_odds_snapshot_rejected":True,
                "unproven_current_feature_gate_rejected":True,
                "budget_overspend_rejected":True,
                "official_and_magi_pure_ledgers_separated":True,
                "real_money_bet":False,
                "validation_oos_opened":False,
            },
            "freeze_hash_example": first_hash,
        }
        print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
