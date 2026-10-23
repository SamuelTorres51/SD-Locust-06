set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCENARIOS=("A" "B" "C")
PROFILES=("leitura" "escrita")
REPS=$(seq 1 10)
RUN_SECONDS=420
MONITOR_MARGIN_SECONDS=10
COOLDOWN_SECONDS=15

TOTAL_RUNS=$(( ${#SCENARIOS[@]} * ${#PROFILES[@]} * 10 ))
COUNT=0
ESTIMATED_SECONDS=$((TOTAL_RUNS * (RUN_SECONDS + MONITOR_MARGIN_SECONDS + COOLDOWN_SECONDS)))
ESTIMATED_HOURS=$((ESTIMATED_SECONDS / 3600))
ESTIMATED_MINUTES=$(((ESTIMATED_SECONDS % 3600) / 60))

echo "Iniciando bateria de ${TOTAL_RUNS} execuções (BASE_URL=${BASE_URL})"
echo "Tempo estimado: ~${ESTIMATED_HOURS}h${ESTIMATED_MINUTES}min (${TOTAL_RUNS} x ~7min25s)"
echo

for SCENARIO in "${SCENARIOS[@]}"; do
  for PROFILE in "${PROFILES[@]}"; do
    for REP in $REPS; do
      COUNT=$((COUNT + 1))
      echo ">>> [$COUNT/$TOTAL_RUNS] Cenário=$SCENARIO Perfil=$PROFILE Repetição=$REP"
      # run_single.sh já trata falhas de requisição (resultado esperado do
      # experimento) sem retornar erro. Esta rede de segurança extra cobre
      # qualquer outro problema inesperado numa execução isolada, sem
      # derrubar a bateria inteira de 7h por causa de uma única execução.
      if ! bash "${SCRIPT_DIR}/run_single.sh" "$SCENARIO" "$PROFILE" "$REP" "$BASE_URL"; then
        echo "[aviso] Execução ${SCENARIO}_${PROFILE}_rep${REP} retornou erro inesperado — continuando com a próxima."
      fi
      # Pequena pausa entre execuções para a aplicação "esfriar"
      sleep "$COOLDOWN_SECONDS"
    done
  done
done

echo
echo "Todas as ${TOTAL_RUNS} execuções concluídas."
echo "Os resultados brutos estão em: ${SCRIPT_DIR}/../results/raw"
echo "Rode agora:"
echo "  python3 scripts/aggregate_results.py"
echo "  python3 scripts/generate_graphs.py"