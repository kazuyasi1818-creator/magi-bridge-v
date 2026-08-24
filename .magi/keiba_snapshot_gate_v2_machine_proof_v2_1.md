# KEIBA Snapshot Gate v2 Machine Proof v2.1

## Frozen exact-byte identities

- GitHub contract path: `.magi/keiba_pre_race_snapshot_contract_v2.json`
- contract SHA-256: `801cea0d8998401b4d3c7adfa9b381d830ded70520241be5faad52cddcad1227`
- contract Git blob after refreeze: `1d2fb3bf37b3ad4b69fd24fcee7d328056df5ee3`
- canonical checker path: `scripts/keiba_snapshot_gate_check_v2.py`
- checker SHA-256: `3e4bcc4b8bd045ac8f79f53ae90a5570c18eecd6594c606522840c1621f8bdeb`
- checker Git blob after refreeze: `9686bb21c3c6b5ed4e5482d36a646d870c2104f5`

The contract and checker were refrozen byte-for-byte before this proof. No model, Gate threshold, DEV split, VALIDATION, or OOS state was changed.

## Actual source files used by the source manifest

- `raw/wh.txt` SHA `c75f0fa4e390afc8c3fb63c1eb97b0303f3bb78599b41c9080890d8156f8d2b3` exact content: `WH synthetic pre-race bodyweight capture\n`
- `raw/odds.txt` SHA `99d443c75a1ff279ce2b9ae3a985ef4fce278049673d942e0b30cbe508530f78` exact content: `O1 synthetic odds capture\n`

## Source manifest

- SHA-256: `ce28da5c5dd02bc09e9cdb820b8fc0a6dfc15dfa8c1aa355a70cb9edf59c1999`

```json
{
  "sources": [
    {
      "path": "raw/wh.txt",
      "sha256": "c75f0fa4e390afc8c3fb63c1eb97b0303f3bb78599b41c9080890d8156f8d2b3"
    },
    {
      "path": "raw/odds.txt",
      "sha256": "99d443c75a1ff279ce2b9ae3a985ef4fce278049673d942e0b30cbe508530f78"
    }
  ]
}
```

## PASS input CSV

- SHA-256: `24a3933b8c48f3d32b11bfa28d9aec1b026dc6fbed003ab509c7df441032ef4b`

```csv
race_id,horse_no,snapshot_role,prediction_snapshot_time_jst,feature_name,feature_value,feature_source_time_jst,source_capture_time_jst,source_time_basis,source_kind,source_file_sha256,source_row_id
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,body_weight_kg,480,2026-08-24T11:10:00+09:00,2026-08-24T11:10:10+09:00,OFFICIAL_ANNOUNCEMENT,JRA_VAN_0B11_WH,c75f0fa4e390afc8c3fb63c1eb97b0303f3bb78599b41c9080890d8156f8d2b3,WH:1:1
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,pre_win_odds,3.5,2026-08-24T11:59:00+09:00,2026-08-24T11:59:00+09:00,LOCAL_ACQUISITION,JRA_VAN_ODDS_TIMESERIES,99d443c75a1ff279ce2b9ae3a985ef4fce278049673d942e0b30cbe508530f78,O1:1:1
```

## PASS output JSON

- SHA-256: `425e8716643e5ef08948edac25dd7cff080207a4d5b520692f75b555e7de481a`

```json
{
  "checker_id": "KEIBA_SNAPSHOT_GATE_CHECK_V2",
  "input_file": "pass.csv",
  "input_sha256": "24a3933b8c48f3d32b11bfa28d9aec1b026dc6fbed003ab509c7df441032ef4b",
  "source_manifest_file": "source_manifest.json",
  "source_manifest_sha256": "ce28da5c5dd02bc09e9cdb820b8fc0a6dfc15dfa8c1aa355a70cb9edf59c1999",
  "verified_source_file_count": 2,
  "rows": 2,
  "snapshot_counts": {"EARLY": 2},
  "feature_counts": {"body_weight_kg": 1, "pre_win_odds": 1},
  "violation_count": 0,
  "status": "PASS",
  "violations": [],
  "violations_truncated": false
}
```

## FAIL input CSV

- SHA-256: `03d2f769a347adcdf1157de17ac6b3339a00f12397911daee28a4716d7c0b14b`

