#!/usr/bin/env python3
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from keiba_conditional_market_residual_aggregate_v2 import mean_posterior_objective_and_grad

BETA_DIM=6


def fit_conditional_residual(races:list[dict]) -> dict:
    if not races:
        raise ValueError('at least one race is required')
    ordered=sorted(races,key=lambda r:str(r.get('race_id') or ''))
    ids=[str(r.get('race_id') or '') for r in ordered]
    if any(not x for x in ids) or len(ids)!=len(set(ids)):
        raise ValueError('unique nonblank race_id required')

    def fg(beta):
        f,g,_=mean_posterior_objective_and_grad(ordered,beta)
        return f,g

    x0=np.zeros(BETA_DIM,dtype=float)
    start_obj=float(fg(x0)[0])
    res=minimize(
        fg,x0,method='L-BFGS-B',jac=True,
        options={'maxiter':2000,'gtol':1e-8,'ftol':1e-12,'maxls':50,'maxcor':10}
    )
    if not bool(res.success):
        raise RuntimeError(f'optimizer nonconvergence: status={res.status} message={res.message}')
    beta=np.asarray(res.x,dtype=float)
    final_obj=float(res.fun)
    if np.any(~np.isfinite(beta)) or not np.isfinite(final_obj):
        raise RuntimeError('nonfinite fitted result')
    if final_obj>start_obj+1e-12:
        raise RuntimeError('optimizer worsened objective')
    return {
        'trainer_id':'KEIBA-CONDITIONAL-MARKET-RESIDUAL-TRAINER-V1',
        'optimizer':'L-BFGS-B',
        'race_order':'race_id ascending',
        'race_count':len(ordered),
        'beta':[float(x) for x in beta],
        'start_objective':start_obj,
        'final_objective':final_obj,
        'iterations':int(res.nit),
        'function_evaluations':int(res.nfev),
        'jacobian_evaluations':int(getattr(res,'njev',res.nfev)),
        'success':True,
        'status':int(res.status),
        'message':str(res.message),
        'initial_beta':'zeros',
        'randomness_used':False,
        'alternate_optimizer_used':False,
    }
