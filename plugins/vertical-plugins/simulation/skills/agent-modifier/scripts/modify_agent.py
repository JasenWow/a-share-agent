import json
import subprocess
from pathlib import Path

BLOCKED_AGENTS = ["meta-strategist"]

def update_agent_skill_references(agent_dir: Path, new_skill: str) -> bool:
    """Add a new skill reference to an agent's plugin.json. Blocks meta-strategist self-mod."""
    agent_name = agent_dir.name

    if agent_name in BLOCKED_AGENTS:
        return False

    plugin_path = agent_dir / ".claude-plugin" / "plugin.json"
    if not plugin_path.exists():
        return False

    content = plugin_path.read_text()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return False

    skills = data.get("skills", [])
    skill_ref = f"simulation:{new_skill}"
    if skill_ref not in skills:
        skills.append(skill_ref)
        data["skills"] = skills

        plugin_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        result = subprocess.run(
            ["uv", "run", "python", "scripts/check.py"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            plugin_path.write_text(content)
            return False

    return True

def update_agent_guardrails(agent_md_path: Path, new_guardrail: str) -> bool:
    """Add a new guardrail to an agent's AGENT.md."""
    if not agent_md_path.exists():
        return False

    content = agent_md_path.read_text()

    if "## Guardrails" in content:
        content = content.replace(
            "## Guardrails",
            f"## Guardrails\n- {new_guardrail}"
        )
    else:
        content += f"\n\n## Additional Guardrails\n- {new_guardrail}\n"

    agent_md_path.write_text(content)

    result = subprocess.run(
        ["uv", "run", "python", "scripts/check.py"],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return False

    return True

def validate_modification(agent_dir: Path) -> bool:
    """Run check.py to validate agent modification."""
    result = subprocess.run(
        ["uv", "run", "python", "scripts/check.py"],
        capture_output=True, text=True, timeout=60
    )
    return result.returncode == 0