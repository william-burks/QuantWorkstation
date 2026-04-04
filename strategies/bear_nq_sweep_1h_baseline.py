"""
NQ Bear Sweep Strategy — 1H baseline

Detects liquidity sweeps on 1H NQ charts and trades the post-sweep reversal.
Uses identical confirmation logic to ES and CL bear sweep.

NQ-specific note: Higher volatility than ES, potentially sharper reversals.
Phase 1 baseline: all sessions, no wick filter, default target_r=1.25.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from strategies.common.strategy_artifacts import (
        build_baseline_summary_for_csv,
        parse_float_list,
        parse_str_list,
        write_results_csv,
    )
except ModuleNotFoundError:  # pragma: no cover
    from common.strategy_artifacts import (
        build_baseline_summary_for_csv,
        parse_float_list,
        parse_str_list,
        write_results_csv,
    )

try:
    from scipy import stats
except Exception:  # pragma: no cover
    stats = None

# PATHS — adjust BASE if data location differs
BASE = Path('/Users/will/quant-research/data/futures')
MNQ_5M = BASE / 'MNQ_continuous_5min.parquet'
MNQ_1H = BASE / 'MNQ_continuous_1H.parquet'
MES_5M = BASE / 'MES_continuous_5min.parquet'

# PARAMETERS — baseline profile (same as ES with atr_mult_stop open for grid)
DEFAULT_CONFIG = {
    'signal_window': 36,
    'atr_mult_stop': 0.5,
    'target_r': 1.25,
    'max_hold_bars': 36,
    'allowed_sessions': ['ASIA', 'LONDON', 'NY_PRE', 'NY', 'AFTER'],  # Test all sessions
    'allowed_dir': ['BEAR'],
    'swing_n': 3,
    'min_r_dist': 0.10,
    'chain_mode': 'no_smt_in_chain',
    'wick_mode': 'none',
    'sweep_lookback': 50,
    'stop_mode': 'sweep_atr',
    'lh_lookback': 5,
    'lh_buffer_mult': 0.10,
    'partial_exit_r': 0.0,
    'partial_size': 0.5,
    'stall_bars': 0,
    'stall_threshold': 0.5,
}


def load(path):
    """Load parquet file and convert to US/Eastern timezone."""
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert('US/Eastern')
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.sort_index()


def compute_atr(df, period=14):
    """14-period EMA of true range."""
    hi = df['high']
    lo = df['low']
    pc = df['close'].shift(1)
    tr = pd.concat([(hi - lo), (hi - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def label_session(idx):
    """Map hour to session label. Assumes US/Eastern timezone."""
    h = idx.hour + idx.minute / 60
    if 0.0 <= h < 2.0:
        return 'ASIA'
    if 2.0 <= h < 7.0:
        return 'LONDON'
    if 7.0 <= h < 9.5:
        return 'NY_PRE'
    if 9.5 <= h < 16.0:
        return 'NY'
    if 16.0 <= h < 20.0:
        return 'AFTER'
    return 'ASIA'


def swing_pivots(df, n=3):
    """Identify swing highs and lows using n-bar lookback."""
    hi = df['high'].values
    lo = df['low'].values
    sh = np.full(len(df), np.nan)
    sl = np.full(len(df), np.nan)
    for i in range(n, len(df) - n):
        if hi[i] == max(hi[i - n:i + n + 1]):
            sh[i] = hi[i]
        if lo[i] == min(lo[i - n:i + n + 1]):
            sl[i] = lo[i]
    df = df.copy()
    df['swing_high'] = sh
    df['swing_low'] = sl
    return df


def detect_sweeps(htf_df, allowed_sessions, allowed_dir, tf_label='1H', lookback=50):
    """
    Detect liquidity sweeps: bars that exceed a swing level then close back inside.

    BEAR: high > prior swing high AND close < prior swing high
    BULL: low < prior swing low AND close > prior swing low
    """
    sweeps = []
    highs = htf_df['swing_high'].dropna()
    lows = htf_df['swing_low'].dropna()

    for i in range(lookback, len(htf_df)):
        row = htf_df.iloc[i]
        session = row.get('session', 'NY')
        if session not in allowed_sessions:
            continue

        if 'BEAR' in allowed_dir:
            prior_highs = highs[highs.index < htf_df.index[i]]
            if len(prior_highs):
                nearest_sh = float(prior_highs.iloc[-1])
                if row['high'] > nearest_sh and row['close'] < nearest_sh:
                    sweeps.append({
                        'time': htf_df.index[i],
                        'direction': 'BEAR',
                        'level': nearest_sh,
                        'session': session,
                        'tf': tf_label,
                        'wick_size': row['high'] - nearest_sh,
                        'atr': row.get('atr', np.nan),
                    })

        if 'BULL' in allowed_dir:
            prior_lows = lows[lows.index < htf_df.index[i]]
            if len(prior_lows):
                nearest_sl = float(prior_lows.iloc[-1])
                if row['low'] < nearest_sl and row['close'] > nearest_sl:
                    sweeps.append({
                        'time': htf_df.index[i],
                        'direction': 'BULL',
                        'level': nearest_sl,
                        'session': session,
                        'tf': tf_label,
                        'wick_size': nearest_sl - row['low'],
                        'atr': row.get('atr', np.nan),
                    })

    return pd.DataFrame(sweeps)


def detect_fvg(df):
    """Detect fair value gaps (3-bar imbalances)."""
    hi = df['high'].values
    lo = df['low'].values
    fvg_bull = np.full(len(df), np.nan)
    fvg_bear = np.full(len(df), np.nan)
    fvg_bull_top = np.full(len(df), np.nan)
    fvg_bull_bot = np.full(len(df), np.nan)
    fvg_bear_top = np.full(len(df), np.nan)
    fvg_bear_bot = np.full(len(df), np.nan)
    for i in range(2, len(df)):
        if lo[i] > hi[i - 2]:
            fvg_bull[i] = 1
            fvg_bull_top[i] = lo[i]
            fvg_bull_bot[i] = hi[i - 2]
        if hi[i] < lo[i - 2]:
            fvg_bear[i] = 1
            fvg_bear_top[i] = lo[i - 2]
            fvg_bear_bot[i] = hi[i]
    df = df.copy()
    df['fvg_bull'] = fvg_bull
    df['fvg_bear'] = fvg_bear
    df['fvg_bull_top'] = fvg_bull_top
    df['fvg_bull_bot'] = fvg_bull_bot
    df['fvg_bear_top'] = fvg_bear_top
    df['fvg_bear_bot'] = fvg_bear_bot
    return df


def detect_ifvg(df):
    """Detect incomplete fair value gaps (price still within FVG)."""
    df = df.copy()
    df['ifvg_bull'] = 0
    df['ifvg_bear'] = 0
    bull_fvgs = df[df['fvg_bull'] == 1][['fvg_bull_bot', 'fvg_bull_top']].copy()
    bear_fvgs = df[df['fvg_bear'] == 1][['fvg_bear_bot', 'fvg_bear_top']].copy()
    for i in range(len(df)):
        price = df['close'].iloc[i]
        prior_bull = bull_fvgs[bull_fvgs.index < df.index[i]]
        if len(prior_bull):
            last = prior_bull.iloc[-1]
            if last['fvg_bull_bot'] <= price <= last['fvg_bull_top']:
                df.iloc[i, df.columns.get_loc('ifvg_bull')] = 1
        prior_bear = bear_fvgs[bear_fvgs.index < df.index[i]]
        if len(prior_bear):
            last = prior_bear.iloc[-1]
            if last['fvg_bear_bot'] <= price <= last['fvg_bear_top']:
                df.iloc[i, df.columns.get_loc('ifvg_bear')] = 1
    return df


def detect_bos(df, direction, lookback=10):
    """Detect break of structure: close breaks lookback high/low."""
    closes = df['close'].values
    hi = df['high'].values
    lo = df['low'].values
    bos = np.zeros(len(df))
    lb = min(lookback, len(df) - 1)
    for i in range(lb, len(df)):
        if direction == 'BULL':
            if closes[i] > max(hi[max(0, i - lb):i]):
                bos[i] = 1
        else:
            if closes[i] < min(lo[max(0, i - lb):i]):
                bos[i] = 1
    return bos


def detect_smt(mes_win, mnq_win, direction, lookback=10):
    """Detect SMT divergence: one market breaks lookback while other doesn't."""
    smt = np.zeros(len(mes_win))
    lb = min(lookback, len(mes_win) - 1)
    mes_hi = mes_win['high'].values
    mes_lo = mes_win['low'].values
    mnq_hi = mnq_win['high'].values
    mnq_lo = mnq_win['low'].values
    for i in range(lb, len(mes_win)):
        if direction == 'BEAR':
            if (mes_hi[i] > max(mes_hi[max(0, i - lb):i]) and
                    mnq_hi[i] < max(mnq_hi[max(0, i - lb):i])):
                smt[i] = 1
        else:
            if (mes_lo[i] < min(mes_lo[max(0, i - lb):i]) and
                    mnq_lo[i] > min(mnq_lo[max(0, i - lb):i])):
                smt[i] = 1
    return smt


