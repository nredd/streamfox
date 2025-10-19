"""Stream player with automatic failover."""

import logging
import subprocess
import time

from .playback_monitor import PlaybackMonitor
from .stream_pool import StreamPool
from .types import QualityThresholds, StreamQualityMetrics, StreamURL

logger = logging.getLogger(__name__)

# Special return code to indicate quality-based stream switch
QUALITY_SWITCH_RETURN_CODE = -999


class StreamPlayer:
    """
    Plays video streams with automatic failover.

    Attempts to play streams in order, automatically switching to the next
    stream if one fails. Supports mpv, vlc, and ffplay.

    In continuous mode, the player will keep running indefinitely, pulling
    new streams from a pool as needed when the current stream fails.

    Attributes:
        stream_urls: List of stream URLs to try.
        player_cmd: Preferred video player command.
        current_index: Index of currently playing stream.
        continuous: Whether to run in continuous playback mode.
        stream_pool: Pool of backup streams for continuous mode.
        enable_quality_monitoring: Whether to monitor stream quality during playback.
        quality_thresholds: Thresholds for quality-based switching.
        current_stream_url: The currently playing stream URL.
        playback_monitor: Quality monitor for the current stream.
    """

    def __init__(
        self,
        stream_urls: list[StreamURL] | set[StreamURL],
        player_cmd: str = "mpv",
        continuous: bool = False,
        stream_pool: StreamPool | None = None,
        enable_quality_monitoring: bool = True,
        quality_thresholds: QualityThresholds | None = None,
    ) -> None:
        """
        Initialize the stream player.

        Args:
            stream_urls: List or set of stream URLs to play.
            player_cmd: Preferred video player (default: 'mpv').
            continuous: Enable continuous playback mode (default: False).
            stream_pool: StreamPool to use for continuous mode (optional).
            enable_quality_monitoring: Enable real-time quality monitoring (default: True).
            quality_thresholds: Quality thresholds for monitoring (uses defaults if None).
        """
        self.stream_urls = list(stream_urls)
        self.player_cmd = player_cmd
        self.current_index = 0
        self.process: subprocess.Popen | None = None
        self.continuous = continuous
        self.stream_pool = stream_pool
        self.enable_quality_monitoring = enable_quality_monitoring
        self.quality_thresholds = quality_thresholds or QualityThresholds()
        self._stop_requested = False
        self._switch_requested = False
        self._switch_to_url: StreamURL | None = None
        self.current_stream_url: StreamURL | None = None
        self.playback_monitor: PlaybackMonitor | None = None

        logger.info("StreamPlayer initialized with %d streams", len(self.stream_urls))
        if continuous:
            logger.info("Continuous playback mode enabled")
        if enable_quality_monitoring:
            logger.info("Quality monitoring enabled")

    def _find_available_player(self) -> str | None:
        """
        Find an available video player on the system.

        Returns:
            Name of the first available player, or None if none found.
        """
        players = ["mpv", "vlc", "ffplay"]
        for player in players:
            try:
                result = subprocess.run(
                    ["which", player],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info("Found player: %s", player)
                    return player
            except Exception:
                continue
        return None

    def _build_player_command(self, player: str, url: StreamURL) -> list[str]:
        """
        Build the command line for the video player.

        Args:
            player: Name of the player to use.
            url: Stream URL to play.

        Returns:
            List of command arguments.
        """
        if player == "mpv":
            # mpv can handle both video and audio streams well
            return ["mpv", url]
        if player == "vlc":
            return ["vlc", url]
        # ffplay
        return ["ffplay", "-autoexit", url]

    def _on_quality_change(self, metrics: StreamQualityMetrics) -> None:
        """
        Callback invoked when quality metrics update.

        Args:
            metrics: The updated quality metrics.
        """
        # Update the stream pool with quality metrics
        if self.stream_pool:
            self.stream_pool.update_quality_metrics(metrics)

            # Check if we should switch to a better stream
            if self.continuous and not self._switch_requested:
                better_stream = self.stream_pool.should_switch_stream(
                    metrics.url,
                    metrics.quality_score,
                )
                if better_stream:
                    logger.info("Requesting switch to better quality stream")
                    self._switch_requested = True
                    self._switch_to_url = better_stream

    def _start_quality_monitoring(self, url: StreamURL) -> None:
        """
        Start quality monitoring for the given stream.

        Args:
            url: The stream URL to monitor.
        """
        if not self.enable_quality_monitoring:
            return

        # Stop any existing monitor
        self._stop_quality_monitoring()

        # Create and start new monitor
        self.playback_monitor = PlaybackMonitor(
            url=url,
            thresholds=self.quality_thresholds,
            check_interval=self.quality_thresholds.quality_check_interval_seconds,
            on_quality_change=self._on_quality_change,
        )
        self.playback_monitor.start()
        logger.debug("Started quality monitoring for %s", url)

    def _stop_quality_monitoring(self) -> None:
        """Stop the current quality monitoring."""
        if self.playback_monitor:
            self.playback_monitor.stop()
            self.playback_monitor = None
            logger.debug("Stopped quality monitoring")

    def _wait_for_stream_with_monitoring(self) -> int:
        """
        Wait for the stream process to finish, checking for quality-based switch requests.

        Returns:
            The return code of the process (0 for success, non-zero for failure).
            Returns -999 if a quality-based switch was requested.
        """
        if not self.process:
            return -1

        # Check interval for switch requests (in seconds)
        check_interval = 1.0

        while True:
            # Poll the process
            return_code = self.process.poll()

            # If process has ended, return its code
            if return_code is not None:
                self._stop_quality_monitoring()
                return return_code

            # Check if a quality-based switch was requested
            if self._switch_requested and self._switch_to_url:
                logger.info(
                    "Quality-based switch requested from %s to %s",
                    self.current_stream_url,
                    self._switch_to_url,
                )
                # Terminate current stream
                self.process.terminate()
                self._stop_quality_monitoring()

                # Return the switch URL to the pool so it can be picked up next
                if self.stream_pool:
                    self.stream_pool.return_stream(self._switch_to_url)

                # Reset switch flags
                self._switch_requested = False
                self._switch_to_url = None

                # Return special code to indicate switch
                return QUALITY_SWITCH_RETURN_CODE

            # Sleep briefly before next check
            time.sleep(check_interval)

    def _get_next_stream_url(self) -> StreamURL | None:
        """
        Get the next stream URL to play.

        In normal mode, gets from the internal list.
        In continuous mode, pulls from the stream pool.

        Returns:
            Next stream URL, or None if no more streams available.
        """
        if self.continuous and self.stream_pool:
            # In continuous mode, try to get from pool
            url = self.stream_pool.get_next_stream()
            if url:
                return url

            # If pool is empty, check if we need to refill
            if self.stream_pool.needs_refill():
                logger.warning("Stream pool is empty and needs refill")

            # Fall back to internal list if pool is empty
            if self.current_index < len(self.stream_urls):
                url = self.stream_urls[self.current_index]
                self.current_index += 1
                return url

            return None

        # Normal mode: use internal list
        if self.current_index < len(self.stream_urls):
            url = self.stream_urls[self.current_index]
            self.current_index += 1
            return url

        return None

    def play(self) -> None:
        """
        Play streams with automatic failover.

        In normal mode, tries each stream URL in order until one succeeds or all fail.
        In continuous mode, keeps playing indefinitely, pulling from the stream pool
        when the current stream fails. Only stops when manually interrupted or when
        both the pool and internal list are exhausted.

        Handles keyboard interrupts gracefully.
        """
        player = self._find_available_player()
        if not player:
            logger.error("No video player found! Install mpv, vlc, or ffplay")
            logger.info("On macOS: brew install mpv")
            logger.info("On Linux: sudo apt install mpv (or yum/dnf)")
            return

        if not self.stream_urls and (not self.continuous or not self.stream_pool):
            logger.error("No stream URLs to play!")
            return

        streams_tried = 0
        consecutive_failures = 0
        max_consecutive_failures = 5  # Stop after 5 consecutive failures in continuous mode

        while not self._stop_requested:
            url = self._get_next_stream_url()

            if url is None:
                if self.continuous:
                    logger.warning("No streams available. Waiting for pool refill...")
                    # In continuous mode, wait a bit and try again
                    time.sleep(5)
                    continue
                # Normal mode: no more streams
                logger.error("All streams exhausted!")
                break

            streams_tried += 1
            pool_size = self.stream_pool.pool_size() if self.stream_pool else 0
            logger.info("Playing stream (pool size: %d): %s", pool_size, url)

            try:
                self.current_stream_url = url
                cmd = self._build_player_command(player, url)
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # Start quality monitoring for this stream
                self._start_quality_monitoring(url)

                # Wait for the stream to finish or fail, checking for switch requests
                return_code = self._wait_for_stream_with_monitoring()

                # Handle quality-based switch (special return code)
                if return_code == QUALITY_SWITCH_RETURN_CODE:
                    logger.info("Switched to better quality stream")
                    consecutive_failures = 0  # Reset failure counter
                    continue  # Continue to next stream immediately

                if return_code != 0:
                    consecutive_failures += 1
                    logger.warning(
                        "Stream failed with code %d (consecutive failures: %d)",
                        return_code,
                        consecutive_failures,
                    )

                    # Mark as failed in pool if we're using one
                    if self.stream_pool:
                        self.stream_pool.mark_failed(url)

                    # In continuous mode, check if we've had too many failures
                    if self.continuous and consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            "Too many consecutive failures (%d). Stopping playback.",
                            consecutive_failures,
                        )
                        break

                    # Continue to next stream
                    continue
                # Stream ended normally
                consecutive_failures = 0  # Reset failure counter
                logger.info("Stream ended normally")

                if not self.continuous:
                    # In normal mode, stop after successful playback
                    break
                # In continuous mode, continue to next stream
                logger.info("Continuing to next stream in continuous mode...")

            except KeyboardInterrupt:
                logger.info("Playback interrupted by user")
                self._stop_quality_monitoring()
                if self.process:
                    self.process.terminate()
                break
            except Exception:
                consecutive_failures += 1
                logger.exception(
                    "Error playing stream (consecutive failures: %d)", consecutive_failures
                )

                # Mark as failed in pool
                if self.stream_pool:
                    self.stream_pool.mark_failed(url)

                if self.continuous and consecutive_failures >= max_consecutive_failures:
                    logger.error("Too many consecutive failures. Stopping playback.")
                    break

        logger.info("Playback ended after trying %d streams", streams_tried)

    def stop(self) -> None:
        """Stop the currently playing stream and exit continuous mode."""
        self._stop_requested = True
        self._stop_quality_monitoring()
        if self.process:
            self.process.terminate()
            self.process = None
        logger.info("Playback stopped")
