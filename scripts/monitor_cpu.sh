# monitor_cpu.sh — Amostra o uso de CPU (docker stats) dos serviços indicados
# durante a execução de um teste Locust e grava em CSV.


set -euo pipefail

OUT_FILE="${1:?Uso: monitor_cpu.sh <saida.csv> <duracao_s> [containers...]}"
DURATION="${2:?Uso: monitor_cpu.sh <saida.csv> <duracao_s> [containers...]}"
shift 2 || true
CONTAINERS=("$@")

if [ ${#CONTAINERS[@]} -eq 0 ]; then
  CONTAINERS=("customers-service" "vets-service")
fi

INTERVAL=2  # segundos entre amostras

echo "timestamp,container,cpu_percent,mem_usage" > "$OUT_FILE"

END_TIME=$(( $(date +%s) + DURATION ))

while [ "$(date +%s)" -lt "$END_TIME" ]; do
  TS=$(date +%s)
  for c in "${CONTAINERS[@]}"; do
    # docker stats --no-stream retorna uma linha com CPU% e MEM uso para o container
    LINE=$(docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}}" "$c" 2>/dev/null || echo "NA,NA")
    CPU=$(echo "$LINE" | cut -d',' -f1 | tr -d '%')
    MEM=$(echo "$LINE" | cut -d',' -f2)
    echo "${TS},${c},${CPU},\"${MEM}\"" >> "$OUT_FILE"
  done
  sleep "$INTERVAL"
done
