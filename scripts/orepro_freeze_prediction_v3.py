#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from copy import deepcopy
from pathlib import Path
import orepro_freeze_prediction_v2 as v2

EXPECTED_GATE = "KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def validate(card: dict) -> list[str]:
    errs = set(v2.validate(card))
    if card.get("feature_gate_version") != EXPECTED_GATE:
        errs.add("FEATURE_GATE_VERSION_NOT_V5")

    snap = card.get("data_snapshot") or {}
    source_hashes = snap.get("source_hashes")
    if not isinstance(source_hashes, list) or not source_hashes:
        errs.add("SOURCE_HASHES_REQUIRED")
    else:
        for i, h in enumerate(source_hashes):
            if not isinstance(h, str) or not HEX64.fullmatch(h):
                errs.add(f"INVALID_SOURCE_HASH:{i}")

    gate_pass = snap.get("current_feature_gate_pass") is True
    handoff_sha = str(snap.get("gate_v5_handoff_sha256") or "")
    if gate_pass:
        # v2 intentionally fails any current-feature gate claim. v3 permits it
        # only when the card explicitly names Gate v5 and carries a frozen
        # reviewed handoff hash. The actual handoff review remains external.
        errs.discard("CURRENT_FEATURE_GATE_UNPROVEN")
        if not HEX64.fullmatch(handoff_sha):
            errs.add("GATE_V5_HANDOFF_SHA_REQUIRED")
    elif handoff_sha:
        errs.add("GATE_V5_HANDOFF_SHA_WITHOUT_PASS")

    if card.get("submitted_to_orepro") is not False:
        errs.add("CARD_ALREADY_MARKED_SUBMITTED")
    return sorted(errs)


def canonical_payload(card: dict) -> bytes:
    return v2.canonical_payload(card)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("card_json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    card = json.loads(Path(args.card_json).read_text(encoding="utf-8"))
    errs = validate(card)
    if errs:
        print(json.dumps({"status":"FAIL","validator":"OREPRO_FREEZE_V3_GATE_V5","violations":errs}, ensure_ascii=False, indent=2))
        return 2
    digest = hashlib.sha256(canonical_payload(card)).hexdigest()
    frozen = deepcopy(card)
    frozen["freeze_hash_sha256"] = digest
    Path(args.out).write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"PASS","validator":"OREPRO_FREEZE_V3_GATE_V5","freeze_hash_sha256":digest,"out":args.out}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
