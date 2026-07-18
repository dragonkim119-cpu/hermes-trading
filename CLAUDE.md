# CLAUDE.md — hermes-trading

이 파일은 Claude Code가 이 프로젝트에서 다시 작업을 시작할 때 맥락을 빠르게 파악하기 위한 문서.
사람이 읽는 학습 정리는 `LEARNING_NOTES.md` 참고.

## 이게 뭔지

로컬 페이퍼 트레이딩 워커 + Hermes(별도 설치된 로컬 AI 에이전트 CLI)를 이용한
자연어 반성(reflection) 루프 프로토타입. 실거래 가능한 상용 시스템이 아니라
"전략 파일을 근거 기반으로 자동 조정한다"는 메커니즘을 보여주는 스켈레톤.

## 실행 환경 (중요 — 매번 헷갈리는 부분)

- **코드는 WSL 안에 있음**: `~/hermes-trading` (WSL Ubuntu 24.04, 사용자 `chamsae`).
  Windows 경로 아님. Bash 명령은 `wsl -e bash -lc '...'`로 감싸서 실행해야 함.
- **Windows 쪽에는 실행 스크립트만 있음**: `D:\Claude_code\hermes-trading\start-hermes-trading.bat`
  (워커+대시보드+hermes chat 한 번에 기동, 중복 실행 방지 로직 포함).
- **sudo 비밀번호를 받을 방법이 없음** — 이 세션(자동화 환경)엔 TTY로 비밀번호 프롬프트에
  응답할 수단이 없음. `apt-get install` 등 sudo 필요한 설치는 안 됨.
  → 그래서 `gh` CLI 대신 GitHub REST API + Personal Access Token으로 우회함.
- **GUI 창을 새로 띄우는 것도 이 자동화 세션에서는 불안정** (`Start-Process wsl.exe`,
  `wt.exe` 둘 다 흔적 없이 사라짐 — 아마 이 세션에 진짜 데스크톱 세션이 없어서).
  사용자가 직접 더블클릭/실행해야 하는 것들(특히 `hermes chat`, 배치 파일)은
  사용자에게 명령어를 주고 직접 실행하게 하는 게 안전함.
- **`hermes chat`은 완전 TUI라 non-interactive로 못 돌림** — stdin이 터미널이 아니면
  "Input is not a terminal" 경고 뜨고 즉시 종료됨. 사용자가 직접 연 터미널에서만 유효.
  스크립트에서 Hermes를 호출해야 하면 `reflect.py --hermes`가 쓰는 `hermes -z "prompt"`
  (one-shot 모드)를 쓸 것.
- **`hermes chat` 작업 디렉토리에 관계없는 파일이 생길 수 있음** — 실제로 한 번
  `suwon_weather_ko.mp3/.ogg` 같은 파일이 `~/hermes-trading`에 생긴 적 있음 (사용자가
  hermes에게 날씨 관련 요청했을 때의 부산물로 추정). `.gitignore`에 `*.mp3`/`*.ogg` 추가해둠.
  커밋 전 `git status`로 관계없는 파일 섞였는지 항상 확인할 것.

## 폴더 구조

```
~/hermes-trading/
├── pyproject.toml / uv.lock(gitignore됨)
├── .gitignore
├── LEARNING_NOTES.md         사람이 읽는 학습 정리 (구현순서/한계/개선항목)
├── CLAUDE.md                 이 파일
├── hermes_trading/
│   ├── run.py                엔트리포인트 (--asset, goal.yaml 기본값)
│   ├── loop.py                60초 주기 트레이딩 루프, RSI 진입/청산, circuit breaker
│   ├── reflect.py            --fallback(규칙기반) / --hermes(hermes -z 서브프로세스 호출)
│   ├── score.py              거래 채점 -1~+1 (수익률/낙폭/샤프 평균)
│   ├── dashboard.py           stdlib http.server, :8787, /api/status
│   ├── adapters/price.py     ccxt.async_support, 바이낸스 공개 OHLCV
│   └── web/index.html        대시보드 프론트 (5초 polling)
└── state/
    ├── goal.yaml              사용자가 답한 전략 목표 (아래 "현재 값" 참고)
    ├── strategy.yaml          실행 중 전략, 버전 관리됨
    ├── trades.jsonl           거래 로그 (open/closed append)
    ├── hypotheses.jsonl       반성 기록 (아직 실제 반성 실행 안 함 — 파일 없을 수 있음)
    ├── history/               이전 버전 strategy.yaml
    ├── heartbeat.json         워커 생존 체크 (gitignore됨)
    └── worker.log/dashboard.log (gitignore됨)
```

