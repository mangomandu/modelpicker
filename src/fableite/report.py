"""MetricsReport construction (reporting only; never a pass/fail gate)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from .models import MetricsReport, RoutingDecision


def build_report(
    decisions: Sequence[RoutingDecision],
    routing_accuracy: Optional[float] = None,
) -> MetricsReport:
    """Summarize latency/cost over decisions. routing_accuracy is supplied only
    when expected labels exist (golden suite); a plain CLI run passes None.
    """
    latencies = sorted(d.latency for d in decisions)
    n = len(latencies)
    mean_ms = round(sum(latencies) / n * 1000.0, 4) if n else 0.0
    p95_ms = round(latencies[min(n - 1, int(0.95 * (n - 1)))] * 1000.0, 4) if n else 0.0

    by_model: dict[str, float] = {}
    total_cost = 0.0
    for d in decisions:
        key = d.selected_model.value
        by_model[key] = round(by_model.get(key, 0.0) + d.estimated_cost, 6)
        total_cost += d.estimated_cost

    return MetricsReport(
        routing_accuracy=routing_accuracy,
        latency_summary={"count": n, "mean_ms": mean_ms, "p95_ms": p95_ms},
        cost_summary={"total_estimated_cost": round(total_cost, 6), "by_model": by_model},
        n_cases=n,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
