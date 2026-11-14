import re
import sys

try:
    import mysql.connector
except ImportError:
    print("Falta instalar mysql-connector-python.")
    sys.exit(1)

CANDIDATOS = [(3306, ""), (3306, "root"), (8889, "root"), (8889, ""), (3307, ""), (3307, "root")]


def probar():
    for puerto, clave in CANDIDATOS:
        try:
            con = mysql.connector.connect(host="127.0.0.1", port=puerto, user="root",
                                          password=clave, connection_timeout=3)
            return con, puerto, clave
        except mysql.connector.Error as err:
            print(f"  Puerto {puerto}, contraseña '{clave}': no ({err.msg[:60]})")
    return None, None, None


print("Buscando el servidor MySQL...")
con, puerto, clave = probar()
if not con:
    print("\nNo se encontró MySQL. Encienda MySQL en MAMP/XAMPP (luz verde) y vuelva a ejecutar.")
    sys.exit(1)
print(f"\nMySQL encontrado en el puerto {puerto} con usuario root y contraseña '{clave}'.")

cur = con.cursor()
cur.execute("SHOW DATABASES LIKE 'cafeconecta'")
existe = cur.fetchone() is not None
if existe:
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cafeconecta'")
    existe = cur.fetchone()[0] >= 3
if existe:
    print("La base de datos 'cafeconecta' ya existe con sus tablas. No se modificó.")
else:
    print("Creando la base de datos 'cafeconecta' desde cafeconecta.sql...")
    with open("cafeconecta.sql", encoding="utf-8") as f:
        sql = "\n".join(l for l in f.read().splitlines() if not l.strip().startswith("--"))
    for sentencia in sql.split(";"):
        if sentencia.strip():
            cur.execute(sentencia)
    con.commit()
    print("Base de datos creada. Usuario inicial: admin / admin123")
con.close()

with open("config.py", encoding="utf-8") as f:
    texto = f.read()
texto = re.sub(r'"host":\s*"[^"]*"', '"host": "127.0.0.1"', texto, count=1)
texto = re.sub(r'"port":\s*\d+', f'"port": {puerto}', texto, count=1)
texto = re.sub(r'("user":\s*"root",\s*\n\s*"password":\s*)"[^"]*"', rf'\1"{clave}"', texto, count=1)
with open("config.py", "w", encoding="utf-8") as f:
    f.write(texto)
print("config.py actualizado con ese puerto y contraseña.")
