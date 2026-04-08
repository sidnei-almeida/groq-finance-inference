"""
Tipos de domínio para paper trading (espelham colunas SQL).

Os repositórios retornam dict compatível com estes TypedDicts para type hints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, TypedDict


class PaperPortfolioRow(TypedDict, total=False):
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


class PaperPositionRow(TypedDict, total=False):
    id: int
    portfolio_id: int
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    opened_at: datetime
    updated_at: datetime


class PaperTradeRow(TypedDict, total=False):
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


class PaperSignalRow(TypedDict, total=False):
    id: int
    symbol: str
    signal_type: str
    signal_price: float
    confidence_score: Optional[float]
    explanation: Optional[str]
    created_at: datetime
