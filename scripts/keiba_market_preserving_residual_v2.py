#!/usr/bin/env python3
from __future__ import annotations
import math
from typing import Iterable


def entropy_linear_alpha(alpha_base: float, normalized_entropy: float) -> float:
    if not (math.isfinite(alpha_base) and alpha_base >= 0):
        raise ValueError('alpha_base must be finite and >= 0')
    if not (math.isfinite(normalized_entropy) and 0 <= normalized_entropy <= 1):
        raise ValueError('normalized_entropy must be in [0,1]')
    return alpha_base * (1.0 - normalized_entropy)


def market_preserving_residual(
    market_p: Iterable[float],
    residual_score: Iterable[float],
    alpha_base: float,
    normalized_entropy: float,
    residual_clip: float,
) -> list[float]:
    p = [float(x) for x in market_p]
    r = [float(x) for x in residual_score]
    if len(p) != len(r) or not p:
        raise ValueError('market_p and residual_score must have the same non-zero length')
    if any((not math.isfinite(x)) or x <= 0 for x in p):
        raise ValueError('market probabilities must be finite and > 0')
    if any(not math.isfinite(x) for x in r):
        raise ValueError('residual scores must be finite')
    if not (math.isfinite(residual_clip) and residual_clip > 0):
        raise ValueError('residual_clip must be finite and > 0')

    alpha_eff = entropy_linear_alpha(alpha_base, normalized_entropy)
    ps = sum(p)
    p = [x / ps for x in p]
    mean_r = sum(pi * ri for pi, ri in zip(p, r))
    centered = [ri - mean_r for ri in r]
    clipped = [max(-residual_clip, min(residual_clip, x)) for x in centered]
    z = [alpha_eff * x for x in clipped]
    zmax = max(z)
    w = [pi * math.exp(zi - zmax) for pi, zi in zip(p, z)]
    ws = sum(w)
    return [x / ws for x in w]
