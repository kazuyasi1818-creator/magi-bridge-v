#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

BET_TYPES = {"TRIFECTA_3REN_TAN", "TRIO_3REN_PUKU", "EXACTA_UMA_TAN", "QUINELLA_UMA_REN"}
METHODS = {"equal_among_qualified_tickets", "edge_proportional_with_caps", "fractional_kelly_with_race_cap"}


def floor_unit(x: float, unit: int) -> int:
    return max(0, int(math.floor((x + 1e-12) / unit)) * unit)


def ticket_metrics(t: dict) -> dict:
    p = float(t["model_probability"])
    odds = float(t["market_odds"])
    if not (0.0 < p < 1.0):
        raise ValueError(f"invalid model_probability for {t.get('ticket_id')}: {p}")
    if odds <= 1.0:
        raise ValueError(f"invalid market_odds for {t.get('ticket_id')}: {odds}")
    ev = p * odds - 1.0
    b = odds - 1.0
    kelly = max(0.0, ev / b) if b > 0 else 0.0
    return {"ev": ev, "full_kelly_fraction": kelly}


def allocate_units(qualified: list[dict], budget_yen: int, unit_yen: int, target_deploy_yen: int,
                   weight_by_ticket: dict[str, float], per_ticket_cap_fraction: float,
                   per_bet_type_cap_fraction: float, correlation_group_cap_fraction: float,
                   desired_cap_by_ticket: dict[str, int] | None = None) -> dict[str, int]:
    alloc = {t["ticket_id"]: 0 for t in qualified}
    by_type = defaultdict(int)
    by_group = defaultdict(int)

    ticket_cap = floor_unit(budget_yen * per_ticket_cap_fraction, unit_yen)
    type_cap = floor_unit(budget_yen * per_bet_type_cap_fraction, unit_yen)
    group_cap = floor_unit(budget_yen * correlation_group_cap_fraction, unit_yen)

    spent = 0
    while spent + unit_yen <= target_deploy_yen:
        eligible = []
        for t in qualified:
            tid = t["ticket_id"]
            bt = t["bet_type"]
            grp = str(t.get("correlation_group") or tid)
            if alloc[tid] + unit_yen > ticket_cap:
                continue
            if by_type[bt] + unit_yen > type_cap:
                continue
            if by_group[grp] + unit_yen > group_cap:
                continue
            if desired_cap_by_ticket is not None and alloc[tid] + unit_yen > desired_cap_by_ticket.get(tid, 0):
                continue
            w = max(0.0, float(weight_by_ticket.get(tid, 0.0)))
            if w <= 0:
                continue
            # Deterministic proportional-fair score; ticket_id breaks ties.
            score = w / (alloc[tid] + unit_yen)
            eligible.append((score, tid, t))
        if not eligible:
            break
        eligible.sort(key=lambda x: (-x[0], x[1]))
        _, tid, t = eligible[0]
        bt = t["bet_type"]
        grp = str(t.get("correlation_group") or tid)
        alloc[tid] += unit_yen
        by_type[bt] += unit_yen
        by_group[grp] += unit_yen
        spent += unit_yen
    return alloc


