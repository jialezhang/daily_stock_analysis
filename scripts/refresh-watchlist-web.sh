#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

show_usage() {
  cat <<'EOF'
Usage:
  ./scripts/refresh-watchlist-web.sh [--stocks "hk00700,hk09988,AAPL"] [--serial|--batch]
                                   [--retries 3] [--retry-delay 2] [--print-only]

Options:
  --stocks       Optional custom stock list. If omitted, read STOCK_LIST from .env.
  --serial       Refresh one stock per run with retry (default mode).
  --batch        Refresh all stocks in a single run (legacy behavior).
  --retries      Retry times for each stock in serial mode. Default: 3.
  --retry-delay  Seconds between retries in serial mode. Default: 2.
  --print-only   Only print the resolved stocks and command, do not execute.
  -h, --help     Show this help message.
EOF
}

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "${s}"
}

normalize_code() {
  local raw="$1"
  local code
  code="$(trim "${raw}")"
  if [[ -z "${code}" ]]; then
    return 0
  fi

  if [[ "${code}" =~ ^[Hh][Kk]([0-9]{5})$ ]]; then
    printf 'hk%s' "${BASH_REMATCH[1]}"
    return 0
  fi

  if [[ "${code}" =~ ^[0-9]{5}$ ]]; then
    printf 'hk%s' "${code}"
    return 0
  fi

  printf '%s' "${code}" | tr '[:lower:]' '[:upper:]'
}

read_stock_list_from_env() {
  local env_file="${ROOT_DIR}/.env"
  if [[ ! -f "${env_file}" ]]; then
    echo "[refresh-watchlist] .env not found: ${env_file}" >&2
    return 1
  fi

  local line value
  line="$(grep -E '^STOCK_LIST=' "${env_file}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    echo "[refresh-watchlist] STOCK_LIST is missing in .env" >&2
    return 1
  fi

  value="${line#STOCK_LIST=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "${value}"
}

read_stock_list_from_history() {
  local db_file="${ROOT_DIR}/data/stock_analysis.db"
  if [[ ! -f "${db_file}" ]]; then
    return 0
  fi

  python3 - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/stock_analysis.db")
if not db.exists():
    print("")
    raise SystemExit(0)

conn = sqlite3.connect(str(db))
cur = conn.cursor()
cur.execute(
    """
    SELECT code, MAX(created_at) AS last_seen
    FROM analysis_history
    WHERE code IS NOT NULL
      AND TRIM(code) != ''
      AND created_at >= datetime('now', '-30 days')
    GROUP BY code
    ORDER BY last_seen DESC
    LIMIT 200
    """,
)
codes = [row[0] for row in cur.fetchall() if row and row[0]]
print(",".join(codes))
PY
}

join_by_comma() {
  local out=""
  local item
  for item in "$@"; do
    if [[ -z "${item}" ]]; then
      continue
    fi
    if [[ -z "${out}" ]]; then
      out="${item}"
    else
      out="${out},${item}"
    fi
  done
  printf '%s' "${out}"
}

