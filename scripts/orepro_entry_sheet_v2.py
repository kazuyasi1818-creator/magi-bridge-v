#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

LABELS = {
    "EXACTA_UMA_TAN": "馬単",
    "QUINELLA_UMA_REN": "馬連",
    "TRIFECTA_3REN_TAN": "3連単",
    "TRIO_3REN_PUKU": "3連複",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frozen_card_json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    c = json.loads(Path(args.frozen_card_json).read_text(encoding="utf-8"))
    h = str(c.get("freeze_hash_sha256") or "")
    if len(h) != 64:
        raise SystemExit("frozen card SHA is missing")

    pure_total = sum(int(t.get("magi_pure_stake_yen",0)) for t in c.get("tickets",[]))
    reg_total = sum(int(t.get("orepro_registered_stake_yen",0)) for t in c.get("tickets",[]))
    forced = reg_total - pure_total
    lines = [
        f"【俺プロ登録票 v2】 {c['venue']} {c['race_no']}R",
        f"race_id: {c['race_id']}",
        f"発走: {c['post_time_jst']}",
        f"MAGI凍結: {c['prediction_frozen_at_jst']}",
        f"主モデル: {c['model_version']}",
        f"勝負レース: {'YES' if c.get('battle_race_flag') else 'NO'}",
        f"freeze SHA256: {h}",
        "",
        "買い目（MAGI推奨 → 俺プロ登録）:",
    ]
    for t in c.get("tickets", []):
        reg = int(t.get("orepro_registered_stake_yen",0))
        pure = int(t.get("magi_pure_stake_yen",0))
        if reg <= 0 and pure <= 0:
            continue
        label = LABELS.get(t.get("bet_type"), t.get("bet_type"))
        odds = t.get("purchase_available_decimal_odds")
        ev = t.get("expected_value")
        extra=[]
        if odds is not None:
            extra.append(f"odds {float(odds):.1f}")
        if ev is not None:
            extra.append(f"EV {float(ev):+.3f}")
        suffix=(" / "+" / ".join(extra)) if extra else ""
        lines.append(f"- {label} {t['combination']}  MAGI {pure:,}円 → 俺プロ {reg:,}円 (+{reg-pure:,}円){suffix}")
    lines += [
        "",
        f"MAGI_PURE合計: {pure_total:,}円",
        f"俺プロ登録合計: {reg_total:,}円",
        f"ランキング用増額: {forced:,}円",
        "※俺プロ公式成績・通常化成績・MAGI_PURE成績は別集計",
    ]
    Path(args.out).write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