def detect_eq_retrace(window, direction, sweep_close):
    """Detect equal retrace: price returns to within 0.05% of sweep close."""
    closes = window['close'].values
    eq = np.zeros(len(window))
    if direction == 'BEAR':
        for i in range(1, len(window)):
            if closes[i] >= sweep_close * 0.9995:
                eq[i] = 1
    else:
        for i in range(1, len(window)):
            if closes[i] <= sweep_close * 1.0005:
                eq[i] = 1
    return eq


def find_5m_lower_high_stop(window, entry_bar, direction, atr_val, lh_lookback=5, lh_buffer_mult=0.10):
    """
    Tighter stop based on recent 5m local extreme before entry.

    BEAR: stop = max(high) in last lh_lookback bars + buffer
    BULL: stop = min(low)  in last lh_lookback bars - buffer
    """
    if entry_bar < 1:
        return None
    pre = window.iloc[max(0, entry_bar - lh_lookback):entry_bar]
    if pre.empty:
        return None
    buffer = atr_val * lh_buffer_mult
    if direction == 'BEAR':
        return float(pre['high'].max()) + buffer
    else:
        return float(pre['low'].min()) - buffer


def build_confirmations(window, direction, smt_arr, eq_arr, is_2b, chain_mode):
    """Build 2-stage, 3-stage, 4-stage confirmation checks."""
    if direction == 'BULL':
        ifvg = window['ifvg_bull'].values == 1
        fvg = window['fvg_bull'].fillna(0).values == 1
    else:
        ifvg = window['ifvg_bear'].values == 1
        fvg = window['fvg_bear'].fillna(0).values == 1

    smt = smt_arr == 1
    bos = None

    if chain_mode == 'no_smt_in_chain':
        conf2 = ifvg | (detect_bos(window, direction) == 1)
        conf3 = fvg | (eq_arr == 1)
        conf4 = ifvg | (detect_bos(window, direction) == 1)
        return conf2, conf3, conf4

    bos = detect_bos(window, direction) == 1
    conf2 = bos | ifvg | smt
    conf3 = fvg | (eq_arr == 1) | (smt if is_2b else np.zeros(len(window), dtype=bool))
    conf4 = bos | ifvg

    if chain_mode == 'bos_heavy':
        conf4 = bos
    elif chain_mode == 'ifvg_heavy':
        conf4 = ifvg

    return conf2, conf3, conf4


