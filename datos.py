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
              (SELECT COUNT(*) FROM variedad    WHERE estado = 'Activo') AS variedades,
              (SELECT COUNT(*) FROM lote l WHERE l.estado = 'Activo'
                 AND l.cantidad > COALESCE((SELECT SUM(d.cantidad) FROM detalle_negocio d
                        INNER JOIN negocio n ON n.idnegocio = d.idnegocio
                        WHERE d.codigoc = l.codigoc AND n.estado = 'Activo'
                          AND n.estado_negocio IN ('Aceptado', 'En entrega', 'Completado')), 0)) AS lotes,
              (SELECT COUNT(*) FROM negocio WHERE estado = 'Activo'
                 AND estado_negocio IN ('Propuesto', 'Aceptado', 'En entrega')) AS negocios
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
                   f.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS productor,
                   (SELECT COUNT(*) FROM lote l WHERE l.codigof = f.codigof AND l.estado = 'Activo') AS lotes,
                   f.estado
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


# =====================================================================
# FINAL
# =====================================================================
ESTADOS_QUE_COMPROMETEN = "('Aceptado', 'En entrega', 'Completado')"
ESTADOS_ACTIVOS = "('Propuesto', 'Aceptado', 'En entrega')"

# Empaques de un lote ya comprometidos en negocios Aceptados, En entrega o Completados.
SQL_COMPROMETIDA = f"""(SELECT COALESCE(SUM(dn.cantidad), 0)
        FROM detalle_negocio dn INNER JOIN negocio ng ON ng.idnegocio = dn.idnegocio
        WHERE dn.codigoc = l.codigoc AND ng.estado = 'Activo'
          AND ng.estado_negocio IN {ESTADOS_QUE_COMPROMETEN})"""


class DatosListas:

    @staticmethod
    def empaques():
        return _consultar("SELECT idempaque, descripcion FROM empaque WHERE estado = 'Activo' ORDER BY descripcion")

    @staticmethod
    def medios_pago():
        return _consultar("SELECT idmedio, descripcion FROM medio_pago WHERE estado = 'Activo' ORDER BY idmedio")


