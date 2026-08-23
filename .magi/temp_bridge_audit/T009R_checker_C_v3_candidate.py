#!/usr/bin/env python3
"""
T009R deterministic reconciliation checker C v3 CANDIDATE.

Purpose:
- Strictly validate two independently-produced implementation bundles.
- Verify deterministic A/B equality where equality is required.
- Verify each bundle's internal arithmetic from primitive aggregates.
- Verify pre-outcome identity/subgroup hashes against a separately locked expected manifest.
- Independently recompute each implementation's statistical verdict from preregistered rules.

This checker never reads holdout row-level data or outcome rows.
It is a candidate for Claude audit and MUST NOT be treated as locked until reviewed.
"""
from pathlib import Path
import argparse, hashlib, json, math, re, sys

TOL = 1e-10
PARTITIONS = ("FULL", "A", "B")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_IMPL_IDS = {"A", "B"}
BOOTSTRAP_REPS = 20000
MIN_VALID_REPS = 19980
MIN_VALID_FRAC = 0.999
EXPECTED_RNG = "numpy.random.Generator(PCG64)"
EXPECTED_QUANTILE = "linear"

TOP_REQUIRED = {
    "implementation_id", "prereg_id", "input_sha256", "race_manifest_sha256",
    "split_manifest_sha256", "partitions", "inference", "confirmatory_verdict"
}
PART_REQUIRED = {
    "row_count", "race_count", "subgroup_membership_count", "observed_wins",
    "row_identity_sha256", "race_set_sha256", "subgroup_membership_sha256",
    "sum_predicted_probability_control", "sum_predicted_probability_ablation",
    "observed_win_rate", "mean_predicted_probability_control",
    "mean_predicted_probability_ablation", "Rc", "Ra", "D"
}
INFERENCE_REQUIRED = {
    "bootstrap_seed", "bootstrap_replications", "bootstrap_valid_replicates",
    "bootstrap_invalid_replicates", "bootstrap_valid_fraction",
    "full_D_ci_lower", "full_D_ci_upper", "rng", "quantile_method"
}
EXPECTED_MANIFEST_REQUIRED = {
    "prereg_id", "input_sha256", "race_manifest_sha256", "split_manifest_sha256", "partitions"
}
EXPECTED_PART_REQUIRED = {
    "row_identity_sha256", "race_set_sha256", "subgroup_membership_sha256"
}


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def finite_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def require_exact_keys(obj, required, scope, errors):
    if not isinstance(obj, dict):
        errors.append({"scope": scope, "error": "not_object"})
        return
    missing = sorted(required - set(obj))
    extra = sorted(set(obj) - required)
    if missing:
        errors.append({"scope": scope, "error": "missing_fields", "fields": missing})
    if extra:
        errors.append({"scope": scope, "error": "unexpected_fields", "fields": extra})


def valid_sha(x):
    return isinstance(x, str) and SHA_RE.fullmatch(x) is not None


def close(a, b, tol=TOL):
    return finite_num(a) and finite_num(b) and abs(float(a) - float(b)) <= tol


def seed_for(prereg_id, impl_id):
    raw = hashlib.sha256(f"{prereg_id}:{impl_id}".encode("utf-8")).digest()
    return int.from_bytes(raw[:8], "big", signed=False)


def validate_expected_manifest(m, errors):
    require_exact_keys(m, EXPECTED_MANIFEST_REQUIRED, "expected_manifest", errors)
    if errors:
        return
    if not isinstance(m.get("prereg_id"), str) or not m["prereg_id"]:
        errors.append({"scope": "expected_manifest", "error": "invalid_prereg_id"})
    for k in ("input_sha256", "race_manifest_sha256", "split_manifest_sha256"):
        if not valid_sha(m.get(k)):
            errors.append({"scope": "expected_manifest", "error": "invalid_sha256", "field": k})
    parts = m.get("partitions")
    if not isinstance(parts, dict) or set(parts) != set(PARTITIONS):
        errors.append({"scope": "expected_manifest", "error": "invalid_partitions"})
        return
    for p in PARTITIONS:
        ep = parts[p]
        require_exact_keys(ep, EXPECTED_PART_REQUIRED, f"expected_manifest.{p}", errors)
        if isinstance(ep, dict):
            for k in EXPECTED_PART_REQUIRED:
                if not valid_sha(ep.get(k)):
                    errors.append({"scope": f"expected_manifest.{p}", "error": "invalid_sha256", "field": k})


