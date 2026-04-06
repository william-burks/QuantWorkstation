import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy import stats
except Exception:  # pragma: no cover - optional dependency fallback
    stats = None

# PATHS
BASE = Path('/Users/will/quant-research/data/futures')
CL_5M = BASE / 'CL_continuous_5min.parquet'
CL_1H = BASE / 'CL_continuous_1H.parquet'
MES_5M = BASE / 'MES_continuous_5min.parquet'
MNQ_5M = BASE / 'MNQ_continuous_5min.parquet'

# PARAMETERS — baseline profile
DEFAULT_CONFIG = {
    'signal_window': 36,
    'atr_mult_stop': 0.5,
    'target_r': 1.5,
    'max_hold_bars': 36,
    'allowed_sessions': ['NY_PRE', 'AFTER'],
    'allowed_dir': ['BEAR'],
    'swing_n': 3,
    'min_r_dist': 0.10,
    'chain_mode': 'baseline_relaxed',
    'wick_mode': 'none',
    'sweep_lookback': 50,
    # stop_mode:
    #   'sweep_atr'      — original: sweep_level + atr_mult_stop * ATR
    #   '5m_lower_high'  — tighter: most recent 5m local high before entry + small ATR buffer
    'stop_mode': 'sweep_atr',
    'lh_lookback': 5,
    'lh_buffer_mult': 0.10,
    # partial exit: take partial_size of position off at partial_exit_r * r_dist,
    # then move stop to breakeven; 0 = disabled
    'partial_exit_r': 0.0,
    'partial_size': 0.5,
    # stall exit: if price hasn't moved past stall_threshold * r_dist favorably
    # after stall_bars bars, close at market; 0 = disabled
    'stall_bars': 0,
    'stall_threshold': 0.5,
}


def load(path):
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert('US/Eastern')
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.sort_index()


