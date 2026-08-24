#!/usr/bin/env python3
from __future__ import annotations
import math
import numpy as np
from keiba_conditional_market_residual_objective_v1 import race_loss_and_grad


def mean_race_loss_and_grad(races:list[dict], beta, lambda_l2:float):
    b=np.asarray(beta,dtype=float)
    if not races:
        raise ValueError('at least one race is required')
    if not (math.isfinite(lambda_l2) and lambda_l2>=0):
        raise ValueError('lambda_l2 must be finite and >=0')
    losses=[]
    grads=[]
    # Put ridge once at aggregate level so its strength does not depend on race count.
    for r in races:
        loss,grad,_,_,_=race_loss_and_grad(
            r['market_p'],r['z'],b,r['history_eligible'],int(r['winner_index']),l2=0.0
        )
        losses.append(loss)
        grads.append(grad)
    data_loss=float(np.mean(losses))
    data_grad=np.mean(np.vstack(grads),axis=0)
    total_loss=data_loss+0.5*lambda_l2*float(b@b)
    total_grad=data_grad+lambda_l2*b
    return float(total_loss),np.asarray(total_grad,float),{
        'race_count':len(races),
        'data_loss_mean_per_race':data_loss,
        'ridge_penalty':0.5*lambda_l2*float(b@b),
        'race_weighting':'EQUAL_PER_RACE'
    }
