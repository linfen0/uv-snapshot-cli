# core_clean_readable_lib.py
"""
env_snapshot.core 模块职责说明：

本模块是 `env_snapshot` 的核心计算逻辑层，负责将当前 Python 环境的状态映射为
标准的 `pyproject.toml` 依赖快照。

设计原则：
1. **纯粹计算逻辑**：本模块只负责“输入环境信息 -> 输出 TOML 对象”的计算过程，不包含任何
   文件写入（I/O）、网络请求或特定库的各种补丁逻辑。
2. **通用性**：本模块不应包含针对特定包（如 torch）的特殊处理逻辑，所有包一视同仁。
3. **不可变性**：输入数据（base_doc, installed）在计算过程中不应被修改，输出为全新的 TOML 对象。

主要功能：
- `collect_installed_packages`: 收集当前环境已安装的包信息。
- `assign_package_groups`: 根据规则（base, requirements.txt, root deps）将包分配到对应的optional-dependencies中。
- `build_uv_sections`: 推断并生成 uv 专属的 source 和 index 配置。
- `render_snapshot`: 将包信息渲染到 tomlkit.TOMLDocument 对象中。
- `create_snapshot`: 编排上述步骤的主流程函数，返回 `tomlkit.TOMLDocument` 对象。
"""
from __future__ import annotations

import json

import subprocess
from importlib import metadata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import tomlkit
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import parse as parse_version
from pydantic import BaseModel, PrivateAttr, computed_field


# -------------------------------------------------
# Canonical group names (snapshot-visible semantics)
# -------------------------------------------------

GROUP_PROJECT_DEPENDENCY = "project-dependency"
GROUP_USER_COMPILED = "user-compiled"
GROUP_USER_DOWNLOAD = "user-download"


# -------------------------------------------------
# Group decision priority (higher overrides lower)
# -------------------------------------------------

PRIORITY_ROOT_DEPENDENCY = 10
PRIORITY_BASE_TOML = 20
PRIORITY_REQUIREMENTS = 30
PRIORITY_ENV_INFERENCE = 40


# -------------------------------------------------
# Small helpers (library-backed)
# -------------------------------------------------

def pkg_key(name: str) -> str:
    # PEP 503 canonical form (pip / uv / packaging standard)
    return canonicalize_name(name)


def requirement_name(req: str) -> str:
    return Requirement(req).name


def index_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.replace(":", "-").lower()


# -------------------------------------------------
# Domain model
# -------------------------------------------------

class Package(BaseModel):
    pkg_name: str
    version: str

    group: Optional[str] = None
    tool_uv_sources_indexname: Optional[str] = None
    _group_priority: int = PrivateAttr(default=-1)

    @computed_field
    @property
    def install_sources(self) -> Optional[str]:
        dist = metadata.distribution(self.pkg_name)
        txt = dist.read_text("direct_url.json")
        return json.loads(txt).get("url") if txt else None

    def set_group(self, group: str, priority: int) -> None:
        if priority > self._group_priority:
            self.group = group
            self._group_priority = priority


# -------------------------------------------------
# Stage 1: environment collection
# -------------------------------------------------

def collect_installed_packages() -> Dict[str, Package]:
    return {
        pkg_key(d.metadata["Name"]): Package(
            pkg_name=d.metadata["Name"],
            version=d.version,
        )
        for d in metadata.distributions()
    }


