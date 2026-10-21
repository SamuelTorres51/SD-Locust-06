#!/usr/bin/env bash
# run_single.sh — Executa UMA repetição de um cenário/perfil contra o
# Spring PetClinic Microservices e salva os CSVs do Locust e o CSV de CPU.
#
# Uso:
#   ./run_single.sh <cenario:A|B|C> <perfil:leitura|escrita> <repeticao:1-10> [base_url]
#
# Exemplo:
#   ./run_single.sh A leitura 1
#   ./run_single.sh C escrita 10 http://localhost:8080

set -euo pipefail

SCENARIO="${1:?Uso: run_single.sh <A|B|C> <leitura|escrita> <rep> [base_url]}"
PROFILE="${2:?Uso: run_single.sh <A|B|C> <leitura|escrita> <rep> [base_url]}"
REP="${3:?Uso: run_single.sh <A|B|C> <leitura|escrita> <rep> [base_url]}"
BASE_URL="${4:-http://localhost:8080}"

# Containers monitorados (ajuste os nomes reais com `docker ps`)
CONTAINERS=("customers-service" "vets-service")

WARMUP_SECONDS=60
MEASURE_SECONDS=360   # 6 minutos
TOTAL_SECONDS=$((WARMUP_SECONDS + MEASURE_SECONDS))  # 7 minutos (420s)

case "$SCENARIO" in
  A) USERS=30  ;;
  B) USERS=80  ;;
  C) USERS=150 ;;
  *) echo "Cenário inválido: $SCENARIO (use A, B ou C)"; exit 1 ;;
esac

# Ramp-up em ~10s: todos os usuários sobem ainda dentro do aquecimento.
SPAWN_RATE=$(( USERS / 10 ))
if [ "$SPAWN_RATE" -lt 1 ]; then SPAWN_RATE=1; fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve como chamar o Locust. Em ambientes Windows + Bash, o Python do
# venv pode existir apenas em `.venv/Scripts`, fora do PATH do shell.
if command -v locust >/dev/null 2>&1; then
  LOCUST_CMD=(locust)
else
  LOCUST_CMD=()
  for PYTHON_CMD in \
    "${PROJECT_DIR}/.venv/Scripts/python.exe" \
    "${PROJECT_DIR}/.venv/bin/python" \
    python \
    python3
  do
    if [ -f "$PYTHON_CMD" ] || command -v "$PYTHON_CMD" >/dev/null 2>&1; then
      if "$PYTHON_CMD" -m locust --version >/dev/null 2>&1; then
        LOCUST_CMD=("$PYTHON_CMD" -m locust)
        break
      fi
    fi
  done

  if [ "${#LOCUST_CMD[@]}" -eq 0 ]; then
    echo "Erro: não encontrei o Locust instalado."
    echo "Ative o venv correto ou rode: python -m pip install -r requirements.txt"
    exit 1
  fi
fi
RUN_ID="${SCENARIO}_${PROFILE}_rep${REP}"
RAW_DIR="${PROJECT_DIR}/results/raw"
mkdir -p "$RAW_DIR"

CSV_PREFIX="${RAW_DIR}/${RUN_ID}"
CPU_CSV="${RAW_DIR}/${RUN_ID}_cpu.csv"
LOG_FILE="${RAW_DIR}/${RUN_ID}.log"
LOCUST_FILE="${PROJECT_DIR}/locustfile.py"
LOCUST_CSV_PREFIX="$CSV_PREFIX"
LOCUST_HTML="${CSV_PREFIX}.html"

# O Python Windows não entende caminhos WSL (`/mnt/c/...`). Converta apenas
# os caminhos entregues ao Locust quando o interpretador selecionado for o
# executável Windows do venv.
case "${LOCUST_CMD[0]}" in
  *.exe)
    if command -v wslpath >/dev/null 2>&1; then
      LOCUST_FILE="$(wslpath -w "$LOCUST_FILE")"
      LOCUST_CSV_PREFIX="$(wslpath -w "$LOCUST_CSV_PREFIX")"
      LOCUST_HTML="$(wslpath -w "$LOCUST_HTML")"
    fi
    ;;
esac

echo "=== Executando ${RUN_ID} | usuários=${USERS} | spawn_rate=${SPAWN_RATE} | total=${TOTAL_SECONDS}s ==="

# Inicia o monitor de CPU em segundo plano (duração = total + margem)
bash "${SCRIPT_DIR}/monitor_cpu.sh" "$CPU_CSV" $((TOTAL_SECONDS + 10)) "${CONTAINERS[@]}" &
MONITOR_PID=$!

# Executa o Locust headless. WARMUP_SECONDS é lido pelo locustfile.py,
# que reseta as estatísticas após esse tempo — o CSV final conterá
# apenas a janela de medição de 6 minutos.
#
# Importante: o Locust sai com código != 0 quando há requisições com
# falha. Isso é um RESULTADO ESPERADO do experimento (a taxa de falhas
# é uma das métricas pedidas), não um erro de script — por isso
# desligamos "set -e" só para esta chamada, para não abortar a bateria
# inteira por causa de uma falha isolada em algum cenário de carga alta.
set +e
LOAD_PROFILE="$PROFILE" \
WARMUP_SECONDS="$WARMUP_SECONDS" \
BASE_URL="$BASE_URL" \
"${LOCUST_CMD[@]}" -f "$LOCUST_FILE" \
  --headless \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "${TOTAL_SECONDS}s" \
  --csv "$LOCUST_CSV_PREFIX" \
  --csv-full-history \
  --html "$LOCUST_HTML" \
  --only-summary \
  2>&1 | tee "$LOG_FILE"
LOCUST_EXIT=${PIPESTATUS[0]}
set -e

if [ "$LOCUST_EXIT" -ne 0 ]; then
  echo "[aviso] Locust retornou código ${LOCUST_EXIT} para ${RUN_ID} — geralmente indica que houve requisições com falha (dado válido do experimento). Conferir ${CSV_PREFIX}_stats.csv."
fi

# Garante que o monitor de CPU termine
wait "$MONITOR_PID" 2>/dev/null || true

echo "=== Concluído ${RUN_ID} -> ${CSV_PREFIX}_stats.csv / ${CPU_CSV} ==="