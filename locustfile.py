import os
import random
import gevent

from locust import HttpUser, task, between, events

LOAD_PROFILE = os.environ.get("LOAD_PROFILE", "leitura").strip().lower()
WARMUP_SECONDS = int(os.environ.get("WARMUP_SECONDS", "60"))

# (GET /owners, GET /owners/{id}, GET /vets, POST /owners)
PROFILE_WEIGHTS = {
    "leitura": {"list_owners": 45, "get_owner": 35, "list_vets": 15, "create_owner": 5},
    "escrita": {"list_owners": 20, "get_owner": 20, "list_vets": 20, "create_owner": 40},
}

if LOAD_PROFILE not in PROFILE_WEIGHTS:
    raise ValueError(
        f"LOAD_PROFILE inválido: '{LOAD_PROFILE}'. Use 'leitura' ou 'escrita'."
    )

WEIGHTS = PROFILE_WEIGHTS[LOAD_PROFILE]

_SEED_OWNER_IDS = list(range(1, 11))

# Nomes/sobrenomes para gerar POST /owners com dados variados (evita que
# toda requisição de escrita insira exatamente o mesmo registro).
_FIRST_NAMES = ["Maria", "João", "Ana", "Pedro", "Lucas", "Carla", "Bruno", "Fernanda"]
_LAST_NAMES = ["Silva", "Souza", "Oliveira", "Pereira", "Costa", "Rodrigues", "Almeida"]
_CITIES = ["Teresina", "Parnaíba", "Picos", "Floriano", "Campo Maior"]


def _random_owner_payload():
    return {
        "firstName": random.choice(_FIRST_NAMES),
        "lastName": random.choice(_LAST_NAMES),
        "address": f"Rua {random.randint(1, 999)}",
        "city": random.choice(_CITIES),
        "telephone": f"{random.randint(1000000000, 9999999999)}",
    }


class PetClinicUser(HttpUser):

    host = os.environ.get("BASE_URL", "http://localhost:8080")
    wait_time = between(1, 3)
    known_owner_ids = list(_SEED_OWNER_IDS)

    def on_start(self):
        # Tenta descobrir IDs reais de owners para as consultas por ID.
        with self.client.get(
            "/api/customer/owners", name="GET /api/customer/owners (on_start)", catch_response=True
        ) as resp:
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    ids = [o["id"] for o in data if "id" in o]
                    if ids:
                        self.known_owner_ids = ids
                except Exception:
                    pass
                resp.success()
            else:
                resp.failure(f"on_start falhou: {resp.status_code}")

    @task(WEIGHTS["list_owners"])
    def list_owners(self):
        self.client.get("/api/customer/owners", name="GET /api/customer/owners")

    @task(WEIGHTS["get_owner"])
    def get_owner(self):
        owner_id = random.choice(self.known_owner_ids)
        self.client.get(
            f"/api/customer/owners/{owner_id}", name="GET /api/customer/owners/[id]"
        )

    @task(WEIGHTS["list_vets"])
    def list_vets(self):
        self.client.get("/api/vet/vets", name="GET /api/vet/vets")

    @task(WEIGHTS["create_owner"])
    def create_owner(self):
        self.client.post(
            "/api/customer/owners",
            json=_random_owner_payload(),
            name="POST /api/customer/owners",
        )

@events.test_start.add_listener
def _schedule_warmup_reset(environment, **kwargs):
    if environment.runner is None:
        return

    def _reset_after_warmup():
        gevent.sleep(WARMUP_SECONDS)
        environment.runner.stats.reset_all()
        print(
            f"[warmup] {WARMUP_SECONDS}s decorridos — estatísticas resetadas, "
            f"iniciando janela de medição (perfil={LOAD_PROFILE})."
        )

    # Apenas o processo master (ou um processo standalone) deve resetar.
    if environment.runner.__class__.__name__ in ("LocalRunner", "MasterRunner"):
        gevent.spawn(_reset_after_warmup)


@events.test_start.add_listener
def _log_start(environment, **kwargs):
    print(
        f"[start] Perfil={LOAD_PROFILE} | host={environment.host} | "
        f"warmup={WARMUP_SECONDS}s"
    )
