from conexion import conectar_bd

def _consultar(sql, parametros=(), uno=False):
    conexion = conectar_bd()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(sql, parametros)
        resultado = cursor.fetchone() if uno else cursor.fetchall()
        cursor.close()
        return resultado
    finally:
        conexion.close()


def _ejecutar(sql, parametros=()):
    """Ejecuta INSERT/UPDATE y devuelve el id generado (o filas afectadas)."""
    conexion = conectar_bd()
    try:
        cursor = conexion.cursor()
        cursor.execute(sql, parametros)
        conexion.commit()
        resultado = cursor.lastrowid or cursor.rowcount
        cursor.close()
        return resultado
    finally:
        conexion.close()


def _filtro_texto(texto):
    return f"%{texto}%"


class DatosAcceso:

    @staticmethod
    def buscar_usuario_login(nombreu):
        """Trae el usuario con su perfil y persona para validar el ingreso."""
        sql = """
            SELECT u.Idusuario, u.nombreu, u.contrasena, u.estado,
                   u.idperfil, p.descripc AS perfil, p.estado AS estado_perfil,
                   u.idpersona, per.nom1, per.apell1, per.estado AS estado_persona
            FROM usuario u
            INNER JOIN perfil  p   ON u.idperfil  = p.Idperfil
            INNER JOIN persona per ON u.idpersona = per.Idpersona
            WHERE u.nombreu = %s
        """
        return _consultar(sql, (nombreu,), uno=True)

    @staticmethod
    def buscar_para_recuperacion(dato):
        """Busca por nombre de usuario, correo o número de identificación (Idpersona)."""
        sql = """
            SELECT u.nombreu, u.contrasena, u.estado,
                   per.Idpersona, per.nom1, per.apell1, per.correo
            FROM usuario u
            INNER JOIN persona per ON u.idpersona = per.Idpersona
            WHERE u.nombreu = %s OR per.correo = %s OR CAST(per.Idpersona AS CHAR) = %s
            LIMIT 1
        """
        return _consultar(sql, (dato, dato, dato), uno=True)

    @staticmethod
    def contar_activos():
        """Totales para las tarjetas del panel principal."""
        sql = """
            SELECT
              (SELECT COUNT(*) FROM persona WHERE estado = 'Activo') AS personas,
              (SELECT COUNT(*) FROM usuario WHERE estado = 'Activo') AS usuarios,
              (SELECT COUNT(*) FROM perfil  WHERE estado = 'Activo') AS perfiles
        """
        return _consultar(sql, uno=True)



class DatosPerfil:

    @staticmethod
    def listar(filtro=""):
        sql = """
            SELECT Idperfil, descripc, estado FROM perfil
            WHERE descripc LIKE %s OR CAST(Idperfil AS CHAR) = %s
            ORDER BY Idperfil
        """
        return _consultar(sql, (_filtro_texto(filtro), filtro))

    @staticmethod
    def listar_activos():
        return _consultar("SELECT Idperfil, descripc FROM perfil WHERE estado = 'Activo' ORDER BY descripc")

    @staticmethod
    def buscar_por_descripcion(descripc):
        return _consultar("SELECT Idperfil, estado FROM perfil WHERE descripc = %s", (descripc,), uno=True)

    @staticmethod
    def existe_descripcion(descripc, excluir_id=None):
        fila = _consultar(
            "SELECT COUNT(*) AS total FROM perfil WHERE descripc = %s AND Idperfil <> %s",
            (descripc, excluir_id or 0), uno=True)
        return fila["total"] > 0

    @staticmethod
    def insertar(datos):
        return _ejecutar("INSERT INTO perfil (descripc, estado) VALUES (%s, 'Activo')", (datos["descripc"],))

    @staticmethod
    def actualizar(id_registro, datos):
        return _ejecutar("UPDATE perfil SET descripc = %s WHERE Idperfil = %s", (datos["descripc"], id_registro))

    @staticmethod
    def cambiar_estado(id_registro, estado):
        return _ejecutar("UPDATE perfil SET estado = %s WHERE Idperfil = %s", (estado, id_registro))

    @staticmethod
    def usuarios_activos_con_perfil(id_registro):
        fila = _consultar(
            "SELECT COUNT(*) AS total FROM usuario WHERE idperfil = %s AND estado = 'Activo'",
            (id_registro,), uno=True)
        return fila["total"]


