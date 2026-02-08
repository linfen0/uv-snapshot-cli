# Env Snapshot Tool

[中文](./README_zh.md) | English

A command-line tool to snapshot your current Python environment dependencies into a UV-compatible `pyproject.toml` file.

## Features

- **Snapshots dependencies**: Captures installed packages and versions.
- **Categorizes dependencies**: Splits packages into `project-dependencies` (from `pyproject.toml` or `requirements.txt`), `optional-dependencies`, and identifies `user-compiled` or `user-downloaded` packages.
- **Resolves PyTorch URLs**: Automatically detects the installed PyTorch CUDA version and updates the `uv` index URL accordingly.
- **UV Compatible**: Generates a `pyproject.toml` configured for use with [uv](https://github.com/astral-sh/uv).

## Installation

Install using `uv tool` for global availability:

```bash
uv tool install .
```

Or install into the current environment:

```bash
uv pip install .
```

## Usage

```bash
# Use default base.toml (bundled) and requirements.txt (current dir)
env-snapshot

# Specify custom files
env-snapshot --base-toml ./custom_base.toml --requirements ./reqs.txt -o my_snapshot.toml
```

### Options

- `--base-toml PATH`: Path to the base `pyproject.toml` file. Defaults to bundled base.
- `--requirements PATH`: Path to a `requirements.txt` file. Defaults to `requirements.txt`.
- `-o, --output PATH`: Output file path. Defaults to `pyproject.snapshot.toml`.
- `--help`: Show this message and exit.

## Development

This project uses `hatch` as the build backend and is fully compatible with `uv`.

```bash
# Create a virtual environment with uv
uv venv

# Activate the environment (Windows)
.venv\Scripts\activate

# Install in editable mode
uv pip install -e .
```
