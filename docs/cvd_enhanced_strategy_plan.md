# CVD-Enhanced Mean Reversion Strategy Implementation Plan

## Executive Summary

**Goal**: Build a mean reversion strategy enhanced with Hyperliquid CVD (Cumulative Volume Delta) flow data to improve hit rate from ~53% (synthetic baseline) to 56-60% on real Polymarket closed markets.

**Key Insight**: Synthetic backtests validated the mean reversion logic works. The real alpha comes from Hyperliquid order flow data that captures information NOT present in CSV price data.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         STRATEGY STACK                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 1: Mean Reversion Base (Validated ✓)                              │ │
│  │ • synthetic_optimized_mr_v2                                             │ │
│  │ • 53.4% hit rate on BTC 5m markets                                      │ │
│  │ • Signal: -(distance_from_vwap × 3.0) + ((0.5 - range_pos) × 2.5)      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 2: CVD Flow Confirmation (REAL ALPHA)                             │ │
│  │ • external_cvd: Hyperliquid cumulative volume delta                     │ │
│  │ • external_trade_imbalance: Buy/sell pressure ratio                     │ │
│  │ • flow_alignment_score: Venue divergence signal                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 3: Agreement Filter                                               │ │
│  │ • Only trade when MR + CVD agree                                        │ │
│  │ • Confidence: 0.6 (agree) vs 0.3 (disagree)                             │ │
│  │ • Expected: 50-60% trade frequency, 55-60% hit rate                     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Create CVD-Enhanced Strategy (Days 1-2)

**File**: `services/backtester/synthetic_strategies.py`

**Tasks**:
1. Create `SyntheticCVDEnhancedMRStrategy` class
2. Implement MR + CVD signal combination logic
3. Add confidence calibration based on agreement
4. Register strategy in `build_synthetic_strategy_registry()`

**Key Logic**:
```python
# MR signal (direction)
mr_signal = -(distance_from_vwap * 3.0) + ((0.5 - range_position) * 2.5)

# CVD signal (confirmation)
cvd_imbalance = feature_snapshot.external_trade_imbalance

# Combine with agreement check
if mr_signal > 0 and cvd_imbalance > 0.1:  # YES + bullish flow
    combined = mr_signal * 1.3
    confidence = 0.7
elif mr_signal < 0 and cvd_imbalance < -0.1:  # NO + bearish flow
    combined = mr_signal * 1.3
    confidence = 0.7
elif abs(cvd_imbalance) > 0.3:  # Strong CVD overrides MR
    combined = cvd_imbalance * 0.5
    confidence = 0.5
else:  # Disagreement
    combined = mr_signal * 0.5  # Reduce position
    confidence = 0.3
```

---

### Phase 2: Add CVD Features to Synthetic Snapshots (Days 2-3)

**File**: `services/backtester/synthetic_research.py`

**Tasks**:
1. Add CVD fields to `SyntheticFeatureSnapshot`
2. Generate synthetic CVD values from CSV price data (proxy)
3. Ensure compatibility with real `FeatureSnapshot` schema

**Synthetic CVD Proxy** (for backtesting):
```python
# Generate pseudo-CVD from price/volume relationship
def generate_synthetic_cvd(bars: list) -> float:
    """Create synthetic CVD proxy from price action."""
    if not bars:
        return 0.0
    
    # CVD proxy: positive if close > VWAP with volume
    last_bar = bars[-1]
    vwap = sum(b['close'] * b['volume'] for b in bars[-20:]) / sum(b['volume'] for b in bars[-20:])
    
    if last_bar['close'] > vwap:
        return min((last_bar['close'] - vwap) / vwap * 1000, 1.0)
    else:
        return max((last_bar['close'] - vwap) / vwap * 1000, -1.0)
```

---

### Phase 3: Test on Synthetic Data (Day 3)

**API Endpoint**: `POST /api/v1/research/synthetic/run`

**Test Commands**:
```bash
# Baseline: MR-only
curl -X POST "http://localhost:8000/api/v1/research/synthetic/run?asset=BTC&timeframe=crypto_5m&limit=300&strategy_name=synthetic_optimized_mr_v2"

# CVD-enhanced
curl -X POST "http://localhost:8000/api/v1/research/synthetic/run?asset=BTC&timeframe=crypto_5m&limit=300&strategy_name=synthetic_cvd_enhanced_mr"

# Compare results
curl "http://localhost:8000/api/v1/research/synthetic/results"
```

**Success Criteria**:
- CVD-enhanced shows ≥2% edge improvement over MR-only
- Trade frequency 50-70% (not 100%)
- Confidence calibration: high-confidence trades have higher accuracy

---

### Phase 4: Test on Real Closed Markets (Days 4-5)

**API Endpoint**: `POST /api/v1/evaluations/closed-markets/run`

