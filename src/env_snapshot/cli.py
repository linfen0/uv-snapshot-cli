import click
from pathlib import Path

import tomlkit
from importlib import metadata
from packaging.version import parse as parse_version
from env_snapshot.core import create_snapshot

@click.command()
@click.option(
    "--base-toml",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path(__file__).parent / "base_pyproject.toml",
    help="Path to the base pyproject.toml file.",
    show_default=True,
)
@click.option(
    "--requirements",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default="requirements.txt",
    help="Path to the requirements.txt file.",
    show_default=True,
)
@click.option(
    "--output",
    "-o",
    default="pyproject.snapshot.toml",
    help="Output file path.",
    show_default=True,
)
def main(base_toml: Path, requirements: Path, output: str) -> None:
    """
    Generates a locked pyproject.toml snapshot from the current environment.

    BASE_TOML: Path to the base pyproject.toml file.
    REQUIREMENTS: Path to the requirements.txt file.
    """  
    try:
        snapshot_doc = create_snapshot(
            base_toml_path=str(base_toml),
            requirements_path=str(requirements),
        )
        
        # Apply specific patches (Business Rules)
        update_torch_index_url(snapshot_doc)
        
        # Handle I/O (Interface Adapter)
        save_snapshot_to_file(snapshot_doc, output)

        click.echo(f"Snapshot successfully created: {Path(output).resolve()}")
    except Exception as e:
        raise click.ClickException(f"Error during snapshot creation: {e}")


def update_torch_index_url(base_doc: tomlkit.TOMLDocument) -> None:
    """
    Update the PyTorch index URL in the snapshot if a placeholder is present.
    Uses the robust collect_installed_packages to get the version from the target environment.
    """
    try:
        from env_snapshot.core import collect_installed_packages, pkg_key
        installed = collect_installed_packages()
        torch_pkg = installed.get(pkg_key("torch"))
        
        if not torch_pkg:
            return

        version = parse_version(torch_pkg.version)
        
        if not version.local:
            return
            
        new_url = f"https://download.pytorch.org/whl/{version.local}"
        
        # Replace XXX in index URLs
        if "tool" in base_doc and "uv" in base_doc["tool"]:
            base_doc["tool"]["uv"]["index"] = [
                {**index, "url": new_url} if "XXX" in index.get("url", "") else index
                for index in base_doc["tool"]["uv"].get("index", [])
            ]
    except Exception as e:
        # Avoid crashing if optional patching fails
        import logging
        logging.warning(f"Failed to update torch index url: {e}")


def save_snapshot_to_file(
    base_doc: tomlkit.TOMLDocument,
    save_name: str,
) -> None:
    path = Path(save_name)
    path.write_text(tomlkit.dumps(base_doc), encoding="utf-8")


if __name__ == "__main__":
    main()
