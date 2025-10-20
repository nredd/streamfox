"""Tests for quality monitoring functionality."""

import time
from unittest.mock import MagicMock, Mock, patch

from streamfox.playback_monitor import PlaybackMonitor
from streamfox.stream_pool import StreamPool
from streamfox.types import QualityThresholds, StreamQualityMetrics


class TestStreamQualityMetrics:
    """Test StreamQualityMetrics class."""

    def test_quality_score_excellent(self):
        """Test quality score calculation for excellent metrics."""
        metrics = StreamQualityMetrics(
            url="http://test.com/stream.m3u8",
            latency_ms=500,
            fps=30,
            is_active=True,
            buffering_detected=False,
            error_count=0,
        )
        score = metrics.quality_score
        assert score > 0.9  # Should be excellent

    def test_quality_score_poor(self):
        """Test quality score calculation for poor metrics."""
        metrics = StreamQualityMetrics(
            url="http://test.com/stream.m3u8",
            latency_ms=5000,
            fps=3,
            is_active=False,
            buffering_detected=True,
            error_count=5,
        )
        score = metrics.quality_score
        assert score < 0.3  # Should be poor

    def test_is_healthy_true(self):
        """Test healthy stream detection."""
        metrics = StreamQualityMetrics(
            url="http://test.com/stream.m3u8",
            latency_ms=1000,
            fps=15,
            is_active=True,
            buffering_detected=False,
            error_count=0,
        )
        thresholds = QualityThresholds()
        assert metrics.is_healthy(thresholds)

    def test_is_healthy_false_buffering(self):
        """Test unhealthy stream detection due to buffering."""
        metrics = StreamQualityMetrics(
            url="http://test.com/stream.m3u8",
            latency_ms=1000,
            fps=15,
            is_active=True,
            buffering_detected=True,
            error_count=0,
        )
        thresholds = QualityThresholds()
        assert not metrics.is_healthy(thresholds)

    def test_is_healthy_false_low_fps(self):
        """Test unhealthy stream detection due to low FPS."""
        metrics = StreamQualityMetrics(
            url="http://test.com/stream.m3u8",
            latency_ms=1000,
            fps=2,
            is_active=True,
            buffering_detected=False,
            error_count=0,
        )
        thresholds = QualityThresholds()
        assert not metrics.is_healthy(thresholds)

    def test_is_healthy_false_high_latency(self):
        """Test unhealthy stream detection due to high latency."""
        metrics = StreamQualityMetrics(
            url="http://test.com/stream.m3u8",
            latency_ms=5000,
            fps=15,
            is_active=True,
            buffering_detected=False,
            error_count=0,
        )
        thresholds = QualityThresholds()
        assert not metrics.is_healthy(thresholds)


class TestQualityThresholds:
    """Test QualityThresholds class."""

    def test_default_values(self):
        """Test default threshold values."""
        thresholds = QualityThresholds()
        assert thresholds.max_latency_ms == 3000.0
        assert thresholds.min_fps == 5.0
        assert thresholds.max_consecutive_errors == 3
        assert thresholds.quality_check_interval_seconds == 10.0
        assert thresholds.switch_threshold_score == 0.3

    def test_custom_values(self):
        """Test custom threshold values."""
        thresholds = QualityThresholds(
            max_latency_ms=2000.0,
            min_fps=10.0,
            max_consecutive_errors=5,
            quality_check_interval_seconds=5.0,
            switch_threshold_score=0.5,
        )
        assert thresholds.max_latency_ms == 2000.0
        assert thresholds.min_fps == 10.0
        assert thresholds.max_consecutive_errors == 5
        assert thresholds.quality_check_interval_seconds == 5.0
        assert thresholds.switch_threshold_score == 0.5


class TestPlaybackMonitor:
    """Test PlaybackMonitor class."""

    @patch("streamfox.playback_monitor.cv2.VideoCapture")
    @patch("streamfox.playback_monitor.requests.get")
    def test_monitor_creation(self, _mock_requests, _mock_cv2):
        """Test creating a playback monitor."""
        url = "http://test.com/stream.m3u8"
        monitor = PlaybackMonitor(url=url, check_interval=1.0)

        assert monitor.url == url
        assert monitor.check_interval == 1.0
        assert not monitor._monitoring
        assert monitor.current_metrics is None

    @patch("streamfox.playback_monitor.cv2.VideoCapture")
    @patch("streamfox.playback_monitor.requests.get")
    def test_monitor_start_stop(self, _mock_requests, _mock_cv2):
        """Test starting and stopping monitor."""
        url = "http://test.com/stream.m3u8"
        monitor = PlaybackMonitor(url=url, check_interval=0.1)

        monitor.start()
        assert monitor._monitoring
        assert monitor._monitor_thread is not None

        time.sleep(0.2)  # Let it run briefly

        monitor.stop()
        assert not monitor._monitoring

    @patch("streamfox.playback_monitor.cv2.VideoCapture")
    @patch("streamfox.playback_monitor.requests.get")
    def test_quality_change_callback(self, mock_requests, mock_cv2):
        """Test quality change callback is invoked."""
        url = "http://test.com/stream.m3u8"
        callback_mock = Mock()

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.return_value = mock_response

        # Mock VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.return_value = mock_cap

        monitor = PlaybackMonitor(
            url=url,
            check_interval=0.1,
            on_quality_change=callback_mock,
        )

        monitor.start()
        time.sleep(0.3)  # Let it run and collect metrics
        monitor.stop()

        # Callback should have been called at least once
        assert callback_mock.call_count >= 1
        # Check that the callback received StreamQualityMetrics
        args = callback_mock.call_args
        assert isinstance(args[0][0], StreamQualityMetrics)


