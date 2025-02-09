#!/usr/bin/env python3
"""
Streamfox implementation!!!
"""

import argparse
import asyncio
import cv2
import logging
import numpy as np
import time
import requests
import yaml
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
# TODO(redd): Try other browsers
# TODO(redd): Try auto installing arbitrary browser driver manager


logging.basicConfig(
    level=logging.INFO, # Set the minimum logging level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(f'{__file__}.log'), logging.StreamHandler()]
)
LOGGER = logging.getLogger(__name__)



class VideoCrawler:
    def __init__(self, base_url, max_depth=10, headless=True):
        self.base_url = base_url
        self.visited_urls = set()
        self.video_urls = set()
        self.max_depth = max_depth
        self.headless = headless
        self.driver = self.init_driver()

    def init_driver(self):
        """Initialize Selenium WebDriver"""
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu") # TODO(redd): Needed?
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def find_videos_on_page(self, url):
        """Find video stream links on a given webpage"""
        self.driver.get(url)
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # Find <video> tags
        for video in soup.find_all("video"):
            if "src" in video.attrs:
                self.video_urls.add(video["src"])

        # Find common streaming platforms (YouTube, embedded iframes)
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if "youtube.com" in src or "vimeo.com" in src:
                self.video_urls.add(src)

    def crawl(self, url, depth=0):
        """Recursively crawl a website to extract video streams"""
        if depth > self.max_depth or url in self.visited_urls:
            return
        self.visited_urls.add(url)

        try:
            self.find_videos_on_page(url)
            LOGGER.info(f"[Crawled] {url} | Found {len(self.video_urls)} videos")

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            for link in soup.find_all("a", href=True):
                next_url = link["href"]
                if next_url.startswith("http"):
                    self.crawl(next_url, depth + 1)

        except Exception as e:
            LOGGER.info(f"[Error] Failed to crawl {url}: {e}")

    def close(self):
        """Close the Selenium WebDriver"""
        self.driver.quit()


class AsyncStreamMonitor:
    def __init__(self, video_urls, check_interval=10, max_workers=5):
        self.video_urls = list(video_urls)
        self.check_interval = check_interval
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = asyncio.get_event_loop()

    async def check_stream(self, url):
        """Asynchronously checks a video stream for activity."""
        LOGGER.info(f"Checking stream: {url}")

        latency_ok = await self.loop.run_in_executor(self.executor, self.check_latency, url)
        if not latency_ok:
            LOGGER.info(f"[WARN] {url} is slow or unresponsive.")
            return False

        stream_active = await self.loop.run_in_executor(self.executor, self.is_stream_active, url)
        if not stream_active:
            LOGGER.info(f"[WARN] {url} appears to be frozen or not updating frames.")
            return False

        fps_ok = await self.loop.run_in_executor(self.executor, self.check_fps, url)
        if not fps_ok:
            LOGGER.info(f"[WARN] {url} has low FPS or excessive buffering.")
            return False

        LOGGER.info(f"[OK] {url} is running smoothly.")
        return True

    def check_latency(self, url):
        """Checks the response time of the video stream."""
        try:
            start_time = time.time()
            response = requests.get(url, stream=True, timeout=5)
            latency = time.time() - start_time
            return response.status_code == 200 and latency < 3  # Acceptable latency threshold
        except requests.RequestException:
            return False

    def is_stream_active(self, url, check_duration=5, frame_interval=1):
        """Checks if a video stream is delivering new frames by comparing frame differences."""
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            return False

        prev_frame = None
        active = False
        start_time = time.time()

        while time.time() - start_time < check_duration:
            ret, frame = cap.read()
            if not ret:
                break

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_frame is not None:
                diff = np.sum(cv2.absdiff(prev_frame, gray_frame))
                if diff > 5000:  # Motion threshold
                    active = True
                    break

            prev_frame = gray_frame
            time.sleep(frame_interval)

        cap.release()
        return active

    def check_fps(self, url, check_duration=5):
        """Measures FPS and checks for buffering or excessive identical frames."""
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            return False

        frame_count = 0
        identical_frames = 0
        prev_frame = None
        start_time = time.time()

        while time.time() - start_time < check_duration:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_frame is not None and np.array_equal(prev_frame, gray_frame):
                identical_frames += 1
            else:
                identical_frames = 0  # Reset counter if frames change

            prev_frame = gray_frame
            time.sleep(1)

        cap.release()
        fps = frame_count / check_duration
        return fps > 5 and identical_frames < 3  # Ensure FPS is acceptable and frames change

    async def monitor_streams(self):
        """Periodically checks all streams asynchronously."""
        while True:
            tasks = [self.check_stream(url) for url in self.video_urls]
            await asyncio.gather(*tasks)
            LOGGER.info("\n[INFO] Waiting for next check...\n")
            await asyncio.sleep(self.check_interval)

    def start_monitoring(self):
        """Starts the async monitoring loop."""
        try:
            self.loop.run_until_complete(self.monitor_streams())
        except KeyboardInterrupt:
            LOGGER.info("\n[INFO] Stopping monitoring...")
        finally:
            self.executor.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    if args.debug:
        LOGGER.set_level(logging.DEBUG)
    
    streams_yaml = (pathlib.Path(__file__) / 'streams.yaml').resolve()
    streams_yaml = yaml.safe_load(open(streams_yaml))
    for s in streams_yaml['streams']:
        crawler = VideoCrawler(s, max_depth=20, headless=True)
        LOGGER.info(f"[INFO] Crawling {base_url} for video streams...")
        crawler.crawl(base_url)
        crawler.close()

        # Step 2: Monitor extracted video streams
        if crawler.video_urls:
            LOGGER.info(f"[INFO] Found {len(crawler.video_urls)} video streams. Starting monitoring...")
            monitor = AsyncStreamMonitor(crawler.video_urls, check_interval=10, max_workers=5)
            monitor.start_monitoring()
        else:
            LOGGER.info("[ERROR] No video streams found!")
