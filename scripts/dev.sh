#!/usr/bin/env bash
# Aquan 本地开发环境一键启停（macOS / Linux）
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT/data/dev-runtime"
PID_DIR="$RUNTIME_DIR/pids"
LOG_DIR="$RUNTIME_DIR/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

# shellcheck disable=SC1091
if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env"
  set +a
fi

AKSHARE_PORT="${AKSHARE_PORT:-8000}"
TUSHARE_PORT="${TUSHARE_PORT:-8001}"
INTERNAL_STORE_PORT="${INTERNAL_STORE_PORT:-8002}"
QLIB_PORT="${QLIB_PORT:-8003}"
ORCHESTRATOR_PORT="${ORCHESTRATOR_PORT:-3010}"
SERVER_PORT="${SERVER_PORT:-3001}"
WEB_PORT="${WEB_PORT:-3000}"
DATA_ROOT="${DATA_ROOT:-$ROOT/data}"
[[ "$DATA_ROOT" = /* ]] || DATA_ROOT="$ROOT/${DATA_ROOT#./}"
export DATA_ROOT AKSHARE_PORT TUSHARE_PORT INTERNAL_STORE_PORT QLIB_PORT
export ORCHESTRATOR_PORT SERVER_PORT

BASE_SERVICES="akshare tushare internal-store orchestrator server web"
ALL_SERVICES="$BASE_SERVICES qlib"

usage() {
  cat <<'EOF'
用法: scripts/dev.sh <start|stop|restart|status|logs> [服务名] [--with-qlib]

示例:
  scripts/dev.sh start                 # 启动 MCP、编排器、API 和 Web
  scripts/dev.sh start --with-qlib     # 额外启动可选的 Qlib MCP
  scripts/dev.sh stop                  # 停止全部服务（包括 Qlib）
  scripts/dev.sh restart server        # 仅重启 API 服务
  scripts/dev.sh logs web              # 持续查看 Web 日志
  scripts/dev.sh status                # 查看全部服务状态

服务名: akshare, tushare, internal-store, qlib, orchestrator, server, web
日志目录: data/dev-runtime/logs/
EOF
}

is_known() {
  case " $ALL_SERVICES " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

pid_of() {
  local file="$PID_DIR/$1.pid" pid
  [[ -f "$file" ]] || return 1
  pid="$(cat "$file" 2>/dev/null)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null || return 1
  printf '%s' "$pid"
}

port_of() {
  case "$1" in
    akshare) echo "$AKSHARE_PORT" ;; tushare) echo "$TUSHARE_PORT" ;;
    internal-store) echo "$INTERNAL_STORE_PORT" ;; qlib) echo "$QLIB_PORT" ;;
    orchestrator) echo "$ORCHESTRATOR_PORT" ;; server) echo "$SERVER_PORT" ;;
    web) echo "$WEB_PORT" ;;
  esac
}

command_of() {
  case "$1" in
    akshare) echo "cd '$ROOT/python/mcp-servers/akshare-server' && exec uv run uvicorn server:mcp_app --host 127.0.0.1 --port '$AKSHARE_PORT'" ;;
    tushare) echo "cd '$ROOT/python/mcp-servers/tushare-server' && exec uv run uvicorn server:mcp_app --host 127.0.0.1 --port '$TUSHARE_PORT'" ;;
    internal-store) echo "cd '$ROOT/python/mcp-servers/internal-store' && exec uv run uvicorn server:mcp_app --host 127.0.0.1 --port '$INTERNAL_STORE_PORT'" ;;
    qlib) echo "cd '$ROOT/python/mcp-servers/qlib-server' && exec uv run uvicorn server:mcp_app --host 127.0.0.1 --port '$QLIB_PORT'" ;;
    orchestrator) echo "cd '$ROOT' && exec bun run orchestrator" ;;
    server) echo "cd '$ROOT' && exec bun run dev:server" ;;
    web) echo "cd '$ROOT' && PORT='$WEB_PORT' exec bun run dev:web" ;;
  esac
}

wait_ready() {
  local name="$1" port i
  port="$(port_of "$name")"
  for i in $(seq 1 30); do
    if ! pid_of "$name" >/dev/null; then return 1; fi
    # 不使用 -f：MCP 的根路径可能返回 404/405，但这仍说明服务已监听。
    if curl -sS --max-time 1 -o /dev/null "http://127.0.0.1:$port/" 2>/dev/null; then return 0; fi
    sleep 1
  done
  return 1
}

start_one() {
  local name="$1" pid cmd log="$LOG_DIR/$1.log"
  if pid="$(pid_of "$name")"; then
    printf '✓ %-16s 已运行 (PID %s, 端口 %s)\n' "$name" "$pid" "$(port_of "$name")"
    return 0
  fi
  rm -f "$PID_DIR/$name.pid"
  cmd="$(command_of "$name")"
  printf '→ 启动 %-16s 端口 %s\n' "$name" "$(port_of "$name")"
  nohup bash -c "$cmd" >>"$log" 2>&1 < /dev/null &
  pid=$!
  echo "$pid" > "$PID_DIR/$name.pid"
  if wait_ready "$name"; then
    printf '✓ %-16s 已就绪 (PID %s)\n' "$name" "$pid"
  else
    printf '✗ %-16s 启动失败，最近日志：\n' "$name" >&2
    tail -n 20 "$log" >&2 || true
    rm -f "$PID_DIR/$name.pid"
    return 1
  fi
}

kill_tree() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do kill_tree "$child"; done
  kill -TERM "$pid" 2>/dev/null || true
}

stop_one() {
  local name="$1" pid i
  if ! pid="$(pid_of "$name")"; then
    rm -f "$PID_DIR/$name.pid"
    printf -- '- %-16s 未运行\n' "$name"
    return 0
  fi
  printf '→ 停止 %-16s (PID %s)\n' "$name" "$pid"
  kill_tree "$pid"
  for i in $(seq 1 10); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid" 2>/dev/null || true; fi
  rm -f "$PID_DIR/$name.pid"
  printf '✓ %-16s 已停止\n' "$name"
}

status_one() {
  local name="$1" pid
  if pid="$(pid_of "$name")"; then
    printf '● %-16s 运行中  PID=%-7s http://127.0.0.1:%s\n' "$name" "$pid" "$(port_of "$name")"
  else
    rm -f "$PID_DIR/$name.pid"
    printf '○ %-16s 已停止\n' "$name"
  fi
}

ACTION="${1:-}"
[[ -n "$ACTION" ]] || { usage; exit 1; }
shift || true
TARGET=""
WITH_QLIB=0
for arg in "$@"; do
  case "$arg" in
    --with-qlib) WITH_QLIB=1 ;;
    -h|--help) usage; exit 0 ;;
    *) [[ -z "$TARGET" ]] || { echo "参数过多: $arg" >&2; exit 2; }; TARGET="$arg" ;;
  esac
done
[[ -z "$TARGET" ]] || is_known "$TARGET" || { echo "未知服务: $TARGET" >&2; usage; exit 2; }

case "$ACTION" in
  start)
    command -v bun >/dev/null || { echo '缺少 bun，请先安装依赖。' >&2; exit 1; }
    command -v uv >/dev/null || { echo '缺少 uv，请先安装 Python 依赖。' >&2; exit 1; }
    services="${TARGET:-$BASE_SERVICES}"
    [[ "$WITH_QLIB" -eq 0 || -n "$TARGET" ]] || services="$services qlib"
    failed=0
    for service in $services; do start_one "$service" || failed=1; done
    exit "$failed"
    ;;
  stop)
    services="${TARGET:-$ALL_SERVICES}"
    # 逆启动顺序停止，先停调用方，再停 MCP。
    if [[ -z "$TARGET" ]]; then services="web server orchestrator qlib internal-store tushare akshare"; fi
    for service in $services; do stop_one "$service"; done
    ;;
  restart)
    if [[ -n "$TARGET" ]]; then
      "$0" stop "$TARGET" && "$0" start "$TARGET"
    elif [[ "$WITH_QLIB" -eq 1 ]]; then
      "$0" stop && "$0" start --with-qlib
    else
      "$0" stop && "$0" start
    fi
    ;;
  status)
    services="${TARGET:-$ALL_SERVICES}"
    for service in $services; do status_one "$service"; done
    ;;
  logs)
    if [[ -n "$TARGET" ]]; then
      touch "$LOG_DIR/$TARGET.log"
      tail -n 100 -f "$LOG_DIR/$TARGET.log"
    else
      echo "日志文件："
      ls -1 "$LOG_DIR"/*.log 2>/dev/null || echo '（暂无）'
      echo "使用 '$0 logs <服务名>' 持续查看。"
    fi
    ;;
  -h|--help|help) usage ;;
  *) echo "未知操作: $ACTION" >&2; usage; exit 2 ;;
esac
