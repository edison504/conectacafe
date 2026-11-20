BASE_DATOS = {
       "host": "127.0.0.1",
       "port": 8889,
       "user": "root",
       "password": "root",
       "database": "cafeconecta",
   }

CORREO = {
    "servidor": "smtp.gmail.com",
    "puerto": 587,
    "remitente": "su_correo@gmail.com",
    "contrasena_aplicacion": "xxxxxxxxxxxxxxxx",
    "nombre_remitente": "Café Conecta",
}

# ---------------------------------------------------------------------
# Final · Avisos por WhatsApp (HU-07, HU-08 y HU-09)
#   "whatsapp_web"  Abre WhatsApp con el mensaje ya escrito; solo falta presionar Enviar (no necesita cuenta).
#   "cloud_api"     Envío automático con la API oficial de Meta (token y phone_number_id).
#   "twilio"        Envío automático con Twilio (twilio_sid, twilio_token y twilio_numero).
#   "simulado"      No envía: solo deja el mensaje en la bitácora (Gestión > Mensajes).
# ---------------------------------------------------------------------
WHATSAPP = {
    "modo": "whatsapp_web",
    "indicativo": "57",
    "token": "",
    "phone_number_id": "",
    "twilio_sid": "",
    "twilio_token": "",
    "twilio_numero": "whatsapp:+14155238886",
}

# Enlaces que van dentro de los mensajes: al abrirlos, Café Conecta muestra el negocio o la entrega.
ENLACES = {
    "url_base": "http://127.0.0.1:8765",
    "puerto": 8765,
}
