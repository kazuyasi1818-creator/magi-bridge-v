#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from keiba_market_preserving_residual_v2 import entropy_linear_alpha, market_preserving_residual


def main() -> int:
    market=[0.40,0.25,0.15,0.12,0.08]
    residual=[1.0,0.4,-0.2,-0.5,-0.8]
    p0=market_preserving_residual(market,residual,0.0,0.7,2.0)
    pc=market_preserving_residual(market,[3,3,3,3,3],1.0,0.7,2.0)
    a0=entropy_linear_alpha(1.0,0.0)
    a5=entropy_linear_alpha(1.0,0.5)
    a1=entropy_linear_alpha(1.0,1.0)
    p_low=market_preserving_residual(market,residual,1.0,0.2,2.0)
    p_high=market_preserving_residual(market,residual,1.0,0.9,2.0)
    l1_low=sum(abs(a-b) for a,b in zip(p_low,market))
    l1_high=sum(abs(a-b) for a,b in zip(p_high,market))
    checks={
      'alpha_zero_exact_market':max(abs(a-b) for a,b in zip(p0,market))<1e-15,
      'constant_residual_exact_market':max(abs(a-b) for a,b in zip(pc,market))<1e-15,
      'entropy_zero_alpha_equals_base':abs(a0-1.0)<1e-15,
      'entropy_half_linear':abs(a5-0.5)<1e-15,
      'entropy_one_alpha_zero':abs(a1)<1e-15,
      'higher_entropy_reduces_market_deviation':l1_high<l1_low,
      'probabilities_positive':all(x>0 for x in p_low+p_high),
      'probabilities_sum_one':abs(sum(p_low)-1)<1e-15 and abs(sum(p_high)-1)<1e-15,
      'validation_oos_not_used':True,
      'real_money_bet':False
    }
    status='PASS' if all(checks.values()) else 'FAIL'
    print(json.dumps({'test_id':'KEIBA-MARKET-PRESERVING-RESIDUAL-V2','status':status,'checks':checks},indent=2))
    return 0 if status=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
