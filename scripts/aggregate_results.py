import csv
import glob
import os
import statistics as stats

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_DIR, "results", "raw")
PROCESSED_DIR = os.path.join(PROJECT_DIR, "results", "processed")

SCENARIOS = ["A", "B", "C"]
SCENARIO_USERS = {"A": 30, "B": 80, "C": 150}
PROFILES = ["leitura", "escrita"]
N_REPS = 10
WARMUP_SECONDS = 60


def read_locust_stats(stats_csv_path):
    """Lê a linha 'Aggregated' de um *_stats.csv do Locust."""
    if not os.path.isfile(stats_csv_path):
        return None
    with open(stats_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Name", "").strip() == "Aggregated":
                try:
                    req_count = int(float(row["Request Count"]))
                    fail_count = int(float(row["Failure Count"]))
                    return {
                        "avg_response_ms": float(row["Average Response Time"]),
                        "p95_ms": float(row.get("95%", row.get('"95%"', "nan"))),
                        "throughput_rps": float(row["Requests/s"]),
                        "request_count": req_count,
                        "failure_count": fail_count,
                        "failure_rate_pct": (fail_count / req_count * 100.0) if req_count else 0.0,
                    }
                except (KeyError, ValueError):
                    return None
    return None


def read_cpu_stats(cpu_csv_path, warmup_seconds=WARMUP_SECONDS):
    """
    Lê o CSV de CPU (timestamp,container,cpu_percent,mem_usage) e calcula a
    média de CPU% por container, descartando as amostras do aquecimento.
    """
    if not os.path.isfile(cpu_csv_path):
        return {}
    rows = []
    with open(cpu_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append(
                    {
                        "timestamp": int(row["timestamp"]),
                        "container": row["container"],
                        "cpu_percent": float(row["cpu_percent"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    if not rows:
        return {}
    t0 = min(r["timestamp"] for r in rows)
    measured = [r for r in rows if r["timestamp"] - t0 >= warmup_seconds]
    by_container = {}
    for r in measured:
        by_container.setdefault(r["container"], []).append(r["cpu_percent"])
    return {c: stats.mean(v) for c, v in by_container.items() if v}


def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    per_run_rows = []

    for scenario in SCENARIOS:
        for profile in PROFILES:
            for rep in range(1, N_REPS + 1):
                run_id = f"{scenario}_{profile}_rep{rep}"
                stats_csv = os.path.join(RAW_DIR, f"{run_id}_stats.csv")
                cpu_csv = os.path.join(RAW_DIR, f"{run_id}_cpu.csv")

                locust_stats = read_locust_stats(stats_csv)
                if locust_stats is None:
                    print(f"[aviso] faltando ou inválido: {stats_csv}")
                    continue
                cpu_stats = read_cpu_stats(cpu_csv)

                row = {
                    "scenario": scenario,
                    "users": SCENARIO_USERS[scenario],
                    "profile": profile,
                    "repetition": rep,
                    **locust_stats,
                }
                for container, cpu_avg in cpu_stats.items():
                    row[f"cpu_{container}_pct"] = round(cpu_avg, 2)
                per_run_rows.append(row)

    if not per_run_rows:
        print(
            "Nenhuma execução encontrada em results/raw/. Rode "
            "scripts/run_all_experiments.sh (ou run_single.sh) primeiro."
        )
        return

    # --- per_run.csv --------------------------------------------------
    all_fields = sorted({k for row in per_run_rows for k in row.keys()})
    ordered_fields = ["scenario", "users", "profile", "repetition"] + [
        f for f in all_fields if f not in ("scenario", "users", "profile", "repetition")
    ]
    per_run_path = os.path.join(PROCESSED_DIR, "per_run.csv")
    with open(per_run_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ordered_fields)
        writer.writeheader()
        for row in per_run_rows:
            writer.writerow(row)
    print(f"Gravado: {per_run_path} ({len(per_run_rows)} execuções)")

    # --- summary.csv (média das 10 repetições por cenário/perfil) -----
    groups = {}
    for row in per_run_rows:
        key = (row["scenario"], row["profile"])
        groups.setdefault(key, []).append(row)

    cpu_field_names = sorted(
        {k for row in per_run_rows for k in row.keys() if k.startswith("cpu_")}
    )
    numeric_fields = [
        "avg_response_ms",
        "p95_ms",
        "throughput_rps",
        "request_count",
        "failure_count",
        "failure_rate_pct",
    ] + cpu_field_names

    summary_rows = []
    for (scenario, profile), rows in sorted(groups.items()):
        summary = {
            "scenario": scenario,
            "users": SCENARIO_USERS[scenario],
            "profile": profile,
            "n_repeticoes": len(rows),
        }
        for field in numeric_fields:
            values = [r[field] for r in rows if field in r]
            summary[field] = round(stats.mean(values), 2) if values else ""
        summary_rows.append(summary)

    summary_path = os.path.join(PROCESSED_DIR, "summary.csv")
    summary_fields = ["scenario", "users", "profile", "n_repeticoes"] + numeric_fields
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)
    print(f"Gravado: {summary_path} ({len(summary_rows)} configurações)")

    # --- summary.md (tabela pronta para colar no README) ---------------
    md_path = os.path.join(PROCESSED_DIR, "summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("| Cenário | Usuários | Perfil | Tempo médio (ms) | P95 (ms) | "
                "Vazão (req/s) | Total req. | Taxa de falhas (%) | "
                + " | ".join(f"CPU {c.replace('cpu_', '').replace('_pct', '')} (%)" for c in cpu_field_names)
                + " |\n")
        f.write("|---" * (8 + len(cpu_field_names)) + "|\n")
        for row in summary_rows:
            cpu_cells = " | ".join(str(row.get(c, "")) for c in cpu_field_names)
            f.write(
                f"| {row['scenario']} | {row['users']} | {row['profile']} | "
                f"{row['avg_response_ms']} | {row['p95_ms']} | "
                f"{row['throughput_rps']} | {row['request_count']} | "
                f"{row['failure_rate_pct']} | {cpu_cells} |\n"
            )
    print(f"Gravado: {md_path}")


if __name__ == "__main__":
    main()
