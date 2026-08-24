#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path


def lint(policy: dict, features: list[str]) -> list[str]:
    errs = []
    wl = list(policy["residual_feature_whitelist"])
    base = set(policy["baseline_market_fields"])
    held = set(policy["explicitly_held_out"])
    if not features:
        errs.append("EMPTY_RESIDUAL_FEATURE_SET")
    if len(features) != len(set(features)):
        errs.append("DUPLICATE_RESIDUAL_FEATURE")
    for f in features:
        if f in base:
            errs.append(f"CURRENT_MARKET_BASELINE_LEAK:{f}")
        if f in held:
            errs.append(f"HELD_OUT_FEATURE_USED:{f}")
        if f not in wl:
            errs.append(f"UNREGISTERED_RESIDUAL_FEATURE:{f}")
    if policy["rules"].get("feature_order_must_match_whitelist") and features != wl:
        errs.append("FEATURE_ORDER_OR_SET_MISMATCH")
    return sorted(set(errs))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("policy_json")
    ap.add_argument("features_json")
    args = ap.parse_args()
    policy = json.loads(Path(args.policy_json).read_text(encoding="utf-8"))
    obj = json.loads(Path(args.features_json).read_text(encoding="utf-8"))
    features = obj["residual_features"]
    errs = lint(policy, features)
    out = {"status": "PASS" if not errs else "FAIL", "violations": errs, "residual_features": features}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not errs else 2


if __name__ == "__main__":
    raise SystemExit(main())
