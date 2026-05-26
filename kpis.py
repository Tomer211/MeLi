import json
import os
from datetime import datetime, timedelta

import requests

MELI_BASE = "https://api.mercadolibre.com"
DATA_DIR = "data"


def _get(token, url, params=None):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        print(f"[kpis] {url} → {r.status_code}")
    except Exception as e:
        print(f"[kpis] Error GET {url}: {e}")
    return None


def capturar_kpis(token, user_id):
    """Captura todos los KPIs actuales del cliente desde la API de MeLi."""
    kpis = {
        "fecha_captura": datetime.now().isoformat(),
        "reputacion": {
            "nivel": "",
            "power_seller": "",
            "ventas_completadas": 0,
            "calificaciones_positivas": 0,
            "calificaciones_negativas": 0,
            "reclamos_porcentaje": 0.0,
            "cancelaciones_porcentaje": 0.0,
            "demora_porcentaje": 0.0,
        },
        "preguntas_sin_responder": 0,
        "ventas_ultimo_mes": 0,
        "publicaciones_activas": 0,
    }

    # Reputación
    rep = _get(token, f"{MELI_BASE}/users/{user_id}/reputation")
    if rep:
        m = rep.get("metrics", {})
        kpis["reputacion"] = {
            "nivel": rep.get("level_id", ""),
            "power_seller": rep.get("power_seller_status") or "",
            "ventas_completadas": rep.get("transactions", {}).get("completed", 0),
            "calificaciones_positivas": rep.get("transactions", {}).get("ratings", {}).get("positive", 0),
            "calificaciones_negativas": rep.get("transactions", {}).get("ratings", {}).get("negative", 0),
            "reclamos_porcentaje": round(m.get("claims", {}).get("rate", 0) * 100, 2),
            "cancelaciones_porcentaje": round(m.get("cancellations", {}).get("rate", 0) * 100, 2),
            "demora_porcentaje": round(m.get("delayed_handling_time", {}).get("rate", 0) * 100, 2),
        }

    # Preguntas sin responder (solo el total, sin traer todos los datos)
    preguntas = _get(token, f"{MELI_BASE}/questions/search", {
        "seller_id": user_id,
        "status": "UNANSWERED",
        "limit": 1,
    })
    if preguntas:
        kpis["preguntas_sin_responder"] = preguntas.get("paging", {}).get("total", 0)

    # Ventas último mes (total de órdenes pagadas en los últimos 30 días)
    hace_30 = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000-00:00")
    ventas = _get(token, f"{MELI_BASE}/orders/search", {
        "seller": user_id,
        "order.status": "paid",
        "order.date_created.from": hace_30,
        "limit": 1,
    })
    if ventas:
        kpis["ventas_ultimo_mes"] = ventas.get("paging", {}).get("total", 0)

    # Publicaciones activas
    items = _get(token, f"{MELI_BASE}/users/{user_id}/items/search", {
        "status": "active",
        "limit": 1,
    })
    if items:
        kpis["publicaciones_activas"] = items.get("paging", {}).get("total", 0)

    return kpis


def guardar_kpis_inicial(cliente_id, kpis):
    carpeta = os.path.join(DATA_DIR, f"cliente_{cliente_id}")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "kpis_inicial.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(kpis, f, ensure_ascii=False, indent=2)
    print(f"[kpis] KPIs iniciales guardados para cliente {cliente_id}")


def leer_kpis_inicial(cliente_id):
    ruta = os.path.join(DATA_DIR, f"cliente_{cliente_id}", "kpis_inicial.json")
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def construir_comparacion(inicial, actual):
    """
    Devuelve una lista de filas para la tabla de comparación.
    mejor='mayor' → delta positivo es bueno (verde)
    mejor='menor' → delta negativo es bueno (verde)
    """
    rep_i = inicial.get("reputacion", {})
    rep_a = actual.get("reputacion", {})

    filas = []

    # Nivel de reputación (texto, sin delta numérico)
    nivel_i = rep_i.get("nivel", "—")
    nivel_a = rep_a.get("nivel", "—")
    filas.append({
        "metrica": "Nivel de reputación",
        "inicial": nivel_i,
        "actual": nivel_a,
        "delta": "—" if nivel_i == nivel_a else f"{nivel_i} → {nivel_a}",
        "tipo": "texto",
        "mejor": None,
    })

    # Métricas numéricas
    def fila_num(label, clave_i, clave_a, mejor, sufijo=""):
        v_i = clave_i if isinstance(clave_i, (int, float)) else 0
        v_a = clave_a if isinstance(clave_a, (int, float)) else 0
        delta = v_a - v_i
        return {
            "metrica": label,
            "inicial": f"{v_i}{sufijo}",
            "actual": f"{v_a}{sufijo}",
            "delta": delta,
            "tipo": "numero",
            "mejor": mejor,
            "sufijo": sufijo,
        }

    filas.append(fila_num("Ventas completadas (total)",
                           rep_i.get("ventas_completadas", 0),
                           rep_a.get("ventas_completadas", 0), "mayor"))
    filas.append(fila_num("Calificaciones positivas",
                           rep_i.get("calificaciones_positivas", 0),
                           rep_a.get("calificaciones_positivas", 0), "mayor"))
    filas.append(fila_num("Calificaciones negativas",
                           rep_i.get("calificaciones_negativas", 0),
                           rep_a.get("calificaciones_negativas", 0), "menor"))
    filas.append(fila_num("Reclamos (%)",
                           rep_i.get("reclamos_porcentaje", 0),
                           rep_a.get("reclamos_porcentaje", 0), "menor", "%"))
    filas.append(fila_num("Cancelaciones (%)",
                           rep_i.get("cancelaciones_porcentaje", 0),
                           rep_a.get("cancelaciones_porcentaje", 0), "menor", "%"))
    filas.append(fila_num("Demora en entregas (%)",
                           rep_i.get("demora_porcentaje", 0),
                           rep_a.get("demora_porcentaje", 0), "menor", "%"))
    filas.append(fila_num("Preguntas sin responder",
                           inicial.get("preguntas_sin_responder", 0),
                           actual.get("preguntas_sin_responder", 0), "menor"))
    filas.append(fila_num("Ventas último mes",
                           inicial.get("ventas_ultimo_mes", 0),
                           actual.get("ventas_ultimo_mes", 0), "mayor"))
    filas.append(fila_num("Publicaciones activas",
                           inicial.get("publicaciones_activas", 0),
                           actual.get("publicaciones_activas", 0), "mayor"))

    return filas
