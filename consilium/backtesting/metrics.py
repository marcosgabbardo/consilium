"""Financial metrics calculator for backtesting."""

import math
from decimal import Decimal
from statistics import mean, stdev

from consilium.backtesting.models import (
    BacktestMetrics,
    BacktestTrade,
    DailySnapshot,
    TradeAction,
)


class MetricsCalculator:
    """Calculates all financial metrics for backtesting."""

    # Annualization factor (trading days per year)
    TRADING_DAYS_PER_YEAR = 252

    # Default risk-free rate (annualized)
    DEFAULT_RISK_FREE_RATE = Decimal("0.04")  # 4%

    def __init__(self, risk_free_rate: Decimal | None = None):
        """Initialize with optional custom risk-free rate."""
        self.risk_free_rate = risk_free_rate or self.DEFAULT_RISK_FREE_RATE

    def calculate(
        self,
        initial_capital: Decimal,
        snapshots: list[DailySnapshot],
        trades: list[BacktestTrade],
    ) -> BacktestMetrics:
        """
        Calculate all metrics from simulation results.

        Args:
            initial_capital: Starting capital
            snapshots: Daily portfolio snapshots
            trades: List of executed trades

        Returns:
            BacktestMetrics with all calculated values
        """
        if not snapshots:
            return self._empty_metrics()

        # Extract values from snapshots
        portfolio_values = [float(s.portfolio_value) for s in snapshots]
        benchmark_values = [float(s.benchmark_value) for s in snapshots]
        drawdowns = [float(s.drawdown) for s in snapshots]

        # Calculate returns
        portfolio_returns = self._calculate_returns(portfolio_values)
        benchmark_returns = self._calculate_returns(benchmark_values)

        # Final values
        final_value = Decimal(str(portfolio_values[-1]))
        final_benchmark = Decimal(str(benchmark_values[-1]))

        # Total return
        total_return = final_value - initial_capital
        total_return_pct = (total_return / initial_capital) * Decimal("100") if initial_capital > 0 else Decimal("0")

        # Benchmark return
        benchmark_return = ((final_benchmark - initial_capital) / initial_capital) * Decimal("100") if initial_capital > 0 else Decimal("0")

        # Excess return
        excess_return = total_return_pct - benchmark_return

        # CAGR
        num_years = len(snapshots) / self.TRADING_DAYS_PER_YEAR
        cagr = self._calculate_cagr(initial_capital, final_value, Decimal(str(num_years)))

        # Alpha and Beta
        alpha, beta = self._calculate_alpha_beta(portfolio_returns, benchmark_returns)

        # Risk metrics
        sharpe = self._calculate_sharpe(portfolio_returns)
        sortino = self._calculate_sortino(portfolio_returns)
        max_dd, max_dd_duration = self._calculate_max_drawdown(drawdowns, snapshots)
        calmar = self._calculate_calmar(cagr, max_dd)
        var_95 = self._calculate_var(portfolio_returns, confidence=0.95)

        # Trade statistics
        trade_stats = self._calculate_trade_stats(trades)

        return BacktestMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            cagr=cagr,
            alpha=alpha,
            beta=beta,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            max_drawdown_duration_days=max_dd_duration,
            var_95=var_95,
            total_trades=trade_stats["total_trades"],
            winning_trades=trade_stats["winning_trades"],
            losing_trades=trade_stats["losing_trades"],
            win_rate=trade_stats["win_rate"],
            profit_factor=trade_stats["profit_factor"],
            avg_holding_days=trade_stats["avg_holding_days"],
            avg_win=trade_stats["avg_win"],
            avg_loss=trade_stats["avg_loss"],
            benchmark_return=benchmark_return,
            excess_return=excess_return,
        )

    def _calculate_returns(self, values: list[float]) -> list[float]:
        """Calculate daily returns from a list of values."""
        if len(values) < 2:
            return []
        returns = []
        for i in range(1, len(values)):
            if values[i - 1] != 0:
                ret = (values[i] - values[i - 1]) / values[i - 1]
                returns.append(ret)
        return returns

    def _calculate_cagr(
        self,
        initial: Decimal,
        final: Decimal,
        years: Decimal,
    ) -> Decimal:
        """Calculate Compound Annual Growth Rate."""
        if initial <= 0 or years <= 0:
            return Decimal("0")
        try:
            ratio = float(final / initial)
            years_f = float(years)
            cagr = (ratio ** (1 / years_f)) - 1
            return Decimal(str(cagr * 100))  # As percentage
        except (ValueError, ZeroDivisionError):
            return Decimal("0")

    def _calculate_sharpe(self, returns: list[float]) -> Decimal:
        """
        Calculate Sharpe Ratio.

        Sharpe = (Mean Return - Risk Free Rate) / Std Dev
        Annualized.
        """
        if len(returns) < 2:
            return Decimal("0")

        try:
            mean_return = mean(returns)
            std_return = stdev(returns)

            if std_return == 0:
                return Decimal("0")

            # Annualize
            daily_rf = float(self.risk_free_rate) / self.TRADING_DAYS_PER_YEAR
            excess_return = mean_return - daily_rf
            annualized_sharpe = (excess_return / std_return) * math.sqrt(self.TRADING_DAYS_PER_YEAR)

            return Decimal(str(round(annualized_sharpe, 4)))
        except (ValueError, ZeroDivisionError):
            return Decimal("0")

    def _calculate_sortino(self, returns: list[float]) -> Decimal:
        """
        Calculate Sortino Ratio.

        Sortino = (Mean Return - Risk Free Rate) / Downside Std Dev
        Only considers negative returns for risk.
        """
        if len(returns) < 2:
            return Decimal("0")

        try:
            mean_return = mean(returns)
            daily_rf = float(self.risk_free_rate) / self.TRADING_DAYS_PER_YEAR

            # Calculate downside deviation (only negative returns)
            downside_returns = [r for r in returns if r < daily_rf]
            if len(downside_returns) < 2:
                return Decimal("0")

            downside_std = stdev(downside_returns)
            if downside_std == 0:
                return Decimal("0")

            excess_return = mean_return - daily_rf
            annualized_sortino = (excess_return / downside_std) * math.sqrt(self.TRADING_DAYS_PER_YEAR)

            return Decimal(str(round(annualized_sortino, 4)))
        except (ValueError, ZeroDivisionError):
            return Decimal("0")

    def _calculate_max_drawdown(
        self,
        drawdowns: list[float],
        snapshots: list[DailySnapshot],
    ) -> tuple[Decimal, int]:
        """
        Calculate maximum drawdown and its duration.

        Returns:
            Tuple of (max_drawdown_pct, duration_days)
        """
        if not drawdowns:
            return Decimal("0"), 0

        max_dd = max(drawdowns)

        # Find duration of max drawdown
        duration = 0
        current_duration = 0
        in_drawdown = False

        for dd in drawdowns:
            if dd > 0:
                in_drawdown = True
                current_duration += 1
            else:
                if in_drawdown:
                    duration = max(duration, current_duration)
                    current_duration = 0
                    in_drawdown = False

        # Check if still in drawdown at end
        if in_drawdown:
            duration = max(duration, current_duration)

        return Decimal(str(max_dd * 100)), duration  # As percentage

    def _calculate_calmar(self, cagr: Decimal, max_drawdown: Decimal) -> Decimal:
        """
        Calculate Calmar Ratio.

        Calmar = CAGR / |Max Drawdown|
        """
        if max_drawdown == 0:
            return Decimal("0")
        return abs(cagr / max_drawdown)

    def _calculate_var(
        self,
        returns: list[float],
        confidence: float = 0.95,
    ) -> Decimal:
        """
        Calculate Value at Risk (VaR).

        Historical VaR at given confidence level.
        """
        if len(returns) < 10:
            return Decimal("0")

        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        var = sorted_returns[index]

        return Decimal(str(abs(var) * 100))  # As positive percentage

    def _calculate_alpha_beta(
        self,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate Alpha and Beta using CAPM regression.

        Beta = Cov(Rp, Rb) / Var(Rb)
        Alpha = Mean(Rp) - Beta * Mean(Rb)
        """
        if len(portfolio_returns) < 10 or len(benchmark_returns) < 10:
            return Decimal("0"), Decimal("1")

        # Ensure same length
        min_len = min(len(portfolio_returns), len(benchmark_returns))
        p_returns = portfolio_returns[:min_len]
        b_returns = benchmark_returns[:min_len]

        try:
            # Calculate means
            mean_p = mean(p_returns)
            mean_b = mean(b_returns)

            # Calculate covariance and variance
            covariance = sum((p - mean_p) * (b - mean_b) for p, b in zip(p_returns, b_returns)) / (min_len - 1)
            variance_b = sum((b - mean_b) ** 2 for b in b_returns) / (min_len - 1)

            if variance_b == 0:
                return Decimal("0"), Decimal("1")

            beta = covariance / variance_b

            # Annualize alpha
            daily_rf = float(self.risk_free_rate) / self.TRADING_DAYS_PER_YEAR
            alpha = (mean_p - daily_rf) - beta * (mean_b - daily_rf)
            annualized_alpha = alpha * self.TRADING_DAYS_PER_YEAR * 100  # As percentage

            return Decimal(str(round(annualized_alpha, 4))), Decimal(str(round(beta, 4)))
        except (ValueError, ZeroDivisionError):
            return Decimal("0"), Decimal("1")

    def _calculate_trade_stats(self, trades: list[BacktestTrade]) -> dict:
        """Calculate trade-related statistics."""
        sells = [t for t in trades if t.trade_type == TradeAction.SELL]
        buys = [t for t in trades if t.trade_type == TradeAction.BUY]

        if not sells:
            return {
                "total_trades": len(trades),
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": Decimal("0"),
                "profit_factor": Decimal("0"),
                "avg_holding_days": 0,
                "avg_win": Decimal("0"),
                "avg_loss": Decimal("0"),
            }

        # Win/loss analysis
        winning = [t for t in sells if t.realized_pnl and t.realized_pnl > 0]
        losing = [t for t in sells if t.realized_pnl and t.realized_pnl < 0]

        gross_profit = sum(t.realized_pnl for t in winning if t.realized_pnl) or Decimal("0")
        gross_loss = abs(sum(t.realized_pnl for t in losing if t.realized_pnl)) or Decimal("0")

        win_rate = Decimal(str(len(winning) / len(sells) * 100)) if sells else Decimal("0")
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal("0")

        avg_win = gross_profit / len(winning) if winning else Decimal("0")
        avg_loss = gross_loss / len(losing) if losing else Decimal("0")

        # Calculate average holding period
        # Match buys to sells by order
        holding_days = []
        for i, sell in enumerate(sells):
            if i < len(buys):
                days = (sell.trade_date - buys[i].trade_date).days
                holding_days.append(days)

        avg_holding = int(mean(holding_days)) if holding_days else 0

        return {
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_holding_days": avg_holding,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        }

    def _empty_metrics(self) -> BacktestMetrics:
        """Return empty metrics when no data is available."""
        return BacktestMetrics(
            total_return=Decimal("0"),
            total_return_pct=Decimal("0"),
            cagr=Decimal("0"),
            alpha=Decimal("0"),
            beta=Decimal("1"),
            sharpe_ratio=Decimal("0"),
            sortino_ratio=Decimal("0"),
            calmar_ratio=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_duration_days=0,
            var_95=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            profit_factor=Decimal("0"),
            avg_holding_days=0,
            avg_win=Decimal("0"),
            avg_loss=Decimal("0"),
            benchmark_return=Decimal("0"),
            excess_return=Decimal("0"),
        )
