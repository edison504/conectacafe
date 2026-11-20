"""
Envío de mensajes de WhatsApp de Café Conecta.

Cada mensaje queda guardado en la tabla 'mensaje' con su resultado (bitácora).
El modo de envío se elige en config.py, en la sección WHATSAPP:

  "whatsapp_web"  Abre WhatsApp (app o web) con el mensaje ya escrito para ese número;
                  solo falta presionar Enviar. No necesita ninguna cuenta. (Predeterminado)
  "cloud_api"     Envío automático con la API oficial de WhatsApp de Meta
                  (necesita token e identificador del número de prueba).
  "twilio"        Envío automático con Twilio (necesita cuenta y número de WhatsApp de Twilio).
  "simulado"      No envía nada: solo lo registra en la bitácora (útil para pruebas).
"""
import base64
import json
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

import config
from datos import DatosMensaje

PREDETERMINADO = {
    "modo": "whatsapp_web",
    "indicativo": "57",            # Colombia
    # Para "cloud_api" (Meta):
    "token": "",
    "phone_number_id": "",
    # Para "twilio":
    "twilio_sid": "",
    "twilio_token": "",
    "twilio_numero": "whatsapp:+14155238886",
}

ENLACES_PREDETERMINADO = {
    "url_base": "http://127.0.0.1:8765",
    "puerto": 8765,
}


def configuracion():
    datos = dict(PREDETERMINADO)
    datos.update(getattr(config, "WHATSAPP", {}) or {})
    return datos


def configuracion_enlaces():
    datos = dict(ENLACES_PREDETERMINADO)
    datos.update(getattr(config, "ENLACES", {}) or {})
    return datos


def enlace(tipo, token):
    """tipo 'n' = negocio (el productor acepta o rechaza), 'e' = entrega (el comprador confirma)."""
    return f"{configuracion_enlaces()['url_base'].rstrip('/')}/{tipo}/{token}"


def _numero_internacional(telefono):
    digitos = "".join(c for c in str(telefono or "") if c.isdigit())
    indicativo = configuracion()["indicativo"]
    return digitos if digitos.startswith(indicativo) and len(digitos) > 10 else indicativo + digitos


def _enviar_whatsapp_web(numero, texto):
    url = f"https://wa.me/{numero}?text={urllib.parse.quote(texto)}"
    abierto = webbrowser.open(url)
    if abierto:
        return "Abierto", "Se abrió WhatsApp con el mensaje listo para enviar."
    return "Error", "No se pudo abrir el navegador."


def _enviar_cloud_api(numero, texto, cfg):
    if not cfg["token"] or not cfg["phone_number_id"]:
        return "Error", "Falta configurar token y phone_number_id de Meta en config.py."
    url = f"https://graph.facebook.com/v20.0/{cfg['phone_number_id']}/messages"
    cuerpo = json.dumps({"messaging_product": "whatsapp", "to": numero, "type": "text",
                         "text": {"preview_url": True, "body": texto}}).encode("utf-8")
    peticion = urllib.request.Request(url, data=cuerpo, method="POST", headers={
        "Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=15) as respuesta:
        datos = json.loads(respuesta.read().decode("utf-8"))
    return "Enviado", f"Meta id: {datos.get('messages', [{}])[0].get('id', '')}"


def _enviar_twilio(numero, texto, cfg):
    if not cfg["twilio_sid"] or not cfg["twilio_token"]:
        return "Error", "Falta configurar twilio_sid y twilio_token en config.py."
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['twilio_sid']}/Messages.json"
    cuerpo = urllib.parse.urlencode({"From": cfg["twilio_numero"], "To": f"whatsapp:+{numero}",
                                     "Body": texto}).encode("utf-8")
    credencial = base64.b64encode(f"{cfg['twilio_sid']}:{cfg['twilio_token']}".encode()).decode()
    peticion = urllib.request.Request(url, data=cuerpo, method="POST",
                                      headers={"Authorization": f"Basic {credencial}"})
    with urllib.request.urlopen(peticion, timeout=15) as respuesta:
        datos = json.loads(respuesta.read().decode("utf-8"))
    return "Enviado", f"Twilio sid: {datos.get('sid', '')}"


def enviar(telefono, destinatario, tipo, referencia, texto):
    """Envía el mensaje según el modo configurado y lo registra en la bitácora. Devuelve (resultado, detalle)."""
    cfg = configuracion()
    modo = cfg["modo"]
    numero = _numero_internacional(telefono)
    try:
        if not telefono:
            resultado, detalle = "Error", "El destinatario no tiene teléfono registrado."
        elif modo == "simulado":
            resultado, detalle = "Simulado", "Modo simulado: el mensaje solo quedó registrado en la bitácora."
        elif modo == "cloud_api":
            resultado, detalle = _enviar_cloud_api(numero, texto, cfg)
        elif modo == "twilio":
            resultado, detalle = _enviar_twilio(numero, texto, cfg)
        else:
            resultado, detalle = _enviar_whatsapp_web(numero, texto)
    except urllib.error.HTTPError as err:
        resultado, detalle = "Error", f"HTTP {err.code}: {err.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as err:  # sin internet, tiempo agotado, etc.
        resultado, detalle = "Error", str(err)[:250]
    try:
        DatosMensaje.insertar(numero, destinatario, tipo, referencia, texto, modo, resultado, detalle)
    except Exception:
        pass
    return resultado, detalle


def pesos(valor):
    """1234567.5 -> '$1.234.568'"""
    return "$" + f"{float(valor):,.0f}".replace(",", ".")
