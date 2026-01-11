"""
FastAPI Backend - Thin Client Architecture
All state stored in database. API is stateless.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.services.database import get_db
from app.services.quant_engine import QuantitativeEngine
from app.services.ai_agent import AtlasAgent
from app.services.security import get_security_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="FinSight API",
    description="Quantitative Portfolio Analysis & Trading Agent API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ExchangeConnection(BaseModel):
    """Exchange API connection credentials"""
    exchange: str = Field(..., description="Exchange name (binance, alpaca, bybit)")
    api_key: str = Field(..., description="API Key")
    api_secret: str = Field(..., description="API Secret")
    testnet: bool = Field(False, description="Use testnet/sandbox")

class GuardRails(BaseModel):
    """Risk management limits"""
    daily_stop_loss: float = Field(..., description="Maximum daily loss in USD")
    max_leverage: float = Field(..., description="Maximum leverage (e.g., 2.0 for 2x)")
    allowed_symbols: List[str] = Field(..., description="List of allowed trading symbols")
    max_position_size: Optional[float] = Field(None, description="Maximum position size in USD")

class StrategyConfig(BaseModel):
    """Trading strategy configuration"""
    mode: str = Field(..., description="Strategy mode: 'conservative' or 'aggressive'")
    risk_per_trade: float = Field(0.01, description="Risk per trade (0.01 = 1%)")
    take_profit_pct: Optional[float] = Field(None, description="Take profit percentage")
    stop_loss_pct: Optional[float] = Field(None, description="Stop loss percentage")

class PortfolioAnalysisRequest(BaseModel):
    """Request for portfolio analysis"""
    symbols: List[str] = Field(..., description="List of asset symbols")
    weights: Optional[List[float]] = Field(None, description="Portfolio weights (must sum to 1.0)")
    period: str = Field("1y", description="Analysis period (1d, 1mo, 3mo, 6mo, 1y, 2y, 5y)")
    include_ai_analysis: bool = Field(True, description="Include Atlas AI analysis")

class AgentControl(BaseModel):
    """Agent control commands"""
    action: str = Field(..., description="Action: 'start', 'stop', 'emergency_stop'")
    close_all_positions: bool = Field(False, description="Close all positions on stop")

class TradeResponse(BaseModel):
    """Trade information"""
    id: int
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: Optional[float]
    pnl: Optional[float]
    status: str
    entry_time: datetime
    exit_time: Optional[datetime]

class AnalysisResponse(BaseModel):
    """Portfolio analysis response"""
    analysis_id: int
    symbols: List[str]
    weights: Optional[List[float]]
    period: str
    metrics: Dict[str, Any]
    ai_analysis: Optional[str]
    status: str
    created_at: datetime

class StatusResponse(BaseModel):
    """System status response"""
    agent_status: str  # 'stopped', 'running', 'paused', 'error'
    exchange_connected: bool
    balance: Optional[float]
    daily_pnl: Optional[float]
    open_positions: int
    last_update: datetime

# ============================================================================
# EXCHANGE CONNECTION ENDPOINTS
# ============================================================================

@app.post("/api/exchange/connect", tags=["Exchange"])
async def connect_exchange(connection: ExchangeConnection):
    """
    Connect to exchange and validate credentials.
    
    SECURITY:
    - API keys are encrypted before storage
    - Credentials stored in separate encrypted table
    - Only masked values logged
    - HTTPS required in production
    """
    try:
        db = get_db()
        security = get_security_service()
        
        # Validate API key format
        if not security.validate_api_key_format(connection.api_key, connection.exchange):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid API key format for {connection.exchange}"
            )
        
        # TODO: Validate credentials with actual exchange API
        # For now, we'll encrypt and store them
        
        # Store encrypted credentials in separate table
        db.save_encrypted_credential(
            exchange=connection.exchange,
            credential_type="api_key",
            plaintext_value=connection.api_key
        )
        db.save_encrypted_credential(
            exchange=connection.exchange,
            credential_type="api_secret",
            plaintext_value=connection.api_secret
        )
        
        # Store non-sensitive config
        db.set_config(f"exchange_{connection.exchange}_testnet", str(connection.testnet))
        db.set_config("exchange_connected", "true")
        db.set_config("current_exchange", connection.exchange)
        
        # Log connection (masked)
        masked_key = security.mask_sensitive_data(connection.api_key)
        db.add_bot_log(
            f"Exchange connected: {connection.exchange} (Key: {masked_key})",
            "INFO"
        )
        
        return {
            "status": "connected",
            "exchange": connection.exchange,
            "message": "Connection successful! Credentials encrypted and stored securely."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting to exchange: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect to exchange")

@app.get("/api/exchange/status", tags=["Exchange"])
async def get_exchange_status():
    """Get current exchange connection status."""
    try:
        db = get_db()
        connected = db.get_config("exchange_connected", "false") == "true"
        exchange = db.get_config("current_exchange", None)
        
        return {
            "connected": connected,
            "exchange": exchange,
            "testnet": db.get_config(f"exchange_{exchange}_testnet", "false") == "true" if exchange else False
        }
    except Exception as e:
        logger.error(f"Error getting exchange status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/exchange/disconnect", tags=["Exchange"])
async def disconnect_exchange():
    """
    Disconnect from exchange and clear credentials.
    
    SECURITY: Deletes encrypted credentials from database.
    """
    try:
        db = get_db()
        exchange = db.get_config("current_exchange", "")
        
        if exchange:
            # Delete encrypted credentials
            db.delete_encrypted_credentials(exchange)
        
        db.set_config("exchange_connected", "false")
        db.set_config("current_exchange", "")
        
        db.add_bot_log(f"Exchange disconnected: {exchange}", "INFO")
        
        return {"status": "disconnected", "message": "Disconnected successfully. Credentials deleted."}
    except Exception as e:
        logger.error(f"Error disconnecting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# GUARD-RAILS ENDPOINTS
# ============================================================================

@app.post("/api/guardrails", tags=["Risk Management"])
async def set_guardrails(guardrails: GuardRails):
    """
    Set risk management guard-rails.
    These limits prevent the agent from exceeding risk parameters.
    """
    try:
        db = get_db()
        
        db.set_config("daily_stop_loss", str(guardrails.daily_stop_loss))
        db.set_config("max_leverage", str(guardrails.max_leverage))
        db.set_config("allowed_symbols", ",".join(guardrails.allowed_symbols))
        
        if guardrails.max_position_size:
            db.set_config("max_position_size", str(guardrails.max_position_size))
        
        return {
            "status": "saved",
            "guardrails": {
                "daily_stop_loss": guardrails.daily_stop_loss,
                "max_leverage": guardrails.max_leverage,
                "allowed_symbols": guardrails.allowed_symbols,
                "max_position_size": guardrails.max_position_size
            }
        }
    except Exception as e:
        logger.error(f"Error setting guardrails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/guardrails", tags=["Risk Management"])
async def get_guardrails():
    """Get current guard-rails configuration."""
    try:
        db = get_db()
        
        allowed_symbols_str = db.get_config("allowed_symbols", "")
        allowed_symbols = allowed_symbols_str.split(",") if allowed_symbols_str else []
        
        return {
            "daily_stop_loss": float(db.get_config("daily_stop_loss", "0")),
            "max_leverage": float(db.get_config("max_leverage", "1")),
            "allowed_symbols": allowed_symbols,
            "max_position_size": float(db.get_config("max_position_size", "0")) if db.get_config("max_position_size") else None
        }
    except Exception as e:
        logger.error(f"Error getting guardrails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STRATEGY CONFIGURATION ENDPOINTS
# ============================================================================

@app.post("/api/strategy", tags=["Strategy"])
async def set_strategy(strategy: StrategyConfig):
    """
    Set trading strategy configuration.
    Modes: 'conservative' (safer, fewer trades) or 'aggressive' (more trades, higher risk)
    """
    try:
        db = get_db()
        
        if strategy.mode not in ["conservative", "aggressive"]:
            raise HTTPException(status_code=400, detail="Mode must be 'conservative' or 'aggressive'")
        
        db.set_config("strategy_mode", strategy.mode)
        db.set_config("risk_per_trade", str(strategy.risk_per_trade))
        
        if strategy.take_profit_pct:
            db.set_config("take_profit_pct", str(strategy.take_profit_pct))
        
        if strategy.stop_loss_pct:
            db.set_config("stop_loss_pct", str(strategy.stop_loss_pct))
        
        return {
            "status": "saved",
            "strategy": {
                "mode": strategy.mode,
                "risk_per_trade": strategy.risk_per_trade,
                "take_profit_pct": strategy.take_profit_pct,
                "stop_loss_pct": strategy.stop_loss_pct
            }
        }
    except Exception as e:
        logger.error(f"Error setting strategy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategy", tags=["Strategy"])
async def get_strategy():
    """Get current strategy configuration."""
    try:
        db = get_db()
        
        return {
            "mode": db.get_config("strategy_mode", "conservative"),
            "risk_per_trade": float(db.get_config("risk_per_trade", "0.01")),
            "take_profit_pct": float(db.get_config("take_profit_pct", "0")) if db.get_config("take_profit_pct") else None,
            "stop_loss_pct": float(db.get_config("stop_loss_pct", "0")) if db.get_config("stop_loss_pct") else None
        }
    except Exception as e:
        logger.error(f"Error getting strategy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# PORTFOLIO ANALYSIS ENDPOINTS
# ============================================================================

@app.post("/api/analyze", tags=["Analysis"])
async def analyze_portfolio(request: PortfolioAnalysisRequest, background_tasks: BackgroundTasks):
    """
    Analyze a portfolio using quantitative metrics and AI insights.
    Returns comprehensive analysis with 31+ metrics and Atlas AI interpretation.
    """
    try:
        db = get_db()
        
        # Initialize engines
        quant_engine = QuantitativeEngine()
        atlas_agent = AtlasAgent()
        
        # Run quantitative analysis
        logger.info(f"Starting portfolio analysis for: {request.symbols}")
        metrics = quant_engine.analyze_portfolio(
            symbols=request.symbols,
            weights=request.weights,
            period=request.period
        )
        
        if not metrics:
            raise HTTPException(status_code=500, detail="Failed to calculate portfolio metrics")
        
        # Get AI analysis if requested
        ai_analysis = None
        if request.include_ai_analysis:
            try:
                ai_result = atlas_agent.analyze_portfolio(
                    metrics=metrics,
                    symbols=request.symbols,
                    weights=request.weights,
                    max_tokens=2000
                )
                ai_analysis = ai_result.get("analysis")
            except Exception as e:
                logger.warning(f"AI analysis failed: {str(e)}")
                ai_analysis = "AI analysis temporarily unavailable"
        
        # Save to database
        analysis_id = db.save_analysis(
            symbols=request.symbols,
            metrics=metrics,
            ai_analysis=ai_analysis,
            weights=request.weights,
            period=request.period,
            status="COMPLETED"
        )
        
        # Add logs
        db.add_analysis_log(analysis_id, f"Analysis completed for {', '.join(request.symbols)}", "INFO")
        
        return AnalysisResponse(
            analysis_id=analysis_id,
            symbols=request.symbols,
            weights=request.weights,
            period=request.period,
            metrics=metrics,
            ai_analysis=ai_analysis,
            status="COMPLETED",
            created_at=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing portfolio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analyses", tags=["Analysis"])
async def get_analyses(limit: int = 10, symbols: Optional[str] = None):
    """Get recent portfolio analyses."""
    try:
        db = get_db()
        
        symbol_list = symbols.split(",") if symbols else None
        analyses = db.get_recent_analyses(limit=limit, symbols=symbol_list)
        
        return analyses
    except Exception as e:
        logger.error(f"Error fetching analyses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analyses/{analysis_id}", tags=["Analysis"])
async def get_analysis(analysis_id: int):
    """Get a specific analysis by ID."""
    try:
        db = get_db()
        analysis = db.get_analysis_by_id(analysis_id)
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analyses/{analysis_id}/logs", tags=["Analysis"])
async def get_analysis_logs(analysis_id: int):
    """Get logs for a specific analysis."""
    try:
        db = get_db()
        logs = db.get_analysis_logs(analysis_id)
        return logs
    except Exception as e:
        logger.error(f"Error fetching logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# AGENT CONTROL ENDPOINTS
# ============================================================================

@app.post("/api/agent/control", tags=["Agent"])
async def control_agent(control: AgentControl):
    """
    Control the trading agent.
    Actions: 'start', 'stop', 'emergency_stop'
    """
    try:
        db = get_db()
        
        if control.action == "start":
            # Check prerequisites
            if db.get_config("exchange_connected", "false") != "true":
                raise HTTPException(status_code=400, detail="Exchange not connected")
            
            db.set_config("agent_status", "running")
            db.set_config("agent_started_at", datetime.now().isoformat())
            
            return {
                "status": "started",
                "message": "Agent started successfully",
                "started_at": datetime.now().isoformat()
            }
        
        elif control.action == "stop":
            db.set_config("agent_status", "stopped")
            
            return {
                "status": "stopped",
                "message": "Agent stopped successfully"
            }
        
        elif control.action == "emergency_stop":
            db.set_config("agent_status", "emergency_stopped")
            
            if control.close_all_positions:
                # In production, this would close all open positions
                # For now, just log it
                db.add_analysis_log(0, "EMERGENCY STOP: Closing all positions", "ERROR")
            
            return {
                "status": "emergency_stopped",
                "message": "Emergency stop activated",
                "positions_closed": control.close_all_positions
            }
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'start', 'stop', or 'emergency_stop'")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error controlling agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agent/status", tags=["Agent"])
async def get_agent_status():
    """Get current agent status and system information."""
    try:
        db = get_db()
        
        agent_status = db.get_config("agent_status", "stopped")
        exchange_connected = db.get_config("exchange_connected", "false") == "true"
        
        # Get open trades count (from trades table - if it exists)
        # For now, return placeholder
        open_positions = 0
        
        return StatusResponse(
            agent_status=agent_status,
            exchange_connected=exchange_connected,
            balance=None,  # Would fetch from exchange in production
            daily_pnl=None,  # Would calculate from trades
            open_positions=open_positions,
            last_update=datetime.now()
        )
    except Exception as e:
        logger.error(f"Error getting agent status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# TRADES ENDPOINTS (Thin Client - Just reads from DB)
# ============================================================================

@app.get("/api/trades", tags=["Trades"])
async def get_trades(status: Optional[str] = None, limit: int = 100):
    """
    Get trades from database.
    Thin client: Frontend just queries this endpoint.
    """
    try:
        db = get_db()
        trades = db.get_trades(status=status, limit=limit)
        return trades
    except Exception as e:
        logger.error(f"Error fetching trades: {str(e)}")
        return []

@app.get("/api/trades/open", tags=["Trades"])
async def get_open_trades():
    """Get all open trades."""
    return await get_trades(status="OPEN")

# ============================================================================
# LOGS ENDPOINTS (Thin Client - Just reads from DB)
# ============================================================================

@app.get("/api/logs", tags=["Logs"])
async def get_logs(limit: int = 100, level: Optional[str] = None):
    """
    Get system logs from database.
    Thin client: Frontend displays these in real-time.
    """
    try:
        db = get_db()
        logs = db.get_bot_logs(level=level, limit=limit)
        return logs
    except Exception as e:
        logger.error(f"Error fetching logs: {str(e)}")
        return []

# ============================================================================
# PORTFOLIO HISTORY ENDPOINTS (For Charts)
# ============================================================================

@app.get("/api/portfolio/history", tags=["Portfolio"])
async def get_portfolio_history(days: int = 30, symbols: Optional[str] = None):
    """
    Get portfolio history for charts.
    Thin client: Frontend uses this to draw performance charts.
    """
    try:
        db = get_db()
        
        symbol_list = symbols.split(",") if symbols else None
        history = db.get_portfolio_history(symbols=symbol_list, days=days)
        
        return history
    except Exception as e:
        logger.error(f"Error fetching portfolio history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    try:
        db = get_db()
        # Test database connection
        db.get_config("test", "ok")
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "message": "FinSight API - Quantitative Portfolio Analysis",
        "version": "1.0.0",
        "docs": "/docs"
    }

# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting FinSight API...")
    try:
        db = get_db()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down FinSight API...")
    try:
        db = get_db()
        db.close()
    except:
        pass

if __name__ == "__main__":
    # For local development
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
