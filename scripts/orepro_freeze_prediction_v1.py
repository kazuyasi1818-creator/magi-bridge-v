#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

SUPPORTED = {
    "EXACTA_UMA_TAN",
    "QUINELLA_UMA_REN",
    "TRIFECTA_3REN_TAN",
    "TRIO_3REN_PUKU",
}

REQUIRED = [
    "race_id", "race_date_jst", "venue", "race_no", "post_time_jst",
    "prediction_frozen_at_jst", "submission_deadline_jst", "model_version",
    "feature_gate_version", "race_budget_B_yen", "tickets",
]


def parse_dt(v: str) -> datetime:
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        raise ValueError(f"timezone-aware datetime required: {v}")
    return dt


def canonical_payload(card: dict) -> bytes:
    x = deepcopy(card)
    x["freeze_hash_sha256"] = ""
    # Submission is a later operational receipt, not part of the frozen prediction.
    x["submitted_to_orepro"] = False
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate(card: dict) -> list[str]:
    errs: list[str] = []
    for k in REQUIRED:
        if k not in card or card[k] in (None, ""):
            errs.append(f"MISSING_REQUIRED:{k}")

    try:
        post = parse_dt(str(card.get("post_time_jst", "")))
        freeze = parse_dt(str(card.get("prediction_frozen_at_jst", "")))
        deadline = parse_dt(str(card.get("submission_deadline_jst", "")))
        if freeze > deadline:
            errs.append("FREEZE_AFTER_SUBMISSION_DEADLINE")
        if deadline >= post:
            errs.append("SUBMISSION_DEADLINE_NOT_BEFORE_POST")
    except Exception:
        errs.append("INVALID_RACE_TIMES")

    budget = card.get("race_budget_B_yen")
    if not isinstance(budget, int) or budget < 0 or budget > 10000 or budget % 100 != 0:
        errs.append("INVALID_RACE_BUDGET")

    tickets = card.get("tickets")
    if not isinstance(tickets, list):
        errs.append("TICKETS_NOT_LIST")
        tickets = []

    total = 0
    seen = set()
    for i, t in enumerate(tickets):
        if not isinstance(t, dict):
            errs.append(f"TICKET_NOT_OBJECT:{i}")
            continue
        bt = str(t.get("bet_type") or "")
        combo = str(t.get("combination") or "").strip()
        stake = t.get("stake_yen")
        if bt not in SUPPORTED:
            errs.append(f"UNSUPPORTED_BET_TYPE:{i}")
        if not combo:
            errs.append(f"MISSING_COMBINATION:{i}")
        key = (bt, combo)
        if key in seen:
            errs.append(f"DUPLICATE_TICKET:{i}")
        seen.add(key)
        if not isinstance(stake, int) or stake <= 0 or stake % 100 != 0:
            errs.append(f"INVALID_STAKE:{i}")
        else:
            total += stake
        p = t.get("model_probability")
        if p is not None and not (0.0 < float(p) < 1.0):
            errs.append(f"INVALID_MODEL_PROBABILITY:{i}")
        odds = t.get("purchase_available_decimal_odds")
        if odds is not None and not (float(odds) > 1.0):
            errs.append(f"INVALID_PURCHASE_ODDS:{i}")

    if isinstance(budget, int) and total > budget:
        errs.append("STAKE_EXCEEDS_RACE_BUDGET")

    totals = card.get("totals") or {}
    if totals:
        if totals.get("ticket_count") != len(tickets):
            errs.append("TOTALS_TICKET_COUNT_MISMATCH")
        if totals.get("total_stake_yen") != total:
            errs.append("TOTALS_STAKE_MISMATCH")
        if isinstance(budget, int) and totals.get("unspent_budget_yen") != budget - total:
            errs.append("TOTALS_UNSPENT_MISMATCH")

    snap = card.get("data_snapshot") or {}
    snap_time = snap.get("odds_snapshot_time_jst")
    if snap_time:
        try:
            sdt = parse_dt(str(snap_time))
            fdt = parse_dt(str(card.get("prediction_frozen_at_jst", "")))
            if sdt > fdt:
                errs.append("ODDS_SNAPSHOT_AFTER_FREEZE")
        except Exception:
            errs.append("INVALID_ODDS_SNAPSHOT_TIME")

    # Until a real Gate-v4 forward capture passes, first-week cards must remain false.
    if snap.get("current_feature_gate_pass") not in (False, None):
        errs.append("CURRENT_FEATURE_GATE_UNPROVEN")

    if card.get("result_fields_locked_until_after_post") is not True:
        errs.append("RESULT_FIELDS_NOT_LOCKED")

    return sorted(set(errs))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("card_json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    card = json.loads(Path(args.card_json).read_text(encoding="utf-8"))
    errs = validate(card)
    if errs:
        print(json.dumps({"status": "FAIL", "violations": errs}, ensure_ascii=False, indent=2))
        return 2

    digest = hashlib.sha256(canonical_payload(card)).hexdigest()
    frozen = deepcopy(card)
    frozen["freeze_hash_sha256"] = digest
    Path(args.out).write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "freeze_hash_sha256": digest, "out": args.out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
