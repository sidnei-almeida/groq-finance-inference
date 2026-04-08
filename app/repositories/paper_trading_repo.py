"""
Repositório paper trading — SQL via psycopg2 (mesmo padrão do DatabaseService).

Mantém SQL explícito para facilitar migração futura (PostgreSQL já em uso).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.services.database import get_db

logger = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


class PaperTradingRepository:
    """CRUD e consultas para portfólio, posições, trades, sinais e equity."""

    def insert_signal(
        self,
        user_id: Optional[int],
        symbol: str,
        signal_type: str,
        signal_price: float,
        confidence_score: Optional[float],
        explanation: Optional[str],
    ) -> int:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO paper_signals
                    (user_id, symbol, signal_type, signal_price, confidence_score, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (user_id, symbol, signal_type, signal_price, confidence_score, explanation),
                )
                sid = cur.fetchone()[0]
            conn.commit()
        return int(sid)

    def get_signal(self, signal_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if user_id is None:
                    cur.execute("SELECT * FROM paper_signals WHERE id = %s;", (signal_id,))
                else:
                    cur.execute(
                        """
                        SELECT * FROM paper_signals
                        WHERE id = %s AND (user_id = %s OR user_id IS NULL);
                        """,
                        (signal_id, user_id),
                    )
                row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def list_signals(self, limit: int = 100, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if user_id is None:
                    cur.execute(
                        """
                        SELECT * FROM paper_signals
                        ORDER BY created_at DESC
                        LIMIT %s;
                        """,
                        (limit,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM paper_signals
                        WHERE user_id = %s OR user_id IS NULL
                        ORDER BY created_at DESC
                        LIMIT %s;
                        """,
                        (user_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def get_portfolio_by_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM paper_portfolios WHERE user_id = %s;",
                    (user_id,),
                )
                row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def create_portfolio(
        self,
        user_id: int,
        initial_balance: float,
        allocation_pct: float,
        fee_rate: float,
        slippage_bps: float,
    ) -> int:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO paper_portfolios
                    (user_id, initial_balance, cash_balance, equity, total_return_pct,
                     allocation_pct, fee_rate, slippage_bps)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        user_id,
                        initial_balance,
                        initial_balance,
                        initial_balance,
                        0,
                        allocation_pct,
                        fee_rate,
                        slippage_bps,
                    ),
                )
                pid = cur.fetchone()[0]
            conn.commit()
        return int(pid)

    def update_cash_balance(self, portfolio_id: int, cash_balance: float) -> None:
        """Atualiza apenas o caixa (durante execução de trades antes do snapshot final)."""

        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE paper_portfolios
                    SET cash_balance = %s
                    WHERE id = %s;
                    """,
                    (cash_balance, portfolio_id),
                )
            conn.commit()

    def update_portfolio_row(
        self,
        portfolio_id: int,
        cash_balance: float,
        equity: float,
        total_return_pct: float,
    ) -> None:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE paper_portfolios
                    SET cash_balance = %s, equity = %s, total_return_pct = %s
                    WHERE id = %s;
                    """,
                    (cash_balance, equity, total_return_pct, portfolio_id),
                )
            conn.commit()

    def update_portfolio_initial(
        self,
        portfolio_id: int,
        initial_balance: float,
    ) -> None:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE paper_portfolios
                    SET initial_balance = %s, cash_balance = %s, equity = %s,
                        total_return_pct = 0
                    WHERE id = %s;
                    """,
                    (initial_balance, initial_balance, initial_balance, portfolio_id),
                )
            conn.commit()

    def set_portfolio_risk_params(
        self,
        portfolio_id: int,
        allocation_pct: Optional[float] = None,
        fee_rate: Optional[float] = None,
        slippage_bps: Optional[float] = None,
    ) -> None:
        fields: List[str] = []
        values: List[Any] = []
        if allocation_pct is not None:
            fields.append("allocation_pct = %s")
            values.append(allocation_pct)
        if fee_rate is not None:
            fields.append("fee_rate = %s")
            values.append(fee_rate)
        if slippage_bps is not None:
            fields.append("slippage_bps = %s")
            values.append(slippage_bps)
        if not fields:
            return
        values.append(portfolio_id)
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE paper_portfolios
                    SET {", ".join(fields)}
                    WHERE id = %s;
                    """,
                    values,
                )
            conn.commit()

    def list_positions(self, portfolio_id: int) -> List[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM paper_positions
                    WHERE portfolio_id = %s
                    ORDER BY symbol;
                    """,
                    (portfolio_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def get_position(self, portfolio_id: int, symbol: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM paper_positions
                    WHERE portfolio_id = %s AND symbol = %s;
                    """,
                    (portfolio_id, symbol),
                )
                row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def upsert_position(
        self,
        portfolio_id: int,
        symbol: str,
        quantity: float,
        avg_entry_price: float,
        current_price: float,
        unrealized_pnl: float,
        opened_at: Optional[datetime] = None,
    ) -> None:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                if opened_at:
                    cur.execute(
                        """
                        INSERT INTO paper_positions
                        (portfolio_id, symbol, quantity, avg_entry_price, current_price,
                         unrealized_pnl, opened_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (portfolio_id, symbol)
                        DO UPDATE SET
                            quantity = EXCLUDED.quantity,
                            avg_entry_price = EXCLUDED.avg_entry_price,
                            current_price = EXCLUDED.current_price,
                            unrealized_pnl = EXCLUDED.unrealized_pnl,
                            updated_at = NOW();
                        """,
                        (
                            portfolio_id,
                            symbol,
                            quantity,
                            avg_entry_price,
                            current_price,
                            unrealized_pnl,
                            opened_at,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO paper_positions
                        (portfolio_id, symbol, quantity, avg_entry_price, current_price,
                         unrealized_pnl)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (portfolio_id, symbol)
                        DO UPDATE SET
                            quantity = EXCLUDED.quantity,
                            avg_entry_price = EXCLUDED.avg_entry_price,
                            current_price = EXCLUDED.current_price,
                            unrealized_pnl = EXCLUDED.unrealized_pnl,
                            updated_at = NOW();
                        """,
                        (
                            portfolio_id,
                            symbol,
                            quantity,
                            avg_entry_price,
                            current_price,
                            unrealized_pnl,
                        ),
                    )
            conn.commit()

    def delete_position(self, portfolio_id: int, symbol: str) -> None:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM paper_positions
                    WHERE portfolio_id = %s AND symbol = %s;
                    """,
                    (portfolio_id, symbol),
                )
            conn.commit()

    def insert_trade(
        self,
        portfolio_id: int,
        signal_id: Optional[int],
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        status: str = "OPEN",
    ) -> int:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO paper_trades
                    (portfolio_id, signal_id, symbol, side, quantity, entry_price, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        portfolio_id,
                        signal_id,
                        symbol,
                        side,
                        quantity,
                        entry_price,
                        status,
                    ),
                )
                tid = cur.fetchone()[0]
            conn.commit()
        return int(tid)

    def list_open_trades_fifo(self, portfolio_id: int, symbol: str) -> List[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM paper_trades
                    WHERE portfolio_id = %s AND symbol = %s AND status = 'OPEN'
                    ORDER BY opened_at ASC, id ASC;
                    """,
                    (portfolio_id, symbol),
                )
                return [dict(r) for r in cur.fetchall()]

    def get_trade(self, trade_id: int) -> Optional[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM paper_trades WHERE id = %s;", (trade_id,))
                row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        realized_pnl: float,
    ) -> None:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE paper_trades
                    SET exit_price = %s, realized_pnl = %s, status = 'CLOSED',
                        closed_at = NOW()
                    WHERE id = %s;
                    """,
                    (exit_price, realized_pnl, trade_id),
                )
            conn.commit()

    def list_trades(
        self,
        portfolio_id: int,
        limit: int = 200,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if status:
                    cur.execute(
                        """
                        SELECT * FROM paper_trades
                        WHERE portfolio_id = %s AND status = %s
                        ORDER BY opened_at DESC
                        LIMIT %s;
                        """,
                        (portfolio_id, status, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM paper_trades
                        WHERE portfolio_id = %s
                        ORDER BY opened_at DESC
                        LIMIT %s;
                        """,
                        (portfolio_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def insert_equity_snapshot(
        self,
        portfolio_id: int,
        equity: float,
        cash_balance: float,
        recorded_at: Optional[datetime] = None,
    ) -> int:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                if recorded_at:
                    cur.execute(
                        """
                        INSERT INTO paper_equity_history
                        (portfolio_id, equity, cash_balance, recorded_at)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (portfolio_id, equity, cash_balance, recorded_at),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO paper_equity_history
                        (portfolio_id, equity, cash_balance)
                        VALUES (%s, %s, %s)
                        RETURNING id;
                        """,
                        (portfolio_id, equity, cash_balance),
                    )
                eid = cur.fetchone()[0]
            conn.commit()
        return int(eid)

    def list_equity_history(
        self,
        portfolio_id: int,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT equity, cash_balance, recorded_at
                    FROM paper_equity_history
                    WHERE portfolio_id = %s
                    ORDER BY recorded_at ASC
                    LIMIT %s;
                    """,
                    (portfolio_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def reset_portfolio_data(self, portfolio_id: int, initial_balance: float) -> None:
        """Remove posições, trades e histórico; redefine caixa e equity."""

        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM paper_equity_history WHERE portfolio_id = %s;",
                    (portfolio_id,),
                )
                cur.execute(
                    "DELETE FROM paper_trades WHERE portfolio_id = %s;",
                    (portfolio_id,),
                )
                cur.execute(
                    "DELETE FROM paper_positions WHERE portfolio_id = %s;",
                    (portfolio_id,),
                )
                cur.execute(
                    """
                    UPDATE paper_portfolios
                    SET initial_balance = %s,
                        cash_balance = %s,
                        equity = %s,
                        total_return_pct = 0,
                        updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (initial_balance, initial_balance, initial_balance, portfolio_id),
                )
            conn.commit()


def get_paper_repo() -> PaperTradingRepository:
    return PaperTradingRepository()
