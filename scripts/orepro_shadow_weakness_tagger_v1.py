#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REQUIRED = {
    "race_id",
    "is_newcomer_race",
    "field_size",
    "distance",
    "history_coverage",
    "market_top1_p",
    "market_gap",
    "market_norm_entropy",
}


def b(v: str) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y"}


def tags_for(row: dict) -> list[str]:
    if b(row["is_newcomer_race"]):
        return ["NEWCOMER_RACE_EXCLUDED"]

    field_size = int(row["field_size"])
    distance = int(float(row["distance"]))
    history_coverage = float(row["history_coverage"])
    top1 = float(row["market_top1_p"])
    gap = float(row["market_gap"])
    entropy = float(row["market_norm_entropy"])

    tags: list[str] = []
    if field_size <= 10:
        tags.append("SMALL_FIELD_LE_10")
    if 1800 <= distance <= 2199:
        tags.append("DIST_1800_2199")
    if top1 < 0.20:
        tags.append("MARKET_TOP1_P_LT_0_20")
    if 0.80 <= entropy < 0.85:
        tags.append("MARKET_NORM_ENTROPY_0_80_0_85")
    if 0.05 <= gap < 0.10:
        tags.append("MARKET_GAP_0_05_0_10")
    if 0.80 <= history_coverage < 0.95:
        tags.append("HISTORY_COV_0_80_0_949")
    return tags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("race_csv")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with Path(args.race_csv).open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        names = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - names)
        if missing:
            print(json.dumps({"status":"FAIL","violations":[f"MISSING_REQUIRED_COLUMN:{x}" for x in missing]}, ensure_ascii=False, indent=2))
            return 2
        rows = list(reader)

    tagged = []
    for r in rows:
        ts = tags_for(r)
        tagged.append({
            "race_id": r["race_id"],
            "shadow_tags": ts,
            "newcomer_excluded": "NEWCOMER_RACE_EXCLUDED" in ts,
            "selection_effect": "NONE",
            "prediction_effect": "NONE",
            "ticket_effect": "NONE",
            "stake_effect": "NONE",
        })

    out = {
        "tagger_id": "OREPRO-SHADOW-WEAKNESS-TAGGER-V1",
        "status": "PASS",
        "rows": tagged,
        "guard": "Tags are diagnostic-only. They must not alter race selection, prediction, ticket choice, or stake. Newcomer exclusion is a separate preregistered scope rule.",
        "validation_opened": False,
        "oos_opened": False,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
