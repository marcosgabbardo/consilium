"""Export utilities for analysis results."""

import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from consilium.core.models import AnalysisResult, ConsensusResult
from consilium.analysis.reporter import AnalysisReporter


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class JSONExporter:
    """Export results to JSON format."""

    def export(self, result: AnalysisResult, file_path: str | Path) -> None:
        """Export analysis result to JSON file."""
        data = result.model_dump()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=DecimalEncoder, indent=2)

    def export_consensus(self, result: ConsensusResult, file_path: str | Path) -> None:
        """Export single consensus result to JSON file."""
        data = result.model_dump()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=DecimalEncoder, indent=2)

    def to_string(self, result: AnalysisResult) -> str:
        """Convert analysis result to JSON string."""
        data = result.model_dump()
        return json.dumps(data, cls=DecimalEncoder, indent=2)


class CSVExporter:
    """Export results to CSV format."""

    def export(self, result: AnalysisResult, file_path: str | Path) -> None:
        """Export analysis result to CSV file."""
        rows = []

        for consensus in result.results:
            for response in consensus.agent_responses:
                rows.append({
                    "ticker": consensus.ticker,
                    "consensus_signal": consensus.final_signal.value,
                    "consensus_score": float(consensus.weighted_score),
                    "consensus_confidence": consensus.confidence.value,
                    "agent_id": response.agent_id,
                    "agent_name": response.agent_name,
                    "agent_signal": response.signal.value,
                    "agent_confidence": response.confidence.value,
                    "target_price": float(response.target_price) if response.target_price else "",
                    "time_horizon": response.time_horizon or "",
                    "reasoning": response.reasoning[:200],  # Truncate for CSV
                    "analyzed_at": response.analyzed_at.isoformat(),
                })

        if not rows:
            return

        fieldnames = list(rows[0].keys())

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def export_summary(self, result: AnalysisResult, file_path: str | Path) -> None:
        """Export summary-only CSV (one row per ticker)."""
        rows = []

        for consensus in result.results:
            rows.append({
                "ticker": consensus.ticker,
                "signal": consensus.final_signal.value,
                "confidence": consensus.confidence.value,
                "score": float(consensus.weighted_score),
                "buy_votes": consensus.buy_votes,
                "hold_votes": consensus.hold_votes,
                "sell_votes": consensus.sell_votes,
                "agreement": float(consensus.agreement_ratio),
                "dissenters": ", ".join(consensus.dissenters),
                "key_themes": "; ".join(consensus.key_themes[:3]),
                "primary_risks": "; ".join(consensus.primary_risks[:3]),
                "generated_at": consensus.generated_at.isoformat(),
            })

        if not rows:
            return

        fieldnames = list(rows[0].keys())

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


class MarkdownExporter:
    """Export results to Markdown format."""

    def __init__(self) -> None:
        self._reporter = AnalysisReporter()

    def export(self, result: AnalysisResult, file_path: str | Path) -> None:
        """Export analysis result to Markdown file."""
        content = self._reporter.generate_full_report(result)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def export_consensus(self, result: ConsensusResult, file_path: str | Path) -> None:
        """Export single consensus result to Markdown file."""
        content = self._reporter.generate_detailed_report(result)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def to_string(self, result: AnalysisResult) -> str:
        """Convert analysis result to Markdown string."""
        return self._reporter.generate_full_report(result)


def export_result(
    result: AnalysisResult,
    file_path: str | Path,
    format: str = "json",
) -> None:
    """
    Export analysis result to file.

    Args:
        result: Analysis result to export
        file_path: Output file path
        format: Export format ('json', 'csv', 'md')
    """
    format = format.lower()

    if format == "json":
        JSONExporter().export(result, file_path)
    elif format == "csv":
        CSVExporter().export(result, file_path)
    elif format in ("md", "markdown"):
        MarkdownExporter().export(result, file_path)
    else:
        raise ValueError(f"Unknown export format: {format}")
