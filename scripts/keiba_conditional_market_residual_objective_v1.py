#!/usr/bin/env python3
from __future__ import annotations
import math
import numpy as np


def normalized_entropy(market_p: np.ndarray) -> float:
    p=np.asarray(market_p,dtype=float)
    if p.ndim!=1 or len(p)<2 or np.any(~np.isfinite(p)) or np.any(p<=0):
        raise ValueError('market_p must be positive finite 1D with >=2 horses')
    p=p/p.sum()
    return float(-(p*np.log(p)).sum()/math.log(len(p)))


def race_probabilities(market_p, z, beta, history_eligible):
    p=np.asarray(market_p,dtype=float)
    X=np.asarray(z,dtype=float)
    b=np.asarray(beta,dtype=float)
    e=np.asarray(history_eligible,dtype=bool)
    if X.ndim!=2 or X.shape[0]!=len(p) or X.shape[1]!=len(b) or len(e)!=len(p):
        raise ValueError('shape mismatch')
    if np.any(~np.isfinite(X)) or np.any(~np.isfinite(b)):
        raise ValueError('non-finite X/beta')
    if np.any(~np.isfinite(p)) or np.any(p<=0):
        raise ValueError('market_p must be positive finite')
    p=p/p.sum()
    h=normalized_entropy(p)
    alpha=1.0-h
    raw=X@b
    residual=np.zeros(len(p),dtype=float)
    residual[e]=np.tanh(raw[e])
    adj=alpha*residual
    m=float(np.max(adj))
    w=p*np.exp(adj-m)
    q=w/w.sum()
    return q, residual, alpha


def race_loss_and_grad(market_p, z, beta, history_eligible, winner_index:int, l2:float=0.0):
    X=np.asarray(z,dtype=float)
    b=np.asarray(beta,dtype=float)
    e=np.asarray(history_eligible,dtype=bool)
    if winner_index<0 or winner_index>=X.shape[0]:
        raise ValueError('winner_index out of range')
    if not (math.isfinite(l2) and l2>=0):
        raise ValueError('l2 must be finite and >=0')
    q,residual,alpha=race_probabilities(market_p,X,b,e)
    loss=-math.log(max(float(q[winner_index]),1e-300))+0.5*l2*float(b@b)
    y=np.zeros(len(q),dtype=float); y[winner_index]=1.0
    raw=X@b
    deriv=np.zeros(len(q),dtype=float)
    deriv[e]=1.0-np.tanh(raw[e])**2
    grad=X.T@(alpha*(q-y)*deriv)+l2*b
    return float(loss),np.asarray(grad,float),q,residual,alpha
