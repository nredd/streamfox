"""
Streamfox - Robust stream crawler and player for live video streams.

This package provides tools to discover, monitor, and play video streams
with automatic failover and quality monitoring.
"""

from .crawler import VideoCrawler
from .monitor import AsyncStreamMonitor
from .player import StreamPlayer

__version__ = "0.1.0"
__all__ = ["AsyncStreamMonitor", "StreamPlayer", "VideoCrawler"]
