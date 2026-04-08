# Phase 2 - Paper Trading (FInsight)

## Quick start

1. Configure `DATABASE_URL` (PostgreSQL; this project already uses Neon/psycopg2).
2. Install dependencies: `pip install -r requirements.txt`
3. Run API: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
4. On first startup, `paper_*` tables are created automatically in `app/services/database.py` (`_initialize_tables`).
5. Open dashboard: **http://127.0.0.1:8000/paper-dashboard**
6. Use a valid `user_id` from `users` table (create one via auth endpoints in `/docs` if needed).

## Dashboard

- **Load**: fetches summary, equity history, positions, trades, and signals.
- **Seed 10k**: `POST /api/paper/simulation/{user_id}/seed-balance`
- **Reset**: clears positions/trades/history and resets cash.

## Main endpoints (prefix `/api/paper`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/portfolio/{user_id}` | Simulated portfolio |
| GET | `/portfolio/{user_id}/summary` | KPIs (win rate, equity, etc.) |
| GET | `/portfolio/{user_id}/positions` | Open positions |
| GET | `/portfolio/{user_id}/trades` | Trade history |
| GET | `/portfolio/{user_id}/equity-history` | Equity chart series |
| POST | `/signals` | Create signal |
| GET | `/signals` | List signals |
| POST | `/signals/process/{user_id}` | Process signal by `signal_id` |
| POST | `/simulation/{user_id}/seed-balance` | Create/reset with initial balance |
| POST | `/simulation/{user_id}/reset` | Reset simulation |
| POST | `/simulation/{user_id}/process-signal` | Create + process inline signal |
| POST | `/signals/mock-batch` | Insert sample signal batch |

## Mocked mode (test mode) - Full Phase 2

When mocked wallet is connected (`POST /api/test-mode` with `{"action":"connect"}`), the endpoints below use the **same paper trading engine**:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/test-mode/paper-dashboard` | Full payload: portfolio, summary, positions, trades, signals, equity_history |
| POST | `/api/test-mode/paper/seed-balance` | Set mocked simulation initial balance |
| POST | `/api/test-mode/paper/reset` | Reset mocked simulation |
| POST | `/api/test-mode/paper/process-signal` | Create + process inline signal |
| POST | `/api/test-mode/paper/signals` | Create user-scoped signal |
| GET | `/api/test-mode/paper/signals` | User signal history |
| POST | `/api/test-mode/paper/process-signal-by-id` | Process existing `signal_id` |

## Payload examples (curl)

**Seed / reset (10,000)**

```bash
curl -s -X POST "http://127.0.0.1:8000/api/paper/simulation/1/seed-balance" \
  -H "Content-Type: application/json" \
  -d '{"initial_balance": 10000}'
```

**Create BUY signal**

```bash
curl -s -X POST "http://127.0.0.1:8000/api/paper/signals" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","signal_type":"BUY","signal_price":180.5,"confidence_score":0.8,"explanation":"test"}'
```

**Process existing signal**

```bash
curl -s -X POST "http://127.0.0.1:8000/api/paper/signals/process/1" \
  -H "Content-Type: application/json" \
  -d '{"signal_id": 1}'
```

**Inline signal (create + execute)**

```bash
curl -s -X POST "http://127.0.0.1:8000/api/paper/simulation/1/process-signal" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","signal_type":"SELL","signal_price":185.0}'
```

## Rules summary

- Buy: allocates `allocation_pct` of available cash (default 10%), no leverage.
- Sell: closes symbol position (FIFO by open lots), updates cash and realized PnL.
- `fee_rate` and `slippage_bps` are ready for extension (currently default 0).
- Equity history is persisted to `paper_equity_history` on metrics refresh.

## Folder architecture

- `app/schemas/paper_trading.py` - Pydantic schemas
- `app/repositories/paper_trading_repo.py` - SQL repository
- `app/services/paper_trading_service.py` - execution rules
- `app/services/portfolio_service.py` - reads/summaries
- `app/services/metrics_service.py` - KPIs and equity
- `app/api/paper_trading.py` - FastAPI routes
- `app/static/dashboard.html` - UI

## Manual adjustment

- **SQLite**: current implementation uses PostgreSQL; SQLite needs DDL/SQL adaptation (types and `ON CONFLICT` differences).
- **Fees**: update `fee_rate` directly in `paper_portfolios` or add a PATCH endpoint.
