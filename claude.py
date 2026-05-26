import os
import requests

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"


def _formatear_faq(faq_list):
    if not faq_list:
        return "Sin preguntas frecuentes cargadas."
    lines = []
    for item in faq_list:
        q = item.get("pregunta", "").strip()
        a = item.get("respuesta", "").strip()
        if q and a:
            lines.append(f"P: {q}\nR: {a}")
    return "\n\n".join(lines) if lines else "Sin preguntas frecuentes cargadas."


def generar_respuesta(config, pregunta_texto, producto):
    negocio = config.get("negocio", {})
    nombre = config.get("nombre_negocio", "la tienda")
    faq_texto = _formatear_faq(config.get("faq", []))

    system = f"""Sos el asistente de atención al cliente de {nombre}.

Tu único trabajo es responder preguntas de compradores en Mercado Libre de forma clara, amable y concisa.

INFORMACIÓN DEL NEGOCIO:
- Categoría de productos: {negocio.get('categoria', 'N/D')}
- Zonas de envío: {negocio.get('zonas_envio', 'N/D')}
- Tiempo de entrega: {negocio.get('tiempo_entrega', 'N/D')}
- Formas de pago: {negocio.get('formas_pago', 'N/D')}
- Garantía: {negocio.get('garantia', 'N/D')}
- Política de devoluciones: {negocio.get('politica_devoluciones', 'N/D')}

PREGUNTAS FRECUENTES Y RESPUESTAS EXACTAS:
{faq_texto}

REGLAS QUE NUNCA PODÉS ROMPER:
1. Máximo 3 líneas por respuesta
2. Tono: {negocio.get('tono', 'cercano')}
3. Respondé en el mismo idioma del comprador
4. Si no tenés el dato exacto, respondé: 'Consultamos y te avisamos en menos de 1 hora'
5. Nunca inventes información
6. Nunca menciones a la competencia
7. Nunca hagas promesas que no estén en la información del negocio
8. Si la pregunta es sobre precio, confirmá el precio que figura en la publicación"""

    user = f"""PRODUCTO CONSULTADO:
Título: {producto.get('titulo', '')}
Descripción: {producto.get('descripcion', '')}
Precio: {producto.get('precio', '')}
Características: {producto.get('atributos', '')}

PREGUNTA DEL COMPRADOR:
{pregunta_texto}

Respondé esta pregunta siguiendo estrictamente las reglas del system prompt."""

    headers = {
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 200,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    for intento in range(3):
        try:
            r = requests.post(ANTHROPIC_API, json=payload, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()["content"][0]["text"].strip()
            print(f"[claude] Intento {intento + 1}: status {r.status_code}")
        except Exception as e:
            print(f"[claude] Intento {intento + 1} fallido: {e}")

    return None
