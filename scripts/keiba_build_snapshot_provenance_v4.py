#!/usr/bin/env python3
from __future__ import annotations
import keiba_build_snapshot_provenance_v3 as v3


def emit_wh(rows, plan, c, feature_name, feature_value, horse_no):
    if feature_value is None or str(feature_value).strip() == '':
        return
    announce = c.get('announce_time')
    raw_announce = str(c.get('record', {}).get('raw_announcement_code') or '').strip()
    if announce is not None:
        source_time = announce
        basis = 'OFFICIAL_ANNOUNCEMENT'
    elif raw_announce == '00000000':
        source_time = c['capture_time']
        basis = 'LOCAL_ACQUISITION'
    else:
        return
    rows.append({
        'race_id': plan['race_id'],
        'horse_no': horse_no,
        'snapshot_role': plan['snapshot_role'],
        'prediction_snapshot_time_jst': plan['snapshot_time'].isoformat(),
        'feature_name': feature_name,
        'feature_value': feature_value,
        'feature_source_time_jst': source_time.isoformat(),
        'source_capture_time_jst': c['capture_time'].isoformat(),
        'source_time_basis': basis,
        'source_kind': 'JRA_VAN_0B11_WH',
        'source_file_sha256': c['raw_sha'],
        'source_row_id': f"{c['capture_id']}:{c['record_sequence']}:{horse_no}",
    })


def build_for_plan(captures, plan):
    # Keep all v3 semantics except WH, whose official timestamp is unavailable
    # in 0B11 and therefore must use actual local acquisition time.
    rows = [r for r in v3.build_for_plan(captures, plan)
            if r.get('source_kind') != 'JRA_VAN_0B11_WH']
    race_id = plan['race_id']
    horse_no = plan['horse_no']
    b11 = v3.latest_complete_capture(captures, '0B11', plan['snapshot_time'])
    wh_candidates = []
    for c in b11:
        if c.get('record_id') != 'WH' or str(c.get('record', {}).get('race_id') or '') != race_id:
            continue
        raw_a = str(c.get('record', {}).get('raw_announcement_code') or '').strip()
        if c.get('announce_time') is not None or raw_a == '00000000':
            wh_candidates.append(c)
    wh = v3.latest_record(wh_candidates)
    if wh:
        h = next((x for x in wh['record'].get('horses', [])
                  if str(x.get('horse_no') or '').zfill(2) == horse_no), None)
        if h:
            emit_wh(rows, plan, wh, 'body_weight_kg', h.get('body_weight_kg'), horse_no)
            if h.get('body_weight_change_status') == 'MEASURED_CHANGE':
                emit_wh(rows, plan, wh, 'body_weight_change_kg', h.get('body_weight_change_kg'), horse_no)
    return rows


v3.base.build_for_plan = build_for_plan

if __name__ == '__main__':
    raise SystemExit(v3.main())
