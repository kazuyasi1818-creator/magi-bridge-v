#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import traceback
from typing import Any

VALIDATOR_ID = "T009R_EXPECTED_MANIFEST_SELFCHECK_V1_1"
EXIT_PASS = 0
EXIT_PROTOCOL_INVALID = 2
EXIT_INTERNAL_EXCEPTION = 3
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PARTITIONS = ("FULL", "A", "B")
TOP = {"prereg_id", "input_sha256", "race_manifest_sha256", "split_manifest_sha256", "partitions", "feasibility"}
PART = {"row_identity_sha256", "race_set_sha256", "subgroup_membership_sha256"}
FEAS = {"distinct_race_dates_total", "partitions"}
FEAS_PART = {"distinct_race_dates", "race_count", "primary_subgroup_rows"}
NOTE = (
    "This validates manifest structure and arithmetic only; it does not prove race-set virginity, "
    "semantic correctness of hashes, or outcome non-exposure."
)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def nni(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def exact_keys(x: Any, expected: set[str], scope: str, errs: list[dict]) -> bool:
    if not isinstance(x, dict):
        errs.append({"scope": scope, "error": "not_object", "actual_type": type(x).__name__})
        return False
    actual = set(x)
    if actual != expected:
        errs.append({
            "scope": scope,
            "error": "key_set_mismatch",
            "missing": sorted(expected - actual),
            "unexpected": sorted(actual - expected),
        })
        return False
    return True


def write_result(path: Path, result: dict) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    print(text)


def protocol_invalid(manifest_sha256: str | None, errors: list[dict], *, stopped_early: bool = False) -> dict:
    return {
        "validator_id": VALIDATOR_ID,
        "manifest_sha256": manifest_sha256,
        "status": "PROTOCOL_INVALID",
        "protocol_effect": "PROTOCOL_INVALID",
        "self_consistency_pass": False,
        "errors": errors,
        "lock_eligibility": "PROHIBITED",
        "stopped_early": stopped_early,
        "exit_code": EXIT_PROTOCOL_INVALID,
        "note": NOTE,
    }


def validate_manifest(obj: Any, manifest_sha256: str) -> tuple[dict, int]:
    errs: list[dict] = []

    # Fail closed immediately at the top-level type/key boundary. Do not call .get()
    # on a malformed top-level JSON value.
    if not exact_keys(obj, TOP, "manifest", errs):
        return protocol_invalid(manifest_sha256, errs, stopped_early=True), EXIT_PROTOCOL_INVALID

    if not isinstance(obj.get("prereg_id"), str) or not obj.get("prereg_id"):
        errs.append({"scope": "manifest", "error": "invalid_prereg_id"})
    for k in ("input_sha256", "race_manifest_sha256", "split_manifest_sha256"):
        v = obj.get(k)
        if not isinstance(v, str) or not SHA_RE.fullmatch(v):
            errs.append({"scope": "manifest", "error": "invalid_sha256", "field": k})

    parts = obj.get("partitions")
    if not isinstance(parts, dict) or set(parts) != set(PARTITIONS):
        errs.append({"scope": "manifest.partitions", "error": "invalid_partitions", "actual_type": type(parts).__name__})
    else:
        for p in PARTITIONS:
            q = parts[p]
            if exact_keys(q, PART, f"manifest.partitions.{p}", errs):
                for k in PART:
                    v = q.get(k)
                    if not isinstance(v, str) or not SHA_RE.fullmatch(v):
                        errs.append({"scope": f"manifest.partitions.{p}", "error": "invalid_sha256", "field": k})

    f = obj.get("feasibility")
    if exact_keys(f, FEAS, "manifest.feasibility", errs):
        if not nni(f.get("distinct_race_dates_total")):
            errs.append({"scope": "manifest.feasibility", "error": "invalid_nonnegative_integer", "field": "distinct_race_dates_total"})
        fp = f.get("partitions")
        if not isinstance(fp, dict) or set(fp) != set(PARTITIONS):
            errs.append({"scope": "manifest.feasibility.partitions", "error": "invalid_partitions", "actual_type": type(fp).__name__})
        else:
            structural_ok = True
            for p in PARTITIONS:
                q = fp[p]
                if not exact_keys(q, FEAS_PART, f"manifest.feasibility.partitions.{p}", errs):
                    structural_ok = False
                    continue
                for k in FEAS_PART:
                    if not nni(q.get(k)):
                        errs.append({"scope": f"manifest.feasibility.partitions.{p}", "error": "invalid_nonnegative_integer", "field": k})
                        structural_ok = False
            if structural_ok:
                F, A, B = fp["FULL"], fp["A"], fp["B"]
                for k in ("race_count", "primary_subgroup_rows", "distinct_race_dates"):
                    ab = A[k] + B[k]
                    if F[k] != ab:
                        errs.append({"scope": "manifest.feasibility", "error": "FULL_NOT_A_PLUS_B", "field": k, "FULL": F[k], "A_plus_B": ab})
                ab_dates = A["distinct_race_dates"] + B["distinct_race_dates"]
                if f["distinct_race_dates_total"] != ab_dates:
                    errs.append({
                        "scope": "manifest.feasibility",
                        "error": "TOTAL_DATES_NOT_A_PLUS_B",
                        "distinct_race_dates_total": f["distinct_race_dates_total"],
                        "A_plus_B": ab_dates,
                    })
                if F["distinct_race_dates"] != f["distinct_race_dates_total"]:
                    errs.append({
                        "scope": "manifest.feasibility",
                        "error": "FULL_DATES_NOT_TOTAL",
                        "FULL": F["distinct_race_dates"],
                        "distinct_race_dates_total": f["distinct_race_dates_total"],
                    })

    result = {
        "validator_id": VALIDATOR_ID,
        "manifest_sha256": manifest_sha256,
        "status": "PASS" if not errs else "PROTOCOL_INVALID",
        "protocol_effect": None if not errs else "PROTOCOL_INVALID",
        "self_consistency_pass": not errs,
        "errors": errs,
        "lock_eligibility": "ELIGIBLE_FOR_HASH_ANCHOR" if not errs else "PROHIBITED",
        "stopped_early": False,
        "exit_code": EXIT_PASS if not errs else EXIT_PROTOCOL_INVALID,
        "note": NOTE,
    }
    return result, result["exit_code"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    manifest_sha256: str | None = None
    try:
        # Hash the exact bytes before parsing so even malformed/non-object JSON gets an evidence anchor.
        manifest_sha256 = sha256_file(args.manifest)
        try:
            obj = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception as e:
            result = protocol_invalid(
                manifest_sha256,
                [{"scope": "manifest", "error": "invalid_json", "detail": repr(e)}],
                stopped_early=True,
            )
            write_result(args.out, result)
            raise SystemExit(EXIT_PROTOCOL_INVALID)

        result, exit_code = validate_manifest(obj, manifest_sha256)
        write_result(args.out, result)
        raise SystemExit(exit_code)

    except SystemExit:
        raise
    except Exception as e:
        # Unexpected validator failures are distinct from invalid input, but still fail closed
        # and preserve machine-readable evidence whenever --out is writable.
        result = {
            "validator_id": VALIDATOR_ID,
            "manifest_sha256": manifest_sha256,
            "status": "PROTOCOL_INVALID",
            "protocol_effect": "PROTOCOL_INVALID",
            "self_consistency_pass": False,
            "errors": [{
                "scope": "validator",
                "error": "internal_exception",
                "exception_type": type(e).__name__,
                "detail": repr(e),
                "traceback": traceback.format_exc(),
            }],
            "lock_eligibility": "PROHIBITED",
            "stopped_early": True,
            "exit_code": EXIT_INTERNAL_EXCEPTION,
            "note": NOTE,
        }
        try:
            write_result(args.out, result)
        except Exception as write_error:
            # If the evidence destination itself is unwritable, JSON cannot be guaranteed on disk;
            # still emit a machine-readable object to stdout/stderr and exit 3.
            result["evidence_write_failure"] = {
                "exception_type": type(write_error).__name__,
                "detail": repr(write_error),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(EXIT_INTERNAL_EXCEPTION)


if __name__ == "__main__":
    main()
