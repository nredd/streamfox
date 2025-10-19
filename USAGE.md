# Usage Guide

## Running Streamfox

### Option 1: Activate venv first (recommended)

```bash
source .venv/bin/activate
streamfox --url https://www.nasa.gov/live
```

### Option 2: Use make commands

```bash
make run                                    # Default
make run-url URL=https://www.nasa.gov/live # Specific URL
make run-debug                              # Debug mode
make monitor                                # Quality monitoring
```

### Option 3: Use uv run

```bash
uv run streamfox --url https://www.nasa.gov/live
```

## Examples

### Play a specific stream

```bash
streamfox --url https://example.com/stream.m3u8
```

### Use configuration file

Edit `streams.yaml`:
```yaml
streams:
  - https://www.nasa.gov/live
  - https://example.com/stream.m3u8
```

Then run:
```bash
streamfox
```

### Monitor stream quality

```bash
streamfox --monitor --url https://example.com/stream.m3u8
```

### Debug mode with deep crawling

```bash
streamfox --debug --max-depth 5 --url https://example.com
```

### Custom config file

```bash
streamfox --config /path/to/my-streams.yaml
```

## Command-Line Options

```
--url, -u URL           Specific stream URL to watch
--monitor, -m           Monitor streams instead of playing
--debug, -d             Enable debug logging
--max-depth N           Max crawl depth (default: 2)
--config, -c PATH       Path to streams.yaml
--headless              Run browser in headless mode (default)
```

## Video Player Support

Streamfox auto-detects and uses the first available player:
1. mpv (recommended)
2. vlc
3. ffplay

### Install a player

**macOS:**
```bash
brew install mpv
```

**Linux:**
```bash
sudo apt install mpv  # Debian/Ubuntu
sudo dnf install mpv  # Fedora
```

## Legitimate Stream Sources

**Legal streaming options:**
- NASA TV: `https://www.nasa.gov/live`
- Your own streaming servers
- Authorized streaming services you subscribe to

**For sports (like UFC):**
- ESPN+ (official UFC streams in US)
- UFC Fight Pass (official)
- DAZN, BT Sport, etc. (depending on region)

## Troubleshooting

**"No video player found"**
```bash
brew install mpv  # or apt/dnf install mpv
```

**"ChromeDriver not found"**
```bash
# Should auto-install, but if not:
brew install chromedriver
```

**"No streams found"**
```bash
# Try debug mode to see what's happening
streamfox --debug --url https://example.com

# Or increase crawl depth
streamfox --max-depth 5 --url https://example.com
```

**Streams are slow/buffering**
```bash
# Use monitor mode to check quality
streamfox --monitor --url https://example.com/stream.m3u8
```
