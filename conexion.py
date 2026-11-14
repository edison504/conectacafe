import mysql.connector

from config import BASE_DATOS


class ErrorConexion(Exception):
    """Se lanza cuando no es posible conectarse a la base de datos."""


def conectar_bd():
    """Devuelve una conexión abierta o lanza ErrorConexion con un mensaje claro."""
    try:
        return mysql.connector.connect(**BASE_DATOS)
    except mysql.connector.Error as err:
        raise ErrorConexion(
            "No se pudo conectar a la base de datos 'cafeconecta'.\n"
            "Verifique que MySQL esté encendido en XAMPP y que los datos "
            f"de config.py sean correctos.\n\nDetalle: {err}"
        ) from err
