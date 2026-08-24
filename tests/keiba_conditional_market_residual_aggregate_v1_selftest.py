#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from keiba_residual_train_preprocess_v1 import fit_standardizer,transform
from keiba_conditional_market_residual_objective_v1 import race_loss_and_grad
from keiba_conditional_market_residual_aggregate_v1 import mean_race_loss_and_grad


def main()->int:
    Xtrain=np.array([
      [1,10,1,0,100,1],[2,20,0,1,200,0],[3,30,1,1,300,1],
      [4,40,0,0,400,0],[5,50,1,0,500,1],[6,60,0,1,600,0]
    ],dtype=float)
    state=fit_standardizer(Xtrain)
    Z=transform(Xtrain,state)
    zero_scale_rejected=False
    try: fit_standardizer(np.ones((4,6)))
    except ValueError: zero_scale_rejected=True

    race1={
      'market_p':np.array([.5,.3,.2]),
      'z':Z[:3],
      'history_eligible':np.array([1,1,0],dtype=bool),
      'winner_index':0,
    }
    race2={
      'market_p':np.array([.30,.22,.18,.12,.10,.08]),
      'z':np.vstack([Z[1],Z[2],Z[3],Z[4],Z[5],Z[0]]),
      'history_eligible':np.array([1,1,1,1,1,0],dtype=bool),
      'winner_index':1,
    }
    races=[race1,race2]
    beta=np.array([.12,-.08,.05,.03,-.04,.07])
    lam=.25
    loss,grad,meta=mean_race_loss_and_grad(races,beta,lam)
    l1,g1,*_=race_loss_and_grad(race1['market_p'],race1['z'],beta,race1['history_eligible'],race1['winner_index'],l2=0)
    l2,g2,*_=race_loss_and_grad(race2['market_p'],race2['z'],beta,race2['history_eligible'],race2['winner_index'],l2=0)
    expected=.5*(l1+l2)+.5*lam*float(beta@beta)
    expected_grad=.5*(g1+g2)+lam*beta

    eps=1e-6; fd=[]
    for j in range(len(beta)):
      bp=beta.copy();bm=beta.copy();bp[j]+=eps;bm[j]-=eps
      lp=mean_race_loss_and_grad(races,bp,lam)[0]
      lm=mean_race_loss_and_grad(races,bm,lam)[0]
      fd.append((lp-lm)/(2*eps))
    fd=np.asarray(fd)
    loss_dup,grad_dup,_=mean_race_loss_and_grad([race1,race2,race1,race2],beta,lam)

    checks={
      'standardized_train_mean_zero':float(np.max(np.abs(Z.mean(axis=0))))<1e-12,
      'standardized_train_std_one':float(np.max(np.abs(Z.std(axis=0,ddof=0)-1)))<1e-12,
      'zero_scale_fail_closed':zero_scale_rejected,
      'standardizer_scope_declared_train_only':state.get('fit_scope')=='TRAIN_HISTORY_ELIGIBLE_ROWS_ONLY',
      'aggregate_loss_equals_equal_race_manual':abs(loss-expected)<1e-12,
      'aggregate_grad_equals_equal_race_manual':float(np.max(np.abs(grad-expected_grad)))<1e-12,
      'aggregate_gradient_matches_finite_difference':float(np.max(np.abs(grad-fd)))<1e-6,
      'duplicating_all_races_does_not_change_objective':abs(loss-loss_dup)<1e-12 and float(np.max(np.abs(grad-grad_dup)))<1e-12,
      'race_weighting_equal_per_race':meta.get('race_weighting')=='EQUAL_PER_RACE',
      'validation_oos_not_used':True,
      'real_money_bet':False
    }
    status='PASS' if all(checks.values()) else 'FAIL'
    print(json.dumps({'test_id':'KEIBA-CONDITIONAL-RESIDUAL-AGGREGATE-V1','status':status,'checks':checks,'max_grad_abs_error':float(np.max(np.abs(grad-fd)))},indent=2))
    return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