def compute_atr(df, period=14):
    hi = df['high']
    lo = df['low']
    pc = df['close'].shift(1)
    tr = pd.concat([(hi - lo), (hi - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def label_session(idx):
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
    Tighter stop based on the most recent local extreme on the 5m chart before entry.

    BEAR: stop = max(high) over the last lh_lookback bars before entry + lh_buffer_mult * ATR
    BULL: stop = min(low)  over the last lh_lookback bars before entry - lh_buffer_mult * ATR

    Returns None if there are not enough pre-entry bars; caller falls back to sweep_atr stop.
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
    cl5 = load(CL_5M)
    cl1h = load(CL_1H)
    mes5 = load(MES_5M)
    mnq5 = load(MNQ_5M)

    cl5['atr'] = compute_atr(cl5)
    cl1h['atr'] = compute_atr(cl1h)

    cl5['session'] = [label_session(i) for i in cl5.index]
    cl1h['session'] = [label_session(i) for i in cl1h.index]

    cl1h = swing_pivots(cl1h, n=config['swing_n'])

    cl5 = detect_fvg(cl5)
    cl5 = detect_ifvg(cl5)

    return {
        'cl5': cl5,
        'cl1h': cl1h,
        'mes5': mes5,
        'mnq5': mnq5,
    }


def compute_wick_breakdown(tdf, sweeps_all):
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
    Walk forward bars simulating the trade with optional partial exit and stall exit.

    Partial exit (partial_exit_r > 0):
      - When price reaches partial_exit_r * r_dist in the favorable direction,
        exit partial_size fraction of the position and move stop to breakeven.
      - Remaining portion runs to full target or is stopped at breakeven.

    Stall exit (stall_bars > 0):
      - After stall_bars bars, if MFE < stall_threshold * r_dist, close at market.
      - Fires before the regular max_hold time exit.

    Outcome semantics:
      - WIN  = full target hit, or partial taken then remainder stopped at breakeven
      - LOSS = full stop hit before any partial
      - OPEN = timed/stall market exit without a hard stop/target resolution

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
    mfe = 0.0  # max favorable excursion in price units

    if partial_exit_r > 0:
        if direction == 'BEAR':
            partial_price = entry_price - partial_exit_r * r_dist
        else:
            partial_price = entry_price + partial_exit_r * r_dist
    else:
        partial_price = None

    for bars_elapsed, (_, fbar) in enumerate(forward.iterrows(), start=1):
        # Track MFE
        if direction == 'BEAR':
            mfe = max(mfe, entry_price - fbar['low'])
        else:
            mfe = max(mfe, fbar['high'] - entry_price)

        # Partial exit — checked first in bar (conservative: only fires if bar reached level)
        if partial_price is not None and not partial_fired:
            hit = (direction == 'BEAR' and fbar['low'] <= partial_price) or \
                  (direction == 'BULL' and fbar['high'] >= partial_price)
            if hit:
                partial_fired = True
                leg1_pnl = partial_exit_r * partial_size
                current_stop = entry_price  # move stop to breakeven

        # Stop check
        stopped = (direction == 'BULL' and fbar['low'] <= current_stop) or \
                  (direction == 'BEAR' and fbar['high'] >= current_stop)
        if stopped:
            ep = current_stop
            if partial_fired:
                pnl = leg1_pnl  # leg2 = 0 (stopped at BE)
            else:
                pnl = -1.0
            return ('WIN' if pnl > 0 else 'LOSS'), ep, pnl

        # Full target check
        hit_target = (direction == 'BULL' and fbar['high'] >= target) or \
                     (direction == 'BEAR' and fbar['low'] <= target)
        if hit_target:
            ep = target
            if partial_fired:
                pnl = leg1_pnl + target_r * (1 - partial_size)
            else:
                pnl = target_r
            return 'WIN', ep, pnl

        # Stall exit — fires at exactly stall_bars elapsed
        if stall_bars > 0 and bars_elapsed == stall_bars:
            if mfe < stall_threshold * r_dist:
                ep = float(fbar['close'])
                raw_r = ((entry_price - ep) / r_dist if direction == 'BEAR'
                         else (ep - entry_price) / r_dist)
                pnl = (leg1_pnl + raw_r * (1 - partial_size)) if partial_fired else raw_r
                return 'OPEN', ep, pnl

    # Time exit
    ep = float(forward.iloc[-1]['close']) if len(forward) else entry_price
    raw_r = ((entry_price - ep) / r_dist if direction == 'BEAR'
             else (ep - entry_price) / r_dist)
    pnl = (leg1_pnl + raw_r * (1 - partial_size)) if partial_fired else raw_r
    return 'OPEN', ep, pnl


def run_backtest(data, config):
    cl5 = data['cl5']
    cl1h = data['cl1h']
    mes5 = data['mes5']
    mnq5 = data['mnq5']

    sweeps_all = detect_sweeps(
        cl1h,
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

        sw_bar = cl1h[cl1h.index == sweep_time]
        sweep_close = float(sw_bar['close'].iloc[0]) if len(sw_bar) else np.nan

        window = cl5[cl5.index > sweep_time].head(config['signal_window'])
        if len(window) < 4:
            continue

        mes_win = mes5.reindex(window.index, method='ffill').infer_objects(copy=False).ffill()
        mnq_win = mnq5.reindex(window.index, method='ffill').infer_objects(copy=False).ffill()
        smt_arr = detect_smt(mes_win, mnq_win, direction)
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

        # ── Stop placement ────────────────────────────────────────────────
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

        forward = cl5[cl5.index > entry_row.name].head(config['max_hold_bars'])
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
    monthly = monthly['pnl_r'].resample('ME').sum()

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
    metrics = result['metrics']
    funnel = result['funnel']

    print(f"loaded_rows: {loaded_rows['cl5']} {loaded_rows['cl1h']} {loaded_rows['mes5']} {loaded_rows['mnq5']}")
    print(f"Total qualifying sweeps: {funnel['sweeps_total']}")
    if not result['sweeps_all'].empty:
        print(result['sweeps_all']['session'].value_counts().to_string())

    print('\n--- Confirmation Chain Funnel ---')
    print(f"sweeps_total: {funnel['sweeps_total']}")
    print(f"sweeps_after_wick_filter: {funnel['sweeps_after_wick_filter']}")
    print(f"skipped_chain: {funnel['skipped_chain']}")
    print(f"skipped_r_dist: {funnel['skipped_r_dist']}")
    print(f"converted_to_trade: {funnel['converted_to_trade']}")

    if metrics['sample_size'] == 0:
        print('\nsample_size: 0')
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
    print(result['session_stats'].to_string())

    print('\n--- Wick Size Quartiles (sweep quality) ---')
    wick = result['wick_breakdown']
    if wick['table'] is None:
        print(wick['message'])
    else:
        print(wick['table'].to_string())

    print('\n--- Monthly P&L (R) ---')
    print(result['monthly'].to_string())

    n = metrics['sample_size']
    if n < 30:
        print(f"\nInterpretation: n={n} still thin. Wick size quartiles show which sweep quality matters most.")
    elif metrics['win_rate'] >= metrics['breakeven_win_rate'] and metrics['sharpe'] > 0:
        print(
            f"\nInterpretation: Cleared {metrics['breakeven_win_rate']} breakeven at "
            f"{result['config']['target_r']}R. BEAR-only NY_PRE+AFTER 1H sweep strategy has positive expectancy "
            '— proceed to out-of-sample validation.'
        )
    else:
        print(
            '\nInterpretation: Below breakeven. Check wick size quartiles — if Q3/Q4 large wicks win more, '
            'add a minimum wick size filter (e.g. wick > 0.5 ATR) to remove weak sweeps.'
        )


def parse_float_list(raw):
    return [float(x.strip()) for x in raw.split(',') if x.strip()]


def parse_str_list(raw):
    return [x.strip() for x in raw.split(',') if x.strip()]


def run_grid(data, base_config, args):
    target_rs = parse_float_list(args.target_r_grid)
    min_r_dists = parse_float_list(args.min_r_dist_grid)
    chain_modes = parse_str_list(args.chain_modes)
    wick_modes = parse_str_list(args.wick_modes)
    stop_modes = parse_str_list(args.stop_modes)
    partial_exit_rs = parse_float_list(args.partial_exit_r_grid)
    stall_bars_list = [int(x) for x in parse_float_list(args.stall_bars_grid)]

    rows = []
    for target_r, min_r_dist, chain_mode, wick_mode, stop_mode, partial_exit_r, stall_bars in itertools.product(
            target_rs, min_r_dists, chain_modes, wick_modes, stop_modes, partial_exit_rs, stall_bars_list
    ):
        cfg = dict(base_config)
        cfg['target_r'] = target_r
        cfg['min_r_dist'] = min_r_dist
        cfg['chain_mode'] = chain_mode
        cfg['wick_mode'] = wick_mode
        cfg['stop_mode'] = stop_mode
        cfg['partial_exit_r'] = partial_exit_r
        cfg['stall_bars'] = stall_bars

        result = run_backtest(data, cfg)
        m = result['metrics']
        f = result['funnel']

        rows.append({
            'target_r': target_r,
            'min_r_dist': min_r_dist,
            'chain_mode': chain_mode,
            'wick_mode': wick_mode,
            'stop_mode': stop_mode,
            'partial_exit_r': partial_exit_r,
            'stall_bars': stall_bars,
            'sample_size': m['sample_size'],
            'win_rate': m['win_rate'],
            'avg_r_per_trade': m['avg_r_per_trade'],
            'total_r': m['total_r'],
            'profit_factor': m['profit_factor'],
            'sharpe': m['sharpe'],
            'max_drawdown_r': m['max_drawdown_r'],
            'breakeven_win_rate': m['breakeven_win_rate'],
            'sweeps_total': f['sweeps_total'],
            'sweeps_after_wick_filter': f['sweeps_after_wick_filter'],
            'skipped_chain': f['skipped_chain'],
            'skipped_r_dist': f['skipped_r_dist'],
            'converted_to_trade': f['converted_to_trade'],
        })

    out_df = pd.DataFrame(rows)
    out_df = out_df.sort_values(['sharpe', 'total_r', 'sample_size'], ascending=[False, False, False])

    out_path = Path(args.results_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    print(f"grid_runs: {len(out_df)}")
    print(f"results_csv: {out_path}")
    print('\n--- Top 10 by Sharpe ---')
    cols = [
        'target_r', 'min_r_dist', 'chain_mode', 'wick_mode', 'stop_mode',
        'partial_exit_r', 'stall_bars',
        'sample_size', 'win_rate', 'avg_r_per_trade',
        'total_r', 'profit_factor', 'sharpe', 'max_drawdown_r',
    ]
    print(out_df.head(10)[cols].to_string(index=False))


def build_arg_parser():
    parser = argparse.ArgumentParser(description='Liquidity sweep strategy backtest and grid runner')
    parser.add_argument('--grid', action='store_true', help='Run parameter grid and save CSV summary')
    parser.add_argument('--results-csv', default='results/grid_results.csv', help='Output CSV path for --grid mode')

    parser.add_argument('--target-r', type=float, default=None, help='Single-run target R override')
    parser.add_argument('--min-r-dist', type=float, default=None, help='Single-run min R distance override')
    parser.add_argument('--chain-mode', type=str, default=None, help='Single-run chain mode override')
    parser.add_argument('--wick-mode', type=str, default=None, help='Single-run wick mode override')
    parser.add_argument('--max-hold-bars', type=int, default=None, help='Single-run max hold bars override')
    parser.add_argument('--stop-mode', type=str, default=None,
                        help='Single-run stop mode: sweep_atr | 5m_lower_high')
    parser.add_argument('--lh-lookback', type=int, default=None,
                        help='Bars before entry to scan for 5m lower high (default 5)')
    parser.add_argument('--lh-buffer-mult', type=float, default=None,
                        help='ATR fraction added above local high as stop buffer (default 0.10)')
    parser.add_argument('--partial-exit-r', type=float, default=None,
                        help='Single-run partial exit R level (0 = disabled)')
    parser.add_argument('--stall-bars', type=int, default=None,
                        help='Single-run stall exit bar count (0 = disabled)')
    parser.add_argument('--stall-threshold', type=float, default=None,
                        help='Single-run stall MFE threshold as fraction of r_dist (default 0.5)')

    parser.add_argument('--target-r-grid', default='1.0,1.25,1.5,1.75,2.0,2.5', help='Comma-separated TARGET_R list')
    parser.add_argument('--min-r-dist-grid', default='0.10', help='Comma-separated MIN_R_DIST list')
    parser.add_argument('--chain-modes', default='baseline_relaxed', help='Comma-separated chain modes')
    parser.add_argument('--wick-modes', default='none', help='Comma-separated wick modes')
    parser.add_argument('--stop-modes', default='sweep_atr',
                        help='Comma-separated stop modes: sweep_atr,5m_lower_high')
    parser.add_argument('--partial-exit-r-grid', default='0.0',
                        help='Comma-separated partial exit R levels (0 = disabled)')
    parser.add_argument('--stall-bars-grid', default='0',
                        help='Comma-separated stall bar counts (0 = disabled)')
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    config = dict(DEFAULT_CONFIG)
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

    data = prepare_data(config)
    loaded_rows = {
        'cl5': len(data['cl5']),
        'cl1h': len(data['cl1h']),
        'mes5': len(data['mes5']),
        'mnq5': len(data['mnq5']),
    }

    if args.grid:
        run_grid(data, config, args)
    else:
        result = run_backtest(data, config)
        print_backtest_report(result, loaded_rows)


if __name__ == '__main__':
    main()
