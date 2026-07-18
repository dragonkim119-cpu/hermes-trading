import argparse
import asyncio
from pathlib import Path

import yaml

from hermes_trading.loop import run_loop

STATE_DIR = Path(__file__).resolve().parent.parent / 'state'
GOAL_PATH = STATE_DIR / 'goal.yaml'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', default=None)
    args = parser.parse_args()

    with open(GOAL_PATH) as f:
        goal = yaml.safe_load(f)

    asset = args.asset or goal['asset']
    asyncio.run(run_loop(asset))


if __name__ == '__main__':
    main()
