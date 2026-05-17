from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime

import requests

INTERNAL_STORE_URL = "http://localhost:8002"
STORE_EXPERIMENT_TOOL = "store_experiment"


def store_experiment_via_mcp(
    experiment_name: str,
    strategy_config: dict,
    simulation_result: dict | None = None,
) -> dict:
    experiment_id = str(uuid.uuid4())
    config_json = json.dumps(strategy_config, ensure_ascii=False, sort_keys=True)
    result_json = json.dumps(simulation_result, ensure_ascii=False, sort_keys=True) if simulation_result else None

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": STORE_EXPERIMENT_TOOL,
            "arguments": {
                "experiment_id": experiment_id,
                "experiment_name": experiment_name,
                "strategy_config": config_json,
                "simulation_result": result_json,
                "created_at": datetime.now().isoformat(),
            },
        },
    }

    try:
        response = requests.post(
            f"{INTERNAL_STORE_URL}/mcp",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()

        if "result" in result:
            return {
                "experiment_id": experiment_id,
                "lineage": {"parent_id": None, "generation": 1},
                "status": "stored",
            }
        elif "error" in result:
            return {
                "experiment_id": experiment_id,
                "status": "error",
                "error": result["error"],
            }
    except requests.exceptions.ConnectionError:
        return {
            "experiment_id": experiment_id,
            "status": "error",
            "error": f"Cannot connect to internal-store at {INTERNAL_STORE_URL}. Is the server running?",
        }
    except requests.exceptions.RequestException as e:
        return {
            "experiment_id": experiment_id,
            "status": "error",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Track trading strategy experiment via internal-store MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python track_experiment.py --name "ma_cross_v1" --config '{"ma_short": 5, "ma_long": 20}'
  python track_experiment.py -n "rsi_strategy" -c '{"rsi_period": 14}' -r '{"sharpe": 1.5}'
        """,
    )
    parser.add_argument(
        "-n", "--name",
        required=True,
        help="Human-readable experiment name",
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Strategy config as JSON string",
    )
    parser.add_argument(
        "-r", "--result",
        default=None,
        help="Simulation result as JSON string (optional)",
    )

    args = parser.parse_args()

    try:
        config = json.loads(args.config)
        if not isinstance(config, dict):
            raise ValueError("Config must be a JSON object (dict)")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in --config: {e}")
        return 1

    result = None
    if args.result:
        try:
            result = json.loads(args.result)
            if not isinstance(result, dict):
                raise ValueError("Result must be a JSON object (dict)")
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --result: {e}")
            return 1

    output = store_experiment_via_mcp(args.name, config, result)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if output.get("status") == "stored" else 1


if __name__ == "__main__":
    raise SystemExit(main())