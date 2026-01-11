"""
AI Agent - Atlas: Advanced Portfolio Analyst
Uses Groq's LLM to provide sophisticated financial insights from quantitative metrics.
"""

import os
import logging
from typing import Dict, Optional, List
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AtlasAgent:
    """
    Atlas - Advanced Portfolio Analyst AI Agent
    
    Atlas is a sophisticated financial analyst persona that interprets complex
    quantitative metrics and provides actionable insights, with special expertise
    in tail risk, distribution analysis, and portfolio optimization.
    """
    
    def __init__(self, model: str = None):
        """
        Initialize Atlas AI Agent.
        
        Args:
            model: Groq model to use. If None, will try best available models.
        """
        logger.info("Initializing Atlas AI Agent...")
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables. Please set it in .env file.")
        
        self.client = Groq(api_key=api_key)
        
        # Try to find available model
        if model:
            self.model = model
        else:
            # Try models in order of preference (best reasoning first)
            available_models = [
                "llama-3.3-70b-versatile",
                "llama-3.1-70b-versatile", 
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768"
            ]
            
            self.model = None
            for test_model in available_models:
                try:
                    # Quick test call
                    test_response = self.client.chat.completions.create(
                        model=test_model,
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=1
                    )
                    self.model = test_model
                    logger.info(f"Found available model: {test_model}")
                    break
                except Exception as e:
                    logger.debug(f"Model {test_model} not available: {str(e)}")
                    continue
            
            if not self.model:
                # Default fallback
                self.model = "llama-3.1-8b-instant"
                logger.warning(f"Could not verify model availability, using default: {self.model}")
        
        logger.info(f"Atlas Agent initialized with model: {self.model}")
    
    def _build_analysis_prompt(self, metrics: Dict, symbols: List[str], weights: Optional[List[float]] = None) -> str:
        """
        Build a sophisticated prompt that groups metrics logically and emphasizes tail risk.
        
        Args:
            metrics: Dictionary with all portfolio metrics from quant_engine
            symbols: List of asset symbols
            weights: Portfolio weights
        
        Returns:
            Formatted prompt string
        """
        
        # Extract metrics by category
        basic_metrics = {
            "annual_return": metrics.get("annual_return"),
            "volatility": metrics.get("volatility"),
            "sharpe_ratio": metrics.get("sharpe_ratio"),
            "start_date": metrics.get("start_date"),
            "end_date": metrics.get("end_date")
        }
        
        risk_metrics = {
            "max_drawdown": metrics.get("max_drawdown"),
            "var_95_annualized": metrics.get("var_95_annualized"),
            "var_99_annualized": metrics.get("var_99_annualized"),
            "cvar_95_annualized": metrics.get("cvar_95_annualized"),
            "cvar_99_annualized": metrics.get("cvar_99_annualized"),
            "downside_deviation": metrics.get("downside_deviation"),
            "worst_day": metrics.get("worst_day")
        }
        
        performance_metrics = {
            "sortino_ratio": metrics.get("sortino_ratio"),
            "calmar_ratio": metrics.get("calmar_ratio"),
            "win_rate": metrics.get("win_rate"),
            "best_day": metrics.get("best_day"),
            "median_daily_return": metrics.get("median_daily_return")
        }
        
        distribution_metrics = {
            "skewness": metrics.get("skewness"),
            "kurtosis": metrics.get("kurtosis"),
            "return_std": metrics.get("return_std")
        }
        
        diversification_metrics = {
            "avg_correlation": metrics.get("avg_correlation"),
            "min_correlation": metrics.get("min_correlation"),
            "max_correlation": metrics.get("max_correlation"),
            "concentration_hhi": metrics.get("concentration_hhi"),
            "concentration_ratio": metrics.get("concentration_ratio"),
            "beta": metrics.get("beta")
        }
        
        optimization_metrics = {
            "min_variance_volatility": metrics.get("min_variance_volatility"),
            "min_variance_return": metrics.get("min_variance_return"),
            "volatility_improvement_potential": metrics.get("volatility_improvement_potential")
        }
        
        # Build weights string
        if weights:
            weights_str = ", ".join([f"{symbol}: {w*100:.1f}%" for symbol, w in zip(symbols, weights)])
        else:
            weights_str = "Equal weights"
        
        prompt = f"""You are Atlas, an elite quantitative portfolio analyst at a top-tier Wall Street firm. You specialize in identifying hidden risks that standard models miss, particularly tail risk and distribution asymmetries.

PORTFOLIO COMPOSITION:
Assets: {', '.join(symbols)}
Weights: {weights_str}
Analysis Period: {basic_metrics['start_date']} to {basic_metrics['end_date']}

═══════════════════════════════════════════════════════════════
📊 BASIC PERFORMANCE METRICS
═══════════════════════════════════════════════════════════════
Annual Return: {basic_metrics['annual_return']}%
Volatility (Std Dev): {basic_metrics['volatility']}%
Sharpe Ratio: {basic_metrics['sharpe_ratio']}

═══════════════════════════════════════════════════════════════
⚠️ RISK METRICS (CRITICAL ANALYSIS REQUIRED)
═══════════════════════════════════════════════════════════════
Maximum Drawdown: {risk_metrics['max_drawdown']}%
Value at Risk (95% confidence, annualized): {risk_metrics['var_95_annualized']}%
Value at Risk (99% confidence, annualized): {risk_metrics['var_99_annualized']}%
Conditional VaR / Expected Shortfall (95%): {risk_metrics['cvar_95_annualized']}%
Conditional VaR / Expected Shortfall (99%): {risk_metrics['cvar_99_annualized']}%
Downside Deviation: {risk_metrics['downside_deviation']}%
Worst Single Day Loss: {risk_metrics['worst_day']}%

═══════════════════════════════════════════════════════════════
📈 RISK-ADJUSTED PERFORMANCE METRICS
═══════════════════════════════════════════════════════════════
Sortino Ratio: {performance_metrics['sortino_ratio']} (penalizes only downside volatility)
Calmar Ratio: {performance_metrics['calmar_ratio']} (return / max drawdown)
Win Rate: {performance_metrics['win_rate']}% of trading days were positive
Best Single Day Gain: +{performance_metrics['best_day']}%
Median Daily Return: {performance_metrics['median_daily_return']}%

═══════════════════════════════════════════════════════════════
🔍 DISTRIBUTION ANALYSIS (TAIL RISK - YOUR SPECIALTY)
═══════════════════════════════════════════════════════════════
⚠️ CRITICAL: Pay special attention to these metrics - they reveal hidden risks:

Skewness: {distribution_metrics['skewness']}
  → Interpretation: 
    • Positive (>0.5): Right tail (good surprises possible, but left tail risk exists)
    • Negative (<-0.5): LEFT TAIL RISK - More frequent large losses than gains (RED FLAG)
    • Near zero (-0.5 to 0.5): Relatively symmetric distribution

Kurtosis: {distribution_metrics['kurtosis']}
  → Interpretation:
    • Normal distribution = 0 (excess kurtosis)
    • >3: FAT TAILS - Extreme events occur more frequently than normal distribution predicts
    • >5: VERY FAT TAILS - Significant tail risk, portfolio vulnerable to black swan events
    • <0: Thin tails (less extreme events than normal)

Daily Return Standard Deviation: {distribution_metrics['return_std']}%

ANALYSIS REQUIRED:
1. Assess tail risk: What does the combination of Skewness and Kurtosis tell you about the probability of extreme losses?
2. Asymmetry analysis: Is the portfolio more vulnerable to sudden crashes than its volatility suggests?
3. Hidden risks: Are there distribution characteristics that standard metrics (Sharpe, Volatility) are masking?

═══════════════════════════════════════════════════════════════
🔗 DIVERSIFICATION ANALYSIS
═══════════════════════════════════════════════════════════════
Average Correlation Between Assets: {diversification_metrics['avg_correlation']}
Correlation Range: [{diversification_metrics['min_correlation']}, {diversification_metrics['max_correlation']}]
Portfolio Concentration (HHI): {diversification_metrics['concentration_hhi']} (lower = more diversified)
Concentration vs Equal-Weight: {diversification_metrics['concentration_ratio']}x
Beta vs S&P 500: {diversification_metrics['beta'] if diversification_metrics['beta'] else 'N/A'} (1.0 = market, >1 = more volatile)

═══════════════════════════════════════════════════════════════
⚡ OPTIMIZATION OPPORTUNITIES
═══════════════════════════════════════════════════════════════
Minimum Variance Portfolio Volatility: {optimization_metrics.get('min_variance_volatility', 'N/A')}%
Minimum Variance Portfolio Return: {optimization_metrics.get('min_variance_return', 'N/A')}%
Potential Volatility Reduction: {optimization_metrics.get('volatility_improvement_potential', 'N/A')}%

═══════════════════════════════════════════════════════════════
YOUR ANALYSIS TASK
═══════════════════════════════════════════════════════════════

Provide a comprehensive analysis in the following structure:

1. EXECUTIVE SUMMARY (2-3 sentences)
   - Overall portfolio health and key takeaway

2. RISK ASSESSMENT (Focus heavily here)
   - Tail Risk Analysis: Deep dive into Skewness and Kurtosis implications
   - Maximum Drawdown interpretation: Can the investor stomach this?
   - VaR/CVaR Analysis: What are the worst-case scenarios?
   - Asymmetry Warning: Are there hidden risks that volatility doesn't capture?

3. PERFORMANCE EVALUATION
   - Risk-adjusted returns (Sharpe, Sortino, Calmar)
   - Consistency (Win Rate, Median Return)
   - Comparison to risk-free rate and market (Beta)

4. DIVERSIFICATION QUALITY
   - Is the portfolio truly diversified or just a collection of correlated assets?
   - Concentration risk assessment

5. ACTIONABLE RECOMMENDATIONS
   - Specific, actionable advice based on the metrics
   - Optimization opportunities
   - Risk mitigation strategies if tail risk is high

IMPORTANT GUIDELINES:
- Write in clear, professional English suitable for sophisticated investors
- Use specific numbers from the metrics to support your analysis
- Pay EXTRA attention to tail risk (Skewness < -0.5 or Kurtosis > 5 = warning flags)
- Don't just describe metrics - interpret what they mean for an investor
- Be direct about risks - if tail risk is high, say so clearly
- Provide context: compare metrics to industry benchmarks where relevant

Begin your analysis:"""
        
        return prompt
    
    def analyze_portfolio(
        self,
        metrics: Dict,
        symbols: List[str],
        weights: Optional[List[float]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, str]:
        """
        Generate comprehensive portfolio analysis using Atlas AI agent.
        
        Args:
            metrics: Dictionary with portfolio metrics from quant_engine
            symbols: List of asset symbols analyzed
            weights: Portfolio weights (optional)
            temperature: Model temperature (0.0-1.0, lower = more focused)
            max_tokens: Maximum response length
        
        Returns:
            Dictionary with analysis sections
        """
        logger.info("=" * 60)
        logger.info("ATLAS AI AGENT - STARTING PORTFOLIO ANALYSIS")
        logger.info("=" * 60)
        logger.info(f"Analyzing portfolio: {', '.join(symbols)}")
        
        try:
            # Build sophisticated prompt
            logger.info("Building analysis prompt with advanced metrics...")
            prompt = self._build_analysis_prompt(metrics, symbols, weights)
            
            # Call Groq API
            logger.info(f"Calling Groq API (model: {self.model})...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are Atlas, an elite quantitative portfolio analyst. You excel at identifying tail risks, distribution asymmetries, and hidden portfolio vulnerabilities that standard metrics miss. You provide clear, actionable insights backed by data."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9
            )
            
            # Extract response
            analysis_text = response.choices[0].message.content
            logger.info(f"Received analysis ({len(analysis_text)} characters)")
            
            # Parse response into structured sections (if possible)
            # For now, return as single analysis
            result = {
                "analysis": analysis_text,
                "model": self.model,
                "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None
            }
            
            logger.info("=" * 60)
            logger.info("ATLAS AI AGENT - ANALYSIS COMPLETE")
            logger.info("=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Atlas AI analysis: {str(e)}", exc_info=True)
            return {
                "error": str(e),
                "analysis": "Failed to generate analysis. Please check logs."
            }
    
    def generate_insights_summary(
        self,
        metrics: Dict,
        symbols: List[str],
        weights: Optional[List[float]] = None
    ) -> str:
        """
        Generate a concise insights summary (shorter than full analysis).
        
        Args:
            metrics: Portfolio metrics
            symbols: Asset symbols
            weights: Portfolio weights
        
        Returns:
            Concise summary string
        """
        logger.info("Generating concise insights summary...")
        
        # Build shorter prompt for summary
        prompt = f"""You are Atlas, a quantitative portfolio analyst. Provide a concise 3-paragraph summary:

Portfolio: {', '.join(symbols)}
Key Metrics:
- Return: {metrics.get('annual_return')}%, Volatility: {metrics.get('volatility')}%, Sharpe: {metrics.get('sharpe_ratio')}
- Max Drawdown: {metrics.get('max_drawdown')}%
- Tail Risk: Skewness={metrics.get('skewness')}, Kurtosis={metrics.get('kurtosis')}
- VaR (95%): {metrics.get('var_95_annualized')}%

Write 3 paragraphs:
1. Overall assessment (1-2 sentences)
2. Key risk concerns, especially tail risk if Skewness < -0.5 or Kurtosis > 5
3. One actionable recommendation

Be direct and specific."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are Atlas, a concise financial analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Summary generation failed: {str(e)}"
