# hermes-trading — 학습 정리

로컬 페이퍼 트레이딩 워커 + 자연어 반성(reflection) 루프를 만들어본 프로토타입 기록.
"전략을 파일로 관리하고, 거래 로그를 근거로 에이전트가 변수를 하나씩 조정한다"는
메커니즘을 눈으로 보기 위한 스켈레톤이며, 실거래 가능한 상용 시스템이 아님.

---

## 1. 구현 순서 (실제로 진행한 순서)

1. **전략 정의** — 사용자에게 5개 질문(자산 / 목표수익률 / 최대낙폭 / 최소샤프 / 반성주기)을
   받아 `state/goal.yaml`로 저장. 이게 "성공/실패가 뭔지"를 숫자로 못박는 단계.
2. **워커 스캐폴딩** — `uv init`으로 파이썬 프로젝트 생성, `ccxt`/`pyyaml`/`numpy` 설치.
   RSI 기반 진입/청산 로직(`loop.py`), 채점 로직(`score.py`), 가격 어댑터(`adapters/price.py`)
   작성. 초기 `state/strategy.yaml` (v01) 작성.
3. **반성(reflection) 로직** — `reflect.py`에 두 모드 구현:
   - `--fallback`: 목표 미달/낙폭 초과를 규칙 기반으로 판단해 변수 하나 바꾸는 결정론적 버전
   - `--hermes`: 실제 Hermes CLI를 서브프로세스로 호출해 변수 변경을 위임하는 버전
   합성 거래 데이터로 `--fallback` 동작 검증 (v01→v02 버전업, `state/history/`에 이전 버전 저장).
4. **실행 검증** — 워커를 실제로 돌려서 바이낸스 공개 API에서 실가격/RSI를 받아오는지 확인.
5. **로컬 대시보드 추가** — 표준 라이브러리 `http.server`만으로 상태 조회 API + HTML 페이지 작성
   (새 의존성 없이 RSI/가격/전략버전/최근거래를 5초 간격으로 보여줌).
6. **GitHub 백업** — `gh` CLI는 sudo가 필요해 설치 실패 → GitHub REST API + Personal Access
   Token으로 우회. 토큰은 커밋에 남기지 않고 1회성 credential helper로만 사용.
7. **Hermes 연동 방식 확정** — 처음엔 자동 cron 루프를 고려했으나, 사용자가 "대화형으로 직접
   확인"을 선택 → `hermes chat`을 사용자가 직접 열어 브리핑을 붙여넣는 방식으로 결정.
8. **원클릭 실행 스크립트** — 워커/대시보드 중복 실행 방지 로직을 넣은
   `start-hermes-trading.bat` 작성 (PowerShell에서 더블클릭 한 번으로 전체 기동).

---

## 2. 폴더 구조

```
~/hermes-trading/                    (WSL 안에 위치)
├── pyproject.toml                   uv 프로젝트 정의 (ccxt, pyyaml, numpy)
├── .gitignore                       .venv/, *.log, heartbeat.json, uv.lock 제외
├── hermes_trading/
│   ├── __init__.py
│   ├── run.py                       엔트리포인트 (--asset 플래그, goal.yaml 기본값)
│   ├── loop.py                      24/7 트레이딩 루프 (60초 주기)
│   ├── reflect.py                   반성 로직 (--fallback / --hermes)
│   ├── score.py                     거래 채점 (-1~+1)
│   ├── dashboard.py                 로컬 웹 대시보드 서버 (stdlib http.server)
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── price.py                 ccxt.async_support로 바이낸스 OHLCV 수집
│   └── web/
│       └── index.html               대시보드 프론트엔드 (vanilla JS, 5초 polling)
└── state/
    ├── goal.yaml                    전략 목표 (성공/실패 정의, 사용자 입력값)
    ├── strategy.yaml                실행 중 전략 (버전 관리, v01부터 시작)
    ├── trades.jsonl                 거래 로그 (open/closed 이벤트 append)
    ├── hypotheses.jsonl             반성 시마다 남는 판단 근거 로그
    ├── history/                     이전 버전 strategy.yaml 스냅샷 (v01.yaml, v02.yaml, ...)
    ├── heartbeat.json               워커 생존 확인용 (ts, status, price, rsi)
    ├── worker.log / dashboard.log   각 프로세스 stdout

D:\Claude_code\hermes-trading\
└── start-hermes-trading.bat         워커+대시보드+Hermes chat 한 번에 기동 (Windows 쪽)
```

---

## 3. 실행 방법

**한 번에 시작 (권장)**
```
D:\Claude_code\hermes-trading\start-hermes-trading.bat  더블클릭
```
워커/대시보드가 이미 떠 있으면 건너뛰고, 아니면 새로 시작 + 브라우저로 대시보드 오픈 +
Hermes chat 새 창 시도.

**수동으로 하나씩 (WSL 안에서)**
```bash
cd ~/hermes-trading

# 워커
nohup uv run python -u -m hermes_trading.run > state/worker.log 2>&1 &
disown

# 대시보드
nohup uv run python -u -m hermes_trading.dashboard > state/dashboard.log 2>&1 &
disown
# → http://localhost:8787 (WSL2는 localhost 자동 포워딩됨)

# Hermes와 대화 (별도 터미널, TUI라 리다이렉트 불가)
hermes chat
```

**상태 확인**
```bash
cat ~/hermes-trading/state/heartbeat.json      # 현재 가격/RSI/상태
wc -l ~/hermes-trading/state/trades.jsonl      # 쌓인 거래 수
ps aux | grep hermes_trading                   # 프로세스 살아있는지
```

