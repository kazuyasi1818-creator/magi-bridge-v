#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import copy, hashlib, json, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent
CHECKER = ROOT/'T009R_expected_manifest_selfcheck_v1_1.py'

def H(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def baseline():
    return {
        'prereg_id':'T009R-CONFIRM-001',
        'input_sha256':H('input'),
        'race_manifest_sha256':H('race'),
        'split_manifest_sha256':H('split'),
        'partitions':{
            p:{
                'row_identity_sha256':H('row-'+p),
                'race_set_sha256':H('race-'+p),
                'subgroup_membership_sha256':H('sub-'+p),
            } for p in ('FULL','A','B')
        },
        'feasibility':{
            'distinct_race_dates_total':12,
            'partitions':{
                'FULL':{'distinct_race_dates':12,'race_count':240,'primary_subgroup_rows':600},
                'A':{'distinct_race_dates':6,'race_count':120,'primary_subgroup_rows':300},
                'B':{'distinct_race_dates':6,'race_count':120,'primary_subgroup_rows':300},
            }
        }
    }

def run_case(td: Path, name: str, payload, *, raw=False):
    inp=td/f'{name}.json'; out=td/f'{name}.out.json'
    if raw:
        inp.write_text(str(payload),encoding='utf-8')
    else:
        inp.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    cp=subprocess.run([sys.executable,str(CHECKER),str(inp),'--out',str(out)],capture_output=True,text=True)
    obj=None
    if out.exists():
        try: obj=json.loads(out.read_text(encoding='utf-8'))
        except Exception: pass
    return {'id':name,'exit_code':cp.returncode,'out_exists':out.exists(),'result':obj,'stdout':cp.stdout,'stderr':cp.stderr}

def has_error(c, err):
    return any(e.get('error')==err for e in (c['result'] or {}).get('errors',[]))

def main():
    with tempfile.TemporaryDirectory() as tmp:
        td=Path(tmp)
        cases=[]
        b=baseline()
        cases.append(run_case(td,'valid_manifest',b))

        x=copy.deepcopy(b); x['feasibility']['partitions']['FULL']['race_count']=241
        cases.append(run_case(td,'FULL_race_count_not_A_plus_B',x))
        x=copy.deepcopy(b); x['feasibility']['partitions']['FULL']['primary_subgroup_rows']=601
        cases.append(run_case(td,'FULL_subgroup_not_A_plus_B',x))
        x=copy.deepcopy(b); x['feasibility']['partitions']['FULL']['distinct_race_dates']=13
        cases.append(run_case(td,'FULL_dates_not_A_plus_B',x))
        x=copy.deepcopy(b); x['feasibility']['distinct_race_dates_total']=13
        cases.append(run_case(td,'total_dates_not_A_plus_B',x))

        cases.append(run_case(td,'top_level_list',[]))
        cases.append(run_case(td,'top_level_number',123))
        cases.append(run_case(td,'top_level_string','bad'))
        cases.append(run_case(td,'top_level_null',None))
        x=copy.deepcopy(b); x['partitions']=[]
        cases.append(run_case(td,'partitions_list',x))
        x=copy.deepcopy(b); x['feasibility']=None
        cases.append(run_case(td,'feasibility_null',x))
        cases.append(run_case(td,'invalid_json','{not valid json',raw=True))

        expect={
          'valid_manifest': lambda c: c['exit_code']==0 and c['out_exists'] and c['result'].get('status')=='PASS',
          'FULL_race_count_not_A_plus_B': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'FULL_NOT_A_PLUS_B'),
          'FULL_subgroup_not_A_plus_B': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'FULL_NOT_A_PLUS_B'),
          'FULL_dates_not_A_plus_B': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'FULL_NOT_A_PLUS_B'),
          'total_dates_not_A_plus_B': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'TOTAL_DATES_NOT_A_PLUS_B'),
          'top_level_list': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'not_object'),
          'top_level_number': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'not_object'),
          'top_level_string': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'not_object'),
          'top_level_null': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'not_object'),
          'partitions_list': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'invalid_partitions'),
          'feasibility_null': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'not_object'),
          'invalid_json': lambda c: c['exit_code']==2 and c['out_exists'] and has_error(c,'invalid_json'),
        }
        summary=[]; all_ok=True
        for c in cases:
            ok=expect[c['id']](c); all_ok &= ok
            print(f"[{'PASS' if ok else 'FAIL'}] {c['id']} exit={c['exit_code']} out={c['out_exists']} status={(c['result'] or {}).get('status')}")
            summary.append({
                'id':c['id'],'test_pass':ok,'exit_code':c['exit_code'],'out_exists':c['out_exists'],
                'status':(c['result'] or {}).get('status'),
                'error_codes':[e.get('error') for e in (c['result'] or {}).get('errors',[])]
            })
        report={
          'suite_id':'T009R_EXPECTED_MANIFEST_SELFCHECK_V1_1_ADVERSARIAL',
          'validator_sha256':hashlib.sha256(CHECKER.read_bytes()).hexdigest(),
          'case_count':len(summary),'all_passed':all_ok,'cases':summary,
          'required_user_cases':{
             'top_level_list_exit2_json': next(x for x in summary if x['id']=='top_level_list')['test_pass'],
             'top_level_number_string_null_exit2_json': all(next(x for x in summary if x['id']==i)['test_pass'] for i in ('top_level_number','top_level_string','top_level_null')),
             'partitions_list_exit2': next(x for x in summary if x['id']=='partitions_list')['test_pass'],
             'feasibility_null_exit2': next(x for x in summary if x['id']=='feasibility_null')['test_pass'],
          }
        }
        out=ROOT/'T009R_expected_manifest_selfcheck_v1_1_selftest_report.json'
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
        raise SystemExit(0 if all_ok else 1)

if __name__=='__main__': main()
