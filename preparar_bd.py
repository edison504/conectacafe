import getpass
import re
import sys

try:
    import mysql.connector
except ImportError:
    print("Falta instalar mysql-connector-python.")
    sys.exit(1)

PUERTOS = [3306, 8889, 3307]
CLAVES_COMUNES = ["", "root"]


def conectar(puerto, usuario, clave):
    return mysql.connector.connect(host="127.0.0.1", port=puerto, user=usuario,
                                   password=clave, connection_timeout=3)


def probar():
    """Prueba los puertos y contraseñas más comunes. Devuelve la conexión y los puertos que responden."""
    responden = []
    for puerto in PUERTOS:
        for clave in CLAVES_COMUNES:
            try:
                return conectar(puerto, "root", clave), puerto, "root", clave, responden
            except mysql.connector.Error as err:
                print(f"  Puerto {puerto}, contraseña '{clave}': no ({err.msg[:60]})")
                if err.errno == 1045 and puerto not in responden:  # 1045 = acceso denegado
                    responden.append(puerto)
    return None, None, None, None, responden


def pedir_clave(puertos):
    """MySQL está encendido pero no acepta las contraseñas comunes: se le pide al usuario."""
    puerto = puertos[0]
    print(f"\nMySQL está encendido en el puerto {puerto}, pero no acepta las contraseñas comunes.")
    usuario = input("Usuario de MySQL [root]: ").strip() or "root"
    for intento in range(3):
        clave = getpass.getpass(f"Contraseña de '{usuario}' (no se ve al escribir; Enter si no tiene): ")
        try:
            return conectar(puerto, usuario, clave), puerto, usuario, clave
        except mysql.connector.Error as err:
            print(f"  No funcionó ({err.msg[:60]}). Intentos restantes: {2 - intento}")
    return None, None, None, None


print("Buscando el servidor MySQL...")
con, puerto, usuario, clave, responden = probar()
if not con and responden:
    con, puerto, usuario, clave = pedir_clave(responden)
if not con:
    print("\nNo se pudo conectar a MySQL. Encienda MySQL en MAMP/XAMPP (luz verde) y revise "
          "el usuario y la contraseña.")
    sys.exit(1)
print(f"\nConectado a MySQL en el puerto {puerto} con el usuario '{usuario}'.")


def ejecutar_archivo(cursor, archivo):
    with open(archivo, encoding="utf-8") as f:
        sql = "\n".join(l for l in f.read().splitlines() if not l.strip().startswith("--"))
    for sentencia in sql.split(";"):
        if sentencia.strip():
            cursor.execute(sentencia)


def tabla_existe(cursor, tabla):
    cursor.execute("SELECT COUNT(*) FROM information_schema.tables "
                   "WHERE table_schema = 'cafeconecta' AND table_name = %s", (tabla,))
    return cursor.fetchone()[0] > 0


cur = con.cursor()
if not tabla_existe(cur, "usuario"):
    print("Creando la base de datos 'cafeconecta' desde cafeconecta.sql...")
    ejecutar_archivo(cur, "cafeconecta.sql")
    con.commit()
    print("Base de datos creada. Usuarios: admin / admin123, productor1 / cafe2026, comprador1 / cafe2026")
elif not tabla_existe(cur, "productor"):
    print("La base del Parcial I existe. Agregando las tablas del Parcial II (sus datos se conservan)...")
    ejecutar_archivo(cur, "actualizar_parcial2.sql")
    con.commit()
    print("Base de datos actualizada al Parcial II.")
else:
    print("La base de datos 'cafeconecta' ya tiene las tablas del Parcial II. No se modificó.")
con.close()

# Guarda en config.py el puerto, el usuario y la contraseña que funcionaron.
with open("config.py", encoding="utf-8") as f:
    texto = f.read()
texto = re.sub(r'"host":\s*"[^"]*"', '"host": "127.0.0.1"', texto, count=1)
texto = re.sub(r'"port":\s*\d+', f'"port": {puerto}', texto, count=1)
texto = re.sub(r'"user":\s*"[^"]*"', f'"user": "{usuario}"', texto, count=1)
clave_escapada = clave.replace("\\", "\\\\").replace('"', '\\"')
texto = re.sub(r'"password":\s*"[^"]*"', lambda m: f'"password": "{clave_escapada}"', texto, count=1)
with open("config.py", "w", encoding="utf-8") as f:
    f.write(texto)
print("config.py actualizado con ese puerto, usuario y contraseña.")