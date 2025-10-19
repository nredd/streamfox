"""Type definitions for streamfox."""

from dataclasses import dataclass, field
from datetime import datetime

# Common type aliases (Python 3.12+ syntax)
type URL = str
type StreamURL = str

# Quality scoring constants
LATENCY_EXCELLENT_MS = 1000
LATENCY_GOOD_MS = 2000
LATENCY_POOR_MS = 3000
FPS_EXCELLENT = 24
FPS_GOOD = 15
FPS_MINIMUM = 10


@dataclass
class StreamQualityMetrics:
    """Quality metrics for a stream at a point in time.

    Attributes:
        url: The stream URL being measured.
        timestamp: When the metrics were collected.
        latency_ms: HTTP response time in milliseconds.
        fps: Measured frames per second.
        is_active: Whether the stream is delivering new frames.
        http_status: HTTP status code from health check.
        buffering_detected: Whether buffering/frozen frames detected.
        error_count: Number of consecutive errors encountered.
    """

    url: StreamURL
    timestamp: datetime = field(default_factory=datetime.now)
    latency_ms: float | None = None
    fps: float | None = None
    is_active: bool = True
    http_status: int | None = None
    buffering_detected: bool = False
    error_count: int = 0

    @property
    def quality_score(self) -> float:
        """Calculate a quality score from 0.0 (worst) to 1.0 (best).

        Scoring criteria:
        - Latency: 0.4 weight (faster is better)
        - FPS: 0.3 weight (higher is better)
        - Activity: 0.2 weight (active vs frozen)
        - Errors: 0.1 weight (fewer is better)
        """
        score = 0.0

        # Latency score (target: < 1000ms excellent, > 3000ms poor)
        if self.latency_ms is not None:
            if self.latency_ms < LATENCY_EXCELLENT_MS:
                latency_score = 1.0
            elif self.latency_ms < LATENCY_GOOD_MS:
                latency_score = 0.7
            elif self.latency_ms < LATENCY_POOR_MS:
                latency_score = 0.4
            else:
                latency_score = 0.1
            score += latency_score * 0.4

        # FPS score (target: > 24fps excellent, < 10fps poor)
        if self.fps is not None:
            if self.fps >= FPS_EXCELLENT:
                fps_score = 1.0
            elif self.fps >= FPS_GOOD:
                fps_score = 0.7
            elif self.fps >= FPS_MINIMUM:
                fps_score = 0.4
            else:
                fps_score = 0.1
            score += fps_score * 0.3

        # Activity score
        activity_score = 1.0 if self.is_active and not self.buffering_detected else 0.0
        score += activity_score * 0.2

        # Error score
        error_score = max(0.0, 1.0 - (self.error_count * 0.2))
        score += error_score * 0.1

        return min(1.0, max(0.0, score))

    def is_healthy(self, thresholds: "QualityThresholds") -> bool:
        """Check if metrics meet minimum quality thresholds."""
        if not self.is_active:
            return False

        if self.buffering_detected:
            return False

        if self.error_count >= thresholds.max_consecutive_errors:
            return False

        if self.latency_ms is not None and self.latency_ms > thresholds.max_latency_ms:
            return False

        return not (self.fps is not None and self.fps < thresholds.min_fps)


@dataclass
class QualityThresholds:
    """Thresholds for determining stream quality health.

    Attributes:
        max_latency_ms: Maximum acceptable latency in milliseconds.
        min_fps: Minimum acceptable frames per second.
        max_consecutive_errors: Max errors before marking unhealthy.
        quality_check_interval_seconds: How often to check quality during playback.
        switch_threshold_score: Minimum score difference to trigger switch.
    """

    max_latency_ms: float = 3000.0
    min_fps: float = 5.0
    max_consecutive_errors: int = 3
    quality_check_interval_seconds: float = 10.0
    switch_threshold_score: float = 0.3  # Switch if better stream is 0.3+ higher score
