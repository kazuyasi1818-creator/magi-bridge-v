#!/usr/bin/env python3
from __future__ import annotations
import contextlib, io, json, sys
from pathlib import Path
import keiba_snapshot_gate_check_v2 as base

base.FEATURE_SOURCES = {
    "pre_win_odds":{"JRA_VAN_ODDS_TIMESERIES","TARGET_PRE_RACE_EXPORT"},
    "body_weight_kg":{"JRA_VAN_0B11_WH"},
    "body_weight_change_kg":{"JRA_VAN_0B11_WH"},
    "weather":{"JRA_VAN_0B14_WE","TARGET_PRE_RACE_EXPORT"},
    "track_condition_turf":{"JRA_VAN_0B14_WE"},
    "track_condition_dirt":{"JRA_VAN_0B14_WE"},
    "scratch_exclusion_code":{"JRA_VAN_0B14_AV"},
    "current_jockey_code":{"JRA_VAN_0B14_JC","TARGET_PRE_RACE_EXPORT"},
    "current_jockey_name":{"JRA_VAN_0B14_JC","TARGET_PRE_RACE_EXPORT"},
    "current_carried_weight_x10":{"JRA_VAN_0B14_JC","TARGET_PRE_RACE_EXPORT"},
    "current_post_time":{"JRA_VAN_0B14_TC","TARGET_PRE_RACE_EXPORT"},
    "current_distance":{"JRA_VAN_0B14_CC","TARGET_PRE_RACE_EXPORT"},
    "current_track_code":{"JRA_VAN_0B14_CC","TARGET_PRE_RACE_EXPORT"},
    "current_surface":{"TARGET_PRE_RACE_EXPORT"},
    "current_class_code":{"TARGET_PRE_RACE_EXPORT"},
    "registered_horses":{"TARGET_PRE_RACE_EXPORT"},
    "starters":{"TARGET_PRE_RACE_EXPORT"},
}
base.FORBIDDEN_FEATURES = {
    "final_finish","target_win","target_top3","final_win_odds","final_popularity",
    "win_payout_yen_per_100","place_payout_yen_per_100",
    "abnormal_code","current_course_code","track_condition"
}
base.FORBIDDEN_SOURCES = {"JVD_FINAL_PARSED","POST_RACE_FINAL_STATE","RESULT_FILE"}


def main():
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        rc = base.main()
    text = capture.getvalue().strip()
    try:
        obj = json.loads(text)
    except Exception:
        print(text)
        return rc
    obj["checker_id"] = "KEIBA_SNAPSHOT_GATE_CHECK_V3"
    obj["supersedes_checker"] = "KEIBA_SNAPSHOT_GATE_CHECK_V2"
    obj["schema_semantics"] = "JV-Data AV/WE/CC semantics corrected before real capture/model execution"
    out_path = None
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        if i + 1 < len(sys.argv):
            out_path = Path(sys.argv[i+1])
    final = json.dumps(obj, ensure_ascii=False, indent=2)
    if out_path:
        out_path.write_text(final, encoding="utf-8")
    print(final)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
