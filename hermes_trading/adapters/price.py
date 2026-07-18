import ccxt.async_support as ccxt


class SchemaError(Exception):
    pass


SCHEMA_VERSION = 1


async def fetch(symbol: str, timeframe: str = "1h", limit: int = 100) -> dict:
    exchange = ccxt.binance()
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    finally:
        await exchange.close()

    if not ohlcv or len(ohlcv[0]) != 6:
        raise SchemaError(f"unexpected ohlcv shape from binance for {symbol}")

    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        # each candle: [timestamp, open, high, low, close, volume]
        "candles": ohlcv,
    }
