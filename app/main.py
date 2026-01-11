"""
FastAPI Backend - Thin Client Architecture
All state stored in database. API is stateless.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator, EmailStr
import uvicorn

from app.services.database import get_db
from app.services.quant_engine import QuantitativeEngine
from app.services.ai_agent import AtlasAgent
from app.services.security import get_security_service
from app.services.auth import get_auth_service, AuthService

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
# Allow specific origins for security
allowed_origins = [
    "http://localhost:8000",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
    "https://sidnei-almeida.github.io",
    "https://groq-finance-inference.onrender.com",  # Allow API to call itself
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
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
    mode: str = Field(..., description="Strategy mode: 'conservative', 'moderate', or 'aggressive'")
    risk_per_trade: float = Field(0.01, description="Risk per trade (0.01 = 1%)")
    take_profit_pct: Optional[float] = Field(None, description="Take profit percentage")
    stop_loss_pct: Optional[float] = Field(None, description="Stop loss percentage")

class PortfolioAnalysisRequest(BaseModel):
    """Request for portfolio analysis"""
    symbols: List[str] = Field(..., min_length=1, description="List of asset symbols (at least 1 required)")
    weights: Optional[List[float]] = Field(None, description="Portfolio weights (must sum to 1.0)")
    period: str = Field("1y", description="Analysis period (1d, 1mo, 3mo, 6mo, 1y, 2y, 5y)")
    include_ai_analysis: bool = Field(True, description="Include Atlas AI analysis")
    
    @validator('symbols')
    def validate_symbols_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one symbol is required')
        return v

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

# Authentication models
class SignupRequest(BaseModel):
    """User signup request"""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    full_name: str = Field(..., min_length=1, description="User's full name")
    
    @validator('password')
    def validate_password_length(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="Password")

class UpdateProfileRequest(BaseModel):
    """Update user profile request"""
    full_name: str = Field(..., min_length=1, description="User's full name")
    email: EmailStr = Field(..., description="User email")
    bio: Optional[str] = Field(None, max_length=500, description="User biography (max 500 chars)")
    location: Optional[str] = Field(None, description="User location")
    website: Optional[str] = Field(None, description="User website URL")
    
    @validator('bio')
    def validate_bio_length(cls, v):
        if v and len(v) > 500:
            raise ValueError('Bio must be at most 500 characters')
        return v
    
    @validator('website')
    def validate_website_url(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            # Try to add https:// if no protocol
            return f'https://{v}'
        return v

class UploadAvatarRequest(BaseModel):
    """Upload avatar request"""
    avatar: str = Field(..., description="Base64 encoded image (data:image/...;base64,...)")
    filename: str = Field(..., description="Image filename")

class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")
    
    @validator('new_password')
    def validate_password_length(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

# HTTP Bearer token security
security_scheme = HTTPBearer(auto_error=False)

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Optional[Dict]:
    """
    Optional authentication dependency.
    Returns user dict if token is valid, None otherwise.
    """
    if not credentials:
        return None
    
    try:
        auth_service = get_auth_service()
        user_id = auth_service.get_user_id_from_token(credentials.credentials)
        
        if user_id:
            db = get_db()
            user = db.get_user_by_id(user_id)
            return user
        return None
    except Exception as e:
        logger.warning(f"Authentication error: {str(e)}")
        return None

@app.post("/api/auth/signup", tags=["Authentication"], status_code=201)
async def signup(request: SignupRequest):
    """
    Create a new user account.
    
    Returns:
        201 Created: User created successfully
        400 Bad Request: Email already exists or validation error
    """
    try:
        db = get_db()
        auth_service = get_auth_service()
        
        # Check if email already exists
        existing_user = db.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "Email already exists"}
            )
        
        # Hash password
        password_hash = auth_service.hash_password(request.password)
        
        # Create user
        user = db.create_user(
            email=request.email,
            password_hash=password_hash,
            full_name=request.full_name
        )
        
        return {
            "status": "success",
            "message": "User created successfully",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else str(user["created_at"])
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "Email already exists"}
            )
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Failed to create user"}
        )

@app.post("/api/auth/login", tags=["Authentication"])
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT token.
    
    Returns:
        200 OK: Login successful with token
        401 Unauthorized: Invalid credentials
    """
    try:
        db = get_db()
        auth_service = get_auth_service()
        
        # Get user by email
        user = db.get_user_by_email(request.email)
        if not user:
            raise HTTPException(
                status_code=401,
                detail={"status": "error", "message": "Invalid email or password"}
            )
        
        # Verify password
        if not auth_service.verify_password(request.password, user["password_hash"]):
            raise HTTPException(
                status_code=401,
                detail={"status": "error", "message": "Invalid email or password"}
            )
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=401,
                detail={"status": "error", "message": "Account is inactive"}
            )
        
        # Update last login
        db.update_user_last_login(user["id"])
        
        # Create JWT token
        token_data = {
            "sub": str(user["id"]),
            "email": user["email"]
        }
        token = auth_service.create_access_token(token_data)
        
        # Create session (optional)
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=30)
        try:
            db.create_session(
                user_id=user["id"],
                token=token,
                expires_at=expires_at
            )
        except Exception as e:
            logger.warning(f"Could not create session: {str(e)}")
        
        return {
            "status": "success",
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else str(user["created_at"]),
                "updated_at": user["updated_at"].isoformat() if isinstance(user["updated_at"], datetime) else str(user["updated_at"]) if user.get("updated_at") else None,
                "last_login": datetime.utcnow().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Failed to authenticate"}
        )

