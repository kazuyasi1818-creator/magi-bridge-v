#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAGGER = ROOT / "scripts" / "orepro_shadow_weakness_tagger_v1.py"

FIELDS = [
    "race_id","is_newcomer_race","field_size","distance","history_coverage",
    "market_top1_p","market_gap","market_norm_entropy"
]


def run(rows):
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); inp=td/'in.csv'; out=td/'out.json'
        with inp.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
        p=subprocess.run([sys.executable,str(TAGGER),str(inp),'--out',str(out)],text=True,capture_output=True)
        if p.returncode != 0:
            raise AssertionError(p.stdout+'\n'+p.stderr)
        return json.loads(out.read_text(encoding='utf-8'))


def main():
    rows=[
        {"race_id":"R1","is_newcomer_race":"false","field_size":"10","distance":"2000","history_coverage":"0.90","market_top1_p":"0.18","market_gap":"0.07","market_norm_entropy":"0.82"},
        {"race_id":"R2","is_newcomer_race":"false","field_size":"16","distance":"1600","history_coverage":"1.00","market_top1_p":"0.31","market_gap":"0.15","market_norm_entropy":"0.75"},
        {"race_id":"R3","is_newcomer_race":"true","field_size":"12","distance":"1800","history_coverage":"0.10","market_top1_p":"0.25","market_gap":"0.08","market_norm_entropy":"0.83"},
    ]
    o=run(rows)
    r={x['race_id']:x for x in o['rows']}
    expected={"SMALL_FIELD_LE_10","DIST_1800_2199","HISTORY_COV_0_80_0_949","MARKET_TOP1_P_LT_0_20","MARKET_GAP_0_05_0_10","MARKET_NORM_ENTROPY_0_80_0_85"}
    assert set(r['R1']['shadow_tags']) == expected
    assert r['R2']['shadow_tags'] == []
    assert r['R3']['shadow_tags'] == ['NEWCOMER_RACE_EXCLUDED']
    for x in o['rows']:
        assert x['selection_effect']=='NONE'
        assert x['prediction_effect']=='NONE'
        assert x['ticket_effect']=='NONE'
        assert x['stake_effect']=='NONE'
    proof={
        "test_id":"OREPRO-SHADOW-WEAKNESS-TAGGER-V1-SYNTHETIC",
        "status":"PASS",
        "checks":{
            "all_diagnostic_tags_fire_on_boundary_case":True,
            "clean_case_has_no_tags":True,
            "newcomer_is_scope_excluded":True,
            "diagnostic_tags_cannot_change_selection_prediction_ticket_or_stake":True
        },
        "validation_opened":False,
        "oos_opened":False
    }
    print(json.dumps(proof,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
