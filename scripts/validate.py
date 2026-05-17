#!/usr/bin/env python3
"""
Validation utilities for plugin structure, skill definitions, and agent manifests.

Usage:
  python scripts/validate.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def validate_skill(skill_dir: Path) -> list[str]:
    """Validate a skill directory has required files."""
    issues = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        issues.append(f"MISSING: {skill_md}")
        return issues

    content = skill_md.read_text()
    required_sections = ["## Workflow", "## Guardrails"]
    for section in required_sections:
        if section not in content:
            issues.append(f"MISSING section '{section}' in {skill_md}")

    return issues


def validate_agent(agent_dir: Path) -> list[str]:
    """Validate an agent plugin directory."""
    issues = []
    plugin_json = agent_dir / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        issues.append(f"MISSING: {plugin_json}")
        return issues

    with open(plugin_json) as f:
        config = json.load(f)

    for field in ["name", "version", "description"]:
        if field not in config:
            issues.append(f"MISSING field '{field}' in {plugin_json}")

    agents_dir = agent_dir / "agents"
    if not agents_dir.exists():
        issues.append(f"MISSING: {agents_dir}")
    else:
        agent_files = list(agents_dir.glob("*.md"))
        if not agent_files:
            issues.append(f"MISSING: no .md files in {agents_dir}")

    return issues


def validate_vertical_plugin(vp_dir: Path) -> list[str]:
    """Validate a vertical plugin directory."""
    issues = []
    plugin_json = vp_dir / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        issues.append(f"MISSING: {plugin_json}")

    mcp_json = vp_dir / ".mcp.json"
    if not mcp_json.exists():
        issues.append(f"MISSING: {mcp_json}")

    skills_dir = vp_dir / "skills"
    if not skills_dir.exists():
        issues.append(f"MISSING: {skills_dir}")
    else:
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                issues.extend(validate_skill(skill_dir))

    commands_dir = vp_dir / "commands"
    if not commands_dir.exists():
        issues.append(f"MISSING: {commands_dir}")

    return issues


def main():
    print("A-Share Agents Validation")
    print("=" * 50)

    all_issues = []

    # Validate vertical plugins (5 verticals: market-data, equity-research, trading-strategy, simulation, market-monitor)
    verticals_dir = ROOT / "plugins" / "vertical-plugins"
    if verticals_dir.exists():
        for vp in sorted(verticals_dir.iterdir()):
            if not vp.is_dir():
                continue
            plugin_json = vp / ".claude-plugin" / "plugin.json"
            if not plugin_json.exists():
                continue
            print(f"\n[Vertical Plugin: {vp.name}]")
            issues = validate_vertical_plugin(vp)
            all_issues.extend(issues)
            for issue in issues:
                print(f"  - {issue}")
            if not issues:
                print("  OK")

    # Validate agent plugins
    ap_dir = ROOT / "plugins" / "agent-plugins"
    if ap_dir.exists():
        for agent_dir in sorted(ap_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            print(f"\n[Agent: {agent_dir.name}]")
            issues = validate_agent(agent_dir)
            all_issues.extend(issues)
            for issue in issues:
                print(f"  - {issue}")
            if not issues:
                print("  OK")

    print(f"\n{'=' * 50}")
    if all_issues:
        print(f"Found {len(all_issues)} issue(s).")
        sys.exit(1)
    else:
        print("All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
