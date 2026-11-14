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


def _transaccion(pasos):
    """Ejecuta varios INSERT/UPDATE en una sola transacción: o se guardan todos o ninguno.
    Cada paso es (sql, parametros) o una función que recibe el id generado por el paso anterior."""
    conexion = conectar_bd()
    try:
        cursor = conexion.cursor()
        ultimo_id = None
        for paso in pasos:
            sql, parametros = paso(ultimo_id) if callable(paso) else paso
            cursor.execute(sql, parametros)
            ultimo_id = cursor.lastrowid or ultimo_id
        conexion.commit()
        cursor.close()
        return ultimo_id
    except Exception:
        conexion.rollback()
        raise
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
                   u.idpersona, per.nom1, per.apell1, per.estado AS estado_persona,
                   pr.documento, pr.estado AS estado_productor,
                   u.nit, c.nombre AS cooperativa, c.estado AS estado_cooperativa
            FROM usuario u
            INNER JOIN perfil  p   ON u.idperfil  = p.Idperfil
            INNER JOIN persona per ON u.idpersona = per.Idpersona
            LEFT JOIN productor pr ON pr.idpersona = per.Idpersona
            LEFT JOIN cooperativa c ON c.nit = u.nit
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
            LEFT JOIN productor pr ON pr.idpersona = per.Idpersona
            WHERE u.nombreu = %s OR per.correo = %s OR CAST(per.Idpersona AS CHAR) = %s
               OR pr.documento = %s
            LIMIT 1
        """
        return _consultar(sql, (dato, dato, dato, dato), uno=True)

    @staticmethod
    def contar_activos():
        """Totales para las tarjetas del panel principal."""
        sql = """
            SELECT
              (SELECT COUNT(*) FROM persona WHERE estado = 'Activo') AS personas,
              (SELECT COUNT(*) FROM usuario WHERE estado = 'Activo') AS usuarios,
              (SELECT COUNT(*) FROM perfil  WHERE estado = 'Activo') AS perfiles,
              (SELECT COUNT(*) FROM productor   WHERE estado = 'Activo') AS productores,
              (SELECT COUNT(*) FROM finca       WHERE estado = 'Activo') AS fincas,
              (SELECT COUNT(*) FROM cooperativa WHERE estado = 'Activo') AS cooperativas,
              (SELECT COUNT(*) FROM variedad    WHERE estado = 'Activo') AS variedades
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
    def obtener(id_registro):
        return _consultar("SELECT Idperfil, descripc, estado FROM perfil WHERE Idperfil = %s",
                          (id_registro,), uno=True)

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
                   u.idpersona, CONCAT(per.nom1, ' ', per.apell1) AS persona,
                   u.nit, c.nombre AS cooperativa, u.estado
            FROM usuario u
            INNER JOIN perfil  p   ON u.idperfil  = p.Idperfil
            INNER JOIN persona per ON u.idpersona = per.Idpersona
            LEFT JOIN cooperativa c ON c.nit = u.nit
            WHERE u.nombreu LIKE %s OR p.descripc LIKE %s OR c.nombre LIKE %s
               OR CONCAT(per.nom1, ' ', per.apell1) LIKE %s OR CAST(u.Idusuario AS CHAR) = %s
            ORDER BY u.Idusuario
        """
        return _consultar(sql, (_filtro_texto(filtro),) * 4 + (filtro,))

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
        sql = """INSERT INTO usuario (nombreu, contrasena, idperfil, idpersona, nit, estado)
                 VALUES (%s, %s, %s, %s, %s, 'Activo')"""
        return _ejecutar(sql, (datos["nombreu"], datos["contrasena"], datos["idperfil"],
                               datos["idpersona"], datos.get("nit")))

    @staticmethod
    def actualizar(id_registro, datos):
        sql = """UPDATE usuario SET nombreu = %s, contrasena = %s, idperfil = %s, idpersona = %s, nit = %s
                 WHERE Idusuario = %s"""
        return _ejecutar(sql, (datos["nombreu"], datos["contrasena"], datos["idperfil"],
                               datos["idpersona"], datos.get("nit"), id_registro))

    @staticmethod
    def cambiar_estado(id_registro, estado):
        return _ejecutar("UPDATE usuario SET estado = %s WHERE Idusuario = %s", (estado, id_registro))


# =====================================================================
# PARCIAL II
# =====================================================================
class DatosUbicacion:
    """Departamentos y municipios de Colombia para las listas desplegables."""

    @staticmethod
    def departamentos():
        return _consultar("SELECT iddepartamento, nombre FROM departamento ORDER BY nombre")

    @staticmethod
    def municipios(iddepartamento):
        return _consultar("SELECT idmunicipio, nombre FROM municipio WHERE iddepartamento = %s ORDER BY nombre",
                          (iddepartamento,))

    @staticmethod
    def municipio(idmunicipio):
        return _consultar("SELECT idmunicipio, nombre, iddepartamento FROM municipio WHERE idmunicipio = %s",
                          (idmunicipio,), uno=True)


# ---------------------------------------------------------------------
# HU-01 · Productores cafeteros
# ---------------------------------------------------------------------
class DatosProductor:
    CAMPOS_PERSONA = ("nom1", "nom2", "apell1", "apell2", "movil", "direccion", "fecha_nac", "correo")

    @staticmethod
    def listar(filtro="", solo_documento=None):
        """Busca por documento, nombre, apellido o cooperativa. Trae sus cooperativas y su número de fincas."""
        sql = """
            SELECT pr.documento, pr.idpersona, per.nom1, per.nom2, per.apell1, per.apell2,
                   per.movil, per.direccion, CAST(per.fecha_nac AS CHAR) AS fecha_nac, per.correo,
                   CONCAT_WS(' ', per.nom1, per.nom2, per.apell1, per.apell2) AS nombre,
                   (SELECT GROUP_CONCAT(c.nombre ORDER BY c.nombre SEPARATOR ', ')
                      FROM asociacion a INNER JOIN cooperativa c ON c.nit = a.nit
                     WHERE a.documento = pr.documento AND a.estado = 'Activo') AS cooperativas,
                   (SELECT COUNT(*) FROM finca f
                     WHERE f.documento = pr.documento AND f.estado = 'Activo') AS fincas,
                   pr.estado
            FROM productor pr
            INNER JOIN persona per ON per.Idpersona = pr.idpersona
            WHERE (pr.documento LIKE %s
                   OR CONCAT_WS(' ', per.nom1, per.nom2) LIKE %s
                   OR CONCAT_WS(' ', per.apell1, per.apell2) LIKE %s
                   OR CONCAT_WS(' ', per.nom1, per.nom2, per.apell1, per.apell2) LIKE %s
                   OR EXISTS (SELECT 1 FROM asociacion a INNER JOIN cooperativa c ON c.nit = a.nit
                               WHERE a.documento = pr.documento AND c.nombre LIKE %s))
        """
        parametros = [_filtro_texto(filtro)] * 5
        if solo_documento is not None:
            sql += " AND pr.documento = %s"
            parametros.append(solo_documento)
        sql += " ORDER BY per.apell1, per.nom1"
        return _consultar(sql, tuple(parametros))

    @staticmethod
    def listar_activos():
        sql = """SELECT pr.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS nombre
                 FROM productor pr INNER JOIN persona per ON per.Idpersona = pr.idpersona
                 WHERE pr.estado = 'Activo' ORDER BY per.nom1, per.apell1"""
        return _consultar(sql)

    @staticmethod
    def listar_todos():
        sql = """SELECT pr.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS nombre
                 FROM productor pr INNER JOIN persona per ON per.Idpersona = pr.idpersona
                 ORDER BY per.nom1, per.apell1"""
        return _consultar(sql)

    @staticmethod
    def obtener(documento):
        return _consultar("SELECT documento, idpersona, estado FROM productor WHERE documento = %s",
                          (documento,), uno=True)

    @staticmethod
    def de_persona(idpersona):
        return _consultar("SELECT documento, estado FROM productor WHERE idpersona = %s", (idpersona,), uno=True)

    @staticmethod
    def existe_documento(documento):
        return _consultar("SELECT 1 AS si FROM productor WHERE documento = %s", (documento,), uno=True) is not None

    @staticmethod
    def existe_correo(correo, excluir_idpersona=None):
        fila = _consultar("SELECT COUNT(*) AS total FROM persona WHERE correo = %s AND Idpersona <> %s",
                          (correo, excluir_idpersona or 0), uno=True)
        return fila["total"] > 0

    @staticmethod
    def insertar(datos):
        """Crea la persona y el productor en una sola transacción."""
        columnas = ", ".join(DatosProductor.CAMPOS_PERSONA)
        marcas = ", ".join(["%s"] * len(DatosProductor.CAMPOS_PERSONA))
        valores = tuple(datos[c] for c in DatosProductor.CAMPOS_PERSONA)
        _transaccion([
            (f"INSERT INTO persona ({columnas}, estado) VALUES ({marcas}, 'Activo')", valores),
            lambda idpersona: ("INSERT INTO productor (documento, idpersona, estado) VALUES (%s, %s, 'Activo')",
                               (datos["documento"], idpersona)),
        ])
        return datos["documento"]

    @staticmethod
    def actualizar(idpersona, datos):
        """El documento no se modifica: solo los datos personales."""
        asignaciones = ", ".join(f"{c} = %s" for c in DatosProductor.CAMPOS_PERSONA)
        return _ejecutar(f"UPDATE persona SET {asignaciones} WHERE Idpersona = %s",
                         tuple(datos[c] for c in DatosProductor.CAMPOS_PERSONA) + (idpersona,))

    @staticmethod
    def cambiar_estado(documento, estado):
        return _ejecutar("UPDATE productor SET estado = %s WHERE documento = %s", (estado, documento))


# ---------------------------------------------------------------------
# HU-02 · Fincas
# ---------------------------------------------------------------------
class DatosFinca:
    CAMPOS = ("codigof", "nombre", "area", "temperatura", "telefono", "direccion", "idmunicipio", "documento")

    @staticmethod
    def listar(filtro="", solo_documento=None, iddepartamento=None, idmunicipio=None, documento=None):
        sql = """
            SELECT f.codigof, f.nombre, CAST(f.area AS CHAR) AS area, CAST(f.temperatura AS CHAR) AS temperatura,
                   f.telefono, f.direccion, f.idmunicipio, m.nombre AS municipio,
                   d.iddepartamento, d.nombre AS departamento,
                   f.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS productor, f.estado
            FROM finca f
            INNER JOIN municipio m    ON m.idmunicipio = f.idmunicipio
            INNER JOIN departamento d ON d.iddepartamento = m.iddepartamento
            INNER JOIN productor pr   ON pr.documento = f.documento
            INNER JOIN persona per    ON per.Idpersona = pr.idpersona
            WHERE (f.codigof LIKE %s OR f.nombre LIKE %s OR m.nombre LIKE %s
                   OR CONCAT_WS(' ', per.nom1, per.apell1) LIKE %s)
        """
        parametros = [_filtro_texto(filtro)] * 4
        for columna, valor in (("f.documento", solo_documento), ("d.iddepartamento", iddepartamento),
                               ("f.idmunicipio", idmunicipio), ("f.documento", documento)):
            if valor is not None:
                sql += f" AND {columna} = %s"
                parametros.append(valor)
        sql += " ORDER BY f.nombre"
        return _consultar(sql, tuple(parametros))

    @staticmethod
    def obtener(codigof):
        return _consultar("SELECT codigof, documento, estado FROM finca WHERE codigof = %s", (codigof,), uno=True)

    @staticmethod
    def insertar(datos):
        columnas = ", ".join(DatosFinca.CAMPOS)
        marcas = ", ".join(["%s"] * len(DatosFinca.CAMPOS))
        _ejecutar(f"INSERT INTO finca ({columnas}, estado) VALUES ({marcas}, 'Activo')",
                  tuple(datos[c] for c in DatosFinca.CAMPOS))
        return datos["codigof"]

    @staticmethod
    def actualizar(codigof, datos):
        """Se modifican todos los datos menos el codigof."""
        campos = [c for c in DatosFinca.CAMPOS if c != "codigof"]
        asignaciones = ", ".join(f"{c} = %s" for c in campos)
        return _ejecutar(f"UPDATE finca SET {asignaciones} WHERE codigof = %s",
                         tuple(datos[c] for c in campos) + (codigof,))

    @staticmethod
    def cambiar_estado(codigof, estado):
        return _ejecutar("UPDATE finca SET estado = %s WHERE codigof = %s", (estado, codigof))


# ---------------------------------------------------------------------
# HU-03 · Cooperativas
# ---------------------------------------------------------------------
class DatosCooperativa:
    CAMPOS = ("nit", "nombre", "direccion", "telefono", "correo")

    @staticmethod
    def listar(filtro="", solo_nit=None):
        sql = """
            SELECT c.nit, c.nombre, c.direccion, c.telefono, c.correo,
                   (SELECT COUNT(*) FROM asociacion a WHERE a.nit = c.nit AND a.estado = 'Activo') AS productores,
                   (SELECT COUNT(*) FROM usuario u WHERE u.nit = c.nit AND u.estado = 'Activo') AS compradores,
                   c.estado
            FROM cooperativa c
            WHERE (c.nit LIKE %s OR c.nombre LIKE %s OR c.correo LIKE %s)
        """
        parametros = [_filtro_texto(filtro)] * 3
        if solo_nit is not None:
            sql += " AND c.nit = %s"
            parametros.append(solo_nit)
        sql += " ORDER BY c.nombre"
        return _consultar(sql, tuple(parametros))

    @staticmethod
    def listar_activas():
        return _consultar("SELECT nit, nombre FROM cooperativa WHERE estado = 'Activo' ORDER BY nombre")

    @staticmethod
    def obtener(nit):
        return _consultar("SELECT nit, nombre, estado FROM cooperativa WHERE nit = %s", (nit,), uno=True)

    @staticmethod
    def existe(columna, valor, excluir_nit=None):
        assert columna in ("nit", "nombre", "correo")
        fila = _consultar(f"SELECT COUNT(*) AS total FROM cooperativa WHERE {columna} = %s AND nit <> %s",
                          (valor, excluir_nit or ""), uno=True)
        return fila["total"] > 0

    @staticmethod
    def productores_asociados(nit):
        sql = """
            SELECT a.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS productor, per.movil,
                   CAST(a.fecha_afiliacion AS CHAR) AS fecha_afiliacion,
                   CAST(a.fecha_retiro AS CHAR) AS fecha_retiro, a.estado
            FROM asociacion a
            INNER JOIN productor pr ON pr.documento = a.documento
            INNER JOIN persona per ON per.Idpersona = pr.idpersona
            WHERE a.nit = %s
            ORDER BY FIELD(a.estado, 'Activo', 'Pendiente', 'Inactivo', 'Rechazada'), per.nom1
        """
        return _consultar(sql, (nit,))

    @staticmethod
    def usuarios_compradores(nit):
        sql = """
            SELECT u.nombreu, CONCAT_WS(' ', per.nom1, per.apell1) AS persona, per.correo, u.estado
            FROM usuario u INNER JOIN persona per ON per.Idpersona = u.idpersona
            WHERE u.nit = %s ORDER BY u.nombreu
        """
        return _consultar(sql, (nit,))

    @staticmethod
    def insertar(datos):
        columnas = ", ".join(DatosCooperativa.CAMPOS)
        marcas = ", ".join(["%s"] * len(DatosCooperativa.CAMPOS))
        _ejecutar(f"INSERT INTO cooperativa ({columnas}, estado) VALUES ({marcas}, 'Activo')",
                  tuple(datos[c] for c in DatosCooperativa.CAMPOS))
        return datos["nit"]

    @staticmethod
    def actualizar(nit, datos):
        """Se modifican todos los datos menos el NIT."""
        campos = [c for c in DatosCooperativa.CAMPOS if c != "nit"]
        asignaciones = ", ".join(f"{c} = %s" for c in campos)
        return _ejecutar(f"UPDATE cooperativa SET {asignaciones} WHERE nit = %s",
                         tuple(datos[c] for c in campos) + (nit,))

    @staticmethod
    def cambiar_estado(nit, estado):
        return _ejecutar("UPDATE cooperativa SET estado = %s WHERE nit = %s", (estado, nit))


# ---------------------------------------------------------------------
# HU-04 · Asociación de productores a cooperativas
# ---------------------------------------------------------------------
class DatosAsociacion:

    @staticmethod
    def listar(filtro="", solo_nit=None, solo_documento=None):
        sql = """
            SELECT a.idasociacion, a.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS productor,
                   a.nit, c.nombre AS cooperativa,
                   CAST(DATE(a.fecha_solicitud) AS CHAR) AS fecha_solicitud,
                   CAST(a.fecha_afiliacion AS CHAR) AS fecha_afiliacion,
                   CAST(a.fecha_retiro AS CHAR) AS fecha_retiro,
                   us.nombreu AS solicitado_por, a.estado
            FROM asociacion a
            INNER JOIN productor pr  ON pr.documento = a.documento
            INNER JOIN persona per   ON per.Idpersona = pr.idpersona
            INNER JOIN cooperativa c ON c.nit = a.nit
            LEFT JOIN usuario us     ON us.Idusuario = a.idusuario_solicita
            WHERE (a.documento LIKE %s OR CONCAT_WS(' ', per.nom1, per.apell1) LIKE %s
                   OR c.nombre LIKE %s OR a.estado LIKE %s)
        """
        parametros = [_filtro_texto(filtro)] * 4
        if solo_nit is not None:
            sql += " AND a.nit = %s"
            parametros.append(solo_nit)
        if solo_documento is not None:
            sql += " AND a.documento = %s"
            parametros.append(solo_documento)
        sql += " ORDER BY FIELD(a.estado, 'Pendiente', 'Activo', 'Inactivo', 'Rechazada'), a.idasociacion DESC"
        return _consultar(sql, tuple(parametros))

    @staticmethod
    def de_productor(documento):
        sql = """
            SELECT c.nit, c.nombre AS cooperativa, CAST(a.fecha_afiliacion AS CHAR) AS fecha_afiliacion,
                   CAST(a.fecha_retiro AS CHAR) AS fecha_retiro, a.estado
            FROM asociacion a INNER JOIN cooperativa c ON c.nit = a.nit
            WHERE a.documento = %s
            ORDER BY FIELD(a.estado, 'Activo', 'Pendiente', 'Inactivo', 'Rechazada'), c.nombre
        """
        return _consultar(sql, (documento,))

    @staticmethod
    def obtener(idasociacion):
        return _consultar("SELECT idasociacion, documento, nit, estado FROM asociacion WHERE idasociacion = %s",
                          (idasociacion,), uno=True)

    @staticmethod
    def vigente(documento, nit):
        """Asociación Activa o Pendiente entre ese productor y esa cooperativa (si existe)."""
        return _consultar("""SELECT idasociacion, estado FROM asociacion
                             WHERE documento = %s AND nit = %s AND estado IN ('Activo', 'Pendiente')""",
                          (documento, nit), uno=True)

    @staticmethod
    def insertar(documento, nit, estado, idusuario_solicita=None):
        if estado == "Activo":
            sql = """INSERT INTO asociacion (documento, nit, fecha_afiliacion, idusuario_solicita, estado)
                     VALUES (%s, %s, CURDATE(), %s, 'Activo')"""
            return _ejecutar(sql, (documento, nit, idusuario_solicita))
        sql = """INSERT INTO asociacion (documento, nit, idusuario_solicita, estado)
                 VALUES (%s, %s, %s, 'Pendiente')"""
        return _ejecutar(sql, (documento, nit, idusuario_solicita))

    @staticmethod
    def aprobar(idasociacion):
        return _ejecutar("""UPDATE asociacion SET estado = 'Activo', fecha_afiliacion = CURDATE()
                            WHERE idasociacion = %s AND estado = 'Pendiente'""", (idasociacion,))

    @staticmethod
    def rechazar(idasociacion):
        return _ejecutar("""UPDATE asociacion SET estado = 'Rechazada'
                            WHERE idasociacion = %s AND estado = 'Pendiente'""", (idasociacion,))

    @staticmethod
    def desasociar(idasociacion):
        return _ejecutar("""UPDATE asociacion SET estado = 'Inactivo', fecha_retiro = CURDATE()
                            WHERE idasociacion = %s AND estado = 'Activo'""", (idasociacion,))


# ---------------------------------------------------------------------
# HU-05 · Tipos de variedades
# ---------------------------------------------------------------------
class DatosVariedad:

    @staticmethod
    def listar(filtro="", solo_activas=False):
        sql = """
            SELECT codigotv, descripcion, imagen_tipo, ROUND(LENGTH(imagen) / 1024) AS imagen_kb, estado
            FROM variedad
            WHERE (codigotv LIKE %s OR descripcion LIKE %s)
        """
        if solo_activas:
            sql += " AND estado = 'Activo'"
        sql += " ORDER BY descripcion"
        return _consultar(sql, (_filtro_texto(filtro),) * 2)

    @staticmethod
    def imagen(codigotv):
        fila = _consultar("SELECT imagen FROM variedad WHERE codigotv = %s", (codigotv,), uno=True)
        return bytes(fila["imagen"]) if fila and fila["imagen"] is not None else None

    @staticmethod
    def existe(columna, valor, excluir_codigo=None):
        assert columna in ("codigotv", "descripcion")
        fila = _consultar(f"SELECT COUNT(*) AS total FROM variedad WHERE {columna} = %s AND codigotv <> %s",
                          (valor, excluir_codigo or ""), uno=True)
        return fila["total"] > 0

    @staticmethod
    def insertar(datos):
        _ejecutar("""INSERT INTO variedad (codigotv, descripcion, imagen, imagen_tipo, estado)
                     VALUES (%s, %s, %s, %s, 'Activo')""",
                  (datos["codigotv"], datos["descripcion"], datos["imagen"], datos["imagen_tipo"]))
        return datos["codigotv"]

    @staticmethod
    def actualizar(codigotv, datos):
        """El codigotv no se modifica. La imagen solo cambia si se eligió una nueva."""
        if datos.get("imagen") is not None:
            return _ejecutar("UPDATE variedad SET descripcion = %s, imagen = %s, imagen_tipo = %s WHERE codigotv = %s",
                             (datos["descripcion"], datos["imagen"], datos["imagen_tipo"], codigotv))
        return _ejecutar("UPDATE variedad SET descripcion = %s WHERE codigotv = %s",
                         (datos["descripcion"], codigotv))

    @staticmethod
    def cambiar_estado(codigotv, estado):
        return _ejecutar("UPDATE variedad SET estado = %s WHERE codigotv = %s", (estado, codigotv))

