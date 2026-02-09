# Env Snapshot Tool

[English](./README.md) | 中文

一个命令行工具，用于将当前 Python 环境依赖项快照到兼容 UV 的 `pyproject.toml` 文件中。
## 主要功能

在 **ComfyUI** 这类包含大量用户插件的环境中，手动使用uv保存的 `uv.lock` 会**混杂核心组件的依赖与个人插件的依赖**，且容易**锁定仅适用于当前平台的特定版本**（如 Windows 编译版），导致环境无法迁移到 Linux 等其他系统。本工具通过 `pyproject.toml` 的 `optional-dependencies` 实现了依赖的**自动分组**与**按需恢复**，提升此类项目的整合包分发体验：

- **🛡️ 核心依赖与插件依赖隔离**：自动分离 `requirements.txt`（核心依赖）与 `uv pip install`（插件依赖），避免环境臃肿。
- **🔌 动态平台适配**：按当前环境下载的pytorch自动填充 PyTorch 等库的 Index URL。
- **📦 编译依赖隔离**：本地编译的包归入 `user-compiled` 组，避免破坏环境的可复现性。
- **🚀 灵活按需恢复**：支持仅恢复核心环境或包含特定插件组，完美适配 Windows/Linux 等不同硬件平台。



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

### 1. 创建环境快照 (Create Snapshot)

运行以下命令，将当前环境状态保存为 `pyproject.snapshot.toml`：

```bash
New-EnvSnapshot -o pyproject.snapshot.toml
```

### 2. 恢复环境 (Restore Environment)
1. 重命名为pyproject.toml
   ```bash
    mv pyproject.toml pyproject.origin.toml
    mv pyproject.snapshot.toml pyproject.toml
   ```
2. 使用uv工具安装依赖

#### 恢复为仅核心依赖 (Core Only)
将环境恢复到原始 `requirements.txt` 中定义的依赖：
```bash
uv sync
```

#### 安装核心依赖和用户插件的依赖 (Core + User Downloaded)
1. 命令格式
   ```bash
   uv pip install . [extra-group]
   ```
 2. 恢复核心依赖以及用户额外下载的插件依赖：

```bash
uv pip install . --extra user-download
```


#### 完整恢复 (All Dependencies)
安装所有分组（包含用户自行编译的组件）：

```bash
uv pip install . --all-extras
```

### 3. 命令参数 (Options)

```bash
env-snapshot [OPTIONS]
```

- `--base-toml PATH`      : 基础 `pyproject.toml` 模板路径 (默认: 内置模板)
- `--requirements PATH`   : `requirements.txt` 文件路径 (默认: `YOUR_WORK_DIR/requirements.txt`)
- `-o, --output PATH`     : 输出快照文件路径 (默认: `YOUR_WORK_DIR/pyproject.snapshot.toml`)
- `--help`                : 显示帮助信息

## 开发

本项目使用 `hatch` 作为构建后端，暂时只为 `uv`工具设计。

```bash
# 使用 uv 创建虚拟环境
uv venv

# 激活环境 (Windows)
.venv\Scripts\activate

# 以可编辑模式安装
uv pip install -e .
```
