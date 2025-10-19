"""Command-line interface for streamfox."""

import argparse
import logging
import pathlib
import time
import webbrowser

import yaml

from .crawler import VideoCrawler
from .monitor import AsyncStreamMonitor
from .player import StreamPlayer
from .stream_pool import StreamPool

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for the application.

    Args:
        debug: Enable debug level logging if True.
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("streamfox.log"),
            logging.StreamHandler(),
        ],
    )


def is_direct_stream_url(url: str) -> bool:
    """
    Check if a URL is likely a direct video stream (playable by mpv/vlc/ffplay).

    Args:
        url: The URL to check.

    Returns:
        True if URL appears to be a direct stream, False if it's an embed/iframe.
    """
    # Direct stream indicators
    stream_extensions = [".m3u8", ".mp4", ".ts", ".mpd", ".webm", ".mkv", ".avi", ".mov"]
    stream_patterns = ["manifest", "playlist", "chunk"]

    url_lower = url.lower()

    # Check for direct stream file extensions
    if any(ext in url_lower for ext in stream_extensions):
        return True

    # Check for stream-related patterns
    if any(pattern in url_lower for pattern in stream_patterns):
        return True

    # If it contains "embed" or "iframe", it's likely not a direct stream
    if any(pattern in url_lower for pattern in ["embed", "iframe", "player"]):
        return False

    # Default: assume it's NOT a direct stream to be safe
    return False


def add_autoplay_to_url(url: str) -> str:
    """
    Add autoplay parameters to iframe/embed URLs for automatic playback.

    Args:
        url: The iframe/embed URL.

    Returns:
        URL with autoplay parameters added.
    """
    # YouTube embeds
    if "youtube.com/embed" in url or "youtube-nocookie.com/embed" in url:
        separator = "&" if "?" in url else "?"
        # Add autoplay, mute (required by browsers), and remove controls for cleaner view
        return f"{url}{separator}autoplay=1&mute=1"

    # Vimeo embeds
    if "vimeo.com" in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}autoplay=1&muted=1"

    # Twitch embeds
    if "twitch.tv" in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}autoplay=true&muted=false"

    # Default: return as-is for unknown platforms
    return url


def load_streams_from_yaml(yaml_path: pathlib.Path | None = None) -> list[str]:
    """
    Load stream URLs from a YAML configuration file.

    Args:
        yaml_path: Path to streams.yaml file. If None, looks in package directory.

    Returns:
        List of stream URLs.

    Raises:
        FileNotFoundError: If the YAML file doesn't exist.
        ValueError: If the YAML format is invalid.
    """
    if yaml_path is None:
        # Look for streams.yaml in the project root
        yaml_path = pathlib.Path.cwd() / "streams.yaml"

    if not yaml_path.exists():
        msg = f"Streams configuration not found at {yaml_path}"
        raise FileNotFoundError(msg)

    with yaml_path.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "streams" not in data:
        msg = "YAML file must contain a 'streams' key with a list of URLs"
        raise ValueError(msg)

    streams = data["streams"]
    if not isinstance(streams, list):
        msg = "'streams' must be a list of URLs"
        raise TypeError(msg)

    return streams


