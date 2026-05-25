import os
import requests
import time
from datetime import datetime, timedelta

MELI_BASE = "https://api.mercadolibre.com"


def obtener_user_id(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{MELI_BASE}/users/me", headers=headers, timeout=10)
        if r.status_code == 200:
            return str(r.json().get("id", ""))
    except Exception as e:
        print(f"[meli] Error obteniendo user_id: {e}")
    return ""


def renovar_token(cliente_id, config):
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": os.environ.get("MELI_CLIENT_ID", ""),
        "client_secret": os.environ.get("MELI_CLIENT_SECRET", ""),
        "refresh_token": config["meli"]["refresh_token"],
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "token_expira": (
                    datetime.utcnow() + timedelta(seconds=data["expires_in"] - 300)
                ).isoformat(),
            }
        print(f"[meli] Renovación fallida para {cliente_id}: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[meli] Error renovando token cliente {cliente_id}: {e}")
    return None


def token_valido(config):
    expira = config["meli"].get("token_expira", "")
    if not expira:
        return False
    try:
        return datetime.utcnow() < datetime.fromisoformat(expira)
    except Exception:
        return False


def obtener_preguntas(token, user_id):
    url = f"{MELI_BASE}/questions/search"
    params = {
        "seller_id": user_id,
        "status": "UNANSWERED",
        "sort_fields": "date_created",
        "sort_types": "DESC",
        "limit": 50,
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("questions", [])
        if r.status_code == 429:
            print("[meli] Rate limit — esperando 60 segundos")
            time.sleep(60)
            r = requests.get(url, params=params, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json().get("questions", [])
        print(f"[meli] Error preguntas: {r.status_code}")
    except Exception as e:
        print(f"[meli] Error obteniendo preguntas: {e}")
    return []


def obtener_producto(token, item_id):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{MELI_BASE}/items/{item_id}", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            atributos = [
                f"{a['name']}: {a.get('value_name', '')}"
                for a in data.get("attributes", [])[:10]
                if a.get("value_name")
            ]
            return {
                "titulo": data.get("title", ""),
                "precio": data.get("price", ""),
                "descripcion": "",
                "atributos": "\n".join(atributos),
            }
    except Exception as e:
        print(f"[meli] Error obteniendo producto {item_id}: {e}")
    return {"titulo": "", "precio": "", "descripcion": "", "atributos": ""}


def publicar_respuesta(token, question_id, texto):
    url = f"{MELI_BASE}/answers"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"question_id": question_id, "text": texto}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        return r.status_code == 200, r.json()
    except Exception as e:
        print(f"[meli] Error publicando respuesta: {e}")
        return False, str(e)
