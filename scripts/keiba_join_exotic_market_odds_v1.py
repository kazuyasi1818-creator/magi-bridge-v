#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

SUPPORTED = {"EXACTA_UMA_TAN", "QUINELLA_UMA_REN", "TRIFECTA_3REN_TAN", "TRIO_3REN_PUKU"}


def parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(str(s))
    if dt.tzinfo is None:
        raise ValueError(f"timezone-aware timestamp required: {s}")
    return dt


def join(probability_rows: list[dict], odds_rows: list[dict], snapshot_time_jst: str, max_age_seconds: int) -> dict:
    snap = parse_dt(snapshot_time_jst)
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be >=0")

    obs = {}
    for row in odds_rows:
        bt = row.get("bet_type")
        if bt not in SUPPORTED:
            continue
        key = (str(row.get("race_id")), bt, str(row.get("ticket_key")))
        t = parse_dt(row["odds_source_time_jst"])
        market_odds = float(row["market_odds"])
        if market_odds <= 1.0:
            continue
        item = dict(row)
        item["_time"] = t
        obs.setdefault(key, []).append(item)

    joined = []
    skipped = []
    for p in probability_rows:
        bt = p.get("bet_type")
        if bt not in SUPPORTED:
            skipped.append({"ticket_key": p.get("ticket_key"), "bet_type": bt, "reason": "UNSUPPORTED_BET_TYPE"})
            continue
        race_id = str(p.get("race_id"))
        ticket_key = str(p.get("ticket_key"))
        prob = float(p["model_probability"])
        if not (0.0 < prob < 1.0):
            skipped.append({"ticket_key": ticket_key, "bet_type": bt, "reason": "INVALID_MODEL_PROBABILITY"})
            continue
        candidates = [x for x in obs.get((race_id, bt, ticket_key), []) if x["_time"] <= snap]
        if not candidates:
            skipped.append({"ticket_key": ticket_key, "bet_type": bt, "reason": "NO_PRE_SNAPSHOT_ODDS"})
            continue
        chosen = max(candidates, key=lambda x: x["_time"])
        age = (snap - chosen["_time"]).total_seconds()
        if age > max_age_seconds:
            skipped.append({"ticket_key": ticket_key, "bet_type": bt, "reason": "STALE_PRE_SNAPSHOT_ODDS", "odds_age_seconds": age})
            continue
        source_sha = str(chosen.get("source_file_sha256") or "").strip()
        if len(source_sha) != 64:
            skipped.append({"ticket_key": ticket_key, "bet_type": bt, "reason": "MISSING_OR_INVALID_SOURCE_SHA256"})
            continue
        odds = float(chosen["market_odds"])
        joined.append({
            "race_id": race_id,
            "bet_type": bt,
            "ticket_key": ticket_key,
            "model_probability": prob,
            "market_odds": odds,
            "ev": prob * odds - 1.0,
            "prediction_snapshot_time_jst": snap.isoformat(),
            "odds_source_time_jst": chosen["_time"].isoformat(),
            "odds_age_seconds": age,
            "source_file_sha256": source_sha,
            "odds_source_id": chosen.get("odds_source_id"),
        })

    return {
        "joiner_id": "KEIBA_EXOTIC_MARKET_ODDS_JOINER_V1",
        "prediction_snapshot_time_jst": snap.isoformat(),
        "max_age_seconds": max_age_seconds,
        "joined": joined,
        "skipped": skipped,
        "future_odds_backfill_allowed": False,
        "post_race_final_odds_as_purchase_price": False,
        "validation_oos_opened": False,
        "place_bets": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probabilities", required=True)
    ap.add_argument("--odds", required=True)
    ap.add_argument("--snapshot-time-jst", required=True)
    ap.add_argument("--max-age-seconds", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    probs = json.loads(Path(args.probabilities).read_text(encoding="utf-8"))
    odds = json.loads(Path(args.odds).read_text(encoding="utf-8"))
    if not isinstance(probs, list) or not isinstance(odds, list):
        raise ValueError("probabilities and odds must each be JSON lists")
    out = join(probs, odds, args.snapshot_time_jst, args.max_age_seconds)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