# ---------------------------------------------------------------------
# HU-06 · Inventario de lotes de café
# ---------------------------------------------------------------------
class DatosLote:
    CAMPOS = ("codigoc", "descripcion", "peso", "cantidad", "precio", "codigof", "codigotv", "idempaque")

    @staticmethod
    def listar(filtro="", solo_documento=None):
        sql = f"""
            SELECT l.codigoc, l.descripcion, l.codigof, f.nombre AS finca, f.documento,
                   l.codigotv, v.descripcion AS variedad, l.idempaque, e.descripcion AS empaque,
                   CAST(l.peso AS CHAR) AS peso, l.cantidad, CAST(l.precio AS CHAR) AS precio,
                   {SQL_COMPROMETIDA} AS comprometida,
                   l.cantidad - {SQL_COMPROMETIDA} AS disponible,
                   CAST(l.fecha_registro AS CHAR) AS fecha_registro, l.imagen_tipo, l.estado
            FROM lote l
            INNER JOIN finca f    ON f.codigof = l.codigof
            INNER JOIN variedad v ON v.codigotv = l.codigotv
            INNER JOIN empaque e  ON e.idempaque = l.idempaque
            WHERE (l.codigoc LIKE %s OR l.descripcion LIKE %s OR v.descripcion LIKE %s OR f.nombre LIKE %s)
        """
        parametros = [_filtro_texto(filtro)] * 4
        if solo_documento is not None:
            sql += " AND f.documento = %s"
            parametros.append(solo_documento)
        sql += " ORDER BY l.fecha_registro DESC"
        return _consultar(sql, tuple(parametros))

    @staticmethod
    def obtener(codigoc):
        sql = f"""
            SELECT l.codigoc, l.descripcion, l.peso, l.cantidad, l.precio, l.codigof, l.codigotv, l.idempaque,
                   l.estado, f.documento, f.estado AS estado_finca, pr.estado AS estado_productor,
                   v.descripcion AS variedad, e.descripcion AS empaque,
                   {SQL_COMPROMETIDA} AS comprometida
            FROM lote l
            INNER JOIN finca f     ON f.codigof = l.codigof
            INNER JOIN productor pr ON pr.documento = f.documento
            INNER JOIN variedad v  ON v.codigotv = l.codigotv
            INNER JOIN empaque e   ON e.idempaque = l.idempaque
            WHERE l.codigoc = %s
        """
        return _consultar(sql, (codigoc,), uno=True)

    @staticmethod
    def imagen(codigoc):
        fila = _consultar("SELECT imagen FROM lote WHERE codigoc = %s", (codigoc,), uno=True)
        return bytes(fila["imagen"]) if fila and fila["imagen"] is not None else None

    @staticmethod
    def tiene_negocios(codigoc):
        """True si el lote está en algún negocio vigente (no rechazado, cancelado ni anulado)."""
        fila = _consultar(f"""SELECT COUNT(*) AS total FROM detalle_negocio d
                              INNER JOIN negocio n ON n.idnegocio = d.idnegocio
                              WHERE d.codigoc = %s AND n.estado = 'Activo'
                                AND n.estado_negocio IN ('Propuesto', 'Aceptado', 'En entrega', 'Completado')""",
                          (codigoc,), uno=True)
        return fila["total"] > 0

    @staticmethod
    def insertar(datos):
        _ejecutar("""INSERT INTO lote (codigoc, descripcion, imagen, imagen_tipo, peso, cantidad, precio,
                                       codigof, codigotv, idempaque, fecha_registro, estado)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 'Activo')""",
                  (datos["codigoc"], datos["descripcion"], datos["imagen"], datos["imagen_tipo"], datos["peso"],
                   datos["cantidad"], datos["precio"], datos["codigof"], datos["codigotv"], datos["idempaque"]))
        return datos["codigoc"]

    @staticmethod
    def actualizar(codigoc, datos):
        campos = ["descripcion", "peso", "cantidad", "precio", "codigof", "codigotv", "idempaque"]
        valores = [datos[c] for c in campos]
        if datos.get("imagen") is not None:
            campos += ["imagen", "imagen_tipo"]
            valores += [datos["imagen"], datos["imagen_tipo"]]
        asignaciones = ", ".join(f"{c} = %s" for c in campos)
        return _ejecutar(f"UPDATE lote SET {asignaciones} WHERE codigoc = %s", tuple(valores) + (codigoc,))

    @staticmethod
    def cambiar_estado(codigoc, estado):
        return _ejecutar("UPDATE lote SET estado = %s WHERE codigoc = %s", (estado, codigoc))

    @staticmethod
    def finca_ocupada(codigof):
        """Lotes de la finca con café disponible, o comprometidos en negocios activos."""
        fila = _consultar(f"""
            SELECT
              (SELECT COUNT(*) FROM lote l WHERE l.codigof = %s AND l.estado = 'Activo'
                 AND l.cantidad - {SQL_COMPROMETIDA} > 0) AS disponibles,
              (SELECT COUNT(*) FROM detalle_negocio d INNER JOIN negocio n ON n.idnegocio = d.idnegocio
                 INNER JOIN lote l2 ON l2.codigoc = d.codigoc
                 WHERE l2.codigof = %s AND n.estado = 'Activo' AND n.estado_negocio IN {ESTADOS_ACTIVOS}) AS en_negocios
        """, (codigof, codigof), uno=True)
        return fila

    @staticmethod
    def de_productor_disponibles(documento):
        """Lotes activos con cantidad disponible de un productor (para armar un negocio)."""
        sql = f"""
            SELECT l.codigoc, l.descripcion, v.descripcion AS variedad, e.descripcion AS empaque,
                   l.peso, l.precio, l.cantidad - {SQL_COMPROMETIDA} AS disponible
            FROM lote l
            INNER JOIN finca f    ON f.codigof = l.codigof
            INNER JOIN variedad v ON v.codigotv = l.codigotv
            INNER JOIN empaque e  ON e.idempaque = l.idempaque
            WHERE f.documento = %s AND l.estado = 'Activo' AND f.estado = 'Activo'
            HAVING disponible > 0
            ORDER BY l.codigoc
        """
        return _consultar(sql, (documento,))