def find_entry_bar(conf2, conf3, conf4, chain_mode):
    """Find first bar where all three confirmations are sequentially met."""
    if chain_mode == 'strict_ordered':
        first2 = None
        first3_after_2 = None
        for i in range(1, len(conf4)):
            if first2 is None and conf2[i - 1]:
                first2 = i - 1
            if first2 is not None and first3_after_2 is None:
                if conf3[max(first2 + 1, 0):i].any():
                    first3_after_2 = i - 1
            if first2 is not None and first3_after_2 is not None and conf4[i]:
                return i
        return None

    for i in range(1, len(conf4)):
        if conf2[:i].any() and conf3[:i].any() and conf4[i]:
            return i
    return None


def add_wick_quantiles(sweeps_df):
    """Bucket wick sizes into quartiles."""
    sweeps = sweeps_df.copy()
    if 'wick_size' not in sweeps.columns:
        sweeps['wick_size'] = np.nan
    sweeps['wick_qcode'] = np.nan
    wick_valid = sweeps['wick_size'].dropna()
    if wick_valid.empty or wick_valid.nunique() < 2:
        return sweeps, 0

    qcodes = pd.qcut(wick_valid, q=4, labels=False, duplicates='drop')
    if qcodes.empty:
        return sweeps, 0

    n_bins = int(qcodes.max()) + 1
    sweeps.loc[qcodes.index, 'wick_qcode'] = qcodes.astype(float)
    return sweeps, n_bins


def filter_sweeps_by_wick_mode(sweeps_df, wick_mode):
    """Apply wick size filter."""
    sweeps, n_bins = add_wick_quantiles(sweeps_df)
    if wick_mode == 'none':
        return sweeps

    if wick_mode == 'wick_atr_min_0.25':
        return sweeps[(sweeps['atr'] > 0) & (sweeps['wick_size'] >= 0.25 * sweeps['atr'])]
    if wick_mode == 'wick_atr_min_0.50':
        return sweeps[(sweeps['atr'] > 0) & (sweeps['wick_size'] >= 0.50 * sweeps['atr'])]

    if n_bins < 2:
        return sweeps

    qcodes = sweeps['wick_qcode']
    if wick_mode == 'q1_only':
        return sweeps[qcodes == 0]
    if wick_mode == 'q3_q4_only':
        cutoff = int(np.floor(n_bins / 2))
        return sweeps[qcodes >= cutoff]
    if wick_mode == 'exclude_q2':
        return sweeps[qcodes != 1]

    return sweeps


