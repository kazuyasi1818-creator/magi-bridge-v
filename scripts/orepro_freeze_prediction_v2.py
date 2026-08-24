#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path

UNIT = 100
SUPPORTED = {
    "EXACTA_UMA_TAN",
    "QUINELLA_UMA_REN",
    "TRIFECTA_3REN_TAN",
    "TRIO_3REN_PUKU",
}
REQUIRED = [
    "race_id","race_date_jst","venue","race_no","post_time_jst",
    "prediction_frozen_at_jst","submission_deadline_jst","model_version",
    "feature_gate_version","magi_pure_budget_cap_yen","orepro_registered_target_yen",
    "ranking_included_flag","tickets"
]


def parse_dt(v: str) -> datetime:
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return dt


def canonical_payload(card: dict) -> bytes:
    x = deepcopy(card)
    x["freeze_hash_sha256"] = ""
    x["submitted_to_orepro"] = False
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate(card: dict) -> list[str]:
    errs = []
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

    pure_cap = card.get("magi_pure_budget_cap_yen")
    target = card.get("orepro_registered_target_yen")
    for label, v in [("MAGI_PURE_CAP", pure_cap), ("OREPRO_TARGET", target)]:
        if not isinstance(v, int) or v < 0 or v > 10000 or v % UNIT:
            errs.append(f"INVALID_{label}")

    tickets = card.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        errs.append("EMPTY_OR_INVALID_TICKET_UNIVERSE")
        tickets = []

    pure_total = 0
    registered_total = 0
    forced_total = 0
    seen = set()
    by_type = defaultdict(int)
    by_group = defaultdict(int)
    for i, t in enumerate(tickets):
        if not isinstance(t, dict):
            errs.append(f"TICKET_NOT_OBJECT:{i}")
            continue
        bt = str(t.get("bet_type") or "")
        combo = str(t.get("combination") or "").strip()
        if bt not in SUPPORTED:
            errs.append(f"UNSUPPORTED_BET_TYPE:{i}")
        if not combo:
            errs.append(f"MISSING_COMBINATION:{i}")
        key = (bt, combo)
        if key in seen:
            errs.append(f"DUPLICATE_TICKET:{i}")
        seen.add(key)

        pure = t.get("magi_pure_stake_yen")
        reg = t.get("orepro_registered_stake_yen")
        forced = t.get("forced_scale_up_yen")
        for label, v in [("PURE", pure),("REGISTERED", reg),("FORCED", forced)]:
            if not isinstance(v, int) or v < 0 or v % UNIT:
                errs.append(f"INVALID_{label}_STAKE:{i}")
        if all(isinstance(v, int) for v in [pure,reg,forced]):
            pure_total += pure
            registered_total += reg
            forced_total += forced
            if reg < pure:
                errs.append(f"REGISTERED_LT_PURE:{i}")
            if forced != reg - pure:
                errs.append(f"FORCED_DELTA_MISMATCH:{i}")
            by_type[bt] += reg
            by_group[str(t.get("correlation_group") or f"UNGROUPED:{i}")] += reg

        p = t.get("model_probability")
        if p is not None:
            try:
                if not (0.0 < float(p) < 1.0):
                    errs.append(f"INVALID_MODEL_PROBABILITY:{i}")
            except Exception:
                errs.append(f"INVALID_MODEL_PROBABILITY:{i}")
        odds = t.get("purchase_available_decimal_odds")
        if odds is not None:
            try:
                if not (float(odds) > 1.0):
                    errs.append(f"INVALID_PURCHASE_ODDS:{i}")
            except Exception:
                errs.append(f"INVALID_PURCHASE_ODDS:{i}")

    if isinstance(pure_cap, int) and pure_total > pure_cap:
        errs.append("MAGI_PURE_STAKE_EXCEEDS_CAP")
    ranking = bool(card.get("ranking_included_flag"))
    if isinstance(target, int):
        if ranking and registered_total != target:
            errs.append("RANKING_REGISTERED_TOTAL_NOT_TARGET")
        if not ranking and registered_total != pure_total:
            errs.append("NONRANKING_REGISTERED_MUST_EQUAL_PURE")
    if forced_total != registered_total - pure_total:
        errs.append("FORCED_TOTAL_MISMATCH")

    totals = card.get("totals") or {}
    if totals:
        expected = {
            "ticket_count": len(tickets),
            "magi_pure_total_stake_yen": pure_total,
            "orepro_registered_total_stake_yen": registered_total,
            "forced_scale_up_total_yen": forced_total,
        }
        for k,v in expected.items():
            if totals.get(k) != v:
                errs.append(f"TOTALS_MISMATCH:{k}")

    caps = card.get("competition_overlay_caps") or {}
    if ranking and isinstance(target, int) and target > 0:
        try:
            single_ratio = float(caps["single_ticket_ratio"])
            type_ratio = float(caps["bet_type_ratio"])
            group_ratio = float(caps["correlation_group_ratio"])
            if not (0 < single_ratio <= 1 and 0 < type_ratio <= 1 and 0 < group_ratio <= 1):
                raise ValueError
            single_cap = int((target * single_ratio) // UNIT) * UNIT
            type_cap = int((target * type_ratio) // UNIT) * UNIT
            group_cap = int((target * group_ratio) // UNIT) * UNIT
            for i,t in enumerate(tickets):
                reg = t.get("orepro_registered_stake_yen")
                if isinstance(reg,int) and reg > single_cap:
                    errs.append(f"SINGLE_TICKET_CAP_EXCEEDED:{i}")
            for bt,v in by_type.items():
                if v > type_cap:
                    errs.append(f"BET_TYPE_CAP_EXCEEDED:{bt}")
            for g,v in by_group.items():
                if v > group_cap:
                    errs.append(f"CORRELATION_GROUP_CAP_EXCEEDED:{g}")
        except Exception:
            errs.append("INVALID_OVERLAY_CAPS")

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
        print(json.dumps({"status":"FAIL","violations":errs}, ensure_ascii=False, indent=2))
        return 2
    digest = hashlib.sha256(canonical_payload(card)).hexdigest()
    frozen = deepcopy(card)
    frozen["freeze_hash_sha256"] = digest
    Path(args.out).write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"PASS","freeze_hash_sha256":digest,"out":args.out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
