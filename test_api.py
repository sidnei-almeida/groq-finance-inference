#!/usr/bin/env python3
"""
Comprehensive API Test Suite
Tests all endpoints before deployment
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "https://groq-finance-inference.onrender.com"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def print_section(title: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def test_endpoint(method: str, endpoint: str, data: Dict = None, expected_status: int = 200) -> Dict[str, Any]:
    """Test an API endpoint."""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=60)
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            return {"error": f"Unknown method: {method}"}
        
        result = {
            "status_code": response.status_code,
            "success": response.status_code == expected_status,
            "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
        
        return result
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "success": False}

def main():
    print_section("🚀 FinSight API - Comprehensive Test Suite")
    
    # Check if API is running
    print_info("Checking if API is running...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print_success("API is running and healthy!")
        else:
            print_error(f"API returned status {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to API. Is it running?")
        print_info("Start the API with: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
        return
    
    tests_passed = 0
    tests_failed = 0
    
    # ========================================================================
    # 1. HEALTH & ROOT ENDPOINTS
    # ========================================================================
    print_section("1. Health & Root Endpoints")
    
    # Root endpoint
    result = test_endpoint("GET", "/")
    if result.get("success"):
        print_success("GET / - Root endpoint")
        tests_passed += 1
    else:
        print_error(f"GET / - Failed: {result.get('error', result.get('response'))}")
        tests_failed += 1
    
    # Health check
    result = test_endpoint("GET", "/api/health")
    if result.get("success"):
        health_data = result.get("response", {})
        print_success(f"GET /api/health - Status: {health_data.get('status')}")
        tests_passed += 1
    else:
        print_error(f"GET /api/health - Failed: {result.get('error', result.get('response'))}")
        tests_failed += 1
    
    # ========================================================================
    # 2. PORTFOLIO ANALYSIS
    # ========================================================================
    print_section("2. Portfolio Analysis Endpoints")
    
    # Test analysis without AI (faster)
    print_info("Testing portfolio analysis (without AI for speed)...")
    analysis_data = {
        "symbols": ["AAPL", "TSLA"],
        "weights": [0.6, 0.4],
        "period": "6mo",
        "include_ai_analysis": False
    }
    
    result = test_endpoint("POST", "/api/analyze", data=analysis_data, expected_status=200)
    if result.get("success"):
        analysis_response = result.get("response", {})
        analysis_id = analysis_response.get("analysis_id")
        metrics = analysis_response.get("metrics", {})
        
        print_success(f"POST /api/analyze - Analysis ID: {analysis_id}")
        print_info(f"  Annual Return: {metrics.get('annual_return')}%")
        print_info(f"  Volatility: {metrics.get('volatility')}%")
        print_info(f"  Sharpe Ratio: {metrics.get('sharpe_ratio')}")
        print_info(f"  Max Drawdown: {metrics.get('max_drawdown')}%")
        tests_passed += 1
        
        # Test getting specific analysis
        if analysis_id:
            result2 = test_endpoint("GET", f"/api/analyses/{analysis_id}")
            if result2.get("success"):
                print_success(f"GET /api/analyses/{analysis_id} - Retrieved successfully")
                tests_passed += 1
            else:
                print_error(f"GET /api/analyses/{analysis_id} - Failed")
                tests_failed += 1
            
            # Test analysis logs
            result3 = test_endpoint("GET", f"/api/analyses/{analysis_id}/logs")
            if result3.get("success"):
                logs = result3.get("response", [])
                print_success(f"GET /api/analyses/{analysis_id}/logs - Found {len(logs)} logs")
                tests_passed += 1
            else:
                print_error(f"GET /api/analyses/{analysis_id}/logs - Failed")
                tests_failed += 1
    else:
        print_error(f"POST /api/analyze - Failed: {result.get('error', result.get('response'))}")
        tests_failed += 1
    
    # Test getting recent analyses
    result = test_endpoint("GET", "/api/analyses?limit=5")
    if result.get("success"):
        analyses = result.get("response", [])
        print_success(f"GET /api/analyses - Found {len(analyses)} analyses")
        tests_passed += 1
    else:
        print_error(f"GET /api/analyses - Failed")
        tests_failed += 1
    
    # ========================================================================
    # 3. EXCHANGE CONNECTION
    # ========================================================================
    print_section("3. Exchange Connection Endpoints")
    
    # Get exchange status
    result = test_endpoint("GET", "/api/exchange/status")
    if result.get("success"):
        status = result.get("response", {})
        print_success(f"GET /api/exchange/status - Connected: {status.get('connected')}")
        tests_passed += 1
    else:
        print_error("GET /api/exchange/status - Failed")
        tests_failed += 1
    
    # Test exchange connection (with dummy credentials - will fail validation)
    print_info("Testing exchange connection (expected to fail validation)...")
    connection_data = {
        "exchange": "binance",
        "api_key": "test_key_too_short",  # Too short for binance (needs 64 chars), should fail validation
        "api_secret": "test_secret",
        "testnet": True
    }
    
    result = test_endpoint("POST", "/api/exchange/connect", data=connection_data, expected_status=400)
    if result.get("status_code") == 400:  # Expected to fail validation with 400
        print_success("POST /api/exchange/connect - Validation working (rejected invalid key)")
        tests_passed += 1
    else:
        print_error(f"POST /api/exchange/connect - Should have rejected invalid key (got status {result.get('status_code')})")
        tests_failed += 1
    
    # ========================================================================
    # 4. GUARD-RAILS
    # ========================================================================
    print_section("4. Risk Management (Guard-Rails)")
    
    # Get guard-rails
    result = test_endpoint("GET", "/api/guardrails")
    if result.get("success"):
        guardrails = result.get("response", {})
        print_success("GET /api/guardrails - Retrieved successfully")
        tests_passed += 1
    else:
        print_error("GET /api/guardrails - Failed")
        tests_failed += 1
    
    # Set guard-rails
    guardrails_data = {
        "daily_stop_loss": 500.0,
        "max_leverage": 2.0,
        "allowed_symbols": ["BTC", "ETH", "AAPL", "TSLA"],
        "max_position_size": 10000.0
    }
    
    result = test_endpoint("POST", "/api/guardrails", data=guardrails_data)
    if result.get("success"):
        print_success("POST /api/guardrails - Set successfully")
        tests_passed += 1
    else:
        print_error(f"POST /api/guardrails - Failed: {result.get('error', result.get('response'))}")
        tests_failed += 1
    
    # ========================================================================
    # 5. STRATEGY CONFIGURATION
    # ========================================================================
    print_section("5. Strategy Configuration")
    
    # Get strategy
    result = test_endpoint("GET", "/api/strategy")
    if result.get("success"):
        strategy = result.get("response", {})
        print_success(f"GET /api/strategy - Mode: {strategy.get('mode')}")
        tests_passed += 1
    else:
        print_error("GET /api/strategy - Failed")
        tests_failed += 1
    
    # Set strategy
    strategy_data = {
        "mode": "conservative",
        "risk_per_trade": 0.01,
        "take_profit_pct": 5.0,
        "stop_loss_pct": 2.0
    }
    
    result = test_endpoint("POST", "/api/strategy", data=strategy_data)
    if result.get("success"):
        print_success("POST /api/strategy - Set successfully")
        tests_passed += 1
    else:
        print_error(f"POST /api/strategy - Failed: {result.get('error', result.get('response'))}")
        tests_failed += 1
    
    # ========================================================================
    # 6. AGENT CONTROL
    # ========================================================================
    print_section("6. Agent Control")
    
    # Get agent status
    result = test_endpoint("GET", "/api/agent/status")
    if result.get("success"):
        status = result.get("response", {})
        print_success(f"GET /api/agent/status - Status: {status.get('agent_status')}")
        tests_passed += 1
    else:
        print_error("GET /api/agent/status - Failed")
        tests_failed += 1
    
    # Test agent control (stop - safe operation)
    control_data = {
        "action": "stop",
        "close_all_positions": False
    }
    
    result = test_endpoint("POST", "/api/agent/control", data=control_data)
    if result.get("success"):
        print_success("POST /api/agent/control (stop) - Success")
        tests_passed += 1
    else:
        print_error(f"POST /api/agent/control - Failed: {result.get('error', result.get('response'))}")
        tests_failed += 1
    
    # ========================================================================
    # 7. MONITORING ENDPOINTS (Thin Client)
    # ========================================================================
    print_section("7. Monitoring Endpoints (Thin Client)")
    
    # Get trades
    result = test_endpoint("GET", "/api/trades?limit=10")
    if result.get("success"):
        trades = result.get("response", [])
        print_success(f"GET /api/trades - Found {len(trades)} trades")
        tests_passed += 1
    else:
        print_error("GET /api/trades - Failed")
        tests_failed += 1
    
    # Get open trades
    result = test_endpoint("GET", "/api/trades/open")
    if result.get("success"):
        open_trades = result.get("response", [])
        print_success(f"GET /api/trades/open - Found {len(open_trades)} open trades")
        tests_passed += 1
    else:
        print_error("GET /api/trades/open - Failed")
        tests_failed += 1
    
    # Get logs
    result = test_endpoint("GET", "/api/logs?limit=10")
    if result.get("success"):
        logs = result.get("response", [])
        print_success(f"GET /api/logs - Found {len(logs)} logs")
        tests_passed += 1
    else:
        print_error("GET /api/logs - Failed")
        tests_failed += 1
    
    # Get portfolio history
    result = test_endpoint("GET", "/api/portfolio/history?days=30")
    if result.get("success"):
        history = result.get("response", [])
        print_success(f"GET /api/portfolio/history - Found {len(history)} snapshots")
        tests_passed += 1
    else:
        print_error("GET /api/portfolio/history - Failed")
        tests_failed += 1
    
    # ========================================================================
    # 8. ERROR HANDLING
    # ========================================================================
    print_section("8. Error Handling Tests")
    
    # Test invalid analysis request
    invalid_data = {
        "symbols": [],  # Empty symbols should fail
        "period": "1y"
    }
    
    result = test_endpoint("POST", "/api/analyze", data=invalid_data, expected_status=422)
    if result.get("status_code") == 422:
        print_success("POST /api/analyze - Validation working (rejected empty symbols)")
        tests_passed += 1
    else:
        print_error("POST /api/analyze - Should validate empty symbols")
        tests_failed += 1
    
    # Test non-existent analysis
    result = test_endpoint("GET", "/api/analyses/99999", expected_status=404)
    if result.get("status_code") == 404:
        print_success("GET /api/analyses/{id} - 404 handling working")
        tests_passed += 1
    else:
        print_error("GET /api/analyses/{id} - Should return 404 for non-existent ID")
        tests_failed += 1
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print_section("📊 Test Summary")
    
    total_tests = tests_passed + tests_failed
    success_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"{Colors.BOLD}Total Tests: {total_tests}{Colors.END}")
    print(f"{Colors.GREEN}✅ Passed: {tests_passed}{Colors.END}")
    print(f"{Colors.RED}❌ Failed: {tests_failed}{Colors.END}")
    print(f"{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.END}")
    
    if tests_failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed! API is ready for deployment! 🚀{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some tests failed. Review errors above before deployment.{Colors.END}")
        return 1

if __name__ == "__main__":
    exit(main())