**Test Commands**:
```bash
# Run on real Polymarket closed markets WITH Hyperliquid enrichment
curl -X POST "http://localhost:8000/api/v1/evaluations/closed-markets/run?asset=BTC&timeframe=crypto_5m&limit=50&strategy_name=cvd_enhanced_mr&include_hyperliquid_enrichment=true"

# Compare to MR-only baseline
curl -X POST "http://localhost:8000/api/v1/evaluations/closed-markets/run?asset=BTC&timeframe=crypto_5m&limit=50&strategy_name=synthetic_optimized_mr_v2&include_hyperliquid_enrichment=false"
```

**Expected Results**:
| Strategy | Enrichment | Expected Hit Rate | Expected Edge |
|----------|------------|-------------------|---------------|
| MR-only | No | 52-54% | +2-3% |
| CVD-enhanced | Yes | 56-60% | +6-10% |

---

### Phase 5: Production Deployment (Days 5-7)

**Tasks**:
1. Add strategy to paper trading rotation
2. Set up monitoring dashboard for CVD signal quality
3. Configure confidence thresholds for live trading
4. Document parameter tuning guide

**Configuration**:
```bash
# .env for live paper trading
PAPER_TRADING_STRATEGY=cvd_enhanced_mr
PAPER_TRADING_MIN_CONFIDENCE=0.5  # Only trade medium+ confidence
PAPER_TRADING_MARKET_TYPES=crypto_5m,crypto_15m
PAPER_TRADING_UNDERLYINGS=BTC
```

---

## File Changes Required

### 1. `services/backtester/synthetic_strategies.py`
- Add `SyntheticCVDEnhancedMRStrategy` class
- Register in `build_synthetic_strategy_registry()`

### 2. `services/backtester/synthetic_research.py`
- Add CVD proxy generation to `_build_synthetic_features()`
- Update `SyntheticFeatureSnapshot` creation

### 3. `packages/core_types/schemas.py`
- Verify `SyntheticFeatureSnapshot` has CVD fields
- Add if missing: `external_cvd`, `external_trade_imbalance`

### 4. `services/feature_engine/service.py`
- Ensure real feature snapshots include CVD from Hyperliquid
- Verify CVD alignment with Polymarket market windows

---

## Testing Checklist

- [ ] Synthetic CVD proxy generates reasonable values (-1.0 to +1.0)
- [ ] CVD-enhanced strategy compiles without errors
- [ ] Synthetic backtest runs successfully (300+ samples)
- [ ] CVD-enhanced shows improved edge vs MR-only
- [ ] Real closed market evaluation runs with Hyperliquid enrichment
- [ ] Hit rate improvement ≥2% on real markets
- [ ] Confidence calibration: high-confidence trades more accurate
- [ ] Paper trading loop accepts new strategy

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| CVD data unavailable | Fall back to MR-only with reduced position size |
| CVD adds noise, not signal | Add CVD threshold filter (only use when |imbalance| > 0.1) |
| Overfitting to historical CVD | Walk-forward validation on different time periods |
| Latency in live CVD data | Use rolling 1-minute CVD, not real-time tick |

---

## Success Metrics

| Metric | Baseline (MR-only) | Target (CVD-enhanced) |
|--------|-------------------|----------------------|
| Hit Rate | 53.4% | ≥56% |
| Edge over 50% | +3.4% | ≥+6% |
| Contract Score | +14 (500 samples) | ≥+20 |
| Trade Frequency | 100% | 50-70% |
| High-confidence accuracy | N/A | ≥60% |

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Strategy Implementation | 2 days | `SyntheticCVDEnhancedMRStrategy` |
| 2. CVD Proxy for Synthetic | 1 day | Synthetic CVD generation |
| 3. Synthetic Testing | 1 day | Backtest comparison report |
| 4. Real Market Testing | 2 days | Closed market evaluation |
| 5. Production Deployment | 2 days | Paper trading live |

**Total**: 7-8 days to production-ready

---

## Next Actions

1. **Create `SyntheticCVDEnhancedMRStrategy`** (Phase 1)
2. **Add CVD proxy to synthetic research** (Phase 2)
3. **Run synthetic backtest comparison** (Phase 3)
4. **Evaluate on real closed markets** (Phase 4)
5. **Deploy to paper trading** (Phase 5)

---

## Appendix: Key API Endpoints

### Synthetic Backtesting
```
POST /api/v1/research/synthetic/run?asset=BTC&timeframe=crypto_5m&limit=300&strategy_name={strategy}
GET  /api/v1/research/synthetic/results
GET  /api/v1/research/synthetic/strategies
```

### Real Market Evaluation
```
POST /api/v1/evaluations/closed-markets/run?asset=BTC&timeframe=crypto_5m&limit=50&strategy_name={strategy}&include_hyperliquid_enrichment=true
GET  /api/v1/evaluations/results
GET  /api/v1/evaluations/closed-markets?asset=BTC&timeframe=crypto_5m&limit=50
```

### Paper Trading
```
GET  /api/v1/paper-trading/status
POST /api/v1/paper-trading/start?strategy=cvd_enhanced_mr
GET  /api/v1/paper-trading/blotter
```
