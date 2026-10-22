import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(PROJECT_DIR, "results", "processed")
GRAPHS_DIR = os.path.join(PROJECT_DIR, "results", "graphs")

SCENARIO_ORDER = ["A", "B", "C"]
SCENARIO_LABELS = {"A": "A — Leve (30)", "B": "B — Moderado (80)", "C": "C — Elevado (150)"}
PROFILE_LABELS = {"leitura": "Perfil 1 — Leitura", "escrita": "Perfil 2 — Escrita"}
COLORS = {"leitura": "#2563eb", "escrita": "#dc2626"}


def load_summary():
    path = os.path.join(PROCESSED_DIR, "summary.csv")
    if not os.path.isfile(path):
        raise SystemExit(
            f"Não encontrei {path}. Rode scripts/aggregate_results.py primeiro."
        )
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def grouped_bar(rows, value_field, ylabel, title, out_name, scale=1.0):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(SCENARIO_ORDER))
    width = 0.35

    for i, profile in enumerate(["leitura", "escrita"]):
        values = []
        for scenario in SCENARIO_ORDER:
            match = [r for r in rows if r["scenario"] == scenario and r["profile"] == profile]
            v = float(match[0][value_field]) * scale if match and match[0][value_field] != "" else 0
            values.append(v)
        offset = (i - 0.5) * width
        ax.bar(
            [xi + offset for xi in x],
            values,
            width,
            label=PROFILE_LABELS[profile],
            color=COLORS[profile],
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIO_ORDER])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    out_path = os.path.join(GRAPHS_DIR, out_name)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Gravado: {out_path}")


def cpu_graph(rows):
    cpu_fields = sorted({k for r in rows for k in r.keys() if k.startswith("cpu_")})
    if not cpu_fields:
        print("[aviso] nenhuma coluna de CPU encontrada em summary.csv — pulando cpu_servicos.png")
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(SCENARIO_ORDER))
    width = 0.8 / max(len(cpu_fields), 1)

    for i, field in enumerate(cpu_fields):
        service_name = field.replace("cpu_", "").replace("_pct", "")
        values = []
        for scenario in SCENARIO_ORDER:
            # média entre os dois perfis para o gráfico de CPU por cenário
            match = [r for r in rows if r["scenario"] == scenario and r.get(field, "")]
            vals = [float(r[field]) for r in match if r.get(field, "")]
            values.append(sum(vals) / len(vals) if vals else 0)
        offset = (i - (len(cpu_fields) - 1) / 2) * width
        ax.bar([xi + offset for xi in x], values, width, label=service_name)

    ax.set_xticks(list(x))
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIO_ORDER])
    ax.set_ylabel("CPU média (%)")
    ax.set_title("Utilização de CPU por serviço e cenário")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    out_path = os.path.join(GRAPHS_DIR, "cpu_servicos.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Gravado: {out_path}")


def main():
    os.makedirs(GRAPHS_DIR, exist_ok=True)
    rows = load_summary()

    grouped_bar(
        rows, "avg_response_ms", "Tempo médio de resposta (ms)",
        "Tempo médio de resposta por cenário e perfil", "tempo_resposta.png",
    )
    grouped_bar(
        rows, "p95_ms", "Tempo de resposta P95 (ms)",
        "Tempo de resposta P95 por cenário e perfil", "tempo_resposta_p95.png",
    )
    grouped_bar(
        rows, "throughput_rps", "Vazão (req/s)",
        "Vazão por cenário e perfil", "vazao.png",
    )
    grouped_bar(
        rows, "failure_rate_pct", "Taxa de falhas (%)",
        "Taxa de falhas por cenário e perfil", "taxa_falhas.png",
    )
    cpu_graph(rows)


if __name__ == "__main__":
    main()
