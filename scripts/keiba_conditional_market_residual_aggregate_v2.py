#!/usr/bin/env python3
from __future__ import annotations
import numpy as np
from keiba_conditional_market_residual_objective_v1 import race_loss_and_grad


def mean_posterior_objective_and_grad(races:list[dict], beta):
    b=np.asarray(beta,dtype=float)
    if not races:
        raise ValueError('at least one race is required')
    ids=[str(r.get('race_id') or '') for r in races]
    if any(not x for x in ids):
        raise ValueError('race_id is required for every race')
    if len(ids)!=len(set(ids)):
        raise ValueError('duplicate race_id is forbidden')
    losses=[]; grads=[]
    for r in races:
        loss,grad,_,_,_=race_loss_and_grad(
            r['market_p'],r['z'],b,r['history_eligible'],int(r['winner_index']),l2=0.0
        )
        losses.append(loss); grads.append(grad)
    R=len(races)
    data_loss=float(np.mean(losses))
    data_grad=np.mean(np.vstack(grads),axis=0)
    # Fixed beta~N(0,I) prior. Mean-objective form is exactly
    # (sum_r NLL_r + 0.5||beta||^2) / R. No tunable lambda exists.
    prior_penalty=0.5*float(b@b)/R
    prior_grad=b/R
    return float(data_loss+prior_penalty),np.asarray(data_grad+prior_grad,float),{
        'race_count':R,
        'data_loss_mean_per_race':data_loss,
        'prior_penalty_mean_scale':prior_penalty,
        'race_weighting':'EQUAL_PER_RACE',
        'coefficient_prior':'BETA_STANDARDIZED_UNITS_IID_NORMAL_0_1',
        'tunable_l2_lambda':False,
    }
