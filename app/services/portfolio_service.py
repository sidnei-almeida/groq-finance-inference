"""Portfolio queries, summaries, and history for the dashboard."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException

from app.repositories.paper_trading_repo import get_paper_repo
from app.services.database import get_db
from app.services.metrics_service import build_dashboard_kpis, compute_equity, compute_total_return_pct


class PortfolioService:
    """Orchestrates reads and ensures a portfolio exists when required."""

    def __init__(self) -> None:
        self.repo = get_paper_repo()

    def require_user(self, user_id: int) -> None:
        user = get_db().get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    def get_portfolio(self, user_id: int) -> Dict[str, Any]:
        self.require_user(user_id)
        p = self.repo.get_portfolio_by_user(user_id)
        if not p:
            raise HTTPException(
                status_code=404,
                detail="Paper portfolio not found. Use seed-balance or reset.",
            )
        return p

    def get_summary(self, user_id: int) -> Dict[str, Any]:
        p = self.get_portfolio(user_id)
        pid = int(p["id"])
        positions = self.repo.list_positions(pid)
        trades = self.repo.list_trades(pid, limit=500)
        kpis = build_dashboard_kpis(user_id, p, positions, trades)
        return kpis

    def list_positions(self, user_id: int) -> List[Dict[str, Any]]:
        p = self.get_portfolio(user_id)
        return self.repo.list_positions(int(p["id"]))

    def list_trades(self, user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        p = self.get_portfolio(user_id)
        return self.repo.list_trades(int(p["id"]), limit=limit)

    def equity_history(self, user_id: int, limit: int = 500) -> List[Dict[str, Any]]:
        p = self.get_portfolio(user_id)
        return self.repo.list_equity_history(int(p["id"]), limit=limit)

    def refresh_metrics_row(self, portfolio_id: int, portfolio_row: Dict[str, Any]) -> Dict[str, Any]:
        """Recalculate and persist portfolio equity and total return."""
        positions = self.repo.list_positions(portfolio_id)
        cash = float(portfolio_row["cash_balance"])
        initial = float(portfolio_row["initial_balance"])
        equity = compute_equity(cash, positions)
        ret = compute_total_return_pct(initial, equity)
        self.repo.update_portfolio_row(portfolio_id, cash, equity, ret)
        portfolio_row["equity"] = equity
        portfolio_row["total_return_pct"] = ret
        return portfolio_row


def get_portfolio_service() -> PortfolioService:
    return PortfolioService()
