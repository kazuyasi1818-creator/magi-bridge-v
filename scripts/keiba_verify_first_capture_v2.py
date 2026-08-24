#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime
from pathlib import Path

REQUIRED_SPECS = {'0B11', '0B14'}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_ts(s: str) -> datetime:
    x = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError('timestamp not offset-aware')
    return x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--clock-file', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    raw_dir = root / 'RAW_APPEND_ONLY' / args.date
    violations = []
    captures = []

    try:
        clock = json.loads(Path(args.clock_file).read_text(encoding='utf-8-sig'))
        run_started_utc = parse_ts(clock['recorded_at_utc'])
    except Exception as e:
        result = {
            'verifier_id': 'KEIBA_VERIFY_FIRST_CAPTURE_V2',
            'date': args.date,
            'status': 'FAIL',
            'violation_count': 1,
            'violations': [{'type': 'CLOCK_AUDIT_INVALID', 'error': str(e)}],
            'validation_oos_opened': False,
        }
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    if not raw_dir.exists():
        violations.append({'type': 'RAW_DATE_DIR_MISSING', 'path': str(raw_dir)})
    else:
        for mp in sorted(raw_dir.glob('*.json')):
            try:
                meta = json.loads(mp.read_text(encoding='utf-8-sig'))
                cap_utc = parse_ts(meta.get('source_capture_time_utc'))
            except Exception:
                # Old/unrelated metadata is ignored unless it belongs to this run.
                continue
            if cap_utc < run_started_utc:
                continue
            if str(meta.get('request_key') or '') != args.date:
                continue

            raw_path = Path(meta.get('raw_file') or '')
            if not raw_path.exists():
                violations.append({'type': 'RAW_FILE_MISSING', 'meta': str(mp), 'raw_file': str(raw_path)})
                continue
            actual = sha256_file(raw_path)
            declared = str(meta.get('raw_file_sha256') or '').lower()
            if actual.lower() != declared:
                violations.append({'type': 'RAW_SHA_MISMATCH', 'meta': str(mp), 'declared': declared, 'actual': actual})
            if meta.get('open_code') != 0:
                violations.append({'type': 'JVRTOpen_NONZERO', 'meta': str(mp), 'code': meta.get('open_code')})
            if meta.get('read_error') not in (None, 0):
                violations.append({'type': 'JVREAD_ERROR', 'meta': str(mp), 'code': meta.get('read_error')})
            try:
                capture_t = parse_ts(meta.get('source_capture_time_jst'))
                utc_t = parse_ts(meta.get('source_capture_time_utc'))
                if abs((capture_t.astimezone(utc_t.tzinfo) - utc_t).total_seconds()) > 2:
                    violations.append({'type': 'CAPTURE_JST_UTC_MISMATCH', 'meta': str(mp)})
            except Exception as e:
                violations.append({'type': 'CAPTURE_TIME_INVALID', 'meta': str(mp), 'error': str(e)})

            record_count = int(meta.get('record_count') or 0)
            records = meta.get('records') or []
            if record_count != len(records):
                violations.append({'type': 'RECORD_COUNT_MISMATCH', 'meta': str(mp), 'declared': record_count, 'actual': len(records)})
            captures.append({
                'capture_id': meta.get('capture_id'),
                'dataspec': meta.get('dataspec'),
                'request_key': meta.get('request_key'),
                'raw_file': str(raw_path),
                'raw_file_sha256': actual,
                'record_count': record_count,
                'record_ids': sorted({r.get('record_id') for r in records if r.get('record_id')}),
                'unsupported_record_ids': sorted({r.get('record_id') for r in records if r.get('record_id') and not r.get('supported_parser', False)}),
                'open_code': meta.get('open_code'),
                'read_error': meta.get('read_error'),
                'source_capture_time_jst': meta.get('source_capture_time_jst'),
                'source_capture_time_utc': meta.get('source_capture_time_utc'),
            })

    by_spec = {spec: 0 for spec in sorted(REQUIRED_SPECS)}
    capture_count_by_spec = {spec: 0 for spec in sorted(REQUIRED_SPECS)}
    for c in captures:
        spec = c.get('dataspec')
        if spec in by_spec:
            by_spec[spec] += int(c.get('record_count') or 0)
            capture_count_by_spec[spec] += 1

    missing_capture_specs = sorted(spec for spec in REQUIRED_SPECS if capture_count_by_spec[spec] == 0)
    if missing_capture_specs:
        violations.append({'type': 'MISSING_REQUIRED_DATASPEC_CAPTURE_IN_CURRENT_RUN', 'dataspecs': missing_capture_specs})

    if violations:
        status, exit_code = 'FAIL', 2
    elif all(by_spec[spec] > 0 for spec in REQUIRED_SPECS):
        status, exit_code = 'PASS', 0
    else:
        status, exit_code = 'WAITING_FOR_REQUIRED_SPEC_RECORDS', 3

    result = {
        'verifier_id': 'KEIBA_VERIFY_FIRST_CAPTURE_V2',
        'root': str(root),
        'date': args.date,
        'run_started_utc': run_started_utc.isoformat(),
        'status': status,
        'capture_count_current_run': len(captures),
        'capture_count_by_dataspec': capture_count_by_spec,
        'record_count_by_dataspec': by_spec,
        'total_records_current_run': sum(by_spec.values()),
        'violation_count': len(violations),
        'violations': violations,
        'captures': captures,
        'meaning': 'Current-run JV-Link plumbing only. PASS requires both 0B11 and 0B14 to contain records in this run. It does not pass Race-time Snapshot Gate v5 or authorize a new DEV trial.',
        'gate_v5_passed': False,
        'validation_oos_opened': False,
        'dev_new_trial_allowed': False,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
