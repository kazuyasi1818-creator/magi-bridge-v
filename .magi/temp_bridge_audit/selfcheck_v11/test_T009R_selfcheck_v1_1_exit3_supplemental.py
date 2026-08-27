#!/usr/bin/env python3
from __future__ import annotations
import contextlib, importlib.util, io, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKER = ROOT/'T009R_expected_manifest_selfcheck_v1_1.py'

def loadmod():
    spec = importlib.util.spec_from_file_location('t009r_sc_v11', CHECKER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

def valid_manifest():
    import hashlib
    H=lambda s: hashlib.sha256(s.encode()).hexdigest()
    return {
      'prereg_id':'T009R-CONFIRM-001','input_sha256':H('input'),'race_manifest_sha256':H('race'),'split_manifest_sha256':H('split'),
      'partitions':{p:{'row_identity_sha256':H('row-'+p),'race_set_sha256':H('race-'+p),'subgroup_membership_sha256':H('sub-'+p)} for p in ('FULL','A','B')},
      'feasibility':{'distinct_race_dates_total':12,'partitions':{
        'FULL':{'distinct_race_dates':12,'race_count':240,'primary_subgroup_rows':600},
        'A':{'distinct_race_dates':6,'race_count':120,'primary_subgroup_rows':300},
        'B':{'distinct_race_dates':6,'race_count':120,'primary_subgroup_rows':300}}}
    }

def test_internal_exception(td: Path):
    mod=loadmod(); inp=td/'valid_for_internal.json'; out=td/'internal.out.json'
    inp.write_text(json.dumps(valid_manifest()),encoding='utf-8')
    def boom(*a,**k): raise TypeError('synthetic-post-parse-internal-exception')
    mod.validate_manifest=boom
    old=sys.argv[:]; sys.argv=[str(CHECKER),str(inp),'--out',str(out)]; code=None
    try:
      try: mod.main()
      except SystemExit as e: code=int(e.code)
    finally: sys.argv=old
    obj=json.loads(out.read_text(encoding='utf-8')) if out.exists() else None
    ok=(code==3 and out.exists() and obj and obj.get('status')=='PROTOCOL_INVALID' and obj.get('exit_code')==3 and any(e.get('error')=='internal_exception' and e.get('exception_type')=='TypeError' for e in obj.get('errors',[])))
    return {'id':'exit3_internal_exception_json','test_pass':ok,'exit_code':code,'out_exists':out.exists(),'status':obj.get('status') if obj else None}

def test_stderr_fallback(td: Path):
    mod=loadmod(); inp=td/'valid_for_stderr.json'; inp.write_text(json.dumps(valid_manifest()),encoding='utf-8')
    def boom(*a,**k): raise RuntimeError('synthetic-internal-before-output')
    mod.validate_manifest=boom
    out=Path('/proc/1/t009r_should_not_write/reconciliation.json')
    old=sys.argv[:]; sys.argv=[str(CHECKER),str(inp),'--out',str(out)]; err=io.StringIO(); code=None
    try:
      try:
        with contextlib.redirect_stderr(err): mod.main()
      except SystemExit as e: code=int(e.code)
    finally: sys.argv=old
    try: parsed=json.loads(err.getvalue())
    except Exception: parsed=None
    ok=(code==3 and parsed is not None and parsed.get('status')=='PROTOCOL_INVALID' and parsed.get('exit_code')==3 and 'evidence_write_failure' in parsed and any(e.get('error')=='internal_exception' for e in parsed.get('errors',[])))
    return {'id':'exit3_unwritable_out_stderr_fallback','test_pass':ok,'exit_code':code,'stderr_json':parsed is not None,'status':parsed.get('status') if parsed else None,'has_evidence_write_failure':bool(parsed and 'evidence_write_failure' in parsed)}

def test_invalid_utf8(td: Path):
    inp=td/'invalid_utf8.json'; out=td/'invalid_utf8.out.json'; inp.write_bytes(b'{"x":"\xff\xfe"}')
    cp=subprocess.run([sys.executable,str(CHECKER),str(inp),'--out',str(out)],capture_output=True,text=True)
    obj=json.loads(out.read_text(encoding='utf-8')) if out.exists() else None
    ok=(cp.returncode==2 and out.exists() and obj and obj.get('status')=='PROTOCOL_INVALID' and obj.get('exit_code')==2 and any(e.get('error')=='invalid_json' for e in obj.get('errors',[])))
    return {'id':'invalid_utf8_fail_closed','test_pass':ok,'exit_code':cp.returncode,'out_exists':out.exists(),'status':obj.get('status') if obj else None,'error_codes':[e.get('error') for e in obj.get('errors',[])] if obj else []}

def main():
    import hashlib
    with tempfile.TemporaryDirectory() as d:
      td=Path(d); cases=[test_internal_exception(td),test_stderr_fallback(td),test_invalid_utf8(td)]
    all_ok=all(c['test_pass'] for c in cases)
    report={'suite_id':'T009R_SELFCHECK_V1_1_EXIT3_SUPPLEMENTAL','checker_sha256':hashlib.sha256(CHECKER.read_bytes()).hexdigest(),'case_count':len(cases),'all_passed':all_ok,'cases':cases}
    out=ROOT/'T009R_selfcheck_v1_1_exit3_supplemental_report.json'; out.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    for c in cases: print(f"[{'PASS' if c['test_pass'] else 'FAIL'}] {c['id']} exit={c['exit_code']} status={c.get('status')}")
    print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
    raise SystemExit(0 if all_ok else 1)
if __name__=='__main__': main()
