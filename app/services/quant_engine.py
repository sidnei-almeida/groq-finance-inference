"""
Quantitative Finance Engine
Handles data collection, cleaning, and financial calculations for portfolio analysis.
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
from scipy.optimize import minimize

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuantitativeEngine:
    """
    Engine for quantitative financial analysis.
    Fetches market data, cleans it, and calculates portfolio metrics.
    """
    
    def __init__(self):
        """
        Initialize the Quantitative Engine.
        Sets risk-free rate for Sharpe Ratio calculations (4% = Treasury Yield).
        """
        logger.info("Initializing Quantitative Engine...")
        # We assume a risk-free rate of 4% (Treasury Yield) for Sharpe Ratio calculations
        self.risk_free_rate = 0.04
        logger.info(f"Risk-free rate set to {self.risk_free_rate * 100}% (Treasury Yield)")
    
    def fetch_market_data(
        self, 
        symbols: List[str], 
        period: str = "1y",
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical market data from Yahoo Finance.
        
        Args:
            symbols: List of ticker symbols (e.g., ['AAPL', 'TSLA', 'BTC-USD'])
            period: Time period for data ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
            interval: Data interval ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')
        
        Returns:
            DataFrame with historical prices, or None if fetch fails
        """
        logger.info(f"=== STEP 1: FETCHING MARKET DATA ===")
        logger.info(f"Symbols requested: {', '.join(symbols)}")
        logger.info(f"Period: {period}, Interval: {interval}")
        
        try:
            # Fetch data from yfinance
            logger.info("Connecting to Yahoo Finance API...")
            # Use group_by='ticker' only for multiple symbols
            download_kwargs = {
                'period': period,
                'interval': interval,
                'progress': False
            }
            if len(symbols) > 1:
                download_kwargs['group_by'] = 'ticker'
            
            data = yf.download(symbols, **download_kwargs)
            
            if data.empty:
                logger.error("No data returned from Yahoo Finance")
                return None
            
            logger.info(f"Successfully fetched data: {data.shape[0]} rows, {data.shape[1]} columns")
            logger.info(f"Date range: {data.index[0]} to {data.index[-1]}")
            
            # Handle multi-level columns (yfinance uses MultiIndex even for single symbols with group_by='ticker')
            if isinstance(data.columns, pd.MultiIndex):
                logger.info("Processing MultiIndex data structure...")
                # Extract 'Close' prices for each symbol
                close_prices = {}
                for symbol in symbols:
                    # Try both (symbol, 'Close') and ('Close', symbol) formats
                    if (symbol, 'Close') in data.columns:
                        close_prices[symbol] = data[(symbol, 'Close')]
                        logger.info(f"  ✓ Found data for {symbol}: {len(close_prices[symbol])} data points")
                    elif ('Close', symbol) in data.columns:
                        close_prices[symbol] = data[('Close', symbol)]
                        logger.info(f"  ✓ Found data for {symbol}: {len(close_prices[symbol])} data points")
                    else:
                        # Try to find any column with this symbol
                        found = False
                        for col in data.columns:
                            if isinstance(col, tuple) and symbol in col and 'Close' in col:
                                close_prices[symbol] = data[col]
                                logger.info(f"  ✓ Found data for {symbol}: {len(close_prices[symbol])} data points")
                                found = True
                                break
                        if not found:
                            logger.warning(f"  ✗ No data found for {symbol}")
                            logger.debug(f"  Available columns: {data.columns.tolist()}")
                
                if not close_prices:
                    logger.error("No valid close prices found for any symbol")
                    return None
                
                # Combine into single DataFrame
                data = pd.DataFrame(close_prices)
                logger.info(f"Combined DataFrame created with {len(data)} rows and {len(data.columns)} symbols")
            else:
                # Single symbol case - yfinance returns flat structure (when group_by is not used)
                logger.info("Processing flat data structure...")
                if 'Close' in data.columns:
                    data = pd.DataFrame({symbols[0]: data['Close']})
                    logger.info(f"  ✓ Extracted Close prices for {symbols[0]}: {len(data)} data points")
                elif len(symbols) == 1:
                    # Sometimes yfinance returns data with symbol as column name directly
                    if symbols[0] in data.columns:
                        data = pd.DataFrame({symbols[0]: data[symbols[0]]})
                        logger.info(f"  ✓ Found data for {symbols[0]}: {len(data)} data points")
                    else:
                        # Try to use the first numeric column
                        numeric_cols = data.select_dtypes(include=[np.number]).columns
                        if len(numeric_cols) > 0:
                            logger.info(f"  Using first numeric column: {numeric_cols[0]}")
                            data = pd.DataFrame({symbols[0]: data[numeric_cols[0]]})
                        else:
                            logger.error("No 'Close' column or numeric data found")
                            return None
                else:
                    logger.error("No 'Close' column found in data")
                    return None
            
            logger.info("=== STEP 1 COMPLETE: Market data fetched successfully ===\n")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}", exc_info=True)
            return None
    
    def clean_data(self, data: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Clean and prepare market data for analysis.
        
        Args:
            data: Raw DataFrame with historical prices
        
        Returns:
            Cleaned DataFrame, or None if cleaning fails
        """
        logger.info("=== STEP 2: CLEANING DATA ===")
        logger.info(f"Input data shape: {data.shape[0]} rows, {data.shape[1]} columns")
        
        try:
            # Remove rows with all NaN values
            initial_rows = len(data)
            data = data.dropna(how='all')
            removed_rows = initial_rows - len(data)
            if removed_rows > 0:
                logger.info(f"  Removed {removed_rows} rows with all NaN values")
            
            # Forward fill missing values (carry last known price forward)
            missing_before = data.isna().sum().sum()
            data = data.ffill()
            missing_after = data.isna().sum().sum()
            if missing_before > 0:
                logger.info(f"  Forward-filled {missing_before - missing_after} missing values")
            
            # Backward fill any remaining NaN (fill from next known price)
            missing_before = data.isna().sum().sum()
            data = data.bfill()
            missing_after = data.isna().sum().sum()
            if missing_before > 0:
                logger.info(f"  Backward-filled {missing_before - missing_after} remaining missing values")
            
            # Remove any rows that still have NaN (shouldn't happen, but safety check)
            final_nan_count = data.isna().sum().sum()
            if final_nan_count > 0:
                logger.warning(f"  Warning: {final_nan_count} NaN values remain after cleaning")
                data = data.dropna()
                logger.info(f"  Removed rows with remaining NaN values")
            
            # Ensure we have enough data points (at least 30 days for meaningful analysis)
            if len(data) < 30:
                logger.warning(f"  Warning: Only {len(data)} data points available (recommended: 30+)")
            
            logger.info(f"Cleaned data shape: {data.shape[0]} rows, {data.shape[1]} columns")
            logger.info(f"Date range after cleaning: {data.index[0]} to {data.index[-1]}")
            logger.info("=== STEP 2 COMPLETE: Data cleaned successfully ===\n")
            
            return data
            
        except Exception as e:
            logger.error(f"Error cleaning data: {str(e)}", exc_info=True)
            return None
    
    def calculate_portfolio_metrics(
        self, 
        data: pd.DataFrame, 
        weights: Optional[List[float]] = None
    ) -> Optional[Dict]:
        """
        Calculate portfolio financial metrics.
        
        Args:
            data: Cleaned DataFrame with historical prices
            weights: Portfolio weights (must sum to 1.0). If None, equal weights are used.
        
        Returns:
            Dictionary with portfolio metrics, or None if calculation fails
        """
        logger.info("=== STEP 3: DATA ANALYSIS ===")
        logger.info(f"Input data shape: {data.shape[0]} rows, {data.shape[1]} columns")
        
        try:
            # Validate weights
            if weights is None:
                # Equal weights for all assets
                n_assets = len(data.columns)
                weights = [1.0 / n_assets] * n_assets
                logger.info(f"No weights provided. Using equal weights: {[round(w, 3) for w in weights]}")
            else:
                # Validate weights sum to 1.0
                weights_sum = sum(weights)
                if abs(weights_sum - 1.0) > 0.01:  # Allow small floating point error
                    logger.warning(f"Weights sum to {weights_sum}, normalizing to 1.0")
                    weights = [w / weights_sum for w in weights]
                logger.info(f"Using provided weights: {[round(w, 3) for w in weights]}")
            
            # Convert weights to numpy array
            weights = np.array(weights)
            
            # Validate weights match number of assets
            if len(weights) != len(data.columns):
                logger.error(f"Weights count ({len(weights)}) doesn't match assets count ({len(data.columns)})")
                return None
            
            # --- 3. DATA ANALYSIS ---
            logger.info("Calculating daily returns (percentage change from previous day)...")
            # Calculate Daily Returns (Percentage change from previous day)
            daily_returns = data.pct_change().dropna()
            logger.info(f"  ✓ Daily returns calculated: {len(daily_returns)} data points")
            logger.info(f"  Sample daily returns:\n{daily_returns.head().to_string()}")
            
            logger.info("Calculating annualized covariance matrix (risk measure)...")
            # Annualized Covariance Matrix (Risk)
            # 252 = Trading days in a year
            cov_matrix = daily_returns.cov() * 252
            logger.info(f"  ✓ Covariance matrix calculated (annualized with 252 trading days)")
            logger.info(f"  Matrix shape: {cov_matrix.shape}")
            logger.info(f"  Diagonal (variances): {[round(cov_matrix.iloc[i, i], 6) for i in range(len(cov_matrix))]}")
            
            logger.info("Calculating annualized average returns...")
            # Annualized Average Return
            avg_returns = daily_returns.mean() * 252
            logger.info(f"  ✓ Average returns calculated (annualized)")
            logger.info(f"  Annualized returns per asset: {avg_returns.to_dict()}")
            
            logger.info("Calculating portfolio return (weighted average)...")
            # Portfolio Calculation (Matrix Multiplication)
            # Weight * Return
            port_return = np.sum(avg_returns * weights)
            logger.info(f"  ✓ Portfolio return: {round(port_return * 100, 2)}%")
            
            logger.info("Calculating portfolio variance and volatility...")
            # Weight * Covariance * Weight = Variance
            port_variance = np.dot(weights, np.dot(cov_matrix, weights))
            port_volatility = np.sqrt(port_variance)
            logger.info(f"  ✓ Portfolio variance: {round(port_variance, 6)}")
            logger.info(f"  ✓ Portfolio volatility (standard deviation): {round(port_volatility * 100, 2)}%")
            
            logger.info("Calculating Sharpe Ratio...")
            # Sharpe Ratio: (Return - Risk Free) / Volatility
            sharpe_ratio = (port_return - self.risk_free_rate) / port_volatility
            logger.info(f"  Formula: (Portfolio Return - Risk-Free Rate) / Volatility")
            logger.info(f"  Calculation: ({round(port_return * 100, 2)}% - {round(self.risk_free_rate * 100, 2)}%) / {round(port_volatility * 100, 2)}%")
            logger.info(f"  ✓ Sharpe Ratio: {round(sharpe_ratio, 2)}")
            
            # Calculate portfolio returns time series for advanced metrics
            portfolio_returns = daily_returns.dot(weights)
            portfolio_cumulative = (1 + portfolio_returns).cumprod()
            
            # Advanced metrics
            advanced_metrics = self._calculate_advanced_metrics(
                daily_returns, 
                portfolio_returns, 
                portfolio_cumulative,
                weights,
                data
            )
            
            # Return comprehensive dictionary
            result = {
                "annual_return": round(port_return * 100, 2),   # Percentage
                "volatility": round(port_volatility * 100, 2),  # Percentage
                "sharpe_ratio": round(sharpe_ratio, 2),         # Decimal
                "start_date": str(data.index[0].date()),
                "end_date": str(data.index[-1].date()),
                **advanced_metrics  # Merge advanced metrics
            }
            
            logger.info("=== STEP 3 COMPLETE: Portfolio metrics calculated successfully ===")
            logger.info(f"Final Results:\n  Annual Return: {result['annual_return']}%\n  Volatility: {result['volatility']}%\n  Sharpe Ratio: {result['sharpe_ratio']}\n  Period: {result['start_date']} to {result['end_date']}\n")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating portfolio metrics: {str(e)}", exc_info=True)
            return None
    
    def _calculate_advanced_metrics(
        self,
        daily_returns: pd.DataFrame,
        portfolio_returns: pd.Series,
        portfolio_cumulative: pd.Series,
        weights: np.ndarray,
        price_data: pd.DataFrame
    ) -> Dict:
        """
        Calculate advanced risk and performance metrics.
        
        Args:
            daily_returns: DataFrame with daily returns per asset
            portfolio_returns: Series with portfolio daily returns
            portfolio_cumulative: Series with cumulative portfolio value
            weights: Portfolio weights
            price_data: Original price data
        
        Returns:
            Dictionary with advanced metrics
        """
        logger.info("=== ADVANCED METRICS CALCULATION ===")
        advanced = {}
        
        try:
            # 1. MAXIMUM DRAWDOWN - Worst peak-to-trough decline
            logger.info("Calculating Maximum Drawdown...")
            running_max = portfolio_cumulative.expanding().max()
            drawdown = (portfolio_cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
            advanced['max_drawdown'] = round(abs(max_drawdown) * 100, 2)  # Percentage
            logger.info(f"  ✓ Maximum Drawdown: {advanced['max_drawdown']}%")
            
            # 2. CALMAR RATIO - Annual Return / Maximum Drawdown
            logger.info("Calculating Calmar Ratio...")
            annual_return_decimal = portfolio_returns.mean() * 252
            if abs(max_drawdown) > 0.0001:  # Avoid division by zero
                calmar_ratio = annual_return_decimal / abs(max_drawdown)
                advanced['calmar_ratio'] = round(calmar_ratio, 2)
                logger.info(f"  ✓ Calmar Ratio: {advanced['calmar_ratio']}")
            else:
                advanced['calmar_ratio'] = None
                logger.info("  ⚠ Calmar Ratio: Cannot calculate (no drawdown)")
            
            # 3. SORTINO RATIO - Sharpe but only penalizes downside volatility
            logger.info("Calculating Sortino Ratio...")
            downside_returns = portfolio_returns[portfolio_returns < 0]
            if len(downside_returns) > 0:
                downside_std = np.sqrt((downside_returns ** 2).mean() * 252)
                if downside_std > 0.0001:
                    sortino_ratio = (annual_return_decimal - self.risk_free_rate) / downside_std
                    advanced['sortino_ratio'] = round(sortino_ratio, 2)
                    advanced['downside_deviation'] = round(downside_std * 100, 2)
                    logger.info(f"  ✓ Sortino Ratio: {advanced['sortino_ratio']}")
                    logger.info(f"  ✓ Downside Deviation: {advanced['downside_deviation']}%")
                else:
                    advanced['sortino_ratio'] = None
                    advanced['downside_deviation'] = 0.0
            else:
                advanced['sortino_ratio'] = None
                advanced['downside_deviation'] = 0.0
                logger.info("  ⚠ Sortino Ratio: Cannot calculate (no negative returns)")
            
            # 4. VALUE AT RISK (VaR) - Potential loss at 95% confidence
            logger.info("Calculating Value at Risk (VaR)...")
            var_95 = np.percentile(portfolio_returns, 5)  # 5th percentile (95% VaR)
            var_99 = np.percentile(portfolio_returns, 1)  # 1st percentile (99% VaR)
            advanced['var_95'] = round(abs(var_95) * 100, 2)  # Daily VaR as percentage
            advanced['var_99'] = round(abs(var_99) * 100, 2)
            # Annualized VaR (multiply by sqrt(252))
            advanced['var_95_annualized'] = round(abs(var_95) * np.sqrt(252) * 100, 2)
            advanced['var_99_annualized'] = round(abs(var_99) * np.sqrt(252) * 100, 2)
            logger.info(f"  ✓ VaR 95% (daily): {advanced['var_95']}%")
            logger.info(f"  ✓ VaR 99% (daily): {advanced['var_99']}%")
            
            # 5. CONDITIONAL VaR (CVaR/Expected Shortfall) - Average loss beyond VaR
            logger.info("Calculating Conditional VaR (Expected Shortfall)...")
            cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()
            cvar_99 = portfolio_returns[portfolio_returns <= var_99].mean()
            advanced['cvar_95'] = round(abs(cvar_95) * 100, 2)
            advanced['cvar_99'] = round(abs(cvar_99) * 100, 2)
            advanced['cvar_95_annualized'] = round(abs(cvar_95) * np.sqrt(252) * 100, 2)
            advanced['cvar_99_annualized'] = round(abs(cvar_99) * np.sqrt(252) * 100, 2)
            logger.info(f"  ✓ CVaR 95% (daily): {advanced['cvar_95']}%")
            logger.info(f"  ✓ CVaR 99% (daily): {advanced['cvar_99']}%")
            
            # 6. SKEWNESS & KURTOSIS - Distribution shape analysis
            logger.info("Calculating Skewness and Kurtosis...")
            skewness = stats.skew(portfolio_returns)
            kurtosis = stats.kurtosis(portfolio_returns)  # Excess kurtosis (normal = 0)
            advanced['skewness'] = round(skewness, 3)
            advanced['kurtosis'] = round(kurtosis, 3)
            logger.info(f"  ✓ Skewness: {advanced['skewness']} (negative = left tail risk)")
            logger.info(f"  ✓ Kurtosis: {advanced['kurtosis']} (>3 = fat tails, higher tail risk)")
            
            # 7. CORRELATION MATRIX - Diversification analysis
            logger.info("Calculating Correlation Matrix...")
            correlation_matrix = daily_returns.corr()
            
            # Handle single asset case (no correlation to calculate)
            if len(daily_returns.columns) == 1:
                advanced['avg_correlation'] = None
                advanced['min_correlation'] = None
                advanced['max_correlation'] = None
                logger.info("  ✓ Single asset portfolio - correlation metrics not applicable")
            else:
                # Get upper triangle indices (excluding diagonal, k=1)
                triu_indices = np.triu_indices_from(correlation_matrix.values, k=1)
                triu_values = correlation_matrix.values[triu_indices]
                
                if len(triu_values) > 0:
                    advanced['avg_correlation'] = round(triu_values.mean(), 3)
                    advanced['min_correlation'] = round(triu_values.min(), 3)
                    advanced['max_correlation'] = round(triu_values.max(), 3)
                    logger.info(f"  ✓ Average Correlation: {advanced['avg_correlation']}")
                    logger.info(f"  ✓ Correlation Range: [{advanced['min_correlation']}, {advanced['max_correlation']}]")
                else:
                    # Fallback: should not happen, but handle gracefully
                    advanced['avg_correlation'] = None
                    advanced['min_correlation'] = None
                    advanced['max_correlation'] = None
                    logger.warning("  ⚠️  Could not calculate correlation metrics")
            
            # 8. PORTFOLIO CONCENTRATION (Herfindahl-Hirschman Index)
            logger.info("Calculating Portfolio Concentration (HHI)...")
            hhi = np.sum(weights ** 2)
            advanced['concentration_hhi'] = round(hhi, 3)
            # HHI interpretation: 1/N (equal weights) to 1.0 (single asset)
            n_assets = len(weights)
            equal_weight_hhi = 1.0 / n_assets
            concentration_ratio = hhi / equal_weight_hhi
            advanced['concentration_ratio'] = round(concentration_ratio, 2)
            logger.info(f"  ✓ HHI: {advanced['concentration_hhi']} (lower = more diversified)")
            logger.info(f"  ✓ Concentration Ratio: {advanced['concentration_ratio']}x equal-weight")
            
            # 9. BETA (if we can get market data - using SPY as proxy)
            logger.info("Calculating Beta vs S&P 500 (SPY)...")
            try:
                spy_data = yf.download('SPY', period='1y', progress=False)
                if not spy_data.empty and 'Close' in spy_data.columns:
                    spy_returns = spy_data['Close'].pct_change().dropna()
                    # Align dates by index
                    portfolio_returns_aligned = portfolio_returns.reindex(spy_returns.index).dropna()
                    spy_returns_aligned = spy_returns.reindex(portfolio_returns_aligned.index).dropna()
                    
                    # Final alignment
                    common_index = portfolio_returns_aligned.index.intersection(spy_returns_aligned.index)
                    if len(common_index) > 30:
                        portfolio_vals = portfolio_returns_aligned.loc[common_index].values.flatten()
                        spy_vals = spy_returns_aligned.loc[common_index].values.flatten()
                        
                        # Calculate beta: Cov(Portfolio, Market) / Var(Market)
                        covariance = np.cov(portfolio_vals, spy_vals)[0, 1]
                        market_variance = np.var(spy_vals)
                        if market_variance > 0:
                            beta = covariance / market_variance
                            advanced['beta'] = round(beta, 3)
                            logger.info(f"  ✓ Beta: {advanced['beta']} (1.0 = market, >1 = more volatile, <1 = less volatile)")
                        else:
                            advanced['beta'] = None
                            logger.info("  ⚠ Beta: Market variance is zero")
                    else:
                        advanced['beta'] = None
                        logger.info("  ⚠ Beta: Insufficient overlapping data")
                else:
                    advanced['beta'] = None
                    logger.info("  ⚠ Beta: Could not fetch SPY data")
            except Exception as e:
                advanced['beta'] = None
                logger.warning(f"  ⚠ Beta calculation failed: {str(e)}")
            
            # 10. WIN RATE - Percentage of positive return days
            logger.info("Calculating Win Rate...")
            win_rate = (portfolio_returns > 0).sum() / len(portfolio_returns)
            advanced['win_rate'] = round(win_rate * 100, 2)
            logger.info(f"  ✓ Win Rate: {advanced['win_rate']}% of days positive")
            
            # 11. BEST/WORST DAYS
            logger.info("Calculating Best/Worst Days...")
            best_day = portfolio_returns.max()
            worst_day = portfolio_returns.min()
            advanced['best_day'] = round(best_day * 100, 2)
            advanced['worst_day'] = round(worst_day * 100, 2)
            logger.info(f"  ✓ Best Day: +{advanced['best_day']}%")
            logger.info(f"  ✓ Worst Day: {advanced['worst_day']}%")
            
            # 12. RETURN DISTRIBUTION STATS
            logger.info("Calculating Return Distribution Statistics...")
            advanced['median_daily_return'] = round(portfolio_returns.median() * 100, 3)
            advanced['return_std'] = round(portfolio_returns.std() * 100, 2)
            logger.info(f"  ✓ Median Daily Return: {advanced['median_daily_return']}%")
            
            # 13. EFFICIENT FRONTIER ANALYSIS (if multiple assets)
            if len(weights) > 1:
                logger.info("Calculating Efficient Frontier metrics...")
                frontier_metrics = self._calculate_efficient_frontier_metrics(
                    daily_returns, 
                    weights
                )
                advanced.update(frontier_metrics)
            
            logger.info("=== ADVANCED METRICS COMPLETE ===\n")
            
        except Exception as e:
            logger.error(f"Error calculating advanced metrics: {str(e)}", exc_info=True)
            # Return what we have so far
            pass
        
        return advanced
    
    def _calculate_efficient_frontier_metrics(
        self,
        daily_returns: pd.DataFrame,
        current_weights: np.ndarray
    ) -> Dict:
        """
        Calculate metrics related to efficient frontier optimization.
        
        Args:
            daily_returns: DataFrame with daily returns
            current_weights: Current portfolio weights
        
        Returns:
            Dictionary with efficient frontier metrics
        """
        metrics = {}
        
        try:
            logger.info("  Analyzing Efficient Frontier...")
            
            # Annualized returns and covariance
            avg_returns = daily_returns.mean() * 252
            cov_matrix = daily_returns.cov() * 252
            
            n_assets = len(daily_returns.columns)
            
            # Current portfolio metrics
            current_return = np.sum(avg_returns * current_weights)
            current_vol = np.sqrt(np.dot(current_weights, np.dot(cov_matrix, current_weights)))
            
            # Find minimum variance portfolio
            def portfolio_variance(weights):
                return np.dot(weights, np.dot(cov_matrix, weights))
            
            constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
            bounds = tuple((0, 1) for _ in range(n_assets))
            initial_weights = np.array([1.0 / n_assets] * n_assets)
            
            min_var_result = minimize(
                portfolio_variance,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if min_var_result.success:
                min_var_weights = min_var_result.x
                min_var_return = np.sum(avg_returns * min_var_weights)
                min_var_vol = np.sqrt(min_var_result.fun)
                
                metrics['min_variance_volatility'] = round(min_var_vol * 100, 2)
                metrics['min_variance_return'] = round(min_var_return * 100, 2)
                logger.info(f"    ✓ Min Variance Portfolio: {metrics['min_variance_return']}% return, {metrics['min_variance_volatility']}% vol")
            
            # Calculate distance to efficient frontier
            # Simple approximation: compare current portfolio to min variance
            if 'min_variance_volatility' in metrics:
                vol_improvement = ((current_vol - metrics['min_variance_volatility'] / 100) / current_vol) * 100
                metrics['volatility_improvement_potential'] = round(vol_improvement, 2)
                logger.info(f"    ✓ Volatility improvement potential: {metrics['volatility_improvement_potential']}%")
            
        except Exception as e:
            logger.warning(f"  Efficient Frontier calculation failed: {str(e)}")
        
        return metrics
    
    def analyze_portfolio(
        self,
        symbols: List[str],
        weights: Optional[List[float]] = None,
        period: str = "1y"
    ) -> Optional[Dict]:
        """
        Complete pipeline: fetch, clean, and analyze portfolio.
        
        Args:
            symbols: List of ticker symbols
            weights: Portfolio weights (optional, defaults to equal weights)
            period: Time period for data
        
        Returns:
            Dictionary with portfolio metrics, or None if pipeline fails
        """
        logger.info("=" * 60)
        logger.info("STARTING PORTFOLIO ANALYSIS PIPELINE")
        logger.info("=" * 60)
        
        # Step 1: Fetch data
        data = self.fetch_market_data(symbols, period=period)
        if data is None:
            logger.error("Pipeline failed at data fetching stage")
            return None
        
        # Step 2: Clean data
        cleaned_data = self.clean_data(data)
        if cleaned_data is None:
            logger.error("Pipeline failed at data cleaning stage")
            return None
        
        # Step 3: Calculate metrics
        metrics = self.calculate_portfolio_metrics(cleaned_data, weights)
        if metrics is None:
            logger.error("Pipeline failed at metrics calculation stage")
            return None
        
        logger.info("=" * 60)
        logger.info("PORTFOLIO ANALYSIS PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
        return metrics
