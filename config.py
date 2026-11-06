"""
Configuración de Café Conecta.

Aquí van los datos de conexión a la base de datos y la cuenta de correo
que envía la recuperación de usuario y contraseña. Edite estos valores
antes de ejecutar el programa.
"""

BASE_DATOS = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    "password": "",
    "database": "cafeconecta",
}

CORREO = {
    "servidor": "smtp.gmail.com",
    "puerto": 587,
    "remitente": "su_correo@gmail.com",
    "contrasena_aplicacion": "xxxxxxxxxxxxxxxx",
    "nombre_remitente": "Café Conecta",
}
