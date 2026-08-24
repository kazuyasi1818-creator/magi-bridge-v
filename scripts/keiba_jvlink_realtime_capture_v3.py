#!/usr/bin/env python3
from __future__ import annotations
import keiba_jvlink_realtime_capture_v1 as base

_BASE_PARSE_RECORD = base.parse_record


def parse_record_v3(raw: bytes) -> dict:
    out = _BASE_PARSE_RECORD(raw)
    rid = out.get('record_id')

    if rid == 'WH':
        out['raw_announcement_code'] = base.afield(raw, 28, 8)
        for h in out.get('horses', []):
            weight_code = str(h.get('raw_weight_code') or '').strip()
            change_code = str(h.get('raw_change_code') or '').strip()
            sign = str(h.get('raw_change_sign') or '').strip()
            if weight_code == '000':
                h['body_weight_kg'] = None
                h['body_weight_status'] = 'SCRATCH'
            elif weight_code == '999':
                h['body_weight_kg'] = None
                h['body_weight_status'] = 'UNMEASURABLE'
            else:
                h['body_weight_status'] = 'MEASURED' if h.get('body_weight_kg') is not None else 'UNKNOWN'

            if change_code == '000':
                h['body_weight_change_kg'] = None
                h['body_weight_change_status'] = 'NO_PREVIOUS_RACE'
            elif change_code == '999':
                h['body_weight_change_kg'] = None
                h['body_weight_change_status'] = 'UNMEASURABLE'
            elif change_code == '':
                h['body_weight_change_kg'] = None
                h['body_weight_change_status'] = 'FIRST_START_OR_SCRATCH'
            elif change_code.isdigit() and 1 <= int(change_code) <= 998:
                d = int(change_code)
                h['body_weight_change_kg'] = -d if sign in {'-', '－'} else d
                h['body_weight_change_status'] = 'MEASURED_CHANGE'
            else:
                h['body_weight_change_kg'] = None
                h['body_weight_change_status'] = 'UNKNOWN'
        out['parser_version'] = 'V3_OFFICIAL_SEMANTICS'

    elif rid == 'AV':
        out.pop('abnormal_code', None)
        code = base.afield(raw, 3, 1)
        out['raw_announcement_code'] = base.afield(raw, 28, 8)
        out['scratch_exclusion_code'] = code
        out['scratch_exclusion_state'] = {'1':'SCRATCH','2':'EXCLUSION'}.get(code, 'UNKNOWN')
        out['parser_version'] = 'V3_OFFICIAL_SEMANTICS'

    elif rid == 'WE':
        raw_announce = base.afield(raw, 26, 8)
        out['raw_announcement_code'] = raw_announce
        out['current_weather_code'] = out.pop('weather_code', None)
        out['current_track_condition_turf'] = out.pop('track_turf_code', None)
        out['current_track_condition_dirt'] = out.pop('track_dirt_code', None)
        out['previous_weather_code'] = base.afield(raw, 38, 1)
        out['previous_track_condition_turf'] = base.afield(raw, 39, 1)
        out['previous_track_condition_dirt'] = base.afield(raw, 40, 1)
        if raw_announce == '00000000':
            out['source_announcement_time_jst'] = None
            out['announcement_time_status'] = 'INITIAL_STATE_NO_OFFICIAL_TIMESTAMP'
        else:
            out['announcement_time_status'] = 'OFFICIAL_ANNOUNCEMENT'
        out['parser_version'] = 'V3_OFFICIAL_SEMANTICS'

    elif rid == 'JC':
        out['raw_announcement_code'] = base.afield(raw, 28, 8)
        out['parser_version'] = 'V3_OFFICIAL_SEMANTICS'

    elif rid == 'TC':
        out['raw_announcement_code'] = base.afield(raw, 28, 8)
        out['parser_version'] = 'V3_OFFICIAL_SEMANTICS'

    elif rid == 'CC':
        out['raw_announcement_code'] = base.afield(raw, 28, 8)
        out['current_distance'] = base.afield(raw, 36, 4)
        out['current_track_code'] = base.afield(raw, 40, 2)
        out['previous_distance'] = base.afield(raw, 42, 4)
        out['previous_track_code'] = base.afield(raw, 46, 2)
        out['reason_code'] = base.afield(raw, 48, 1)
        out['parser_scope'] = 'FULL_OFFICIAL_FORMAT_106'
        out['parser_version'] = 'V3_OFFICIAL_SEMANTICS'

    return out


base.parse_record = parse_record_v3

if __name__ == '__main__':
    raise SystemExit(base.main())