def prepare_data(config):
    """Load and prepare all data files."""
    try:
        mnq5 = load(MNQ_5M)
        mnq1h = load(MNQ_1H)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"MNQ data files not found at {MNQ_5M} or {MNQ_1H}. "
            "Ensure MNQ_continuous_5min.parquet and MNQ_continuous_1H.parquet exist."
        )

    try:
        mes5 = load(MES_5M)
    except FileNotFoundError:
        # MES used for SMT divergence; graceful fallback if not available
        mes5 = pd.DataFrame()

    mnq5['atr'] = compute_atr(mnq5)
    mnq1h['atr'] = compute_atr(mnq1h)

    mnq5['session'] = [label_session(i) for i in mnq5.index]
    mnq1h['session'] = [label_session(i) for i in mnq1h.index]

    mnq1h = swing_pivots(mnq1h, n=config['swing_n'])

    mnq5 = detect_fvg(mnq5)
    mnq5 = detect_ifvg(mnq5)

    return {
        'mnq5': mnq5,
        'mnq1h': mnq1h,
        'mes5': mes5,
    }


def compute_wick_breakdown(tdf, sweeps_all):
    """Break down trades by sweep wick size quartile."""
    out: dict[str, object] = {'message': None, 'table': None}
    if tdf.empty:
        out['message'] = 'No trades to bucket.'
        return out

    wmap = sweeps_all.set_index('time')['wick_size']
    tdf = tdf.copy()
    tdf['wick_size'] = tdf['sweep_time'].map(wmap)
    wick_valid = tdf['wick_size'].dropna()
    if wick_valid.empty or wick_valid.nunique() < 2:
        out['message'] = 'Insufficient wick-size variation for quantile buckets.'
        return out

    qcodes = pd.qcut(wick_valid, q=4, labels=False, duplicates='drop')
    n_bins = int(qcodes.max()) + 1
    labels = ['Q1_small', 'Q2', 'Q3', 'Q4_large'][:n_bins]

    tdf['wick_q'] = pd.Series(index=tdf.index, dtype='object')
    tdf.loc[qcodes.index, 'wick_q'] = qcodes.map(lambda x: labels[int(x)])
    out['table'] = tdf.dropna(subset=['wick_q']).groupby('wick_q', observed=True).agg(
        count=('pnl_r', 'count'),
        win_rate=('outcome', lambda x: (x == 'WIN').mean()),
        avg_r=('pnl_r', 'mean'),
    )
    return out


def simulate_trade(forward, entry_price, stop, target, r_dist, direction, config):
    """
    Simulate trade forward. Supports partial exit and stall exit.

    Returns (outcome, exit_price, pnl_r).
    """
    target_r = config['target_r']
    partial_exit_r = config.get('partial_exit_r', 0.0)
    partial_size = config.get('partial_size', 0.5)
    stall_bars = config.get('stall_bars', 0)
    stall_threshold = config.get('stall_threshold', 0.5)

    current_stop = stop
    partial_fired = False
    leg1_pnl = 0.0
    mfe = 0.0

    if partial_exit_r > 0:
        if direction == 'BEAR':
            partial_price = entry_price - partial_exit_r * r_dist
        else:
            partial_price = entry_price + partial_exit_r * r_dist
    else:
        partial_price = None

    for bars_elapsed, (_, fbar) in enumerate(forward.iterrows(), start=1):
        if direction == 'BEAR':
            mfe = max(mfe, entry_price - fbar['low'])
        else:
            mfe = max(mfe, fbar['high'] - entry_price)

        if partial_price is not None and not partial_fired:
            hit = (direction == 'BEAR' and fbar['low'] <= partial_price) or \
                  (direction == 'BULL' and fbar['high'] >= partial_price)
            if hit:
                partial_fired = True
                leg1_pnl = partial_exit_r * partial_size
                current_stop = entry_price

        stopped = (direction == 'BULL' and fbar['low'] <= current_stop) or \
                  (direction == 'BEAR' and fbar['high'] >= current_stop)
        if stopped:
            ep = current_stop
            if partial_fired:
                pnl = leg1_pnl
            else:
                pnl = -1.0
            return ('WIN' if pnl > 0 else 'LOSS'), ep, pnl

        hit_target = (direction == 'BULL' and fbar['high'] >= target) or \
                     (direction == 'BEAR' and fbar['low'] <= target)
        if hit_target:
            ep = target
            if partial_fired:
                pnl = leg1_pnl + target_r * (1 - partial_size)
            else:
                pnl = target_r
            return 'WIN', ep, pnl

        if stall_bars > 0 and bars_elapsed == stall_bars:
            if mfe < stall_threshold * r_dist:
                ep = float(fbar['close'])
                raw_r = ((entry_price - ep) / r_dist if direction == 'BEAR'
                         else (ep - entry_price) / r_dist)
                pnl = (leg1_pnl + raw_r * (1 - partial_size)) if partial_fired else raw_r
                return 'OPEN', ep, pnl

    ep = float(forward.iloc[-1]['close']) if len(forward) else entry_price
    raw_r = ((entry_price - ep) / r_dist if direction == 'BEAR'
             else (ep - entry_price) / r_dist)
    pnl = (leg1_pnl + raw_r * (1 - partial_size)) if partial_fired else raw_r
    return 'OPEN', ep, pnl


