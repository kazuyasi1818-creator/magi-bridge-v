#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    raw_dir = root / 'RAW_APPEND_ONLY' / args.date
    captures = []
    if raw_dir.exists():
        for mp in sorted(raw_dir.glob('*.json')):
            try:
                m = json.loads(mp.read_text(encoding='utf-8-sig'))
            except Exception:
                continue
            records = m.get('records') or []
            captures.append({
                'capture_id': m.get('capture_id'),
                'dataspec': m.get('dataspec'),
                'request_key': m.get('request_key'),
                'source_capture_time_jst': m.get('source_capture_time_jst'),
                'source_capture_time_utc': m.get('source_capture_time_utc'),
                'raw_file_name': Path(str(m.get('raw_file') or '')).name,
                'raw_file_sha256': m.get('raw_file_sha256'),
                'record_count': m.get('record_count'),
                'record_ids': sorted({r.get('record_id') for r in records if r.get('record_id')}),
                'unsupported_record_ids': sorted({r.get('record_id') for r in records if r.get('record_id') and not r.get('supported_parser', False)}),
                'open_code': m.get('open_code'),
                'read_error': m.get('read_error'),
            })

    log_dir = root / 'LOG'
    clock_summary = None
    clocks = sorted(log_dir.glob('clock_audit_*.json')) if log_dir.exists() else []
    if clocks:
        try:
            c = json.loads(clocks[-1].read_text(encoding='utf-8-sig'))
            keys = [
                'recorded_at_local', 'recorded_at_utc', 'timezone_id', 'utc_offset', 'date_key',
                'gate_contract', 'provenance_builder', 'gate_checker', 'verifier', 'handoff_maker'
            ]
            clock_summary = {k: c.get(k) for k in keys}
            clock_summary['clock_file_sha256'] = sha256_file(clocks[-1])
        except Exception:
            pass

    verifier_summary = None
    vr = sorted(log_dir.glob('first_capture_verify_*.json')) if log_dir.exists() else []
    if vr:
        try:
            v = json.loads(vr[-1].read_text(encoding='utf-8-sig'))
            keys = [
                'verifier_id', 'date', 'status', 'run_started_utc',
                'capture_count_current_run', 'capture_count_by_dataspec',
                'record_count_by_dataspec', 'total_records_current_run',
                'violation_count', 'violations', 'gate_v5_passed',
                'validation_oos_opened', 'dev_new_trial_allowed'
            ]
            verifier_summary = {k: v.get(k) for k in keys}
            verifier_summary['verifier_file_sha256'] = sha256_file(vr[-1])
        except Exception:
            pass

    lineage_ok = bool(clock_summary) and all([
        clock_summary.get('gate_contract') == 'KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5',
        clock_summary.get('provenance_builder') == 'keiba_build_snapshot_provenance_v4.py',
        clock_summary.get('gate_checker') == 'keiba_snapshot_gate_check_v5.py',
        clock_summary.get('verifier') == 'keiba_verify_first_capture_v2.py',
        clock_summary.get('handoff_maker') == 'keiba_make_capture_handoff_v2.py',
    ])

    out = {
        'handoff_id': 'KEIBA_REAL_CAPTURE_REDACTED_HANDOFF_V2',
        'created_at': datetime.now().astimezone().isoformat(),
        'date': args.date,
        'scope': 'Metadata/hashes only. Raw JV-Data record bytes and parsed feature values are intentionally excluded.',
        'gate_v5_lineage_verified': lineage_ok,
        'captures': captures,
        'clock_audit': clock_summary,
        'verifier': verifier_summary,
        'raw_jvdata_included': False,
        'parsed_feature_values_included': False,
        'model_executed': False,
        'validation_oos_opened': False,
        'dev_v6_allowed': False,
        'next_action': 'Provide this handoff JSON for audit. Keep RAW_APPEND_ONLY locally. Gate v5 is not passed until real snapshot provenance is built and reviewed.'
    }
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(p))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