class DatosPersona:
    CAMPOS = ("nom1", "nom2", "apell1", "apell2", "direccion", "tele", "movil", "correo", "fecha_nac")

    @staticmethod
    def listar(filtro="", solo_id=None):
        sql = """
            SELECT Idpersona, nom1, nom2, apell1, apell2, direccion, tele, movil, correo,
                   CAST(fecha_nac AS CHAR) AS fecha_nac, estado
            FROM persona
            WHERE (CONCAT_WS(' ', nom1, nom2, apell1, apell2) LIKE %s
                   OR correo LIKE %s OR movil LIKE %s OR CAST(Idpersona AS CHAR) = %s)
        """
        parametros = [_filtro_texto(filtro)] * 3 + [filtro]
        if solo_id is not None:
            sql += " AND Idpersona = %s"
            parametros.append(solo_id)
        sql += " ORDER BY Idpersona"
        return _consultar(sql, tuple(parametros))

    @staticmethod
    def listar_sin_usuario(incluir_id=None):
        """Personas activas que aún no tienen usuario (más la persona actual al modificar)."""
        sql = """
            SELECT per.Idpersona, per.nom1, per.apell1, per.correo
            FROM persona per
            LEFT JOIN usuario u ON u.idpersona = per.Idpersona
            WHERE per.estado = 'Activo' AND (u.Idusuario IS NULL OR per.Idpersona = %s)
            ORDER BY per.nom1, per.apell1
        """
        return _consultar(sql, (incluir_id or 0,))

    @staticmethod
    def obtener(id_registro):
        return _consultar("SELECT * FROM persona WHERE Idpersona = %s", (id_registro,), uno=True)

    @staticmethod
    def existe_correo(correo, excluir_id=None):
        fila = _consultar(
            "SELECT COUNT(*) AS total FROM persona WHERE correo = %s AND Idpersona <> %s",
            (correo, excluir_id or 0), uno=True)
        return fila["total"] > 0

    @staticmethod
    def insertar(datos):
        columnas = ", ".join(DatosPersona.CAMPOS)
        marcas = ", ".join(["%s"] * len(DatosPersona.CAMPOS))
        sql = f"INSERT INTO persona ({columnas}, estado) VALUES ({marcas}, 'Activo')"
        return _ejecutar(sql, tuple(datos[c] for c in DatosPersona.CAMPOS))

    @staticmethod
    def actualizar(id_registro, datos):
        asignaciones = ", ".join(f"{c} = %s" for c in DatosPersona.CAMPOS)
        sql = f"UPDATE persona SET {asignaciones} WHERE Idpersona = %s"
        return _ejecutar(sql, tuple(datos[c] for c in DatosPersona.CAMPOS) + (id_registro,))

    @staticmethod
    def cambiar_estado(id_registro, estado):
        return _ejecutar("UPDATE persona SET estado = %s WHERE Idpersona = %s", (estado, id_registro))


# ---------------------------------------------------------------------
# Usuario
# ---------------------------------------------------------------------
class DatosUsuario:

    @staticmethod
    def listar(filtro=""):
        sql = """
            SELECT u.Idusuario, u.nombreu, u.contrasena, u.idperfil, p.descripc AS perfil,
                   u.idpersona, CONCAT(per.nom1, ' ', per.apell1) AS persona, u.estado
            FROM usuario u
            INNER JOIN perfil  p   ON u.idperfil  = p.Idperfil
            INNER JOIN persona per ON u.idpersona = per.Idpersona
            WHERE u.nombreu LIKE %s OR p.descripc LIKE %s
               OR CONCAT(per.nom1, ' ', per.apell1) LIKE %s OR CAST(u.Idusuario AS CHAR) = %s
            ORDER BY u.Idusuario
        """
        return _consultar(sql, (_filtro_texto(filtro),) * 3 + (filtro,))

    @staticmethod
    def existe_nombre(nombreu, excluir_id=None):
        fila = _consultar(
            "SELECT COUNT(*) AS total FROM usuario WHERE nombreu = %s AND Idusuario <> %s",
            (nombreu, excluir_id or 0), uno=True)
        return fila["total"] > 0

    @staticmethod
    def persona_tiene_usuario(idpersona, excluir_id=None):
        fila = _consultar(
            "SELECT COUNT(*) AS total FROM usuario WHERE idpersona = %s AND Idusuario <> %s",
            (idpersona, excluir_id or 0), uno=True)
        return fila["total"] > 0

    @staticmethod
    def insertar(datos):
        sql = """INSERT INTO usuario (nombreu, contrasena, idperfil, idpersona, estado)
                 VALUES (%s, %s, %s, %s, 'Activo')"""
        return _ejecutar(sql, (datos["nombreu"], datos["contrasena"], datos["idperfil"], datos["idpersona"]))

    @staticmethod
    def actualizar(id_registro, datos):
        sql = """UPDATE usuario SET nombreu = %s, contrasena = %s, idperfil = %s, idpersona = %s
                 WHERE Idusuario = %s"""
        return _ejecutar(sql, (datos["nombreu"], datos["contrasena"], datos["idperfil"],
                               datos["idpersona"], id_registro))

    @staticmethod
    def cambiar_estado(id_registro, estado):
        return _ejecutar("UPDATE usuario SET estado = %s WHERE Idusuario = %s", (estado, id_registro))
