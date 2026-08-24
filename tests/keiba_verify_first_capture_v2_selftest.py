#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / 'scripts' / 'keiba_verify_first_capture_v2.py'
DATE = '20260829'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_capture(root: Path, name: str, spec: str, utc: str, jst: str, n: int) -> None:
    d = root / 'RAW_APPEND_ONLY' / DATE
    d.mkdir(parents=True, exist_ok=True)
    raw = (name + spec).encode()
    raw_path = d / f'{name}.jvraw'
    raw_path.write_bytes(raw)
    records = [{'record_id': 'WH' if spec == '0B11' else 'WE', 'supported_parser': True} for _ in range(n)]
    meta = {
        'capture_id': name,
        'dataspec': spec,
        'request_key': DATE,
        'source_capture_time_jst': jst,
        'source_capture_time_utc': utc,
        'raw_file': str(raw_path),
        'raw_file_sha256': sha256_bytes(raw),
        'record_count': n,
        'open_code': 0,
        'read_error': None,
        'records': records,
    }
    (d / f'{name}.json').write_text(json.dumps(meta), encoding='utf-8')


def run_case(root: Path, clock: Path, label: str) -> tuple[int, dict]:
    out = root / f'{label}.json'
    p = subprocess.run([sys.executable, str(VERIFIER), '--root', str(root), '--date', DATE, '--clock-file', str(clock), '--out', str(out)], capture_output=True, text=True)
    return p.returncode, json.loads(out.read_text(encoding='utf-8'))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = root / 'LOG'; log.mkdir(parents=True)
        clock = log / 'clock.json'
        clock.write_text(json.dumps({'recorded_at_utc': '2026-08-29T05:00:00+00:00'}), encoding='utf-8')

        # Old captures must not satisfy the current run.
        write_capture(root, 'OLD11', '0B11', '2026-08-29T04:00:00+00:00', '2026-08-29T13:00:00+09:00', 2)
        write_capture(root, 'OLD14', '0B14', '2026-08-29T04:00:01+00:00', '2026-08-29T13:00:01+09:00', 2)
        # Current run initially has only 0B14 records and an empty 0B11 capture.
        write_capture(root, 'NEW11_EMPTY', '0B11', '2026-08-29T05:00:01+00:00', '2026-08-29T14:00:01+09:00', 0)
        write_capture(root, 'NEW14', '0B14', '2026-08-29T05:00:02+00:00', '2026-08-29T14:00:02+09:00', 1)
        rc_wait, wait = run_case(root, clock, 'wait')

        # Add a fresh 0B11 record; now both required specs have current-run data.
        write_capture(root, 'NEW11', '0B11', '2026-08-29T05:00:03+00:00', '2026-08-29T14:00:03+09:00', 1)
        rc_pass, passed = run_case(root, clock, 'pass')

        checks = {
            'old_capture_ignored': wait.get('total_records_current_run') == 1,
            'partial_current_run_waits': rc_wait == 3 and wait.get('status') == 'WAITING_FOR_REQUIRED_SPEC_RECORDS',
            'both_specs_current_run_pass': rc_pass == 0 and passed.get('status') == 'PASS',
            'both_specs_counted': passed.get('record_count_by_dataspec') == {'0B11': 1, '0B14': 1},
            'gate_not_auto_passed': passed.get('gate_v5_passed') is False,
            'dev_not_authorized': passed.get('dev_new_trial_allowed') is False,
            'validation_oos_closed': passed.get('validation_oos_opened') is False,
        }
        status = 'PASS' if all(checks.values()) else 'FAIL'
        print(json.dumps({'test_id': 'KEIBA-VERIFY-FIRST-CAPTURE-V2-SELFTEST', 'status': status, 'checks': checks}, ensure_ascii=False, indent=2))
        return 0 if status == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
