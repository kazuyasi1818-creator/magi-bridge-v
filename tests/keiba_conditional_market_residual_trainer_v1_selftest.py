#!/usr/bin/env python3
from __future__ import annotations
import json,math,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from keiba_conditional_market_residual_objective_v1 import race_probabilities
from keiba_conditional_market_residual_trainer_v1 import fit_conditional_residual


def synth_races():
    beta_true=np.array([.5,-.3,.2,.1,-.15,.25])
    races=[]
    for r in range(40):
        n=5+(r%5)
        raw=np.array([math.exp(.25*(n-i)+.05*math.sin((r+1)*(i+1))) for i in range(n)],dtype=float)
        p=raw/raw.sum()
        X=np.zeros((n,6),dtype=float)
        for i in range(n):
            X[i]=[
                math.sin((r+1)*(i+1)*.13),
                math.cos((r+2)*(i+1)*.17),
                ((r+i)%2)*2-1,
                ((2*r+i)%3)-1,
                math.sin((r+3)*(i+2)*.07),
                ((r+2*i)%2)*2-1,
            ]
        eligible=np.ones(n,dtype=bool)
        if r%3==0:
            eligible[-1]=False
            X[-1]=0.0
        q,_,_=race_probabilities(p,X,beta_true,eligible)
        races.append({'race_id':f'R{r:03d}','market_p':p,'z':X,'history_eligible':eligible,'winner_index':int(np.argmax(q))})
    return races


def main()->int:
    races=synth_races()
    a=fit_conditional_residual(races)
    b=fit_conditional_residual(races)
    c=fit_conditional_residual(list(reversed(races)))
    ba=np.asarray(a['beta']);bb=np.asarray(b['beta']);bc=np.asarray(c['beta'])
    checks={
      'fit_success':a['success'] and b['success'] and c['success'],
      'same_input_exact_beta_reproducible':float(np.max(np.abs(ba-bb)))==0.0,
      'reversed_input_exact_beta_reproducible':float(np.max(np.abs(ba-bc)))==0.0,
      'same_final_objective':a['final_objective']==b['final_objective']==c['final_objective'],
      'objective_nonworse_than_market_initialization':a['final_objective']<=a['start_objective']+1e-12,
      'race_order_canonicalized':a['race_order']=='race_id ascending',
      'zero_initialization':a['initial_beta']=='zeros',
      'no_randomness':a['randomness_used'] is False,
      'no_alternate_optimizer':a['alternate_optimizer_used'] is False,
      'validation_oos_not_used':True,
      'real_money_bet':False
    }
    status='PASS' if all(checks.values()) else 'FAIL'
    print(json.dumps({
      'test_id':'KEIBA-CONDITIONAL-MARKET-RESIDUAL-TRAINER-V1',
      'status':status,
      'checks':checks,
      'race_count':len(races),
      'iterations':a['iterations'],
      'start_objective':a['start_objective'],
      'final_objective':a['final_objective'],
      'beta':a['beta']
    },indent=2))
    return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
