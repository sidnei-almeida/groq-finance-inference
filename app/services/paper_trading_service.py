"""
Regras de negócio do paper trading: execução simulada, métricas e snapshots.

Extensível: fee_rate e slippage_bps no portfólio (preparado para taxas/slippage).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.core.paper_defaults import (
    DEFAULT_ALLOCATION_PCT,
    DEFAULT_FEE_RATE,
    DEFAULT_INITIAL_BALANCE,
    DEFAULT_SLIPPAGE_BPS,
)
from app.repositories.paper_trading_repo import PaperTradingRepository, get_paper_repo
from app.services.metrics_service import (
    compute_equity,
    compute_total_return_pct,
    compute_unrealized_for_position,
)
from app.services.portfolio_service import get_portfolio_service

logger = logging.getLogger(__name__)


def _f(x: Any) -> float:
    return float(x) if x is not None else 0.0


def apply_slippage(raw_price: float, side: str, slippage_bps: float) -> float:
    """Apply slippage in bps (buys pay more, sells receive less)."""
    bps = _f(slippage_bps)
    if side.upper() == "BUY":
        return raw_price * (1.0 + bps / 10_000.0)
    return raw_price * (1.0 - bps / 10_000.0)


class PaperTradingService:
    """Process BUY/SELL signals and maintain portfolio, positions, and trades."""

    def __init__(self) -> None:
        self.repo = get_paper_repo()
        self._portfolio_svc = get_portfolio_service()

    def ensure_portfolio(
        self,
        user_id: int,
        initial_balance: float = DEFAULT_INITIAL_BALANCE,
    ) -> Dict[str, Any]:
        """Ensure a paper portfolio exists for the user."""
        self._portfolio_svc.require_user(user_id)
        existing = self.repo.get_portfolio_by_user(user_id)
        if existing:
            return existing
        self.repo.create_portfolio(
            user_id=user_id,
            initial_balance=initial_balance,
            allocation_pct=DEFAULT_ALLOCATION_PCT,
            fee_rate=DEFAULT_FEE_RATE,
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
        )
        row = self.repo.get_portfolio_by_user(user_id)
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create paper portfolio")
        self._snapshot_equity(row)
        return row

    def _snapshot_equity(self, portfolio_row: Dict[str, Any]) -> None:
        pid = int(portfolio_row["id"])
        positions = self.repo.list_positions(pid)
        cash = _f(portfolio_row["cash_balance"])
        eq = compute_equity(cash, positions)
        self.repo.insert_equity_snapshot(pid, eq, cash)

    def _persist_metrics(self, portfolio_row: Dict[str, Any]) -> Dict[str, Any]:
        pid = int(portfolio_row["id"])
        positions = self.repo.list_positions(pid)
        cash = _f(portfolio_row["cash_balance"])
        initial = _f(portfolio_row["initial_balance"])
        equity = compute_equity(cash, positions)
        ret = compute_total_return_pct(initial, equity)
        self.repo.update_portfolio_row(pid, cash, equity, ret)
        portfolio_row["cash_balance"] = cash
        portfolio_row["equity"] = equity
        portfolio_row["total_return_pct"] = ret
        self.repo.insert_equity_snapshot(pid, equity, cash)
        return portfolio_row

    def _update_position_prices(
        self,
        portfolio_id: int,
        symbol: str,
        mark_price: float,
    ) -> None:
        """Update mark price and unrealized PnL for signal symbol position."""
        positions = self.repo.list_positions(portfolio_id)
        for p in positions:
            sym = str(p["symbol"])
            px = mark_price if sym == symbol else _f(p["current_price"])
            qty = _f(p["quantity"])
            avg = _f(p["avg_entry_price"])
            unreal = compute_unrealized_for_position(qty, avg, px)
            self.repo.upsert_position(
                portfolio_id,
                sym,
                qty,
                avg,
                px,
                unreal,
            )

    def process_signal(self, user_id: int, signal_id: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Load a signal and execute BUY or SELL."""
        self._portfolio_svc.require_user(user_id)
        portfolio = self.repo.get_portfolio_by_user(user_id)
        if not portfolio:
            raise HTTPException(
                status_code=400,
                detail="Create a portfolio with POST .../seed-balance before processing signals.",
            )
        signal = self.repo.get_signal(signal_id, user_id=user_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")

        side = str(signal["signal_type"]).upper()
        symbol = str(signal["symbol"]).upper()
        raw_price = _f(signal["signal_price"])
        fee = _f(portfolio["fee_rate"])
        slip = _f(portfolio["slippage_bps"])

        trades_out: List[Dict[str, Any]] = []
        pid = int(portfolio["id"])

        if side == "BUY":
            trades_out = self._execute_buy(
                portfolio, signal_id, symbol, raw_price, fee, slip
            )
        elif side == "SELL":
            trades_out = self._execute_sell(
                portfolio, signal_id, symbol, raw_price, fee, slip
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid signal type")

        self._update_position_prices(pid, symbol, raw_price)
        portfolio = self.repo.get_portfolio_by_user(user_id) or portfolio
        portfolio = self._persist_metrics(portfolio)
        return portfolio, trades_out

    def _execute_buy(
        self,
        portfolio: Dict[str, Any],
        signal_id: int,
        symbol: str,
        raw_price: float,
        fee_rate: float,
        slippage_bps: float,
    ) -> List[Dict[str, Any]]:
        pid = int(portfolio["id"])
        cash = _f(portfolio["cash_balance"])
        alloc_pct = _f(portfolio["allocation_pct"])
        fill = apply_slippage(raw_price, "BUY", slippage_bps)
        allocation = cash * alloc_pct
        # Per-unit cost including buy fee.
        unit_cost = fill * (1.0 + fee_rate)
        if unit_cost <= 0 or cash <= 0:
            return []
        max_qty = min(allocation / unit_cost, cash / unit_cost)
        if max_qty <= 0:
            logger.info("Buy skipped: insufficient cash or zero allocation")
            return []

        cost_total = max_qty * unit_cost
        new_cash = cash - cost_total
        portfolio["cash_balance"] = new_cash

        pos = self.repo.get_position(pid, symbol)
        if pos:
            old_q = _f(pos["quantity"])
            old_avg = _f(pos["avg_entry_price"])
            new_q = old_q + max_qty
            new_avg = (old_q * old_avg + max_qty * fill) / new_q if new_q > 0 else fill
        else:
            new_q = max_qty
            new_avg = fill

        unreal = compute_unrealized_for_position(new_q, new_avg, fill)
        self.repo.upsert_position(pid, symbol, new_q, new_avg, fill, unreal)

        self.repo.update_cash_balance(pid, new_cash)

        tid = self.repo.insert_trade(
            pid, signal_id, symbol, "BUY", max_qty, fill, "OPEN"
        )
        trade = self.repo.get_trade(tid)
        return [trade] if trade else []

    def _execute_sell(
        self,
        portfolio: Dict[str, Any],
        signal_id: int,
        symbol: str,
        raw_price: float,
        fee_rate: float,
        slippage_bps: float,
    ) -> List[Dict[str, Any]]:
        pid = int(portfolio["id"])
        cash = _f(portfolio["cash_balance"])
        fill = apply_slippage(raw_price, "SELL", slippage_bps)

        open_trades = self.repo.list_open_trades_fifo(pid, symbol)
        pos = self.repo.get_position(pid, symbol)
        if not open_trades or not pos:
            logger.info("Sell skipped: no open position for %s", symbol)
            return []

        closed: List[Dict[str, Any]] = []
        for tr in open_trades:
            tqty = _f(tr["quantity"])
            entry = _f(tr["entry_price"])
            proceeds = tqty * fill * (1.0 - fee_rate)
            cost_basis = tqty * entry * (1.0 + fee_rate)
            realized = proceeds - cost_basis
            tid = int(tr["id"])
            self.repo.close_trade(tid, fill, realized)
            cash += proceeds
            got = self.repo.get_trade(tid)
            if got:
                closed.append(got)

        self.repo.delete_position(pid, symbol)
        self.repo.update_cash_balance(pid, cash)
        portfolio["cash_balance"] = cash
        return closed

    def reset_simulation(self, user_id: int, initial_balance: float) -> Dict[str, Any]:
        p = self.ensure_portfolio(user_id, initial_balance=initial_balance)
        pid = int(p["id"])
        self.repo.reset_portfolio_data(pid, initial_balance)
        p2 = self.repo.get_portfolio_by_user(user_id)
        assert p2 is not None
        self._persist_metrics(p2)
        return p2

    def seed_balance(self, user_id: int, initial_balance: float) -> Dict[str, Any]:
        """Set initial balance; create portfolio if needed."""
        self._portfolio_svc.require_user(user_id)
        existing = self.repo.get_portfolio_by_user(user_id)
        if not existing:
            return self.ensure_portfolio(user_id, initial_balance=initial_balance)
        pid = int(existing["id"])
        self.repo.reset_portfolio_data(pid, initial_balance)
        p2 = self.repo.get_portfolio_by_user(user_id)
        assert p2 is not None
        self._persist_metrics(p2)
        return p2

    def process_inline_signal(
        self,
        user_id: int,
        symbol: str,
        signal_type: str,
        signal_price: float,
        confidence_score: Optional[float] = None,
        explanation: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Create and process a signal in one operation."""
        sid = self.repo.insert_signal(
            user_id,
            symbol,
            signal_type.upper(),
            signal_price,
            confidence_score,
            explanation,
        )
        return self.process_signal(user_id, sid)


def get_paper_trading_service() -> PaperTradingService:
    return PaperTradingService()