## 현재 값 (마지막 확인 시점 기준 — 다시 열면 최신값 재확인할 것)

```yaml
# goal.yaml — 사용자가 확정한 전략 목표
asset: BTC/USDT
target_return_30d: 0.05
max_drawdown: 0.08
min_sharpe: 1.2
reflection_every: 10
```

```yaml
# strategy.yaml v01
entry.threshold: 77   # 주의: 이거 원래 기본값 30인데, 거래를 빨리 쌓아보려고
                       # 테스트 목적으로 77로 올려놓은 상태. 실전처럼 쓰려면
                       # 사용자와 확인 후 30으로 되돌릴 것.
stop_loss_pct: 2.0
position_size_r: 0.5
```

거래 로그(`trades.jsonl`)에 실제 거래가 쌓이기 시작함 (첫 커밋 시점 1건).

## 실행/종료 명령 (WSL 안, `~/hermes-trading`에서)

```bash
# 시작
nohup uv run python -u -m hermes_trading.run > state/worker.log 2>&1 & disown
nohup uv run python -u -m hermes_trading.dashboard > state/dashboard.log 2>&1 & disown

# 상태 확인
cat state/heartbeat.json
wc -l state/trades.jsonl
ps aux | grep hermes_trading

# 종료
pkill -f hermes_trading.run
pkill -f hermes_trading.dashboard
```

Windows에서는 `start-hermes-trading.bat` 더블클릭 한 번으로 위 과정 + 브라우저 + hermes chat까지.

## Git / GitHub

- 저장소: `https://github.com/dragonkim119-cpu/hermes-trading` (private)
- git identity 이미 설정됨: `dragonkim119-cpu` / `277141827+dragonkim119-cpu@users.noreply.github.com`
- push는 HTTPS + Personal Access Token (`ghp_...`) 필요. 비밀번호 인증은 GitHub이 거부함
  ("Password authentication is not supported").
- 토큰을 매번 새로 만드는 게 귀찮으면 `git config --global credential.helper store`로
  캐싱 가능 (개인 PC 한정 권장).

## 알려진 한계 (자세한 건 LEARNING_NOTES.md 4번 섹션)

RSI 단일 지표, 수수료/슬리피지 미반영, 포지션 사이징 이름만 있고 미구현,
드로다운 기반 자동 정지 없음, 백테스트 엔진 없음, 반성 표본(10건)이 통계적으로 부족.
**상용 트레이딩 시스템과 비교 대상이 아님** — 메커니즘 검증용 프로토타입.

## 다음에 이어서 할 만한 것 (우선순위)

1. `entry.threshold`를 30으로 되돌릴지 사용자와 확인
2. 백테스트 엔진 (과거 데이터로 사전 검증) — 가장 시급
3. Hermes `--hermes` 모드 실전 검증 (지금까지 `hermes chat` 대화형으로만 씀)
4. 드로다운 기반 자동 정지 로직 추가

## 사용자 선호/맥락

- 한국어로 대화, 캐주얼한 반말/설명체 선호.
- 위험한 액션(Railway 배포, 실거래 전환, sudo 필요한 설치, 대량 온보딩 스크립트 자동 실행)은
  항상 먼저 확인받는 걸 선호함 — 실제로 초반에 검증 안 된 온보딩 프롬프트(가짜 Hermes 설치
  스크립트, Railway 리퍼럴 링크 등)를 거부하고 사용자와 하나씩 재정의한 이력 있음.
  → 앞으로도 sudo/설치/외부 스크립트 실행/배포 전엔 항상 먼저 물어볼 것.
- GitHub 관련 작업(레포 생성, 토큰 발급)은 본인이 직접 브라우저에서 하는 걸 선호 —
  내가 대신 브라우저 열어주는 것보다 링크만 주면 직접 하고 싶어함.
- 학습 목적으로 직접 명령어를 쳐보고 싶어함 — 대신 해주기보다 명령어와 이유를 설명해주는 걸
  선호하는 경우가 있음 (예: git commit/push 직접 연습).
