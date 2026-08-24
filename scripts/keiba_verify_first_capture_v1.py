#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_ts(s: str):
    x = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError('timestamp not offset-aware')
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    raw_dir = root / 'RAW_APPEND_ONLY' / args.date
    violations = []
    captures = []

    if not raw_dir.exists():
        violations.append({'type': 'RAW_DATE_DIR_MISSING', 'path': str(raw_dir)})
    else:
        meta_files = sorted(raw_dir.glob('*.json'))
        if not meta_files:
            violations.append({'type': 'NO_CAPTURE_METADATA'})
        for mp in meta_files:
            try:
                meta = json.loads(mp.read_text(encoding='utf-8-sig'))
            except Exception as e:
                violations.append({'type': 'META_PARSE_ERROR', 'file': str(mp), 'error': str(e)})
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
            unsupported = sorted({r.get('record_id') for r in records if not r.get('supported_parser', False)})
            captures.append({
                'capture_id': meta.get('capture_id'),
                'dataspec': meta.get('dataspec'),
                'request_key': meta.get('request_key'),
                'raw_file': str(raw_path),
                'raw_file_sha256': actual,
                'record_count': record_count,
                'record_ids': sorted({r.get('record_id') for r in records if r.get('record_id')}),
                'unsupported_record_ids': unsupported,
                'open_code': meta.get('open_code'),
                'read_error': meta.get('read_error'),
                'source_capture_time_jst': meta.get('source_capture_time_jst'),
            })

    by_spec = {}
    for c in captures:
        by_spec.setdefault(c.get('dataspec'), 0)
        by_spec[c.get('dataspec')] += c.get('record_count', 0)

    has_required_specs = any(c.get('dataspec') == '0B11' for c in captures) and any(c.get('dataspec') == '0B14' for c in captures)
    usable_records = sum(c.get('record_count', 0) for c in captures)
    if not has_required_specs and not violations:
        violations.append({'type': 'MISSING_REQUIRED_DATASPEC_CAPTURE'})

    if violations:
        status, exit_code = 'FAIL', 2
    elif usable_records == 0:
        status, exit_code = 'WAITING_FOR_REALTIME_RECORDS', 3
    else:
        status, exit_code = 'PASS', 0

    result = {
        'verifier_id': 'KEIBA_VERIFY_FIRST_CAPTURE_V1',
        'root': str(root),
        'date': args.date,
        'status': status,
        'capture_count': len(captures),
        'record_count_by_dataspec': by_spec,
        'total_records': usable_records,
        'violation_count': len(violations),
        'violations': violations,
        'captures': captures,
        'meaning': 'Plumbing/timing integrity only. PASS does not authorize DEV v6 until real snapshot provenance is built and Race-time Snapshot Gate V2 also passes.',
        'validation_oos_opened': False,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