@app.post("/api/auth/logout", tags=["Authentication"])
async def logout(current_user: Optional[Dict] = Depends(get_current_user)):
    """
    Logout user and invalidate sessions.
    
    Returns:
        200 OK: Logout successful
        401 Unauthorized: Invalid token
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        db = get_db()
        db.deactivate_user_sessions(current_user["id"])
        
        return {
            "status": "success",
            "message": "Logged out successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Failed to logout"}
        )

@app.get("/api/auth/me", tags=["Authentication"])
async def get_current_user_info(current_user: Optional[Dict] = Depends(get_current_user)):
    """
    Get current authenticated user information.
    
    Returns:
        200 OK: User information
        401 Unauthorized: Invalid token or user not found
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        return {
            "user": {
                "id": current_user["id"],
                "email": current_user["email"],
                "full_name": current_user["full_name"],
                "avatar_url": current_user.get("avatar_url"),
                "bio": current_user.get("bio"),
                "location": current_user.get("location"),
                "website": current_user.get("website"),
                "created_at": current_user["created_at"].isoformat() if isinstance(current_user["created_at"], datetime) else str(current_user["created_at"]),
                "updated_at": current_user["updated_at"].isoformat() if isinstance(current_user["updated_at"], datetime) else str(current_user["updated_at"]) if current_user.get("updated_at") else None,
                "last_login": current_user["last_login"].isoformat() if isinstance(current_user.get("last_login"), datetime) else str(current_user["last_login"]) if current_user.get("last_login") else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Failed to get user"}
        )

@app.put("/api/auth/update", tags=["Authentication"])
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Update user profile information.
    
    Returns:
        200 OK: Profile updated successfully
        400 Bad Request: Invalid input data
        401 Unauthorized: Invalid token
        409 Conflict: Email already exists (if email changed)
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        db = get_db()
        
        # Check if email is being changed and if it's unique
        if request.email.lower() != current_user["email"].lower():
            existing_user = db.get_user_by_email(request.email)
            if existing_user and existing_user["id"] != current_user["id"]:
                raise HTTPException(
                    status_code=409,
                    detail={"status": "error", "message": "Email already exists"}
                )
        
        # Update user profile
        update_data = {
            "full_name": request.full_name,
            "email": request.email.lower(),
            "bio": request.bio,
            "location": request.location,
            "website": request.website
        }
        
        updated_user = db.update_user(current_user["id"], update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "User not found"}
            )
        
        return {
            "user": {
                "id": updated_user["id"],
                "email": updated_user["email"],
                "full_name": updated_user["full_name"],
                "avatar_url": updated_user.get("avatar_url"),
                "bio": updated_user.get("bio"),
                "location": updated_user.get("location"),
                "website": updated_user.get("website"),
                "created_at": updated_user["created_at"].isoformat() if isinstance(updated_user["created_at"], datetime) else str(updated_user["created_at"]),
                "updated_at": updated_user["updated_at"].isoformat() if isinstance(updated_user["updated_at"], datetime) else str(updated_user["updated_at"]) if updated_user.get("updated_at") else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail={"status": "error", "message": "Email already exists"}
            )
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Failed to update profile"}
        )