# ---------------------------------------------------------------------
# HU-10 · Listado detallado de lotes disponibles
# ---------------------------------------------------------------------
class DatosCatalogo:
    ORDENES = {"precio": "precio_num", "kg": "kg_disponibles", "fecha": "fecha_registro"}

    @staticmethod
    def listar(texto="", nit_comprador=None, incluir_todos=False, codigotv=None, iddepartamento=None,
               idmunicipio=None, nit=None, precio_min=None, precio_max=None, orden="fecha", descendente=True):
        interno = f"""
            SELECT l.codigoc, l.descripcion, l.codigotv, v.descripcion AS variedad,
                   e.descripcion AS empaque, l.peso AS peso_num, CAST(l.peso AS CHAR) AS peso,
                   l.precio AS precio_num, CAST(l.precio AS CHAR) AS precio,
                   l.cantidad - {SQL_COMPROMETIDA} AS disponible,
                   (l.cantidad - {SQL_COMPROMETIDA}) * l.peso AS kg_disponibles,
                   f.codigof, f.nombre AS finca, f.temperatura, m.idmunicipio, m.nombre AS municipio,
                   d.iddepartamento, d.nombre AS departamento,
                   pr.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS productor,
                   (SELECT GROUP_CONCAT(c.nombre ORDER BY c.nombre SEPARATOR ', ')
                      FROM asociacion a INNER JOIN cooperativa c ON c.nit = a.nit
                     WHERE a.documento = pr.documento AND a.estado = 'Activo') AS cooperativas,
                   EXISTS (SELECT 1 FROM asociacion a WHERE a.documento = pr.documento AND a.estado = 'Activo'
                             AND a.nit = %s) AS asociado,
                   l.fecha_registro, l.estado, f.estado AS estado_finca, pr.estado AS estado_productor
            FROM lote l
            INNER JOIN variedad v     ON v.codigotv = l.codigotv
            INNER JOIN empaque e      ON e.idempaque = l.idempaque
            INNER JOIN finca f        ON f.codigof = l.codigof
            INNER JOIN municipio m    ON m.idmunicipio = f.idmunicipio
            INNER JOIN departamento d ON d.iddepartamento = m.iddepartamento
            INNER JOIN productor pr   ON pr.documento = f.documento
            INNER JOIN persona per    ON per.Idpersona = pr.idpersona
        """
        sql = f"SELECT * FROM ({interno}) t WHERE 1 = 1"
        parametros = [nit_comprador or ""]
        if not incluir_todos:
            # Solo lotes Activos, con cantidad disponible, de productores y fincas activos.
            sql += " AND t.estado = 'Activo' AND t.disponible > 0 AND t.estado_finca = 'Activo' AND t.estado_productor = 'Activo'"
        if texto:
            sql += " AND t.descripcion LIKE %s"
            parametros.append(_filtro_texto(texto))
        for columna, valor in (("t.codigotv", codigotv), ("t.iddepartamento", iddepartamento),
                               ("t.idmunicipio", idmunicipio)):
            if valor is not None:
                sql += f" AND {columna} = %s"
                parametros.append(valor)
        if nit is not None:
            sql += (" AND EXISTS (SELECT 1 FROM asociacion a WHERE a.documento = t.documento"
                    " AND a.estado = 'Activo' AND a.nit = %s)")
            parametros.append(nit)
        if precio_min is not None:
            sql += " AND t.precio_num >= %s"
            parametros.append(precio_min)
        if precio_max is not None:
            sql += " AND t.precio_num <= %s"
            parametros.append(precio_max)
        sql += f" ORDER BY {DatosCatalogo.ORDENES.get(orden, 'fecha_registro')} {'DESC' if descendente else 'ASC'}"
        return _consultar(sql, tuple(parametros))


