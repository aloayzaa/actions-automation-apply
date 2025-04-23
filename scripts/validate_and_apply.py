import os
import re
import requests
import json
from tabulate import tabulate

# Cargar variables de entorno
TFC_TOKEN = os.getenv("TFC_TOKEN")
RUN_URL = os.getenv("RUN_URL")

# Configuración de API
TFC_API = "https://app.terraform.io/api/v2"
HEADERS = {
    "Authorization": f"Bearer " + TFC_TOKEN,
    "Content-Type": "application/vnd.api+json"
}

def extract_run_id(url):
    match = re.search(r"runs/(run-[\w\d]+)", url)
    if match:
        return match.group(1)
    print("❌ No se pudo extraer el run_id de la URL.")
    exit(1)

def get_plan_id(run_id):
    response = requests.get(f"{TFC_API}/runs/{run_id}", headers=HEADERS)
    response.raise_for_status()
    return response.json()["data"]["relationships"]["plan"]["data"]["id"]

def get_plan_json(plan_id):
    response = requests.get(f"{TFC_API}/plans/{plan_id}/json-output", headers=HEADERS)
    response.raise_for_status()
    return response.json()

def analyze_plan(plan_json):
    changes = plan_json.get("resource_changes", [])
    table = []
    only_add = True

    counts = {
        "create": 0,
        "update": 0,
        "delete": 0,
        "replace": 0,
        "unknown": 0
    }

    for change in changes:
        actions = change["change"]["actions"]
        address = change["address"]
        action_str = ", ".join(actions)
        table.append([address, action_str])

        if actions == ["create"]:
            counts["create"] += 1
        elif actions == ["update"]:
            counts["update"] += 1
            only_add = False
        elif actions == ["delete"]:
            counts["delete"] += 1
            only_add = False
        elif actions == ["delete", "create"]:
            counts["replace"] += 1
            only_add = False
        else:
            counts["unknown"] += 1
            only_add = False

    # Mostrar resumen en consola
    print(tabulate(table, headers=["Recurso", "Acción"], tablefmt="fancy_grid"))
    print("\n📊 Resumen:")
    for k, v in counts.items():
        print(f"  {k.capitalize()}: {v}")

    # Guardar archivo TXT
    with open("plan_summary.txt", "w") as f:
        f.write("Resumen del plan de Terraform:\n\n")
        for row in table:
            f.write(f"- {row[0]} => {row[1]}\n")
        f.write("\nResumen total:\n")
        for k, v in counts.items():
            f.write(f"{k.capitalize()}: {v}\n")

    # Guardar archivo JSON
    summary_data = {
        "resource_changes": [{"resource": r[0], "action": r[1]} for r in table],
        "counts": counts,
        "only_add": only_add
    }

    with open("plan_summary.json", "w") as f:
        json.dump(summary_data, f, indent=2)

    return only_add

def apply_run(run_id):
    response = requests.post(f"{TFC_API}/runs/{run_id}/actions/apply", headers=HEADERS)
    if response.status_code in [200, 201, 202]:
        print("✅ Apply iniciado correctamente.")
    else:
        print(f"❌ Error al iniciar apply. Código: {response.status_code}, Respuesta: {response.text}")
        exit(1)

if __name__ == "__main__":
    run_id = extract_run_id(RUN_URL)
    print(f"🔎 Run ID detectado: {run_id}")

    plan_id = get_plan_id(run_id)
    print(f"📄 Plan ID: {plan_id}")

    plan_json = get_plan_json(plan_id)
    print("📊 Analizando plan...\n")

    if analyze_plan(plan_json):
        print("✅ Plan válido. Ejecutando apply...\n")
        apply_run(run_id)
    else:
        print("⛔️ Plan contiene acciones que no son solo `create`. Apply cancelado.")
        exit(1)
