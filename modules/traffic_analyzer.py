"""
modules/traffic_analyzer.py
────────────────────────────
Converts raw vehicle counts into traffic density classifications
and recommends traffic-signal timings.

Density classification
  LOW    : total ≤ DENSITY_LOW_MAX
  MEDIUM : total ≤ DENSITY_MEDIUM_MAX
  HIGH   : total > DENSITY_MEDIUM_MAX

Signal timing recommendations are advisory only.
They must NOT be used to directly control physical signal hardware
without authorisation from the relevant road authority.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List

from config import Config


# ─── Data classes ─────────────────────────────────────────────────────────

@dataclass
class DensityResult:
    camera_id: str
    total_vehicles: int
    counts: Dict[str, int]
    density_score: float          # vehicles per unit (0.0 – 1.0 normalised)
    density_label: str            # "LOW" | "MEDIUM" | "HIGH"
    signal_timing: Dict[str, int] # {"green": N, "yellow": N, "red": N}
    timestamp: float = field(default_factory=time.time)

    @property
    def density_colour(self) -> str:
        return {"LOW": "#00c853", "MEDIUM": "#ffd600", "HIGH": "#f44336"}.get(
            self.density_label, "#aaa"
        )


@dataclass
class HistoryEntry:
    timestamp: float
    total: int
    label: str


# ─── Analyzer ─────────────────────────────────────────────────────────────

class TrafficAnalyzer:
    """
    Maintains a rolling history of vehicle counts per camera and
    produces density + signal-timing recommendations.

    Parameters
    ----------
    history_len : int
        Number of readings to keep in the rolling window (for trend display).
    """

    def __init__(self, history_len: int = 60):
        self._history: Dict[str, List[HistoryEntry]] = {}
        self._history_len = history_len

    # ── Public API ─────────────────────────────────────────────────────────

    def analyze(
        self,
        camera_id: str,
        total_vehicles: int,
        counts: Dict[str, int],
    ) -> DensityResult:
        """
        Analyse one frame's vehicle count and return a DensityResult.
        """
        label = self._classify(total_vehicles)
        timing = Config.SIGNAL_TIMINGS[label].copy()
        score = self._normalise(total_vehicles)

        result = DensityResult(
            camera_id=camera_id,
            total_vehicles=total_vehicles,
            counts=counts,
            density_score=score,
            density_label=label,
            signal_timing=timing,
        )

        # Rolling history
        hist = self._history.setdefault(camera_id, [])
        hist.append(HistoryEntry(timestamp=result.timestamp, total=total_vehicles, label=label))
        if len(hist) > self._history_len:
            hist.pop(0)

        return result

    def get_history(self, camera_id: str) -> List[HistoryEntry]:
        return list(self._history.get(camera_id, []))

    def get_all_summaries(self) -> Dict[str, dict]:
        """
        Return the latest density result for every camera that has
        been processed at least once.
        """
        summaries: Dict[str, dict] = {}
        for cam_id, hist in self._history.items():
            if hist:
                latest = hist[-1]
                summaries[cam_id] = {
                    "total": latest.total,
                    "label": latest.label,
                    "timestamp": latest.timestamp,
                    "signal": Config.SIGNAL_TIMINGS[latest.label],
                }
        return summaries

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _classify(total: int) -> str:
        if total <= Config.DENSITY_LOW_MAX:
            return "LOW"
        elif total <= Config.DENSITY_MEDIUM_MAX:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def _normalise(total: int) -> float:
        """Map vehicle count to 0.0–1.0 for UI progress bars."""
        ceiling = Config.DENSITY_MEDIUM_MAX * 2  # treat 2× medium as 100 %
        return min(total / ceiling, 1.0)

    # ── Utility ────────────────────────────────────────────────────────────

    @staticmethod
    def format_signal(timing: Dict[str, int]) -> str:
        return (
            f"🟢 Green {timing['green']}s  "
            f"🟡 Yellow {timing['yellow']}s  "
            f"🔴 Red {timing['red']}s"
        )


# ─── Smoke-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    analyzer = TrafficAnalyzer()
    for count in [3, 10, 20]:
        r = analyzer.analyze("cam_test", count, {"car": count})
        print(
            f"count={count:>2}  density={r.density_label:<6}  "
            f"green={r.signal_timing['green']}s"
        )