def validate_bundle(b, expected, label):
    errors = []
    require_exact_keys(b, TOP_REQUIRED, label, errors)
    if errors:
        return errors, None

    impl = b.get("implementation_id")
    if impl not in EXPECTED_IMPL_IDS:
        errors.append({"scope": label, "error": "invalid_implementation_id", "value": impl})
        return errors, None

    if not isinstance(b.get("prereg_id"), str) or not b["prereg_id"]:
        errors.append({"scope": label, "error": "invalid_prereg_id"})
    for k in ("input_sha256", "race_manifest_sha256", "split_manifest_sha256"):
        if not valid_sha(b.get(k)):
            errors.append({"scope": label, "error": "invalid_sha256", "field": k})
    if errors:
        return errors, None

    # Must anchor to separately locked pre-outcome expected manifest.
    if b.get("prereg_id") != expected.get("prereg_id"):
        errors.append({"scope": label, "error": "expected_manifest_mismatch", "field": "prereg_id"})
    for k in ("input_sha256", "race_manifest_sha256", "split_manifest_sha256"):
        if b.get(k) != expected.get(k):
            errors.append({"scope": label, "error": "expected_manifest_mismatch", "field": k})
    if errors:
        return errors, None

    parts = b.get("partitions")
    if not isinstance(parts, dict) or set(parts) != set(PARTITIONS):
        errors.append({"scope": label, "error": "invalid_partitions"})
        return errors, None

    partition_states = {}
    for p in PARTITIONS:
        x = parts[p]
        before = len(errors)
        require_exact_keys(x, PART_REQUIRED, f"{label}.{p}", errors)
        if len(errors) != before:
            continue
        if not isinstance(x, dict):
            continue

        for k in ("row_count", "race_count", "subgroup_membership_count", "observed_wins"):
            v = x.get(k)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                errors.append({"scope": f"{label}.{p}", "error": "invalid_nonnegative_integer", "field": k, "value": v})
        for k in ("row_identity_sha256", "race_set_sha256", "subgroup_membership_sha256"):
            if not valid_sha(x.get(k)):
                errors.append({"scope": f"{label}.{p}", "error": "invalid_sha256", "field": k})
            if x.get(k) != expected["partitions"][p].get(k):
                errors.append({"scope": f"{label}.{p}", "error": "expected_manifest_mismatch", "field": k})
        primitive_float_fields = (
            "sum_predicted_probability_control", "sum_predicted_probability_ablation",
            "observed_win_rate", "mean_predicted_probability_control",
            "mean_predicted_probability_ablation", "Rc", "Ra"
        )
        for k in primitive_float_fields:
            if not finite_num(x.get(k)):
                errors.append({"scope": f"{label}.{p}", "error": "nonfinite_numeric", "field": k, "value": x.get(k)})
        if x.get("observed_wins") == 0:
            if x.get("D") is not None:
                errors.append({"scope": f"{label}.{p}", "error": "zero_event_D_must_be_null", "value": x.get("D")})
        elif not finite_num(x.get("D")):
            errors.append({"scope": f"{label}.{p}", "error": "nonfinite_numeric", "field": "D", "value": x.get("D")})

        rc = x.get("row_count")
        races = x.get("race_count")
        n = x.get("subgroup_membership_count")
        wins = x.get("observed_wins")
        if all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (rc, races, n, wins)):
            if races > rc:
                errors.append({"scope": f"{label}.{p}", "error": "race_count_gt_row_count"})
            if n > rc:
                errors.append({"scope": f"{label}.{p}", "error": "subgroup_count_gt_row_count"})
            if wins > n:
                errors.append({"scope": f"{label}.{p}", "error": "observed_wins_gt_subgroup_count"})

            if n == 0:
                partition_states[p] = "INCONCLUSIVE_ZERO_EVENTS"
                continue

            s_c = x.get("sum_predicted_probability_control")
            s_a = x.get("sum_predicted_probability_ablation")
            if finite_num(s_c) and finite_num(s_a):
                if not (0.0 < float(s_c) <= n + TOL):
                    errors.append({"scope": f"{label}.{p}", "error": "invalid_probability_sum", "field": "control", "value": s_c})
                if not (0.0 < float(s_a) <= n + TOL):
                    errors.append({"scope": f"{label}.{p}", "error": "invalid_probability_sum", "field": "ablation", "value": s_a})

                obs = wins / n
                mc = float(s_c) / n
                ma = float(s_a) / n
                if not close(x.get("observed_win_rate"), obs):
                    errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "observed_win_rate", "recomputed": obs})
                if not close(x.get("mean_predicted_probability_control"), mc):
                    errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "mean_predicted_probability_control", "recomputed": mc})
                if not close(x.get("mean_predicted_probability_ablation"), ma):
                    errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "mean_predicted_probability_ablation", "recomputed": ma})
                if mc <= 0.0 or ma <= 0.0:
                    errors.append({"scope": f"{label}.{p}", "error": "nonpositive_mean_probability"})
                elif wins == 0:
                    if not close(x.get("Rc"), 0.0):
                        errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "Rc", "recomputed": 0.0})
                    if not close(x.get("Ra"), 0.0):
                        errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "Ra", "recomputed": 0.0})
                    partition_states[p] = "INCONCLUSIVE_ZERO_EVENTS"
                else:
                    Rc = obs / mc
                    Ra = obs / ma
                    if Rc <= 0.0 or Ra <= 0.0:
                        partition_states[p] = "INCONCLUSIVE_ZERO_EVENTS"
                        continue
                    D = abs(math.log(Rc)) - abs(math.log(Ra))
                    if not close(x.get("Rc"), Rc):
                        errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "Rc", "recomputed": Rc})
                    if not close(x.get("Ra"), Ra):
                        errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "Ra", "recomputed": Ra})
                    if not close(x.get("D"), D):
                        errors.append({"scope": f"{label}.{p}", "error": "arithmetic_mismatch", "field": "D", "recomputed": D})
                    partition_states[p] = "VALID"

    if errors:
        return errors, None

    inf = b.get("inference")
    before = len(errors)
    require_exact_keys(inf, INFERENCE_REQUIRED, f"{label}.inference", errors)
    if len(errors) != before or not isinstance(inf, dict):
        return errors, None

    expected_seed = seed_for(b["prereg_id"], impl)
    if inf.get("bootstrap_seed") != expected_seed:
        errors.append({"scope": f"{label}.inference", "error": "wrong_bootstrap_seed", "expected": expected_seed, "actual": inf.get("bootstrap_seed")})
    if inf.get("bootstrap_replications") != BOOTSTRAP_REPS:
        errors.append({"scope": f"{label}.inference", "error": "wrong_bootstrap_replications"})
    vr = inf.get("bootstrap_valid_replicates")
    ir = inf.get("bootstrap_invalid_replicates")
    vf = inf.get("bootstrap_valid_fraction")
    if not isinstance(vr, int) or isinstance(vr, bool) or vr < 0:
        errors.append({"scope": f"{label}.inference", "error": "invalid_valid_replicates"})
    if not isinstance(ir, int) or isinstance(ir, bool) or ir < 0:
        errors.append({"scope": f"{label}.inference", "error": "invalid_invalid_replicates"})
    if isinstance(vr, int) and isinstance(ir, int) and not isinstance(vr, bool) and not isinstance(ir, bool):
        if vr + ir != BOOTSTRAP_REPS:
            errors.append({"scope": f"{label}.inference", "error": "bootstrap_count_mismatch"})
        expected_frac = vr / BOOTSTRAP_REPS
        if not close(vf, expected_frac):
            errors.append({"scope": f"{label}.inference", "error": "bootstrap_fraction_mismatch", "recomputed": expected_frac})
    for k in ("full_D_ci_lower", "full_D_ci_upper", "bootstrap_valid_fraction"):
        if not finite_num(inf.get(k)):
            errors.append({"scope": f"{label}.inference", "error": "nonfinite_numeric", "field": k})
    if finite_num(inf.get("full_D_ci_lower")) and finite_num(inf.get("full_D_ci_upper")):
        if float(inf["full_D_ci_lower"]) > float(inf["full_D_ci_upper"]):
            errors.append({"scope": f"{label}.inference", "error": "ci_lower_gt_upper"})
    if inf.get("rng") != EXPECTED_RNG:
        errors.append({"scope": f"{label}.inference", "error": "wrong_rng"})
    if inf.get("quantile_method") != EXPECTED_QUANTILE:
        errors.append({"scope": f"{label}.inference", "error": "wrong_quantile_method"})

    if errors:
        return errors, None

    if any(partition_states.get(p) == "INCONCLUSIVE_ZERO_EVENTS" for p in PARTITIONS):
        recomputed_verdict = "INCONCLUSIVE"
    elif not isinstance(vr, int) or not finite_num(vf) or vr < MIN_VALID_REPS or float(vf) < MIN_VALID_FRAC:
        recomputed_verdict = "INCONCLUSIVE"
    else:
        pA, pB, pF = parts["A"], parts["B"], parts["FULL"]
        supported = (
            float(pA["D"]) > 0.0 and float(pB["D"]) > 0.0
            and float(pA["Rc"]) < 1.0 and float(pB["Rc"]) < 1.0 and float(pF["Rc"]) < 1.0
            and float(inf["full_D_ci_lower"]) > 0.0
        )
        recomputed_verdict = "SUPPORTED" if supported else "NOT_SUPPORTED"

    reported = b.get("confirmatory_verdict")
    if reported not in {"SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE"}:
        errors.append({"scope": label, "error": "invalid_implementation_verdict", "value": reported})
    elif reported != recomputed_verdict:
        errors.append({"scope": label, "error": "verdict_mismatch", "reported": reported, "recomputed": recomputed_verdict})

    return errors, recomputed_verdict