```csv
race_id,horse_no,snapshot_role,prediction_snapshot_time_jst,feature_name,feature_value,feature_source_time_jst,source_capture_time_jst,source_time_basis,source_kind,source_file_sha256,source_row_id
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,body_weight_kg,480,2026-08-24T12:01:00+09:00,2026-08-24T11:10:10+09:00,OFFICIAL_ANNOUNCEMENT,JRA_VAN_0B11_WH,c75f0fa4e390afc8c3fb63c1eb97b0303f3bb78599b41c9080890d8156f8d2b3,WH:1:1
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,body_weight_kg,480,2026-08-24T11:10:00+09:00,2026-08-24T11:10:10+09:00,OFFICIAL_ANNOUNCEMENT,JVD_FINAL_PARSED,c75f0fa4e390afc8c3fb63c1eb97b0303f3bb78599b41c9080890d8156f8d2b3,x2
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,final_finish,1,2026-08-24T11:10:00+09:00,2026-08-24T11:10:10+09:00,OFFICIAL_ANNOUNCEMENT,JRA_VAN_0B11_WH,c75f0fa4e390afc8c3fb63c1eb97b0303f3bb78599b41c9080890d8156f8d2b3,x3
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,pre_win_odds,3.5,2026-08-24T11:59:00+09:00,2026-08-24T12:02:00+09:00,LOCAL_ACQUISITION,JRA_VAN_ODDS_TIMESERIES,99d443c75a1ff279ce2b9ae3a985ef4fce278049673d942e0b30cbe508530f78,x4
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,pre_win_odds,3.5,2026-08-24T11:59:00+09:00,2026-08-24T11:59:00+09:00,LOCAL_ACQUISITION,JRA_VAN_ODDS_TIMESERIES,ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff,x5
2026082401010101,1,EARLY,2026-08-24T12:00:00+09:00,mystery_feature,480,2026-08-24T11:10:00+09:00,2026-08-24T11:10:10+09:00,OFFICIAL_ANNOUNCEMENT,JRA_VAN_0B11_WH,c75f0fa4e390afc8c3fb63c1eb97b0303f3bb78599b41c9080890d8156f8d2b3,x6
```

## FAIL output JSON

- SHA-256: `01562ba509754e0fba955cf92774579110b0ca69593b3248271bec265fd31830`

```json
{
  "checker_id": "KEIBA_SNAPSHOT_GATE_CHECK_V2",
  "input_file": "fail.csv",
  "input_sha256": "03d2f769a347adcdf1157de17ac6b3339a00f12397911daee28a4716d7c0b14b",
  "source_manifest_file": "source_manifest.json",
  "source_manifest_sha256": "ce28da5c5dd02bc09e9cdb820b8fc0a6dfc15dfa8c1aa355a70cb9edf59c1999",
  "verified_source_file_count": 2,
  "rows": 6,
  "snapshot_counts": {"EARLY": 6},
  "feature_counts": {"body_weight_kg": 2, "final_finish": 1, "pre_win_odds": 2, "mystery_feature": 1},
  "violation_count": 12,
  "status": "FAIL",
  "violations": [
    {"type":"SOURCE_AFTER_PREDICTION_SNAPSHOT","line":2,"feature":"body_weight_kg"},
    {"type":"ANNOUNCEMENT_AFTER_CAPTURE","line":2,"feature":"body_weight_kg"},
    {"type":"DUPLICATE_FROZEN_FEATURE","line":3,"key":["2026082401010101","1","EARLY","body_weight_kg"]},
    {"type":"FORBIDDEN_FINAL_SOURCE","line":3,"source_kind":"JVD_FINAL_PARSED"},
    {"type":"FEATURE_SOURCE_NOT_APPROVED","line":3,"feature":"body_weight_kg","source_kind":"JVD_FINAL_PARSED","approved":["JRA_VAN_0B11_WH"]},
    {"type":"FORBIDDEN_POST_RACE_FEATURE","line":4,"feature":"final_finish"},
    {"type":"UNKNOWN_FEATURE_FAIL_CLOSED","line":4,"feature":"final_finish"},
    {"type":"CAPTURE_AFTER_PREDICTION_SNAPSHOT","line":5,"feature":"pre_win_odds"},
    {"type":"LOCAL_ACQUISITION_TIME_MISMATCH","line":5,"feature":"pre_win_odds"},
    {"type":"DUPLICATE_FROZEN_FEATURE","line":6,"key":["2026082401010101","1","EARLY","pre_win_odds"]},
    {"type":"SOURCE_SHA_NOT_VERIFIED_BY_MANIFEST","line":6,"sha256":"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"},
    {"type":"UNKNOWN_FEATURE_FAIL_CLOSED","line":7,"feature":"mystery_feature"}
  ],
  "violations_truncated": false
}
```

## Re-execution result

- command basis: `python checker_v2.py <csv> --source-manifest source_manifest.json --expected-input-sha256 <actual csv sha> --out <output.json>`
- PASS: exit code `0`, status `PASS`, violation_count `0`
- FAIL: exit code `2`, status `FAIL`, violation_count `12`
- FAIL unique violation types:
  - `ANNOUNCEMENT_AFTER_CAPTURE`
  - `CAPTURE_AFTER_PREDICTION_SNAPSHOT`
  - `DUPLICATE_FROZEN_FEATURE`
  - `FEATURE_SOURCE_NOT_APPROVED`
  - `FORBIDDEN_FINAL_SOURCE`
  - `FORBIDDEN_POST_RACE_FEATURE`
  - `LOCAL_ACQUISITION_TIME_MISMATCH`
  - `SOURCE_AFTER_PREDICTION_SNAPSHOT`
  - `SOURCE_SHA_NOT_VERIFIED_BY_MANIFEST`
  - `UNKNOWN_FEATURE_FAIL_CLOSED`

## Scope

- Synthetic machine proof only.
- No DEV performance trial executed.
- VALIDATION/OOS remained closed.
- Real JV-Link COM/network capture is not claimed by this proof.
