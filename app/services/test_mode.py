"""
Test Mode Service - Gerenciamento de modo teste
"""

import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from app.services.database import get_db

logger = logging.getLogger(__name__)


class TestModeService:
    """Serviço para gerenciar modo teste"""
    
    # Preços base para simulação
    BASE_PRICES = {
        "BTC": 45000.00,
        "ETH": 2800.00,
        "AAPL": 175.50
    }
    
    # Variação percentual máxima para simular movimento de preços
    PRICE_VARIATION = 0.02  # 2%
    
    @staticmethod
    def connect_test_mode(user_id: int) -> Dict[str, Any]:
        """
        Conecta usuário ao modo teste
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Status da exchange em modo teste
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
                        # Criar nova conexão
                        cur.execute("""
                            INSERT INTO test_mode_connections
                            (user_id, connected, exchange, test_mode, balance_total, 
                             balance_available, balance_in_positions, currency, connected_at)
                            VALUES (%s, TRUE, 'test', TRUE, 10000.00, 8500.00, 1500.00, 'USD', CURRENT_TIMESTAMP)
                        """, (user_id,))
                        
                        # Criar trades iniciais
                        TestModeService._create_initial_trades(cur, user_id)
                        
                        # Criar logs iniciais
                        TestModeService._create_initial_logs(cur, user_id)
                    
                    conn.commit()
                    
                    # Retornar status
                    return TestModeService.get_test_mode_status(user_id)
        except Exception as e:
            logger.error(f"Error connecting test mode: {str(e)}")
            raise
    
    @staticmethod
    def disconnect_test_mode(user_id: int) -> Dict[str, Any]:
        """
        Desconecta usuário do modo teste
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Confirmação de desconexão
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
        Obtém status do modo teste do usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Status da exchange ou None se não conectado
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
                    
                    return {
                        "connected": connection["connected"],
                        "exchange": connection["exchange"],
                        "test_mode": connection["test_mode"],
                        "balance": {
                            "total": float(connection["balance_total"]),
                            "available": float(connection["balance_available"]),
                            "in_positions": float(connection["balance_in_positions"]),
                            "currency": connection["currency"]
                        },
                        "connected_at": connection["connected_at"].isoformat() if isinstance(connection["connected_at"], datetime) else str(connection["connected_at"]),
                        "user_id": connection["user_id"]
                    }
        except Exception as e:
            logger.error(f"Error getting test mode status: {str(e)}")
            return None
    
    @staticmethod
    def get_test_mode_trades(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtém trades abertos em modo teste
        
        Args:
            user_id: ID do usuário
            limit: Limite de resultados
            
        Returns:
            Lista de trades
        """
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
        Obtém logs em modo teste
        
        Args:
            user_id: ID do usuário
            limit: Limite de resultados
            
        Returns:
            Lista de logs
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
        Obtém status do agente em modo teste
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Status do agente
        """
        return {
            "agent_status": "stopped",
            "test_mode": True,
            "last_update": datetime.utcnow().isoformat(),
            "strategy": "moderate"
        }
    
    @staticmethod
    def _create_initial_trades(cur, user_id: int):
        """Cria trades iniciais para demonstração"""
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
        """Cria logs iniciais para demonstração"""
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
        Simula mudança de preço baseada em variação aleatória
        
        Args:
            symbol: Símbolo do ativo
            base_price: Preço base
            
        Returns:
            Novo preço simulado
        """
        variation = random.uniform(-TestModeService.PRICE_VARIATION, TestModeService.PRICE_VARIATION)
        new_price = base_price * (1 + variation)
        return round(new_price, 2)
