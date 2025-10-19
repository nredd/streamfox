"""Tests for the stream player."""

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
