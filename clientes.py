import json
import os

DATA_DIR = "data"


def listar_clientes_activos():
    todos = listar_todos_clientes()
    return [c for c in todos if c.get("activo", False)]


def listar_todos_clientes():
    resultado = []
    if not os.path.exists(DATA_DIR):
        return resultado
    for carpeta in sorted(os.listdir(DATA_DIR)):
        if not carpeta.startswith("cliente_"):
            continue
        ruta = os.path.join(DATA_DIR, carpeta, "config.json")
        if os.path.isfile(ruta):
            config = _leer_json(ruta)
            if config:
                resultado.append(config)
    return resultado


def cargar_cliente(cliente_id):
    ruta = os.path.join(DATA_DIR, f"cliente_{cliente_id}", "config.json")
    return _leer_json(ruta)


def guardar_cliente(cliente_id, datos):
    carpeta = os.path.join(DATA_DIR, f"cliente_{cliente_id}")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "config.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def pausar_cliente(cliente_id):
    config = cargar_cliente(cliente_id)
    if config:
        config["activo"] = False
        guardar_cliente(cliente_id, config)


def activar_cliente(cliente_id):
    config = cargar_cliente(cliente_id)
    if config:
        config["activo"] = True
        guardar_cliente(cliente_id, config)


def guardar_log(cliente_id, entrada):
    carpeta = os.path.join(DATA_DIR, f"cliente_{cliente_id}")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "log.json")
    logs = _leer_json(ruta) or []
    logs.insert(0, entrada)
    logs = logs[:500]
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def leer_log(cliente_id, limite=50):
    ruta = os.path.join(DATA_DIR, f"cliente_{cliente_id}", "log.json")
    logs = _leer_json(ruta) or []
    return logs[:limite]


def proximo_id():
    existentes = []
    if os.path.exists(DATA_DIR):
        for carpeta in os.listdir(DATA_DIR):
            if carpeta.startswith("cliente_"):
                try:
                    existentes.append(int(carpeta.split("_")[1]))
                except (ValueError, IndexError):
                    pass
    return str(max(existentes, default=0) + 1).zfill(3)


def _leer_json(ruta):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
