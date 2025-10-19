"""Command-line interface for streamfox."""

import argparse
import logging
import pathlib

import yaml

from .crawler import VideoCrawler
from .monitor import AsyncStreamMonitor
from .player import StreamPlayer

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
        )

        try:
            crawler.crawl()
            all_video_urls.update(crawler.video_urls)

            # If we found streams and user wants to play immediately, do it
            if crawler.video_urls and not args.monitor:
                logger.info("Found %d video streams!", len(crawler.video_urls))
                for idx, url in enumerate(crawler.video_urls, 1):
                    logger.info("  %d. %s", idx, url)

                player = StreamPlayer(crawler.video_urls)
                player.play()
                return
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
            logger.info("Found %d total video streams!", len(all_video_urls))
            for idx, url in enumerate(all_video_urls, 1):
                logger.info("  %d. %s", idx, url)
            player = StreamPlayer(all_video_urls)
            player.play()
    else:
        logger.error("No video streams found!")


if __name__ == "__main__":
    main()
