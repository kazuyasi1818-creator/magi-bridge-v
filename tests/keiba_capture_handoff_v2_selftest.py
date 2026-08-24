#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'keiba_make_capture_handoff_v2.py'


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        date = '20260829'
        raw_dir = root / 'RAW_APPEND_ONLY' / date
        log_dir = root / 'LOG'
        raw_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        cap = {
            'capture_id': 'SYNTH_CAP',
            'dataspec': '0B11',
            'request_key': date,
            'source_capture_time_jst': '2026-08-29T14:00:00+09:00',
            'source_capture_time_utc': '2026-08-29T05:00:00+00:00',
            'raw_file': str(raw_dir / 'SYNTH_CAP.jvraw'),
            'raw_file_sha256': 'a' * 64,
            'record_count': 1,
            'open_code': 0,
            'read_error': None,
            'records': [{
                'record_id': 'WH',
                'supported_parser': True,
                'horse_name': 'DO_NOT_LEAK_HORSE_NAME',
                'body_weight_kg': 488,
            }],
        }
        (raw_dir / 'SYNTH_CAP.json').write_text(json.dumps(cap), encoding='utf-8')
        (raw_dir / 'SYNTH_CAP.jvraw').write_bytes(b'SYNTHETIC')

        clock = {
            'recorded_at_local': '2026-08-29T14:00:01+09:00',
            'recorded_at_utc': '2026-08-29T05:00:01+00:00',
            'timezone_id': 'Tokyo Standard Time',
            'utc_offset': '+09:00',
            'computer_name': 'REDACTED',
            'date_key': date,
            'gate_contract': 'KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5',
            'provenance_builder': 'keiba_build_snapshot_provenance_v4.py',
            'gate_checker': 'keiba_snapshot_gate_check_v5.py',
            'verifier': 'keiba_verify_first_capture_v2.py',
            'handoff_maker': 'keiba_make_capture_handoff_v2.py',
        }
        (log_dir / 'clock_audit_20260829_140001.json').write_text(json.dumps(clock), encoding='utf-8')
        verify = {
            'verifier_id': 'KEIBA_VERIFY_FIRST_CAPTURE_V2',
            'date': date,
            'status': 'PASS',
            'run_started_utc': '2026-08-29T04:59:59+00:00',
            'capture_count_current_run': 2,
            'capture_count_by_dataspec': {'0B11': 1, '0B14': 1},
            'record_count_by_dataspec': {'0B11': 1, '0B14': 1},
            'total_records_current_run': 2,
            'violation_count': 0,
            'violations': [],
            'gate_v5_passed': False,
            'validation_oos_opened': False,
            'dev_new_trial_allowed': False,
        }
        (log_dir / 'first_capture_verify_20260829_140002.json').write_text(json.dumps(verify), encoding='utf-8')

        out = root / 'HANDOFF.json'
        subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), '--date', date, '--out', str(out)], check=True)
        obj = json.loads(out.read_text(encoding='utf-8'))
        text = out.read_text(encoding='utf-8')

        checks = {
            'handoff_v2': obj.get('handoff_id') == 'KEIBA_REAL_CAPTURE_REDACTED_HANDOFF_V2',
            'gate_v5_lineage_verified': obj.get('gate_v5_lineage_verified') is True,
            'contract_v5_retained': obj.get('clock_audit', {}).get('gate_contract') == 'KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5',
            'builder_v4_retained': obj.get('clock_audit', {}).get('provenance_builder') == 'keiba_build_snapshot_provenance_v4.py',
            'checker_v5_retained': obj.get('clock_audit', {}).get('gate_checker') == 'keiba_snapshot_gate_check_v5.py',
            'verifier_v2_retained': obj.get('clock_audit', {}).get('verifier') == 'keiba_verify_first_capture_v2.py',
            'handoff_v2_retained': obj.get('clock_audit', {}).get('handoff_maker') == 'keiba_make_capture_handoff_v2.py',
            'verifier_current_run_metrics_retained': obj.get('verifier', {}).get('total_records_current_run') == 2,
            'raw_bytes_not_included': obj.get('raw_jvdata_included') is False,
            'parsed_values_not_included': obj.get('parsed_feature_values_included') is False,
            'horse_name_not_leaked': 'DO_NOT_LEAK_HORSE_NAME' not in text,
            'body_weight_not_leaked': '488' not in text,
            'hash_retained': obj.get('captures', [{}])[0].get('raw_file_sha256') == 'a' * 64,
            'record_id_retained': obj.get('captures', [{}])[0].get('record_ids') == ['WH'],
        }
        status = 'PASS' if all(checks.values()) else 'FAIL'
        result = {'test_id': 'KEIBA-CAPTURE-HANDOFF-V2-SELFTEST', 'status': status, 'checks': checks}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if status == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
