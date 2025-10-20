# Streamfox

A robust, production-quality stream crawler and player for live video streams. Built with Python, featuring automatic failover, quality monitoring, and concurrent stream discovery.

## Features

- **Smart Crawling**: Uses Selenium to discover video streams by analyzing both DOM and network traffic
- **Automatic Failover**: Seamlessly switches between streams if one fails
- **Real-Time Quality Monitoring**: Monitors latency, FPS, and buffering during playback
- **Intelligent Stream Switching**: Automatically switches to higher quality streams when available
- **Quality-Based Stream Ranking**: Prioritizes streams by measured performance metrics
- **Configurable Thresholds**: Customize quality requirements and switching behavior
- **Multiple Players**: Supports mpv, vlc, and ffplay
- **Type-Safe**: Comprehensive type hints throughout the codebase
- **Well-Tested**: Full test coverage with pytest
- **Production-Ready**: Clean, documented, and linted code

## Requirements

- **Python 3.13+** (uv will download automatically if needed)
- Chrome/Chromium browser (for crawling)
- A video player: mpv (recommended), vlc, or ffplay

## Installation

### Quick Start

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone <your-repo-url>
cd streamfox
make install

# Activate venv (optional - make commands work without this)
source .venv/bin/activate
```

**Note**: `uv` automatically downloads Python 3.13 if you don't have it. All configuration is in `pyproject.toml` - no `.python-version` file needed.

## Quick Start

After installation, activate the venv and run:

```bash
# Activate venv
source .venv/bin/activate

# Show help
streamfox --help

# Play a stream
streamfox --url https://www.nasa.gov/live

# Or use make (no activation needed)
make run-url URL=https://www.nasa.gov/live
```

### Install a video player

**macOS:**
```bash
brew install mpv
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install mpv
```

**Linux (RHEL/Fedora):**
```bash
sudo dnf install mpv
```

## Configuration

Create a `streams.yaml` file in the project root:

```yaml
streams:
  # Add your legitimate stream URLs here
  - https://www.nasa.gov/live
  - https://example.com/your-stream.m3u8
```

**Important**: Only use streams you are authorized to access. Respect copyright and terms of service.

## Usage

### Command Line

```bash
# Play streams from streams.yaml with automatic quality monitoring
streamfox

# Play a specific stream URL
streamfox --url https://example.com/stream.m3u8

# Disable quality monitoring during playback
streamfox --disable-quality-monitoring

# Monitor streams for quality without playing
streamfox --monitor

# Customize quality thresholds
streamfox --max-latency 2000 --min-fps 10 --quality-check-interval 5

# Set switch threshold (quality difference needed to trigger switch)
streamfox --switch-threshold 0.5

# Enable debug logging
streamfox --debug

# Set maximum crawl depth
streamfox --max-depth 3

# Continuous playback with larger pool of backup streams
streamfox --continuous --pool-size 5
```

### Using Make

```bash
# Run with default configuration
make run

# Run with debug logging
make run-debug

# Run with a specific URL
make run-url URL=https://example.com/stream.m3u8

# Run in monitor mode
make monitor
```

### Programmatic Usage

```python
from streamfox import (
    VideoCrawler,
    StreamPlayer,
    StreamPool,
    PlaybackMonitor,
    QualityThresholds,
)

# Crawl a site for video streams
crawler = VideoCrawler("https://example.com", max_depth=2)
crawler.crawl()
print(f"Found {len(crawler.video_urls)} streams")
crawler.close()

# Configure quality thresholds
thresholds = QualityThresholds(
    max_latency_ms=2000.0,  # Max acceptable latency
    min_fps=10.0,           # Min acceptable FPS
    quality_check_interval_seconds=5.0,  # Check every 5s
    switch_threshold_score=0.4,  # Switch if 0.4+ better
)

# Create a pool of streams with quality tracking
stream_pool = StreamPool(
    initial_streams=list(crawler.video_urls),
    min_pool_size=3,
    quality_thresholds=thresholds,
)
stream_pool.start_monitoring()

# Play streams with automatic quality-based switching
player = StreamPlayer(
    stream_urls=list(crawler.video_urls),
    continuous=True,
    stream_pool=stream_pool,
    enable_quality_monitoring=True,
    quality_thresholds=thresholds,
)

try:
    player.play()
finally:
    stream_pool.stop_monitoring()

# Or monitor a single stream during playback
def on_quality_change(metrics):
    print(f"Quality: {metrics.quality_score:.2f}")
    print(f"  Latency: {metrics.latency_ms}ms")
    print(f"  FPS: {metrics.fps}")
    print(f"  Active: {metrics.is_active}")

monitor = PlaybackMonitor(
    url="https://example.com/stream.m3u8",
    thresholds=thresholds,
    check_interval=10.0,
    on_quality_change=on_quality_change,
)
monitor.start()
# ... monitor runs in background ...
monitor.stop()
```

## Development

### Setup Development Environment

```bash
# Create venv and install all dependencies (including dev tools)
make install