CUSTOM_STOCKS=""
PRINT_ONLY="false"
MODE="serial"
RETRIES=3
RETRY_DELAY=2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stocks)
      if [[ $# -lt 2 ]]; then
        echo "[refresh-watchlist] --stocks requires a value" >&2
        exit 2
      fi
      CUSTOM_STOCKS="$2"
      shift 2
      ;;
    --print-only)
      PRINT_ONLY="true"
      shift
      ;;
    --serial)
      MODE="serial"
      shift
      ;;
    --batch)
      MODE="batch"
      shift
      ;;
    --retries)
      if [[ $# -lt 2 ]]; then
        echo "[refresh-watchlist] --retries requires a value" >&2
        exit 2
      fi
      RETRIES="$2"
      shift 2
      ;;
    --retry-delay)
      if [[ $# -lt 2 ]]; then
        echo "[refresh-watchlist] --retry-delay requires a value" >&2
        exit 2
      fi
      RETRY_DELAY="$2"
      shift 2
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    *)
      echo "[refresh-watchlist] unknown argument: $1" >&2
      show_usage >&2
      exit 2
      ;;
  esac
done

if [[ ! "${RETRIES}" =~ ^[0-9]+$ ]] || [[ "${RETRIES}" -lt 1 ]]; then
  echo "[refresh-watchlist] --retries must be a positive integer" >&2
  exit 2
fi
if [[ ! "${RETRY_DELAY}" =~ ^[0-9]+$ ]]; then
  echo "[refresh-watchlist] --retry-delay must be a non-negative integer" >&2
  exit 2
fi

RAW_STOCKS="${CUSTOM_STOCKS}"
if [[ -z "${RAW_STOCKS}" ]]; then
  RAW_STOCKS="$(read_stock_list_from_env)"
fi
if [[ -z "$(trim "${RAW_STOCKS}")" ]]; then
  RAW_STOCKS="$(read_stock_list_from_history)"
  if [[ -n "$(trim "${RAW_STOCKS}")" ]]; then
    echo "[refresh-watchlist] STOCK_LIST is empty in .env, fallback to deduped codes from last 30 days in local history"
  fi
fi

STOCKS=""
SEEN_CODES=","
remaining="${RAW_STOCKS}"
while [[ -n "${remaining}" ]]; do
  if [[ "${remaining}" == *,* ]]; then
    raw_code="${remaining%%,*}"
    remaining="${remaining#*,}"
  else
    raw_code="${remaining}"
    remaining=""
  fi

  normalized_code="$(normalize_code "${raw_code}")"
  if [[ -z "${normalized_code}" ]]; then
    continue
  fi
  if [[ "${SEEN_CODES}" == *",${normalized_code},"* ]]; then
    continue
  fi
  SEEN_CODES="${SEEN_CODES}${normalized_code},"

  if [[ -z "${STOCKS}" ]]; then
    STOCKS="${normalized_code}"
  else
    STOCKS="${STOCKS},${normalized_code}"
  fi
done
if [[ -z "${STOCKS}" ]]; then
  echo "[refresh-watchlist] resolved stock list is empty" >&2
  exit 1
fi

IFS=',' read -r -a STOCK_ARRAY <<< "${STOCKS}"
if [[ "${#STOCK_ARRAY[@]}" -eq 0 ]]; then
  echo "[refresh-watchlist] no stock resolved after split" >&2
  exit 1
fi

BASE_CMD=(
  python3 main.py
  --force-run
  --no-notify
  --no-market-review
)
ENV_DESC="AGENT_MODE=false ENABLE_REALTIME_QUOTE=false ENABLE_REALTIME_TECHNICAL_INDICATORS=false EFINANCE_PRIORITY=0 AKSHARE_PRIORITY=1 TUSHARE_PRIORITY=2 PYTDX_PRIORITY=3 BAOSTOCK_PRIORITY=4 YFINANCE_PRIORITY=99 USE_PROXY=false"

echo "[refresh-watchlist] resolved stocks: ${STOCKS}"
echo "[refresh-watchlist] mode: ${MODE}"
echo "[refresh-watchlist] running with stable env overrides for web refresh"
echo "[refresh-watchlist] env: ${ENV_DESC}"
if [[ "${MODE}" == "serial" ]]; then
  echo "[refresh-watchlist] serial retries: ${RETRIES}, retry delay: ${RETRY_DELAY}s"
fi

if [[ "${PRINT_ONLY}" == "true" ]]; then
  if [[ "${MODE}" == "batch" ]]; then
    echo "[refresh-watchlist] command: ${ENV_DESC} ${BASE_CMD[*]} --stocks ${STOCKS}"
  else
    for code in "${STOCK_ARRAY[@]}"; do
      echo "[refresh-watchlist] command(${code}): ${ENV_DESC} ${BASE_CMD[*]} --stocks ${code}"
    done
  fi
  echo "[refresh-watchlist] print-only mode, exit without execution"
  exit 0
fi

run_refresh_once() {
  local stock_code="$1"
  AGENT_MODE=false \
  ENABLE_REALTIME_QUOTE=false \
  ENABLE_REALTIME_TECHNICAL_INDICATORS=false \
  EFINANCE_PRIORITY=0 \
  AKSHARE_PRIORITY=1 \
  TUSHARE_PRIORITY=2 \
  PYTDX_PRIORITY=3 \
  BAOSTOCK_PRIORITY=4 \
  YFINANCE_PRIORITY=99 \
  USE_PROXY=false \
  "${BASE_CMD[@]}" --stocks "${stock_code}"
}

if [[ "${MODE}" == "batch" ]]; then
  echo "[refresh-watchlist] command: ${ENV_DESC} ${BASE_CMD[*]} --stocks ${STOCKS}"
  AGENT_MODE=false \
  ENABLE_REALTIME_QUOTE=false \
  ENABLE_REALTIME_TECHNICAL_INDICATORS=false \
  EFINANCE_PRIORITY=0 \
  AKSHARE_PRIORITY=1 \
  TUSHARE_PRIORITY=2 \
  PYTDX_PRIORITY=3 \
  BAOSTOCK_PRIORITY=4 \
  YFINANCE_PRIORITY=99 \
  USE_PROXY=false \
  "${BASE_CMD[@]}" --stocks "${STOCKS}"
  echo "[refresh-watchlist] refresh finished (batch)"
  exit 0
fi

success_count=0
fail_count=0
failed_codes=""

for code in "${STOCK_ARRAY[@]}"; do
  attempt=1
  stock_ok="false"
  while [[ "${attempt}" -le "${RETRIES}" ]]; do
    echo "[refresh-watchlist] [${code}] attempt ${attempt}/${RETRIES}"
    if run_refresh_once "${code}"; then
      stock_ok="true"
      break
    fi
    if [[ "${attempt}" -lt "${RETRIES}" ]]; then
      echo "[refresh-watchlist] [${code}] retry after ${RETRY_DELAY}s"
      sleep "${RETRY_DELAY}"
    fi
    attempt=$((attempt + 1))
  done

  if [[ "${stock_ok}" == "true" ]]; then
    success_count=$((success_count + 1))
    echo "[refresh-watchlist] [${code}] done"
  else
    fail_count=$((fail_count + 1))
    if [[ -z "${failed_codes}" ]]; then
      failed_codes="${code}"
    else
      failed_codes="${failed_codes},${code}"
    fi
    echo "[refresh-watchlist] [${code}] failed after ${RETRIES} attempts"
  fi
done

echo "[refresh-watchlist] refresh finished (serial): success=${success_count}, failed=${fail_count}"
if [[ "${fail_count}" -gt 0 ]]; then
  echo "[refresh-watchlist] failed codes: ${failed_codes}" >&2
  exit 1
fi
