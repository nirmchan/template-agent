"""Overlay sync — fetch skill overlays from GitLab into the config PVC.

Reads overlay sources from runtime/agent.yaml and fetches each into
the corresponding skill's overlay/<source_name>/ directory.

Runnable as CLI for init containers:
    python -m deep_agent.src.infrastructure.overlay --sync-all
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

import yaml


def _load_overlay_config(config_dir: Path) -> list[dict]:
    """Load overlays list from agent.yaml."""
    agent_yaml = config_dir / "runtime" / "agent.yaml"
    if not agent_yaml.is_file():
        return []
    raw = yaml.safe_load(agent_yaml.read_text()) or {}
    middleware: dict = raw.get("middleware", {})
    skills: dict = middleware.get("skills", {})
    overlays: list[dict] = skills.get("overlays", [])
    return overlays


def _fetch_archive(source: dict, dest: Path, config_dir: Path) -> bool:
    """Fetch overlay via GitLab archive API. Returns True on success."""
    host = source.get("host", "")
    project = source.get("project", "")
    ref = source.get("ref", "main")
    path = source.get("path", "")
    token = os.environ.get("GITLAB_TOKEN", "")

    enc_project = urllib.parse.quote(project, safe="")
    url = f"{host}/api/v4/projects/{enc_project}/repository/archive.tar.gz?sha={ref}"
    if path:
        url += f"&path={urllib.parse.quote(path, safe='')}"

    req = urllib.request.Request(url)
    if token:
        req.add_header("PRIVATE-TOKEN", token)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status != 200:
                return False
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                shutil.copyfileobj(resp, tmp)
                tmp_path = tmp.name
    except Exception:
        return False

    try:
        with tempfile.TemporaryDirectory() as extract_dir:
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(extract_dir, filter="data")
            _distribute(Path(extract_dir), dest, config_dir)
    finally:
        os.unlink(tmp_path)
    return True


def _fetch_sparse_clone(source: dict, dest: Path, config_dir: Path) -> bool:
    """Fallback: sparse clone from GitLab."""
    host = source.get("host", "")
    project = source.get("project", "")
    ref = source.get("ref", "main")
    path = source.get("path", "")
    token = os.environ.get("GITLAB_TOKEN", "")

    host_only = host.replace("https://", "").replace("http://", "")
    if token:
        clone_url = f"https://oauth2:{token}@{host_only}/{project}.git"
    else:
        clone_url = f"https://{host_only}/{project}.git"

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "--sparse",
                    "--branch",
                    ref,
                    clone_url,
                    tmp_dir + "/repo",
                ],
                check=True,
                capture_output=True,
                env=env,
            )
            if path:
                subprocess.run(
                    ["git", "-C", tmp_dir + "/repo", "sparse-checkout", "set", path],
                    check=True,
                    capture_output=True,
                    env=env,
                )
            src = Path(tmp_dir) / "repo" / path if path else Path(tmp_dir) / "repo"
            _distribute(src, dest, config_dir)
            return True
        except subprocess.CalledProcessError:
            return False


def _distribute(extracted: Path, source_dest: Path, config_dir: Path) -> None:
    """Distribute fetched overlay files into skill/overlay/<source>/ dirs."""
    skills_dir = config_dir / "skills"
    for skill_md in extracted.rglob("SKILL.md"):
        skill_dir_name = skill_md.parent.name
        target_skill = _find_skill_dir(skills_dir, skill_dir_name)
        if target_skill:
            overlay_dest = target_skill / "overlay" / source_dest.name
            overlay_dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill_md.parent, overlay_dest, dirs_exist_ok=True)


def _find_skill_dir(skills_dir: Path, skill_name: str) -> Path | None:
    """Find a base skill directory by name (recursive)."""
    for candidate in skills_dir.rglob("SKILL.md"):
        if "overlay" not in candidate.parts and candidate.parent.name == skill_name:
            return candidate.parent
    return None


def sync_all(config_dir: Path | None = None) -> None:
    """Sync all configured overlay sources."""
    if config_dir is None:
        config_dir = Path(__file__).parent.parent.parent.parent / "config" / "agent"

    overlays = _load_overlay_config(config_dir)
    if not overlays:
        print("No overlays configured — nothing to sync")
        return

    for source in sorted(overlays, key=lambda s: s.get("priority", 99)):
        name = source.get("name", "unnamed")
        dest = Path(name)
        print(f"Syncing overlay '{name}' (priority={source.get('priority', 99)})...")

        if _fetch_archive(source, dest, config_dir):
            print(f"  ✓ '{name}' synced via archive API")
        elif _fetch_sparse_clone(source, dest, config_dir):
            print(f"  ✓ '{name}' synced via sparse clone fallback")
        else:
            print(
                f"  ✗ '{name}' FAILED — check GITLAB_TOKEN and network", file=sys.stderr
            )


if __name__ == "__main__":
    if "--sync-all" in sys.argv:
        config_path = None
        if "--config-dir" in sys.argv:
            idx = sys.argv.index("--config-dir")
            config_path = Path(sys.argv[idx + 1])
        sync_all(config_path)
    else:
        print("Usage: python -m deep_agent.src.infrastructure.overlay --sync-all")
        sys.exit(1)