# Activate the virtual environment (optional - make commands work without this)
source .venv/bin/activate
```

**Note**: All `make` commands automatically use the virtual environment via `uv run`. You don't need to activate it manually when using `make`.

### Dependencies

All dependencies are managed in `pyproject.toml`:

```toml
[project]
dependencies = [
    "beautifulsoup4>=4.12.0",
    "numpy>=1.24.0",
    "opencv-python>=4.8.0",
    # ... etc
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
    # ... etc
]
```

To add dependencies:
1. Edit `pyproject.toml`
2. Run `uv sync` (runtime deps) or `uv sync --all-extras` (dev deps)

**No `requirements.txt` needed** - uv uses `pyproject.toml` directly.

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type check
make type

# Run tests with coverage
make test

# Clean all artifacts (cache, venv, logs, untracked files)
make clean

# Run everything (format, lint, type check, test)
make all
```

### Project Structure

```
streamfox/
├── src/streamfox/              # Source code
│   ├── __init__.py             # Package initialization
│   ├── cli.py                  # Command-line interface
│   ├── crawler.py              # Video stream crawler
│   ├── monitor.py              # Async stream quality monitor
│   ├── playback_monitor.py     # Real-time playback quality monitor
│   ├── player.py               # Stream player with quality-based switching
│   ├── stream_pool.py          # Stream pool with quality ranking
│   └── types.py                # Type definitions (metrics, thresholds)
├── tests/                      # Test suite
│   ├── test_cli.py
│   ├── test_crawler.py
│   ├── test_monitor.py
│   ├── test_player.py
│   └── test_quality_monitoring.py  # Quality monitoring tests
├── pyproject.toml              # Project configuration
├── Makefile                    # Development commands
├── streams.yaml                # Stream configuration
└── README.md                   # This file
```

## How It Works

### 1. Crawling
The `VideoCrawler` uses Selenium with Chrome to:
- Load web pages and execute JavaScript
- Monitor network traffic for video URLs
- Parse the DOM for `<video>` tags and iframes
- Recursively follow links up to a specified depth
- Detect common streaming formats (.m3u8, .mp4, .ts, .mpd, .webm)

### 2. Playing with Quality Monitoring
The `StreamPlayer`:
- Detects available video players on your system (mpv, vlc, ffplay)
- Plays streams with automatic failover to backup streams
- **Monitors stream quality in real-time** during playback
- **Automatically switches to higher quality streams** when available
- Tracks latency, FPS, buffering, and frame activity
- Maintains a pool of validated backup streams
- Handles user interrupts gracefully

**Quality Metrics Tracked:**
- **Latency**: HTTP response time (target: < 1000ms excellent, > 3000ms poor)
- **FPS**: Frames per second (target: > 24fps excellent, < 5fps poor)
- **Buffering**: Detects frozen/identical frames
- **Stream Activity**: Verifies frames are updating with motion detection

**Quality Scoring:**
Streams are scored from 0.0 (worst) to 1.0 (best) based on:
- Latency (40% weight)
- FPS (30% weight)
- Activity (20% weight)
- Error count (10% weight)

**Automatic Switching:**
- Quality is checked every 10 seconds (configurable)
- Switches to better stream if quality difference exceeds threshold (default: 0.3)
- Seamlessly terminates poor stream and starts better one
- No manual intervention required

### 3. Monitoring
The `AsyncStreamMonitor`:
- Checks stream latency (response time)
- Verifies frames are updating (not frozen)
- Measures FPS and detects buffering
- Runs checks concurrently for all streams
- Used for monitor-only mode (`--monitor` flag)

## Troubleshooting

### "No video player found"
Install mpv, vlc, or ffplay as described in the Installation section.

### "ChromeDriver not found"
The webdriver-manager package should automatically download ChromeDriver. If it fails:
```bash
brew install chromedriver  # macOS
# or check: https://chromedriver.chromium.org/
```

### Streams not detected
- Try increasing `--max-depth` for deeper crawling
- Use `--debug` to see detailed logs
- Some sites use complex JavaScript that may be hard to parse
- Consider providing direct .m3u8 URLs if you know them

### Type checking errors
```bash
# Install type stubs
uv sync --all-extras
```

## Testing

```bash
# Run all tests
make test

# Run specific test file
uv run pytest tests/test_crawler.py -v

# Run with coverage
uv run pytest --cov=src/streamfox --cov-report=html
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the full test suite: `make all`
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Disclaimer

This tool is intended for accessing streams you are authorized to view. Users are responsible for ensuring their use complies with applicable laws, terms of service, and copyright regulations. The authors assume no liability for misuse.

## Acknowledgments

Built with:
- [Selenium](https://www.selenium.dev/) for browser automation
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- [OpenCV](https://opencv.org/) for stream quality analysis
- [uv](https://github.com/astral-sh/uv) for dependency management
- [ruff](https://github.com/astral-sh/ruff) for linting and formatting
