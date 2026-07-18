import numpy as np


def _sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    arr = np.array(returns)
    std = arr.std()
    if std == 0:
        return 0.0
    return float(arr.mean() / std * np.sqrt(len(arr)))


def _max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for x in equity_curve:
        peak = max(peak, x)
        dd = (peak - x) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return max_dd


def score(trades: list[dict], goal: dict) -> float:
    """Composite score in [-1, +1] from closed trades vs goal.yaml targets."""
    closed = [t for t in trades if t.get("status") == "closed"]
    if not closed:
        return 0.0

    returns = [t["pnl_pct"] for t in closed]
    realised_return = sum(returns)
    target_return = goal["target_return_30d"]
    return_score = np.clip(realised_return / target_return, -1.5, 1.5) if target_return else 0.0

    equity_curve = list(np.cumprod([1 + r for r in returns]))
    drawdown = _max_drawdown(equity_curve)
    max_dd = goal["max_drawdown"]
    dd_score = np.clip(1 - (drawdown / max_dd), -1.5, 1.0) if max_dd else 0.0

    sharpe = _sharpe(returns)
    min_sharpe = goal["min_sharpe"]
    sharpe_score = np.clip(sharpe / min_sharpe, -1.5, 1.5) if min_sharpe else 0.0

    composite = (return_score + dd_score + sharpe_score) / 3
    return float(np.clip(composite, -1.0, 1.0))
