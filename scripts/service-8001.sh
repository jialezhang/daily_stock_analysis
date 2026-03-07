#!/usr/bin/env bash
set -euo pipefail

HOST="127.0.0.1"
PORT="8001"
PID_FILE="/tmp/dsa-serve-8001.pid"
LOG_FILE="/tmp/dsa-serve-8001.log"
HEALTH_URL="http://${HOST}:${PORT}/api/health"

print_listener() {
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN || true
}

is_listening() {
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1
}

is_healthy() {
  curl -fsS "${HEALTH_URL}" >/dev/null 2>&1
}

start_service() {
  if is_listening; then
    if is_healthy; then
      echo "[service-8001] already running and healthy on ${HOST}:${PORT}"
      return 0
    fi
    echo "[service-8001] port ${PORT} is occupied but health check failed"
    print_listener
    return 1
  fi

  echo "[service-8001] starting service on ${HOST}:${PORT}"
  nohup python3 main.py --serve-only --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
  local pid="$!"
  echo "${pid}" >"${PID_FILE}"

  for _ in $(seq 1 40); do
    if is_healthy; then
      echo "[service-8001] started (pid=${pid})"
      curl -fsS "${HEALTH_URL}"
      echo
      return 0
    fi
    sleep 1
  done

  echo "[service-8001] failed to start, tailing log:"
  tail -n 120 "${LOG_FILE}" || true
  return 1
}

stop_service() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}" || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
    rm -f "${PID_FILE}"
  fi

  local listeners
  listeners="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN || true)"
  if [[ -n "${listeners}" ]]; then
    kill ${listeners} >/dev/null 2>&1 || true
  fi
  echo "[service-8001] stopped"
}

status_service() {
  if is_healthy; then
    echo "[service-8001] healthy on ${HOST}:${PORT}"
    print_listener
    return 0
  fi
  echo "[service-8001] not running or unhealthy on ${HOST}:${PORT}"
  print_listener
  return 1
}

case "${1:-start}" in
  start)
    start_service
    ;;
  stop)
    stop_service
    ;;
  restart)
    stop_service
    start_service
    ;;
  status)
    status_service
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 2
    ;;
esac
