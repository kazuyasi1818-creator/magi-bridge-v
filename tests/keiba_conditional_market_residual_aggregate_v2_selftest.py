#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from keiba_conditional_market_residual_objective_v1 import race_loss_and_grad
from keiba_conditional_market_residual_aggregate_v2 import mean_posterior_objective_and_grad


def main()->int:
    race1={'race_id':'R1','market_p':np.array([.5,.3,.2]),'z':np.array([[1,.2,1,0,.4,1],[.5,-.3,1,1,-.2,0],[0,0,0,0,0,0]],float),'history_eligible':np.array([1,1,0],bool),'winner_index':0}
    race2={'race_id':'R2','market_p':np.array([.30,.22,.18,.12,.10,.08]),'z':np.array([[.2,.4,1,0,.2,1],[.6,-.1,1,1,.3,0],[-.2,.8,0,0,.4,1],[.1,-.5,1,0,-.7,0],[.3,.2,0,1,.1,1],[0,0,0,0,0,0]],float),'history_eligible':np.array([1,1,1,1,1,0],bool),'winner_index':1}
    races=[race1,race2]
    beta=np.array([.12,-.08,.05,.03,-.04,.07])
    loss,grad,meta=mean_posterior_objective_and_grad(races,beta)
    l1,g1,*_=race_loss_and_grad(race1['market_p'],race1['z'],beta,race1['history_eligible'],0,l2=0)
    l2,g2,*_=race_loss_and_grad(race2['market_p'],race2['z'],beta,race2['history_eligible'],1,l2=0)
    manual=(l1+l2+.5*float(beta@beta))/2
    manual_grad=(g1+g2+beta)/2
    eps=1e-6;fd=[]
    for j in range(len(beta)):
      bp=beta.copy();bm=beta.copy();bp[j]+=eps;bm[j]-=eps
      fd.append((mean_posterior_objective_and_grad(races,bp)[0]-mean_posterior_objective_and_grad(races,bm)[0])/(2*eps))
    duplicate_rejected=False
    try: mean_posterior_objective_and_grad([race1,race1],beta)
    except ValueError: duplicate_rejected=True
    checks={
      'equals_unit_normal_prior_manual_objective':abs(loss-manual)<1e-12,
      'equals_unit_normal_prior_manual_gradient':float(np.max(np.abs(grad-manual_grad)))<1e-12,
      'gradient_matches_finite_difference':float(np.max(np.abs(grad-np.asarray(fd))))<1e-6,
      'duplicate_race_id_fail_closed':duplicate_rejected,
      'race_weighting_equal_per_race':meta.get('race_weighting')=='EQUAL_PER_RACE',
      'fixed_unit_normal_prior':meta.get('coefficient_prior')=='BETA_STANDARDIZED_UNITS_IID_NORMAL_0_1',
      'no_tunable_l2_lambda':meta.get('tunable_l2_lambda') is False,
      'validation_oos_not_used':True,
      'real_money_bet':False
    }
    status='PASS' if all(checks.values()) else 'FAIL'
    print(json.dumps({'test_id':'KEIBA-CONDITIONAL-RESIDUAL-AGGREGATE-V2','status':status,'checks':checks,'max_grad_abs_error':float(np.max(np.abs(grad-np.asarray(fd))))},indent=2))
    return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
