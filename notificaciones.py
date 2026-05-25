import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def enviar_email(destinatario, asunto, cuerpo):
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_pass = os.environ.get("GMAIL_PASSWORD", "")
    if not gmail_user or not gmail_pass:
        print(f"[notif] Sin credenciales Gmail — email no enviado: {asunto}")
        return False
    if not destinatario:
        print(f"[notif] Destinatario vacío — email no enviado: {asunto}")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, destinatario, msg.as_string())
        print(f"[notif] Email enviado a {destinatario}: {asunto}")
        return True
    except Exception as e:
        print(f"[notif] Error enviando email a {destinatario}: {e}")
        return False


def alerta_token_expirado(config):
    consultor = os.environ.get(
        "CONSULTOR_EMAIL", config.get("negocio", {}).get("email_consultor", "")
    )
    nombre = config.get("nombre_negocio", "Cliente")
    client_id = os.environ.get("MELI_CLIENT_ID", "")
    cuerpo = f"""El token de {nombre} expiró y no se pudo renovar automáticamente.

Pedile al cliente que autorice nuevamente tu app desde este link:
https://auth.mercadolibre.com.ar/authorization?response_type=code&client_id={client_id}&redirect_uri=https://www.mercadolibre.com.ar

Una vez que tengas el nuevo access_token y refresh_token, actualizalos desde el panel en:
Clientes → {nombre} → Editar"""
    enviar_email(consultor, f"⚠️ Token expirado — {nombre}", cuerpo)


def alerta_pregunta_manual(config, pregunta_texto, question_id):
    seller_email = config.get("negocio", {}).get("email_seller", "")
    nombre = config.get("nombre_negocio", "tu tienda")
    if not seller_email:
        return
    cuerpo = f"""Recibiste una pregunta que necesita respuesta personalizada en {nombre}:

"{pregunta_texto}"

Respondela desde tu cuenta de Mercado Libre lo antes posible.
ID de pregunta: {question_id}"""
    enviar_email(seller_email, f"💬 Pregunta requiere tu atención — {nombre}", cuerpo)


def reporte_diario(clientes_data):
    consultor = os.environ.get("CONSULTOR_EMAIL", "")
    if not consultor:
        return
    hoy = datetime.now().strftime("%d/%m/%Y")
    lineas = [
        f"Reporte diario MeLi Auto-Responder — {hoy}",
        "",
        f"{'Cliente':<25} {'Respondidas':>12} {'Manuales':>10} {'Errores':>8} {'Estado':>10}",
        "-" * 70,
    ]
    for c in clientes_data:
        lineas.append(
            f"{c['nombre'][:25]:<25} {c['respondidas']:>12} {c['manuales']:>10}"
            f" {c['errores']:>8} {c['estado']:>10}"
        )
    enviar_email(consultor, f"📊 Reporte diario MeLi — {hoy}", "\n".join(lineas))
