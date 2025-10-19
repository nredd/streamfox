"""Tests for the async stream monitor."""

import pytest

from streamfox.monitor import AsyncStreamMonitor


def test_monitor_initialization() -> None:
    """Test that the monitor initializes correctly."""
    urls = ["https://example.com/stream1.m3u8", "https://example.com/stream2.mp4"]
    monitor = AsyncStreamMonitor(urls, check_interval=5, max_workers=3)

    assert len(monitor.video_urls) == 2
    assert monitor.check_interval == 5
    assert monitor.executor is not None


def test_monitor_with_set_urls() -> None:
    """Test that monitor works with set of URLs."""
    urls = {"https://example.com/stream1.m3u8", "https://example.com/stream2.mp4"}
    monitor = AsyncStreamMonitor(urls)

    # Should convert set to list
    assert len(monitor.video_urls) == 2
    assert isinstance(monitor.video_urls, list)


@pytest.mark.asyncio
async def test_monitor_check_stream_invalid_url() -> None:
    """Test monitoring an invalid URL."""
    monitor = AsyncStreamMonitor(["https://invalid-url-that-does-not-exist.com"])

    # Should return False for invalid URLs
    result = await monitor.check_stream("https://invalid-url-that-does-not-exist.com")

    # Expecting False since the URL is invalid
    assert result is False


def test_monitor_check_latency_invalid() -> None:
    """Test latency check with invalid URL."""
    monitor = AsyncStreamMonitor([])

    # Use a definitely unreachable URL (reserved test domain)
    result = monitor.check_latency("https://192.0.2.1:9999/nonexistent")

    # Should return False for unreachable URLs
    assert result is False
