"""
Repository path helpers.

Centralizes path defaults so scripts do not depend on one deployment path.
"""

from pathlib import Path
import os


REPO_ROOT = Path(__file__).resolve().parents[1]


def repo_path(*parts: str) -> Path:
    """Return an absolute path under the repository root."""
    return REPO_ROOT.joinpath(*parts)


def env_path(name: str, default: str | Path) -> Path:
    """Resolve a path from an environment variable, falling back to default."""
    value = os.environ.get(name)
    return Path(value).expanduser() if value else Path(default).expanduser()


def brussels_data_dir() -> Path:
    """Default Brussels trajectory data directory."""
    local_data = repo_path("data")
    return env_path("FLOW_ANALYTICS_DATA_BRUSSELS", local_data if local_data.exists() else "/home/ubuntu/data/uploads/objects/clean")


def output_root() -> Path:
    """Default results root for generated outputs."""
    return env_path("FLOW_ANALYTICS_OUTPUT_ROOT", repo_path("results"))


def default_config_path() -> Path:
    """Default master config path."""
    return repo_path("config.yaml")
