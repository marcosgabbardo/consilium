"""Report generation utilities for analysis results."""

from consilium.core.models import ConsensusResult, AnalysisResult, AgentResponse


class AnalysisReporter:
    """Generates text reports from analysis results."""

    def generate_summary(self, result: ConsensusResult) -> str:
        """Generate a text summary of consensus result."""
        lines = [
            f"# Analysis Summary: {result.ticker}",
            f"",
            f"## Recommendation",
            f"Signal: {result.final_signal.value}",
            f"Confidence: {result.confidence.value}",
            f"Weighted Score: {result.weighted_score:.1f}",
            f"",
            f"## Vote Distribution",
            f"Buy Votes: {result.buy_votes}",
            f"Hold Votes: {result.hold_votes}",
            f"Sell Votes: {result.sell_votes}",
            f"Agreement: {result.agreement_ratio:.0%}",
            f"",
        ]

        if result.key_themes:
            lines.append("## Key Themes")
            for theme in result.key_themes:
                lines.append(f"- {theme}")
            lines.append("")

        if result.primary_risks:
            lines.append("## Primary Risks")
            for risk in result.primary_risks:
                lines.append(f"- {risk}")
            lines.append("")

        if result.dissenters:
            lines.append("## Dissenters")
            lines.append(f"The following agents disagreed: {', '.join(result.dissenters)}")
            lines.append("")

        lines.append("## Consensus Reasoning")
        lines.append(result.consensus_reasoning)

        return "\n".join(lines)

    def generate_detailed_report(self, result: ConsensusResult) -> str:
        """Generate a detailed report with all agent responses."""
        lines = [self.generate_summary(result)]

        lines.append("")
        lines.append("# Agent Responses")
        lines.append("")

        for response in result.agent_responses:
            lines.extend(self._format_agent_response(response))
            lines.append("")

        if result.specialist_reports:
            lines.append("# Specialist Reports")
            lines.append("")

            for report in result.specialist_reports:
                lines.append(f"## {report.specialist_name}")
                lines.append(f"Score: {report.score}/100")
                lines.append(f"Summary: {report.summary}")
                lines.append(f"Analysis: {report.analysis}")
                lines.append("")

        return "\n".join(lines)

    def _format_agent_response(self, response: AgentResponse) -> list[str]:
        """Format a single agent response."""
        lines = [
            f"## {response.agent_name}",
            f"Signal: {response.signal.value}",
            f"Confidence: {response.confidence.value}",
        ]

        if response.target_price:
            lines.append(f"Target Price: ${response.target_price}")

        if response.time_horizon:
            lines.append(f"Time Horizon: {response.time_horizon}")

        lines.append("")
        lines.append("### Reasoning")
        lines.append(response.reasoning)

        if response.key_factors:
            lines.append("")
            lines.append("### Key Factors")
            for factor in response.key_factors:
                lines.append(f"- {factor}")

        if response.risks:
            lines.append("")
            lines.append("### Risks")
            for risk in response.risks:
                lines.append(f"- {risk}")

        return lines

    def generate_full_report(self, result: AnalysisResult) -> str:
        """Generate a full report for multiple tickers."""
        lines = [
            f"# Consilium Analysis Report",
            f"",
            f"**Tickers Analyzed:** {', '.join(result.tickers)}",
            f"**Agents Used:** {result.agents_used}",
            f"**Execution Time:** {result.execution_time_seconds:.1f}s",
            f"**Generated:** {result.completed_at.isoformat()}",
            f"",
            "---",
            "",
        ]

        for consensus in result.results:
            lines.append(self.generate_detailed_report(consensus))
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)
