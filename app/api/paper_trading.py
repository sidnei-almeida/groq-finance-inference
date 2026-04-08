"""REST routes — paper trading, signals, and simulation (Phase 2)."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.schemas.paper_trading import (
    DashboardSummary,
    EquityPoint,
    PaperTradingResult,
    PortfolioRead,
    PositionRead,
    ProcessInlineSignalRequest,
    ProcessSignalRequest,
    SeedBalanceRequest,
    SignalCreate,
    SignalRead,
    SimulationResetResponse,
    TradeRead,
)
from app.services.paper_trading_service import get_paper_trading_service
from app.services.portfolio_service import get_portfolio_service

router = APIRouter(prefix="/api/paper", tags=["Paper Trading"])

_paper = get_paper_trading_service()
_portfolio = get_portfolio_service()


def _port(d: Dict[str, Any]) -> PortfolioRead:
    return PortfolioRead.model_validate({**d})


@router.get("/portfolio/{user_id}", response_model=PortfolioRead)
async def get_portfolio(user_id: int) -> PortfolioRead:
    row = _portfolio.get_portfolio(user_id)
    return _port(row)


@router.get("/portfolio/{user_id}/summary", response_model=DashboardSummary)
async def get_summary(user_id: int) -> DashboardSummary:
    kpis = _portfolio.get_summary(user_id)
    return DashboardSummary.model_validate(kpis)


@router.get("/portfolio/{user_id}/positions", response_model=List[PositionRead])
async def get_positions(user_id: int) -> List[PositionRead]:
    rows = _portfolio.list_positions(user_id)
    return [PositionRead.model_validate(r) for r in rows]


@router.get("/portfolio/{user_id}/trades", response_model=List[TradeRead])
async def get_trades(user_id: int, limit: int = Query(200, ge=1, le=500)) -> List[TradeRead]:
    rows = _portfolio.list_trades(user_id, limit=limit)
    return [TradeRead.model_validate(r) for r in rows]


@router.get("/portfolio/{user_id}/equity-history", response_model=List[EquityPoint])
async def get_equity_history(user_id: int, limit: int = Query(500, ge=1, le=2000)) -> List[EquityPoint]:
    rows = _portfolio.equity_history(user_id, limit=limit)
    return [EquityPoint.model_validate(r) for r in rows]


@router.post("/signals", response_model=SignalRead)
async def create_signal(body: SignalCreate) -> SignalRead:
    sid = _paper.repo.insert_signal(
        None,
        body.symbol,
        body.signal_type.value,
        body.signal_price,
        body.confidence_score,
        body.explanation,
    )
    row = _paper.repo.get_signal(sid)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create signal")
    return SignalRead.model_validate(row)


@router.get("/signals", response_model=List[SignalRead])
async def list_signals(limit: int = Query(100, ge=1, le=500)) -> List[SignalRead]:
    rows = _paper.repo.list_signals(limit=limit)
    return [SignalRead.model_validate(r) for r in rows]


@router.post("/signals/process/{user_id}", response_model=PaperTradingResult)
async def process_signal_by_id(user_id: int, body: ProcessSignalRequest) -> PaperTradingResult:
    try:
        portfolio, trades = _paper.process_signal(user_id, body.signal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return PaperTradingResult(
        success=True,
        message="Signal processed",
        signal_id=body.signal_id,
        portfolio=_port(portfolio),
        trades_affected=[TradeRead.model_validate(t) for t in trades],
    )


@router.post("/simulation/{user_id}/reset", response_model=SimulationResetResponse)
async def reset_simulation(user_id: int, body: SeedBalanceRequest) -> SimulationResetResponse:
    p = _paper.reset_simulation(user_id, body.initial_balance)
    return SimulationResetResponse(
        user_id=user_id,
        portfolio_id=int(p["id"]),
        initial_balance=float(p["initial_balance"]),
        message="Simulation reset",
    )


@router.post("/simulation/{user_id}/seed-balance", response_model=PortfolioRead)
async def seed_balance(user_id: int, body: SeedBalanceRequest) -> PortfolioRead:
    p = _paper.seed_balance(user_id, body.initial_balance)
    return _port(p)


@router.post("/simulation/{user_id}/process-signal", response_model=PaperTradingResult)
async def process_inline_signal(user_id: int, body: ProcessInlineSignalRequest) -> PaperTradingResult:
    try:
        portfolio, trades = _paper.process_inline_signal(
            user_id,
            body.symbol,
            body.signal_type.value,
            body.signal_price,
            body.confidence_score,
            body.explanation,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return PaperTradingResult(
        success=True,
        message="Signal created and processed",
        portfolio=portfolio and _port(portfolio),
        trades_affected=[TradeRead.model_validate(t) for t in trades],
    )


@router.post("/signals/mock-batch", response_model=List[SignalRead])
async def mock_signals_batch() -> List[SignalRead]:
    """Create a sample signal batch for testing (extra)."""
    samples = [
        ("AAPL", "BUY", 180.0),
        ("MSFT", "BUY", 400.0),
        ("AAPL", "SELL", 185.0),
    ]
    out: List[SignalRead] = []
    for sym, side, px in samples:
        sid = _paper.repo.insert_signal(None, sym, side, px, 0.75, "Mock batch")
        row = _paper.repo.get_signal(sid)
        if row:
            out.append(SignalRead.model_validate(row))
    return out
