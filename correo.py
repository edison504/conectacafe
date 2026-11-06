"""Servicio de correo: envía el usuario y la contraseña para la recuperación."""
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from config import CORREO


def enviar_credenciales(destino, nombre, usuario, contrasena):
    """Envía el correo de recuperación. Devuelve (True, "") o (False, motivo)."""
    if "su_correo" in CORREO["remitente"] or set(CORREO["contrasena_aplicacion"]) == {"x"}:
        return False, ("Falta configurar la cuenta de correo en config.py "
                       "(remitente y contraseña de aplicación).")

    mensaje = EmailMessage()
    mensaje["Subject"] = "Café Conecta - Recuperación de usuario y contraseña"
    mensaje["From"] = formataddr((CORREO["nombre_remitente"], CORREO["remitente"]))
    mensaje["To"] = destino

    mensaje.set_content(
        f"Hola {nombre},\n\n"
        "Recibimos una solicitud para recuperar sus datos de acceso a Café Conecta.\n\n"
        f"Usuario: {usuario}\n"
        f"Contraseña: {contrasena}\n\n"
        "Si usted no hizo esta solicitud, comuníquese con el administrador.\n\n"
        "Café Conecta - Del cultivo a tu taza"
    )
    mensaje.add_alternative(f"""\
<html><body style="font-family:Arial,sans-serif;background:#f6f1ea;padding:24px">
  <div style="max-width:480px;margin:auto;background:#fff;border-radius:10px;overflow:hidden">
    <div style="background:#3e2723;color:#fff;padding:18px 24px">
      <h2 style="margin:0">&#9749; Café Conecta</h2>
      <small>Del cultivo a tu taza</small>
    </div>
    <div style="padding:24px;color:#333">
      <p>Hola <b>{nombre}</b>,</p>
      <p>Recibimos una solicitud para recuperar sus datos de acceso.</p>
      <table style="background:#f1f8e9;border-radius:8px;padding:12px 16px">
        <tr><td><b>Usuario:</b></td><td>{usuario}</td></tr>
        <tr><td><b>Contraseña:</b></td><td>{contrasena}</td></tr>
      </table>
      <p style="font-size:12px;color:#777">Si usted no hizo esta solicitud,
         comuníquese con el administrador.</p>
    </div>
  </div>
</body></html>""", subtype="html")

    try:
        with smtplib.SMTP(CORREO["servidor"], CORREO["puerto"], timeout=20) as servidor:
            servidor.starttls()
            servidor.login(CORREO["remitente"], CORREO["contrasena_aplicacion"])
            servidor.send_message(mensaje)
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, ("El servidor de correo rechazó el usuario o la contraseña de aplicación "
                       "configurados en config.py.")
    except (smtplib.SMTPException, OSError) as err:
        return False, f"No se pudo enviar el correo: {err}"
