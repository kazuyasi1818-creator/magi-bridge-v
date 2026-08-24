#!/usr/bin/env python3
from __future__ import annotations
import sys
import keiba_jvlink_realtime_capture_v1 as base


def parse_record_v2(raw: bytes) -> dict:
    out = base.parse_record(raw)
    rid = out.get('record_id')

    if rid == 'WH':
        for h in out.get('horses', []):
            code = str(h.get('raw_change_code') or '').strip()
            sign = str(h.get('raw_change_sign') or '').strip()
            if code == '000':
                h['body_weight_change_kg'] = 0
            elif code.isdigit() and code != '999':
                d = int(code)
                h['body_weight_change_kg'] = -d if sign in {'-', '－'} else d
        out['parser_version'] = 'V2_OFFICIAL_SEMANTICS'

    elif rid == 'AV':
        out.pop('abnormal_code', None)
        code = base.afield(raw, 3, 1)
        out['scratch_exclusion_code'] = code
        out['scratch_exclusion_state'] = {'1':'SCRATCH','2':'EXCLUSION'}.get(code, 'UNKNOWN')
        out['parser_version'] = 'V2_OFFICIAL_SEMANTICS'

    elif rid == 'WE':
        out['current_weather_code'] = out.pop('weather_code', None)
        out['current_track_condition_turf'] = out.pop('track_turf_code', None)
        out['current_track_condition_dirt'] = out.pop('track_dirt_code', None)
        out['previous_weather_code'] = base.afield(raw, 38, 1)
        out['previous_track_condition_turf'] = base.afield(raw, 39, 1)
        out['previous_track_condition_dirt'] = base.afield(raw, 40, 1)
        out['parser_version'] = 'V2_OFFICIAL_SEMANTICS'

    elif rid == 'CC':
        out['current_distance'] = base.afield(raw, 36, 4)
        out['current_track_code'] = base.afield(raw, 40, 2)
        out['previous_distance'] = base.afield(raw, 42, 4)
        out['previous_track_code'] = base.afield(raw, 46, 2)
        out['reason_code'] = base.afield(raw, 48, 1)
        out['parser_scope'] = 'FULL_OFFICIAL_FORMAT_106'
        out['parser_version'] = 'V2_OFFICIAL_SEMANTICS'

    return out


base.parse_record = parse_record_v2

if __name__ == '__main__':
    raise SystemExit(base.main())
