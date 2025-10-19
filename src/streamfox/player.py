"""Stream player with automatic failover."""

import logging
import subprocess
import time

from .stream_pool import StreamPool
from .types import StreamURL

logger = logging.getLogger(__name__)


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
    """

    def __init__(
        self,
        stream_urls: list[StreamURL] | set[StreamURL],
        player_cmd: str = "mpv",
        continuous: bool = False,
        stream_pool: StreamPool | None = None,
    ) -> None:
        """
        Initialize the stream player.

        Args:
            stream_urls: List or set of stream URLs to play.
            player_cmd: Preferred video player (default: 'mpv').
            continuous: Enable continuous playback mode (default: False).
            stream_pool: StreamPool to use for continuous mode (optional).
        """
        self.stream_urls = list(stream_urls)
        self.player_cmd = player_cmd
        self.current_index = 0
        self.process: subprocess.Popen | None = None
        self.continuous = continuous
        self.stream_pool = stream_pool
        self._stop_requested = False
        logger.info("StreamPlayer initialized with %d streams", len(self.stream_urls))
        if continuous:
            logger.info("Continuous playback mode enabled")

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
                cmd = self._build_player_command(player, url)
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # Wait for the stream to finish or fail
                return_code = self.process.wait()

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
        if self.process:
            self.process.terminate()
            self.process = None
        logger.info("Playback stopped")
