import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml

from hermes_trading.score import score

STATE_DIR = Path(__file__).resolve().parent.parent / 'state'
STRATEGY_PATH = STATE_DIR / 'strategy.yaml'
TRADES_PATH = STATE_DIR / 'trades.jsonl'
GOAL_PATH = STATE_DIR / 'goal.yaml'
HYPOTHESES_PATH = STATE_DIR / 'hypotheses.jsonl'
HISTORY_DIR = STATE_DIR / 'history'


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _load_trades(limit: int = 25) -> list[dict]:
    if not TRADES_PATH.exists():
        return []
    with open(TRADES_PATH) as f:
        trades = [json.loads(line) for line in f]
    return trades[-limit:]


def _bump_version(strategy: dict) -> str:
    current = int(strategy['version'])
    return f'{current + 1:02d}'


def _save_history(strategy: dict) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = HISTORY_DIR / f"v{strategy['version']}.yaml"
    with open(out_path, 'w') as f:
        yaml.safe_dump(strategy, f)


def _append_hypothesis(hypothesis: dict) -> None:
    with open(HYPOTHESES_PATH, 'a') as f:
        f.write(json.dumps(hypothesis) + '\n')


def reflect_fallback() -> dict:
    strategy = _load_yaml(STRATEGY_PATH)
    goal = _load_yaml(GOAL_PATH)
    trades = _load_trades()
    closed = [t for t in trades if t.get('status') == 'closed']

    s = score(closed, goal)
    realised_return = sum(t['pnl_pct'] for t in closed) if closed else 0.0

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for t in closed:
        equity *= 1 + t['pnl_pct']
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)

    prior_version = strategy['version']
    variable_changed = None
    reasoning = None

    if realised_return < goal['target_return_30d']:
        old = strategy['entry']['threshold']
        strategy['entry']['threshold'] = old + 2
        variable_changed = 'entry.threshold'
        reasoning = f'realised_return={realised_return:.4f} below target={goal["target_return_30d"]}; loosened entry.threshold {old} -> {strategy["entry"]["threshold"]}'
    elif max_dd > goal['max_drawdown']:
        old = strategy['stop_loss_pct']
        strategy['stop_loss_pct'] = round(old - 0.2, 2)
        variable_changed = 'stop_loss_pct'
        reasoning = f'drawdown={max_dd:.4f} above max={goal["max_drawdown"]}; tightened stop_loss_pct {old} -> {strategy["stop_loss_pct"]}'
    else:
        reasoning = 'within targets; no change this cycle'

    if variable_changed:
        _save_history({**strategy, 'version': prior_version})
        strategy['version'] = _bump_version(strategy)
        with open(STRATEGY_PATH, 'w') as f:
            yaml.safe_dump(strategy, f)

    hypothesis = {
        'ts': time.time(),
        'mode': 'fallback',
        'score': s,
        'prior_version': prior_version,
        'new_version': strategy['version'],
        'variable_changed': variable_changed,
        'reasoning': reasoning,
    }
    _append_hypothesis(hypothesis)
    print(json.dumps(hypothesis, indent=2))
    return hypothesis


def reflect_hermes() -> dict:
    strategy = _load_yaml(STRATEGY_PATH)
    goal = _load_yaml(GOAL_PATH)
    trades = _load_trades()

    schema_hint = '{"variable": "<dotted.path>", "new_value": <value>, "reasoning": "<why>"}'
    prompt = (
        'You are reflecting on a paper trading strategy. '
        f'Goal: {json.dumps(goal)}\n'
        f'Current strategy: {json.dumps(strategy)}\n'
        f'Last {len(trades)} trades: {json.dumps(trades)}\n\n'
        'Propose exactly ONE variable in the strategy to change and why. '
        f'Reply with strict JSON: {schema_hint}'
    )

    result = subprocess.run(
        ['hermes', '-z', prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f'hermes call failed: {result.stderr}')

    raw = result.stdout.strip()
    start, end = raw.find('{'), raw.rfind('}')
    hypothesis_raw = json.loads(raw[start:end + 1])

    path_parts = hypothesis_raw['variable'].split('.')
    prior_version = strategy['version']
    target = strategy
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = hypothesis_raw['new_value']

    _save_history({**strategy, 'version': prior_version})
    strategy['version'] = _bump_version(strategy)
    with open(STRATEGY_PATH, 'w') as f:
        yaml.safe_dump(strategy, f)

    hypothesis = {
        'ts': time.time(),
        'mode': 'hermes',
        'prior_version': prior_version,
        'new_version': strategy['version'],
        'variable_changed': hypothesis_raw['variable'],
        'new_value': hypothesis_raw['new_value'],
        'reasoning': hypothesis_raw['reasoning'],
    }
    _append_hypothesis(hypothesis)
    print(json.dumps(hypothesis, indent=2))
    return hypothesis


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fallback', action='store_true')
    parser.add_argument('--hermes', action='store_true')
    args = parser.parse_args()

    if args.hermes:
        reflect_hermes()
    else:
        reflect_fallback()
