#!/usr/bin/env python3
import argparse, csv, datetime as dt, hashlib, json, re, sys
from pathlib import Path

REQUIRED = [
    "race_id","horse_no","snapshot_role","prediction_snapshot_time_jst",
    "feature_name","feature_value","feature_source_time_jst","source_capture_time_jst",
    "source_time_basis","source_kind","source_file_sha256","source_row_id"
]
ROLES = {"EARLY","LATE"}
SOURCE_TIME_BASES = {"OFFICIAL_ANNOUNCEMENT","LOCAL_ACQUISITION"}
FEATURE_SOURCES = {
    "pre_win_odds":{"JRA_VAN_ODDS_TIMESERIES","TARGET_PRE_RACE_EXPORT"},
    "body_weight_kg":{"JRA_VAN_0B11_WH"},
    "body_weight_change_kg":{"JRA_VAN_0B11_WH"},
    "weather":{"JRA_VAN_0B14_WE","TARGET_PRE_RACE_EXPORT"},
    "track_condition":{"JRA_VAN_0B14_WE","TARGET_PRE_RACE_EXPORT"},
    "abnormal_code":{"JRA_VAN_0B14_AV","TARGET_PRE_RACE_EXPORT"},
    "current_jockey_code":{"JRA_VAN_0B14_JC","TARGET_PRE_RACE_EXPORT"},
    "current_jockey_name":{"JRA_VAN_0B14_JC","TARGET_PRE_RACE_EXPORT"},
    "current_carried_weight_x10":{"JRA_VAN_0B14_JC","TARGET_PRE_RACE_EXPORT"},
    "current_post_time":{"JRA_VAN_0B14_TC","TARGET_PRE_RACE_EXPORT"},
    "current_distance":{"JRA_VAN_0B14_CC","TARGET_PRE_RACE_EXPORT"},
    "current_course_code":{"JRA_VAN_0B14_CC","TARGET_PRE_RACE_EXPORT"},
    "current_surface":{"TARGET_PRE_RACE_EXPORT"},
    "current_class_code":{"TARGET_PRE_RACE_EXPORT"},
    "registered_horses":{"TARGET_PRE_RACE_EXPORT"},
    "starters":{"TARGET_PRE_RACE_EXPORT"},
}
FORBIDDEN_FEATURES = {
    "final_finish","target_win","target_top3","final_win_odds","final_popularity",
    "win_payout_yen_per_100","place_payout_yen_per_100"
}
FORBIDDEN_SOURCES = {"JVD_FINAL_PARSED","POST_RACE_FINAL_STATE","RESULT_FILE"}
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def parse_ts(s: str):
    if not s:
        raise ValueError("empty timestamp")
    s = s.strip().replace("Z", "+00:00")
    x = dt.datetime.fromisoformat(s)
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError("timestamp must be offset-aware")
    return x

