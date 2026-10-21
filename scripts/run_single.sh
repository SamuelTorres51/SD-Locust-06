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
RUN_ID="${SCENARIO}_${PROFILE}_rep${REP}"
RAW_DIR="${PROJECT_DIR}/results/raw"
mkdir -p "$RAW_DIR"

CSV_PREFIX="${RAW_DIR}/${RUN_ID}"
CPU_CSV="${RAW_DIR}/${RUN_ID}_cpu.csv"
LOG_FILE="${RAW_DIR}/${RUN_ID}.log"

echo "=== Executando ${RUN_ID} | usuários=${USERS} | spawn_rate=${SPAWN_RATE} | total=${TOTAL_SECONDS}s ==="

# Inicia o monitor de CPU em segundo plano (duração = total + margem)
"${SCRIPT_DIR}/monitor_cpu.sh" "$CPU_CSV" $((TOTAL_SECONDS + 10)) "${CONTAINERS[@]}" &
MONITOR_PID=$!

# Executa o Locust headless. WARMUP_SECONDS é lido pelo locustfile.py,
# que reseta as estatísticas após esse tempo — o CSV final conterá
# apenas a janela de medição de 6 minutos.
LOAD_PROFILE="$PROFILE" \
WARMUP_SECONDS="$WARMUP_SECONDS" \
BASE_URL="$BASE_URL" \
locust -f "${PROJECT_DIR}/locustfile.py" \
  --headless \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "${TOTAL_SECONDS}s" \
  --csv "$CSV_PREFIX" \
  --csv-full-history \
  --html "${CSV_PREFIX}.html" \
  --only-summary \
  2>&1 | tee "$LOG_FILE"

# Garante que o monitor de CPU termine
wait "$MONITOR_PID" 2>/dev/null || true

echo "=== Concluído ${RUN_ID} -> ${CSV_PREFIX}_stats.csv / ${CPU_CSV} ==="
