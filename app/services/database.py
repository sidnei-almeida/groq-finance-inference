"""
Database Service - Neon PostgreSQL
Thin client architecture: All state stored in database.
"""

import os
import logging
import json
import math
from typing import Dict, List, Optional, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from dotenv import load_dotenv
from app.services.security import get_security_service

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_json_for_db(data: Any) -> Any:
    """
    Clean data for JSONB storage by replacing NaN/Inf with None.
    PostgreSQL JSONB doesn't support NaN or Infinity.
    
    Args:
        data: Data structure (dict, list, or primitive)
    
    Returns:
        Cleaned data structure
    """
    if isinstance(data, dict):
        return {k: clean_json_for_db(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_for_db(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    else:
        return data


class DatabaseService:
    """
    Database service for Neon PostgreSQL.
    Manages connection pooling and provides methods for portfolio analysis data.
    """
    
    def __init__(self):
        """Initialize database connection pool."""
        self.connection_string = os.getenv(
            "DATABASE_URL",
            "postgresql://neondb_owner:npg_J94cznClZpuD@ep-flat-bar-ahm8kof9-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
        )
        
        # Create connection pool
        try:
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.connection_string
            )
            logger.info("Database connection pool created successfully")
            self._initialize_tables()
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {str(e)}")
            raise
    
    def _initialize_tables(self):
        """Initialize/verify database tables exist."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Create portfolio_analyses table if it doesn't exist
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS portfolio_analyses (
                            id SERIAL PRIMARY KEY,
                            symbols TEXT[] NOT NULL,
                            weights NUMERIC[],
                            period VARCHAR(20) NOT NULL,
                            metrics JSONB NOT NULL,
                            ai_analysis TEXT,
                            status VARCHAR(20) DEFAULT 'COMPLETED',
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            completed_at TIMESTAMPTZ
                        );
                    """)
                    
                    # Create analysis_logs table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS analysis_logs (
                            id SERIAL PRIMARY KEY,
                            analysis_id INTEGER REFERENCES portfolio_analyses(id) ON DELETE CASCADE,
                            timestamp TIMESTAMPTZ DEFAULT NOW(),
                            level VARCHAR(10) DEFAULT 'INFO',
                            message TEXT NOT NULL
                        );
                    """)
                    
                    # Create portfolio_history table (for charts)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS portfolio_history (
                            id SERIAL PRIMARY KEY,
                            timestamp TIMESTAMPTZ DEFAULT NOW(),
                            total_balance NUMERIC(20, 2) NOT NULL,
                            available_cash NUMERIC(20, 2) NOT NULL
                        );
                    """)
                    
                    # Add new columns if they don't exist (migration)
                    cur.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='portfolio_history' AND column_name='symbols'
                            ) THEN
                                ALTER TABLE portfolio_history ADD COLUMN symbols TEXT[];
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='portfolio_history' AND column_name='total_value'
                            ) THEN
                                ALTER TABLE portfolio_history ADD COLUMN total_value NUMERIC(20, 2);
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='portfolio_history' AND column_name='annual_return'
                            ) THEN
                                ALTER TABLE portfolio_history ADD COLUMN annual_return NUMERIC(10, 2);
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='portfolio_history' AND column_name='volatility'
                            ) THEN
                                ALTER TABLE portfolio_history ADD COLUMN volatility NUMERIC(10, 2);
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='portfolio_history' AND column_name='sharpe_ratio'
                            ) THEN
                                ALTER TABLE portfolio_history ADD COLUMN sharpe_ratio NUMERIC(10, 2);
                            END IF;
                        END $$;
                    """)
                    
                    # Create app_config table (remote control)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS app_config (
                            key VARCHAR(50) PRIMARY KEY,
                            value VARCHAR(255) NOT NULL,
                            updated_at TIMESTAMPTZ DEFAULT NOW()
                        );
                    """)
                    
                    # Create encrypted_credentials table for sensitive API keys
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS encrypted_credentials (
                            id SERIAL PRIMARY KEY,
                            exchange VARCHAR(50) NOT NULL,
                            credential_type VARCHAR(20) NOT NULL,  -- 'api_key', 'api_secret', 'passphrase'
                            encrypted_value TEXT NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            updated_at TIMESTAMPTZ DEFAULT NOW(),
                            UNIQUE(exchange, credential_type)
                        );
                    """)
                    
                    # Create trades table if it doesn't exist (user's existing table)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS trades (
                            id SERIAL PRIMARY KEY,
                            symbol VARCHAR(20) NOT NULL,
                            side VARCHAR(10) NOT NULL,
                            quantity NUMERIC(20, 8) NOT NULL,
                            entry_price NUMERIC(20, 8) NOT NULL,
                            exit_price NUMERIC(20, 8),
                            pnl NUMERIC(20, 2),
                            status VARCHAR(20) DEFAULT 'OPEN',
                            entry_time TIMESTAMPTZ DEFAULT NOW(),
                            exit_time TIMESTAMPTZ
                        );
                    """)
                    
                    # Create bot_logs table if it doesn't exist (user's existing table)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS bot_logs (
                            id SERIAL PRIMARY KEY,
                            timestamp TIMESTAMPTZ DEFAULT NOW(),
                            level VARCHAR(10) DEFAULT 'INFO',
                            message TEXT NOT NULL
                        );
                    """)
                    
                    # Create users table for authentication
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL,
                            full_name VARCHAR(255) NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMPTZ,
                            is_active BOOLEAN DEFAULT TRUE,
                            email_verified BOOLEAN DEFAULT FALSE,
                            verification_token VARCHAR(255),
                            reset_token VARCHAR(255),
                            reset_token_expires TIMESTAMPTZ
                        );
                    """)
                    
                    # Add profile fields if they don't exist (migration)
                    cur.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='users' AND column_name='avatar_url'
                            ) THEN
                                ALTER TABLE users ADD COLUMN avatar_url TEXT;
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='users' AND column_name='bio'
                            ) THEN
                                ALTER TABLE users ADD COLUMN bio TEXT;
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='users' AND column_name='location'
                            ) THEN
                                ALTER TABLE users ADD COLUMN location VARCHAR(255);
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name='users' AND column_name='website'
                            ) THEN
                                ALTER TABLE users ADD COLUMN website VARCHAR(255);
                            END IF;
                        END $$;
                    """)
                    
                    # Create user_sessions table for token management
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_sessions (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            token VARCHAR(255) UNIQUE NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                            expires_at TIMESTAMPTZ NOT NULL,
                            ip_address VARCHAR(45),
                            user_agent TEXT,
                            is_active BOOLEAN DEFAULT TRUE
                        );
                    """)
                    
                    # Create test_mode_connections table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS test_mode_connections (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                            connected BOOLEAN NOT NULL DEFAULT TRUE,
                            exchange VARCHAR(50) NOT NULL DEFAULT 'test',
                            test_mode BOOLEAN NOT NULL DEFAULT TRUE,
                            balance_total NUMERIC(20, 2) NOT NULL DEFAULT 10000.00,
                            balance_available NUMERIC(20, 2) NOT NULL DEFAULT 8500.00,
                            balance_in_positions NUMERIC(20, 2) NOT NULL DEFAULT 1500.00,
                            currency VARCHAR(10) NOT NULL DEFAULT 'USD',
                            connected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # Create test_mode_trades table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS test_mode_trades (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            trade_id VARCHAR(100) NOT NULL UNIQUE,
                            symbol VARCHAR(10) NOT NULL,
                            side VARCHAR(10) NOT NULL,
                            quantity NUMERIC(20, 8) NOT NULL,
                            entry_price NUMERIC(20, 8) NOT NULL,
                            current_price NUMERIC(20, 8) NOT NULL,
                            pnl NUMERIC(20, 2) DEFAULT 0.0,
                            pnl_percent NUMERIC(10, 4) DEFAULT 0.0,
                            test_mode BOOLEAN NOT NULL DEFAULT TRUE,
                            opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # Create test_mode_logs table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS test_mode_logs (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            level VARCHAR(20) NOT NULL,
                            message TEXT NOT NULL,
                            test_mode BOOLEAN NOT NULL DEFAULT TRUE
                        );
                    """)
                    
                    # Create indexes for test mode tables
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS ix_test_mode_connections_user_id 
                        ON test_mode_connections(user_id);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS ix_test_mode_trades_user_id 
                        ON test_mode_trades(user_id);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS ix_test_mode_trades_trade_id 
                        ON test_mode_trades(trade_id);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS ix_test_mode_logs_user_id 
                        ON test_mode_logs(user_id);
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS ix_test_mode_logs_timestamp 
                        ON test_mode_logs(timestamp DESC);
                    """)
                    
                    # Create trigger function for updating updated_at
                    cur.execute("""
                        CREATE OR REPLACE FUNCTION update_updated_at_column()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            NEW.updated_at = CURRENT_TIMESTAMP;
                            RETURN NEW;
                        END;
                        $$ language 'plpgsql';
                    """)
                    
                    # Create trigger for users table
                    cur.execute("""
                        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
                        CREATE TRIGGER update_users_updated_at
                        BEFORE UPDATE ON users
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                    """)
                    
                    # Create triggers for test mode tables
                    cur.execute("""
                        DROP TRIGGER IF EXISTS update_test_mode_connections_updated_at ON test_mode_connections;
                        CREATE TRIGGER update_test_mode_connections_updated_at
                        BEFORE UPDATE ON test_mode_connections
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                    """)
                    
                    cur.execute("""
                        DROP TRIGGER IF EXISTS update_test_mode_trades_updated_at ON test_mode_trades;
                        CREATE TRIGGER update_test_mode_trades_updated_at
                        BEFORE UPDATE ON test_mode_trades
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                    """)
                    
                    # Seed initial config if not exists
                    cur.execute("""
                        INSERT INTO app_config (key, value) 
                        VALUES 
                            ('analysis_enabled', 'true'),
                            ('default_period', '1y'),
                            ('risk_free_rate', '0.04'),
                            ('max_concurrent_analyses', '5')
                        ON CONFLICT (key) DO NOTHING;
                    """)
                    
                    # Create indexes for performance
                    self._create_indexes(cur)
                    
                    # Sync bot_config with app_config (if bot_config exists)
                    self._sync_config_tables(cur)
                    
                    conn.commit()
                    logger.info("Database tables initialized/verified")
        except Exception as e:
            logger.error(f"Error initializing tables: {str(e)}")
            raise
    
    def _create_indexes(self, cur):
        """Create indexes for better query performance."""
        indexes = [
            # Trades indexes
            ("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)",),
            ("CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time DESC)",),
            ("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",),
            ("CREATE INDEX IF NOT EXISTS idx_trades_status_time ON trades(status, entry_time DESC)",),
            
            # Bot logs indexes
            ("CREATE INDEX IF NOT EXISTS idx_bot_logs_timestamp ON bot_logs(timestamp DESC)",),
            ("CREATE INDEX IF NOT EXISTS idx_bot_logs_level ON bot_logs(level)",),
            ("CREATE INDEX IF NOT EXISTS idx_bot_logs_level_time ON bot_logs(level, timestamp DESC)",),
            
            # Portfolio history indexes
            ("CREATE INDEX IF NOT EXISTS idx_portfolio_history_timestamp ON portfolio_history(timestamp DESC)",),
            ("CREATE INDEX IF NOT EXISTS idx_portfolio_history_symbols ON portfolio_history USING GIN(symbols)",),
            
            # Portfolio analyses indexes
            ("CREATE INDEX IF NOT EXISTS idx_portfolio_analyses_created_at ON portfolio_analyses(created_at DESC)",),
            ("CREATE INDEX IF NOT EXISTS idx_portfolio_analyses_status ON portfolio_analyses(status)",),
            ("CREATE INDEX IF NOT EXISTS idx_portfolio_analyses_symbols ON portfolio_analyses USING GIN(symbols)",),
            
            # Analysis logs indexes
            ("CREATE INDEX IF NOT EXISTS idx_analysis_logs_analysis_id ON analysis_logs(analysis_id)",),
            ("CREATE INDEX IF NOT EXISTS idx_analysis_logs_timestamp ON analysis_logs(timestamp DESC)",),
            
            # Encrypted credentials indexes
            ("CREATE INDEX IF NOT EXISTS idx_encrypted_credentials_exchange ON encrypted_credentials(exchange)",),
            
            # Users indexes
            ("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",),
            ("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",),
            ("CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",),
            
            # User sessions indexes
            ("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)",),
            ("CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token)",),
            ("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at)",),
        ]
        
        for index_sql in indexes:
            try:
                cur.execute(index_sql[0])
            except Exception as e:
                logger.warning(f"Could not create index: {index_sql[0]}. Error: {str(e)}")
    
    def _sync_config_tables(self, cur):
        """Sync bot_config with app_config if bot_config exists."""
        try:
            # Check if bot_config table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'bot_config'
                );
            """)
            
            bot_config_exists = cur.fetchone()[0]
            
            if bot_config_exists:
                # Add updated_at to bot_config if it doesn't exist
                cur.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name='bot_config' AND column_name='updated_at'
                        ) THEN
                            ALTER TABLE bot_config ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
                        END IF;
                    END $$;
                """)
                
                # Copy bot_config values to app_config (if not exists)
                cur.execute("""
                    INSERT INTO app_config (key, value, updated_at)
                    SELECT key, value, COALESCE(updated_at, NOW())
                    FROM bot_config
                    ON CONFLICT (key) DO NOTHING;
                """)
                
                logger.info("Synced bot_config with app_config")
        except Exception as e:
            logger.warning(f"Could not sync config tables: {str(e)}")
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def save_analysis(
        self,
        symbols: List[str],
        metrics: Dict,
        ai_analysis: Optional[str] = None,
        weights: Optional[List[float]] = None,
        period: str = "1y",
        status: str = "COMPLETED"
    ) -> int:
        """
        Save a portfolio analysis to database.
        
        Args:
            symbols: List of asset symbols
            metrics: Dictionary with all portfolio metrics
            ai_analysis: Atlas AI analysis text (optional)
            weights: Portfolio weights (optional)
            period: Analysis period
            status: Analysis status
        
        Returns:
            Analysis ID
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Clean metrics to remove NaN/Inf values (PostgreSQL JSONB doesn't support them)
                    cleaned_metrics = clean_json_for_db(metrics)
                    
                    cur.execute("""
                        INSERT INTO portfolio_analyses 
                        (symbols, weights, period, metrics, ai_analysis, status, completed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        RETURNING id;
                    """, (
                        symbols,
                        weights,
                        period,
                        json.dumps(cleaned_metrics),
                        ai_analysis,
                        status
                    ))
                    analysis_id = cur.fetchone()[0]
                    conn.commit()
                    logger.info(f"Analysis saved with ID: {analysis_id}")
                    return analysis_id
        except Exception as e:
            logger.error(f"Error saving analysis: {str(e)}")
            raise
    
    def add_analysis_log(
        self,
        analysis_id: int,
        message: str,
        level: str = "INFO"
    ):
        """
        Add a log entry for an analysis.
        
        Args:
            analysis_id: Analysis ID
            message: Log message
            level: Log level (INFO, WARNING, ERROR)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO analysis_logs (analysis_id, level, message)
                        VALUES (%s, %s, %s);
                    """, (analysis_id, level, message))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error adding log: {str(e)}")
    
    def get_recent_analyses(
        self,
        limit: int = 10,
        symbols: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Get recent portfolio analyses.
        
        Args:
            limit: Maximum number of analyses to return
            symbols: Filter by symbols (optional)
        
        Returns:
            List of analysis dictionaries
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if symbols:
                        cur.execute("""
                            SELECT * FROM portfolio_analyses
                            WHERE symbols @> %s
                            ORDER BY created_at DESC
                            LIMIT %s;
                        """, (symbols, limit))
                    else:
                        cur.execute("""
                            SELECT * FROM portfolio_analyses
                            ORDER BY created_at DESC
                            LIMIT %s;
                        """, (limit,))
                    
                    analyses = cur.fetchall()
                    # Convert to list of dicts and parse JSONB
                    result = []
                    for row in analyses:
                        analysis = dict(row)
                        analysis['metrics'] = json.loads(analysis['metrics']) if isinstance(analysis['metrics'], str) else analysis['metrics']
                        result.append(analysis)
                    
                    return result
        except Exception as e:
            logger.error(f"Error fetching analyses: {str(e)}")
            return []
    
    def get_analysis_by_id(self, analysis_id: int) -> Optional[Dict]:
        """
        Get a specific analysis by ID.
        
        Args:
            analysis_id: Analysis ID
        
        Returns:
            Analysis dictionary or None
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM portfolio_analyses
                        WHERE id = %s;
                    """, (analysis_id,))
                    
                    row = cur.fetchone()
                    if row:
                        analysis = dict(row)
                        analysis['metrics'] = json.loads(analysis['metrics']) if isinstance(analysis['metrics'], str) else analysis['metrics']
                        return analysis
                    return None
        except Exception as e:
            logger.error(f"Error fetching analysis: {str(e)}")
            return None
    
    def get_analysis_logs(self, analysis_id: int) -> List[Dict]:
        """
        Get logs for a specific analysis.
        
        Args:
            analysis_id: Analysis ID
        
        Returns:
            List of log dictionaries
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM analysis_logs
                        WHERE analysis_id = %s
                        ORDER BY timestamp ASC;
                    """, (analysis_id,))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching logs: {str(e)}")
            return []
    
    def save_portfolio_snapshot(
        self,
        symbols: Optional[List[str]] = None,
        total_value: Optional[float] = None,
        total_balance: Optional[float] = None,
        available_cash: Optional[float] = None,
        annual_return: Optional[float] = None,
        volatility: Optional[float] = None,
        sharpe_ratio: Optional[float] = None
    ):
        """
        Save a portfolio snapshot for history/charts.
        Supports both old schema (total_balance, available_cash) and new schema.
        
        Args:
            symbols: List of asset symbols (optional)
            total_value: Total portfolio value (optional, uses total_balance if not provided)
            total_balance: Total balance (for compatibility with existing schema)
            available_cash: Available cash (for compatibility with existing schema)
            annual_return: Annual return (optional)
            volatility: Volatility (optional)
            sharpe_ratio: Sharpe ratio (optional)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Use total_balance if provided, otherwise use total_value
                    balance = total_balance if total_balance is not None else (total_value if total_value is not None else 0)
                    cash = available_cash if available_cash is not None else balance
                    
                    # Build dynamic query based on available columns
                    columns = ['total_balance', 'available_cash']
                    values = [balance, cash]
                    
                    if symbols is not None:
                        columns.append('symbols')
                        values.append(symbols)
                    
                    if total_value is not None:
                        columns.append('total_value')
                        values.append(total_value)
                    
                    if annual_return is not None:
                        columns.append('annual_return')
                        values.append(annual_return)
                    
                    if volatility is not None:
                        columns.append('volatility')
                        values.append(volatility)
                    
                    if sharpe_ratio is not None:
                        columns.append('sharpe_ratio')
                        values.append(sharpe_ratio)
                    
                    placeholders = ', '.join(['%s'] * len(values))
                    columns_str = ', '.join(columns)
                    
                    cur.execute(f"""
                        INSERT INTO portfolio_history ({columns_str})
                        VALUES ({placeholders});
                    """, values)
                    conn.commit()
        except Exception as e:
            logger.error(f"Error saving portfolio snapshot: {str(e)}")
    
    def get_portfolio_history(
        self,
        symbols: Optional[List[str]] = None,
        days: int = 30
    ) -> List[Dict]:
        """
        Get portfolio history for charts.
        
        Args:
            symbols: Filter by symbols (optional)
            days: Number of days to retrieve
        
        Returns:
            List of portfolio snapshots
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if symbols:
                        cur.execute("""
                            SELECT * FROM portfolio_history
                            WHERE symbols @> %s
                            AND timestamp >= NOW() - INTERVAL '%s days'
                            ORDER BY timestamp ASC;
                        """, (symbols, days))
                    else:
                        cur.execute("""
                            SELECT * FROM portfolio_history
                            WHERE timestamp >= NOW() - INTERVAL '%s days'
                            ORDER BY timestamp ASC;
                        """, (days,))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching portfolio history: {str(e)}")
            return []
    
    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Configuration value or default
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT value FROM app_config
                        WHERE key = %s;
                    """, (key,))
                    
                    row = cur.fetchone()
                    return row[0] if row else default
        except Exception as e:
            logger.error(f"Error fetching config: {str(e)}")
            return default
    
    def set_config(self, key: str, value: str, encrypt: bool = False):
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            encrypt: If True, encrypt the value before storing
        """
        try:
            security = get_security_service()
            
            # Encrypt if requested
            if encrypt:
                value = security.encrypt(value)
                # Log masked version
                logger.info(f"Config updated (encrypted): {key} = {security.mask_sensitive_data(value)}")
            else:
                logger.info(f"Config updated: {key} = {value}")
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO app_config (key, value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (key) 
                        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
                    """, (key, value))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error setting config: {str(e)}")
            raise
    
    def delete_config(self, key: str):
        """
        Delete a configuration value.
        
        Args:
            key: Configuration key to delete
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM app_config
                        WHERE key = %s;
                    """, (key,))
                    conn.commit()
            logger.info(f"Config deleted: {key}")
        except Exception as e:
            logger.error(f"Error deleting config: {str(e)}")
            raise
    
    def save_encrypted_credential(
        self,
        exchange: str,
        credential_type: str,
        plaintext_value: str
    ):
        """
        Save encrypted credential (API key, secret, etc.).
        
        Args:
            exchange: Exchange name
            credential_type: Type of credential ('api_key', 'api_secret', 'passphrase')
            plaintext_value: Plain text value to encrypt and store
        """
        try:
            security = get_security_service()
            encrypted_value = security.encrypt(plaintext_value)
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO encrypted_credentials 
                        (exchange, credential_type, encrypted_value, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (exchange, credential_type)
                        DO UPDATE SET encrypted_value = EXCLUDED.encrypted_value, updated_at = NOW();
                    """, (exchange, credential_type, encrypted_value))
                    conn.commit()
            
            logger.info(f"Encrypted credential saved: {exchange}/{credential_type}")
        except Exception as e:
            logger.error(f"Error saving encrypted credential: {str(e)}")
            raise
    
    def get_encrypted_credential(
        self,
        exchange: str,
        credential_type: str
    ) -> Optional[str]:
        """
        Get and decrypt a credential.
        
        Args:
            exchange: Exchange name
            credential_type: Type of credential ('api_key', 'api_secret', 'passphrase')
        
        Returns:
            Decrypted plain text value or None
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT encrypted_value FROM encrypted_credentials
                        WHERE exchange = %s AND credential_type = %s;
                    """, (exchange, credential_type))
                    
                    row = cur.fetchone()
                    if row:
                        security = get_security_service()
                        return security.decrypt(row[0])
                    return None
        except Exception as e:
            logger.error(f"Error getting encrypted credential: {str(e)}")
            return None
    
    def delete_encrypted_credentials(self, exchange: str):
        """
        Delete all encrypted credentials for an exchange.
        
        Args:
            exchange: Exchange name
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM encrypted_credentials
                        WHERE exchange = %s;
                    """, (exchange,))
                    conn.commit()
            logger.info(f"Deleted encrypted credentials for {exchange}")
        except Exception as e:
            logger.error(f"Error deleting encrypted credentials: {str(e)}")
            raise
    
    def get_all_config(self) -> Dict[str, str]:
        """
        Get all configuration values.
        
        Returns:
            Dictionary of all config key-value pairs
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT key, value FROM app_config;")
                    return {row[0]: row[1] for row in cur.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching all config: {str(e)}")
            return {}
    
    def add_bot_log(self, message: str, level: str = "INFO"):
        """
        Add a log entry to bot_logs table.
        
        Args:
            message: Log message
            level: Log level (INFO, WARNING, ERROR, TRADE)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO bot_logs (level, message)
                        VALUES (%s, %s);
                    """, (level.upper(), message))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error adding bot log: {str(e)}")
    
    def create_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float
    ) -> int:
        """
        Create a new trade.
        
        Args:
            symbol: Trading symbol
            side: 'BUY' or 'SELL'
            quantity: Trade quantity
            entry_price: Entry price
        
        Returns:
            Trade ID
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO trades (symbol, side, quantity, entry_price, status)
                        VALUES (%s, %s, %s, %s, 'OPEN')
                        RETURNING id;
                    """, (symbol, side.upper(), quantity, entry_price))
                    trade_id = cur.fetchone()[0]
                    conn.commit()
                    logger.info(f"Trade created with ID: {trade_id}")
                    return trade_id
        except Exception as e:
            logger.error(f"Error creating trade: {str(e)}")
            raise
    
    def close_trade(self, trade_id: int, exit_price: float, pnl: float):
        """
        Close a trade.
        
        Args:
            trade_id: Trade ID
            exit_price: Exit price
            pnl: Profit/Loss
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE trades
                        SET exit_price = %s,
                            pnl = %s,
                            status = 'CLOSED',
                            exit_time = NOW()
                        WHERE id = %s;
                    """, (exit_price, pnl, trade_id))
                    conn.commit()
                    logger.info(f"Trade {trade_id} closed")
        except Exception as e:
            logger.error(f"Error closing trade: {str(e)}")
            raise
    
    def get_trades(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get trades from database.
        
        Args:
            status: Filter by status (OPEN, CLOSED, FAILED)
            limit: Maximum number of trades to return
        
        Returns:
            List of trade dictionaries
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if status:
                        cur.execute("""
                            SELECT * FROM trades
                            WHERE status = %s
                            ORDER BY entry_time DESC
                            LIMIT %s;
                        """, (status.upper(), limit))
                    else:
                        cur.execute("""
                            SELECT * FROM trades
                            ORDER BY entry_time DESC
                            LIMIT %s;
                        """, (limit,))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching trades: {str(e)}")
            return []
    
    def get_bot_logs(self, level: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get bot logs from database.
        
        Args:
            level: Filter by level (INFO, WARNING, ERROR, TRADE)
            limit: Maximum number of logs to return
        
        Returns:
            List of log dictionaries
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if level:
                        cur.execute("""
                            SELECT * FROM bot_logs
                            WHERE level = %s
                            ORDER BY timestamp DESC
                            LIMIT %s;
                        """, (level.upper(), limit))
                    else:
                        cur.execute("""
                            SELECT * FROM bot_logs
                            ORDER BY timestamp DESC
                            LIMIT %s;
                        """, (limit,))
                    
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching bot logs: {str(e)}")
            return []
    
    # ============================================================================
    # AUTHENTICATION METHODS
    # ============================================================================
    
    def create_user(self, email: str, password_hash: str, full_name: str) -> Dict:
        """
        Create a new user.
        
        Args:
            email: User email (must be unique)
            password_hash: Hashed password
            full_name: User's full name
        
        Returns:
            User dictionary (without password_hash)
        
        Raises:
            Exception: If email already exists
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        INSERT INTO users (email, password_hash, full_name)
                        VALUES (%s, %s, %s)
                        RETURNING id, email, full_name, created_at, updated_at, last_login, is_active;
                    """, (email.lower(), password_hash, full_name))
                    
                    user = dict(cur.fetchone())
                    conn.commit()
                    logger.info(f"User created: {email}")
                    return user
        except psycopg2.IntegrityError as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise Exception("Email already exists")
            raise
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """
        Get user by email.
        
        Args:
            email: User email
        
        Returns:
            User dictionary (with password_hash) or None
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id, email, password_hash, full_name, created_at, updated_at, last_login, is_active
                        FROM users
                        WHERE email = %s;
                    """, (email.lower(),))
                    
                    row = cur.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            logger.error(f"Error fetching user: {str(e)}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
        
        Returns:
            User dictionary (without password_hash) or None
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id, email, full_name, avatar_url, bio, location, website,
                               created_at, updated_at, last_login, is_active
                        FROM users
                        WHERE id = %s AND is_active = TRUE;
                    """, (user_id,))
                    
                    row = cur.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            logger.error(f"Error fetching user: {str(e)}")
            return None
    
    def update_user_last_login(self, user_id: int):
        """
        Update user's last login timestamp.
        
        Args:
            user_id: User ID
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE users
                        SET last_login = NOW()
                        WHERE id = %s;
                    """, (user_id,))
                    conn.commit()
        except Exception as e:
            logger.warning(f"Error updating last login: {str(e)}")
    
    def create_session(self, user_id: int, token: str, expires_at: datetime, 
                      ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> int:
        """
        Create a user session.
        
        Args:
            user_id: User ID
            token: JWT token string
            expires_at: Token expiration datetime
            ip_address: Optional IP address
            user_agent: Optional user agent string
        
        Returns:
            Session ID
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_sessions (user_id, token, expires_at, ip_address, user_agent)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id;
                    """, (user_id, token, expires_at, ip_address, user_agent))
                    session_id = cur.fetchone()[0]
                    conn.commit()
                    return session_id
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            raise
    
    def deactivate_user_sessions(self, user_id: int):
        """
        Deactivate all sessions for a user.
        
        Args:
            user_id: User ID
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE user_sessions
                        SET is_active = FALSE
                        WHERE user_id = %s AND is_active = TRUE;
                    """, (user_id,))
                    conn.commit()
        except Exception as e:
            logger.warning(f"Error deactivating sessions: {str(e)}")
    
    def update_user(self, user_id: int, update_data: Dict[str, Any]) -> Optional[Dict]:
        """
        Update user profile information.
        
        Args:
            user_id: User ID
            update_data: Dictionary with fields to update (full_name, email, bio, location, website, avatar_url, password_hash)
        
        Returns:
            Updated user dictionary (without password_hash) or None
        
        Raises:
            Exception: If email already exists (when updating email)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check if email is being changed and if it's unique
                    if "email" in update_data:
                        email = update_data["email"].lower()
                        cur.execute("""
                            SELECT id FROM users
                            WHERE email = %s AND id != %s;
                        """, (email, user_id))
                        if cur.fetchone():
                            raise Exception("Email already exists")
                    
                    # Build dynamic UPDATE query
                    allowed_fields = ["full_name", "email", "bio", "location", "website", "avatar_url", "password_hash"]
                    update_fields = []
                    update_values = []
                    
                    for field in allowed_fields:
                        if field in update_data:
                            update_fields.append(f"{field} = %s")
                            update_values.append(update_data[field])
                    
                    if not update_fields:
                        # No fields to update, just return current user
                        return self.get_user_by_id(user_id)
                    
                    # Add updated_at (will be set by trigger, but explicit is fine)
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    
                    update_values.append(user_id)
                    
                    query = f"""
                        UPDATE users
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                        RETURNING id, email, full_name, avatar_url, bio, location, website, 
                                  created_at, updated_at, last_login, is_active;
                    """
                    
                    cur.execute(query, update_values)
                    user = dict(cur.fetchone())
                    conn.commit()
                    logger.info(f"User {user_id} updated")
                    return user
        except psycopg2.IntegrityError as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise Exception("Email already exists")
            raise
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            raise
    
    def update_user_password(self, user_id: int, new_password_hash: str):
        """
        Update user password.
        
        Args:
            user_id: User ID
            new_password_hash: New hashed password
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE users
                        SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (new_password_hash, user_id))
                    conn.commit()
                    logger.info(f"Password updated for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating password: {str(e)}")
            raise
    
    def close(self):
        """Close all database connections."""
        if hasattr(self, 'pool'):
            self.pool.closeall()
            logger.info("Database connection pool closed")


# Global database instance
_db_instance: Optional[DatabaseService] = None


def get_db() -> DatabaseService:
    """Get global database instance (singleton pattern)."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseService()
    return _db_instance