def run_backtest(data, config):
    """Run backtest with given config."""
    mnq5 = data['mnq5']
    mnq1h = data['mnq1h']
    mes5 = data['mes5']

    sweeps_all = detect_sweeps(
        mnq1h,
        allowed_sessions=config['allowed_sessions'],
        allowed_dir=config['allowed_dir'],
        tf_label='1H',
        lookback=config['sweep_lookback'],
    )
    sweeps_for_trading = filter_sweeps_by_wick_mode(sweeps_all, config['wick_mode'])

    trades = []
    skipped_r = 0
    skipped_chain = 0

    for _, sweep in sweeps_for_trading.iterrows():
        sweep_time = sweep['time']
        direction = sweep['direction']
        level = float(sweep['level'])
        session = sweep['session']
        is_2b = session in ('ASIA', 'LONDON', 'NY_PRE', 'AFTER')

        sw_bar = mnq1h[mnq1h.index == sweep_time]
        sweep_close = float(sw_bar['close'].iloc[0]) if len(sw_bar) else np.nan

        window = mnq5[mnq5.index > sweep_time].head(config['signal_window'])
        if len(window) < 4:
            continue

        # SMT gracefully handles missing MES
        if not mes5.empty:
            mes_win = mes5.reindex(window.index, method='ffill').ffill()
            smt_arr = detect_smt(mes_win, mnq5.reindex(window.index, method='ffill').ffill(), direction)
        else:
            smt_arr = np.zeros(len(window))

        eq_arr = detect_eq_retrace(window, direction, sweep_close) if not np.isnan(sweep_close) else np.zeros(
            len(window))

        conf2, conf3, conf4 = build_confirmations(
            window, direction, smt_arr, eq_arr, is_2b, config['chain_mode']
        )

        entry_bar = find_entry_bar(conf2, conf3, conf4, config['chain_mode'])
        if entry_bar is None:
            skipped_chain += 1
            continue

        entry_row = window.iloc[entry_bar]
        entry_price = float(entry_row['close'])
        atr_val = float(entry_row['atr']) if not np.isnan(entry_row['atr']) else 0.5

        if config['stop_mode'] == '5m_lower_high':
            lh_stop = find_5m_lower_high_stop(
                window, entry_bar, direction, atr_val,
                lh_lookback=config['lh_lookback'],
                lh_buffer_mult=config['lh_buffer_mult'],
            )
        else:
            lh_stop = None

        if direction == 'BULL':
            sweep_atr_stop = level - atr_val * config['atr_mult_stop']
            stop = lh_stop if lh_stop is not None else sweep_atr_stop
            r_dist = entry_price - stop
        else:
            sweep_atr_stop = level + atr_val * config['atr_mult_stop']
            stop = lh_stop if lh_stop is not None else sweep_atr_stop
            r_dist = stop - entry_price

        if r_dist < config['min_r_dist']:
            skipped_r += 1
            continue

        target = (
            entry_price + config['target_r'] * r_dist
            if direction == 'BULL'
            else entry_price - config['target_r'] * r_dist
        )

        forward = mnq5[mnq5.index > entry_row.name].head(config['max_hold_bars'])
        outcome, exit_price, pnl_r = simulate_trade(
            forward, entry_price, stop, target, r_dist, direction, config
        )

        trades.append({
            'entry_time': entry_row.name,
            'sweep_time': sweep_time,
            'direction': direction,
            'session': session,
            'tf': sweep['tf'],
            'entry': entry_price,
            'stop': stop,
            'target': target,
            'r_dist': r_dist,
            'exit_price': exit_price,
            'pnl_r': pnl_r,
            'outcome': outcome,
        })

    funnel = {
        'sweeps_total': int(len(sweeps_all)),
        'sweeps_after_wick_filter': int(len(sweeps_for_trading)),
        'skipped_chain': int(skipped_chain),
        'skipped_r_dist': int(skipped_r),
        'converted_to_trade': int(len(trades)),
    }

    if not trades:
        return {
            'config': dict(config),
            'funnel': funnel,
            'sweeps_all': sweeps_all,
            'trades_df': pd.DataFrame(),
            'metrics': {
                'sample_size': 0,
                'win_rate': np.nan,
                'avg_win_r': np.nan,
                'avg_loss_r': np.nan,
                'total_r': np.nan,
                'avg_r_per_trade': np.nan,
                'profit_factor': np.nan,
                'sharpe': np.nan,
                'max_drawdown_r': np.nan,
                'ic': np.nan,
                'breakeven_win_rate': round(1 / (1 + config['target_r']), 6),
            },
            'session_stats': None,
            'wick_breakdown': {'message': 'No trades to bucket.', 'table': None},
            'monthly': None,
        }

    tdf = pd.DataFrame(trades).sort_values('entry_time').reset_index(drop=True)
    n = len(tdf)

    wins = tdf[tdf['outcome'] == 'WIN']
    losses = tdf[tdf['outcome'] == 'LOSS']

    win_rate = len(wins) / n
    avg_win_r = wins['pnl_r'].mean() if len(wins) else 0.0
    avg_loss_r = losses['pnl_r'].mean() if len(losses) else 0.0
    total_r = tdf['pnl_r'].sum()
    avg_r = tdf['pnl_r'].mean()
    profit_factor = (
        wins['pnl_r'].sum() / abs(losses['pnl_r'].sum())
        if len(losses) and losses['pnl_r'].sum() != 0
        else np.nan
    )

    tdf['cum_r'] = tdf['pnl_r'].cumsum()
    r_std = tdf['pnl_r'].std(ddof=1)
    sharpe = (avg_r / r_std * np.sqrt(252)) if r_std > 0 else 0.0
    max_dd = (tdf['cum_r'] - tdf['cum_r'].cummax()).min()

    tdf['sig_dir'] = tdf['direction'].map({'BULL': 1, 'BEAR': -1})
    out_dir = pd.Series(np.sign(tdf['pnl_r']), index=tdf.index)
    if n >= 10 and tdf['sig_dir'].nunique() > 1 and out_dir.nunique() > 1:
        if stats is not None:
            ic_val = stats.spearmanr(tdf['sig_dir'], out_dir).statistic
        else:
            ic_val = tdf['sig_dir'].corr(out_dir, method='spearman')
    else:
        ic_val = np.nan

    session_stats = tdf.groupby('session').agg(
        count=('pnl_r', 'count'),
        win_rate=('outcome', lambda x: (x == 'WIN').mean()),
        avg_r=('pnl_r', 'mean'),
        total_r=('pnl_r', 'sum'),
    )

    monthly = tdf.set_index('entry_time').copy()
    monthly_index = monthly.index
    if getattr(monthly_index, 'tz', None) is not None:
        monthly.index = monthly_index.tz_localize(None)
    monthly = monthly['pnl_r'].resample('M').sum()

    return {
        'config': dict(config),
        'funnel': funnel,
        'sweeps_all': sweeps_all,
        'trades_df': tdf,
        'metrics': {
            'sample_size': int(n),
            'win_rate': float(win_rate),
            'avg_win_r': float(avg_win_r),
            'avg_loss_r': float(avg_loss_r),
            'total_r': float(total_r),
            'avg_r_per_trade': float(avg_r),
            'profit_factor': float(profit_factor) if not np.isnan(profit_factor) else np.nan,
            'sharpe': float(sharpe),
            'max_drawdown_r': float(max_dd),
            'ic': float(ic_val) if not np.isnan(ic_val) else np.nan,
            'breakeven_win_rate': round(1 / (1 + config['target_r']), 6),
        },
        'session_stats': session_stats,
        'wick_breakdown': compute_wick_breakdown(tdf, sweeps_all),
        'monthly': monthly,
    }


