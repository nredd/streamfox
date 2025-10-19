"""Stream pool manager for maintaining healthy backup streams."""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

import requests

from .types import QualityThresholds, StreamQualityMetrics, StreamURL

logger = logging.getLogger(__name__)

# HTTP status code constants
HTTP_CLIENT_ERROR = 400  # Start of client error codes


class StreamPool:
    """
    Manages a pool of validated stream URLs with health checking.

    This class maintains a queue of healthy streams and periodically validates
    them to ensure they're still working. It provides failover capability by
    keeping backup streams ready.

    Attributes:
        healthy_streams: Deque of validated, working stream URLs.
        failed_streams: Set of URLs that have failed validation.
        min_pool_size: Minimum number of streams to keep in the pool.
        health_check_interval: Seconds between health checks.
        quality_metrics: Dictionary mapping stream URLs to their latest quality metrics.
        quality_thresholds: Thresholds for determining stream health.
    """

    def __init__(
        self,
        initial_streams: list[StreamURL] | None = None,
        min_pool_size: int = 3,
        health_check_interval: int = 30,
        quality_thresholds: QualityThresholds | None = None,
    ) -> None:
        """
        Initialize the stream pool.

        Args:
            initial_streams: Initial list of stream URLs to validate.
            min_pool_size: Minimum number of healthy streams to maintain (default: 3).
            health_check_interval: Seconds between health checks (default: 30).
            quality_thresholds: Thresholds for quality-based health checks (uses defaults if None).
        """
        self.healthy_streams: deque[StreamURL] = deque()
        self.failed_streams: set[StreamURL] = set()
        self.min_pool_size = min_pool_size
        self.health_check_interval = health_check_interval
        self.quality_thresholds = quality_thresholds or QualityThresholds()
        self.quality_metrics: dict[StreamURL, StreamQualityMetrics] = {}
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._stream_added_callback: Callable[[StreamURL], None] | None = None

        if initial_streams:
            self.add_streams(initial_streams)

    def check_stream_health(self, url: StreamURL, timeout: int = 5) -> bool:
        """
        Check if a stream URL is healthy and accessible.

        Args:
            url: The stream URL to check.
            timeout: Request timeout in seconds (default: 5).

        Returns:
            True if the stream is healthy, False otherwise.
        """
        try:
            # Quick HEAD request to check if URL is accessible
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code < HTTP_CLIENT_ERROR:
                logger.debug("Stream health check passed: %s", url)
                return True

            # Status code indicates client or server error
            logger.warning("Stream health check failed (status %d): %s", response.status_code, url)
        except requests.RequestException as e:
            logger.debug("Stream health check failed: %s - %s", url, e)

        return False

    def add_streams(self, urls: list[StreamURL]) -> int:
        """
        Add and validate new streams to the pool.

        Args:
            urls: List of stream URLs to add.

        Returns:
            Number of streams successfully added.
        """
        added = 0
        for url in urls:
            # Skip if already failed or in pool
            if url in self.failed_streams:
                logger.debug("Skipping known failed stream: %s", url)
                continue

            with self._lock:
                if url in self.healthy_streams:
                    logger.debug("Stream already in pool: %s", url)
                    continue

            # Validate the stream
            if self.check_stream_health(url):
                with self._lock:
                    self.healthy_streams.append(url)
                added += 1
                logger.info("Added healthy stream to pool: %s", url)

                # Notify callback if registered
                if self._stream_added_callback:
                    self._stream_added_callback(url)
            else:
                self.failed_streams.add(url)
                logger.warning("Stream failed health check, not adding: %s", url)

        logger.info("Added %d streams to pool (total: %d)", added, len(self.healthy_streams))
        return added

    def get_next_stream(self) -> StreamURL | None:
        """
        Get the next healthy stream from the pool.

        This removes the stream from the front of the queue and returns it.
        If the pool is empty, returns None.

        Returns:
            The next stream URL, or None if pool is empty.
        """
        with self._lock:
            if self.healthy_streams:
                stream = self.healthy_streams.popleft()
                logger.info(
                    "Retrieved stream from pool (remaining: %d): %s",
                    len(self.healthy_streams),
                    stream,
                )
                return stream

            logger.warning("Stream pool is empty!")
            return None

    def mark_failed(self, url: StreamURL) -> None:
        """
        Mark a stream as failed and remove it from the pool.

        Args:
            url: The stream URL that failed.
        """
        with self._lock:
            # Remove from healthy streams if present
            if url in self.healthy_streams:
                self.healthy_streams.remove(url)

            # Add to failed set
            self.failed_streams.add(url)
            logger.warning("Marked stream as failed: %s", url)

    def return_stream(self, url: StreamURL) -> None:
        """
        Return a working stream back to the pool.

        This can be used if a stream was retrieved but not used.

        Args:
            url: The stream URL to return.
        """
        with self._lock:
            if url not in self.healthy_streams and url not in self.failed_streams:
                self.healthy_streams.append(url)
                logger.debug("Returned stream to pool: %s", url)

    def pool_size(self) -> int:
        """
        Get the current number of healthy streams in the pool.

        Returns:
            Number of streams in the pool.
        """
        with self._lock:
            return len(self.healthy_streams)

    def needs_refill(self) -> bool:
        """
        Check if the pool needs more streams.

        Returns:
            True if pool size is below minimum, False otherwise.
        """
        return self.pool_size() < self.min_pool_size

    def _monitor_health(self) -> None:
        """Background thread that periodically checks stream health."""
        logger.info("Stream health monitoring started")

        while self._monitoring:
            try:
                # Wait for the health check interval
                time.sleep(self.health_check_interval)

                if not self._monitoring:
                    break

                # Check health of all streams in pool
                with self._lock:
                    streams_to_check = list(self.healthy_streams)

                unhealthy_streams = []
                for stream in streams_to_check:
                    if not self._monitoring:
                        break

                    if not self.check_stream_health(stream):
                        unhealthy_streams.append(stream)

                # Remove unhealthy streams
                for stream in unhealthy_streams:
                    self.mark_failed(stream)
                    logger.warning("Removed unhealthy stream from pool: %s", stream)

                if unhealthy_streams:
                    logger.warning(
                        "Health check removed %d unhealthy streams (pool size: %d)",
                        len(unhealthy_streams),
                        self.pool_size(),
                    )

            except Exception:
                logger.exception("Error in stream health monitoring")

        logger.info("Stream health monitoring stopped")

    def start_monitoring(self) -> None:
        """Start background health monitoring of streams in the pool."""
        if self._monitoring:
            logger.warning("Health monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_health, daemon=True)
        self._monitor_thread.start()
        logger.info("Started background health monitoring")

    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        logger.info("Stopped background health monitoring")

    def set_stream_added_callback(self, callback: Callable[[StreamURL], None]) -> None:
        """
        Register a callback to be called when a new stream is added.

        Args:
            callback: Function to call with the stream URL when a stream is added.
        """
        self._stream_added_callback = callback

    def update_quality_metrics(self, metrics: StreamQualityMetrics) -> None:
        """
        Update quality metrics for a stream.

        Args:
            metrics: The quality metrics to store.
        """
        with self._lock:
            self.quality_metrics[metrics.url] = metrics

            # If stream is unhealthy, consider marking it as failed
            if not metrics.is_healthy(self.quality_thresholds):
                logger.warning(
                    "Stream quality degraded (score: %.2f): %s",
                    metrics.quality_score,
                    metrics.url,
                )

    def get_quality_score(self, url: StreamURL) -> float:
        """
        Get the quality score for a stream.

        Args:
            url: The stream URL.

        Returns:
            Quality score from 0.0 to 1.0, or 0.5 if no metrics available.
        """
        with self._lock:
            if url in self.quality_metrics:
                return self.quality_metrics[url].quality_score
            return 0.5  # Default neutral score for unknown streams

    def get_best_quality_stream(self) -> StreamURL | None:
        """
        Get the highest quality stream from the pool without removing it.

        Returns:
            The URL of the best quality stream, or None if pool is empty.
        """
        with self._lock:
            if not self.healthy_streams:
                return None

            # Sort streams by quality score (highest first)
            ranked_streams = sorted(
                self.healthy_streams,
                key=lambda url: self.get_quality_score(url),
                reverse=True,
            )

            return ranked_streams[0] if ranked_streams else None

    def get_ranked_streams(self) -> list[tuple[StreamURL, float]]:
        """
        Get all healthy streams ranked by quality score.

        Returns:
            List of (url, quality_score) tuples sorted by score (highest first).
        """
        with self._lock:
            ranked = [(url, self.get_quality_score(url)) for url in self.healthy_streams]
            ranked.sort(key=lambda x: x[1], reverse=True)
            return ranked

    def should_switch_stream(
        self,
        current_url: StreamURL,
        current_quality: float,
    ) -> StreamURL | None:
        """
        Determine if we should switch to a better quality stream.

        Args:
            current_url: The currently playing stream URL.
            current_quality: The current stream's quality score.

        Returns:
            The URL of a better stream to switch to, or None if current is best.
        """
        best_stream = self.get_best_quality_stream()

        if not best_stream or best_stream == current_url:
            return None

        best_quality = self.get_quality_score(best_stream)

        # Only switch if the better stream exceeds the threshold
        quality_diff = best_quality - current_quality
        if quality_diff >= self.quality_thresholds.switch_threshold_score:
            logger.info(
                "Found better quality stream (%.2f vs %.2f): %s",
                best_quality,
                current_quality,
                best_stream,
            )
            return best_stream

        return None
