#!/usr/bin/env python3
from __future__ import annotations
import contextlib, io, json, sys
from pathlib import Path
import keiba_snapshot_gate_check_v4 as v4


def main():
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        rc = v4.main()
    text = capture.getvalue().strip()
    try:
        obj = json.loads(text)
    except Exception:
        print(text)
        return rc
    obj['checker_id'] = 'KEIBA_SNAPSHOT_GATE_CHECK_V5'
    obj['supersedes_checker'] = 'KEIBA_SNAPSHOT_GATE_CHECK_V4'
    obj['semantic_correction'] = '0B11 WH announcement 00000000 has no official timestamp; builder v4 uses LOCAL_ACQUISITION and requires capture_time <= snapshot.'
    out_path = None
    if '--out' in sys.argv:
        i = sys.argv.index('--out')
        if i + 1 < len(sys.argv):
            out_path = Path(sys.argv[i+1])
    final = json.dumps(obj, ensure_ascii=False, indent=2)
    if out_path:
        out_path.write_text(final, encoding='utf-8')
    print(final)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
