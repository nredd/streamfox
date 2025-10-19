"""Real-time playback quality monitoring for active streams."""

import logging
import threading
import time
from collections.abc import Callable

import cv2
import numpy as np
import requests

from .types import QualityThresholds, StreamQualityMetrics, StreamURL

logger = logging.getLogger(__name__)

# Buffering detection threshold
MAX_IDENTICAL_FRAMES_FOR_BUFFERING = 3


class PlaybackMonitor:
    """
    Monitors a single active stream's playback quality in real-time.

    Runs quality checks in a background thread without blocking the player.
    Collects latency, FPS, and activity metrics and notifies on quality changes.

    Attributes:
        url: The stream URL being monitored.
        thresholds: Quality thresholds for health checks.
        check_interval: Seconds between quality checks.
        on_quality_change: Callback when quality metrics update.
        current_metrics: Latest quality metrics collected.
    """

    def __init__(
        self,
        url: StreamURL,
        thresholds: QualityThresholds | None = None,
        check_interval: float = 10.0,
        on_quality_change: Callable[[StreamQualityMetrics], None] | None = None,
    ) -> None:
        """
        Initialize the playback monitor.

        Args:
            url: Stream URL to monitor.
            thresholds: Quality thresholds (uses defaults if None).
            check_interval: Seconds between checks (default: 10.0).
            on_quality_change: Callback invoked with new metrics.
        """
        self.url = url
        self.thresholds = thresholds or QualityThresholds()
        self.check_interval = check_interval
        self.on_quality_change = on_quality_change

        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.current_metrics: StreamQualityMetrics | None = None

    def start(self) -> None:
        """Start monitoring in a background thread."""
        with self._lock:
            if self._monitoring:
                logger.warning("Monitoring already started for %s", self.url)
                return

            self._monitoring = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name=f"PlaybackMonitor-{self.url[:30]}",
            )
            self._monitor_thread.start()
            logger.info("Started playback monitoring for %s", self.url)

    def stop(self) -> None:
        """Stop monitoring and wait for thread to finish."""
        with self._lock:
            if not self._monitoring:
                return

            self._monitoring = False

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
            logger.info("Stopped playback monitoring for %s", self.url)

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self._monitoring:
            try:
                metrics = self._collect_metrics()

                with self._lock:
                    self.current_metrics = metrics

                # Notify callback if registered
                if self.on_quality_change:
                    try:
                        self.on_quality_change(metrics)
                    except Exception:
                        logger.exception("Error in quality change callback")

                # Log quality status
                if metrics.is_healthy(self.thresholds):
                    logger.info(
                        "Stream quality: %.2f (latency: %.0fms, fps: %.1f)",
                        metrics.quality_score,
                        metrics.latency_ms or 0,
                        metrics.fps or 0,
                    )
                else:
                    logger.warning(
                        "Stream quality degraded: %.2f (latency: %.0fms, fps: %.1f, active: %s)",
                        metrics.quality_score,
                        metrics.latency_ms or 0,
                        metrics.fps or 0,
                        metrics.is_active,
                    )

            except Exception:
                logger.exception("Error collecting metrics for %s", self.url)

            # Sleep for check interval (with early exit check)
            for _ in range(int(self.check_interval * 10)):
                if not self._monitoring:
                    break
                time.sleep(0.1)

    def _collect_metrics(self) -> StreamQualityMetrics:
        """
        Collect all quality metrics for the current stream.

        Returns:
            StreamQualityMetrics with current measurements.
        """
        metrics = StreamQualityMetrics(url=self.url)

        # Check latency
        latency_ms, http_status = self._check_latency()
        metrics.latency_ms = latency_ms
        metrics.http_status = http_status

        # Check FPS and buffering
        fps, buffering = self._check_fps()
        metrics.fps = fps
        metrics.buffering_detected = buffering

        # Check stream activity (only if previous checks didn't fail)
        if latency_ms is not None and fps is not None:
            metrics.is_active = self._is_stream_active()
        else:
            metrics.is_active = False
            metrics.error_count += 1

        return metrics

    def _check_latency(self, timeout: float = 5.0) -> tuple[float | None, int | None]:
        """
        Check the response time of the stream.

        Args:
            timeout: Maximum time to wait for response.

        Returns:
            Tuple of (latency_ms, http_status_code). Returns (None, None) on error.
        """
        try:
            start_time = time.time()
            response = requests.get(self.url, stream=True, timeout=timeout)
            latency = time.time() - start_time
            return (latency * 1000, response.status_code)  # Convert to milliseconds
        except requests.RequestException as e:
            logger.debug("Latency check failed for %s: %s", self.url, e)
            return (None, None)

    def _is_stream_active(
        self,
        check_duration: int = 3,
        motion_threshold: float = 5000,
    ) -> bool:
        """
        Check if stream is delivering new frames with motion.

        Args:
            check_duration: How long to check in seconds.
            motion_threshold: Minimum pixel difference for motion detection.

        Returns:
            True if stream shows motion, False otherwise.
        """
        cap = cv2.VideoCapture(self.url)
        if not cap.isOpened():
            logger.debug("Failed to open stream for activity check: %s", self.url)
            return False

        prev_frame: np.ndarray | None = None
        active = False
        start_time = time.time()

        try:
            while time.time() - start_time < check_duration and self._monitoring:
                ret, frame = cap.read()
                if not ret:
                    break

                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if prev_frame is not None:
                    diff = float(np.sum(cv2.absdiff(prev_frame, gray_frame)))
                    if diff > motion_threshold:
                        active = True
                        break

                prev_frame = gray_frame
                time.sleep(0.5)  # Check every 0.5s instead of 1s for faster detection
        except Exception as e:
            logger.debug("Activity check error for %s: %s", self.url, e)
        finally:
            cap.release()

        return active

    def _check_fps(self, check_duration: int = 3) -> tuple[float | None, bool]:
        """
        Measure FPS and detect buffering/frozen frames.

        Args:
            check_duration: How long to measure in seconds.

        Returns:
            Tuple of (fps, buffering_detected). Returns (None, True) on error.
        """
        cap = cv2.VideoCapture(self.url)
        if not cap.isOpened():
            logger.debug("Failed to open stream for FPS check: %s", self.url)
            return (None, True)

        frame_count = 0
        identical_frame_count = 0
        prev_frame: np.ndarray | None = None
        start_time = time.time()

        try:
            while time.time() - start_time < check_duration and self._monitoring:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if prev_frame is not None and np.array_equal(prev_frame, gray_frame):
                    identical_frame_count += 1
                else:
                    identical_frame_count = 0

                prev_frame = gray_frame
                time.sleep(0.2)  # Sample more frequently
        except Exception as e:
            logger.debug("FPS check error for %s: %s", self.url, e)
            return (None, True)
        finally:
            cap.release()

        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0

        # Buffering detected if too many identical frames
        buffering = identical_frame_count >= MAX_IDENTICAL_FRAMES_FOR_BUFFERING

        return (fps, buffering)

    def get_current_quality_score(self) -> float:
        """
        Get the current quality score.

        Returns:
            Quality score from 0.0 to 1.0, or 0.0 if no metrics available.
        """
        with self._lock:
            if self.current_metrics:
                return self.current_metrics.quality_score
            return 0.0

    def is_healthy(self) -> bool:
        """
        Check if current stream quality is healthy.

        Returns:
            True if metrics meet thresholds, False otherwise.
        """
        with self._lock:
            if self.current_metrics:
                return self.current_metrics.is_healthy(self.thresholds)
            return False
