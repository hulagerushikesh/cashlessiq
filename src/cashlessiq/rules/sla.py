"""Deterministic pre-authorisation SLA status."""

from __future__ import annotations

from datetime import datetime

from .models import SlaState, SlaStatus


def sla_status(received_at: datetime, now: datetime) -> SlaStatus:
    """Return the one-hour SLA state; amber starts at 30 and red at 45 minutes."""

    if received_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("SLA timestamps must be timezone-aware")
    elapsed = max(int((now - received_at).total_seconds() // 60), 0)
    if elapsed >= 45:
        state = SlaState.RED
    elif elapsed >= 30:
        state = SlaState.AMBER
    else:
        state = SlaState.GREEN
    return SlaStatus(
        received_at=received_at,
        elapsed_min=elapsed,
        remaining_min=max(60 - elapsed, 0),
        state=state,
    )
