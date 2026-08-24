#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def to_i(v: str) -> int:
    v = (v or "").strip()
    return int(float(v)) if v else 0


def to_b(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger_csv")
    ap.add_argument("--week-id", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = []
    with Path(args.ledger_csv).open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("week_id") == args.week_id:
                rows.append(r)

    stake = sum(to_i(r.get("stake_yen")) for r in rows)
    pure_return = sum(to_i(r.get("magi_pure_return_yen")) for r in rows)
    official_return = sum(to_i(r.get("official_return_yen")) for r in rows)
    hit_tickets = sum(1 for r in rows if to_b(r.get("hit_flag")))
    races = sorted({r.get("race_id") for r in rows if r.get("race_id")})
    hit_races = sorted({r.get("race_id") for r in rows if r.get("race_id") and to_b(r.get("hit_flag"))})
    violations = sum(1 for r in rows if to_b(r.get("rule_violation_flag")))

    by_type = defaultdict(lambda: {"stake_yen": 0, "pure_return_yen": 0, "official_return_yen": 0, "tickets": 0, "hits": 0})
    for r in rows:
        bt = r.get("bet_type") or "UNKNOWN"
        d = by_type[bt]
        d["stake_yen"] += to_i(r.get("stake_yen"))
        d["pure_return_yen"] += to_i(r.get("magi_pure_return_yen"))
        d["official_return_yen"] += to_i(r.get("official_return_yen"))
        d["tickets"] += 1
        d["hits"] += int(to_b(r.get("hit_flag")))

    for d in by_type.values():
        d["magi_pure_return_rate"] = (d["pure_return_yen"] / d["stake_yen"]) if d["stake_yen"] else None
        d["orepro_official_return_rate"] = (d["official_return_yen"] / d["stake_yen"]) if d["stake_yen"] else None

    # Virtual drawdown on MAGI_PURE ticket-level ledger order.
    equity = 0
    peak = 0
    max_dd = 0
    for r in rows:
        equity += to_i(r.get("magi_pure_return_yen")) - to_i(r.get("stake_yen"))
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    out = {
        "report_id": "OREPRO-WEEKLY-DUAL-LEDGER-V1",
        "week_id": args.week_id,
        "row_count": len(rows),
        "race_count": len(races),
        "ticket_count": len(rows),
        "stake_yen": stake,
        "MAGI_PURE": {
            "return_yen": pure_return,
            "return_rate": (pure_return / stake) if stake else None,
            "net_yen": pure_return - stake,
            "max_drawdown_virtual_yen": max_dd,
        },
        "OREPRO_OFFICIAL": {
            "return_yen": official_return,
            "return_rate": (official_return / stake) if stake else None,
            "net_yen": official_return - stake,
        },
        "official_minus_pure_return_yen": official_return - pure_return,
        "ticket_hit_rate": (hit_tickets / len(rows)) if rows else None,
        "race_hit_rate": (len(hit_races) / len(races)) if races else None,
        "rule_violation_count": violations,
        "by_bet_type": dict(sorted(by_type.items())),
        "interpretation_guard": "OREPRO_OFFICIAL includes platform-specific effects when recorded; MAGI_PURE excludes such bonuses and is the research score. Neither score proves profitability from one week.",
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
