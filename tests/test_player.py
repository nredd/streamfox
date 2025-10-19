"""Tests for the stream player."""

import subprocess
from unittest.mock import MagicMock, Mock, patch

from streamfox.player import StreamPlayer


def test_player_initialization() -> None:
    """Test that the player initializes correctly."""
    urls = ["https://example.com/stream1.m3u8", "https://example.com/stream2.mp4"]
    player = StreamPlayer(urls)

    assert len(player.stream_urls) == 2
    assert player.current_index == 0
    assert player.process is None


def test_player_with_set_urls() -> None:
    """Test that player works with set of URLs."""
    urls = {"https://example.com/stream1.m3u8", "https://example.com/stream2.mp4"}
    player = StreamPlayer(urls)

    # Should convert set to list
    assert len(player.stream_urls) == 2
    assert isinstance(player.stream_urls, list)


def test_player_build_command_mpv() -> None:
    """Test mpv command building."""
    player = StreamPlayer([])
    cmd = player._build_player_command("mpv", "https://example.com/stream.m3u8")

    assert cmd == ["mpv", "https://example.com/stream.m3u8"]


def test_player_build_command_vlc() -> None:
    """Test vlc command building."""
    player = StreamPlayer([])
    cmd = player._build_player_command("vlc", "https://example.com/stream.m3u8")

    assert cmd == ["vlc", "https://example.com/stream.m3u8"]


def test_player_build_command_ffplay() -> None:
    """Test ffplay command building."""
    player = StreamPlayer([])
    cmd = player._build_player_command("ffplay", "https://example.com/stream.m3u8")

    assert cmd == ["ffplay", "-autoexit", "https://example.com/stream.m3u8"]


def test_player_empty_urls() -> None:
    """Test player behavior with no URLs."""
    player = StreamPlayer([])

    assert len(player.stream_urls) == 0
    # play() should handle this gracefully
    # (tested more thoroughly in integration tests)


def test_find_available_player_mpv_found() -> None:
    """Test finding mpv when it's available."""
    player = StreamPlayer([])

    with patch("subprocess.run") as mock_run:
        # Mock mpv being found
        mock_run.return_value = Mock(returncode=0)
        result = player._find_available_player()

        assert result == "mpv"
        mock_run.assert_called_once_with(
            ["which", "mpv"],
            capture_output=True,
            text=True,
            check=False,
        )


def test_find_available_player_vlc_found() -> None:
    """Test finding vlc when mpv is not available but vlc is."""
    player = StreamPlayer([])

    with patch("subprocess.run") as mock_run:
        # Mock mpv not found, vlc found
        def side_effect(cmd, *args, **kwargs):  # noqa: ARG001
            if "mpv" in cmd:
                return Mock(returncode=1)
            if "vlc" in cmd:
                return Mock(returncode=0)
            return Mock(returncode=1)

        mock_run.side_effect = side_effect
        result = player._find_available_player()

        assert result == "vlc"


def test_find_available_player_none_found() -> None:
    """Test when no player is available."""
    player = StreamPlayer([])

    with patch("subprocess.run") as mock_run:
        # Mock all players not found
        mock_run.return_value = Mock(returncode=1)
        result = player._find_available_player()

        assert result is None


def test_play_no_player_available() -> None:
    """Test play() when no video player is installed."""
    urls = ["https://example.com/stream.m3u8"]
    player = StreamPlayer(urls)

    with patch.object(player, "_find_available_player", return_value=None):
        # Should log error and return gracefully
        player.play()
        # No exception should be raised


def test_play_no_urls() -> None:
    """Test play() with empty URL list."""
    player = StreamPlayer([])

    with patch.object(player, "_find_available_player", return_value="mpv"):
        # Should log error and return gracefully
        player.play()
        # No exception should be raised


@patch("subprocess.Popen")
def test_play_single_url_success(mock_popen: MagicMock) -> None:
    """Test playing a single URL successfully."""
    urls = ["https://example.com/stream.m3u8"]
    player = StreamPlayer(urls)

    # Mock successful playback
    mock_process = Mock()
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process

    with patch.object(player, "_find_available_player", return_value="mpv"):
        player.play()

    # Verify player was called with correct arguments
    mock_popen.assert_called_once_with(
        ["mpv", "https://example.com/stream.m3u8"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    mock_process.wait.assert_called_once()


@patch("subprocess.Popen")
def test_play_failover_to_next_url(mock_popen: MagicMock) -> None:
    """Test automatic failover to next URL when first one fails."""
    urls = [
        "https://example.com/bad_stream.m3u8",
        "https://example.com/good_stream.m3u8",
    ]
    player = StreamPlayer(urls)

    # Mock first stream failing (non-zero exit), second succeeding
    mock_process1 = Mock()
    mock_process1.wait.return_value = 1  # Failure

    mock_process2 = Mock()
    mock_process2.wait.return_value = 0  # Success

    mock_popen.side_effect = [mock_process1, mock_process2]

    with patch.object(player, "_find_available_player", return_value="mpv"):
        player.play()

    # Both URLs should have been tried
    assert mock_popen.call_count == 2
    # After playing 2 streams, current_index points to next stream (would be 2)
    assert player.current_index == 2


@patch("subprocess.Popen")
def test_play_all_urls_fail(mock_popen: MagicMock) -> None:
    """Test when all stream URLs fail."""
    urls = [
        "https://example.com/stream1.m3u8",
        "https://example.com/stream2.m3u8",
    ]
    player = StreamPlayer(urls)

    # Mock all streams failing
    mock_process = Mock()
    mock_process.wait.return_value = 1  # Failure
    mock_popen.return_value = mock_process

    with patch.object(player, "_find_available_player", return_value="mpv"):
        player.play()

    # All URLs should have been attempted
    assert mock_popen.call_count == 2
    assert player.current_index == 2  # Past the last index


@patch("subprocess.Popen")
def test_play_keyboard_interrupt(mock_popen: MagicMock) -> None:
    """Test handling of keyboard interrupt during playback."""
    urls = ["https://example.com/stream.m3u8"]
    player = StreamPlayer(urls)

    # Mock keyboard interrupt
    mock_process = Mock()
    mock_process.wait.side_effect = KeyboardInterrupt()
    mock_process.terminate = Mock()
    mock_popen.return_value = mock_process

    with patch.object(player, "_find_available_player", return_value="mpv"):
        player.play()

    # Process should be terminated
    mock_process.terminate.assert_called_once()


@patch("subprocess.Popen")
def test_play_exception_during_playback(mock_popen: MagicMock) -> None:
    """Test handling of exceptions during playback."""
    urls = [
        "https://example.com/stream1.m3u8",
        "https://example.com/stream2.m3u8",
    ]
    player = StreamPlayer(urls)

    # Mock exception on first stream, success on second
    mock_process1 = Mock()
    mock_process1.wait.side_effect = Exception("Test error")

    mock_process2 = Mock()
    mock_process2.wait.return_value = 0

    mock_popen.side_effect = [mock_process1, mock_process2]

    with patch.object(player, "_find_available_player", return_value="mpv"):
        player.play()

    # Should try next URL after exception
    assert mock_popen.call_count == 2


def test_stop_with_running_process() -> None:
    """Test stopping a running player process."""
    player = StreamPlayer([])

    # Mock a running process
    mock_process = Mock()
    player.process = mock_process

    player.stop()

    # Process should be terminated and cleared
    mock_process.terminate.assert_called_once()
    assert player.process is None


def test_stop_without_running_process() -> None:
    """Test stop() when no process is running."""
    player = StreamPlayer([])

    # Should not raise any exception
    player.stop()
    assert player.process is None
