"""Asynchronous stream quality monitoring."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import requests

from .types import StreamURL

# Quality thresholds
HTTP_OK = 200
MAX_LATENCY_SECONDS = 3.0
MIN_FPS = 5
MAX_IDENTICAL_FRAMES = 3
MOTION_THRESHOLD = 5000

logger = logging.getLogger(__name__)


class AsyncStreamMonitor:
    """
    Monitors multiple video streams for quality and availability.

    Uses asyncio for concurrent monitoring and checks latency, frame updates,
    and FPS for each stream.

    Attributes:
        video_urls: List of video stream URLs to monitor.
        check_interval: Seconds between each check cycle.
        executor: ThreadPoolExecutor for blocking operations.
    """

    def __init__(
        self,
        video_urls: list[StreamURL] | set[StreamURL],
        check_interval: int = 10,
        max_workers: int = 5,
    ) -> None:
        """
        Initialize the stream monitor.

        Args:
            video_urls: List or set of stream URLs to monitor.
            check_interval: Seconds between checks (default: 10).
            max_workers: Maximum concurrent worker threads (default: 5).
        """
        self.video_urls = list(video_urls)
        self.check_interval = check_interval
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def check_stream(self, url: StreamURL) -> bool:
        """
        Asynchronously check a video stream for activity and quality.

        Args:
            url: Stream URL to check.

        Returns:
            True if stream is healthy, False otherwise.
        """
        logger.info("Checking stream: %s", url)

        loop = asyncio.get_running_loop()

        # Check latency
        latency_ok = await loop.run_in_executor(self.executor, self.check_latency, url)
        if not latency_ok:
            logger.warning("%s is slow or unresponsive.", url)
            return False

        # Check if stream is delivering new frames
        stream_active = await loop.run_in_executor(self.executor, self.is_stream_active, url)
        if not stream_active:
            logger.warning("%s appears to be frozen or not updating frames.", url)
            return False

        # Check FPS
        fps_ok = await loop.run_in_executor(self.executor, self.check_fps, url)
        if not fps_ok:
            logger.warning("%s has low FPS or excessive buffering.", url)
            return False

        logger.info("%s is running smoothly.", url)
        return True

    def check_latency(self, url: StreamURL, timeout: float = 5.0) -> bool:
        """
        Check the response time of the video stream.

        Args:
            url: Stream URL to check.
            timeout: Maximum time to wait for response (default: 5.0).

        Returns:
            True if latency is acceptable, False otherwise.
        """
        try:
            start_time = time.time()
            response = requests.get(url, stream=True, timeout=timeout)
            latency = time.time() - start_time
        except requests.RequestException:
            return False
        else:
            # Acceptable latency threshold
            return response.status_code == HTTP_OK and latency < MAX_LATENCY_SECONDS

    def is_stream_active(
        self,
        url: StreamURL,
        check_duration: int = 5,
        frame_interval: int = 1,
    ) -> bool:
        """
        Check if a video stream is delivering new frames.

        Compares consecutive frames to detect motion or changes.

        Args:
            url: Stream URL to check.
            check_duration: How long to check in seconds (default: 5).
            frame_interval: Seconds between frame checks (default: 1).

        Returns:
            True if stream is delivering changing frames, False otherwise.
        """
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            return False

        prev_frame: np.ndarray | None = None
        active = False
        start_time = time.time()

        try:
            while time.time() - start_time < check_duration:
                ret, frame = cap.read()
                if not ret:
                    break

                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if prev_frame is not None:
                    diff = float(np.sum(cv2.absdiff(prev_frame, gray_frame)))
                    # Motion threshold
                    if diff > MOTION_THRESHOLD:
                        active = True
                        break

                prev_frame = gray_frame
                time.sleep(frame_interval)
        finally:
            cap.release()

        return active

    def check_fps(self, url: StreamURL, check_duration: int = 5) -> bool:
        """
        Measure FPS and check for buffering or frozen frames.

        Args:
            url: Stream URL to check.
            check_duration: How long to measure in seconds (default: 5).

        Returns:
            True if FPS is acceptable and frames are changing, False otherwise.
        """
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            return False

        frame_count = 0
        identical_frames = 0
        prev_frame: np.ndarray | None = None
        start_time = time.time()

        try:
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
        finally:
            cap.release()

        fps = frame_count / check_duration if check_duration > 0 else 0
        # Ensure FPS is acceptable and not too many frozen frames
        return fps > MIN_FPS and identical_frames < MAX_IDENTICAL_FRAMES

    async def monitor_streams(self) -> None:
        """
        Periodically check all streams asynchronously.

        Runs indefinitely until interrupted.
        """
        while True:
            tasks = [self.check_stream(url) for url in self.video_urls]
            await asyncio.gather(*tasks)
            logger.info("Waiting for next check...\n")
            await asyncio.sleep(self.check_interval)

    def start_monitoring(self) -> None:
        """
        Start the async monitoring loop.

        Blocks until interrupted with Ctrl+C.
        """
        try:
            asyncio.run(self.monitor_streams())
        except KeyboardInterrupt:
            logger.info("Stopping monitoring...")
        finally:
            self.executor.shutdown()
