#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path


def validate_horses(horses: list[dict]) -> list[dict]:
    if len(horses) < 3:
        raise ValueError("at least 3 horses are required")
    seen = set()
    out = []
    for h in horses:
        no = str(h.get("horse_no") or "").zfill(2)
        if not no.strip("0"):
            raise ValueError("horse_no is required")
        if no in seen:
            raise ValueError(f"duplicate horse_no: {no}")
        seen.add(no)
        score = float(h["score"])
        if not math.isfinite(score) or score <= 0:
            raise ValueError(f"score must be finite and >0 for horse {no}")
        out.append({"horse_no": no, "score": score})
    return sorted(out, key=lambda x: x["horse_no"])


def ordered_top2_probability(scores: dict[str, float], first: str, second: str) -> float:
    if first == second:
        return 0.0
    total = sum(scores.values())
    p1 = scores[first] / total
    rem = total - scores[first]
    return p1 * (scores[second] / rem)


def ordered_top3_probability(scores: dict[str, float], first: str, second: str, third: str) -> float:
    if len({first, second, third}) != 3:
        return 0.0
    total = sum(scores.values())
    p1 = scores[first] / total
    rem1 = total - scores[first]
    p2 = scores[second] / rem1
    rem2 = rem1 - scores[second]
    p3 = scores[third] / rem2
    return p1 * p2 * p3


def generate(horses: list[dict]) -> dict:
    hs = validate_horses(horses)
    scores = {h["horse_no"]: h["score"] for h in hs}
    nos = list(scores)

    exacta = []
    for a, b in itertools.permutations(nos, 2):
        exacta.append({"ticket": f"{a}>{b}", "horses": [a, b], "probability": ordered_top2_probability(scores, a, b)})

    quinella = []
    exacta_map = {tuple(x["horses"]): x["probability"] for x in exacta}
    for a, b in itertools.combinations(nos, 2):
        p = exacta_map[(a, b)] + exacta_map[(b, a)]
        quinella.append({"ticket": f"{a}-{b}", "horses": [a, b], "probability": p})

    trifecta = []
    for a, b, c in itertools.permutations(nos, 3):
        trifecta.append({"ticket": f"{a}>{b}>{c}", "horses": [a, b, c], "probability": ordered_top3_probability(scores, a, b, c)})

    trifecta_map = {tuple(x["horses"]): x["probability"] for x in trifecta}
    trio = []
    for combo in itertools.combinations(nos, 3):
        p = sum(trifecta_map[perm] for perm in itertools.permutations(combo, 3))
        trio.append({"ticket": "-".join(combo), "horses": list(combo), "probability": p})

    win = [{"horse_no": h, "probability": scores[h] / sum(scores.values())} for h in nos]
    return {
        "engine_id": "KEIBA_EXOTIC_PROBABILITY_ENGINE_V1",
        "model_family": "SEQUENTIAL_PLACKETT_LUCE",
        "horse_count": len(nos),
        "win": win,
        "EXACTA_UMA_TAN": exacta,
        "QUINELLA_UMA_REN": quinella,
        "TRIFECTA_3REN_TAN": trifecta,
        "TRIO_3REN_PUKU": trio,
        "probability_sums": {
            "win": sum(x["probability"] for x in win),
            "exacta": sum(x["probability"] for x in exacta),
            "quinella": sum(x["probability"] for x in quinella),
            "trifecta": sum(x["probability"] for x in trifecta),
            "trio": sum(x["probability"] for x in trio),
        },
        "place_bets": False,
        "validation_oos_opened": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horses", required=True, help="JSON list with horse_no and positive score")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    horses = json.loads(Path(args.horses).read_text(encoding="utf-8"))
    if not isinstance(horses, list):
        raise ValueError("horses JSON must be a list")
    out = generate(horses)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
