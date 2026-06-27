# PV1 Dataset Optimization Summary

## Problem Analysis

### Initial Test Results (14 simulations)
- **Submittable**: 0/14 (0%)
- **Errors**: 2 (GROUP field incompatibility)
- **Primary Failure**: LOW_SHARPE (avg: -0.556, required: 1.25)
- **Secondary Failure**: LOW_FITNESS (avg: -0.279, required: 1.0)

### Root Causes Identified

1. **Template Mismatch**: Generic templates not optimized for price-volume data characteristics
2. **Missing Normalization**: Lack of zscore and volatility-scaling operations
3. **No Mean Reversion**: Price-volume data often benefits from mean-reversion strategies
4. **GROUP Field Errors**: `country` field (GROUP type) incompatible with `ts_backfill()` operator

## Optimization Strategy

### 1. Created PV1-Specific Template Library
**File**: `data/worldquant_template_library_pv1.json`

**Key Design Principles**:
- **Volatility Normalization**: All returns divided by standard deviation
- **Zscore Transformations**: Convert raw values to statistical z-scores
- **Mean Reversion**: Negative signals for overbought/oversold conditions
- **Shorter Windows**: 10-30 day windows instead of 20-60 for faster price reactions
- **Cross-Sectional Ranking**: Rank-based operators for relative value

### 2. Template Categories (14 MATRIX + 4 GROUP)

#### High Priority Templates (180-170)
1. **pv1_zscore_mean_reversion_20** (180)
   - `group_rank(ts_zscore(ts_backfill({field}, 240), 20), subindustry)`
   - Statistical normalization for mean reversion

2. **pv1_vol_scaled_change_10_30** (175)
   - `group_rank(ts_delta(ts_backfill({field}, 240), 10) / ts_std_dev(ts_backfill({field}, 240), 30), subindustry)`
   - Volatility-adjusted price changes

3. **pv1_rank_cross_sectional_momentum** (170)
   - `group_rank(rank(ts_backfill({field}, 240)) - rank(ts_backfill({field}, 260)), subindustry)`
   - Cross-sectional momentum with 20-day lookback

#### Medium Priority Templates (168-140)
4. **pv1_mean_reversion_zscore_60** (168) - Negative zscore for mean reversion
5. **pv1_volatility_normalized_return** (165) - Short-term return / volatility
6. **pv1_decay_linear_10** (160) - Linear decay for recent price importance
7. **pv1_rank_delta_short_term** (158) - 1-day rank changes
8. **pv1_corr_market_60** (155) - Correlation-based signals
9. **pv1_ts_rank_momentum_120** (150) - Time series rank momentum
10. **pv1_std_dev_ratio_20_60** (148) - Volatility regime changes
11. **pv1_mean_diff_5_20_norm** (145) - Mean spread normalized by vol
12. **pv1_neutralized_momentum** (142) - Group-neutralized momentum
13. **pv1_signed_volatility** (140) - Volatility-signed returns

#### GROUP Templates (4 templates)
- Use `vec_avg()` operator instead of `ts_backfill()`
- Avoid unit mismatch errors

### 3. Configuration Changes

**Command**:
```bash
python -m alpha --dataset-id pv1 \
  --limit 5 \
  --template-library-file data/worldquant_template_library_pv1.json \
  --max-templates-per-field 15
```

**Key Parameters**:
- `--limit 5`: Test 5 fields (adjfactor, adv20, cap, close, country)
- `--max-templates-per-field 15`: Increased from 3 to 15
- `--template-library-file`: Custom pv1-optimized templates

## Expected Improvements

### Sharpe Ratio
- **Before**: -0.556 avg (need 1.25)
- **Target**: >1.25 through zscore normalization and volatility scaling

### Fitness
- **Before**: -0.279 avg (need 1.0)
- **Target**: >1.0 through better turnover management

### Error Reduction
- **Before**: 2 errors (GROUP field incompatibility)
- **Target**: 0 errors with GROUP-specific templates

## Monitoring Metrics

Watch for:
1. **Sharpe improvement**: From negative to positive values
2. **Near-pass candidates**: Score > 0.5 indicates promising templates
3. **Error-free GROUP fields**: country field should complete without errors
4. **Template ranking**: Higher priority templates should perform better

## Next Steps After This Run

1. **Analyze Results**: Check which templates achieved highest Sharpe
2. **Parameter Tuning**: Adjust window sizes for best-performing templates
3. **Template Expansion**: Create variants of successful templates
4. **Cross-Validation**: Test on different field subsets
5. **Submission**: Submit alphas that pass all quality checks

## Lessons Learned

### What Didn't Work
- Generic `iter_group_*` templates on price-volume data
- Long time windows (60+ days) for fast-moving PV data
- Mean spread without volatility normalization
- GROUP fields with MATRIX operators

### What Should Work
- Zscore transformations for statistical normalization
- Volatility-scaled returns for risk-adjusted signals
- Short-term windows (10-30 days) for price momentum/reversion
- Cross-sectional ranking for relative value
- Group neutralization for industry-adjusted signals

## File Changes

### New Files
- `data/worldquant_template_library_pv1.json`: PV1-specific template library
- `scripts/run_pv1_optimization.py`: Automated optimization runner
- `docs/pv1_optimization_strategy.md`: This document

### Modified Files
- `src/alpha/io/credentials.py`: Fixed missing `suppress` import

### Unchanged
- Core alpha generation logic
- Template loading mechanism
- Result analysis pipeline
