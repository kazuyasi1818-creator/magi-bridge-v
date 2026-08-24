#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

UNIT = 100
SUPPORTED = {
    "EXACTA_UMA_TAN",
    "QUINELLA_UMA_REN",
    "TRIFECTA_3REN_TAN",
    "TRIO_3REN_PUKU",
}


def ratio_cap_units(target_yen: int, ratio: float) -> int:
    return int((target_yen * ratio) // UNIT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("card_json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    card = json.loads(Path(args.card_json).read_text(encoding="utf-8"))
    out = deepcopy(card)
    tickets = out.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        print(json.dumps({"status":"FAIL","violations":["EMPTY_TICKET_UNIVERSE"]}, ensure_ascii=False))
        return 2

    ranking = bool(out.get("ranking_included_flag"))
    target = int(out.get("orepro_registered_target_yen", 0) or 0)
    pure_cap = int(out.get("magi_pure_budget_cap_yen", 0) or 0)
    if target < 0 or target > 10000 or target % UNIT:
        print(json.dumps({"status":"FAIL","violations":["INVALID_OFFICIAL_TARGET"]}, ensure_ascii=False))
        return 2
    if pure_cap < 0 or pure_cap > 10000 or pure_cap % UNIT:
        print(json.dumps({"status":"FAIL","violations":["INVALID_MAGI_PURE_CAP"]}, ensure_ascii=False))
        return 2

    errs = []
    pure_units = []
    weights = []
    keys = []
    groups = []
    types = []
    seen = set()
    for i, t in enumerate(tickets):
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
        stake = t.get("magi_pure_stake_yen", 0)
        if not isinstance(stake, int) or stake < 0 or stake % UNIT:
            errs.append(f"INVALID_MAGI_PURE_STAKE:{i}")
            stake = 0
        w = t.get("competition_weight", 0.0)
        try:
            w = float(w)
        except Exception:
            w = -1.0
        if w < 0:
            errs.append(f"INVALID_COMPETITION_WEIGHT:{i}")
            w = 0.0
        if w == 0 and stake > 0:
            w = float(stake)
        pure_units.append(stake // UNIT)
        weights.append(w)
        keys.append(f"{bt}:{combo}")
        groups.append(str(t.get("correlation_group") or f"UNGROUPED:{i}"))
        types.append(bt)

    pure_total_yen = sum(pure_units) * UNIT
    if pure_total_yen > pure_cap:
        errs.append("MAGI_PURE_STAKE_EXCEEDS_CAP")
    if pure_total_yen > target and ranking:
        errs.append("MAGI_PURE_STAKE_EXCEEDS_OFFICIAL_TARGET")
    if errs:
        print(json.dumps({"status":"FAIL","violations":sorted(set(errs))}, ensure_ascii=False, indent=2))
        return 2

    if not ranking:
        for t, u in zip(tickets, pure_units):
            t["orepro_registered_stake_yen"] = u * UNIT
            t["forced_scale_up_yen"] = 0
        out["totals"] = {
            "ticket_count": len(tickets),
            "magi_pure_total_stake_yen": pure_total_yen,
            "orepro_registered_total_stake_yen": pure_total_yen,
            "forced_scale_up_total_yen": 0,
        }
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status":"PASS","ranking_overlay":False,"out":args.out}, ensure_ascii=False))
        return 0

    if target == 0:
        print(json.dumps({"status":"FAIL","violations":["ZERO_TARGET_FOR_RANKING_ENTRY"]}, ensure_ascii=False))
        return 2
    if sum(weights) <= 0:
        print(json.dumps({"status":"FAIL","violations":["NO_POSITIVE_COMPETITION_WEIGHTS"]}, ensure_ascii=False))
        return 2

    caps = out.get("competition_overlay_caps") or {}
    try:
        single_ratio = float(caps["single_ticket_ratio"])
        type_ratio = float(caps["bet_type_ratio"])
        group_ratio = float(caps["correlation_group_ratio"])
    except Exception:
        print(json.dumps({"status":"FAIL","violations":["INVALID_OVERLAY_CAPS"]}, ensure_ascii=False))
        return 2
    if not (0 < single_ratio <= 1 and 0 < type_ratio <= 1 and 0 < group_ratio <= 1):
        print(json.dumps({"status":"FAIL","violations":["INVALID_OVERLAY_CAP_RATIOS"]}, ensure_ascii=False))
        return 2

    target_units = target // UNIT
    single_cap = ratio_cap_units(target, single_ratio)
    type_cap = ratio_cap_units(target, type_ratio)
    group_cap = ratio_cap_units(target, group_ratio)
    alloc = list(pure_units)
    by_type = defaultdict(int)
    by_group = defaultdict(int)
    for i, u in enumerate(alloc):
        by_type[types[i]] += u
        by_group[groups[i]] += u
        if u > single_cap:
            errs.append(f"PURE_EXCEEDS_SINGLE_TICKET_CAP:{i}")
    for bt, u in by_type.items():
        if u > type_cap:
            errs.append(f"PURE_EXCEEDS_BET_TYPE_CAP:{bt}")
    for g, u in by_group.items():
        if u > group_cap:
            errs.append(f"PURE_EXCEEDS_CORRELATION_GROUP_CAP:{g}")
    if errs:
        print(json.dumps({"status":"FAIL","violations":sorted(set(errs))}, ensure_ascii=False, indent=2))
        return 2

    total_weight = sum(weights)
    desired = [target_units * (w / total_weight) for w in weights]

    while sum(alloc) < target_units:
        candidates = []
        for i, w in enumerate(weights):
            if w <= 0:
                continue
            if alloc[i] + 1 > single_cap:
                continue
            if by_type[types[i]] + 1 > type_cap:
                continue
            if by_group[groups[i]] + 1 > group_cap:
                continue
            deficit = desired[i] - alloc[i]
            candidates.append((deficit, w, keys[i], i))
        if not candidates:
            print(json.dumps({
                "status":"FAIL",
                "violations":["OVERLAY_CAPACITY_INSUFFICIENT"],
                "allocated_yen":sum(alloc)*UNIT,
                "target_yen":target,
            }, ensure_ascii=False, indent=2))
            return 2
        candidates.sort(key=lambda x: (-x[0], -x[1], x[2]))
        i = candidates[0][3]
        alloc[i] += 1
        by_type[types[i]] += 1
        by_group[groups[i]] += 1

    for t, p, a in zip(tickets, pure_units, alloc):
        reg = a * UNIT
        pure = p * UNIT
        t["orepro_registered_stake_yen"] = reg
        t["forced_scale_up_yen"] = reg - pure

    out["totals"] = {
        "ticket_count": len(tickets),
        "magi_pure_total_stake_yen": pure_total_yen,
        "orepro_registered_total_stake_yen": sum(alloc) * UNIT,
        "forced_scale_up_total_yen": sum((a-p) * UNIT for p, a in zip(pure_units, alloc)),
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status":"PASS",
        "ranking_overlay":True,
        "magi_pure_total_stake_yen":pure_total_yen,
        "orepro_registered_total_stake_yen":sum(alloc)*UNIT,
        "forced_scale_up_total_yen":sum((a-p)*UNIT for p,a in zip(pure_units,alloc)),
        "out":args.out,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
