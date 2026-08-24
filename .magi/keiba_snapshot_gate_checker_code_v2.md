# KEIBA Snapshot Gate Checker v2 — Bridge audit copy

Canonical executable: `scripts/keiba_snapshot_gate_check_v2.py`

Canonical tested SHA-256: `3e4bcc4b8bd045ac8f79f53ae90a5570c18eecd6594c606522840c1621f8bdeb`

Key fail-closed behavior in canonical code:

```python
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
```

The source manifest is mandatory. Each manifest entry contains a relative path and declared SHA-256. The checker resolves the actual file, recomputes its bytes, and only adds the SHA to `verified_source_hashes` when actual equals declared. Every provenance row's `source_file_sha256` must exist in that verified set.

For each row the canonical checker:

```python
if key in keys:
    violation("DUPLICATE_FROZEN_FEATURE")
if role not in ROLES:
    violation("INVALID_SNAPSHOT_ROLE")
if basis not in SOURCE_TIME_BASES:
    violation("INVALID_SOURCE_TIME_BASIS")
if feature in FORBIDDEN_FEATURES:
    violation("FORBIDDEN_POST_RACE_FEATURE")
if source in FORBIDDEN_SOURCES:
    violation("FORBIDDEN_FINAL_SOURCE")
approved_sources = FEATURE_SOURCES.get(feature)
if approved_sources is None:
    violation("UNKNOWN_FEATURE_FAIL_CLOSED")
elif source not in approved_sources:
    violation("FEATURE_SOURCE_NOT_APPROVED")
if source_sha not in verified_source_hashes:
    violation("SOURCE_SHA_NOT_VERIFIED_BY_MANIFEST")
```

It parses all timestamps as offset-aware ISO8601 and enforces:

```python
if feature_source_time > prediction_snapshot_time:
    violation("SOURCE_AFTER_PREDICTION_SNAPSHOT")
if source_capture_time > prediction_snapshot_time:
    violation("CAPTURE_AFTER_PREDICTION_SNAPSHOT")
if basis == "OFFICIAL_ANNOUNCEMENT" and feature_source_time > source_capture_time:
    violation("ANNOUNCEMENT_AFTER_CAPTURE")
if basis == "LOCAL_ACQUISITION" and feature_source_time != source_capture_time:
    violation("LOCAL_ACQUISITION_TIME_MISMATCH")
```

It also rejects blank race_id, horse_no, feature_name, feature_value and source_row_id, can compare an expected frozen provenance CSV SHA-256, outputs a JSON audit report, returns exit code 0 only on zero violations and exit code 2 otherwise.

Synthetic tests are separately frozen in `.magi/keiba_snapshot_gate_checker_test_v2.json`. This markdown is an audit representation; the canonical executable is the `.py` file and its SHA above.