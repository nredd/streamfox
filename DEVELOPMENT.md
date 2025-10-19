# Development Guide

Quick reference for developing Streamfox.

## Setup

```bash
# Install everything
make install

# Activate venv (optional - make commands work without this)
source .venv/bin/activate
```

## Virtual Environment

All `make` commands automatically use `.venv/`:

```bash
make test      # Uses .venv automatically
make format    # Uses .venv automatically
make run       # Uses .venv automatically
```

You only need to activate manually for direct Python commands:

```bash
source .venv/bin/activate
python -m pytest
streamfox --help
```

### Venv Commands

```bash
make venv        # Create venv only
make info        # Show venv status
make clean-venv  # Remove venv
make clean-all   # Clean everything
```

## Daily Workflow

```bash
# Make changes...

make format      # Format code
make lint        # Lint code
make test        # Run tests
make all         # Full CI check
```

## Testing

```bash
make test           # With coverage
make test-fast      # Without coverage (faster)
uv run pytest -x    # Stop on first failure
```

## Dependency Management

All dependencies in `pyproject.toml`:

```bash
# Add dependency to [project.dependencies]
# Then:
uv sync

# Add dev dependency to [project.optional-dependencies.dev]
# Then:
uv sync --all-extras

# Update all deps
uv sync --upgrade
```

## Common Issues

**"Virtual environment not found"**
```bash
make install
```

**"Command not found: streamfox"**
```bash
# Option 1: Activate venv
source .venv/bin/activate

# Option 2: Use make
make run

# Option 3: Use uv run
uv run streamfox
```

**Outdated dependencies**
```bash
uv sync --upgrade
```

## Tips

- Use `make` commands - they handle venv automatically
- Activate venv for interactive work
- Check `make info` for quick diagnostics
- Run `make all` before committing
