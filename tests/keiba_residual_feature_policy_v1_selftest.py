#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from keiba_residual_feature_policy_check_v1 import lint

policy = json.loads((ROOT / ".magi/keiba_residual_feature_policy_v1.json").read_text(encoding="utf-8"))
wl = policy["residual_feature_whitelist"]

cases = {
    "good": lint(policy, wl) == [],
    "market_leak": bool(lint(policy, ["log_market_p"] + wl[1:])),
    "held_out": bool(lint(policy, ["last_final_odds"] + wl[1:])),
    "unknown": bool(lint(policy, ["mystery_feature"] + wl[1:])),
    "duplicate": bool(lint(policy, wl[:-1] + [wl[-2]])),
    "reordered": bool(lint(policy, list(reversed(wl)))),
    "empty": bool(lint(policy, [])),
}
out = {
    "status": "PASS" if all(cases.values()) else "FAIL",
    "checks": cases,
    "validation_opened": False,
    "oos_opened": False,
    "real_money_bet": False
}
print(json.dumps(out, ensure_ascii=False, indent=2))
raise SystemExit(0 if out["status"] == "PASS" else 1)
