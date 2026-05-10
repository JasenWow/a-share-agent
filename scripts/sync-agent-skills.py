#!/usr/bin/env python3
"""
Sync skills from vertical-plugins into agent-plugins.

Reads plugin.json from each agent plugin, resolves skill references
(format: "a-share-analysis:factor-screen"), and copies SKILL.md content
into the agent's skills/ directory.

Usage:
  python scripts/sync-agent-skills.py [--check]
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
AGENT_PLUGINS = ROOT / "plugins" / "agent-plugins"
VERTICAL_PLUGINS = ROOT / "plugins" / "vertical-plugins"


def load_plugin_config(plugin_dir: Path) -> dict:
    """Read .claude-plugin/plugin.json."""
    config_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)


def resolve_skill(skill_ref: str) -> Path | None:
    """
    Resolve a skill reference.
    Format: "a-share-analysis:factor-screen"
    -> vertical-plugins/a-share-analysis/skills/factor-screen/
    """
    parts = skill_ref.split(":")
    if len(parts) != 2:
        return None
    plugin_name, skill_name = parts
    skill_path = VERTICAL_PLUGINS / plugin_name / "skills" / skill_name
    if skill_path.exists():
        return skill_path
    return None


def sync_agent(agent_dir: Path, dry_run: bool = False) -> list[str]:
    """Sync skills for a single agent."""
    config = load_plugin_config(agent_dir)
    if not config:
        return [f"SKIP {agent_dir.name}: no .claude-plugin/plugin.json"]

    results = []
    skills_dir = agent_dir / "skills"
    skills_dir.mkdir(exist_ok=True)

    # Clean old synced files
    if not dry_run:
        for f in skills_dir.iterdir():
            if f.is_file() and f.suffix == ".md":
                f.unlink()

    # Sync skills
    for skill_ref in config.get("skills", []):
        skill_path = resolve_skill(skill_ref)
        if not skill_path:
            results.append(f"WARN: skill not found: {skill_ref}")
            continue

        skill_name = skill_ref.split(":")[1]
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            results.append(f"WARN: SKILL.md missing: {skill_ref}")
            continue

        target = skills_dir / f"{skill_name}.md"
        if not dry_run:
            target.write_text(
                f"<!-- Auto-synced from {skill_ref} -->\n"
                f"<!-- Source: {skill_path} -->\n\n"
                f"{skill_md.read_text()}"
            )
        results.append(f"OK: {skill_ref} -> {target.relative_to(agent_dir)}")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check only, do not sync")
    args = parser.parse_args()

    print(f"A-Share Agents Skill Sync {'(dry run)' if args.check else ''}")
    print("=" * 50)

    for agent_dir in sorted(AGENT_PLUGINS.iterdir()):
        if not agent_dir.is_dir():
            continue
        results = sync_agent(agent_dir, dry_run=args.check)
        for r in results:
            print(f"  [{agent_dir.name}] {r}")

    print("\nDone.")


if __name__ == "__main__":
    main()