def allocate(tickets: list[dict], budget_yen: int, method: str, *, unit_yen: int = 100,
             min_ev: float = 0.05, deploy_fraction: float = 1.0,
             per_ticket_cap_fraction: float = 0.35, per_bet_type_cap_fraction: float = 0.60,
             correlation_group_cap_fraction: float = 0.65, kelly_fraction: float = 0.25) -> dict:
    if method not in METHODS:
        raise ValueError(f"unknown method: {method}")
    if budget_yen < 0 or budget_yen % unit_yen != 0:
        raise ValueError("budget_yen must be nonnegative and an exact multiple of unit_yen")
    if unit_yen <= 0:
        raise ValueError("unit_yen must be positive")
    for name, x in {
        "deploy_fraction": deploy_fraction,
        "per_ticket_cap_fraction": per_ticket_cap_fraction,
        "per_bet_type_cap_fraction": per_bet_type_cap_fraction,
        "correlation_group_cap_fraction": correlation_group_cap_fraction,
        "kelly_fraction": kelly_fraction,
    }.items():
        if not (0.0 <= x <= 1.0):
            raise ValueError(f"{name} must be within [0,1]")

    enriched = []
    rejected = []
    for raw in tickets:
        t = dict(raw)
        tid = str(t.get("ticket_id") or "").strip()
        if not tid:
            raise ValueError("ticket_id is required")
        t["ticket_id"] = tid
        if t.get("bet_type") not in BET_TYPES:
            raise ValueError(f"unsupported bet_type for {tid}: {t.get('bet_type')}")
        m = ticket_metrics(t)
        t.update(m)
        reason = None
        if not bool(t.get("liquidity_ok", True)):
            reason = "LIQUIDITY_FAIL"
        elif m["ev"] < min_ev:
            reason = "EV_BELOW_GATE"
        if reason:
            rejected.append({"ticket_id": tid, "reason": reason, "ev": m["ev"]})
        else:
            enriched.append(t)

    if budget_yen == 0 or not enriched:
        alloc = {t["ticket_id"]: 0 for t in enriched}
        target = 0
    elif method == "equal_among_qualified_tickets":
        target = floor_unit(budget_yen * deploy_fraction, unit_yen)
        weights = {t["ticket_id"]: 1.0 for t in enriched}
        alloc = allocate_units(enriched, budget_yen, unit_yen, target, weights,
                               per_ticket_cap_fraction, per_bet_type_cap_fraction,
                               correlation_group_cap_fraction)
    elif method == "edge_proportional_with_caps":
        target = floor_unit(budget_yen * deploy_fraction, unit_yen)
        weights = {t["ticket_id"]: max(0.0, t["ev"]) for t in enriched}
        alloc = allocate_units(enriched, budget_yen, unit_yen, target, weights,
                               per_ticket_cap_fraction, per_bet_type_cap_fraction,
                               correlation_group_cap_fraction)
    else:
        # Fractional Kelly determines its own desired deployment; race/type/ticket/group caps remain binding.
        desired = {
            t["ticket_id"]: floor_unit(budget_yen * t["full_kelly_fraction"] * kelly_fraction, unit_yen)
            for t in enriched
        }
        target = min(budget_yen, sum(desired.values()))
        weights = {t["ticket_id"]: t["full_kelly_fraction"] for t in enriched}
        alloc = allocate_units(enriched, budget_yen, unit_yen, target, weights,
                               per_ticket_cap_fraction, per_bet_type_cap_fraction,
                               correlation_group_cap_fraction, desired_cap_by_ticket=desired)

    allocation_rows = []
    total = 0
    for t in sorted(enriched, key=lambda x: x["ticket_id"]):
        stake = int(alloc.get(t["ticket_id"], 0))
        total += stake
        allocation_rows.append({
            "ticket_id": t["ticket_id"],
            "bet_type": t["bet_type"],
            "model_probability": float(t["model_probability"]),
            "market_odds": float(t["market_odds"]),
            "ev": t["ev"],
            "full_kelly_fraction": t["full_kelly_fraction"],
            "correlation_group": str(t.get("correlation_group") or t["ticket_id"]),
            "stake_yen": stake,
        })

    return {
        "allocator_id": "KEIBA_RACE_BUDGET_ALLOCATOR_V1",
        "method": method,
        "budget_yen": budget_yen,
        "unit_yen": unit_yen,
        "min_ev": min_ev,
        "target_deploy_yen": target,
        "total_stake_yen": total,
        "unspent_yen": budget_yen - total,
        "budget_utilization": (total / budget_yen) if budget_yen else 0.0,
        "caps": {
            "per_ticket_cap_fraction": per_ticket_cap_fraction,
            "per_bet_type_cap_fraction": per_bet_type_cap_fraction,
            "correlation_group_cap_fraction": correlation_group_cap_fraction,
        },
        "deploy_fraction_for_equal_or_edge": deploy_fraction,
        "kelly_fraction": kelly_fraction,
        "allocation": allocation_rows,
        "rejected": rejected,
        "place_bets": False,
        "validation_oos_opened": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", required=True)
    ap.add_argument("--budget-yen", type=int, required=True)
    ap.add_argument("--method", choices=sorted(METHODS), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--unit-yen", type=int, default=100)
    ap.add_argument("--min-ev", type=float, default=0.05)
    ap.add_argument("--deploy-fraction", type=float, default=1.0)
    ap.add_argument("--per-ticket-cap-fraction", type=float, default=0.35)
    ap.add_argument("--per-bet-type-cap-fraction", type=float, default=0.60)
    ap.add_argument("--correlation-group-cap-fraction", type=float, default=0.65)
    ap.add_argument("--kelly-fraction", type=float, default=0.25)
    args = ap.parse_args()

    tickets = json.loads(Path(args.tickets).read_text(encoding="utf-8"))
    if not isinstance(tickets, list):
        raise ValueError("tickets JSON must be a list")
    result = allocate(
        tickets, args.budget_yen, args.method,
        unit_yen=args.unit_yen, min_ev=args.min_ev,
        deploy_fraction=args.deploy_fraction,
        per_ticket_cap_fraction=args.per_ticket_cap_fraction,
        per_bet_type_cap_fraction=args.per_bet_type_cap_fraction,
        correlation_group_cap_fraction=args.correlation_group_cap_fraction,
        kelly_fraction=args.kelly_fraction,
    )
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