def get_uv_root_dependencies() -> List[str]:
    out = subprocess.run(
        ["uv", "pip", "tree", "--depth", "0"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    roots = []
    for line in out.splitlines():
        clean = line.replace("├── ", "").replace("└── ", "").strip()
        if " v" in clean:
            roots.append(clean.split(" v")[0])
    return roots


def parse_requirements_file(path: str) -> List[str]:
    return [
        requirement_name(line.strip())
        for line in Path(path).read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


# -------------------------------------------------
# Stage 2: group assignment
# -------------------------------------------------

def infer_group_from_environment(pkg: Package) -> Optional[str]:
    dist = metadata.distribution(pkg.pkg_name)

    if dist.read_text("PKG-INFO") and not dist.read_text("METADATA"):
        return GROUP_USER_COMPILED

    txt = dist.read_text("direct_url.json")
    if not txt:
        return None

    obj = json.loads(txt)
    url = obj.get("url", "")

    if obj.get("dir_info", {}).get("editable"):
        return GROUP_USER_COMPILED
    if isinstance(obj.get("vcs_info"), dict):
        return "other-vcs"
    if url.startswith("file://"):
        return GROUP_USER_COMPILED
    if url.startswith(("http://", "https://")) and url.lower().endswith(".whl"):
        return GROUP_USER_DOWNLOAD

    return None


def assign_package_groups(
    installed: Dict[str, Package],
    base_doc,
    requirements: Iterable[str],
    root_dependencies: Iterable[str],
) -> None:
    def assign(name: str, group: str, priority: int) -> None:
        installed[pkg_key(name)].set_group(group, priority)

    for name in root_dependencies:
        assign(name, GROUP_USER_DOWNLOAD, PRIORITY_ROOT_DEPENDENCY)

    for dep in base_doc["project"].get("dependencies", []):
        assign(requirement_name(dep), GROUP_PROJECT_DEPENDENCY, PRIORITY_BASE_TOML)

    for group_name, deps in base_doc["project"].get("optional-dependencies", {}).items():
        for dep in deps:
            assign(requirement_name(dep), group_name, PRIORITY_BASE_TOML)

    for name in requirements:
        assign(name, GROUP_PROJECT_DEPENDENCY, PRIORITY_REQUIREMENTS)

    for pkg in installed.values():
        inferred = infer_group_from_environment(pkg)
        if inferred:
            pkg.set_group(inferred, PRIORITY_ENV_INFERENCE)


# -------------------------------------------------
# Stage 3: uv sources / index
# -------------------------------------------------

def assign_uv_index_info(installed: Dict[str, Package], base_doc) -> None:
    for pkg_name, spec in base_doc["tool"]["uv"]["sources"].items():
        installed[pkg_key(pkg_name)].tool_uv_sources_indexname = spec["index"]

    for pkg in installed.values():
        if pkg.tool_uv_sources_indexname is None and pkg.install_sources:
            pkg.tool_uv_sources_indexname = index_name_from_url(pkg.install_sources)


def build_uv_sections(
    installed: Dict[str, Package],
    base_doc,
    keep_keys: Iterable[str],
) -> Tuple[dict, list]:
    # 1. Collect inferred package-to-index mappings from environment
    inferred_sources = {
        installed[k].pkg_name: {"index": installed[k].tool_uv_sources_indexname}
        for k in keep_keys
        if installed[k].tool_uv_sources_indexname
    }

    # 2. Collect inferred URLs for those index names
    inferred_urls = {
        installed[k].tool_uv_sources_indexname: installed[k].install_sources
        for k in keep_keys
        if installed[k].tool_uv_sources_indexname and installed[k].install_sources
    }

    # 3. Process the base indices from pyproject.toml
    merged_indices = [dict(x) for x in base_doc["tool"]["uv"]["index"]]
    declared_names = {x["name"] for x in merged_indices if "name" in x}

    # 4. Check for missing indices required by our inferred sources
    required_names = {v["index"] for v in inferred_sources.values()}
    for name in required_names:
        if name not in declared_names:
            url = inferred_urls.get(name, "https://example.invalid/simple")
            merged_indices.append(
                {"name": name, "url": url, "explicit": True}
            )

    return inferred_sources, merged_indices


# -------------------------------------------------
# Stage 4: snapshot rendering
# -------------------------------------------------

def render_snapshot(
    base_doc,
    installed: Dict[str, Package],
    keep_keys: Iterable[str],
    inferred_sources: dict,
    merged_indices: list,
) -> None:
    base_doc["project"]["dependencies"] = []
    base_doc["project"]["optional-dependencies"] = {}

    for key in sorted(keep_keys):
        pkg = installed[key]
        pinned = f"{pkg.pkg_name}=={pkg.version}"

        if pkg.group == GROUP_PROJECT_DEPENDENCY:
            base_doc["project"]["dependencies"].append(pinned)
        else:
            base_doc["project"]["optional-dependencies"].setdefault(pkg.group, []).append(pinned)

    base_doc["tool"]["uv"]["sources"] = inferred_sources
    base_doc["tool"]["uv"]["index"] = merged_indices


# -------------------------------------------------
# Orchestration
# -------------------------------------------------

def create_snapshot(
    base_toml_path: str,
    requirements_path: str,
) -> tomlkit.TOMLDocument:
    base_doc = tomlkit.parse(Path(base_toml_path).read_text())

    installed = collect_installed_packages()
    requirements = parse_requirements_file(requirements_path)
    root_deps = get_uv_root_dependencies()

    assign_package_groups(installed, base_doc, requirements, root_deps)

    keep_keys = {
        k for k, p in installed.items()
        if p.group or k in map(pkg_key, base_doc["tool"]["uv"]["sources"].keys())
    }

    assign_uv_index_info(installed, base_doc)
    inferred_sources, merged_indices = build_uv_sections(installed, base_doc, keep_keys)

    render_snapshot(base_doc, installed, keep_keys, inferred_sources, merged_indices)
    return base_doc
