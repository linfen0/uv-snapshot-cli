# Env Snapshot Tool

A command-line tool to snapshot your current Python environment dependencies into a UV-compatible `pyproject.toml` file.

## Features

- **Snapshots dependencies**: Captures installed packages and versions.
- **Categorizes dependencies**: Splits packages into `project-dependencies` (from `pyproject.toml` or `requirements.txt`), `optional-dependencies`, and identifies `user-compiled` or `user-downloaded` packages.
- **Resolves PyTorch URLs**: Automatically detects the installed PyTorch CUDA version and updates the `uv` index URL accordingly.
- **UV Compatible**: Generates a `pyproject.toml` configured for use with [uv](https://github.com/astral-sh/uv).

## Installation

```bash
pip install .
```

## Usage

```bash
New-EnvSnapshot BASE_TOML REQUIREMENTS_TXT [OPTIONS]
```

### Arguments

- `BASE_TOML`: Path to the base `pyproject.toml` file containing your project's static configuration.
- `REQUIREMENTS_TXT`: Path to a `requirements.txt` file (if any).

### Options

- `-o, --output PATH`: Output file path. Defaults to `pyproject.snapshot.toml`.
- `--help`: Show this message and exit.

### Example

```bash
New-EnvSnapshot ./pyproject.toml ./requirements.txt -o my_snapshot.toml
```

## Development

This project uses `hatch` as the build backend.

```bash
# Install in editable mode
pip install -e .
```