def compare_bundles(a, b):
    mismatches = []
    if a["implementation_id"] == b["implementation_id"]:
        mismatches.append({"scope": "top", "field": "implementation_id", "error": "implementations_not_distinct"})

    for k in ("prereg_id", "input_sha256", "race_manifest_sha256", "split_manifest_sha256"):
        if a.get(k) != b.get(k):
            mismatches.append({"scope": "top", "field": k, "A": a.get(k), "B": b.get(k), "kind": "exact"})

    for p in PARTITIONS:
        xa, xb = a["partitions"][p], b["partitions"][p]
        for k in (
            "row_count", "race_count", "subgroup_membership_count", "observed_wins",
            "row_identity_sha256", "race_set_sha256", "subgroup_membership_sha256"
        ):
            if xa.get(k) != xb.get(k):
                mismatches.append({"scope": p, "field": k, "A": xa.get(k), "B": xb.get(k), "kind": "exact"})
        for k in (
            "sum_predicted_probability_control", "sum_predicted_probability_ablation",
            "observed_win_rate", "mean_predicted_probability_control",
            "mean_predicted_probability_ablation", "Rc", "Ra", "D"
        ):
            va, vb = xa.get(k), xb.get(k)
            if va is None and vb is None and k == "D":
                continue
            if not close(va, vb):
                mismatches.append({"scope": p, "field": k, "A": va, "B": vb,
                                   "abs_diff": abs(float(va)-float(vb)) if finite_num(va) and finite_num(vb) else None,
                                   "tolerance": TOL, "kind": "float"})
    return mismatches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle_1", type=Path)
    ap.add_argument("bundle_2", type=Path)
    ap.add_argument("--expected-manifest", type=Path, required=True,
                    help="Separately locked pre-outcome identity/subgroup expectation manifest.")
    ap.add_argument("--out", type=Path, default=Path("T009R_reconciliation_v2.json"))
    args = ap.parse_args()

    a, b, expected = load(args.bundle_1), load(args.bundle_2), load(args.expected_manifest)
    errors = []
    validate_expected_manifest(expected, errors)
    if errors:
        verdict_a = None
        verdict_b = None
    else:
        va, verdict_a = validate_bundle(a, expected, "bundle_1")
        vb, verdict_b = validate_bundle(b, expected, "bundle_2")
        errors.extend(va)
        errors.extend(vb)
    if not errors and not va and not vb:
        errors.extend(compare_bundles(a, b))
        if verdict_a != verdict_b:
            errors.append({"scope": "top", "field": "recomputed_verdict", "A": verdict_a, "B": verdict_b, "kind": "exact"})

    result = {
        "checker_id": "T009R_CHECKER_C_V3_CANDIDATE",
        "tolerance_abs": TOL,
        "status": "PASS" if not errors else "REPORT_MISMATCH",
        "protocol_effect": "NONE" if not errors else "PROTOCOL_INVALID",
        "error_count": len(errors),
        "errors": errors,
        "recomputed_verdict_A": verdict_a,
        "recomputed_verdict_B": verdict_b,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if not errors else 2)


if __name__ == "__main__":
    main()
