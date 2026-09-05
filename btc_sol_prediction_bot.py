
"""
BTC/SOL Prediction Bot — Prediction Only
-----------------------------------------
No trading, no API keys, no order execution.

It downloads public Binance spot candlesticks and calculates a simple
multi-factor score using:
- EMA trend
- RSI
- MACD
- volume
- ATR
- recent support/resistance
- BTC direction as a filter for SOL

It prints a prediction for the next horizon and can save every prediction
to predictions.csv for later accuracy testing.

Install:
    pip install requests pandas numpy

Run:
    python btc_sol_prediction_bot.py

Optional:
    python btc_sol_prediction_bot.py --interval 5m --horizon 30
"""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = "https://api.binance.com"
SYMBOLS = ["BTCUSDT", "SOLUSDT"]
CSV = Path("predictions.csv")


def get_klines(symbol, interval="5m", limit=500):
    url = f"{BASE}/api/v3/klines"
    r = requests.get(
        url,
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    r.raise_for_status()
    raw = r.json()

    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ]
    df = pd.DataFrame(raw, columns=cols)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df


def indicators(df):
    x = df.copy()

    x["ema20"] = x.close.ewm(span=20, adjust=False).mean()
    x["ema50"] = x.close.ewm(span=50, adjust=False).mean()

    delta = x.close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    x["rsi"] = 100 - (100 / (1 + rs))

    ema12 = x.close.ewm(span=12, adjust=False).mean()
    ema26 = x.close.ewm(span=26, adjust=False).mean()
    x["macd"] = ema12 - ema26
    x["macd_signal"] = x.macd.ewm(span=9, adjust=False).mean()
    x["macd_hist"] = x.macd - x.macd_signal

    prev_close = x.close.shift(1)
    tr = pd.concat(
        [
            x.high - x.low,
            (x.high - prev_close).abs(),
            (x.low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    x["atr"] = tr.rolling(14).mean()

    x["vol_ma20"] = x.volume.rolling(20).mean()
    x["volume_ratio"] = x.volume / x.vol_ma20

    x["support20"] = x.low.rolling(20).min()
    x["resistance20"] = x.high.rolling(20).max()

    return x.dropna().reset_index(drop=True)


def score_asset(df, btc_df=None):
    x = indicators(df)
    r = x.iloc[-1]
    prev = x.iloc[-2]

    score = 0.0
    reasons = []

    # Trend
    if r.ema20 > r.ema50:
        score += 25
        reasons.append("EMA20 فوق EMA50")
    else:
        score -= 25
        reasons.append("EMA20 تحت EMA50")

    # MACD momentum
    if r.macd_hist > 0 and r.macd_hist >= prev.macd_hist:
        score += 20
        reasons.append("MACD يتحسن")
    elif r.macd_hist < 0 and r.macd_hist <= prev.macd_hist:
        score -= 20
        reasons.append("MACD يضعف")
    else:
        reasons.append("MACD مختلط")

    # RSI
    if 50 <= r.rsi <= 68:
        score += 15
        reasons.append(f"RSI داعم للصعود ({r.rsi:.1f})")
    elif 32 <= r.rsi < 50:
        score -= 10
        reasons.append(f"RSI ضعيف ({r.rsi:.1f})")
    elif r.rsi > 75:
        score -= 12
        reasons.append(f"RSI مرتفع جدًا ({r.rsi:.1f})")
    elif r.rsi < 25:
        score += 8
        reasons.append(f"RSI منخفض جدًا ({r.rsi:.1f})")

    # Volume
    if r.volume_ratio >= 1.3:
        score += 10 if r.close >= r.open else -10
        reasons.append(f"حجم مرتفع x{r.volume_ratio:.1f}")
    else:
        reasons.append("الحجم عادي")

    # BTC filter for SOL
    if btc_df is not None:
        b = indicators(btc_df).iloc[-1]
        if b.ema20 > b.ema50:
            score += 10
            reasons.append("BTC اتجاهه داعم")
        else:
            score -= 10
            reasons.append("BTC اتجاهه ضاغط")

    score = float(np.clip(score, -100, 100))
    direction = "UP" if score > 10 else "DOWN" if score < -10 else "NEUTRAL"

    # Confidence is deliberately capped; this is NOT a probability guarantee.
    confidence = 50 + abs(score) * 0.40
    confidence = float(np.clip(confidence, 50, 90))

    price = float(r.close)
    atr = float(r.atr)

    if direction == "UP":
        target = price + 1.25 * atr
        invalidation = price - 0.85 * atr
    elif direction == "DOWN":
        target = price - 1.25 * atr
        invalidation = price + 0.85 * atr
    else:
        target = price
        invalidation = price

    return {
        "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbol": df.attrs.get("symbol", ""),
        "price": price,
        "direction": direction,
        "confidence": round(confidence, 1),
        "target": target,
        "invalidation": invalidation,
        "rsi": float(r.rsi),
        "atr": atr,
        "score": round(score, 1),
        "reasons": " | ".join(reasons),
    }


def save_prediction(result):
    row = pd.DataFrame([result])
    header = not CSV.exists()
    row.to_csv(CSV, mode="a", index=False, header=header)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="5m", choices=["1m", "3m", "5m", "15m", "30m", "1h", "4h"])
    ap.add_argument("--horizon", type=int, default=30, help="Target horizon in minutes (label only)")
    ap.add_argument("--once", action="store_true", help="Run one prediction and exit")
    ap.add_argument("--every", type=int, default=5, help="Minutes between predictions")
    args = ap.parse_args()

    print("BTC/SOL Prediction Bot — prediction only")
    print("No orders will be placed. No API keys are used.")
    print(f"Interval: {args.interval} | Horizon label: {args.horizon} minutes\n")

    while True:
        try:
            btc = get_klines("BTCUSDT", args.interval)
            btc.attrs["symbol"] = "BTCUSDT"

            sol = get_klines("SOLUSDT", args.interval)
            sol.attrs["symbol"] = "SOLUSDT"

            results = [
                score_asset(btc),
                score_asset(sol, btc),
            ]

            for z in results:
                print("=" * 65)
                print(z["symbol"])
                print(f"Time UTC       : {z['time_utc']}")
                print(f"Price          : {z['price']:.8f}")
                print(f"Direction      : {z['direction']}")
                print(f"Confidence*    : {z['confidence']:.1f}%")
                print(f"Target         : {z['target']:.8f}")
                print(f"Invalidation   : {z['invalidation']:.8f}")
                print(f"RSI            : {z['rsi']:.1f}")
                print(f"Score          : {z['score']:+.1f}")
                print(f"Reasons        : {z['reasons']}")
                print(f"Horizon        : {args.horizon} min")
                print("* Confidence is a model score, NOT a guaranteed probability.")
                save_prediction(z)

            if args.once:
                break

            time.sleep(args.every * 60)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print("Error:", e)
            if args.once:
                break
            time.sleep(30)


if __name__ == "__main__":
    main()
