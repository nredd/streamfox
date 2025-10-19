"""
Streamfox - Robust stream crawler and player for live video streams.

This package provides tools to discover, monitor, and play video streams
with automatic failover and quality monitoring.
"""

from .crawler import VideoCrawler
from .monitor import AsyncStreamMonitor
from .playback_monitor import PlaybackMonitor
from .player import StreamPlayer
from .stream_pool import StreamPool
from .types import QualityThresholds, StreamQualityMetrics

__version__ = "0.1.0"
__all__ = [
    "AsyncStreamMonitor",
    "PlaybackMonitor",
    "QualityThresholds",
    "StreamPlayer",
    "StreamPool",
    "StreamQualityMetrics",
    "VideoCrawler",
]