# ---------------------------------------------------------------------
# HU-07 · Negocios con su detalle
# ---------------------------------------------------------------------
class DatosNegocio:

    @staticmethod
    def insertar(cabecera, lineas):
        """Guarda el negocio y sus líneas en una sola transacción. Devuelve el idnegocio."""
        conexion = conectar_bd()
        try:
            cursor = conexion.cursor()
            cursor.execute("""INSERT INTO negocio (codigoe, fecha_hora, descripcion, idmedio, valor_total,
                                                   estado_negocio, documento, nit, idusuario, token, estado)
                              VALUES (%s, NOW(), %s, %s, %s, 'Propuesto', %s, %s, %s, %s, 'Activo')""",
                           (cabecera["token"][:20], cabecera["descripcion"], cabecera["idmedio"],
                            cabecera["valor_total"], cabecera["documento"], cabecera["nit"],
                            cabecera["idusuario"], cabecera["token"]))
            idnegocio = cursor.lastrowid
            cursor.execute("UPDATE negocio SET codigoe = CONCAT('NEG-', LPAD(idnegocio, 4, '0')) WHERE idnegocio = %s",
                           (idnegocio,))
            DatosNegocio._insertar_lineas(cursor, idnegocio, lineas)
            conexion.commit()
            cursor.close()
            return idnegocio
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    @staticmethod
    def _insertar_lineas(cursor, idnegocio, lineas):
        for linea in lineas:
            cursor.execute("""INSERT INTO detalle_negocio (idnegocio, codigoc, cantidad, peso, precio_kg, subtotal)
                              VALUES (%s, %s, %s, %s, %s, %s)""",
                           (idnegocio, linea["codigoc"], linea["cantidad"], linea["peso"],
                            linea["precio_kg"], linea["subtotal"]))

    @staticmethod
    def actualizar(idnegocio, cabecera, lineas):
        """Solo se usa en negocios Propuestos: todavía no tienen entregas, así que el detalle se rehace."""
        conexion = conectar_bd()
        try:
            cursor = conexion.cursor()
            cursor.execute("""UPDATE negocio SET descripcion = %s, idmedio = %s, valor_total = %s, fecha_hora = NOW()
                              WHERE idnegocio = %s""",
                           (cabecera["descripcion"], cabecera["idmedio"], cabecera["valor_total"], idnegocio))
            cursor.execute("DELETE FROM detalle_negocio WHERE idnegocio = %s", (idnegocio,))
            DatosNegocio._insertar_lineas(cursor, idnegocio, lineas)
            conexion.commit()
            cursor.close()
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    SELECT_NEGOCIO = """
        SELECT n.idnegocio, n.codigoe, CAST(n.fecha_hora AS CHAR) AS fecha_hora, n.descripcion, n.idmedio,
               mp.descripcion AS medio_pago, CAST(n.valor_total AS CHAR) AS valor_total, n.estado_negocio,
               n.documento, CONCAT_WS(' ', per.nom1, per.apell1) AS productor, per.movil AS telefono_productor,
               n.nit, c.nombre AS cooperativa, c.telefono AS telefono_cooperativa, c.estado AS estado_cooperativa,
               u.nombreu AS comprador, n.motivo_rechazo, CAST(n.fecha_respuesta AS CHAR) AS fecha_respuesta,
               n.token, n.estado
        FROM negocio n
        INNER JOIN medio_pago mp ON mp.idmedio = n.idmedio
        INNER JOIN productor pr  ON pr.documento = n.documento
        INNER JOIN persona per   ON per.Idpersona = pr.idpersona
        INNER JOIN cooperativa c ON c.nit = n.nit
        INNER JOIN usuario u     ON u.Idusuario = n.idusuario
    """

    @staticmethod
    def listar(filtro="", nit=None, documento=None):
        sql = DatosNegocio.SELECT_NEGOCIO + """
            WHERE (n.codigoe LIKE %s OR CONCAT_WS(' ', per.nom1, per.apell1) LIKE %s OR c.nombre LIKE %s
                   OR n.estado_negocio LIKE %s)
        """
        parametros = [_filtro_texto(filtro)] * 4
        if nit is not None:
            sql += " AND n.nit = %s"
            parametros.append(nit)
        if documento is not None:
            sql += " AND n.documento = %s"
            parametros.append(documento)
        sql += " ORDER BY n.idnegocio DESC"
        return _consultar(sql, tuple(parametros))

    @staticmethod
    def obtener(idnegocio=None, token=None, codigoe=None):
        if token is not None:
            return _consultar(DatosNegocio.SELECT_NEGOCIO + " WHERE n.token = %s", (token,), uno=True)
        if codigoe is not None:
            return _consultar(DatosNegocio.SELECT_NEGOCIO + " WHERE n.codigoe = %s", (codigoe,), uno=True)
        return _consultar(DatosNegocio.SELECT_NEGOCIO + " WHERE n.idnegocio = %s", (idnegocio,), uno=True)

    @staticmethod
    def detalle(idnegocio):
        """Líneas del negocio con lo programado, lo recibido y lo pendiente por programar."""
        sql = """
            SELECT d.iddetalle, d.codigoc, l.descripcion AS lote, v.descripcion AS variedad,
                   e.descripcion AS empaque, CAST(d.peso AS CHAR) AS peso, d.cantidad,
                   CAST(d.precio_kg AS CHAR) AS precio_kg, CAST(d.subtotal AS CHAR) AS subtotal,
                   COALESCE((SELECT SUM(CASE WHEN en.estado_entrega IN ('Programada', 'En tránsito') THEN en.cantidad
                                             ELSE en.cantidad_recibida END)
                               FROM entrega en WHERE en.iddetalle = d.iddetalle AND en.estado = 'Activo'), 0) AS programada,
                   COALESCE((SELECT SUM(en.cantidad_recibida) FROM entrega en
                              WHERE en.iddetalle = d.iddetalle AND en.estado = 'Activo'
                                AND en.estado_entrega IN ('Recibida', 'Recibida con novedad')), 0) AS recibida
            FROM detalle_negocio d
            INNER JOIN lote l     ON l.codigoc = d.codigoc
            INNER JOIN variedad v ON v.codigotv = l.codigotv
            INNER JOIN empaque e  ON e.idempaque = l.idempaque
            WHERE d.idnegocio = %s
            ORDER BY d.iddetalle
        """
        filas = _consultar(sql, (idnegocio,))
        for fila in filas:
            fila["programada"] = int(fila["programada"])
            fila["recibida"] = int(fila["recibida"])
            fila["pendiente"] = fila["cantidad"] - fila["programada"]
        return filas

    @staticmethod
    def cambiar_estado(idnegocio, estado_negocio, estado="Activo", motivo=None, respuesta=False):
        sql = "UPDATE negocio SET estado_negocio = %s, estado = %s"
        parametros = [estado_negocio, estado]
        if motivo is not None:
            sql += ", motivo_rechazo = %s"
            parametros.append(motivo)
        if respuesta:
            sql += ", fecha_respuesta = NOW()"
        sql += " WHERE idnegocio = %s"
        parametros.append(idnegocio)
        return _ejecutar(sql, tuple(parametros))

    @staticmethod
    def contar(estados, documento=None, nit=None):
        sql = f"SELECT COUNT(*) AS total FROM negocio WHERE estado = 'Activo' AND estado_negocio IN {estados}"
        parametros = []
        if documento is not None:
            sql += " AND documento = %s"
            parametros.append(documento)
        if nit is not None:
            sql += " AND nit = %s"
            parametros.append(nit)
        return _consultar(sql, tuple(parametros), uno=True)["total"]


