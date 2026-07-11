"""
Generic gap lifecycle tracker.

Tracks when a keyed condition opens, how long it stays open, and when it closes.
Callers supply plain observations; this module has no exchange or orderbook dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class GapObservation:
    """
    One sample of whether a named gap is currently open.

    :var key: Stable identifier for the gap (e.g. "kalshi_id|poly_id").
    :var is_open: True when the monitored condition is present.
    :var timestamp: Observation time in UTC.
    :var payload: Arbitrary fields to carry through to emitted events / CSV rows.
    """

    key: str
    is_open: bool
    timestamp: datetime = field(default_factory=utc_now)
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class GapEvent:
    """
    Lifecycle event emitted when a gap opens, updates, or closes.

    :var event: One of "opened", "updated", "closed".
    :var key: Gap key from the observation.
    :var gap_id: Stable ID for this open→close episode.
    :var timestamp: Event time in UTC.
    :var opened_at: When this episode started.
    :var duration_seconds: Seconds since opened_at.
    :var payload: Snapshot fields from the latest observation.
    """

    event: str
    key: str
    gap_id: str
    timestamp: datetime
    opened_at: datetime
    duration_seconds: float
    payload: Mapping[str, Any]


@dataclass
class _OpenGap:
    gap_id: str
    opened_at: datetime
    last_payload: Mapping[str, Any]


class GapTracker:
    """
    Track open/update/close transitions for keyed gaps.

    Useful for arbitrage spreads, inventory imbalances, or any other
    condition you want to time and log independently of trading logic.
    """

    def __init__(self, update_on_change_only: bool = False):
        """
        :param update_on_change_only: If True, emit "updated" only when payload values change.
            If False, emit "updated" on every observation while the gap remains open.
        """
        self.update_on_change_only = update_on_change_only
        self._open: dict[str, _OpenGap] = {}

    def observe(self, observation: GapObservation) -> Optional[GapEvent]:
        """
        Ingest one observation and return a lifecycle event when one should be recorded.
        """
        existing = self._open.get(observation.key)
        timestamp = observation.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if observation.is_open:
            if existing is None:
                gap_id = str(uuid.uuid4())
                self._open[observation.key] = _OpenGap(
                    gap_id=gap_id,
                    opened_at=timestamp,
                    last_payload=dict(observation.payload),
                )
                return GapEvent(
                    event="opened",
                    key=observation.key,
                    gap_id=gap_id,
                    timestamp=timestamp,
                    opened_at=timestamp,
                    duration_seconds=0.0,
                    payload=dict(observation.payload),
                )

            if self.update_on_change_only and dict(observation.payload) == dict(existing.last_payload):
                return None

            existing.last_payload = dict(observation.payload)
            duration = (timestamp - existing.opened_at).total_seconds()
            return GapEvent(
                event="updated",
                key=observation.key,
                gap_id=existing.gap_id,
                timestamp=timestamp,
                opened_at=existing.opened_at,
                duration_seconds=duration,
                payload=dict(observation.payload),
            )

        if existing is None:
            return None

        duration = (timestamp - existing.opened_at).total_seconds()
        event = GapEvent(
            event="closed",
            key=observation.key,
            gap_id=existing.gap_id,
            timestamp=timestamp,
            opened_at=existing.opened_at,
            duration_seconds=duration,
            payload=dict(observation.payload) if observation.payload else dict(existing.last_payload),
        )
        del self._open[observation.key]
        return event

    def open_gaps(self) -> Mapping[str, _OpenGap]:
        """Return a read-only view of currently open gaps."""
        return dict(self._open)