def print_backtest_report(result, loaded_rows):
    """Print comprehensive backtest report."""
    metrics = result['metrics']
    funnel = result['funnel']

    print(f"loaded_rows: mnq5={loaded_rows['mnq5']} mnq1h={loaded_rows['mnq1h']} "
          f"mes5={loaded_rows['mes5']}")
    print(f"Total qualifying sweeps: {funnel['sweeps_total']}")
    if not result['sweeps_all'].empty:
        print("\n--- Sweeps by Session ---")
        print(result['sweeps_all']['session'].value_counts().to_string())

    print('\n--- Confirmation Chain Funnel ---')
    print(f"sweeps_total: {funnel['sweeps_total']}")
    print(f"sweeps_after_wick_filter: {funnel['sweeps_after_wick_filter']}")
    print(f"skipped_chain: {funnel['skipped_chain']}")
    print(f"skipped_r_dist: {funnel['skipped_r_dist']}")
    print(f"converted_to_trade: {funnel['converted_to_trade']}")

    if metrics['sample_size'] == 0:
        print('\nsample_size: 0 — No trades generated. Check sweep detection and confirmation settings.')
        return

    print(f"\nsample_size: {metrics['sample_size']}")
    print(f"win_rate: {metrics['win_rate']:.6f}")
    print(f"avg_win_r: {metrics['avg_win_r']:.6f}")
    print(f"avg_loss_r: {metrics['avg_loss_r']:.6f}")
    print(f"total_r: {metrics['total_r']:.6f}")
    print(f"avg_r_per_trade: {metrics['avg_r_per_trade']:.6f}")
    print(f"profit_factor: {metrics['profit_factor']:.6f}")
    print(f"sharpe: {metrics['sharpe']:.6f}")
    print(f"max_drawdown_r: {metrics['max_drawdown_r']:.6f}")
    print(f"ic: {metrics['ic']:.6f}" if not np.isnan(metrics['ic']) else 'ic: nan')
    print(f"breakeven_win_rate: {metrics['breakeven_win_rate']:.6f}")

    print('\n--- Session Breakdown ---')
    if result['session_stats'] is not None and not result['session_stats'].empty:
        print(result['session_stats'].to_string())
    else:
        print("No session data.")

    print('\n--- Wick Size Quartiles (sweep quality) ---')
    wick = result['wick_breakdown']
    if wick['table'] is None:
        print(wick['message'])
    else:
        print(wick['table'].to_string())

    print('\n--- Monthly P&L (R) ---')
    if result['monthly'] is not None and not result['monthly'].empty:
        print(result['monthly'].to_string())
    else:
        print("No monthly data.")

    n = metrics['sample_size']
    if n < 20:
        print(f"\nInterpretation: n={n} below minimum of 20. Insufficient data for Phase 1 gate.")
    elif n < 30:
        print(f"\nInterpretation: n={n} is thin. Wick size quartiles show which sweep quality matters most.")
    elif metrics['win_rate'] >= metrics['breakeven_win_rate'] and metrics['sharpe'] > 0:
        print(
            f"\nInterpretation: Cleared {metrics['breakeven_win_rate']:.4f} breakeven at "
            f"{result['config']['target_r']}R. NQ bear sweep 1H strategy shows positive expectancy — "
            'proceed to Phase 2 isolation or Phase 3 grid search.'
        )
    else:
        print(
            '\nInterpretation: Below breakeven. Check session breakdown — if specific sessions '
            'carry the signal, isolate them in Phase 2.'
        )


