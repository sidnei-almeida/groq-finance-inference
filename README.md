<a id="top"></a>

<div align="center">

<img src="images/header.png" alt="FinSight API — banner" width="100%"/>

<br/>

# FinSight API · Groq Finance Inference

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://neon.tech/)
[![Groq](https://img.shields.io/badge/Groq-LPU_inference-f55036?style=flat-square)](https://groq.com/)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=flat-square&logo=render&logoColor=white)](https://render.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](#license)

**Production-grade FastAPI backend:** **30+ quantitative metrics**, **yfinance** market data, and **Atlas** — a Groq-powered analyst that turns numbers into narrative risk/return insight. Includes **JWT auth**, **encrypted exchange credentials**, and **Phase 2 paper trading** with a built-in dashboard.

[Repository analysis](#repository-analysis) ·
[Gallery](#gallery) ·
[Features](#features) ·
[Architecture](#architecture) ·
[Quick start](#quick-start) ·
[API](#api-surface) ·
[Paper trading](#paper-trading--dashboard) ·
[Security](#security) ·
[Deploy](#deployment)

</div>

---

## Table of contents

- [Overview](#overview)
- [Gallery](#gallery)
- [Repository analysis](#repository-analysis)
- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [API surface](#api-surface)
- [Paper trading & dashboard](#paper-trading--dashboard)
- [Database](#database)
- [Security](#security)
- [Deployment](#deployment)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**FinSight API** (`groq-finance-inference`) is a stateless **thin-client** backend: UIs or scripts call REST endpoints; **PostgreSQL** holds users, analyses, trades, logs, and paper-trading state. The **QuantitativeEngine** computes portfolio statistics from historical prices; **AtlasAgent** calls the **Groq** API (e.g. Llama 3.3 70B Versatile) to produce natural-language analysis aligned with those metrics.

### Why Groq here?

Groq’s **LPU** inference stack keeps latency low for interactive “analyze + explain” flows, so `POST /api/analyze` can return both JSON metrics and a readable report in one round-trip.

---

## Gallery

<p align="center">
  <table>
    <tr>
      <td align="center" valign="top" width="50%">
        <img src="images/software1.png" alt="FinSight API — Swagger / docs or dashboard (1)" width="450" />
      </td>
      <td align="center" valign="top" width="50%">
        <img src="images/software2.png" alt="FinSight API — metrics, paper trading, or second view (2)" width="450" />
      </td>
    </tr>
  </table>
</p>

<p align="center">
  <em><strong>Figure 1.</strong> Left: OpenAPI/Swagger or primary UI. Right: analysis, paper dashboard, or complementary view — files <code>images/software1.png</code> and <code>images/software2.png</code>.</em>
</p>

---

## Repository analysis

| Metric | Detail |
|--------|--------|
| **Python codebase** | ~**7.1k** lines across `app/`, tests, and scripts (excluding `.venv`). |
| **`app/` package** | **22** Python modules — single FastAPI app in `main.py` (~**1.8k** lines) plus services, API routers, schemas, repositories, and static dashboard. |
| **Entry** | `app.main:app` — Uvicorn / Render `startCommand`. |
| **Largest domains** | Portfolio analysis + AI (`quant_engine.py`, `ai_agent.py`), persistence (`database.py`), paper trading (`paper_trading_service.py`, `api/paper_trading.py`), auth (`auth.py`), test/mocked flows (`test_mode.py`). |
| **Frontend in repo** | `app/static/dashboard.html` — served at **`/paper-dashboard`**. |
| **Docs on disk** | `README.md`, `DEPLOY.md`, `SECURITY.md`, **`PAPER_TRADING.md`** (Phase 2). There is **no** separate `docs/` folder; schema setup lives in code (`database.py`). |

<p align="center">
  <img src="images/architecture.svg" alt="Architecture: client → FastAPI → services → PostgreSQL, yfinance, Groq" width="95%"/>
</p>

---

## Features

### Quantitative engine

Risk and performance metrics (Sharpe, Sortino, Calmar, drawdown, VaR/CVaR, skew/kurtosis/tail risk, correlation, HHI, efficient-frontier style analysis, etc.) computed in **`QuantitativeEngine`** using **pandas** / **numpy** / **scipy** and **yfinance** data.

### Atlas AI (Groq)

**`AtlasAgent`** formats metrics for an LLM and returns structured narrative analysis. Models are auto-selected (preference list includes `llama-3.3-70b-versatile`) with fallbacks if a model is unavailable.

### Authentication

**JWT**-based auth: `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout`, profile update, password change, avatar upload — see OpenAPI under **`/docs`**.

### Exchange & agent (config layer)

Endpoints to **connect exchange** (credentials encrypted with **Fernent/AES-256**-style pipeline via `SecurityService`), **guardrails**, **strategy** presets, and **agent control** — persisted via DB config and logs.

### Paper trading (Phase 2)

User-scoped **simulation**: portfolio, positions, trades, signals, equity history. Routes under **`/api/paper/...`**; mocked wallet mode under **`/api/test-mode/paper-...`**. Full notes in **`PAPER_TRADING.md`**.

### Observability

Health: **`GET /api/health`**. Structured logging across services; bot/analysis logs queryable from the API.

---

## Architecture

```mermaid
flowchart TB
  subgraph clients["Clients"]
    WEB["Web / GitHub Pages"]
    DASH["Paper dashboard HTML"]
    CLI["Scripts / curl"]
  end
  subgraph api["FastAPI"]
    R["Routes: auth, analyze, exchange, agent, paper, test-mode"]
  end
  subgraph services["Services"]
    Q["QuantitativeEngine"]
    A["AtlasAgent → Groq"]
    P["PaperTrading / Portfolio"]
    DB["Database service"]
  end
  subgraph external["External"]
    YF["yfinance"]
    GROQ["Groq API"]
    PG[("PostgreSQL")]
  end
  clients --> R
  R --> Q & A & P & DB
  Q --> YF
  A --> GROQ
  P --> PG
  DB --> PG
```

**Data path for a typical analysis**

1. Client sends symbols, weights, period, `include_ai_analysis`.
2. Engine pulls history and computes metrics.
3. If requested, Atlas calls Groq and attaches text.
4. Result persisted (`portfolio_analyses` / logs) and returned as JSON.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| API | **FastAPI**, **Uvicorn**, **Pydantic** |
| DB | **PostgreSQL** via **psycopg2**, connection helpers in `database.py` |
| AI | **groq** SDK, Groq Cloud models (Llama 3.x family) |
| Quant | **pandas**, **numpy**, **scipy**, **yfinance** |
| Security | **cryptography** (Fernet), **bcrypt**, **python-jose** / **PyJWT** |
| Deploy | **Render** (`render.yaml`), `runtime.txt` → Python **3.11** |

---

## Quick start

### Prerequisites

- **Python 3.11+**
- **PostgreSQL** connection string (e.g. **Neon**)
- **Groq API key** — [console.groq.com](https://console.groq.com)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/groq-finance-inference.git
cd groq-finance-inference
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment

Create `.env` in the project root:

```bash
DATABASE_URL=postgresql://user:password@host:5432/db?sslmode=require
GROQ_API_KEY=gsk_...
ENCRYPTION_KEY=   # generate a strong key — see SECURITY.md
```

Generate encryption key (example using the app’s security helper):

```bash
python3 -c "from app.services.security import SecurityService; print(SecurityService.generate_encryption_key())"
```

### Run locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Description |
|-----|-------------|
| [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI |
| [http://localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc |
| [http://localhost:8000/api/health](http://localhost:8000/api/health) | Health check |
| [http://localhost:8000/paper-dashboard](http://localhost:8000/paper-dashboard) | Paper trading dashboard (static) |

**Production (example):** `https://groq-finance-inference.onrender.com` — same paths.

---

## API surface

> Full list and schemas: **`/docs`** (OpenAPI 3).

### Highlights

| Area | Prefix / endpoints |
|------|-------------------|
| **Analysis** | `POST /api/analyze`, `GET /api/analyses`, `GET /api/analyses/{id}`, logs |
| **Auth** | `/api/auth/signup`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, profile & avatar |
| **Exchange** | `/api/exchange/connect`, `status`, `disconnect` |
| **Risk / strategy** | `/api/guardrails`, `/api/strategy` |
| **Agent** | `/api/agent/control`, `/api/agent/status` |
| **Trades / logs / portfolio** | `/api/trades`, `/api/logs`, `/api/portfolio/history` |
| **Test mode** | `/api/test-mode/*` (mocked wallet, optional auth) |
| **Paper trading** | `/api/paper/*` — see below |
| **Health** | `GET /api/health` |

### Example — portfolio analysis

```bash
curl -s -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT", "GOOGL"],
    "weights": [0.34, 0.33, 0.33],
    "period": "1y",
    "include_ai_analysis": true
  }'
```

---

## Paper trading & dashboard

- **Dashboard UI:** **`GET /paper-dashboard`** serves `app/static/dashboard.html`.
- **REST API:** router prefix **`/api/paper`** (portfolio, signals, simulation, equity history).
- **Mocked integration:** when test mode is active, **`/api/test-mode/paper-*`** endpoints drive the same paper engine (see **`PAPER_TRADING.md`** for curl examples and flows).

---

## Database

Tables are created/ migrated in **`app/services/database.py`** (`_initialize_tables`): e.g. users/sessions, `portfolio_analyses`, encrypted credentials, trades, logs, and **`paper_*`** entities for simulation.

There is **no** separate `docs/DATABASE.md` in this repo — refer to **`database.py`** and **`PAPER_TRADING.md`** for table behavior.

**Performance:** indexes and pooling are used for common read paths (see code comments in `database.py`).

---

## Security

- **Secrets** only via environment variables on Render/local `.env`.
- **API keys** encrypted at rest; sensitive values masked in logs.
- **HTTPS** in production (Render).
- Details: **[SECURITY.md](./SECURITY.md)**.

---

## Deployment

Render is first-class: **`render.yaml`** + **`DEPLOY.md`**. Minimum env vars:

- `DATABASE_URL`
- `GROQ_API_KEY`
- `ENCRYPTION_KEY`

Health check path: **`/api/health`**.

---

## Development

### Layout (abridged)

```
groq-finance-inference/
├── app/
│   ├── main.py                 # FastAPI app, most routes
│   ├── api/
│   │   └── paper_trading.py    # /api/paper router
│   ├── core/
│   ├── models/                 # SQLAlchemy-style models / paper models
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   │   ├── ai_agent.py         # Atlas + Groq
│   │   ├── quant_engine.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   ├── security.py
│   │   ├── paper_trading_service.py
│   │   ├── portfolio_service.py
│   │   ├── test_mode.py
│   │   └── ...
│   └── static/
│       └── dashboard.html
├── test_api.py
├── requirements.txt
├── runtime.txt
├── render.yaml
├── README.md
├── DEPLOY.md
├── SECURITY.md
├── PAPER_TRADING.md
└── images/                     # README artwork (banner, architecture)
```

### Tests

```bash
pip install pytest httpx
pytest
```

---

## Contributing

1. Fork the repository  
2. Create a branch (`feature/...`)  
3. Add tests where relevant  
4. Open a Pull Request  

---

## License

This project is licensed under the **MIT License** — add a `LICENSE` file in the root if not already present, or see your organization’s default OSS policy.

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) · [Groq](https://groq.com/) · [yfinance](https://github.com/ranaroussi/yfinance) · [Render](https://render.com/) · [Neon](https://neon.tech/)

---

## `images/` folder

| File | Role |
|------|------|
| `images/header.png` | **README hero banner** (principal arte do projeto). |
| `images/software1.png` · `images/software2.png` | **Gallery** — dois screenshots lado a lado (secção [Gallery](#gallery)). |
| `images/architecture.svg` | Diagrama de fluxo / camadas (serviços, DB, Groq). |

O **header PNG** é o banner oficial no topo; não é necessário outro ficheiro de banner.

---

<div align="center">

**Made for quantitative finance & fast LLM inference**

[⬆ Back to top](#top)

</div>