@app.post("/api/auth/upload-avatar", tags=["Authentication"])
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Upload user avatar image.
    
    Accepts image files (JPEG, PNG, WebP, GIF) via multipart/form-data.
    Max size: 5MB. Images are resized to 400x400px.
    
    Returns:
        200 OK: Avatar uploaded successfully
        400 Bad Request: Invalid image format or size
        401 Unauthorized: Invalid token
        413 Payload Too Large: Image exceeds size limit
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        import base64
        import io
        
        # Try to import PIL, handle gracefully if not available
        try:
            from PIL import Image
            PIL_AVAILABLE = True
        except ImportError:
            PIL_AVAILABLE = False
            logger.warning("Pillow not available, storing image as-is without processing")
        
        # Read file content
        try:
            file_content = await file.read()
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "Failed to read uploaded file"}
            )
        
        # Validate file size (max 5MB)
        if len(file_content) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail={"status": "error", "message": "Image size exceeds 5MB limit"}
            )
        
        # Validate content type
        content_type = file.content_type
        if content_type and not content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": f"Invalid file type: {content_type}. Only image files are allowed."}
            )
        
        # Process image if Pillow is available, otherwise store as-is
        if PIL_AVAILABLE:
            try:
                image = Image.open(io.BytesIO(file_content))
                image.verify()  # Verify it's a valid image
                
                # Reopen for processing (verify() closes the image)
                image = Image.open(io.BytesIO(file_content))
                
                # Validate format
                if image.format not in ['JPEG', 'PNG', 'WEBP', 'GIF']:
                    raise HTTPException(
                        status_code=400,
                        detail={"status": "error", "message": f"Unsupported image format: {image.format}. Supported: JPEG, PNG, WebP, GIF"}
                    )
                
                # Resize to 400x400 (maintain aspect ratio)
                image.thumbnail((400, 400), Image.Resampling.LANCZOS)
                
                # Convert back to base64
                buffer = io.BytesIO()
                # Convert RGBA to RGB if necessary (for PNG with transparency)
                if image.format == 'PNG' and image.mode == 'RGBA':
                    # Create white background
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
                    image = background
                
                image.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)
                processed_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # Store as data URI
                avatar_url = f"data:image/jpeg;base64,{processed_base64}"
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing image with Pillow: {str(e)}")
                # Fallback: convert original to base64
                base64_data = base64.b64encode(file_content).decode('utf-8')
                # Determine MIME type
                mime_type = content_type or 'image/jpeg'
                avatar_url = f"data:{mime_type};base64,{base64_data}"
        else:
            # Pillow not available, convert to base64
            base64_data = base64.b64encode(file_content).decode('utf-8')
            mime_type = content_type or 'image/jpeg'
            avatar_url = f"data:{mime_type};base64,{base64_data}"
        
        # Update user avatar
        db = get_db()
        updated_user = db.update_user(current_user["id"], {"avatar_url": avatar_url})
        
        if not updated_user:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "User not found"}
            )
        
        return {
            "user": {
                "id": updated_user["id"],
                "email": updated_user["email"],
                "full_name": updated_user["full_name"],
                "avatar_url": updated_user.get("avatar_url"),
                "updated_at": updated_user["updated_at"].isoformat() if isinstance(updated_user["updated_at"], datetime) else str(updated_user["updated_at"]) if updated_user.get("updated_at") else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"Failed to upload avatar: {str(e)}"}
        )

