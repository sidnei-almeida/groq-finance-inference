"""
Métricas agregadas (win rate, retorno, série de equity).

Cálculos centralizados para reutilização no dashboard e nos serviços.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

def _f(x: Any) -> float:
    return float(x) if x is not None else 0.0


def compute_unrealized_for_position(
    quantity: float,
    avg_entry_price: float,
    current_price: float,
) -> float:
    """PnL não realizado mark-to-market (sem taxas sobre posição aberta)."""
    return (current_price - avg_entry_price) * quantity


def compute_equity(
    cash_balance: float,
    positions: List[Dict[str, Any]],
) -> float:
    """Equity = caixa + valor de mercado das posições."""
    mtm = sum(_f(p["quantity"]) * _f(p["current_price"]) for p in positions)
    return cash_balance + mtm


def compute_total_return_pct(initial_balance: float, equity: float) -> float:
    if initial_balance <= 0:
        return 0.0
    return (equity - initial_balance) / initial_balance * 100.0


def win_rate_from_trades(closed_trades: List[Dict[str, Any]]) -> Tuple[float, int, int]:
    """
    Win rate sobre trades fechados com realized_pnl preenchido.

    Returns:
        (win_rate_pct, wins, losses) — empates (pnl==0) não contam como win.
    """
    relevant = [
        t
        for t in closed_trades
        if t.get("realized_pnl") is not None and t.get("status") == "CLOSED"
    ]
    if not relevant:
        return 0.0, 0, 0
    wins = sum(1 for t in relevant if _f(t["realized_pnl"]) > 0)
    losses = sum(1 for t in relevant if _f(t["realized_pnl"]) < 0)
    denom = len(relevant)
    return (wins / denom * 100.0) if denom else 0.0, wins, losses


def build_dashboard_kpis(
    user_id: int,
    portfolio: Dict[str, Any],
    positions: List[Dict[str, Any]],
    all_trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Consolida KPIs para o schema DashboardSummary."""
    closed = [t for t in all_trades if t.get("status") == "CLOSED"]
    win_rate, _, _ = win_rate_from_trades(closed)
    initial = _f(portfolio["initial_balance"])
    cash = _f(portfolio["cash_balance"])
    equity = compute_equity(cash, positions)
    ret = compute_total_return_pct(initial, equity)

    return {
        "user_id": user_id,
        "initial_balance": initial,
        "current_cash": cash,
        "total_equity": equity,
        "total_return_pct": ret,
        "total_trades": len(all_trades),
        "closed_trades": len(closed),
        "win_rate": win_rate,
        "open_positions_count": len(positions),
        "allocation_pct": _f(portfolio.get("allocation_pct", 0.1)),
    }