**종료**
```bash
pkill -f hermes_trading.run
pkill -f hermes_trading.dashboard
```
`hermes chat`은 그 창에서 `/exit` 또는 창 닫기.

**Hermes에게 반성 요청** (거래 `reflection_every`건마다, 지금 설정은 10건)
`hermes chat` 창에서 "반성해줘"라고 입력 → 최근 거래/전략/목표를 보고 변수 하나 제안 →
승인하면 `strategy.yaml` 수정.

---

## 4. 지금 상태의 한계 (솔직한 평가)

### 전략 자체가 얕음
- 지표가 RSI(14) **하나**뿐, 단일 타임프레임(1h), 단일 자산(BTC/USDT)만 지원.
- RSI<30 롱 진입 같은 교과서적 규칙은 이미 시장에 알려진 신호라 알파가 거의 없다고 봄.
- 거래량, 상위 타임프레임 추세 필터, 변동성 필터 없음.
- 수수료·슬리피지 반영 없음 — 페이퍼 손익이 실제보다 낙관적으로 나옴.
- `position_size_r`이라는 필드는 있지만 실제 계좌 잔고/리스크 단위에 연동되지 않고
  기록만 될 뿐 로직에 안 쓰임 — 이름만 있고 실질 기능은 없는 상태.

### 리스크 관리가 얕음
- 손절/익절이 고정 %(2%/4%)이고 ATR 등 변동성 기반 적응이 없음.
- 동시 포지션 1개로 단순화되어 있어 분산/상관관계 개념이 없음.
- `goal.yaml`의 `max_drawdown`은 "실패 판정"에만 쓰이고, 실제로 낙폭 초과 시
  거래를 자동으로 멈추는 회로차단기(circuit breaker)가 없음
  (어댑터 연속 실패에 대한 circuit breaker는 있지만 drawdown 기반은 없음).

### 반성(reflection) 루프가 검증 안 됨
- 거래 10건은 통계적으로 의미 있는 표본이 아님 — 이 정도로 변수를 계속 튜닝하면
  노이즈에 맞춰 과적합(overfitting)될 위험이 큼.
- Walk-forward 검증, train/test 분리, 과적합 방지 장치가 전혀 없음.
- `--hermes` 모드(실제 LLM 호출)는 코드만 작성했고 실전 트레이드로 검증한 적 없음
  (지금까지는 `hermes chat` 대화형으로만 사용).

### 인프라/운영 관점
- 백테스트 엔진이 없음 — 과거 데이터로 전략을 사전 검증하지 않고 바로 페이퍼로 돌림.
- 프로세스 장애 복구 로직 없음 (죽으면 수동으로 다시 띄워야 함, systemd/supervisor 없음).
- 로깅이 JSONL 파일뿐 — 알림(Slack/Discord 등), 대시보드 이력 그래프, 메트릭 저장 없음.
- 무키(No API key) 상태로만 테스트됨 — 실거래 전환 시 시크릿 관리부터 재설계 필요.
- 테스트 중 `entry.threshold`를 임시로 77까지 올려서 거래를 강제로 발생시킨 상태였음
  (원래 기본값은 30) — 학습 후 실제로 쓰려면 이 값부터 되돌려야 함.

---

## 5. 향후 개선하면 좋을 항목 (우선순위 순 제안)

1. **백테스트 엔진 먼저** — 과거 OHLCV로 전략을 사전 검증하는 게 제일 시급.
   지금은 "될지 안 될지 모르는 채로" 페이퍼 트레이딩부터 하고 있음.
2. **신호 다각화** — RSI 단일 지표 대신 추세/거래량/변동성 필터를 조합.
3. **포지션 사이징 실질화** — `position_size_r`을 실제 계좌 잔고 대비 리스크 단위로 계산.
4. **드로다운 기반 자동 정지** — `max_drawdown` 초과 시 실제로 거래를 멈추는 로직 추가.
5. **반성 주기 재검토** — 10건은 너무 적음. 표본 수를 늘리거나, 통계적 유의성 체크를
   반성 로직에 추가.
6. **수수료/슬리피지 반영** — score.py와 loop.py 양쪽에 현실적인 비용 반영.
7. **프로세스 관리** — nohup 대신 systemd(WSL) 또는 supervisor로 자동 재시작.
8. **알림 연동** — 거래 발생/반성 발생 시 Discord/Slack 웹훅으로 알림.
9. **`--hermes` 모드 실전 검증** — 지금은 코드만 있고 실제 거래 데이터로 테스트 안 됨.

---

## 6. 참고 — 이 프로젝트가 보여주는 핵심 아이디어

상용 수준은 아니지만, 아래 패턴 자체는 재사용 가치가 있음:

- **전략을 코드가 아니라 데이터(YAML)로 분리** → 에이전트가 코드를 건드리지 않고
  파라미터만 바꿀 수 있게 함.
- **버전 관리되는 전략 파일** (`state/history/v{NNNN}.yaml`) → 모든 변경 이력 추적 가능.
- **"한 사이클에 변수 하나만"** 이라는 과학적 방법론 가드레일 → 에이전트가 폭주해서
  한 번에 여러 변수를 바꾸는 것을 막음.
- **결정론적 fallback ↔ LLM 기반 반성**을 같은 인터페이스(`reflect.py`)로 스위칭 가능하게
  설계 → LLM 없이도 최소 동작 보장, LLM 있으면 더 똑똑한 판단으로 교체.