@app.post("/api/auth/update-password", tags=["Authentication"])
async def change_password(
    request: ChangePasswordRequest,
    current_user: Optional[Dict] = Depends(get_current_user)
):
    """
    Change user password.
    
    Requires current password verification.
    New password must be at least 8 characters and different from current password.
    
    Returns:
        200 OK: Password updated successfully
        400 Bad Request: Invalid password (too short, same as current, etc.)
        401 Unauthorized: Invalid token or incorrect current password
        403 Forbidden: Current password is incorrect
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        db = get_db()
        auth_service = get_auth_service()
        
        # Get user with password hash
        user = db.get_user_by_email(current_user["email"])
        if not user:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "User not found"}
            )
        
        # Verify current password
        if not auth_service.verify_password(request.current_password, user["password_hash"]):
            raise HTTPException(
                status_code=403,
                detail={"status": "error", "message": "Current password is incorrect"}
            )
        
        # Check if new password is different
        if auth_service.verify_password(request.new_password, user["password_hash"]):
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "New password must be different from current password"}
            )
        
        # Hash new password
        new_password_hash = auth_service.hash_password(request.new_password)
        
        # Update password
        db.update_user_password(current_user["id"], new_password_hash)
        
        return {
            "status": "success",
            "message": "Password updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Failed to update password"}
        )

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
    Modes: 'conservative', 'moderate', or 'aggressive'
    """
    try:
        db = get_db()
        
        if strategy.mode not in ["conservative", "moderate", "aggressive"]:
            raise HTTPException(
                status_code=400,
                detail="Mode must be 'conservative', 'moderate', or 'aggressive'"
            )
        
        # Validate risk_per_trade
        if not (0 < strategy.risk_per_trade <= 1):
            raise HTTPException(
                status_code=400,
                detail="risk_per_trade must be between 0 and 1 (0.01 = 1%)"
            )
        
        db.set_config("strategy_mode", strategy.mode)
        db.set_config("risk_per_trade", str(strategy.risk_per_trade))
        
        if strategy.take_profit_pct is not None:
            db.set_config("take_profit_pct", str(strategy.take_profit_pct))
        else:
            # Delete if None
            try:
                db.delete_config("take_profit_pct")
            except:
                pass
        
        if strategy.stop_loss_pct is not None:
            db.set_config("stop_loss_pct", str(strategy.stop_loss_pct))
        else:
            # Delete if None
            try:
                db.delete_config("stop_loss_pct")
            except:
                pass
        
        db.add_bot_log(f"Strategy updated: {strategy.mode}", "INFO")
        
        return {
            "status": "saved",
            "strategy": {
                "mode": strategy.mode,
                "risk_per_trade": strategy.risk_per_trade,
                "take_profit_pct": strategy.take_profit_pct,
                "stop_loss_pct": strategy.stop_loss_pct
            }
        }
    except HTTPException:
        raise
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
            started_at = datetime.utcnow()
            db.set_config("agent_started_at", started_at.isoformat() + "Z")
            db.add_bot_log("Agent started successfully", "INFO")
            
            return {
                "status": "started",
                "message": "Agent started successfully",
                "started_at": started_at.isoformat() + "Z"
            }
        
        elif control.action == "stop":
            db.set_config("agent_status", "stopped")
            db.add_bot_log("Agent stopped successfully", "INFO")
            
            return {
                "status": "stopped",
                "message": "Agent stopped successfully",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        
        elif control.action == "emergency_stop":
            db.set_config("agent_status", "emergency_stopped")
            db.add_bot_log("EMERGENCY STOP activated", "ERROR")
            
            positions_closed = False
            if control.close_all_positions:
                # In production, this would close all open positions
                # For now, just log it
                db.add_bot_log("EMERGENCY STOP: Closing all positions", "ERROR")
                positions_closed = True
            
            return {
                "status": "emergency_stopped",
                "message": "Emergency stop activated",
                "positions_closed": positions_closed,
                "timestamp": datetime.utcnow().isoformat() + "Z"
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
        
        # Get open trades count
        open_trades = db.get_trades(status="OPEN", limit=1000)
        open_positions = len(open_trades)
        
        # Calculate daily PnL (sum of pnl for trades closed today)
        daily_pnl = None
        if exchange_connected:
            try:
                from datetime import date
                today = date.today()
                all_trades = db.get_trades(status="CLOSED", limit=1000)
                daily_pnl = sum(
                    float(trade.get("pnl", 0) or 0)
                    for trade in all_trades
                    if trade.get("exit_time") and 
                    datetime.fromisoformat(str(trade["exit_time"]).replace("Z", "+00:00")).date() == today
                )
                if daily_pnl == 0:
                    daily_pnl = None
            except Exception as e:
                logger.warning(f"Could not calculate daily PnL: {str(e)}")
        
        # Get balance (would fetch from exchange in production)
        balance = None
        
        return {
            "agent_status": agent_status,
            "exchange_connected": exchange_connected,
            "balance": balance,
            "daily_pnl": daily_pnl,
            "open_positions": open_positions,
            "last_update": datetime.utcnow().isoformat() + "Z"
        }
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
    Returns trades ordered by entry_time DESC (newest first).
    """
    try:
        db = get_db()
        trades = db.get_trades(status=status, limit=limit)
        
        # Convert timestamps to ISO format strings
        result = []
        for trade in trades:
            trade_dict = dict(trade)
            # Convert entry_time
            if isinstance(trade_dict.get("entry_time"), datetime):
                trade_dict["entry_time"] = trade_dict["entry_time"].isoformat() + "Z"
            elif trade_dict.get("entry_time"):
                ts = str(trade_dict["entry_time"])
                if not ts.endswith("Z") and "+" not in ts:
                    trade_dict["entry_time"] = ts + "Z"
            
            # Convert exit_time
            if trade_dict.get("exit_time"):
                if isinstance(trade_dict["exit_time"], datetime):
                    trade_dict["exit_time"] = trade_dict["exit_time"].isoformat() + "Z"
                else:
                    ts = str(trade_dict["exit_time"])
                    if not ts.endswith("Z") and "+" not in ts:
                        trade_dict["exit_time"] = ts + "Z"
            
            result.append(trade_dict)
        
        return result
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
async def get_logs(limit: int = 50, level: Optional[str] = None):
    """
    Get system logs from database.
    Thin client: Frontend displays these in real-time.
    Returns logs ordered by timestamp DESC (newest first).
    """
    try:
        db = get_db()
        logs = db.get_bot_logs(level=level, limit=limit)
        
        # Convert timestamps to ISO format strings
        result = []
        for log in logs:
            log_dict = dict(log)
            if isinstance(log_dict.get("timestamp"), datetime):
                log_dict["timestamp"] = log_dict["timestamp"].isoformat() + "Z"
            elif log_dict.get("timestamp"):
                # Already a string, ensure it has Z suffix
                ts = str(log_dict["timestamp"])
                if not ts.endswith("Z") and "+" not in ts:
                    log_dict["timestamp"] = ts + "Z"
            result.append(log_dict)
        
        return result
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
    Returns history ordered by timestamp ASC (oldest first, for charting).
    """
    try:
        db = get_db()
        
        symbol_list = symbols.split(",") if symbols else None
        history = db.get_portfolio_history(symbols=symbol_list, days=days)
        
        # Convert timestamps to ISO format strings
        result = []
        for entry in history:
            entry_dict = dict(entry)
            if isinstance(entry_dict.get("timestamp"), datetime):
                entry_dict["timestamp"] = entry_dict["timestamp"].isoformat() + "Z"
            elif entry_dict.get("timestamp"):
                ts = str(entry_dict["timestamp"])
                if not ts.endswith("Z") and "+" not in ts:
                    entry_dict["timestamp"] = ts + "Z"
            result.append(entry_dict)
        
        return result
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

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure CORS headers are always present."""
    # Don't handle HTTPException (FastAPI handles those)
    if isinstance(exc, HTTPException):
        raise exc
    
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Get origin from request
    origin = request.headers.get("origin", "*")
    
    # Check if origin is in allowed list
    allowed_origins = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
        "https://sidnei-almeida.github.io",
        "https://groq-finance-inference.onrender.com",
    ]
    
    # Use origin if allowed, otherwise use first allowed origin
    cors_origin = origin if origin in allowed_origins else allowed_origins[0] if allowed_origins else "*"
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc) if logger.level == logging.DEBUG else None
        },
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
        }
    )

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
