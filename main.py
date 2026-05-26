import os
import threading
import time
from datetime import date, datetime

from clientes import guardar_cliente, guardar_log, leer_log, listar_clientes_activos
from claude import generar_respuesta
from meli import (
    obtener_preguntas,
    obtener_producto,
    publicar_respuesta,
    renovar_token,
    token_valido,
)
from notificaciones import alerta_pregunta_manual, alerta_token_expirado


def contiene_palabras_escalado(texto, config):
    texto_lower = texto.lower()
    return any(
        p.lower() in texto_lower
        for p in config.get("palabras_escalado_manual", [])
    )


def verificar_y_renovar_token(config):
    if token_valido(config):
        return config["meli"]["access_token"]

    nombre = config.get("nombre_negocio", config["cliente_id"])
    print(f"[main] Token vencido para {nombre} — renovando")
    nuevos = renovar_token(config["cliente_id"], config)
    if nuevos:
        config["meli"].update(nuevos)
        guardar_cliente(config["cliente_id"], config)
        print(f"[main] Token renovado para {nombre}")
        return nuevos["access_token"]

    print(f"[main] No se pudo renovar token para {nombre} — enviando alerta")
    alerta_token_expirado(config)
    return None


def procesar_cliente(config):
    nombre = config.get("nombre_negocio", config["cliente_id"])
    print(f"[main] → {nombre}")

    token = verificar_y_renovar_token(config)
    if not token:
        return

    user_id = config["meli"].get("user_id", "")
    preguntas = obtener_preguntas(token, user_id)
    if not preguntas:
        print(f"[main]   Sin preguntas pendientes")
        return

    print(f"[main]   {len(preguntas)} pregunta(s)")

    for pregunta in preguntas:
        question_id = pregunta.get("id")
        pregunta_texto = pregunta.get("text", "")
        item_id = pregunta.get("item_id", "")

        entrada = {
            "fecha": datetime.now().isoformat(),
            "question_id": question_id,
            "pregunta": pregunta_texto,
            "producto": item_id,
            "respuesta": "",
            "estado": "",
        }

        try:
            if contiene_palabras_escalado(pregunta_texto, config):
                entrada["estado"] = "manual"
                alerta_pregunta_manual(config, pregunta_texto, question_id)
                print(f"[main]   ⚡ Manual: {pregunta_texto[:60]}")

            else:
                producto = obtener_producto(token, item_id)
                entrada["producto"] = producto.get("titulo", item_id)

                respuesta = generar_respuesta(config, pregunta_texto, producto)

                if not respuesta:
                    entrada["estado"] = "error"
                    alerta_pregunta_manual(config, pregunta_texto, question_id)
                    print(f"[main]   ✗ Claude sin respuesta — escalado a manual")
                else:
                    ok, _ = publicar_respuesta(token, question_id, respuesta)
                    entrada["respuesta"] = respuesta
                    entrada["estado"] = "publicada" if ok else "error"
                    icono = "✓" if ok else "✗"
                    print(f"[main]   {icono} {pregunta_texto[:50]}")

        except Exception as e:
            entrada["estado"] = "error"
            print(f"[main]   Error en pregunta {question_id}: {e}")

        guardar_log(config["cliente_id"], entrada)


def procesar_clientes():
    ahora = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*50}")
    print(f"  Ciclo iniciado — {ahora}")
    print(f"{'='*50}")

    clientes = listar_clientes_activos()
    if not clientes:
        print("[main] Sin clientes activos")
        return

    for config in clientes:
        try:
            procesar_cliente(config)
        except Exception as e:
            print(f"[main] Error fatal en cliente {config.get('cliente_id')}: {e}")


def enviar_reporte_si_corresponde():
    if datetime.now().hour != 8:
        return
    from notificaciones import reporte_diario
    from clientes import listar_todos_clientes
    hoy = date.today().isoformat()
    datos = []
    for c in listar_todos_clientes():
        logs = leer_log(c["cliente_id"], 500)
        datos.append({
            "nombre": c.get("nombre_negocio", c["cliente_id"]),
            "respondidas": sum(1 for l in logs if l.get("fecha", "").startswith(hoy) and l.get("estado") == "publicada"),
            "manuales": sum(1 for l in logs if l.get("fecha", "").startswith(hoy) and l.get("estado") == "manual"),
            "errores": sum(1 for l in logs if l.get("fecha", "").startswith(hoy) and l.get("estado") == "error"),
            "estado": "Activo" if c.get("activo") else "Pausado",
        })
    reporte_diario(datos)


def iniciar_panel():
    from panel import app
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    print("=" * 50)
    print("  MeLi Auto-Responder — Iniciando")
    print("=" * 50)

    hilo_panel = threading.Thread(target=iniciar_panel, daemon=True)
    hilo_panel.start()
    print(f"[main] Panel web iniciado en puerto {os.environ.get('PORT', 8080)}")

    while True:
        procesar_clientes()
        enviar_reporte_si_corresponde()
        print(f"[main] Próximo ciclo en 30 minutos")
        time.sleep(1800)
