# KEIBA Snapshot Gate Checker v1 — Bridge audit copy

- canonical code path: `scripts/keiba_snapshot_gate_check_v1.py`
- canonical code SHA-256: `d359e7e1084e94f655bea855425f353601361736008b5d1fbe50691e8e0b7658`
- purpose: audit copy only; canonical executable remains the `.py` file above.

```python
#!/usr/bin/env python3
import argparse, csv, datetime as dt, hashlib, json, re, sys
from pathlib import Path

REQUIRED = [
    "race_id","horse_no","snapshot_role","prediction_snapshot_time_jst",
    "feature_name","feature_value","feature_source_time_jst","source_kind",
    "source_file_sha256","source_row_id"
]
ROLES = {"EARLY","LATE"}
CURRENT = {
    "current_surface","current_distance","current_class_code","current_course_code",
    "current_jockey_code","current_jockey_name","current_carried_weight_x10",
    "body_weight_kg","body_weight_change_kg","abnormal_code","registered_horses",
    "starters","track_condition","weather"
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--expected-input-sha256", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    p = Path(args.csv_path)
    actual_sha = sha256_file(p)
    violations = []
    rows = 0
    keys = set()
    feature_counts = {}
    snapshot_counts = {}

    if args.expected_input_sha256 and actual_sha.lower() != args.expected_input_sha256.lower():
        violations.append({"type":"INPUT_SHA_MISMATCH","expected":args.expected_input_sha256,"actual":actual_sha})

    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        missing = [c for c in REQUIRED if c not in fields]
        if missing:
            violations.append({"type":"MISSING_COLUMNS","columns":missing})
        else:
            for i, r in enumerate(reader, start=2):
                rows += 1
                feature = (r.get("feature_name") or "").strip()
                role = (r.get("snapshot_role") or "").strip()
                source = (r.get("source_kind") or "").strip().upper()
                key = (r.get("race_id"), r.get("horse_no"), role, feature)
                if key in keys:
                    violations.append({"type":"DUPLICATE_FROZEN_FEATURE","line":i,"key":key})
                keys.add(key)
                feature_counts[feature] = feature_counts.get(feature,0)+1
                snapshot_counts[role] = snapshot_counts.get(role,0)+1

                if role not in ROLES:
                    violations.append({"type":"INVALID_SNAPSHOT_ROLE","line":i,"value":role})
                if feature in FORBIDDEN_FEATURES:
                    violations.append({"type":"FORBIDDEN_POST_RACE_FEATURE","line":i,"feature":feature})
                if feature in CURRENT and source in FORBIDDEN_SOURCES:
                    violations.append({"type":"CURRENT_FEATURE_FROM_FINAL_SOURCE","line":i,"feature":feature,"source_kind":source})
                if not SHA_RE.fullmatch((r.get("source_file_sha256") or "").strip()):
                    violations.append({"type":"INVALID_SOURCE_SHA256","line":i})
                if not (r.get("source_row_id") or "").strip():
                    violations.append({"type":"MISSING_SOURCE_ROW_ID","line":i})
                try:
                    source_t = parse_ts(r.get("feature_source_time_jst") or "")
                    snap_t = parse_ts(r.get("prediction_snapshot_time_jst") or "")
                    if source_t > snap_t:
                        violations.append({"type":"SOURCE_AFTER_PREDICTION_SNAPSHOT","line":i,"feature":feature,"feature_source_time_jst":source_t.isoformat(),"prediction_snapshot_time_jst":snap_t.isoformat()})
                except Exception as e:
                    violations.append({"type":"TIMESTAMP_PARSE_ERROR","line":i,"error":str(e)})

    result = {
        "checker_id":"KEIBA_SNAPSHOT_GATE_CHECK_V1",
        "input_file":p.name,
        "input_sha256":actual_sha,
        "rows":rows,
        "snapshot_counts":snapshot_counts,
        "feature_counts":feature_counts,
        "violation_count":len(violations),
        "status":"PASS" if not violations else "FAIL",
        "violations":violations[:200],
        "violations_truncated":len(violations)>200
    }
    txt = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(txt, encoding="utf-8")
    print(txt)
    return 0 if not violations else 2

if __name__ == "__main__":
    sys.exit(main())
```

Synthetic destructive test evidence is in `.magi/keiba_snapshot_gate_checker_test_v1.json`.