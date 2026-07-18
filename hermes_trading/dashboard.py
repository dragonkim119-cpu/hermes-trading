import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

STATE_DIR = Path(__file__).resolve().parent.parent / 'state'
WEB_DIR = Path(__file__).resolve().parent / 'web'
HEARTBEAT_PATH = STATE_DIR / 'heartbeat.json'
STRATEGY_PATH = STATE_DIR / 'strategy.yaml'
TRADES_PATH = STATE_DIR / 'trades.jsonl'

PORT = 8787


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _read_recent_trades(limit: int = 20) -> list[dict]:
    if not TRADES_PATH.exists():
        return []
    with open(TRADES_PATH) as f:
        lines = [json.loads(line) for line in f]
    return lines[-limit:]


def _find_open_position(trades: list[dict]) -> dict | None:
    open_trade = None
    for t in trades:
        if t['status'] == 'open':
            open_trade = t
        elif t['status'] == 'closed' and open_trade and t['id'] == open_trade['id']:
            open_trade = None
    return open_trade


def build_status() -> dict:
    heartbeat = _read_json(HEARTBEAT_PATH)
    strategy = _read_yaml(STRATEGY_PATH)
    trades = _read_recent_trades()

    return {
        'asset': heartbeat.get('asset'),
        'last_price': heartbeat.get('last_price'),
        'rsi': heartbeat.get('rsi'),
        'status': heartbeat.get('status'),
        'heartbeat_age_sec': (time.time() - heartbeat['ts']) if heartbeat.get('ts') else None,
        'strategy_version': strategy.get('version'),
        'entry_threshold': strategy.get('entry', {}).get('threshold'),
        'stop_loss_pct': strategy.get('stop_loss_pct'),
        'open_position': _find_open_position(trades),
        'recent_trades': trades,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep worker log clean

    def do_GET(self):
        if self.path == '/api/status':
            body = json.dumps(build_status()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path in ('/', '/index.html'):
            body = (WEB_DIR / 'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


def main() -> None:
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print(f'Dashboard serving on http://localhost:{PORT}')
    server.serve_forever()


if __name__ == '__main__':
    main()
