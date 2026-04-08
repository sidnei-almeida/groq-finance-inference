"""REST schemas for paper trading, signals, and simulation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class SignalSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SignalCreate(BaseModel):
    """Payload to create a signal (manual input or future integration)."""

    symbol: str = Field(..., min_length=1, max_length=64)
    signal_type: SignalSide
    signal_price: float = Field(..., gt=0)
    confidence_score: Optional[float] = Field(None, ge=0, le=1)
    explanation: Optional[str] = Field(None, max_length=4000)

    @field_validator("symbol")
    @classmethod
    def strip_symbol(cls, v: str) -> str:
        return v.strip().upper()


class SignalRead(BaseModel):
    id: int
    symbol: str
    signal_type: str
    signal_price: float
    confidence_score: Optional[float]
    explanation: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioRead(BaseModel):
    id: int
    user_id: int
    initial_balance: float
    cash_balance: float
    equity: float
    total_return_pct: float
    allocation_pct: float
    fee_rate: float
    slippage_bps: float
    created_at: datetime
    updated_at: datetime


class PositionRead(BaseModel):
    id: int
    portfolio_id: int
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    opened_at: datetime
    updated_at: datetime


class TradeRead(BaseModel):
    id: int
    portfolio_id: int
    signal_id: Optional[int]
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: Optional[float]
    realized_pnl: Optional[float]
    status: str
    opened_at: datetime
    closed_at: Optional[datetime]


class EquityPoint(BaseModel):
    """Equity time-series point for charts."""

    recorded_at: datetime
    equity: float
    cash_balance: float


class DashboardSummary(BaseModel):
    """Consolidated dashboard KPIs."""

    user_id: int
    initial_balance: float
    current_cash: float
    total_equity: float
    total_return_pct: float
    total_trades: int
    closed_trades: int
    win_rate: float
    open_positions_count: int
    allocation_pct: float


class SeedBalanceRequest(BaseModel):
    """Set initial balance (rebuild metrics; use after reset or first run)."""

    initial_balance: float = Field(..., gt=0)


class ProcessSignalRequest(BaseModel):
    """Process an existing signal by ID."""

    signal_id: int = Field(..., gt=0)


class ProcessInlineSignalRequest(BaseModel):
    """Process inline signal without prior POST to /signals."""

    symbol: str
    signal_type: SignalSide
    signal_price: float = Field(..., gt=0)
    confidence_score: Optional[float] = Field(None, ge=0, le=1)
    explanation: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def strip_symbol(cls, v: str) -> str:
        return v.strip().upper()


class PaperTradingResult(BaseModel):
    """Simulation execution response."""

    success: bool
    message: str
    signal_id: Optional[int] = None
    portfolio: Optional[PortfolioRead] = None
    trades_affected: List[TradeRead] = Field(default_factory=list)


class SimulationResetResponse(BaseModel):
    user_id: int
    portfolio_id: int
    initial_balance: float
    message: str
