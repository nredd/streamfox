"""Tests for the CLI module."""

import pathlib
import tempfile

import pytest
import yaml

from streamfox.cli import load_streams_from_yaml


def test_load_streams_from_yaml() -> None:
    """Test loading streams from YAML file."""
    # Create a temporary YAML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(
            {"streams": ["https://example.com/stream1", "https://example.com/stream2"]},
            f,
        )
        yaml_path = pathlib.Path(f.name)

    try:
        streams = load_streams_from_yaml(yaml_path)
        assert len(streams) == 2
        assert "https://example.com/stream1" in streams
        assert "https://example.com/stream2" in streams
    finally:
        yaml_path.unlink()


def test_load_streams_from_yaml_missing_file() -> None:
    """Test error handling for missing YAML file."""
    with pytest.raises(FileNotFoundError):
        load_streams_from_yaml(pathlib.Path("/nonexistent/file.yaml"))


def test_load_streams_from_yaml_invalid_format() -> None:
    """Test error handling for invalid YAML format."""
    # Create a temporary YAML file with invalid format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"invalid_key": ["url1", "url2"]}, f)
        yaml_path = pathlib.Path(f.name)

    try:
        with pytest.raises(ValueError, match="must contain a 'streams' key"):
            load_streams_from_yaml(yaml_path)
    finally:
        yaml_path.unlink()


def test_load_streams_from_yaml_not_dict() -> None:
    """Test error handling when YAML is not a dictionary."""
    # Create a temporary YAML file that's a list instead of dict
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(["stream1", "stream2"], f)
        yaml_path = pathlib.Path(f.name)

    try:
        with pytest.raises(ValueError, match="must contain a 'streams' key"):
            load_streams_from_yaml(yaml_path)
    finally:
        yaml_path.unlink()