def load_and_verify_source_manifest(path: Path):
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    sources = obj.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("source manifest requires non-empty sources[]")
    verified = {}
    failures = []
    for i, item in enumerate(sources):
        rel = item.get("path")
        declared = (item.get("sha256") or "").lower()
        if not rel or not SHA_RE.fullmatch(declared):
            failures.append({"type":"INVALID_SOURCE_MANIFEST_ENTRY","index":i})
            continue
        fp = (path.parent / rel).resolve()
        if not fp.exists() or not fp.is_file():
            failures.append({"type":"SOURCE_FILE_MISSING","index":i,"path":str(fp)})
            continue
        actual = sha256_file(fp).lower()
        if actual != declared:
            failures.append({"type":"SOURCE_FILE_SHA_MISMATCH","index":i,"path":str(fp),"declared":declared,"actual":actual})
            continue
        verified[actual] = str(fp)
    return obj, verified, failures

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--source-manifest", required=True)
    ap.add_argument("--expected-input-sha256", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    p = Path(args.csv_path)
    manifest_path = Path(args.source_manifest)
    actual_sha = sha256_file(p)
    violations = []
    rows = 0
    keys = set()
    feature_counts = {}
    snapshot_counts = {}

    if args.expected_input_sha256 and actual_sha.lower() != args.expected_input_sha256.lower():
        violations.append({"type":"INPUT_SHA_MISMATCH","expected":args.expected_input_sha256,"actual":actual_sha})

    try:
        manifest_obj, verified_source_hashes, manifest_failures = load_and_verify_source_manifest(manifest_path)
        violations.extend(manifest_failures)
        manifest_sha = sha256_file(manifest_path)
    except Exception as e:
        verified_source_hashes = {}
        manifest_sha = None
        violations.append({"type":"SOURCE_MANIFEST_ERROR","error":str(e)})

    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        missing = [c for c in REQUIRED if c not in fields]
        if missing:
            violations.append({"type":"MISSING_COLUMNS","columns":missing})
        else:
            for i, r in enumerate(reader, start=2):
                rows += 1
                race_id = (r.get("race_id") or "").strip()
                horse_no = (r.get("horse_no") or "").strip()
                feature = (r.get("feature_name") or "").strip()
                value = (r.get("feature_value") or "").strip()
                role = (r.get("snapshot_role") or "").strip()
                source = (r.get("source_kind") or "").strip().upper()
                basis = (r.get("source_time_basis") or "").strip().upper()
                source_sha = (r.get("source_file_sha256") or "").strip().lower()
                row_id = (r.get("source_row_id") or "").strip()
                key = (race_id, horse_no, role, feature)

                for field_name, field_value in [("race_id",race_id),("horse_no",horse_no),("feature_name",feature),("feature_value",value),("source_row_id",row_id)]:
                    if not field_value:
                        violations.append({"type":"BLANK_REQUIRED_VALUE","line":i,"field":field_name})

                if key in keys:
                    violations.append({"type":"DUPLICATE_FROZEN_FEATURE","line":i,"key":key})
                keys.add(key)
                feature_counts[feature] = feature_counts.get(feature,0)+1
                snapshot_counts[role] = snapshot_counts.get(role,0)+1

                if role not in ROLES:
                    violations.append({"type":"INVALID_SNAPSHOT_ROLE","line":i,"value":role})
                if basis not in SOURCE_TIME_BASES:
                    violations.append({"type":"INVALID_SOURCE_TIME_BASIS","line":i,"value":basis})
                if feature in FORBIDDEN_FEATURES:
                    violations.append({"type":"FORBIDDEN_POST_RACE_FEATURE","line":i,"feature":feature})
                if source in FORBIDDEN_SOURCES:
                    violations.append({"type":"FORBIDDEN_FINAL_SOURCE","line":i,"source_kind":source})
                approved_sources = FEATURE_SOURCES.get(feature)
                if approved_sources is None:
                    violations.append({"type":"UNKNOWN_FEATURE_FAIL_CLOSED","line":i,"feature":feature})
                elif source not in approved_sources:
                    violations.append({"type":"FEATURE_SOURCE_NOT_APPROVED","line":i,"feature":feature,"source_kind":source,"approved":sorted(approved_sources)})

                if not SHA_RE.fullmatch(source_sha):
                    violations.append({"type":"INVALID_SOURCE_SHA256","line":i})
                elif source_sha not in verified_source_hashes:
                    violations.append({"type":"SOURCE_SHA_NOT_VERIFIED_BY_MANIFEST","line":i,"sha256":source_sha})

                try:
                    source_t = parse_ts(r.get("feature_source_time_jst") or "")
                    capture_t = parse_ts(r.get("source_capture_time_jst") or "")
                    snap_t = parse_ts(r.get("prediction_snapshot_time_jst") or "")
                    if source_t > snap_t:
                        violations.append({"type":"SOURCE_AFTER_PREDICTION_SNAPSHOT","line":i,"feature":feature})
                    if capture_t > snap_t:
                        violations.append({"type":"CAPTURE_AFTER_PREDICTION_SNAPSHOT","line":i,"feature":feature})
                    if basis == "OFFICIAL_ANNOUNCEMENT" and source_t > capture_t:
                        violations.append({"type":"ANNOUNCEMENT_AFTER_CAPTURE","line":i,"feature":feature})
                    if basis == "LOCAL_ACQUISITION" and source_t != capture_t:
                        violations.append({"type":"LOCAL_ACQUISITION_TIME_MISMATCH","line":i,"feature":feature})
                except Exception as e:
                    violations.append({"type":"TIMESTAMP_PARSE_ERROR","line":i,"error":str(e)})

    result = {
        "checker_id":"KEIBA_SNAPSHOT_GATE_CHECK_V2",
        "input_file":p.name,
        "input_sha256":actual_sha,
        "source_manifest_file":manifest_path.name,
        "source_manifest_sha256":manifest_sha,
        "verified_source_file_count":len(verified_source_hashes),
        "rows":rows,
        "snapshot_counts":snapshot_counts,
        "feature_counts":feature_counts,
        "violation_count":len(violations),
        "status":"PASS" if not violations else "FAIL",
        "violations":violations[:300],
        "violations_truncated":len(violations)>300
    }
    txt = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(txt, encoding="utf-8")
    print(txt)
    return 0 if not violations else 2

if __name__ == "__main__":
    sys.exit(main())
