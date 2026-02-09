# Env Snapshot Tool

[中文](./README_zh.md) | English

A command-line tool to snapshot your current Python environment dependencies into a UV-compatible `pyproject.toml` file.

## Main Features

For complex projects like **ComfyUI** that heavily rely on plugins, the standard `uv.lock` mechanism often **mixes core component dependencies with user plugin dependencies**. It also tends to **lock platform-specific binary versions** (e.g., Windows pre-built packages), making it difficult to reproduce the environment on other systems like Linux. This tool leverages the `optional-dependencies` feature of `pyproject.toml` to achieve **automatic layering** and **on-demand restoration**, significantly improving the distribution experience for cross-platform integration bundles:

- **🛡️ Dependency Isolation**: Automatically separates `requirements.txt` (core) from `uv pip install` (plugins) to keep environments clean.
- **🔌 Dynamic Platform Adaptation**: Automatically populates Index URLs for libraries like PyTorch based on the currently installed version.
- **📦 Compiled Dependency Isolation**: Locally compiled packages are grouped into `user-compiled` to maintain environment reproducibility.
- **🚀 Flexible Restoration**: Restore only the core environment or include specific plugin groups, ensuring compatibility across different hardware platforms (Windows/Linux).

## Installation

Install globally using `uv tool`:

```bash
uv tool install .
```

Or install into the current environment:

```bash
uv pip install .
```

## Usage

### 1. Create Environment Snapshot

Run the following command to save the current environment state to `pyproject.snapshot.toml`:

```bash
New-EnvSnapshot -o pyproject.snapshot.toml
```

### 2. Restore Environment

1. Rename the snapshot to `pyproject.toml`:
   ```bash
   mv pyproject.toml pyproject.origin.toml
   mv pyproject.snapshot.toml pyproject.toml
   ```
2. Install dependencies using `uv`:

#### Restore Core Dependencies Only (Core Only)
Restore the environment to the dependencies defined in the original `requirements.txt`:
```bash
uv sync
```

#### Restore Core + User Plugins (Core + User Downloaded)
1. Command format:
   ```bash
   uv pip install . [extra-group]
   ```
2. Restore core dependencies and additional plugins downloaded by the user:
```bash
uv pip install . --extra user-download
```

#### Full Restoration (All Dependencies)
Install all groups, including locally compiled components:
```bash
uv pip install . --all-extras
```

### 3. Options

```bash
env-snapshot [OPTIONS]
```

- `--base-toml PATH`      : Path to the base `pyproject.toml` template (Default: Bundled)
- `--requirements PATH`   : Path to `requirements.txt` (Default: `YOUR_WORK_DIR/requirements.txt`)
- `-o, --output PATH`     : Path to the output snapshot file (Default: `YOUR_WORK_DIR/pyproject.snapshot.toml`)
- `--help`                : Show help message

## Development

This project uses `hatch` as the build backend and is designed for the `uv` tool.

```bash
# Create a virtual environment with uv
uv venv

# Activate the environment (Windows)
.venv\Scripts\activate

# Install in editable mode
uv pip install -e .
```

