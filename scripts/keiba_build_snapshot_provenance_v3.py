#!/usr/bin/env python3
from __future__ import annotations
import csv, json
from pathlib import Path
import keiba_build_snapshot_provenance_v1 as base


def latest_complete_capture(captures, dataspec, snap):
    eligible = [c for c in captures if c.get('dataspec') == dataspec and c.get('capture_time') <= snap]
    if not eligible:
        return []
    latest_capture_time = max(c['capture_time'] for c in eligible)
    cap_id = next(c['capture_id'] for c in eligible if c['capture_time'] == latest_capture_time)
    return [c for c in eligible if c.get('capture_id') == cap_id]


def event_sort_key(c):
    # Official timestamped events outrank initial-state 00000000 records.
    # Within same class use record sequence for deterministic order.
    if c.get('announce_time') is not None:
        return (1, c['announce_time'], int(c.get('record_sequence') or 0))
    return (0, c['capture_time'], int(c.get('record_sequence') or 0))


def latest_record(items):
    if not items:
        return None
    return max(items, key=event_sort_key)


def emit(rows, plan, c, feature_name, feature_value, source_kind, horse_no=None):
    if feature_value is None or str(feature_value).strip() == '':
        return
    announce = c.get('announce_time')
    raw_announce = str(c.get('record', {}).get('raw_announcement_code') or '').strip()
    if announce is not None:
        source_time = announce
        basis = 'OFFICIAL_ANNOUNCEMENT'
    elif c.get('record_id') == 'WE' and raw_announce == '00000000':
        source_time = c['capture_time']
        basis = 'LOCAL_ACQUISITION'
    else:
        # No trustworthy time: fail closed by omitting the feature.
        return
    rows.append({
        'race_id': plan['race_id'],
        'horse_no': horse_no or plan['horse_no'],
        'snapshot_role': plan['snapshot_role'],
        'prediction_snapshot_time_jst': plan['snapshot_time'].isoformat(),
        'feature_name': feature_name,
        'feature_value': feature_value,
        'feature_source_time_jst': source_time.isoformat(),
        'source_capture_time_jst': c['capture_time'].isoformat(),
        'source_time_basis': basis,
        'source_kind': source_kind,
        'source_file_sha256': c['raw_sha'],
        'source_row_id': f"{c['capture_id']}:{c['record_sequence']}:{horse_no or plan['horse_no']}",
    })


def build_for_plan(captures, plan):
    rows = []
    race_id = plan['race_id']
    horse_no = plan['horse_no']
    scope_key = race_id[:14]
    b11 = latest_complete_capture(captures, '0B11', plan['snapshot_time'])
    b14 = latest_complete_capture(captures, '0B14', plan['snapshot_time'])

    wh = latest_record([c for c in b11 if c.get('record_id') == 'WH' and str(c['record'].get('race_id') or '') == race_id and (c.get('announce_time') is not None)])
    if wh:
        h = next((x for x in wh['record'].get('horses', []) if str(x.get('horse_no') or '').zfill(2) == horse_no), None)
        if h:
            emit(rows, plan, wh, 'body_weight_kg', h.get('body_weight_kg'), 'JRA_VAN_0B11_WH')
            # Only emit a numeric difference when the official code represents 001-998.
            if h.get('body_weight_change_status') == 'MEASURED_CHANGE':
                emit(rows, plan, wh, 'body_weight_change_kg', h.get('body_weight_change_kg'), 'JRA_VAN_0B11_WH')

    av = latest_record([c for c in b14 if c.get('record_id') == 'AV' and str(c['record'].get('race_id') or '') == race_id and str(c['record'].get('horse_no') or '').zfill(2) == horse_no and c.get('announce_time') is not None])
    if av:
        emit(rows, plan, av, 'scratch_exclusion_code', av['record'].get('scratch_exclusion_code'), 'JRA_VAN_0B14_AV')

    jc = latest_record([c for c in b14 if c.get('record_id') == 'JC' and str(c['record'].get('race_id') or '') == race_id and str(c['record'].get('horse_no') or '').zfill(2) == horse_no and c.get('announce_time') is not None])
    if jc:
        emit(rows, plan, jc, 'current_jockey_code', jc['record'].get('current_jockey_code'), 'JRA_VAN_0B14_JC')
        emit(rows, plan, jc, 'current_jockey_name', jc['record'].get('current_jockey_name'), 'JRA_VAN_0B14_JC')
        emit(rows, plan, jc, 'current_carried_weight_x10', jc['record'].get('current_carried_weight_x10'), 'JRA_VAN_0B14_JC')

    tc = latest_record([c for c in b14 if c.get('record_id') == 'TC' and str(c['record'].get('race_id') or '') == race_id and c.get('announce_time') is not None])
    if tc:
        emit(rows, plan, tc, 'current_post_time', tc['record'].get('current_post_time_hhmm'), 'JRA_VAN_0B14_TC')

    cc = latest_record([c for c in b14 if c.get('record_id') == 'CC' and str(c['record'].get('race_id') or '') == race_id and c.get('announce_time') is not None])
    if cc:
        emit(rows, plan, cc, 'current_distance', cc['record'].get('current_distance'), 'JRA_VAN_0B14_CC')
        emit(rows, plan, cc, 'current_track_code', cc['record'].get('current_track_code'), 'JRA_VAN_0B14_CC')

    we_candidates = []
    for c in b14:
        if c.get('record_id') != 'WE' or str(c['record'].get('scope_key') or '') != scope_key:
            continue
        raw_a = str(c['record'].get('raw_announcement_code') or '').strip()
        if c.get('announce_time') is not None or raw_a == '00000000':
            we_candidates.append(c)
    we = latest_record(we_candidates)
    if we:
        emit(rows, plan, we, 'weather', we['record'].get('current_weather_code'), 'JRA_VAN_0B14_WE')
        emit(rows, plan, we, 'track_condition_turf', we['record'].get('current_track_condition_turf'), 'JRA_VAN_0B14_WE')
        emit(rows, plan, we, 'track_condition_dirt', we['record'].get('current_track_condition_dirt'), 'JRA_VAN_0B14_WE')
    return rows


base.build_for_plan = build_for_plan

if __name__ == '__main__':
    raise SystemExit(base.main())
