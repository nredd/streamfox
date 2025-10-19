# Streamfox

A robust, production-quality stream crawler and player for live video streams. Built with Python, featuring automatic failover, quality monitoring, and concurrent stream discovery.

## Features

- **Smart Crawling**: Uses Selenium to discover video streams by analyzing both DOM and network traffic
- **Automatic Failover**: Seamlessly switches between streams if one fails
- **Quality Monitoring**: Asynchronous monitoring of stream latency, FPS, and frame updates
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

See [USAGE.md](USAGE.md) for detailed examples.

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
# Play streams from streams.yaml
streamfox

# Play a specific stream URL
streamfox --url https://example.com/stream.m3u8

# Monitor streams for quality (doesn't play)
streamfox --monitor

# Enable debug logging
streamfox --debug

# Set maximum crawl depth
streamfox --max-depth 3
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
from streamfox import VideoCrawler, StreamPlayer, AsyncStreamMonitor

# Crawl a site for video streams
crawler = VideoCrawler("https://example.com", max_depth=2)
crawler.crawl()
print(f"Found {len(crawler.video_urls)} streams")
crawler.close()

# Play streams with automatic failover
player = StreamPlayer(crawler.video_urls)
player.play()

# Monitor stream quality
monitor = AsyncStreamMonitor(crawler.video_urls, check_interval=10)
monitor.start_monitoring()
```

## Development

### Setup Development Environment

```bash
# Create venv and install all dependencies (including dev tools)
make install

# Activate the virtual environment
source .venv/bin/activate

# Or use the dev target for one-command setup
make dev
```

### Virtual Environment Management

```bash
# Create virtual environment only
make venv

# Show activation instructions
make activate

# Show venv and package information
make info

# Remove virtual environment
make clean-venv

# Clean everything (artifacts + venv)
make clean-all
```

**Note**: All `make` commands automatically use the virtual environment. You don't need to activate it manually when using `make`.

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

# Run tests without coverage (faster)
make test-fast

# Run everything (format, lint, type check, test)
make all
```

### Project Structure

```
streamfox/
├── src/streamfox/         # Source code
│   ├── __init__.py        # Package initialization
│   ├── cli.py             # Command-line interface
│   ├── crawler.py         # Video stream crawler
│   ├── monitor.py         # Async stream quality monitor
│   ├── player.py          # Stream player with failover
│   └── types.py           # Type definitions
├── tests/                 # Test suite
│   ├── test_cli.py
│   ├── test_crawler.py
│   ├── test_monitor.py
│   └── test_player.py
├── pyproject.toml         # Project configuration
├── Makefile              # Development commands
├── streams.yaml          # Stream configuration
└── README.md             # This file
```

## How It Works

### 1. Crawling
The `VideoCrawler` uses Selenium with Chrome to:
- Load web pages and execute JavaScript
- Monitor network traffic for video URLs
- Parse the DOM for `<video>` tags and iframes
- Recursively follow links up to a specified depth
- Detect common streaming formats (.m3u8, .mp4, .ts, .mpd, .webm)

### 2. Playing
The `StreamPlayer`:
- Detects available video players on your system
- Plays streams in order
- Automatically switches to the next stream if one fails
- Handles user interrupts gracefully

### 3. Monitoring
The `AsyncStreamMonitor`:
- Checks stream latency (response time)
- Verifies frames are updating (not frozen)
- Measures FPS and detects buffering
- Runs checks concurrently for all streams

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
