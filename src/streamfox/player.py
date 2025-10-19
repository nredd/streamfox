"""Stream player with automatic failover."""

import logging
import subprocess

from .types import StreamURL

logger = logging.getLogger(__name__)


class StreamPlayer:
    """
    Plays video streams with automatic failover.

    Attempts to play streams in order, automatically switching to the next
    stream if one fails. Supports mpv, vlc, and ffplay.

    Attributes:
        stream_urls: List of stream URLs to try.
        player_cmd: Preferred video player command.
        current_index: Index of currently playing stream.
    """

    def __init__(
        self,
        stream_urls: list[StreamURL] | set[StreamURL],
        player_cmd: str = "mpv",
    ) -> None:
        """
        Initialize the stream player.

        Args:
            stream_urls: List or set of stream URLs to play.
            player_cmd: Preferred video player (default: 'mpv').
        """
        self.stream_urls = list(stream_urls)
        self.player_cmd = player_cmd
        self.current_index = 0
        self.process: subprocess.Popen | None = None
        logger.info("StreamPlayer initialized with %d streams", len(self.stream_urls))

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

    def play(self) -> None:
        """
        Play streams with automatic failover.

        Tries each stream URL in order until one succeeds or all fail.
        Handles keyboard interrupts gracefully.
        """
        player = self._find_available_player()
        if not player:
            logger.error("No video player found! Install mpv, vlc, or ffplay")
            logger.info("On macOS: brew install mpv")
            logger.info("On Linux: sudo apt install mpv (or yum/dnf)")
            return

        if not self.stream_urls:
            logger.error("No stream URLs to play!")
            return

        while self.current_index < len(self.stream_urls):
            url = self.stream_urls[self.current_index]
            logger.info(
                "Playing stream %d/%d: %s",
                self.current_index + 1,
                len(self.stream_urls),
                url,
            )

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
                    logger.warning("Stream failed with code %d, trying next...", return_code)
                    self.current_index += 1
                else:
                    logger.info("Stream ended normally")
                    break

            except KeyboardInterrupt:
                logger.info("Playback interrupted by user")
                if self.process:
                    self.process.terminate()
                break
            except Exception:
                logger.exception("Error playing stream")
                self.current_index += 1

        if self.current_index >= len(self.stream_urls):
            logger.error("All streams failed!")

    def stop(self) -> None:
        """Stop the currently playing stream."""
        if self.process:
            self.process.terminate()
            self.process = None
