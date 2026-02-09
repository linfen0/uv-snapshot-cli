# core_clean_readable_lib.py
"""
env_snapshot.core Module Responsibility:

This module is the core calculation logic of `env_snapshot`, responsible for mapping
the current Python environment state to a standard `pyproject.toml` dependency snapshot.

Design Principles:
1. **Pure Calculation**: This module only handles "Input Environment info -> Output TOML object",
   no filesystem I/O (except for reading base templates), no network, no patching.
2. **Generality**: Treat all packages equally.
3. **Immutability**: Input data is not modified.

Main Functions:
- `collect_installed_packages`: Collects installed package info from the TARGET environment using `uv pip list`.
- `assign_package_groups`: Assigns packages to optional-dependencies based on rules.
- `build_uv_sections`: Infers source/index config.
- `render_snapshot`: Renders to tomlkit document.
- `create_snapshot`: Main orchestration.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Any
from urllib.parse import urlparse

import tomlkit
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
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
    url: Optional[str] = None
    editable: bool = False

    group: Optional[str] = None
    tool_uv_sources_indexname: Optional[str] = None
    _group_priority: int = PrivateAttr(default=-1)

    @computed_field
    @property
    def install_sources(self) -> Optional[str]:
        return self.url

    def set_group(self, group: str, priority: int) -> None:
        if priority > self._group_priority:
            self.group = group
            self._group_priority = priority


# -------------------------------------------------
# Stage 1: environment collection
# -------------------------------------------------

def collect_installed_packages() -> Dict[str, Package]:
    """
    Uses `uv pip list --format json` to get installed packages from the TARGET environment.
    This inspects the active environment (e.g. .venv) where the user is running the command,
    NOT the isolated tool environment.
    """
    # Run uv pip list to get the target environment's packages
    # This automatically respects usage context (e.g. active .venv)
    out = subprocess.run(
        ["uv", "pip", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    data: List[Dict[str, Any]] = json.loads(out)
    
    packages = {}
    for item in data:
        # item structure from uv pip list --format json: 
        # {"name": "...", "version": "...", "url": "...", "editable": bool, ...}
        name = item.get("name", "")
        if not name:
            continue
            
        packages[pkg_key(name)] = Package(
            pkg_name=name,
            version=item.get("version", ""),
            url=item.get("url"), # Direct URL (e.g. from direct_url.json)
            editable=item.get("editable", False),
        )
    return packages


def get_uv_root_dependencies() -> List[str]:
    # Use uv to find what user explicitly installed via `uv pip install`
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
    if not Path(path).exists():
        return []
        
    return [
        requirement_name(line.strip())
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


# -------------------------------------------------
# Stage 2: group assignment
# -------------------------------------------------

def infer_group_from_environment(pkg: Package) -> Optional[str]:
    # Check editable status from JSON output
    if pkg.editable:
        return GROUP_USER_COMPILED

    # Check source URL from JSON output
    if not pkg.url:
        return None

    url = pkg.url
    if url.startswith("file://"):
        return GROUP_USER_COMPILED
    
    if url.startswith(("http://", "https://")) and url.lower().endswith(".whl"):
        return GROUP_USER_DOWNLOAD
        
    if url.startswith("git+"):
         return "other-vcs"

    return None


def assign_package_groups(
    installed: Dict[str, Package],
    base_doc,
    requirements: Iterable[str],
    root_dependencies: Iterable[str],
) -> None:
    def assign(name: str, group: str, priority: int) -> None:
        key = pkg_key(name)
        if key not in installed:
             # Robustness check: requirement exists but package not found in target env
             return
        installed[key].set_group(group, priority)

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
        key = pkg_key(pkg_name)
        if key in installed:
            installed[key].tool_uv_sources_indexname = spec["index"]

    for pkg in installed.values():
        if pkg.tool_uv_sources_indexname is None and pkg.install_sources:
            pkg.tool_uv_sources_indexname = index_name_from_url(pkg.install_sources)


def build_uv_sections(
    installed: Dict[str, Package],
    base_doc,
    keep_keys: Iterable[str],
) -> Tuple[dict, list]:
    inferred_sources = {
        installed[k].pkg_name: {"index": installed[k].tool_uv_sources_indexname}
        for k in keep_keys
        if installed[k].tool_uv_sources_indexname
    }

    inferred_urls = {
        installed[k].tool_uv_sources_indexname: installed[k].install_sources
        for k in keep_keys
        if installed[k].tool_uv_sources_indexname and installed[k].install_sources
    }

    merged_indices = [dict(x) for x in base_doc["tool"]["uv"]["index"]]
    declared_names = {x["name"] for x in merged_indices if "name" in x}

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

    # Create tomlkit inline table for better readability
    # e.g. torch = { index = "pytorch-cuda" }
    sources_table = tomlkit.inline_table()
    sources_table.update(inferred_sources)
    base_doc["tool"]["uv"]["sources"] = sources_table

    base_doc["tool"]["uv"]["index"] = merged_indices


# -------------------------------------------------
# Orchestration
# -------------------------------------------------

def create_snapshot(
    base_toml_path: str,
    requirements_path: str,
) -> tomlkit.TOMLDocument:
    base_doc = tomlkit.parse(Path(base_toml_path).read_text(encoding="utf-8"))

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