class TestStreamPool:
    """Test StreamPool quality ranking functionality."""

    def test_update_quality_metrics(self):
        """Test updating quality metrics for streams."""
        pool = StreamPool(initial_streams=[], min_pool_size=1)

        metrics = StreamQualityMetrics(
            url="http://test.com/stream1.m3u8",
            latency_ms=1000,
            fps=20,
        )

        pool.update_quality_metrics(metrics)

        assert "http://test.com/stream1.m3u8" in pool.quality_metrics
        assert pool.quality_metrics["http://test.com/stream1.m3u8"] == metrics

    def test_get_quality_score(self):
        """Test getting quality score for a stream."""
        pool = StreamPool(initial_streams=[], min_pool_size=1)

        metrics = StreamQualityMetrics(
            url="http://test.com/stream1.m3u8",
            latency_ms=1000,
            fps=20,
        )
        pool.update_quality_metrics(metrics)

        score = pool.get_quality_score("http://test.com/stream1.m3u8")
        assert score > 0.0
        assert score <= 1.0

    def test_get_quality_score_unknown_stream(self):
        """Test getting quality score for unknown stream returns default."""
        pool = StreamPool(initial_streams=[], min_pool_size=1)

        score = pool.get_quality_score("http://unknown.com/stream.m3u8")
        assert score == 0.5  # Default neutral score

    @patch("streamfox.stream_pool.requests.head")
    def test_get_ranked_streams(self, mock_head):
        """Test getting streams ranked by quality."""
        # Mock successful health checks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        pool = StreamPool(
            initial_streams=[
                "http://test.com/stream1.m3u8",
                "http://test.com/stream2.m3u8",
                "http://test.com/stream3.m3u8",
            ],
            min_pool_size=3,
        )

        # Add quality metrics with different scores
        pool.update_quality_metrics(
            StreamQualityMetrics(
                url="http://test.com/stream1.m3u8",
                latency_ms=500,
                fps=30,
            )
        )
        pool.update_quality_metrics(
            StreamQualityMetrics(
                url="http://test.com/stream2.m3u8",
                latency_ms=2000,
                fps=10,
            )
        )
        pool.update_quality_metrics(
            StreamQualityMetrics(
                url="http://test.com/stream3.m3u8",
                latency_ms=1000,
                fps=20,
            )
        )

        ranked = pool.get_ranked_streams()

        # Should be 3 streams
        assert len(ranked) == 3

        # Check that they're sorted by quality (highest first)
        scores = [score for _, score in ranked]
        assert scores == sorted(scores, reverse=True)

        # stream1 should be first (best quality)
        assert ranked[0][0] == "http://test.com/stream1.m3u8"

    @patch("streamfox.stream_pool.requests.head")
    def test_should_switch_stream(self, mock_head):
        """Test stream switching recommendation."""
        # Mock successful health checks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        pool = StreamPool(
            initial_streams=[
                "http://test.com/stream1.m3u8",
                "http://test.com/stream2.m3u8",
            ],
            min_pool_size=2,
        )

        # Add high quality stream
        pool.update_quality_metrics(
            StreamQualityMetrics(
                url="http://test.com/stream1.m3u8",
                latency_ms=500,
                fps=30,
            )
        )

        # Current stream has poor quality
        current_url = "http://test.com/stream2.m3u8"
        current_quality = 0.2

        switch_to = pool.should_switch_stream(current_url, current_quality)

        # Should recommend switching to stream1
        assert switch_to == "http://test.com/stream1.m3u8"

    @patch("streamfox.stream_pool.requests.head")
    def test_should_not_switch_if_current_is_best(self, mock_head):
        """Test no switch recommended if current stream is best."""
        # Mock successful health checks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        pool = StreamPool(
            initial_streams=[
                "http://test.com/stream1.m3u8",
                "http://test.com/stream2.m3u8",
            ],
            min_pool_size=2,
        )

        # Add quality metrics
        pool.update_quality_metrics(
            StreamQualityMetrics(
                url="http://test.com/stream1.m3u8",
                latency_ms=500,
                fps=30,
            )
        )

        # Current stream is already the best
        current_url = "http://test.com/stream1.m3u8"
        current_quality = 0.9

        switch_to = pool.should_switch_stream(current_url, current_quality)

        # Should not recommend switching
        assert switch_to is None
