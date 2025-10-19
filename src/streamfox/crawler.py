"""Video stream crawler using Selenium and BeautifulSoup."""

import json
import logging
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from .types import URL, StreamURL

logger = logging.getLogger(__name__)


class VideoCrawler:
    """
    Crawls websites to discover video stream URLs.

    This crawler uses Selenium to execute JavaScript and capture network traffic,
    then extracts video URLs from both the DOM and network logs.

    Attributes:
        base_url: The starting URL to crawl.
        visited_urls: Set of URLs already visited.
        video_urls: Set of discovered video stream URLs.
        max_depth: Maximum recursion depth for crawling.
        headless: Whether to run browser in headless mode.
    """

    def __init__(
        self,
        base_url: URL,
        max_depth: int = 10,
        headless: bool = True,
    ) -> None:
        """
        Initialize the video crawler.

        Args:
            base_url: The starting URL to begin crawling from.
            max_depth: Maximum depth to crawl (default: 10).
            headless: Run browser in headless mode (default: True).
        """
        self.base_url = base_url
        self.visited_urls: set[URL] = set()
        self.video_urls: set[StreamURL] = set()
        self.max_depth = max_depth
        self.headless = headless
        self.driver: webdriver.Chrome | None = None
        logger.info("VideoCrawler initialized with %s", self.base_url)

    def init_driver(self) -> webdriver.Chrome:
        """
        Initialize Selenium WebDriver with network logging enabled.

        Returns:
            Configured Chrome WebDriver instance.
        """
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Enable performance logging to capture network requests
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def find_videos_on_page(self, url: URL) -> None:
        """
        Find video stream links on a given webpage.

        This method checks both the page DOM and network logs for video URLs.

        Args:
            url: The URL of the page to search for videos.
        """
        if self.driver is None:
            self.driver = self.init_driver()

        try:
            self.driver.get(url)
            # Wait for page to load and JavaScript to execute
            time.sleep(5)

            # Extract from network logs first (most reliable for streaming sites)
            self._extract_from_network_logs()

            # Parse the page HTML
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Find <video> tags
            for video in soup.find_all("video"):
                src = video.get("src")
                if src and isinstance(src, str):
                    self.video_urls.add(src)
                # Check <source> tags inside <video>
                for source in video.find_all("source"):
                    src = source.get("src")
                    if src and isinstance(src, str):
                        self.video_urls.add(src)

            # Find embedded iframes (common in streaming sites)
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src")
                if src and isinstance(src, str):
                    logger.info("Found iframe: %s", src)
                    # Recursively check iframes for streams
                    if src.startswith("http") and src not in self.visited_urls:
                        self.video_urls.add(src)

        except Exception:
            logger.exception("Error finding videos on %s", url)

    def _extract_from_network_logs(self) -> None:
        """
        Extract video URLs from browser network logs.

        Looks for video file extensions and video MIME types in network traffic.
        """
        if self.driver is None:
            return

        try:
            logs = self.driver.get_log("performance")  # type: ignore[no-untyped-call]
            for entry in logs:
                try:
                    log = json.loads(entry["message"])["message"]
                    if log.get("method") == "Network.responseReceived":
                        response = log.get("params", {}).get("response", {})
                        url = response.get("url", "")
                        mime_type = response.get("mimeType", "")

                        # Look for video/streaming URLs
                        video_extensions = [".m3u8", ".mp4", ".ts", ".mpd", ".webm"]
                        if any(ext in url for ext in video_extensions):
                            logger.info("Found stream URL: %s", url)
                            self.video_urls.add(url)
                        elif any(
                            t in mime_type
                            for t in ["video", "mpegurl", "application/vnd.apple.mpegurl"]
                        ):
                            logger.info("Found video mime type: %s", url)
                            self.video_urls.add(url)
                except Exception:
                    # Skip malformed log entries
                    continue
        except Exception as e:
            logger.debug("Could not extract from network logs: %s", e)

    def crawl(self, url: URL | None = None, depth: int = 0) -> None:
        """
        Recursively crawl a website to extract video streams.

        Args:
            url: URL to crawl (defaults to base_url if None).
            depth: Current recursion depth.
        """
        url = self.base_url if url is None else url

        if depth > self.max_depth or url in self.visited_urls:
            return

        self.visited_urls.add(url)

        try:
            self.find_videos_on_page(url)
            logger.info("[Crawled] %s | Found %d videos total", url, len(self.video_urls))

            # Only continue crawling if we haven't exceeded depth
            if depth < self.max_depth and self.driver:
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                for link in soup.find_all("a", href=True):
                    next_url = link.get("href")
                    if next_url and isinstance(next_url, str) and next_url.startswith("http"):
                        self.crawl(next_url, depth + 1)

        except Exception:
            logger.exception("Failed to crawl %s", url)

    def close(self) -> None:
        """Close the Selenium WebDriver and cleanup resources."""
        if self.driver:
            self.driver.quit()
            self.driver = None