def run_grid_search(data, base_config, target_r_list, wick_modes, atr_stops, sessions_list, output_csv):
    """Run grid search across parameter combinations."""
    results = []
    combo_count = 0

    for sessions_str in sessions_list:
        sessions = parse_str_list(sessions_str)
        for tr in target_r_list:
            for wm in wick_modes:
                for atr in atr_stops:
                    combo_count += 1
                    config = dict(base_config)
                    config['target_r'] = tr
                    config['wick_mode'] = wm
                    config['atr_mult_stop'] = atr
                    config['allowed_sessions'] = sessions

                    result = run_backtest(data, config)
                    metrics = result['metrics']

                    results.append({
                        'sessions': ','.join(sessions),
                        'target_r': tr,
                        'wick_mode': wm,
                        'atr_mult_stop': atr,
                        'n': metrics['sample_size'],
                        'win_rate': metrics['win_rate'],
                        'avg_r': metrics['avg_r_per_trade'],
                        'total_r': metrics['total_r'],
                        'profit_factor': metrics['profit_factor'],
                        'sharpe': metrics['sharpe'],
                        'max_dd': metrics['max_drawdown_r'],
                    })

                    print(f"Grid combo {combo_count}: sessions={','.join(sessions)}, "
                          f"target_r={tr}, wick={wm}, atr={atr} -> "
                          f"n={metrics['sample_size']}, sharpe={metrics['sharpe']:.3f}, "
                          f"total_r={metrics['total_r']:.2f}")

    results.sort(key=lambda x: x['sharpe'], reverse=True)

    results_df = pd.DataFrame(results)
    output_path = write_results_csv(results_df, output_csv, artifact_name='grid results CSV')

    print(f"\nGrid search complete: {combo_count} combos, results saved to {output_path}")
    print("\nTop 10 by Sharpe:")
    print("=" * 120)
    for i, r in enumerate(results[:10], 1):
        print(f"{i:2d}. sessions={r['sessions']:20s} tr={r['target_r']:.2f} wick={r['wick_mode']:15s} "
              f"atr={r['atr_mult_stop']:.1f} | n={r['n']:3d} wr={r['win_rate']:.1%} "
              f"total_r={r['total_r']:+.2f} pf={r['profit_factor']:.2f} sharpe={r['sharpe']:.3f} "
              f"max_dd={r['max_dd']:.1f}")
    print("=" * 120)

    return results


