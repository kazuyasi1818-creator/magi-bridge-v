#!/usr/bin/env python3
from __future__ import annotations
import keiba_build_snapshot_provenance_v1 as base


def latest_complete_capture(captures, dataspec, snap):
    eligible = [c for c in captures if c.get('dataspec') == dataspec and c.get('capture_time') <= snap]
    if not eligible:
        return []
    latest = max(eligible, key=lambda c: c['capture_time'])
    cap_id = latest.get('capture_id')
    return [c for c in eligible if c.get('capture_id') == cap_id and c.get('announce_time') is not None and c.get('announce_time') <= snap]


def latest_record(items):
    if not items:
        return None
    return max(items, key=lambda c: (c['announce_time'], int(c.get('record_sequence') or 0)))


def build_for_plan_v2(captures, plan):
    rows = []
    race_id = plan['race_id']
    horse_no = plan['horse_no']
    scope_key = race_id[:14]

    # 0B11 and 0B14 are date-unit bulk feeds. Snapshot state is reconstructed from
    # the latest COMPLETE capture available at/before the prediction snapshot.
    # This prevents a withdrawn 0B14 event from being carried forward from an older poll.
    b11 = latest_complete_capture(captures, '0B11', plan['snapshot_time'])
    b14 = latest_complete_capture(captures, '0B14', plan['snapshot_time'])

    wh = latest_record([c for c in b11 if c.get('record_id') == 'WH' and str(c['record'].get('race_id') or '') == race_id])
    if wh:
        h = next((x for x in wh['record'].get('horses', []) if str(x.get('horse_no') or '').zfill(2) == horse_no), None)
        if h:
            base.emit(rows, plan, wh, 'body_weight_kg', h.get('body_weight_kg'), 'JRA_VAN_0B11_WH')
            base.emit(rows, plan, wh, 'body_weight_change_kg', h.get('body_weight_change_kg'), 'JRA_VAN_0B11_WH')

    av = latest_record([c for c in b14 if c.get('record_id') == 'AV' and str(c['record'].get('race_id') or '') == race_id and str(c['record'].get('horse_no') or '').zfill(2) == horse_no])
    if av:
        base.emit(rows, plan, av, 'scratch_exclusion_code', av['record'].get('scratch_exclusion_code'), 'JRA_VAN_0B14_AV')

    jc = latest_record([c for c in b14 if c.get('record_id') == 'JC' and str(c['record'].get('race_id') or '') == race_id and str(c['record'].get('horse_no') or '').zfill(2) == horse_no])
    if jc:
        base.emit(rows, plan, jc, 'current_jockey_code', jc['record'].get('current_jockey_code'), 'JRA_VAN_0B14_JC')
        base.emit(rows, plan, jc, 'current_jockey_name', jc['record'].get('current_jockey_name'), 'JRA_VAN_0B14_JC')
        base.emit(rows, plan, jc, 'current_carried_weight_x10', jc['record'].get('current_carried_weight_x10'), 'JRA_VAN_0B14_JC')

    tc = latest_record([c for c in b14 if c.get('record_id') == 'TC' and str(c['record'].get('race_id') or '') == race_id])
    if tc:
        base.emit(rows, plan, tc, 'current_post_time', tc['record'].get('current_post_time_hhmm'), 'JRA_VAN_0B14_TC')

    cc = latest_record([c for c in b14 if c.get('record_id') == 'CC' and str(c['record'].get('race_id') or '') == race_id])
    if cc:
        base.emit(rows, plan, cc, 'current_distance', cc['record'].get('current_distance'), 'JRA_VAN_0B14_CC')
        base.emit(rows, plan, cc, 'current_track_code', cc['record'].get('current_track_code'), 'JRA_VAN_0B14_CC')

    we = latest_record([c for c in b14 if c.get('record_id') == 'WE' and str(c['record'].get('scope_key') or '') == scope_key])
    if we:
        base.emit(rows, plan, we, 'weather', we['record'].get('current_weather_code'), 'JRA_VAN_0B14_WE')
        base.emit(rows, plan, we, 'track_condition_turf', we['record'].get('current_track_condition_turf'), 'JRA_VAN_0B14_WE')
        base.emit(rows, plan, we, 'track_condition_dirt', we['record'].get('current_track_condition_dirt'), 'JRA_VAN_0B14_WE')

    return rows


base.build_for_plan = build_for_plan_v2

if __name__ == '__main__':
    raise SystemExit(base.main())