# ---------------------------------------------------------------------
# HU-08 y HU-09 · Entregas y confirmación de recibido
# ---------------------------------------------------------------------
class DatosEntrega:
    SELECT_ENTREGA = """
        SELECT en.code, en.iddetalle, CAST(en.fecha AS CHAR) AS fecha, LEFT(CAST(en.hora AS CHAR), 5) AS hora,
               en.cantidad, en.descripcion, en.lugar, en.estado_entrega, en.estado,
               en.cantidad_recibida, en.novedad, CAST(en.fecha_confirmacion AS CHAR) AS fecha_confirmacion,
               uc.nombreu AS confirmado_por, en.aviso_llegada, en.token,
               d.codigoc, d.cantidad AS cantidad_linea, l.descripcion AS lote,
               n.idnegocio, n.codigoe, n.estado_negocio, n.estado AS estado_negocio_registro, n.documento, n.nit,
               CONCAT_WS(' ', per.nom1, per.apell1) AS productor, per.movil AS telefono_productor,
               c.nombre AS cooperativa, c.telefono AS telefono_cooperativa
        FROM entrega en
        INNER JOIN detalle_negocio d ON d.iddetalle = en.iddetalle
        INNER JOIN lote l            ON l.codigoc = d.codigoc
        INNER JOIN negocio n         ON n.idnegocio = d.idnegocio
        INNER JOIN productor pr      ON pr.documento = n.documento
        INNER JOIN persona per       ON per.Idpersona = pr.idpersona
        INNER JOIN cooperativa c     ON c.nit = n.nit
        LEFT JOIN usuario uc         ON uc.Idusuario = en.idusuario_confirma
    """

    @staticmethod
    def de_negocio(idnegocio):
        return _consultar(DatosEntrega.SELECT_ENTREGA + " WHERE n.idnegocio = %s ORDER BY en.fecha, en.hora",
                          (idnegocio,))

    @staticmethod
    def obtener(code=None, token=None):
        if token is not None:
            return _consultar(DatosEntrega.SELECT_ENTREGA + " WHERE en.token = %s", (token,), uno=True)
        return _consultar(DatosEntrega.SELECT_ENTREGA + " WHERE en.code = %s", (code,), uno=True)

    @staticmethod
    def programado_linea(iddetalle, excluir_code=None):
        """Empaques de la línea en entregas no canceladas (lo recibido cuenta por lo que realmente llegó)."""
        fila = _consultar("""
            SELECT COALESCE(SUM(CASE WHEN estado_entrega IN ('Programada', 'En tránsito') THEN cantidad
                                     ELSE cantidad_recibida END), 0) AS total
            FROM entrega WHERE iddetalle = %s AND estado = 'Activo' AND code <> %s
        """, (iddetalle, excluir_code or ""), uno=True)
        return int(fila["total"])

    @staticmethod
    def insertar(datos):
        _ejecutar("""INSERT INTO entrega (code, iddetalle, fecha, hora, cantidad, descripcion, lugar,
                                          estado_entrega, estado, fecha_registro, token)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, 'Programada', 'Activo', NOW(), %s)""",
                  (datos["code"], datos["iddetalle"], datos["fecha"], datos["hora"], datos["cantidad"],
                   datos["descripcion"], datos["lugar"], datos["token"]))
        return datos["code"]

    @staticmethod
    def actualizar(code, datos):
        return _ejecutar("""UPDATE entrega SET iddetalle = %s, fecha = %s, hora = %s, cantidad = %s,
                                              descripcion = %s, lugar = %s
                            WHERE code = %s""",
                         (datos["iddetalle"], datos["fecha"], datos["hora"], datos["cantidad"],
                          datos["descripcion"], datos["lugar"], code))

    @staticmethod
    def cambiar_estado(code, estado_entrega, estado="Activo"):
        return _ejecutar("UPDATE entrega SET estado_entrega = %s, estado = %s WHERE code = %s",
                         (estado_entrega, estado, code))

    @staticmethod
    def cancelar_pendientes_de_negocio(idnegocio):
        return _ejecutar("""UPDATE entrega en INNER JOIN detalle_negocio d ON d.iddetalle = en.iddetalle
                            SET en.estado_entrega = 'Cancelada', en.estado = 'Anulado'
                            WHERE d.idnegocio = %s AND en.estado_entrega IN ('Programada', 'En tránsito')""",
                         (idnegocio,))

    @staticmethod
    def recibidas_de_negocio(idnegocio):
        fila = _consultar("""SELECT COUNT(*) AS total FROM entrega en
                             INNER JOIN detalle_negocio d ON d.iddetalle = en.iddetalle
                             WHERE d.idnegocio = %s AND en.estado = 'Activo'
                               AND en.estado_entrega IN ('Recibida', 'Recibida con novedad')""",
                          (idnegocio,), uno=True)
        return fila["total"]

    @staticmethod
    def confirmar(code, cantidad_recibida, novedad, estado_entrega, idusuario):
        return _ejecutar("""UPDATE entrega SET cantidad_recibida = %s, novedad = %s, estado_entrega = %s,
                                              fecha_confirmacion = NOW(), idusuario_confirma = %s
                            WHERE code = %s AND estado_entrega = 'En tránsito'""",
                         (cantidad_recibida, novedad, estado_entrega, idusuario, code))

    @staticmethod
    def llegadas_pendientes():
        """Entregas En tránsito cuya hora programada ya llegó y que aún no tienen aviso al comprador."""
        return _consultar(DatosEntrega.SELECT_ENTREGA + """
            WHERE en.estado_entrega = 'En tránsito' AND en.estado = 'Activo' AND en.aviso_llegada IS NULL
              AND TIMESTAMP(en.fecha, en.hora) <= %s
        """, (datetime_ahora(),))

    @staticmethod
    def marcar_aviso(code):
        return _ejecutar("UPDATE entrega SET aviso_llegada = NOW() WHERE code = %s", (code,))


def datetime_ahora():
    from datetime import datetime
    return datetime.now().replace(microsecond=0)


# ---------------------------------------------------------------------
# Bitácora de mensajes de WhatsApp
# ---------------------------------------------------------------------
class DatosMensaje:

    @staticmethod
    def insertar(telefono, destinatario, tipo, referencia, texto, medio, resultado, detalle):
        return _ejecutar("""INSERT INTO mensaje (fecha_hora, telefono, destinatario, tipo, referencia, texto,
                                                 medio, resultado, detalle)
                            VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)""",
                         (telefono, destinatario, tipo, referencia, texto, medio, resultado, (detalle or "")[:255]))

    @staticmethod
    def listar(filtro=""):
        return _consultar("""SELECT idmensaje, CAST(fecha_hora AS CHAR) AS fecha_hora, telefono, destinatario, tipo,
                                    referencia, texto, medio, resultado, detalle
                             FROM mensaje
                             WHERE destinatario LIKE %s OR tipo LIKE %s OR referencia LIKE %s OR texto LIKE %s
                             ORDER BY idmensaje DESC""", (_filtro_texto(filtro),) * 4)

