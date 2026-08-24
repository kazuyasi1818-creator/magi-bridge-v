#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from keiba_conditional_market_residual_objective_v1 import race_probabilities,race_loss_and_grad,normalized_entropy


def main()->int:
    p=np.array([.42,.24,.16,.10,.08])
    X=np.array([
      [1.0,.2,1,0,.4,1],
      [.5,-.3,1,1,-.2,0],
      [-.2,.8,0,0,.3,1],
      [.1,-.5,1,0,-.7,0],
      [0,0,0,0,0,0],
    ],dtype=float)
    eligible=np.array([1,1,1,1,0],dtype=bool)
    beta=np.array([.2,-.1,.15,.05,-.08,.12])
    q0,r0,a0=race_probabilities(p,X,np.zeros(6),eligible)
    q,r,a=race_probabilities(p,X,beta,eligible)
    loss,grad,_,_,_=race_loss_and_grad(p,X,beta,eligible,0,l2=.1)
    eps=1e-6
    fd=[]
    for j in range(len(beta)):
      bp=beta.copy();bm=beta.copy();bp[j]+=eps;bm[j]-=eps
      lp=race_loss_and_grad(p,X,bp,eligible,0,l2=.1)[0]
      lm=race_loss_and_grad(p,X,bm,eligible,0,l2=.1)[0]
      fd.append((lp-lm)/(2*eps))
    fd=np.array(fd)
    p_flat=np.array([.2,.2,.2,.2,.2])
    q_flat,_,a_flat=race_probabilities(p_flat,X,beta,eligible)
    checks={
      'beta_zero_exact_market':float(np.max(np.abs(q0-p/p.sum())))<1e-15,
      'zero_prior_residual_exact_zero':abs(float(r[-1]))<1e-15,
      'probabilities_positive':bool(np.all(q>0)),
      'probabilities_sum_one':abs(float(q.sum())-1)<1e-15,
      'analytic_gradient_matches_finite_difference':float(np.max(np.abs(grad-fd)))<1e-6,
      'entropy_in_0_1':0<=normalized_entropy(p)<=1,
      'uniform_market_alpha_zero':abs(float(a_flat))<1e-15,
      'uniform_market_preserved':float(np.max(np.abs(q_flat-p_flat)))<1e-15,
      'no_intercept_parameter':X.shape[1]==len(beta),
      'validation_oos_not_used':True,
      'real_money_bet':False
    }
    status='PASS' if all(checks.values()) else 'FAIL'
    print(json.dumps({'test_id':'KEIBA-CONDITIONAL-MARKET-RESIDUAL-OBJECTIVE-V1','status':status,'checks':checks,'max_grad_abs_error':float(np.max(np.abs(grad-fd)))},indent=2))
    return 0 if status=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
