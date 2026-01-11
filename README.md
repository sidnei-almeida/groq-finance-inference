# FinSight API

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Render](https://img.shields.io/badge/Deploy-Render-46a3b3.svg)

**Enterprise-grade quantitative portfolio analysis API powered by AI**

[Features](#-features) • [Quick Start](#-quick-start) • [API Documentation](#-api-documentation) • [Deployment](#-deployment) • [Security](#-security)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [API Documentation](#-api-documentation)
- [Database Schema](#-database-schema)
- [Security](#-security)
- [Deployment](#-deployment)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**FinSight API** is a production-ready FastAPI backend that provides sophisticated quantitative portfolio analysis with AI-powered insights. It combines rigorous financial mathematics with state-of-the-art language models to deliver actionable investment intelligence in milliseconds.

### Key Capabilities

- **31+ Advanced Metrics**: Comprehensive risk and performance analysis including Sharpe, Sortino, VaR, CVaR, Tail Risk, and more
- **AI-Powered Analysis**: Atlas AI agent interprets complex metrics and provides natural language insights using Groq's ultra-fast LLM inference
- **Thin Client Architecture**: Stateless API design with all state persisted in PostgreSQL
- **Enterprise Security**: AES-256 encryption for sensitive credentials, secure credential management
- **Production Ready**: Optimized for cloud deployment with health checks, monitoring, and auto-scaling support

---

## ✨ Features

### Quantitative Analysis Engine

- **Risk Metrics**: Maximum Drawdown, Value at Risk (VaR), Conditional VaR (CVaR), Downside Deviation
- **Performance Metrics**: Sharpe Ratio, Sortino Ratio, Calmar Ratio, Win Rate
- **Distribution Analysis**: Skewness, Kurtosis, Tail Risk Assessment
- **Diversification Metrics**: Correlation Matrix, Portfolio Concentration (HHI), Beta Analysis
- **Optimization**: Efficient Frontier Analysis, Minimum Variance Portfolio

### AI-Powered Insights

- **Atlas AI Agent**: Specialized financial analyst persona with expertise in tail risk and distribution analysis
- **Sub-second Inference**: Powered by Groq's LPU technology for real-time analysis
- **Natural Language Reports**: Comprehensive portfolio insights in plain English
- **Risk Interpretation**: Identifies hidden risks that standard metrics miss

### Architecture & Infrastructure

- **Thin Client Design**: Frontend queries API, all state in database
- **Stateless API**: Horizontally scalable, cloud-native architecture
- **Connection Pooling**: Optimized database connections for high throughput
- **Performance Indexes**: 15+ database indexes for sub-100ms query times

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend Layer                        │
│              (Thin Client - React/Vue/Angular)              │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTPS/REST API
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                  (Stateless - Horizontally Scalable)         │
└───────┬───────────────────┬───────────────────┬────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  PostgreSQL  │   │ Quantitative │   │  Atlas AI    │
│   (Neon)     │   │    Engine    │   │   (Groq)     │
│              │   │              │   │              │
│ • Analyses   │   │ • 31+ Metrics│   │ • LLM 3.3    │
│ • Trades     │   │ • Risk Calc  │   │ • Insights   │
│ • Logs       │   │ • Portfolio  │   │ • Reports    │
│ • Config     │   │ • Optimization│   │              │
└──────────────┘   └──────────────┘   └──────────────┘
```

### Data Flow

1. **Client Request** → FastAPI receives HTTP request
2. **Quantitative Analysis** → Engine fetches market data, calculates metrics
3. **AI Processing** → Atlas AI interprets metrics, generates insights
4. **Database Persistence** → Results stored in PostgreSQL
5. **Response** → JSON response with metrics and AI analysis

---

## 🛠️ Tech Stack

| Category | Technology | Version |
|----------|-----------|---------|
| **Framework** | FastAPI | 0.104+ |
| **ASGI Server** | Uvicorn | Standard |
| **Database** | PostgreSQL (Neon) | Latest |
| **ORM/Driver** | psycopg2 | 2.9.9+ |
| **AI/LLM** | Groq (Llama 3.3) | 70B Versatile |
| **Data Science** | pandas, numpy, scipy | Latest |
| **Finance Data** | yfinance | 0.2.28+ |
| **Security** | cryptography (Fernet) | 41.0+ |
| **Deployment** | Render.com | - |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (Neon recommended)
- Groq API key ([Get one here](https://console.groq.com))

### Installation

#### 1. Clone Repository

```bash
git clone https://github.com/yourusername/groq-finance-inference.git
cd groq-finance-inference
```

#### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Configure Environment

Create a `.env` file in the root directory:

```bash
# Database Connection
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require

# Groq API Key
GROQ_API_KEY=gsk_your_groq_api_key_here

# Encryption Key (CRITICAL - Generate a new unique key!)
ENCRYPTION_KEY=your-super-secret-encryption-key-minimum-32-characters
```

**Generate Encryption Key:**
```bash
python3 -c "from app.services.security import SecurityService; print(SecurityService.generate_encryption_key())"
```

#### 5. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 6. Access API

- **API Base URL**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

---

## 📚 API Documentation

### Base URL

```
Production: https://your-app.onrender.com
Development: http://localhost:8000
```

### Authentication

Currently, the API uses environment-based authentication. JWT authentication is planned for future releases.

### Endpoints

#### Portfolio Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze` | Analyze portfolio with 31+ metrics + AI insights |
| `GET` | `/api/analyses` | Get recent portfolio analyses |
| `GET` | `/api/analyses/{id}` | Get specific analysis by ID |
| `GET` | `/api/analyses/{id}/logs` | Get logs for specific analysis |

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "TSLA", "MSFT"],
    "weights": [0.4, 0.3, 0.3],
    "period": "1y",
    "include_ai_analysis": true
  }'
```

**Example Response:**
```json
{
  "analysis_id": 1,
  "symbols": ["AAPL", "TSLA", "MSFT"],
  "weights": [0.4, 0.3, 0.3],
  "period": "1y",
  "metrics": {
    "annual_return": 20.56,
    "volatility": 32.42,
    "sharpe_ratio": 0.51,
    "max_drawdown": 30.81,
    "var_95_annualized": 43.88,
    "skewness": 1.418,
    "kurtosis": 14.844
  },
  "ai_analysis": "Atlas AI analysis text...",
  "status": "COMPLETED",
  "created_at": "2024-01-11T12:00:00Z"
}
```

#### Exchange Connection

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/exchange/connect` | Connect to exchange (credentials encrypted) |
| `GET` | `/api/exchange/status` | Get connection status |
| `POST` | `/api/exchange/disconnect` | Disconnect and delete credentials |

#### Risk Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/guardrails` | Set risk limits (stop loss, leverage, etc.) |
| `GET` | `/api/guardrails` | Get current guard-rails configuration |

#### Strategy Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/strategy` | Set trading strategy (conservative/aggressive) |
| `GET` | `/api/strategy` | Get current strategy configuration |

#### Agent Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/agent/control` | Start/stop/emergency stop agent |
| `GET` | `/api/agent/status` | Get agent status and system information |

#### Monitoring (Thin Client)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/trades` | Get all trades (filter by status) |
| `GET` | `/api/trades/open` | Get open trades only |
| `GET` | `/api/logs` | Get system logs (filter by level) |
| `GET` | `/api/portfolio/history` | Get portfolio history for charts |

### Interactive Documentation

Full interactive API documentation is available at:
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

---

## 💾 Database Schema

### Core Tables

#### `portfolio_analyses`
Stores complete portfolio analysis results with metrics and AI insights.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `symbols` | TEXT[] | Array of asset symbols |
| `weights` | NUMERIC[] | Portfolio weights |
| `period` | VARCHAR(20) | Analysis period |
| `metrics` | JSONB | All 31+ quantitative metrics |
| `ai_analysis` | TEXT | Atlas AI analysis text |
| `status` | VARCHAR(20) | Analysis status |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

#### `encrypted_credentials`
Stores encrypted exchange API credentials.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `exchange` | VARCHAR(50) | Exchange name |
| `credential_type` | VARCHAR(20) | Type (api_key, api_secret) |
| `encrypted_value` | TEXT | AES-256 encrypted value |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

#### `trades`
Trading history and positions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `symbol` | VARCHAR(20) | Trading symbol |
| `side` | VARCHAR(10) | BUY or SELL |
| `quantity` | NUMERIC(20,8) | Trade quantity |
| `entry_price` | NUMERIC(20,8) | Entry price |
| `exit_price` | NUMERIC(20,8) | Exit price (nullable) |
| `pnl` | NUMERIC(20,2) | Profit/Loss |
| `status` | VARCHAR(20) | OPEN, CLOSED, FAILED |
| `entry_time` | TIMESTAMPTZ | Entry timestamp |
| `exit_time` | TIMESTAMPTZ | Exit timestamp (nullable) |

### Performance Optimization

- **15+ Performance Indexes**: Optimized for common query patterns
- **GIN Indexes**: Fast array searches on symbols
- **Composite Indexes**: Multi-column queries optimized
- **Connection Pooling**: Efficient database connection management

See [Database Schema Documentation](./docs/DATABASE.md) for complete details.

---

## 🔒 Security

FinSight API implements enterprise-grade security measures:

### Implemented Security Features

- ✅ **AES-256 Encryption**: All API keys encrypted before storage
- ✅ **Separate Credentials Table**: Sensitive data isolated
- ✅ **Log Masking**: Sensitive data masked in logs
- ✅ **HTTPS Enforcement**: SSL/TLS required in production
- ✅ **Environment Variables**: Secrets never in code
- ✅ **Input Validation**: Pydantic models validate all inputs

### Security Best Practices

- 🔐 Generate unique `ENCRYPTION_KEY` for each deployment
- 🔐 Use HTTPS in production (automatic on Render)
- 🔐 Store all secrets in environment variables
- 🔐 Regularly rotate encryption keys
- 🔐 Monitor access logs for suspicious activity

**📖 For detailed security documentation, see [SECURITY.md](./SECURITY.md)**

---

## 🚀 Deployment

### Render.com (Recommended)

FinSight API is optimized for deployment on Render.com.

**Quick Deploy:**
1. Push code to GitHub
2. Connect repository to Render
3. Configure environment variables
4. Deploy!

**📖 Complete deployment guide: [DEPLOY.md](./DEPLOY.md)**

### Environment Variables

Required environment variables for production:

```bash
DATABASE_URL=postgresql://...          # PostgreSQL connection string
GROQ_API_KEY=gsk_...                   # Groq API key
ENCRYPTION_KEY=...                     # Encryption key (generate new!)
```

### Health Checks

The API includes a health check endpoint for monitoring:

```bash
GET /api/health
```

Returns:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-01-11T12:00:00Z"
}
```

---

## 💻 Development

### Project Structure

```
groq-finance-inference/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application & routes
│   └── services/
│       ├── __init__.py
│       ├── quant_engine.py        # Quantitative analysis engine
│       ├── ai_agent.py            # Atlas AI agent (Groq)
│       ├── database.py           # Database service & connection pool
│       └── security.py           # Encryption & security utilities
├── requirements.txt               # Python dependencies
├── render.yaml                    # Render deployment configuration
├── runtime.txt                    # Python version specification
├── .renderignore                  # Files ignored in Render builds
├── README.md                      # This file
├── DEPLOY.md                      # Deployment guide
└── SECURITY.md                    # Security documentation
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov httpx

# Run tests
pytest

# With coverage
pytest --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

### Development Workflow

1. Create feature branch: `git checkout -b feature/amazing-feature`
2. Make changes and test locally
3. Run tests: `pytest`
4. Commit: `git commit -m "Add amazing feature"`
5. Push: `git push origin feature/amazing-feature`
6. Create Pull Request

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/AmazingFeature`)
3. **Make your changes** with tests
4. **Run tests** (`pytest`)
5. **Commit changes** (`git commit -m 'Add AmazingFeature'`)
6. **Push to branch** (`git push origin feature/AmazingFeature`)
7. **Open a Pull Request**

### Contribution Guidelines

- Write clear, documented code
- Add tests for new features
- Follow PEP 8 style guide
- Update documentation as needed
- Ensure all tests pass

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework
- [Groq](https://groq.com/) - Ultra-fast AI inference
- [yfinance](https://github.com/ranaroussi/yfinance) - Yahoo Finance data
- [Render](https://render.com/) - Cloud hosting platform
- [Neon](https://neon.tech/) - Serverless PostgreSQL

---

## 📧 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/groq-finance-inference/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/groq-finance-inference/discussions)
- **Email**: your.email@example.com

---

<div align="center">

**Made with ❤️ for quantitative finance**

[⬆ Back to Top](#finsight-api)

</div>
