#!/usr/bin/env python3
from __future__ import annotations
import math
import numpy as np

FEATURES = [
    'horse_prior_starts',
    'days_since_last_start_rebuilt',
    'same_surface_as_last',
    'same_venue_as_last',
    'abs_distance_change_m',
    'same_class_code_as_last',
]


def fit_standardizer(X) -> dict:
    a=np.asarray(X,dtype=float)
    if a.ndim!=2 or a.shape[1]!=len(FEATURES) or a.shape[0]<2:
        raise ValueError('X must have >=2 rows and exactly six columns')
    if np.any(~np.isfinite(a)):
        raise ValueError('training standardizer input must be finite')
    mean=a.mean(axis=0)
    scale=a.std(axis=0,ddof=0)
    if np.any(~np.isfinite(mean)) or np.any(~np.isfinite(scale)) or np.any(scale<=0):
        raise ValueError('nonfinite or zero feature scale')
    return {
        'feature_order':list(FEATURES),
        'mean':[float(x) for x in mean],
        'scale':[float(x) for x in scale],
        'ddof':0,
        'fit_scope':'TRAIN_HISTORY_ELIGIBLE_ROWS_ONLY',
    }


def transform(X, state:dict):
    if list(state.get('feature_order') or [])!=FEATURES:
        raise ValueError('feature order mismatch')
    mean=np.asarray(state.get('mean'),dtype=float)
    scale=np.asarray(state.get('scale'),dtype=float)
    if mean.shape!=(len(FEATURES),) or scale.shape!=(len(FEATURES),):
        raise ValueError('invalid standardizer state shape')
    if np.any(~np.isfinite(mean)) or np.any(~np.isfinite(scale)) or np.any(scale<=0):
        raise ValueError('invalid standardizer state values')
    a=np.asarray(X,dtype=float)
    if a.ndim!=2 or a.shape[1]!=len(FEATURES) or np.any(~np.isfinite(a)):
        raise ValueError('transform input must be finite 2D six-feature matrix')
    return (a-mean)/scale
