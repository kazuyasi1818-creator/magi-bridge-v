#!/usr/bin/env python3
"""
KEIBA MAGI exotic-ticket budget allocator v1.

Infrastructure / DEV plumbing only.
- Accepts a user-selected race budget B (e.g. 1,000 or 10,000 JPY).
- Allocates only to tickets that pass a fixed EV gate.
- Uses 100-JPY units by default.
- Never exceeds race, ticket, bet-type, or correlation-group caps.
- Does not force full-budget spend.
- Supports deterministic allocation-score methods for later preregistered comparison.

This module does NOT place bets, open VALIDATION/OOS, or claim profitability.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

ALLOWED_BET_TYPES = {
    "TRIFECTA_3REN_TAN",
    "TRIO_3REN_PUKU",
    "EXACTA_UMA_TAN",
    "QUINELLA_UMA_REN",
}


def full_kelly_fraction(probability: float, decimal_odds: float) -> float:
    """Single-ticket Kelly fraction. Portfolio optimality is NOT implied."""
    b = decimal_odds - 1.0
    if b <= 0.0:
        return 0.0
    q = 1.0 - probability
    return max(0.0, (b * probability - q) / b)


def score_ticket(ticket: dict, method: str, kelly_fraction_multiplier: float) -> float:
    edge = float(ticket["expected_value"])
    if method == "equal_among_qualified_tickets":
        return 1.0
    if method == "edge_proportional_with_caps":
        return max(0.0, edge)
    if method == "fractional_kelly_with_race_cap":
        # Score only. Correlated exotic tickets are not independent, so this is
        # explicitly NOT a claim of portfolio-Kelly optimality.
        k = full_kelly_fraction(float(ticket["model_probability"]), float(ticket["decimal_odds"]))
        return max(0.0, k * kelly_fraction_multiplier)
    raise ValueError(f"unsupported allocation method: {method}")


def round_down_to_unit(value: float, unit: int) -> int:
    return int(math.floor(max(0.0, value) / unit) * unit)


def load_tickets(path: Path, min_ev: float) -> List[dict]:
    out: List[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row_no, row in enumerate(csv.DictReader(f), start=2):
            ticket_id = str(row.get("ticket_id") or "").strip()
            bet_type = str(row.get("bet_type") or "").strip()
            corr = str(row.get("correlation_group") or ticket_id).strip()
            if not ticket_id:
                raise ValueError(f"row {row_no}: missing ticket_id")
            if bet_type not in ALLOWED_BET_TYPES:
                raise ValueError(f"row {row_no}: unsupported bet_type={bet_type}")
            try:
                p = float(row.get("model_probability"))
                odds = float(row.get("decimal_odds"))
            except Exception as e:
                raise ValueError(f"row {row_no}: invalid probability/odds") from e
            if not (0.0 < p < 1.0):
                raise ValueError(f"row {row_no}: model_probability must be in (0,1)")
            if not (odds > 1.0 and math.isfinite(odds)):
                raise ValueError(f"row {row_no}: decimal_odds must be >1")
            ev = p * odds - 1.0
            out.append({
                "ticket_id": ticket_id,
                "bet_type": bet_type,
                "correlation_group": corr,
                "model_probability": p,
                "decimal_odds": odds,
                "expected_value": ev,
                "qualified": ev >= min_ev,
            })
    ids = [x["ticket_id"] for x in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ticket_id")
    return out


def allocate(
    tickets: List[dict],
    race_budget_yen: int,
    method: str,
    unit_yen: int = 100,
    min_ev: float = 0.05,
    deploy_fraction: float = 1.0,
    max_ticket_share: float = 0.35,
    max_bet_type_share: float = 0.60,
    max_correlation_group_share: float = 0.65,
    kelly_fraction_multiplier: float = 0.25,
) -> dict:
    if race_budget_yen < 0:
        raise ValueError("race_budget_yen must be >= 0")
    if unit_yen <= 0:
        raise ValueError("unit_yen must be > 0")
    if race_budget_yen % unit_yen != 0:
        raise ValueError("race_budget_yen must be divisible by unit_yen")
    for name, x in {
        "deploy_fraction": deploy_fraction,
        "max_ticket_share": max_ticket_share,
        "max_bet_type_share": max_bet_type_share,
        "max_correlation_group_share": max_correlation_group_share,
    }.items():
        if not (0.0 <= x <= 1.0):
            raise ValueError(f"{name} must be in [0,1]")

    qualified = [dict(t) for t in tickets if bool(t.get("qualified")) and float(t["expected_value"]) >= min_ev]
    for t in qualified:
        t["allocation_score"] = score_ticket(t, method, kelly_fraction_multiplier)
    qualified = [t for t in qualified if t["allocation_score"] > 0.0]

    target_spend = round_down_to_unit(race_budget_yen * deploy_fraction, unit_yen)
    ticket_cap = round_down_to_unit(race_budget_yen * max_ticket_share, unit_yen)
    type_cap = round_down_to_unit(race_budget_yen * max_bet_type_share, unit_yen)
    corr_cap = round_down_to_unit(race_budget_yen * max_correlation_group_share, unit_yen)

    allocations: Dict[str, int] = defaultdict(int)
    type_alloc: Dict[str, int] = defaultdict(int)
    corr_alloc: Dict[str, int] = defaultdict(int)
    spent = 0

    # Deterministic unit-by-unit weighted balancing. The score/(1+n) rule gives
    # higher-edge tickets more units while preventing a single ticket from
    # absorbing the full race budget before caps are considered.
    while spent + unit_yen <= target_spend:
        eligible = []
        for t in qualified:
            tid = t["ticket_id"]
            bt = t["bet_type"]
            cg = t["correlation_group"]
            if allocations[tid] + unit_yen > ticket_cap:
                continue
            if type_alloc[bt] + unit_yen > type_cap:
                continue
            if corr_alloc[cg] + unit_yen > corr_cap:
                continue
            units_already = allocations[tid] // unit_yen
            priority = t["allocation_score"] / (1.0 + units_already)
            eligible.append((priority, t["allocation_score"], tid, t))
        if not eligible:
            break
        # Stable deterministic tie-break by ticket_id ascending.
        eligible.sort(key=lambda x: (-x[0], -x[1], x[2]))
        t = eligible[0][3]
        allocations[t["ticket_id"]] += unit_yen
        type_alloc[t["bet_type"]] += unit_yen
        corr_alloc[t["correlation_group"]] += unit_yen
        spent += unit_yen

    rows = []
    q_by_id = {t["ticket_id"]: t for t in qualified}
    for tid in sorted(allocations):
        amount = allocations[tid]
        if amount <= 0:
            continue
        t = q_by_id[tid]
        rows.append({
            "ticket_id": tid,
            "bet_type": t["bet_type"],
            "correlation_group": t["correlation_group"],
            "model_probability": t["model_probability"],
            "decimal_odds": t["decimal_odds"],
            "expected_value": t["expected_value"],
            "allocation_score": t["allocation_score"],
            "stake_yen": amount,
            "stake_share_of_budget": (amount / race_budget_yen) if race_budget_yen else 0.0,
        })

    return {
        "allocator_id": "KEIBA_EXOTICS_BUDGET_ALLOCATOR_V1",
        "status": "NO_BET" if spent == 0 else "ALLOCATED",
        "method": method,
        "race_budget_yen": race_budget_yen,
        "unit_yen": unit_yen,
        "min_ev": min_ev,
        "deploy_fraction": deploy_fraction,
        "caps": {
            "max_ticket_share": max_ticket_share,
            "max_bet_type_share": max_bet_type_share,
            "max_correlation_group_share": max_correlation_group_share,
            "ticket_cap_yen": ticket_cap,
            "bet_type_cap_yen": type_cap,
            "correlation_group_cap_yen": corr_cap,
        },
        "qualified_ticket_count": len(qualified),
        "spent_yen": spent,
        "unspent_yen": race_budget_yen - spent,
        "allocations": rows,
        "bet_type_totals_yen": dict(sorted(type_alloc.items())),
        "correlation_group_totals_yen": dict(sorted(corr_alloc.items())),
        "safety": {
            "budget_not_exceeded": spent <= race_budget_yen,
            "all_stakes_unit_aligned": all(r["stake_yen"] % unit_yen == 0 for r in rows),
            "full_budget_spend_not_forced": True,
            "real_bet_placement": False,
            "validation_oos_opened": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tickets_csv")
    ap.add_argument("--budget", type=int, required=True)
    ap.add_argument("--method", choices=[
        "equal_among_qualified_tickets",
        "edge_proportional_with_caps",
        "fractional_kelly_with_race_cap",
    ], default="edge_proportional_with_caps")
    ap.add_argument("--unit", type=int, default=100)
    ap.add_argument("--min-ev", type=float, default=0.05)
    ap.add_argument("--deploy-fraction", type=float, default=1.0)
    ap.add_argument("--max-ticket-share", type=float, default=0.35)
    ap.add_argument("--max-bet-type-share", type=float, default=0.60)
    ap.add_argument("--max-correlation-group-share", type=float, default=0.65)
    ap.add_argument("--kelly-fraction-multiplier", type=float, default=0.25)
    ap.add_argument("--out")
    args = ap.parse_args()

    tickets = load_tickets(Path(args.tickets_csv), args.min_ev)
    result = allocate(
        tickets,
        race_budget_yen=args.budget,
        method=args.method,
        unit_yen=args.unit,
        min_ev=args.min_ev,
        deploy_fraction=args.deploy_fraction,
        max_ticket_share=args.max_ticket_share,
        max_bet_type_share=args.max_bet_type_share,
        max_correlation_group_share=args.max_correlation_group_share,
        kelly_fraction_multiplier=args.kelly_fraction_multiplier,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
