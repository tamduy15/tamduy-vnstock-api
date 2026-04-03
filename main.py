from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from vnstock import Quote
import pandas as pd

DEFAULT_SOURCE = "KBS"

app = FastAPI(title="Tam Duy Trader Vnstock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    }

@app.get("/history")
def history(
    symbol: str = Query(...),
    interval: str = Query("1D"),
    length: str = Query("6M"),
    source: str = Query(DEFAULT_SOURCE),
):
    try:
        q = Quote(symbol=symbol.upper(), source=source)
        df = q.history(length=length, interval=interval)

        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Không có dữ liệu history cho {symbol}",
            )

        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "length": length,
            "source": source,
            "data": df_to_records(df),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quote")
def quote(
    symbol: str = Query(...),
    source: str = Query(DEFAULT_SOURCE),
):
    try:
        q = Quote(symbol=symbol.upper(), source=source)
        df = q.history(length="10D", interval="1D")

        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Không có dữ liệu quote cho {symbol}",
            )

        last = df.iloc[-1]
        prev_close = df.iloc[-2]["close"] if len(df) > 1 else last["close"]

        price = float(last["close"])
        change = price - float(prev_close)
        change_pct = (change / float(prev_close) * 100) if float(prev_close) else 0

        return {
            "symbol": symbol.upper(),
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))