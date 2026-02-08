# Env Snapshot Tool

[English](./README.md) | 中文

一个命令行工具，用于将当前 Python 环境依赖项快照到兼容 UV 的 `pyproject.toml` 文件中。

## 功能特性

- **依赖快照**：捕获已安装的包及其版本。
- **依赖分类**：将包分为 `project-dependencies`（来自 `base_pyproject.toml` 或 `requirements.txt`）、`optional-dependencies`，并识别 `user-compiled`（用户编译）或 `user-downloaded`（用户下载）的包。
- **解析 PyTorch URL**：自动检测安装的 PyTorch CUDA 版本，并相应地更新 `uv` 索引 URL。
- **兼容 UV**：生成配置为与 [uv](https://github.com/astral-sh/uv) 一起使用的 `pyproject.toml`。

## 安装

使用 `uv tool` 进行全局安装：

```bash
uv tool install .
```

或者安装到当前环境中：

```bash
uv pip install .
```

## 使用方法

```bash
# 使用默认的 base.toml (内置) 和 requirements.txt (当前目录)
env-snapshot

# 指定自定义文件
env-snapshot --base-toml ./custom_base.toml --requirements ./reqs.txt -o my_snapshot.toml
```

### 选项

- `--base-toml PATH`: 基础 `pyproject.toml` 文件的路径。默认使用包内自带的基础配置。
- `--requirements PATH`: `requirements.txt` 文件的路径。默认为当前目录下的 `requirements.txt`。
- `-o, --output PATH`: 输出文件路径。默认为 `pyproject.snapshot.toml`。
- `--help`: 显示此帮助信息并退出。

## 开发

本项目使用 `hatch` 作为构建后端，并完全兼容 `uv`。

```bash
# 使用 uv 创建虚拟环境
uv venv

# 激活环境 (Windows)
.venv\Scripts\activate

# 以可编辑模式安装
uv pip install -e .
```
