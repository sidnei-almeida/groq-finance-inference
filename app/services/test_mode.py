"""Test Mode Service - manages mock wallet and paper trading integration."""

import logging
import random
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.repositories.paper_trading_repo import get_paper_repo
from app.services.database import get_db
from app.services.paper_trading_service import get_paper_trading_service
from app.services.portfolio_service import get_portfolio_service

logger = logging.getLogger(__name__)


class TestModeService:
    """Service that manages test mode."""
    
    # Base prices for simulation
    BASE_PRICES = {
        "BTC": 45000.00,
        "ETH": 2800.00,
        "AAPL": 175.50
    }
    
    # Max percentage variation for simulated price movement
    PRICE_VARIATION = 0.02  # 2%
    
    @staticmethod
    def connect_test_mode(user_id: int) -> Dict[str, Any]:
        """
        Connect a user to test mode.
        
        Args:
            user_id: User ID
            
        Returns:
            Test mode exchange status
        """
        db = get_db()
        
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Verificar se já existe conexão
                    cur.execute("""
                        SELECT * FROM test_mode_connections
                        WHERE user_id = %s
                    """, (user_id,))
                    
                    existing = cur.fetchone()
                    
                    if existing:
                        # Atualizar timestamp
                        cur.execute("""
                            UPDATE test_mode_connections
                            SET connected = TRUE,
                                connected_at = CURRENT_TIMESTAMP,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = %s
                        """, (user_id,))
                    else:
                        # Create new connection
                        cur.execute("""
                            INSERT INTO test_mode_connections
                            (user_id, connected, exchange, test_mode, balance_total, 
                             balance_available, balance_in_positions, currency, connected_at)
                            VALUES (%s, TRUE, 'test', TRUE, 10000.00, 8500.00, 1500.00, 'USD', CURRENT_TIMESTAMP)
                        """, (user_id,))
                        
                        # Create initial demo trades
                        TestModeService._create_initial_trades(cur, user_id)
                        
                        # Create initial logs
                        TestModeService._create_initial_logs(cur, user_id)
                    
                    conn.commit()
            # Ensure active paper portfolio in mocked mode
            paper_service = get_paper_trading_service()
            paper_service.ensure_portfolio(user_id, initial_balance=10000.0)
            TestModeService.sync_mock_balance_from_paper(user_id)
            return TestModeService.get_test_mode_status(user_id)
        except Exception as e:
            logger.error(f"Error connecting test mode: {str(e)}")
            raise
    
    @staticmethod
    def disconnect_test_mode(user_id: int) -> Dict[str, Any]:
        """
        Disconnect user from test mode.
        
        Args:
            user_id: User ID
            
        Returns:
            Disconnect confirmation
        """
        db = get_db()
        
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE test_mode_connections
                        SET connected = FALSE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                    """, (user_id,))
                    conn.commit()
            
            return {"disconnected": True, "message": "Test mode disconnected"}
        except Exception as e:
            logger.error(f"Error disconnecting test mode: {str(e)}")
            raise
    
    @staticmethod
    def get_test_mode_status(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the user's test mode status.
        
        Args:
            user_id: User ID
            
        Returns:
            Exchange status or None when disconnected
        """
        db = get_db()
        
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM test_mode_connections
                        WHERE user_id = %s AND connected = TRUE
                    """, (user_id,))
                    
                    row = cur.fetchone()
                    if not row:
                        return None
                    
                    # Converter para dict
                    columns = [desc[0] for desc in cur.description]
                    connection = dict(zip(columns, row))
                    
                    status = {
                        "connected": connection["connected"],
                        "exchange": connection["exchange"],
                        "test_mode": connection["test_mode"],
                        "wallet_mode": "mocked",
                        "balance": {
                            "total": float(connection["balance_total"]),
                            "available": float(connection["balance_available"]),
                            "in_positions": float(connection["balance_in_positions"]),
                            "currency": connection["currency"]
                        },
                        "connected_at": connection["connected_at"].isoformat() if isinstance(connection["connected_at"], datetime) else str(connection["connected_at"]),
                        "user_id": connection["user_id"]
                    }
                    return status
        except Exception as e:
            logger.error(f"Error getting test mode status: {str(e)}")
            return None

    @staticmethod
    def is_mocked_mode_active(user_id: int) -> bool:
        """Return whether user's wallet is currently in mocked mode."""
        db = get_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1
                        FROM test_mode_connections
                        WHERE user_id = %s AND connected = TRUE AND test_mode = TRUE;
                        """,
                        (user_id,),
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    @staticmethod
    def sync_mock_balance_from_paper(user_id: int) -> None:
        """Sync test_mode balances from the paper portfolio state."""
        repo = get_paper_repo()
        portfolio = repo.get_portfolio_by_user(user_id)
        if not portfolio:
            return
        pid = int(portfolio["id"])
        cash = float(portfolio["cash_balance"])
        equity = float(portfolio["equity"])
        in_positions = max(equity - cash, 0.0)
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE test_mode_connections
                    SET balance_total = %s,
                        balance_available = %s,
                        balance_in_positions = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND test_mode = TRUE;
                    """,
                    (equity, cash, in_positions, user_id),
                )
            conn.commit()
    
    @staticmethod
    def get_test_mode_trades(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get open trades in test mode.
        
        Args:
            user_id: User ID
            limit: Result limit
            
        Returns:
            Trade list
        """
        # Prioritize real paper simulation trades when mock wallet is active.
        if TestModeService.is_mocked_mode_active(user_id):
            try:
                psvc = get_portfolio_service()
                trades = psvc.list_trades(user_id, limit=limit)
                out: List[Dict[str, Any]] = []
                for tr in trades:
                    entry = float(tr["entry_price"])
                    current_price = float(tr["exit_price"]) if tr.get("exit_price") is not None else entry
                    if tr.get("realized_pnl") is not None:
                        pnl = float(tr["realized_pnl"])
                    else:
                        pnl = (current_price - entry) * float(tr["quantity"])
                    pnl_percent = (pnl / (entry * float(tr["quantity"])) * 100.0) if entry > 0 else 0.0
                    side = "long" if str(tr["side"]).upper() == "BUY" else "short"
                    out.append(
                        {
                            "id": f"paper-{tr['id']}",
                            "symbol": tr["symbol"],
                            "side": side,
                            "quantity": float(tr["quantity"]),
                            "entry_price": entry,
                            "current_price": current_price,
                            "pnl": pnl,
                            "pnl_percent": pnl_percent,
                            "test_mode": True,
                            "opened_at": tr["opened_at"].isoformat() if hasattr(tr["opened_at"], "isoformat") else str(tr["opened_at"]),
                        }
                    )
                return out
            except Exception as e:
                logger.warning(f"Fallback test_mode_trades due to: {e}")

        db = get_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Atualizar preços simulados primeiro
                    cur.execute("""
                        SELECT id, symbol, entry_price FROM test_mode_trades
                        WHERE user_id = %s AND test_mode = TRUE
                    """, (user_id,))
                    
                    trades_to_update = cur.fetchall()
                    
                    for trade_row in trades_to_update:
                        trade_id, symbol, entry_price = trade_row
                        new_price = TestModeService._simulate_price_change(symbol, float(entry_price))
                        pnl = (new_price - float(entry_price)) * 0.1  # Assumindo quantidade de 0.1
                        pnl_percent = ((new_price - float(entry_price)) / float(entry_price)) * 100
                        
                        cur.execute("""
                            UPDATE test_mode_trades
                            SET current_price = %s,
                                pnl = %s,
                                pnl_percent = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (new_price, pnl, pnl_percent, trade_id))
                    
                    # Buscar trades atualizados
                    cur.execute("""
                        SELECT trade_id, symbol, side, quantity, entry_price, 
                               current_price, pnl, pnl_percent, test_mode, opened_at
                        FROM test_mode_trades
                        WHERE user_id = %s AND test_mode = TRUE
                        ORDER BY opened_at DESC
                        LIMIT %s
                    """, (user_id, limit))
                    
                    columns = [desc[0] for desc in cur.description]
                    trades = []
                    for row in cur.fetchall():
                        trade = dict(zip(columns, row))
                        trades.append({
                            "id": trade["trade_id"],
                            "symbol": trade["symbol"],
                            "side": trade["side"],
                            "quantity": float(trade["quantity"]),
                            "entry_price": float(trade["entry_price"]),
                            "current_price": float(trade["current_price"]),
                            "pnl": float(trade["pnl"]),
                            "pnl_percent": float(trade["pnl_percent"]),
                            "test_mode": trade["test_mode"],
                            "opened_at": trade["opened_at"].isoformat() if isinstance(trade["opened_at"], datetime) else str(trade["opened_at"])
                        })
                    
                    conn.commit()
                    return trades
        except Exception as e:
            logger.error(f"Error getting test mode trades: {str(e)}")
            return []
    
    @staticmethod
    def get_test_mode_logs(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get test mode logs.
        
        Args:
            user_id: User ID
            limit: Result limit
            
        Returns:
            Log list
        """
        db = get_db()
        
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, timestamp, level, message, test_mode
                        FROM test_mode_logs
                        WHERE user_id = %s AND test_mode = TRUE
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """, (user_id, limit))
                    
                    columns = [desc[0] for desc in cur.description]
                    logs = []
                    for row in cur.fetchall():
                        log = dict(zip(columns, row))
                        logs.append({
                            "id": log["id"],
                            "timestamp": log["timestamp"].isoformat() if isinstance(log["timestamp"], datetime) else str(log["timestamp"]),
                            "level": log["level"],
                            "message": log["message"],
                            "test_mode": log["test_mode"]
                        })
                    
                    return logs
        except Exception as e:
            logger.error(f"Error getting test mode logs: {str(e)}")
            return []
    
    @staticmethod
    def get_agent_status(user_id: int) -> Dict[str, Any]:
        """
        Get agent status in test mode.
        
        Args:
            user_id: User ID
            
        Returns:
            Agent status
        """
        return {
            "agent_status": "stopped",
            "test_mode": True,
            "wallet_mode": "mocked",
            "last_update": datetime.utcnow().isoformat(),
            "strategy": "moderate"
        }

    @staticmethod
    def get_phase2_mocked_data(
        user_id: int,
        signals_limit: int = 100,
        trades_limit: int = 200,
        equity_limit: int = 500,
    ) -> Dict[str, Any]:
        """
        Return full Phase 2 payload for mocked wallet:
        portfolio, summary, positions, trades, signals, equity history.
        """
        if not TestModeService.is_mocked_mode_active(user_id):
            raise ValueError("Test mode not connected")

        psvc = get_portfolio_service()
        repo = get_paper_repo()
        paper_service = get_paper_trading_service()
        # Ensure mocked portfolio is available
        paper_service.ensure_portfolio(user_id, initial_balance=10000.0)

        portfolio = psvc.get_portfolio(user_id)
        summary = psvc.get_summary(user_id)
        positions = psvc.list_positions(user_id)
        trades = psvc.list_trades(user_id, limit=trades_limit)
        signals = repo.list_signals(limit=signals_limit, user_id=user_id)
        equity_history = psvc.equity_history(user_id, limit=equity_limit)

        TestModeService.sync_mock_balance_from_paper(user_id)
        return {
            "wallet_mode": "mocked",
            "portfolio": portfolio,
            "summary": summary,
            "positions": positions,
            "trades": trades,
            "signals": signals,
            "equity_history": equity_history,
        }
    
    @staticmethod
    def _create_initial_trades(cur, user_id: int):
        """Create initial demo trades."""
        symbols = ["BTC", "ETH", "AAPL"]
        quantities = [0.1, 2.5, 10]
        entry_prices = [45000.00, 2800.00, 175.50]
        
        for i, symbol in enumerate(symbols):
            entry_price = entry_prices[i]
            current_price = TestModeService._simulate_price_change(symbol, entry_price)
            pnl = (current_price - entry_price) * quantities[i]
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            
            trade_id = f"test-{symbol.lower()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            cur.execute("""
                INSERT INTO test_mode_trades
                (user_id, trade_id, symbol, side, quantity, entry_price, current_price, 
                 pnl, pnl_percent, test_mode, opened_at)
                VALUES (%s, %s, %s, 'long', %s, %s, %s, %s, %s, TRUE, 
                        CURRENT_TIMESTAMP - INTERVAL '%s hours')
            """, (
                user_id, trade_id, symbol, quantities[i], entry_price, current_price,
                pnl, pnl_percent, random.randint(1, 24)
            ))
    
    @staticmethod
    def _create_initial_logs(cur, user_id: int):
        """Create initial demo logs."""
        initial_logs = [
            {"level": "INFO", "message": "Test mode activated - Using demo data"},
            {"level": "INFO", "message": "Guard-rails configured for test symbols: BTC, ETH, AAPL"},
            {"level": "INFO", "message": "Strategy set to: moderate"},
            {"level": "INFO", "message": "Exchange connected: test (Test Mode Active)"}
        ]
        
        for i, log_data in enumerate(initial_logs):
            cur.execute("""
                INSERT INTO test_mode_logs
                (user_id, timestamp, level, message, test_mode)
                VALUES (%s, CURRENT_TIMESTAMP - INTERVAL '%s minutes', %s, %s, TRUE)
            """, (user_id, len(initial_logs) - i, log_data["level"], log_data["message"]))
    
    @staticmethod
    def _simulate_price_change(symbol: str, base_price: float) -> float:
        """
        Simulate a price move based on random variation.
        
        Args:
            symbol: Asset symbol
            base_price: Base price
            
        Returns:
            New simulated price
        """
        variation = random.uniform(-TestModeService.PRICE_VARIATION, TestModeService.PRICE_VARIATION)
        new_price = base_price * (1 + variation)
        return round(new_price, 2)