def main() -> None:
    """Main entry point for the streamfox CLI."""
    parser = argparse.ArgumentParser(
        description="Streamfox - Robust stream crawler and player",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Crawl and play streams from streams.yaml
  streamfox

  # Play a specific stream URL
  streamfox --url https://example.com/stream.m3u8

  # Continuous playback with automatic failover
  streamfox --continuous --pool-size 5

  # Monitor streams for quality
  streamfox --monitor

  # Crawl with verbose output
  streamfox --debug --max-depth 3
        """,
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--url",
        "-u",
        type=str,
        help="Specific stream URL to watch",
    )
    parser.add_argument(
        "--play",
        "-p",
        action="store_true",
        default=True,
        help="Play streams immediately (default)",
    )
    parser.add_argument(
        "--monitor",
        "-m",
        action="store_true",
        help="Monitor streams instead of playing",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Max crawl depth (default: 2)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=pathlib.Path,
        help="Path to streams.yaml configuration file",
    )
    parser.add_argument(
        "--exhaustive",
        action="store_true",
        help="Crawl all pages exhaustively (don't stop when videos are found)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continuous playback mode with automatic failover (keeps playing indefinitely)",
    )
    parser.add_argument(
        "--pool-size",
        type=int,
        default=3,
        help="Minimum number of backup streams to maintain in continuous mode (default: 3)",
    )

    args = parser.parse_args()
    setup_logging(args.debug)

    # Determine stream sources
    if args.url:
        streams = [args.url]
    else:
        try:
            streams = load_streams_from_yaml(args.config)
        except (FileNotFoundError, ValueError):
            logger.exception("Error loading streams")
            logger.info("Please provide a --url or create a streams.yaml file")
            return

    if not streams:
        logger.error("No streams configured!")
        return

    all_video_urls: set[str] = set()

    # Crawl each source
    for stream_url in streams:
        logger.info("Crawling %s...", stream_url)
        crawler = VideoCrawler(
            stream_url,
            max_depth=args.max_depth,
            headless=args.headless,
            stop_on_first_video=not args.exhaustive,
        )

        try:
            crawler.crawl()
            all_video_urls.update(crawler.video_urls)

            # If we found streams and user wants to play immediately, do it
            if crawler.video_urls and not args.monitor:
                # Separate direct streams from iframe/embed URLs
                direct_streams = [url for url in crawler.video_urls if is_direct_stream_url(url)]
                iframe_urls = [url for url in crawler.video_urls if not is_direct_stream_url(url)]

                logger.info("Found %d video streams!", len(crawler.video_urls))
                for idx, url in enumerate(crawler.video_urls, 1):
                    logger.info("  %d. %s", idx, url)

                # Open iframe URLs in browser with autoplay
                if iframe_urls:
                    logger.info(
                        "Opening %d iframe/embed URLs in browser with autoplay...",
                        len(iframe_urls),
                    )
                    for url in iframe_urls:
                        autoplay_url = add_autoplay_to_url(url)
                        logger.info("  Opening in browser: %s", autoplay_url)
                        webbrowser.open(autoplay_url)

                # Play direct streams with video player
                if direct_streams:
                    logger.info("Playing %d direct stream URLs...", len(direct_streams))

                    # Enable continuous mode by default for better UX
                    if not args.continuous:
                        logger.info("Enabling continuous playback mode (use Ctrl+C to stop)")
                        args.continuous = True

                    # Set up continuous mode
                    logger.info("Setting up continuous playback with pool size %d", args.pool_size)
                    stream_pool = StreamPool(
                        initial_streams=direct_streams,
                        min_pool_size=args.pool_size,
                    )
                    stream_pool.start_monitoring()

                    player = StreamPlayer(
                        stream_urls=direct_streams,
                        continuous=True,
                        stream_pool=stream_pool,
                    )
                    try:
                        player.play()
                    finally:
                        stream_pool.stop_monitoring()
                    # Only return if we actually played something with the video player
                    return

                # If we only have iframe URLs, keep the app alive
                if iframe_urls and not direct_streams:
                    logger.info(
                        "Streams opened in browser. App will keep running (press Ctrl+C to exit)..."
                    )
                    try:
                        # Keep alive loop - wait for user interrupt
                        while True:
                            time.sleep(60)  # Check every minute
                            logger.debug("Keep-alive: streams running in browser...")
                    except KeyboardInterrupt:
                        logger.info("Shutting down...")
                        return

                if not iframe_urls and not direct_streams:
                    logger.warning("No playable streams found")
        finally:
            crawler.close()

    # Handle results
    if all_video_urls:
        if args.monitor:
            # Monitor mode
            logger.info("Found %d total video streams. Starting monitoring...", len(all_video_urls))
            monitor = AsyncStreamMonitor(all_video_urls, check_interval=10, max_workers=5)
            monitor.start_monitoring()
        else:
            # Play mode (default)
            # Separate direct streams from iframe/embed URLs
            direct_streams = [url for url in all_video_urls if is_direct_stream_url(url)]
            iframe_urls = [url for url in all_video_urls if not is_direct_stream_url(url)]

            logger.info("Found %d total video streams!", len(all_video_urls))
            for idx, url in enumerate(all_video_urls, 1):
                logger.info("  %d. %s", idx, url)

            # Open iframe URLs in browser with autoplay
            if iframe_urls:
                logger.info(
                    "Opening %d iframe/embed URLs in browser with autoplay...",
                    len(iframe_urls),
                )
                for url in iframe_urls:
                    autoplay_url = add_autoplay_to_url(url)
                    logger.info("  Opening in browser: %s", autoplay_url)
                    webbrowser.open(autoplay_url)

            # Play direct streams with video player
            if direct_streams:
                logger.info("Playing %d direct stream URLs...", len(direct_streams))

                # Enable continuous mode by default for better UX
                if not args.continuous:
                    logger.info("Enabling continuous playback mode (use Ctrl+C to stop)")
                    args.continuous = True

                # Set up continuous mode
                logger.info("Setting up continuous playback with pool size %d", args.pool_size)
                stream_pool = StreamPool(
                    initial_streams=direct_streams,
                    min_pool_size=args.pool_size,
                )
                stream_pool.start_monitoring()

                player = StreamPlayer(
                    stream_urls=direct_streams,
                    continuous=True,
                    stream_pool=stream_pool,
                )
                try:
                    player.play()
                finally:
                    stream_pool.stop_monitoring()

            # If we only have iframe URLs, keep the app alive
            elif iframe_urls:
                logger.info(
                    "Streams opened in browser. App will keep running (press Ctrl+C to exit)..."
                )
                try:
                    # Keep alive loop - wait for user interrupt
                    while True:
                        time.sleep(60)  # Check every minute
                        logger.debug("Keep-alive: streams running in browser...")
                except KeyboardInterrupt:
                    logger.info("Shutting down...")

            else:
                logger.warning("No playable streams found")
    else:
        logger.error("No video streams found!")


if __name__ == "__main__":
    main()
