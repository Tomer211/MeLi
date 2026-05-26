import json
import os
import threading
from datetime import date, datetime

from flask import Flask, redirect, render_template_string, request

from clientes import (
    activar_cliente,
    cargar_cliente,
    guardar_cliente,
    leer_log,
    listar_todos_clientes,
    pausar_cliente,
    proximo_id,
)
from meli import obtener_user_id, token_valido

app = Flask(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _mascara(token):
    if not token:
        return "—"
    return token[:8] + "..." if len(token) > 8 else token


def _stats_hoy(cliente_id):
    hoy = date.today().isoformat()
    logs = leer_log(cliente_id, 500)
    return {
        "respondidas": sum(1 for l in logs if l.get("fecha", "").startswith(hoy) and l.get("estado") == "publicada"),
        "manuales": sum(1 for l in logs if l.get("fecha", "").startswith(hoy) and l.get("estado") == "manual"),
        "errores": sum(1 for l in logs if l.get("fecha", "").startswith(hoy) and l.get("estado") == "error"),
    }


# ── CSS / base ─────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f4f5f7; color: #172b4d; min-height: 100vh; }
nav { background: #fff; border-bottom: 2px solid #ffe58f; padding: .9rem 2rem;
      display: flex; align-items: center; gap: 1.2rem; position: sticky; top: 0; z-index: 10; }
nav .brand { font-weight: 700; font-size: 1.1rem; color: #f5a623; margin-right: auto; }
nav a { text-decoration: none; color: #172b4d; font-size: .9rem; padding: .4rem .8rem;
        border-radius: 6px; }
nav a:hover { background: #f4f5f7; }
.container { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
.page-title { font-size: 1.4rem; font-weight: 700; margin-bottom: 1.5rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 1.2rem; }
.card { background: #fff; border-radius: 12px; padding: 1.4rem;
        box-shadow: 0 1px 8px rgba(0,0,0,.07); }
.card-title { font-size: 1rem; font-weight: 700; margin-bottom: .6rem; }
.badge { display: inline-block; padding: .2rem .65rem; border-radius: 20px;
         font-size: .78rem; font-weight: 600; }
.badge-green  { background: #e3fcef; color: #006644; }
.badge-red    { background: #ffebe6; color: #bf2600; }
.badge-blue   { background: #deebff; color: #0747a6; }
.badge-yellow { background: #fffae6; color: #974f0c; }
.badge-gray   { background: #f4f5f7; color: #5e6c84; }
.stat-row { display: flex; justify-content: space-between; align-items: center;
            padding: .35rem 0; border-bottom: 1px solid #f4f5f7; font-size: .88rem; }
.stat-row:last-child { border-bottom: none; }
.stat-val { font-weight: 700; }
.btn { display: inline-flex; align-items: center; gap: .4rem; padding: .45rem 1rem;
       border-radius: 7px; border: none; cursor: pointer; font-size: .88rem;
       font-family: inherit; text-decoration: none; transition: opacity .15s; }
.btn:hover { opacity: .85; }
.btn-primary  { background: #f5a623; color: #fff; font-weight: 600; }
.btn-success  { background: #36b37e; color: #fff; }
.btn-danger   { background: #ff5630; color: #fff; }
.btn-outline  { background: #fff; color: #172b4d; border: 1px solid #dfe1e6; }
.btn-sm { padding: .3rem .7rem; font-size: .82rem; }
.actions { display: flex; gap: .5rem; margin-top: 1rem; flex-wrap: wrap; }
.alert { padding: 1rem 1.2rem; border-radius: 8px; margin-bottom: 1.2rem; font-size: .9rem; }
.alert-info    { background: #deebff; color: #0747a6; }
.alert-success { background: #e3fcef; color: #006644; }
.alert-warn    { background: #fffae6; color: #974f0c; }
table { width: 100%; border-collapse: collapse; }
th { background: #f4f5f7; padding: .55rem .8rem; text-align: left;
     font-size: .82rem; font-weight: 700; color: #5e6c84; text-transform: uppercase; }
td { padding: .6rem .8rem; border-bottom: 1px solid #f4f5f7; font-size: .88rem;
     vertical-align: top; word-break: break-word; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbff; }
.form-section { margin-bottom: 2rem; }
.form-section h3 { font-size: .95rem; font-weight: 700; color: #5e6c84;
                   text-transform: uppercase; letter-spacing: .05em;
                   margin-bottom: 1rem; padding-bottom: .4rem;
                   border-bottom: 2px solid #f4f5f7; }
.form-group { margin-bottom: .9rem; }
label { display: block; margin-bottom: .3rem; font-size: .88rem; font-weight: 600; }
.hint { font-size: .8rem; color: #5e6c84; margin-top: .25rem; }
input[type=text], input[type=email], textarea, select {
  width: 100%; padding: .5rem .75rem; border: 1.5px solid #dfe1e6;
  border-radius: 6px; font-size: .9rem; font-family: inherit;
  transition: border-color .15s; }
input[type=text]:focus, input[type=email]:focus, textarea:focus, select:focus {
  outline: none; border-color: #f5a623; }
textarea { resize: vertical; }
.checkbox-label { display: flex; align-items: center; gap: .5rem;
                  font-size: .9rem; cursor: pointer; }
.faq-row { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin-bottom: .5rem; }
"""

BASE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titulo }} — MeLi Auto-Responder</title>
<style>{{ css | safe }}</style>
</head>
<body>
<nav>
  <span class="brand">🛒 MeLi Auto-Responder</span>
  <a href="/">Dashboard</a>
  <a href="/cliente/nuevo">+ Nuevo cliente</a>
  <form action="/correr-ahora" method="post" style="margin:0">
    <button class="btn btn-primary btn-sm" type="submit">▶ Correr ahora</button>
  </form>
</nav>
<div class="container">
{{ content | safe }}
</div>
</body>
</html>"""


def render(titulo, content, **kwargs):
    return render_template_string(
        BASE,
        titulo=titulo,
        css=CSS,
        content=render_template_string(content, **kwargs),
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

DASHBOARD_CONTENT = """
<div class="page-title">Dashboard — {{ fecha }}</div>

{% if flash %}
<div class="alert alert-success">{{ flash }}</div>
{% endif %}

{% if not clientes %}
<div class="alert alert-info">
  No hay clientes todavía.
  <a href="/cliente/nuevo" style="font-weight:700">Agregar el primero →</a>
</div>
{% endif %}

<div class="grid">
{% for c in clientes %}
<div class="card">
  <div class="card-title">{{ c.nombre }}</div>
  <div style="margin-bottom:.8rem">
    <span class="badge {{ 'badge-green' if c.activo else 'badge-gray' }}">
      {{ 'Activo' if c.activo else 'Pausado' }}
    </span>
    <span class="badge {{ 'badge-blue' if c.token_ok else 'badge-yellow' }}" style="margin-left:.3rem">
      Token {{ 'vigente' if c.token_ok else 'expirado' }}
    </span>
  </div>
  <div>
    <div class="stat-row">
      <span>Respondidas hoy</span>
      <span class="stat-val">{{ c.respondidas }}</span>
    </div>
    <div class="stat-row">
      <span>Escaladas a manual hoy</span>
      <span class="stat-val">{{ c.manuales }}</span>
    </div>
    <div class="stat-row">
      <span>Errores hoy</span>
      <span class="stat-val">{{ c.errores }}</span>
    </div>
    <div class="stat-row">
      <span>User ID</span>
      <span class="stat-val" style="font-size:.8rem;color:#5e6c84">{{ c.user_id or '—' }}</span>
    </div>
  </div>
  <div class="actions">
    <a class="btn btn-outline btn-sm" href="/cliente/{{ c.id }}">Ver actividad</a>
    <a class="btn btn-outline btn-sm" href="/cliente/{{ c.id }}/editar">Editar</a>
    {% if c.activo %}
    <form action="/cliente/{{ c.id }}/pausar" method="post" style="margin:0">
      <button class="btn btn-danger btn-sm" type="submit">Pausar</button>
    </form>
    {% else %}
    <form action="/cliente/{{ c.id }}/activar" method="post" style="margin:0">
      <button class="btn btn-success btn-sm" type="submit">Activar</button>
    </form>
    {% endif %}
  </div>
</div>
{% endfor %}
</div>
"""


@app.route("/")
def dashboard():
    clientes = listar_todos_clientes()
    tarjetas = []
    for c in clientes:
        stats = _stats_hoy(c["cliente_id"])
        tarjetas.append({
            "id": c["cliente_id"],
            "nombre": c.get("nombre_negocio", "—"),
            "activo": c.get("activo", False),
            "token_ok": token_valido(c),
            "user_id": c.get("meli", {}).get("user_id", ""),
            **stats,
        })
    flash = request.args.get("flash", "")
    return render("Dashboard", DASHBOARD_CONTENT, clientes=tarjetas,
                  fecha=date.today().strftime("%d/%m/%Y"), flash=flash)


# ── Detalle cliente ───────────────────────────────────────────────────────────

DETALLE_CONTENT = """
<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap">
  <div class="page-title" style="margin:0">{{ nombre }}</div>
  <span class="badge {{ 'badge-green' if activo else 'badge-gray' }}">
    {{ 'Activo' if activo else 'Pausado' }}
  </span>
  <div style="margin-left:auto;display:flex;gap:.5rem">
    <a class="btn btn-outline btn-sm" href="/cliente/{{ id }}/editar">Editar</a>
    <a class="btn btn-outline btn-sm" href="/reporte/{{ id }}">Reporte del mes</a>
  </div>
</div>

<div class="card">
  {% if not logs %}
  <div style="text-align:center;padding:2rem;color:#5e6c84">Sin actividad registrada todavía.</div>
  {% else %}
  <div style="overflow-x:auto">
  <table>
    <thead><tr>
      <th>Fecha y hora</th>
      <th>Pregunta</th>
      <th>Respuesta generada</th>
      <th>Producto</th>
      <th>Estado</th>
    </tr></thead>
    <tbody>
    {% for l in logs %}
    <tr>
      <td style="white-space:nowrap;color:#5e6c84">{{ l.get('fecha','')[:16].replace('T',' ') }}</td>
      <td>{{ l.get('pregunta','') }}</td>
      <td>{{ l.get('respuesta','—') }}</td>
      <td style="color:#5e6c84;font-size:.82rem">{{ l.get('producto','') }}</td>
      <td>
        {% set e = l.get('estado','') %}
        <span class="badge {{ 'badge-green' if e == 'publicada' else ('badge-yellow' if e == 'manual' else 'badge-red') }}">
          {{ e }}
        </span>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
  {% endif %}
</div>
"""


@app.route("/cliente/<cliente_id>")
def detalle_cliente(cliente_id):
    config = cargar_cliente(cliente_id)
    if not config:
        return redirect("/")
    logs = leer_log(cliente_id, 50)
    return render(
        config.get("nombre_negocio", cliente_id),
        DETALLE_CONTENT,
        id=cliente_id,
        nombre=config.get("nombre_negocio", "—"),
        activo=config.get("activo", False),
        logs=logs,
    )


# ── Nuevo cliente (3 campos) ──────────────────────────────────────────────────

NUEVO_CONTENT = """
<div class="page-title">Nuevo cliente</div>
<div class="card" style="max-width:580px">
  <div class="alert alert-info" style="margin-bottom:1.2rem">
    Solo necesitás 3 datos para empezar. Podés completar el perfil del negocio después desde <strong>Editar</strong>.
  </div>
  <form method="post">
    <div class="form-group">
      <label>Nombre del negocio</label>
      <input type="text" name="nombre_negocio" required placeholder="Ej: Ferretería Don Pedro">
    </div>
    <div class="form-group">
      <label>Access Token de MeLi</label>
      <input type="text" name="access_token" required placeholder="APP_USR-...">
      <div class="hint">Se obtiene autorizando tu app desde la cuenta del cliente.</div>
    </div>
    <div class="form-group">
      <label>Refresh Token de MeLi</label>
      <input type="text" name="refresh_token" required placeholder="TG-...">
      <div class="hint">Viene junto con el Access Token. El sistema lo usa para renovar automáticamente.</div>
    </div>
    <div style="display:flex;gap:.7rem;margin-top:1.2rem">
      <button class="btn btn-primary" type="submit">Crear cliente</button>
      <a class="btn btn-outline" href="/">Cancelar</a>
    </div>
  </form>
</div>
"""


@app.route("/cliente/nuevo", methods=["GET", "POST"])
def nuevo_cliente():
    if request.method == "POST":
        f = request.form
        nuevo_id = proximo_id()
        access_token = f.get("access_token", "").strip()
        refresh_token = f.get("refresh_token", "").strip()

        user_id = obtener_user_id(access_token) if access_token else ""
        if not user_id:
            print(f"[panel] Advertencia: no se pudo obtener user_id para nuevo cliente {nuevo_id}")

        config = {
            "cliente_id": nuevo_id,
            "nombre_negocio": f.get("nombre_negocio", "").strip(),
            "activo": True,
            "fecha_alta": datetime.now().isoformat(),
            "meli": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user_id": user_id,
                "token_expira": "",
            },
            "negocio": {
                "categoria": "",
                "zonas_envio": "",
                "tiempo_entrega": "",
                "formas_pago": "",
                "garantia": "",
                "politica_devoluciones": "",
                "tono": "cercano",
                "contacto_urgencias": "",
                "email_seller": "",
                "email_consultor": "",
            },
            "faq": [],
            "palabras_escalado_manual": [
                "reclamo", "roto", "no funciona", "devolución",
                "reembolso", "defectuoso", "problema", "queja", "estafa",
            ],
        }
        guardar_cliente(nuevo_id, config)
        return redirect(f"/cliente/{nuevo_id}/editar?flash=Cliente+creado.+Completá+el+perfil+del+negocio.")

    return render("Nuevo cliente", NUEVO_CONTENT)


# ── Editar cliente ────────────────────────────────────────────────────────────

EDITAR_CONTENT = """
<div class="page-title">{{ titulo }}</div>

{% if flash %}
<div class="alert alert-success">{{ flash }}</div>
{% endif %}

<div class="card">
<form method="post">

  <div class="form-section">
    <h3>General</h3>
    <div class="form-group">
      <label>Nombre del negocio</label>
      <input type="text" name="nombre_negocio" value="{{ c.get('nombre_negocio','') }}" required>
    </div>
    <label class="checkbox-label">
      <input type="checkbox" name="activo" {% if c.get('activo') %}checked{% endif %}>
      Cliente activo
    </label>
  </div>

  <div class="form-section">
    <h3>Credenciales Mercado Libre</h3>
    <div class="alert alert-info">
      El Client ID y Client Secret son globales y están en Railway.
      Acá solo actualizás los tokens del cliente si expiran.
    </div>
    <div class="form-group">
      <label>Access Token</label>
      <input type="text" name="access_token" value="{{ c.get('meli',{}).get('access_token','') }}" placeholder="APP_USR-...">
      <div class="hint">Token actual: {{ mascara_token }}</div>
    </div>
    <div class="form-group">
      <label>Refresh Token</label>
      <input type="text" name="refresh_token" value="{{ c.get('meli',{}).get('refresh_token','') }}">
    </div>
    <div class="form-group">
      <label>User ID (solo lectura — se obtiene automáticamente)</label>
      <input type="text" value="{{ c.get('meli',{}).get('user_id','—') }}" disabled
             style="background:#f4f5f7;color:#5e6c84">
    </div>
  </div>

  <div class="form-section">
    <h3>Perfil del negocio</h3>
    <div class="form-group">
      <label>Categoría de productos</label>
      <input type="text" name="categoria" value="{{ n.get('categoria','') }}"
             placeholder="Ej: Herramientas eléctricas, Ropa deportiva...">
    </div>
    <div class="form-group">
      <label>Zonas de envío</label>
      <input type="text" name="zonas_envio" value="{{ n.get('zonas_envio','') }}"
             placeholder="Ej: Todo el país por Mercado Envíos">
    </div>
    <div class="form-group">
      <label>Tiempo de entrega</label>
      <input type="text" name="tiempo_entrega" value="{{ n.get('tiempo_entrega','') }}"
             placeholder="Ej: 3 a 7 días hábiles">
    </div>
    <div class="form-group">
      <label>Formas de pago</label>
      <input type="text" name="formas_pago" value="{{ n.get('formas_pago','') }}"
             placeholder="Ej: Todas las tarjetas, transferencia, efectivo">
    </div>
    <div class="form-group">
      <label>Garantía</label>
      <input type="text" name="garantia" value="{{ n.get('garantia','') }}"
             placeholder="Ej: 6 meses por defecto de fábrica">
    </div>
    <div class="form-group">
      <label>Política de devoluciones</label>
      <textarea name="politica_devoluciones" rows="2"
                placeholder="Ej: Aceptamos devoluciones en 30 días si el producto no fue usado.">{{ n.get('politica_devoluciones','') }}</textarea>
    </div>
    <div class="form-group">
      <label>Tono de comunicación</label>
      <select name="tono">
        {% for t in ['cercano','formal','amigable','neutro'] %}
        <option value="{{ t }}" {% if n.get('tono','cercano') == t %}selected{% endif %}>
          {{ t.capitalize() }}
        </option>
        {% endfor %}
      </select>
    </div>
    <div class="form-group">
      <label>Email del seller (recibe alertas de preguntas manuales)</label>
      <input type="email" name="email_seller" value="{{ n.get('email_seller','') }}">
    </div>
    <div class="form-group">
      <label>Email del consultor (recibe alertas de tokens y reportes)</label>
      <input type="email" name="email_consultor" value="{{ n.get('email_consultor','') }}">
    </div>
    <div class="form-group">
      <label>Contacto de urgencias</label>
      <input type="text" name="contacto_urgencias" value="{{ n.get('contacto_urgencias','') }}"
             placeholder="Ej: WhatsApp +54 9 11 1234-5678">
    </div>
  </div>

  <div class="form-section">
    <h3>Preguntas frecuentes</h3>
    <div class="hint" style="margin-bottom:.8rem">
      Las respuestas exactas se usan textualmente cuando Claude las necesita.
    </div>
    <div id="faq-container">
    {% for item in c.get('faq', []) %}
    <div class="faq-row">
      <input type="text" name="faq_pregunta" placeholder="Pregunta" value="{{ item.get('pregunta','') }}">
      <input type="text" name="faq_respuesta" placeholder="Respuesta exacta" value="{{ item.get('respuesta','') }}">
    </div>
    {% endfor %}
    <div class="faq-row">
      <input type="text" name="faq_pregunta" placeholder="Pregunta">
      <input type="text" name="faq_respuesta" placeholder="Respuesta exacta">
    </div>
    </div>
    <button type="button" class="btn btn-outline btn-sm" onclick="agregarFaq()" style="margin-top:.4rem">
      + Agregar pregunta
    </button>
  </div>

  <div class="form-section">
    <h3>Palabras que escalan a atención manual</h3>
    <div class="form-group">
      <input type="text" name="palabras_escalado" value="{{ palabras_escalado }}">
      <div class="hint">Separadas por coma. Si la pregunta contiene alguna, se envía alerta al seller.</div>
    </div>
  </div>

  <div style="display:flex;gap:.7rem">
    <button class="btn btn-primary" type="submit">Guardar cambios</button>
    <a class="btn btn-outline" href="/cliente/{{ id }}">Cancelar</a>
  </div>

</form>
</div>

<script>
function agregarFaq() {
  const c = document.getElementById('faq-container');
  const div = document.createElement('div');
  div.className = 'faq-row';
  div.innerHTML = '<input type="text" name="faq_pregunta" placeholder="Pregunta">'
                + '<input type="text" name="faq_respuesta" placeholder="Respuesta exacta">';
  c.appendChild(div);
}
</script>
"""


@app.route("/cliente/<cliente_id>/editar", methods=["GET", "POST"])
def editar_cliente(cliente_id):
    config = cargar_cliente(cliente_id)
    if not config:
        return redirect("/")

    if request.method == "POST":
        f = request.form
        negocio_actual = config.get("negocio", {})

        nuevo_token = f.get("access_token", "").strip()
        token_anterior = config["meli"].get("access_token", "")
        user_id = config["meli"].get("user_id", "")

        if nuevo_token and nuevo_token != token_anterior:
            user_id_nuevo = obtener_user_id(nuevo_token)
            if user_id_nuevo:
                user_id = user_id_nuevo

        faq_preguntas = f.getlist("faq_pregunta")
        faq_respuestas = f.getlist("faq_respuesta")
        faq = [
            {"pregunta": p.strip(), "respuesta": r.strip()}
            for p, r in zip(faq_preguntas, faq_respuestas)
            if p.strip() and r.strip()
        ]
        escalado_raw = f.get("palabras_escalado", "")
        escalado = [w.strip() for w in escalado_raw.split(",") if w.strip()]

        config.update({
            "nombre_negocio": f.get("nombre_negocio", config["nombre_negocio"]).strip(),
            "activo": f.get("activo") == "on",
        })
        config["meli"].update({
            "access_token": nuevo_token or token_anterior,
            "refresh_token": f.get("refresh_token", config["meli"]["refresh_token"]).strip(),
            "user_id": user_id,
        })
        config["negocio"] = {
            "categoria": f.get("categoria", negocio_actual.get("categoria", "")),
            "zonas_envio": f.get("zonas_envio", negocio_actual.get("zonas_envio", "")),
            "tiempo_entrega": f.get("tiempo_entrega", negocio_actual.get("tiempo_entrega", "")),
            "formas_pago": f.get("formas_pago", negocio_actual.get("formas_pago", "")),
            "garantia": f.get("garantia", negocio_actual.get("garantia", "")),
            "politica_devoluciones": f.get("politica_devoluciones", negocio_actual.get("politica_devoluciones", "")),
            "tono": f.get("tono", negocio_actual.get("tono", "cercano")),
            "contacto_urgencias": f.get("contacto_urgencias", negocio_actual.get("contacto_urgencias", "")),
            "email_seller": f.get("email_seller", negocio_actual.get("email_seller", "")),
            "email_consultor": f.get("email_consultor", negocio_actual.get("email_consultor", "")),
        }
        if faq:
            config["faq"] = faq
        if escalado:
            config["palabras_escalado_manual"] = escalado

        guardar_cliente(cliente_id, config)
        return redirect(f"/cliente/{cliente_id}/editar?flash=Cambios+guardados.")

    flash = request.args.get("flash", "")
    palabras = ", ".join(config.get("palabras_escalado_manual", []))
    return render(
        f"Editar — {config.get('nombre_negocio')}",
        EDITAR_CONTENT,
        id=cliente_id,
        titulo=f"Editar — {config.get('nombre_negocio')}",
        c=config,
        n=config.get("negocio", {}),
        mascara_token=_mascara(config.get("meli", {}).get("access_token", "")),
        palabras_escalado=palabras,
        flash=flash,
    )


# ── Acciones ──────────────────────────────────────────────────────────────────

@app.route("/cliente/<cliente_id>/pausar", methods=["POST"])
def pausar(cliente_id):
    pausar_cliente(cliente_id)
    return redirect("/?flash=Cliente+pausado.")


@app.route("/cliente/<cliente_id>/activar", methods=["POST"])
def activar(cliente_id):
    activar_cliente(cliente_id)
    return redirect("/?flash=Cliente+activado.")


@app.route("/correr-ahora", methods=["POST"])
def correr_ahora():
    from main import procesar_clientes
    threading.Thread(target=procesar_clientes, daemon=True).start()
    return redirect("/?flash=Ciclo+iniciado.+Revisá+la+actividad+en+unos+momentos.")


# ── Reporte mensual ───────────────────────────────────────────────────────────

@app.route("/reporte/<cliente_id>")
def reporte(cliente_id):
    config = cargar_cliente(cliente_id)
    if not config:
        return redirect("/")
    logs = leer_log(cliente_id, 500)
    mes = datetime.now().strftime("%B %Y").capitalize()
    total = len(logs)
    respondidas = sum(1 for l in logs if l.get("estado") == "publicada")
    manuales = sum(1 for l in logs if l.get("estado") == "manual")
    errores = sum(1 for l in logs if l.get("estado") == "error")
    tasa = round(respondidas / total * 100) if total else 0
    nombre = config.get("nombre_negocio", cliente_id)
    reporte_txt = f"""REPORTE MENSUAL — {nombre} — {mes}
{'=' * 55}
Total de preguntas procesadas  : {total}
Respondidas automáticamente    : {respondidas}
Escaladas a atención manual    : {manuales}
Errores                        : {errores}
Tasa de automatización         : {tasa}%
{'=' * 55}
"""
    return f"<pre style='font-family:monospace;padding:2rem;font-size:.95rem'>{reporte_txt}</pre>"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
