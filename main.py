from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from vnstock import Quote, register_user
import pandas as pd
import os
import time
import traceback

DEFAULT_SOURCE = "KBS"
VNSTOCK_API_KEY = os.getenv("VNSTOCK_API_KEY", "").strip()

if VNSTOCK_API_KEY:
    register_user(api_key=VNSTOCK_API_KEY)

app = FastAPI(title="Tam Duy Trader Vnstock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE = {}

def get_cache(key: str, ttl_seconds: int):
    item = CACHE.get(key)
    if not item:
        return None
    if time.time() - item["ts"] > ttl_seconds:
        CACHE.pop(key, None)
        return None
    return item["value"]

def set_cache(key: str, value):
    CACHE[key] = {
        "ts": time.time(),
        "value": value,
    }

def df_to_records(df: pd.DataFrame):
    if df is None or df.empty:
        return []

    out = df.copy()

    if "time" in out.columns:
        out["time"] = out["time"].astype(str)

    return out.to_dict(orient="records")

@app.get("/health")
def health():
    return {
        "ok": True,
        "source": DEFAULT_SOURCE,
        "hasApiKey": bool(VNSTOCK_API_KEY),
    }

@app.get("/history")
def history(
    symbol: str = Query(...),
    interval: str = Query("1D"),
    length: str = Query("6M"),
    source: str = Query(DEFAULT_SOURCE),
):
    try:
        upper_symbol = symbol.upper()
        cache_key = f"history:{upper_symbol}:{interval}:{length}:{source}"
        cached = get_cache(cache_key, 300)
        if cached is not None:
            return cached

        q = Quote(symbol=upper_symbol, source=source)
        df = q.history(length=length, interval=interval)

        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Không có dữ liệu history cho {upper_symbol}",
            )

        result = {
            "symbol": upper_symbol,
            "interval": interval,
            "length": length,
            "source": source,
            "data": df_to_records(df),
        }

        set_cache(cache_key, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        }

@app.get("/quote")
def quote(
    symbol: str = Query(...),
    source: str = Query(DEFAULT_SOURCE),
):
    try:
        upper_symbol = symbol.upper()
        cache_key = f"quote:{upper_symbol}:{source}"
        cached = get_cache(cache_key, 15)
        if cached is not None:
            return cached

        q = Quote(symbol=upper_symbol, source=source)
        df = q.history(length="10D", interval="1D")

        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Không có dữ liệu quote cho {upper_symbol}",
            )

        last = df.iloc[-1]
        prev_close = df.iloc[-2]["close"] if len(df) > 1 else last["close"]

        price = float(last["close"])
        change = price - float(prev_close)
        change_pct = (change / float(prev_close) * 100) if float(prev_close) else 0

        result = {
            "symbol": upper_symbol,
            "price": price,
            "change": change,
            "changePct": change_pct,
            "open": float(last["open"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "close": float(last["close"]),
            "volume": int(last["volume"]) if "volume" in last else 0,
            "time": str(last["time"]),
            "status": f"Dữ liệu thật từ Vnstock/{source}",
        }

        set_cache(cache_key, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        }