def build_arg_parser():
    """Build argument parser for CLI overrides."""
    parser = argparse.ArgumentParser(description='NQ Bear Sweep 1H Baseline Backtest')
    parser.add_argument('--results-csv', default='results/nq_bear_sweep_1h_baseline.csv', help='Output CSV path')

    # Grid mode
    parser.add_argument('--grid', action='store_true', help='Run grid search mode')
    parser.add_argument('--target-r-grid', type=str, default='1.0,1.25,1.5,1.75', help='Comma-separated target_r values for grid')
    parser.add_argument('--wick-modes', type=str, default='none,exclude_q2,q3_q4_only', help='Comma-separated wick modes for grid')
    parser.add_argument('--atr-mult-stop-grid', type=str, default='0.3,0.5,0.7', help='Comma-separated ATR multipliers for grid')
    parser.add_argument('--sessions-grid', type=str, default='NY_PRE;NY_PRE,LONDON', help='Semicolon-separated session combos for grid')

    # Single-run overrides
    parser.add_argument('--target-r', type=float, default=None, help='Single-run target R override')
    parser.add_argument('--min-r-dist', type=float, default=None, help='Single-run min R distance override')
    parser.add_argument('--chain-mode', type=str, default=None, help='Single-run chain mode override')
    parser.add_argument('--wick-mode', type=str, default=None, help='Single-run wick mode override')
    parser.add_argument('--max-hold-bars', type=int, default=None, help='Single-run max hold bars override')
    parser.add_argument('--stop-mode', type=str, default=None, help='Single-run stop mode: sweep_atr | 5m_lower_high')
    parser.add_argument('--lh-lookback', type=int, default=None, help='Bars before entry to scan for 5m lower high (default 5)')
    parser.add_argument('--lh-buffer-mult', type=float, default=None, help='ATR fraction added above local high as stop buffer (default 0.10)')
    parser.add_argument('--partial-exit-r', type=float, default=None, help='Single-run partial exit R level (0 = disabled)')
    parser.add_argument('--stall-bars', type=int, default=None, help='Single-run stall exit bar count (0 = disabled)')
    parser.add_argument('--stall-threshold', type=float, default=None, help='Single-run stall MFE threshold as fraction of r_dist (default 0.5)')
    parser.add_argument('--allowed-sessions', type=str, default=None, help='Comma-separated session list (ASIA,LONDON,NY_PRE,NY,AFTER)')
    parser.add_argument('--atr-mult-stop', type=float, default=None, help='ATR multiplier for stop placement (default 0.5)')
    
    return parser


def main():
    """Main entry point."""
    parser = build_arg_parser()
    args = parser.parse_args()

    config = dict(DEFAULT_CONFIG)
    
    # Apply CLI overrides
    if args.target_r is not None:
        config['target_r'] = args.target_r
    if args.min_r_dist is not None:
        config['min_r_dist'] = args.min_r_dist
    if args.chain_mode is not None:
        config['chain_mode'] = args.chain_mode
    if args.wick_mode is not None:
        config['wick_mode'] = args.wick_mode
    if args.max_hold_bars is not None:
        config['max_hold_bars'] = args.max_hold_bars
    if args.stop_mode is not None:
        config['stop_mode'] = args.stop_mode
    if args.lh_lookback is not None:
        config['lh_lookback'] = args.lh_lookback
    if args.lh_buffer_mult is not None:
        config['lh_buffer_mult'] = args.lh_buffer_mult
    if args.partial_exit_r is not None:
        config['partial_exit_r'] = args.partial_exit_r
    if args.stall_bars is not None:
        config['stall_bars'] = args.stall_bars
    if args.stall_threshold is not None:
        config['stall_threshold'] = args.stall_threshold
    if args.allowed_sessions is not None:
        config['allowed_sessions'] = parse_str_list(args.allowed_sessions)
    if args.atr_mult_stop is not None:
        config['atr_mult_stop'] = args.atr_mult_stop

    try:
        data = prepare_data(config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # Grid search mode
    if args.grid:
        target_r_list = parse_float_list(args.target_r_grid)
        wick_modes = parse_str_list(args.wick_modes)
        atr_stops = parse_float_list(args.atr_mult_stop_grid)
        sessions_list = args.sessions_grid.split(';')

        run_grid_search(data, config, target_r_list, wick_modes, atr_stops, sessions_list, args.results_csv)
        return

    loaded_rows = {
        'mnq5': len(data['mnq5']),
        'mnq1h': len(data['mnq1h']),
        'mes5': len(data['mes5']),
    }

    result = run_backtest(data, config)
    print_backtest_report(result, loaded_rows)
    summary_csv = build_baseline_summary_for_csv(
        result,
        instrument='NQ',
        timeframe='1H',
        direction='bear',
    )
    output_path = write_results_csv(summary_csv, args.results_csv, artifact_name='baseline summary CSV')
    print(f"\nBaseline results saved to {output_path}")


if __name__ == '__main__':
    main()









