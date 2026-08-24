#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime
import keiba_build_snapshot_provenance_v4 as v4


def dt(s):
    return datetime.fromisoformat(s)


def main():
    plan = {
        'race_id': '2026082901010101',
        'horse_no': '03',
        'snapshot_role': 'LATE',
        'snapshot_time': dt('2026-08-29T12:00:00+09:00'),
    }
    base = {
        'capture_id': 'CAP1', 'dataspec': '0B11',
        'capture_time': dt('2026-08-29T11:55:00+09:00'),
        'raw_sha': 'a' * 64, 'record_sequence': 1,
        'record_id': 'WH', 'announce_time': None,
        'record': {
            'record_id': 'WH', 'race_id': plan['race_id'],
            'raw_announcement_code': '00000000',
            'horses': [{'horse_no': '03', 'body_weight_kg': 480,
                        'body_weight_change_kg': 2,
                        'body_weight_change_status': 'MEASURED_CHANGE'}]
        }
    }
    rows = v4.build_for_plan([base], plan)
    assert len(rows) == 2
    assert all(r['source_time_basis'] == 'LOCAL_ACQUISITION' for r in rows)
    assert all(r['feature_source_time_jst'] == r['source_capture_time_jst'] for r in rows)

    future = {**base, 'capture_id': 'CAP2',
              'capture_time': dt('2026-08-29T12:01:00+09:00'),
              'record': {**base['record'], 'horses': [
                  {'horse_no': '03', 'body_weight_kg': 999,
                   'body_weight_change_kg': 99,
                   'body_weight_change_status': 'MEASURED_CHANGE'}]}}
    rows2 = v4.build_for_plan([base, future], plan)
    assert {r['feature_name']: r['feature_value'] for r in rows2} == {
        'body_weight_kg': 480, 'body_weight_change_kg': 2}

    scratch = {**base, 'capture_id': 'CAP3', 'record': {
        'record_id': 'WH', 'race_id': plan['race_id'],
        'raw_announcement_code': '00000000',
        'horses': [{'horse_no': '03', 'body_weight_kg': None,
                    'body_weight_change_kg': None,
                    'body_weight_change_status': 'NO_PREVIOUS_RACE'}]}}
    assert v4.build_for_plan([scratch], plan) == []
    print('{"status":"PASS","wh_local_acquisition":true,"future_capture_blocked":true,"zero_codes_non_numeric":true}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
