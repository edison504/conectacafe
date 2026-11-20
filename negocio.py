import re
import secrets
from datetime import date, datetime
from functools import wraps

import mysql.connector

import correo
from conexion import ErrorConexion
from datos import (ESTADOS_ACTIVOS, DatosAcceso, DatosAsociacion, DatosCatalogo, DatosCooperativa, DatosEntrega,
                   DatosFinca, DatosListas, DatosLote, DatosMensaje, DatosNegocio, DatosPerfil, DatosPersona,
                   DatosProductor, DatosUbicacion, DatosUsuario, DatosVariedad)

ACTIVO, INACTIVO = "Activo", "Inactivo"
ACCIONES = ("Crear", "Consultar", "Modificar", "Guardar", "Inhabilitar", "Salir")

# Permisos según la tabla de requisitos funcionales del parcial.
TODAS = set(ACCIONES)
SOLO_CONSULTA = {"Consultar", "Salir"}

PERMISOS = {
    "Administrador": {
        "Perfil": TODAS,
        "Usuario": TODAS,
        "Persona": TODAS,
        # Parcial II
        "Productor": TODAS,
        "Finca": TODAS,
        "Cooperativa": TODAS,
        "Asociacion": TODAS,
        "Variedad": TODAS,
        # Final
        "Lote": TODAS,
        "Catalogo": TODAS,
        "Negocio": TODAS,
        "Mensaje": SOLO_CONSULTA,
    },
    # HU-01 y HU-02: el productor consulta y modifica sus propios datos, y gestiona sus fincas.
    "Productor": {
        "Productor": {"Consultar", "Modificar", "Salir"},
        "Finca": TODAS,
        "Variedad": SOLO_CONSULTA,
        "Lote": TODAS,                      # HU-06: Mi inventario
        "Negocio": SOLO_CONSULTA,           # HU-07: acepta o rechaza; HU-08: programa entregas
    },
    # HU-04: el comprador de una cooperativa solicita asociaciones (quedan pendientes).
    "Comprador": {
        "Cooperativa": SOLO_CONSULTA,
        "Asociacion": {"Crear", "Consultar", "Guardar", "Salir"},
        "Variedad": SOLO_CONSULTA,
        "Catalogo": SOLO_CONSULTA,          # HU-10
        "Negocio": TODAS,                   # HU-07 y HU-09
    },
    # Cualquier otro perfil (por ejemplo "Persona") solo gestiona sus propios datos.
    "Persona": {
        "Persona": {"Crear", "Consultar", "Modificar", "Guardar", "Salir"},
    },
    # Registro desde el botón "Registrarse" (todavía sin sesión).
    "Registro": {
        "Persona": {"Crear", "Guardar", "Salir"},
        "Usuario": {"Crear", "Guardar", "Salir"},
    },
}

CELULAR = re.compile(r"^3\d{9}$")
DOCUMENTO = re.compile(r"^\d{6,12}$")
NIT = re.compile(r"^\d{9,10}-\d$")
CODIGO = re.compile(r"^[A-Z0-9-]{2,15}$")
LETRAS = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+$")
CORREO_VALIDO = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
NOMBRE_USUARIO = re.compile(r"^[A-Za-z0-9._]{4,20}$")


def _ok(mensaje, datos=None):
    return {"exito": True, "mensaje": mensaje, "datos": datos}


def _error(mensaje):
    return {"exito": False, "mensaje": mensaje, "datos": None}


def controlar_errores_bd(funcion):
    """Convierte los errores de conexión o de MySQL en mensajes para el usuario."""
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except ErrorConexion as err:
            return _error(str(err))
        except mysql.connector.Error as err:
            return _error(f"Error en la base de datos: {err.msg}")
    return envoltura


def _texto(datos, campo):
    return (datos.get(campo) or "").strip()


def permisos_de(perfil):
    """Formularios y acciones permitidas para un perfil."""
    return PERMISOS.get(perfil, PERMISOS["Persona"])


def es_administrador(sesion):
    return bool(sesion) and sesion.get("perfil") == "Administrador"



class LogicaAcceso:

    @staticmethod
    @controlar_errores_bd
    def autenticar_usuario(usuario, contrasena):
        usuario, contrasena = (usuario or "").strip(), (contrasena or "").strip()
        if not usuario and not contrasena:
            return _error("Los campos de usuario y contraseña no pueden estar vacíos.")
        if not usuario:
            return _error("Digite su nombre de usuario.")
        if not contrasena:
            return _error("Digite su contraseña.")

        fila = DatosAcceso.buscar_usuario_login(usuario)
        if not fila:
            return _error("El usuario no se encuentra registrado.")
        if fila["contrasena"] != contrasena:
            return _error("La contraseña es incorrecta. Verifique e intente de nuevo.")
        if fila["estado"] != ACTIVO:
            return _error("Su usuario está inactivo. Comuníquese con el administrador.")
        if fila["estado_perfil"] != ACTIVO:
            return _error(f"El perfil '{fila['perfil']}' está inactivo. Comuníquese con el administrador.")
        if fila["estado_persona"] != ACTIVO:
            return _error("Los datos de la persona asociada están inactivos. Comuníquese con el administrador.")
        if fila["perfil"] == "Productor":
            if not fila["documento"]:
                return _error("Su usuario tiene perfil Productor, pero usted no está registrado como productor. "
                              "Comuníquese con el administrador.")
            if fila["estado_productor"] != ACTIVO:
                return _error("Su registro como productor está inactivo. Comuníquese con el administrador.")
        if fila["perfil"] == "Comprador":
            if not fila["nit"]:
                return _error("Su usuario tiene perfil Comprador, pero no está asociado a ninguna cooperativa. "
                              "Comuníquese con el administrador.")
            if fila["estado_cooperativa"] != ACTIVO:
                return _error(f"La cooperativa '{fila['cooperativa']}' está inactiva. Comuníquese con el administrador.")

        sesion = {
            "idusuario": fila["Idusuario"],
            "usuario": fila["nombreu"],
            "perfil": fila["perfil"],
            "idperfil": fila["idperfil"],
            "idpersona": fila["idpersona"],
            "nombre": f"{fila['nom1']} {fila['apell1']}",
            "documento": fila["documento"],
            "nit": fila["nit"],
            "cooperativa": fila["cooperativa"],
        }
        return _ok(f"Bienvenido(a), {sesion['nombre']}.", sesion)

    @staticmethod
    @controlar_errores_bd
    def procesar_recuperacion(dato):
        dato = (dato or "").strip()
        if not dato:
            return _error("Digite su usuario, correo electrónico o número de identificación.")

        fila = DatosAcceso.buscar_para_recuperacion(dato)
        if not fila:
            return _error("El usuario no se encuentra registrado")
        if fila["estado"] != ACTIVO:
            return _error("El usuario está inactivo. Comuníquese con el administrador.")
        if not fila["correo"]:
            return _error("Ese usuario no tiene un correo registrado. Comuníquese con el administrador.")

        enviado, motivo = correo.enviar_credenciales(
            fila["correo"], fila["nom1"], fila["nombreu"], fila["contrasena"])
        if not enviado:
            return _error(motivo)
        return _ok("Su usuario y contraseña fue enviado al correo registrado",
                   {"correo": LogicaAcceso.ocultar_correo(fila["correo"])})

    @staticmethod
    def ocultar_correo(direccion):
        """carlos@gmail.com -> c****s@gmail.com"""
        nombre, _, dominio = direccion.partition("@")
        if len(nombre) <= 2:
            return f"{nombre[0]}*@{dominio}"
        return f"{nombre[0]}{'*' * (len(nombre) - 2)}{nombre[-1]}@{dominio}"

    @staticmethod
    @controlar_errores_bd
    def resumen_panel():
        return _ok("", DatosAcceso.contar_activos())



class LogicaPerfil:
    entidad = "Perfil"

    @staticmethod
    def _validar(datos, id_registro=None):
        descripc = _texto(datos, "descripc")
        if not descripc:
            return _error("La descripción del perfil es obligatoria.")
        if not 3 <= len(descripc) <= 50:
            return _error("La descripción debe tener entre 3 y 50 caracteres.")
        if not LETRAS.match(descripc):
            return _error("La descripción solo puede contener letras y espacios.")
        if DatosPerfil.existe_descripcion(descripc, id_registro):
            return _error(f"Ya existe un perfil llamado '{descripc}'.")
        return _ok("", {"descripc": descripc.title() if descripc.islower() else descripc})

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        return _ok("", DatosPerfil.listar((filtro or "").strip()))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        validacion = LogicaPerfil._validar(datos)
        if not validacion["exito"]:
            return validacion
        nuevo_id = DatosPerfil.insertar(validacion["datos"])
        return _ok(f"Perfil guardado correctamente con ID {nuevo_id}.", nuevo_id)

    @staticmethod
    @controlar_errores_bd
    def modificar(id_registro, datos, sesion=None):
        validacion = LogicaPerfil._validar(datos, id_registro)
        if not validacion["exito"]:
            return validacion
        DatosPerfil.actualizar(id_registro, validacion["datos"])
        return _ok("Perfil modificado correctamente.", id_registro)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(id_registro, estado_actual, sesion=None):
        if estado_actual == ACTIVO:
            if sesion and sesion["idperfil"] == id_registro:
                return _error("No puede inhabilitar el perfil con el que inició sesión.")
            activos = DatosPerfil.usuarios_activos_con_perfil(id_registro)
            if activos:
                return _error(f"No se puede inhabilitar: hay {activos} usuario(s) activo(s) con este perfil.")
            DatosPerfil.cambiar_estado(id_registro, INACTIVO)
            return _ok("Perfil inhabilitado (borrado lógico). El registro sigue en la base de datos.")
        DatosPerfil.cambiar_estado(id_registro, ACTIVO)
        return _ok("Perfil activado nuevamente.")



class LogicaPersona:
    entidad = "Persona"

    @staticmethod
    def _validar(datos, id_registro=None):
        limpio = {campo: _texto(datos, campo) for campo in DatosPersona.CAMPOS}

        for campo, etiqueta in (("nom1", "primer nombre"), ("apell1", "primer apellido")):
            if not limpio[campo]:
                return _error(f"El {etiqueta} es obligatorio.")
        for campo, etiqueta in (("nom1", "primer nombre"), ("nom2", "segundo nombre"),
                                ("apell1", "primer apellido"), ("apell2", "segundo apellido")):
            valor = limpio[campo]
            if valor and not LETRAS.match(valor):
                return _error(f"El {etiqueta} solo puede contener letras.")
            if len(valor) > 50:
                return _error(f"El {etiqueta} no puede superar 50 caracteres.")

        if len(limpio["direccion"]) > 100:
            return _error("La dirección no puede superar 100 caracteres.")

        if limpio["tele"] and not re.fullmatch(r"\d{7,10}", limpio["tele"]):
            return _error("El teléfono fijo debe tener entre 7 y 10 números.")

        if not limpio["movil"]:
            return _error("El celular es obligatorio.")
        if not re.fullmatch(r"3\d{9}", limpio["movil"]):
            return _error("El celular debe tener 10 números y empezar por 3.")

        limpio["correo"] = limpio["correo"].lower()
        if not limpio["correo"]:
            return _error("El correo electrónico es obligatorio.")
        if not CORREO_VALIDO.match(limpio["correo"]):
            return _error("El correo electrónico no tiene un formato válido (ejemplo: nombre@correo.com).")
        if DatosPersona.existe_correo(limpio["correo"], id_registro):
            return _error("Ese correo ya está registrado para otra persona.")

        if limpio["fecha_nac"]:
            try:
                fecha = datetime.strptime(limpio["fecha_nac"], "%Y-%m-%d").date()
            except ValueError:
                return _error("La fecha de nacimiento debe tener el formato AAAA-MM-DD (ejemplo: 1995-08-21).")
            if fecha > date.today():
                return _error("La fecha de nacimiento no puede ser una fecha futura.")
            if fecha.year < 1900:
                return _error("La fecha de nacimiento no es válida.")

        for campo in ("nom2", "apell2", "direccion", "tele", "fecha_nac"):
            limpio[campo] = limpio[campo] or None
        for campo in ("nom1", "nom2", "apell1", "apell2"):
            if limpio[campo]:
                limpio[campo] = limpio[campo].title()
        return _ok("", limpio)

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        solo_id = None if (sesion is None or es_administrador(sesion)) else sesion["idpersona"]
        return _ok("", DatosPersona.listar((filtro or "").strip(), solo_id))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        validacion = LogicaPersona._validar(datos)
        if not validacion["exito"]:
            return validacion
        nuevo_id = DatosPersona.insertar(validacion["datos"])
        return _ok(f"Persona guardada correctamente con ID {nuevo_id}.", nuevo_id)

    @staticmethod
    @controlar_errores_bd
    def modificar(id_registro, datos, sesion=None):
        if sesion and not es_administrador(sesion) and sesion["idpersona"] != id_registro:
            return _error("Solo puede modificar sus propios datos.")
        validacion = LogicaPersona._validar(datos, id_registro)
        if not validacion["exito"]:
            return validacion
        DatosPersona.actualizar(id_registro, validacion["datos"])
        return _ok("Datos de la persona modificados correctamente.", id_registro)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(id_registro, estado_actual, sesion=None):
        if not es_administrador(sesion):
            return _error("Solo el administrador puede inhabilitar personas.")
        if estado_actual == ACTIVO:
            if sesion["idpersona"] == id_registro:
                return _error("No puede inhabilitar sus propios datos mientras está en sesión.")
            DatosPersona.cambiar_estado(id_registro, INACTIVO)
            return _ok("Persona inhabilitada (borrado lógico). El registro sigue en la base de datos.")
        DatosPersona.cambiar_estado(id_registro, ACTIVO)
        return _ok("Persona activada nuevamente.")



class LogicaUsuario:
    entidad = "Usuario"

    @staticmethod
    def _validar(datos, id_registro=None):
        nombreu = _texto(datos, "nombreu")
        contrasena = _texto(datos, "contrasena")
        idperfil, idpersona = datos.get("idperfil"), datos.get("idpersona")

        if not nombreu:
            return _error("El nombre de usuario es obligatorio.")
        if not NOMBRE_USUARIO.match(nombreu):
            return _error("El nombre de usuario debe tener de 4 a 20 caracteres, "
                          "sin espacios (solo letras, números, punto o guion bajo).")
        if DatosUsuario.existe_nombre(nombreu, id_registro):
            return _error(f"El nombre de usuario '{nombreu}' ya está en uso. Elija otro.")

        if not contrasena:
            return _error("La contraseña es obligatoria.")
        if len(contrasena) < 6 or not re.search(r"[A-Za-z]", contrasena) or not re.search(r"\d", contrasena):
            return _error("La contraseña debe tener mínimo 6 caracteres, con letras y números.")

        if not idperfil:
            return _error("Seleccione el perfil del usuario.")
        if not idpersona:
            return _error("Seleccione la persona a la que pertenece el usuario.")
        if DatosUsuario.persona_tiene_usuario(idpersona, id_registro):
            return _error("Esa persona ya tiene un usuario. Cada persona solo puede tener uno.")
        persona = DatosPersona.obtener(idpersona)
        if not persona or persona["estado"] != ACTIVO:
            return _error("La persona seleccionada no existe o está inactiva.")

        perfil = DatosPerfil.obtener(idperfil)
        nit = datos.get("nit")
        if perfil["descripc"] == "Comprador":
            if not nit:
                return _error("Un usuario con perfil Comprador debe representar a una cooperativa. Selecciónela.")
            cooperativa = DatosCooperativa.obtener(nit)
            if not cooperativa or cooperativa["estado"] != ACTIVO:
                return _error("La cooperativa seleccionada no existe o está inactiva.")
        elif nit:
            return _error("Solo los usuarios con perfil Comprador se asocian a una cooperativa. "
                          "Deje la cooperativa en (Ninguna).")
        if perfil["descripc"] == "Productor" and not DatosProductor.de_persona(idpersona):
            return _error("Para el perfil Productor, la persona debe estar registrada primero en Gestión Productores.")

        return _ok("", {"nombreu": nombreu, "contrasena": contrasena,
                        "idperfil": int(idperfil), "idpersona": int(idpersona), "nit": nit or None})

    @staticmethod
    @controlar_errores_bd
    def opciones_perfil():
        return _ok("", [(f["Idperfil"], f["descripc"]) for f in DatosPerfil.listar_activos()])

    @staticmethod
    @controlar_errores_bd
    def opciones_persona(incluir_id=None):
        filas = DatosPersona.listar_sin_usuario(incluir_id)
        return _ok("", [(f["Idpersona"], f"{f['nom1']} {f['apell1']} ({f['correo'] or 'sin correo'})")
                        for f in filas])

    @staticmethod
    @controlar_errores_bd
    def opciones_cooperativa():
        return _ok("", [(None, "(Ninguna)")] + [(f["nit"], f["nombre"]) for f in DatosCooperativa.listar_activas()])

    @staticmethod
    @controlar_errores_bd
    def id_perfil_registro():
        """Perfil que reciben quienes se registran solos (perfil 'Persona')."""
        perfil = DatosPerfil.buscar_por_descripcion("Persona")
        if not perfil or perfil["estado"] != ACTIVO:
            return _error("No existe un perfil 'Persona' activo para el registro. Avise al administrador.")
        return _ok("", perfil["Idperfil"])

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        return _ok("", DatosUsuario.listar((filtro or "").strip()))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        validacion = LogicaUsuario._validar(datos)
        if not validacion["exito"]:
            return validacion
        nuevo_id = DatosUsuario.insertar(validacion["datos"])
        return _ok(f"Usuario '{validacion['datos']['nombreu']}' guardado correctamente con ID {nuevo_id}.",
                   nuevo_id)

    @staticmethod
    @controlar_errores_bd
    def modificar(id_registro, datos, sesion=None):
        validacion = LogicaUsuario._validar(datos, id_registro)
        if not validacion["exito"]:
            return validacion
        DatosUsuario.actualizar(id_registro, validacion["datos"])
        return _ok("Usuario modificado correctamente.", id_registro)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(id_registro, estado_actual, sesion=None):
        if estado_actual == ACTIVO:
            if sesion and sesion["idusuario"] == id_registro:
                return _error("No puede inhabilitar su propio usuario mientras está en sesión.")
            DatosUsuario.cambiar_estado(id_registro, INACTIVO)
            return _ok("Usuario inhabilitado (borrado lógico). Ya no podrá ingresar al sistema.")
        DatosUsuario.cambiar_estado(id_registro, ACTIVO)
        return _ok("Usuario activado nuevamente.")


# =====================================================================
# PARCIAL II
# =====================================================================
def _solo_admin(sesion):
    return None if es_administrador(sesion) else _error("Esta acción solo la puede hacer el administrador.")


def _numero(texto, etiqueta):
    """Convierte '4,5' o '4.5' en número. Devuelve (valor, error)."""
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None, f"El campo {etiqueta} es obligatorio."
    try:
        return float(texto), None
    except ValueError:
        return None, f"El campo {etiqueta} debe ser un número (ejemplo: 4.5)."


def _edad(fecha_nac):
    hoy = date.today()
    return hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))


def _validar_nombres(limpio):
    for campo, etiqueta in (("nom1", "primer nombre"), ("apell1", "primer apellido")):
        if not limpio[campo]:
            return f"El {etiqueta} es obligatorio."
    for campo, etiqueta in (("nom1", "primer nombre"), ("nom2", "segundo nombre"),
                            ("apell1", "primer apellido"), ("apell2", "segundo apellido")):
        valor = limpio[campo]
        if valor and not LETRAS.match(valor):
            return f"El {etiqueta} solo puede contener letras."
        if len(valor) > 50:
            return f"El {etiqueta} no puede superar 50 caracteres."
    return None


class LogicaUbicacion:

    @staticmethod
    @controlar_errores_bd
    def departamentos():
        return _ok("", [(f["iddepartamento"], f["nombre"]) for f in DatosUbicacion.departamentos()])

    @staticmethod
    @controlar_errores_bd
    def municipios(iddepartamento):
        if not iddepartamento:
            return _ok("", [])
        return _ok("", [(f["idmunicipio"], f["nombre"]) for f in DatosUbicacion.municipios(iddepartamento)])


# ---------------------------------------------------------------------
# HU-01 · Gestión de Productores Cafeteros
# ---------------------------------------------------------------------
class LogicaProductor:
    entidad = "Productor"

    @staticmethod
    def _validar(datos, idpersona_actual=None):
        """idpersona_actual es None al crear; al modificar es la persona del productor."""
        limpio = {campo: _texto(datos, campo) for campo in
                  ("documento", "nom1", "nom2", "apell1", "apell2", "movil", "direccion", "fecha_nac", "correo")}

        if idpersona_actual is None:
            if not limpio["documento"]:
                return _error("El documento es obligatorio.")
            if not DOCUMENTO.match(limpio["documento"]):
                return _error("El documento debe tener solo números, entre 6 y 12 dígitos.")
            if DatosProductor.existe_documento(limpio["documento"]):
                return _error(f"Ya existe un productor con el documento {limpio['documento']}.")

        error = _validar_nombres(limpio)
        if error:
            return _error(error)

        if not limpio["movil"]:
            return _error("El teléfono es obligatorio.")
        if not CELULAR.match(limpio["movil"]):
            return _error("El teléfono debe ser un celular de 10 dígitos que empiece por 3 "
                          "(allí recibe las notificaciones por WhatsApp).")

        if not limpio["direccion"]:
            return _error("La dirección es obligatoria.")
        if len(limpio["direccion"]) > 100:
            return _error("La dirección no puede superar 100 caracteres.")

        if not limpio["fecha_nac"]:
            return _error("La fecha de nacimiento es obligatoria.")
        try:
            fecha = datetime.strptime(limpio["fecha_nac"], "%Y-%m-%d").date()
        except ValueError:
            return _error("La fecha de nacimiento debe tener el formato AAAA-MM-DD (ejemplo: 1985-03-14).")
        if fecha.year < 1900 or fecha > date.today():
            return _error("La fecha de nacimiento no es válida.")
        if _edad(fecha) < 18:
            return _error("El productor debe ser mayor de 18 años.")

        limpio["correo"] = limpio["correo"].lower()
        if limpio["correo"]:
            if not CORREO_VALIDO.match(limpio["correo"]):
                return _error("El correo electrónico no tiene un formato válido (ejemplo: nombre@correo.com).")
            if DatosProductor.existe_correo(limpio["correo"], idpersona_actual):
                return _error("Ese correo ya está registrado para otra persona.")

        for campo in ("nom2", "apell2", "correo"):
            limpio[campo] = limpio[campo] or None
        for campo in ("nom1", "nom2", "apell1", "apell2"):
            if limpio[campo]:
                limpio[campo] = limpio[campo].title()
        return _ok("", limpio)

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        # El productor solo ve sus propios datos; el administrador ve todos.
        solo = None if (sesion is None or es_administrador(sesion)) else (sesion.get("documento") or "-")
        return _ok("", DatosProductor.listar((filtro or "").strip(), solo))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        validacion = LogicaProductor._validar(datos)
        if not validacion["exito"]:
            return validacion
        documento = DatosProductor.insertar(validacion["datos"])
        return _ok(f"Productor con documento {documento} registrado con estado Activo.", documento)

    @staticmethod
    @controlar_errores_bd
    def modificar(documento, datos, sesion=None):
        productor = DatosProductor.obtener(documento)
        if not productor:
            return _error("El productor no existe.")
        if not es_administrador(sesion) and (sesion or {}).get("documento") != documento:
            return _error("Solo puede modificar sus propios datos.")
        # El documento es la llave primaria: no se modifica.
        validacion = LogicaProductor._validar(datos, productor["idpersona"])
        if not validacion["exito"]:
            return validacion
        DatosProductor.actualizar(productor["idpersona"], validacion["datos"])
        return _ok("Datos del productor modificados correctamente.", documento)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(documento, estado_actual, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        if estado_actual == ACTIVO:
            negocios = DatosNegocio.contar("('Aceptado', 'En entrega')", documento=documento)
            if negocios:
                return _error(f"No se puede inhabilitar: el productor tiene {negocios} negocio(s) "
                              "Aceptado(s) o En entrega.")
            DatosProductor.cambiar_estado(documento, INACTIVO)
            return _ok("Productor inhabilitado (borrado lógico). Sus lotes dejan de aparecer en el catálogo.")
        DatosProductor.cambiar_estado(documento, ACTIVO)
        return _ok("Productor activado nuevamente.")

    @staticmethod
    @controlar_errores_bd
    def cooperativas(documento):
        """HU-04: todas las cooperativas del productor con fecha de afiliación y estado."""
        return _ok("", DatosAsociacion.de_productor(documento))

    @staticmethod
    @controlar_errores_bd
    def opciones(solo_activos=True):
        filas = DatosProductor.listar_activos() if solo_activos else DatosProductor.listar_todos()
        return _ok("", [(f["documento"], f"{f['nombre']} ({f['documento']})") for f in filas])


# ---------------------------------------------------------------------
# HU-02 · Gestión de Fincas
# ---------------------------------------------------------------------
class LogicaFinca:
    entidad = "Finca"

    @staticmethod
    def _validar(datos, sesion, finca_actual=None):
        limpio = {campo: _texto(datos, campo) for campo in ("codigof", "nombre", "telefono", "direccion")}
        limpio["codigof"] = limpio["codigof"].upper()

        if finca_actual is None:
            if not limpio["codigof"]:
                return _error("El código de la finca es obligatorio.")
            if not CODIGO.match(limpio["codigof"]):
                return _error("El código debe tener de 2 a 15 caracteres: letras, números o guion (ejemplo: F-001).")
            if DatosFinca.obtener(limpio["codigof"]):
                return _error(f"Ya existe una finca con el código {limpio['codigof']}.")

        if not limpio["nombre"]:
            return _error("El nombre de la finca es obligatorio.")
        if len(limpio["nombre"]) > 80:
            return _error("El nombre no puede superar 80 caracteres.")

        area, error = _numero(datos.get("area"), "área")
        if error:
            return _error(error)
        if area <= 0 or area > 99999999:
            return _error("El área se registra en hectáreas y debe ser mayor que cero.")

        temperatura, error = _numero(datos.get("temperatura"), "temperatura")
        if error:
            return _error(error)
        if not 5 <= temperatura <= 35:
            return _error("La temperatura promedio debe estar entre 5 °C y 35 °C.")

        if not limpio["telefono"]:
            return _error("El teléfono de la finca es obligatorio.")
        if not re.fullmatch(r"\d{10}", limpio["telefono"]):
            return _error("El teléfono de la finca debe tener 10 dígitos.")

        if not limpio["direccion"]:
            return _error("La dirección de la finca es obligatoria.")
        if len(limpio["direccion"]) > 120:
            return _error("La dirección no puede superar 120 caracteres.")

        iddepartamento, idmunicipio = datos.get("iddepartamento"), datos.get("idmunicipio")
        if not iddepartamento:
            return _error("Seleccione el departamento.")
        if not idmunicipio:
            return _error("Seleccione el municipio.")
        municipio = DatosUbicacion.municipio(idmunicipio)
        if not municipio or municipio["iddepartamento"] != int(iddepartamento):
            return _error("El municipio no pertenece al departamento seleccionado.")

        # La finca queda asociada al documento del productor.
        if es_administrador(sesion):
            documento = datos.get("documento")
            if not documento:
                return _error("Seleccione el productor dueño de la finca.")
        else:
            documento = (sesion or {}).get("documento")
            if not documento:
                return _error("Solo los productores pueden registrar sus fincas.")
        if finca_actual is None or finca_actual["documento"] != documento:
            productor = DatosProductor.obtener(documento)
            if not productor or productor["estado"] != ACTIVO:
                return _error("El productor seleccionado no existe o está inactivo.")

        limpio.update(area=round(area, 2), temperatura=round(temperatura, 1),
                      idmunicipio=int(idmunicipio), documento=documento)
        if finca_actual is not None:
            limpio["codigof"] = finca_actual["codigof"]
        return _ok("", limpio)

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        filtros = filtros or {}
        if es_administrador(sesion):
            # El administrador ve todas y filtra por departamento, municipio y productor.
            filas = DatosFinca.listar((filtro or "").strip(), iddepartamento=filtros.get("iddepartamento"),
                                      idmunicipio=filtros.get("idmunicipio"), documento=filtros.get("documento"))
        else:
            # "Mis fincas": el productor ve solo las suyas.
            filas = DatosFinca.listar((filtro or "").strip(), solo_documento=(sesion or {}).get("documento") or "-")
        return _ok("", filas)

    @staticmethod
    def _es_dueno(finca, sesion):
        return es_administrador(sesion) or (sesion or {}).get("documento") == finca["documento"]

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        validacion = LogicaFinca._validar(datos, sesion)
        if not validacion["exito"]:
            return validacion
        codigo = DatosFinca.insertar(validacion["datos"])
        return _ok(f"Finca {codigo} registrada con estado Activo.", codigo)

    @staticmethod
    @controlar_errores_bd
    def modificar(codigof, datos, sesion=None):
        finca = DatosFinca.obtener(codigof)
        if not finca:
            return _error("La finca no existe.")
        if not LogicaFinca._es_dueno(finca, sesion):
            return _error("Solo puede modificar sus propias fincas.")
        # Se modifican todos los datos menos el codigof.
        validacion = LogicaFinca._validar(datos, sesion, finca)
        if not validacion["exito"]:
            return validacion
        DatosFinca.actualizar(codigof, validacion["datos"])
        return _ok("Finca modificada correctamente.", codigof)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(codigof, estado_actual, sesion=None):
        finca = DatosFinca.obtener(codigof)
        if not finca or not LogicaFinca._es_dueno(finca, sesion):
            return _error("Solo puede inhabilitar sus propias fincas.")
        if estado_actual == ACTIVO:
            ocupada = DatosLote.finca_ocupada(codigof)
            if ocupada["disponibles"] or ocupada["en_negocios"]:
                return _error("No se puede inhabilitar: la finca tiene lotes de café disponibles o "
                              "comprometidos en negocios activos.")
            DatosFinca.cambiar_estado(codigof, INACTIVO)
            return _ok("Finca inhabilitada (borrado lógico). El registro sigue en la base de datos.")
        DatosFinca.cambiar_estado(codigof, ACTIVO)
        return _ok("Finca activada nuevamente.")


# ---------------------------------------------------------------------
# HU-03 · Gestión de Cooperativas
# ---------------------------------------------------------------------
class LogicaCooperativa:
    entidad = "Cooperativa"

    @staticmethod
    def _validar(datos, nit_actual=None):
        limpio = {campo: _texto(datos, campo) for campo in DatosCooperativa.CAMPOS}

        if nit_actual is None:
            if not limpio["nit"]:
                return _error("El NIT es obligatorio.")
            if not NIT.match(limpio["nit"]):
                return _error("El NIT debe llevar el dígito de verificación separado por guion "
                              "(ejemplo: 900123456-7).")
            if DatosCooperativa.existe("nit", limpio["nit"]):
                return _error(f"Ya existe una cooperativa con el NIT {limpio['nit']}.")
        else:
            limpio["nit"] = nit_actual

        if not limpio["nombre"]:
            return _error("El nombre de la cooperativa es obligatorio.")
        if len(limpio["nombre"]) > 100:
            return _error("El nombre no puede superar 100 caracteres.")
        if DatosCooperativa.existe("nombre", limpio["nombre"], nit_actual):
            return _error("Ya existe una cooperativa con ese nombre.")

        if not limpio["direccion"]:
            return _error("La dirección es obligatoria.")
        if len(limpio["direccion"]) > 120:
            return _error("La dirección no puede superar 120 caracteres.")

        if not limpio["telefono"]:
            return _error("El teléfono es obligatorio.")
        if not CELULAR.match(limpio["telefono"]):
            return _error("El teléfono debe ser un celular de 10 dígitos que empiece por 3 "
                          "(allí la cooperativa recibe los avisos de entrega por WhatsApp).")

        limpio["correo"] = limpio["correo"].lower()
        if not limpio["correo"]:
            return _error("El correo electrónico es obligatorio.")
        if not CORREO_VALIDO.match(limpio["correo"]):
            return _error("El correo electrónico no tiene un formato válido (ejemplo: contacto@cooperativa.co).")
        if DatosCooperativa.existe("correo", limpio["correo"], nit_actual):
            return _error("Ya existe una cooperativa con ese correo.")
        return _ok("", limpio)

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        # El comprador solo ve su propia cooperativa.
        solo = None if (sesion is None or es_administrador(sesion)) else ((sesion or {}).get("nit") or "-")
        return _ok("", DatosCooperativa.listar((filtro or "").strip(), solo))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        validacion = LogicaCooperativa._validar(datos)
        if not validacion["exito"]:
            return validacion
        nit = DatosCooperativa.insertar(validacion["datos"])
        return _ok(f"Cooperativa {nit} registrada con estado Activo.", nit)

    @staticmethod
    @controlar_errores_bd
    def modificar(nit, datos, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        # Se modifican todos los datos menos el NIT, que es la llave primaria.
        validacion = LogicaCooperativa._validar(datos, nit)
        if not validacion["exito"]:
            return validacion
        DatosCooperativa.actualizar(nit, validacion["datos"])
        return _ok("Cooperativa modificada correctamente.", nit)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(nit, estado_actual, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        if estado_actual == ACTIVO:
            negocios = DatosNegocio.contar("('Aceptado', 'En entrega')", nit=nit)
            if negocios:
                return _error(f"No se puede inhabilitar: la cooperativa tiene {negocios} negocio(s) "
                              "Aceptado(s) o En entrega.")
            DatosCooperativa.cambiar_estado(nit, INACTIVO)
            return _ok("Cooperativa inhabilitada (borrado lógico). El registro sigue en la base de datos.")
        DatosCooperativa.cambiar_estado(nit, ACTIVO)
        return _ok("Cooperativa activada nuevamente.")

    @staticmethod
    @controlar_errores_bd
    def detalle(nit, sesion=None):
        """Sus productores asociados y sus usuarios compradores."""
        if not es_administrador(sesion) and (sesion or {}).get("nit") != nit:
            return _error("Solo puede consultar el detalle de su propia cooperativa.")
        return _ok("", {"productores": DatosCooperativa.productores_asociados(nit),
                        "compradores": DatosCooperativa.usuarios_compradores(nit)})

    @staticmethod
    @controlar_errores_bd
    def opciones(sesion=None):
        filas = DatosCooperativa.listar_activas()
        if sesion and not es_administrador(sesion):
            filas = [f for f in filas if f["nit"] == sesion.get("nit")]
        return _ok("", [(f["nit"], f["nombre"]) for f in filas])


# ---------------------------------------------------------------------
# HU-04 · Asociación de Productores a Cooperativas
# ---------------------------------------------------------------------
class LogicaAsociacion:
    entidad = "Asociacion"

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        solo = None if (sesion is None or es_administrador(sesion)) else ((sesion or {}).get("nit") or "-")
        return _ok("", DatosAsociacion.listar((filtro or "").strip(), solo_nit=solo))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        documento, nit = datos.get("documento"), datos.get("nit")
        if not documento:
            return _error("Seleccione el productor.")
        if not nit:
            return _error("Seleccione la cooperativa.")
        productor = DatosProductor.obtener(documento)
        if not productor or productor["estado"] != ACTIVO:
            return _error("El productor debe existir y estar activo.")
        cooperativa = DatosCooperativa.obtener(nit)
        if not cooperativa or cooperativa["estado"] != ACTIVO:
            return _error("La cooperativa debe existir y estar activa.")
        vigente = DatosAsociacion.vigente(documento, nit)
        if vigente:
            if vigente["estado"] == "Pendiente":
                return _error("Ya hay una solicitud pendiente de asociación entre ese productor y esa cooperativa.")
            return _error("El productor ya está asociado a esa cooperativa. No se puede asociar dos veces.")

        if es_administrador(sesion):
            nuevo_id = DatosAsociacion.insertar(documento, nit, "Activo", sesion["idusuario"])
            return _ok(f"Asociación registrada con fecha de afiliación de hoy y estado Activo (ID {nuevo_id}).",
                       nuevo_id)
        if (sesion or {}).get("perfil") == "Comprador":
            if sesion.get("nit") != nit:
                return _error("Solo puede solicitar asociaciones a su propia cooperativa.")
            nuevo_id = DatosAsociacion.insertar(documento, nit, "Pendiente", sesion["idusuario"])
            return _ok("Solicitud registrada. Queda Pendiente hasta que el administrador la apruebe.", nuevo_id)
        return _error("No tiene permiso para asociar productores.")

    @staticmethod
    @controlar_errores_bd
    def modificar(idasociacion, datos, sesion=None):
        return _error("Las asociaciones no se modifican. Para cambiarla, desasocie y cree una nueva: "
                      "así se conserva el historial.")

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(idasociacion, estado_actual, sesion=None):
        """Desasociar es un borrado lógico: pasa a Inactivo con fecha de retiro."""
        error = _solo_admin(sesion)
        if error:
            return error
        if estado_actual == ACTIVO:
            DatosAsociacion.desasociar(idasociacion)
            return _ok("Productor desasociado. La asociación queda Inactiva con la fecha de retiro de hoy; "
                       "el historial y los negocios anteriores se conservan.")
        if estado_actual == "Pendiente":
            return _error("Esta solicitud está pendiente: use Aprobar o Rechazar.")
        return _error("Esta asociación ya terminó. Para volver a asociarlo, cree una nueva asociación; "
                      "el historial se conserva.")

    @staticmethod
    @controlar_errores_bd
    def aprobar(idasociacion, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        asociacion = DatosAsociacion.obtener(idasociacion)
        if not asociacion or asociacion["estado"] != "Pendiente":
            return _error("Solo se pueden aprobar solicitudes en estado Pendiente.")
        productor = DatosProductor.obtener(asociacion["documento"])
        cooperativa = DatosCooperativa.obtener(asociacion["nit"])
        if productor["estado"] != ACTIVO or cooperativa["estado"] != ACTIVO:
            return _error("No se puede aprobar: el productor o la cooperativa están inactivos.")
        DatosAsociacion.aprobar(idasociacion)
        return _ok("Solicitud aprobada. La asociación queda Activa con la fecha de afiliación de hoy.")

    @staticmethod
    @controlar_errores_bd
    def rechazar(idasociacion, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        asociacion = DatosAsociacion.obtener(idasociacion)
        if not asociacion or asociacion["estado"] != "Pendiente":
            return _error("Solo se pueden rechazar solicitudes en estado Pendiente.")
        DatosAsociacion.rechazar(idasociacion)
        return _ok("Solicitud rechazada.")


# ---------------------------------------------------------------------
# HU-05 · Gestión de Tipos de Variedades
# ---------------------------------------------------------------------
TAMANO_MAXIMO_IMAGEN = 2 * 1024 * 1024  # 2 MB


def tipo_imagen(contenido):
    """Reconoce JPG o PNG por su contenido (no por el nombre del archivo)."""
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if contenido.startswith(b"\xff\xd8\xff"):
        return "JPG"
    return None


class LogicaVariedad:
    entidad = "Variedad"

    @staticmethod
    def _validar(datos, codigo_actual=None):
        codigotv = _texto(datos, "codigotv").upper()
        descripcion = " ".join(_texto(datos, "descripcion").split())
        imagen = datos.get("imagen")

        if codigo_actual is None:
            if not codigotv:
                return _error("El código de la variedad es obligatorio.")
            if not re.fullmatch(r"[A-Z0-9-]{1,10}", codigotv):
                return _error("El código debe tener máximo 10 caracteres: letras, números o guion (ejemplo: CAS).")
            if DatosVariedad.existe("codigotv", codigotv):
                return _error(f"Ya existe una variedad con el código {codigotv}.")
        else:
            codigotv = codigo_actual

        if not descripcion:
            return _error("La descripción es obligatoria.")
        if len(descripcion) > 50 or not LETRAS.match(descripcion):
            return _error("La descripción solo puede tener letras y espacios (máximo 50).")
        if DatosVariedad.existe("descripcion", descripcion, codigo_actual):
            return _error(f"Ya existe una variedad llamada '{descripcion}'.")
        descripcion = descripcion[0].upper() + descripcion[1:]

        tipo = None
        if imagen is None:
            if codigo_actual is None:
                return _error("La imagen es obligatoria. Elija un archivo JPG o PNG.")
        else:
            tipo = tipo_imagen(imagen)
            if not tipo:
                return _error("La imagen debe ser un archivo JPG o PNG.")
            if len(imagen) > TAMANO_MAXIMO_IMAGEN:
                return _error(f"La imagen pesa {len(imagen) / 1024 / 1024:.1f} MB. El máximo es 2 MB.")

        return _ok("", {"codigotv": codigotv, "descripcion": descripcion, "imagen": imagen, "imagen_tipo": tipo})

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        # Productores y compradores solo ven las variedades activas, en orden alfabético.
        solo_activas = not es_administrador(sesion)
        return _ok("", DatosVariedad.listar((filtro or "").strip(), solo_activas))

    @staticmethod
    @controlar_errores_bd
    def imagen(codigotv):
        return _ok("", DatosVariedad.imagen(codigotv))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        validacion = LogicaVariedad._validar(datos)
        if not validacion["exito"]:
            return validacion
        codigo = DatosVariedad.insertar(validacion["datos"])
        return _ok(f"Variedad {codigo} registrada con estado Activo.", codigo)

    @staticmethod
    @controlar_errores_bd
    def modificar(codigotv, datos, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        # El codigotv no se modifica; la descripción y la imagen sí.
        validacion = LogicaVariedad._validar(datos, codigotv)
        if not validacion["exito"]:
            return validacion
        DatosVariedad.actualizar(codigotv, validacion["datos"])
        return _ok("Variedad modificada correctamente.", codigotv)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(codigotv, estado_actual, sesion=None):
        error = _solo_admin(sesion)
        if error:
            return error
        if estado_actual == ACTIVO:
            DatosVariedad.cambiar_estado(codigotv, INACTIVO)
            return _ok("Variedad inhabilitada (borrado lógico). Ya no aparece para productores y compradores.")
        DatosVariedad.cambiar_estado(codigotv, ACTIVO)
        return _ok("Variedad activada nuevamente.")


# =====================================================================
# FINAL
# =====================================================================
import whatsapp  # noqa: E402  (se importa aquí para que el Parcial II no dependa de él)

ESTADOS_NEGOCIO = ("Propuesto", "Aceptado", "Rechazado", "En entrega", "Completado", "Cancelado")


def _entero(texto, etiqueta):
    texto = str(texto if texto is not None else "").strip()
    if not texto:
        return None, f"El campo {etiqueta} es obligatorio."
    if not re.fullmatch(r"\d+", texto):
        return None, f"El campo {etiqueta} debe ser un número entero (sin decimales)."
    return int(texto), None


def _token():
    return secrets.token_urlsafe(16)


def _es(sesion, perfil):
    return bool(sesion) and sesion.get("perfil") == perfil


def puede_ver_negocio(negocio, sesion):
    if es_administrador(sesion):
        return True
    if _es(sesion, "Comprador"):
        return negocio["nit"] == sesion.get("nit")
    if _es(sesion, "Productor"):
        return negocio["documento"] == sesion.get("documento")
    return False


class LogicaListas:

    @staticmethod
    @controlar_errores_bd
    def empaques():
        return _ok("", [(f["idempaque"], f["descripcion"]) for f in DatosListas.empaques()])

    @staticmethod
    @controlar_errores_bd
    def medios_pago():
        return _ok("", [(f["idmedio"], f["descripcion"]) for f in DatosListas.medios_pago()])


# ---------------------------------------------------------------------
# HU-06 · Gestión de Inventario y Catálogo de Café
# ---------------------------------------------------------------------
class LogicaLote:
    entidad = "Lote"

    @staticmethod
    def _es_dueno(lote, sesion):
        return es_administrador(sesion) or (sesion or {}).get("documento") == lote["documento"]

    @staticmethod
    def _validar(datos, sesion, lote_actual=None):
        codigoc = _texto(datos, "codigoc").upper()
        descripcion = " ".join(_texto(datos, "descripcion").split())

        if lote_actual is None:
            if not codigoc:
                return _error("El código del lote es obligatorio.")
            if not CODIGO.match(codigoc):
                return _error("El código debe tener de 2 a 15 caracteres: letras, números o guion (ejemplo: L-001).")
            if DatosLote.obtener(codigoc):
                return _error(f"Ya existe un lote con el código {codigoc}.")
        else:
            codigoc = lote_actual["codigoc"]

        if len(descripcion) < 10:
            return _error("Describa el tipo de café y sus datos de calidad "
                          "(ejemplo: pergamino seco, factor 92, cosecha 2026).")
        if len(descripcion) > 200:
            return _error("La descripción no puede superar 200 caracteres.")

        # Finca: debe ser del productor y estar activa.
        codigof = datos.get("codigof")
        if not codigof:
            return _error("Seleccione la finca del lote.")
        finca = DatosFinca.obtener(codigof)
        if not finca:
            return _error("La finca seleccionada no existe.")
        if not es_administrador(sesion) and finca["documento"] != (sesion or {}).get("documento"):
            return _error("Solo puede registrar lotes en sus propias fincas.")
        if (lote_actual is None or lote_actual["codigof"] != codigof) and finca["estado"] != ACTIVO:
            return _error("La finca seleccionada está inactiva.")

        codigotv = datos.get("codigotv")
        if not codigotv:
            return _error("Seleccione la variedad del café.")
        activas = {v["codigotv"] for v in DatosVariedad.listar("", solo_activas=True)}
        if (lote_actual is None or lote_actual["codigotv"] != codigotv) and codigotv not in activas:
            return _error("La variedad seleccionada no existe o está inactiva.")

        idempaque = datos.get("idempaque")
        if not idempaque:
            return _error("Seleccione el tipo de empaque.")

        peso, error = _numero(datos.get("peso"), "peso por empaque")
        if error:
            return _error(error)
        if peso <= 0 or peso > 999999:
            return _error("El peso es el peso de cada empaque en kg y debe ser mayor que cero.")

        cantidad, error = _entero(datos.get("cantidad"), "cantidad de empaques")
        if error:
            return _error(error)
        if cantidad <= 0:
            return _error("La cantidad es el número de empaques y debe ser un entero mayor que cero.")

        precio, error = _numero(datos.get("precio"), "precio por kg")
        if error:
            return _error(error)
        if precio <= 0:
            return _error("El precio de compra por kg debe ser mayor que cero.")

        imagen, tipo = datos.get("imagen"), None
        if imagen is None:
            if lote_actual is None:
                return _error("La imagen del lote es obligatoria. Elija un archivo JPG o PNG.")
        else:
            tipo = tipo_imagen(imagen)
            if not tipo:
                return _error("La imagen debe ser un archivo JPG o PNG.")
            if len(imagen) > TAMANO_MAXIMO_IMAGEN:
                return _error(f"La imagen pesa {len(imagen) / 1024 / 1024:.1f} MB. El máximo es 2 MB.")

        if lote_actual is not None:
            comprometida = int(lote_actual["comprometida"])
            if cantidad < comprometida:
                return _error(f"No se puede reducir la cantidad a {cantidad}: ya hay {comprometida} empaque(s) "
                              "comprometidos en negocios aceptados.")
            cambia_peso = round(float(lote_actual["peso"]), 2) != round(peso, 2)
            cambia_empaque = int(lote_actual["idempaque"]) != int(idempaque)
            if (cambia_peso or cambia_empaque) and DatosLote.tiene_negocios(codigoc):
                return _error("No se puede cambiar el peso ni el empaque de un lote que ya tiene negocios.")

        return _ok("", {"codigoc": codigoc, "descripcion": descripcion, "codigof": codigof, "codigotv": codigotv,
                        "idempaque": int(idempaque), "peso": round(peso, 2), "cantidad": cantidad,
                        "precio": round(precio, 2), "imagen": imagen, "imagen_tipo": tipo})

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        # "Mi inventario": el productor ve solo sus lotes; el administrador ve todos.
        solo = None if es_administrador(sesion) else ((sesion or {}).get("documento") or "-")
        filas = DatosLote.listar((filtro or "").strip(), solo)
        for fila in filas:
            fila["comprometida"] = int(fila["comprometida"])
            fila["disponible"] = int(fila["disponible"])
        return _ok("", filas)

    @staticmethod
    @controlar_errores_bd
    def imagen(codigoc):
        return _ok("", DatosLote.imagen(codigoc))

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        if not (es_administrador(sesion) or _es(sesion, "Productor")):
            return _error("Solo los productores registran lotes de café.")
        validacion = LogicaLote._validar(datos, sesion)
        if not validacion["exito"]:
            return validacion
        codigo = DatosLote.insertar(validacion["datos"])
        return _ok(f"Lote {codigo} registrado con estado Activo.", codigo)

    @staticmethod
    @controlar_errores_bd
    def modificar(codigoc, datos, sesion=None):
        lote = DatosLote.obtener(codigoc)
        if not lote:
            return _error("El lote no existe.")
        if not LogicaLote._es_dueno(lote, sesion):
            return _error("Solo puede modificar sus propios lotes.")
        validacion = LogicaLote._validar(datos, sesion, lote)
        if not validacion["exito"]:
            return validacion
        DatosLote.actualizar(codigoc, validacion["datos"])
        mensaje = "Lote modificado correctamente."
        if round(float(lote["precio"]), 2) != validacion["datos"]["precio"]:
            mensaje += " El nuevo precio aplica solo a los negocios nuevos."
        return _ok(mensaje, codigoc)

    @staticmethod
    @controlar_errores_bd
    def cambiar_estado(codigoc, estado_actual, sesion=None):
        lote = DatosLote.obtener(codigoc)
        if not lote or not LogicaLote._es_dueno(lote, sesion):
            return _error("Solo puede inhabilitar sus propios lotes.")
        if estado_actual == ACTIVO:
            DatosLote.cambiar_estado(codigoc, INACTIVO)
            return _ok("Lote inhabilitado (borrado lógico). Ya no aparece en el listado de disponibles, "
                       "pero se conserva en los negocios anteriores.")
        DatosLote.cambiar_estado(codigoc, ACTIVO)
        return _ok("Lote activado nuevamente.")

    @staticmethod
    @controlar_errores_bd
    def opciones_finca(sesion, codigo_lote=None):
        filas = DatosFinca.listar("", solo_documento=None if es_administrador(sesion) else
                                  ((sesion or {}).get("documento") or "-"))
        actual = None
        if codigo_lote:
            lote = DatosLote.obtener(codigo_lote)
            actual = lote["codigof"] if lote else None
        return _ok("", [(f["codigof"], f"{f['nombre']} ({f['codigof']})" +
                         ("" if es_administrador(sesion) is False else f" · {f['productor']}"))
                        for f in filas if f["estado"] == ACTIVO or f["codigof"] == actual])

    @staticmethod
    @controlar_errores_bd
    def opciones_variedad(codigo_lote=None):
        filas = DatosVariedad.listar("")
        actual = None
        if codigo_lote:
            lote = DatosLote.obtener(codigo_lote)
            actual = lote["codigotv"] if lote else None
        return _ok("", [(f["codigotv"], f["descripcion"]) for f in filas
                        if f["estado"] == ACTIVO or f["codigotv"] == actual])


# ---------------------------------------------------------------------
# HU-10 · Listado detallado de lotes disponibles
# ---------------------------------------------------------------------
class LogicaCatalogo:

    @staticmethod
    @controlar_errores_bd
    def listar(sesion, texto="", codigotv=None, iddepartamento=None, idmunicipio=None, nit=None,
               precio_min="", precio_max="", orden="fecha", descendente=True, incluir_todos=False):
        if not (es_administrador(sesion) or _es(sesion, "Comprador")):
            return _error("El listado de lotes es para compradores y el administrador.")
        minimo = maximo = None
        if str(precio_min).strip():
            minimo, error = _numero(precio_min, "precio mínimo")
            if error:
                return _error(error)
        if str(precio_max).strip():
            maximo, error = _numero(precio_max, "precio máximo")
            if error:
                return _error(error)
        if minimo is not None and maximo is not None and minimo > maximo:
            return _error("El precio mínimo no puede ser mayor que el precio máximo.")
        filas = DatosCatalogo.listar(
            texto=(texto or "").strip(), nit_comprador=(sesion or {}).get("nit"),
            incluir_todos=bool(incluir_todos) and es_administrador(sesion), codigotv=codigotv,
            iddepartamento=iddepartamento, idmunicipio=idmunicipio, nit=nit, precio_min=minimo,
            precio_max=maximo, orden=orden, descendente=descendente)
        totales = {}
        for fila in filas:
            fila["disponible"] = int(fila["disponible"])
            fila["kg_disponibles"] = round(float(fila["kg_disponibles"]), 2)
            fila["asociado"] = bool(fila["asociado"])
            if fila["disponible"] > 0 and fila["estado"] == ACTIVO:
                totales[fila["variedad"]] = totales.get(fila["variedad"], 0) + fila["kg_disponibles"]
        return _ok("", {"filas": filas, "totales": dict(sorted(totales.items()))})

    @staticmethod
    @controlar_errores_bd
    def opciones_variedad():
        return _ok("", [(f["codigotv"], f["descripcion"]) for f in DatosVariedad.listar("", solo_activas=True)])


# ---------------------------------------------------------------------
# HU-07 · Gestión de Emparejamiento Comercial con Detalle
# ---------------------------------------------------------------------
class LogicaNegocio:

    @staticmethod
    def _validar(datos, sesion):
        """Valida el negocio y calcula subtotales y total. Devuelve cabecera y líneas listas para guardar."""
        documento = datos.get("documento")
        if not documento:
            return _error("Seleccione el productor.")
        productor = DatosProductor.obtener(documento)
        if not productor or productor["estado"] != ACTIVO:
            return _error("El productor no existe o está inactivo.")

        medios = dict((i, d) for i, d in ((f["idmedio"], f["descripcion"]) for f in DatosListas.medios_pago()))
        idmedio = datos.get("idmedio")
        if not idmedio or int(idmedio) not in medios:
            return _error("Seleccione el medio de pago de la lista.")

        descripcion = " ".join(_texto(datos, "descripcion").split())
        if len(descripcion) > 250:
            return _error("La descripción no puede superar 250 caracteres.")

        lineas = datos.get("lineas") or []
        if not lineas:
            return _error("Agregue al menos un lote al detalle del negocio.")
        vistos, listas, total = set(), [], 0.0
        for linea in lineas:
            codigoc = (linea.get("codigoc") or "").upper()
            if codigoc in vistos:
                return _error(f"El lote {codigoc} está repetido: un lote no puede ir en dos líneas.")
            vistos.add(codigoc)
            lote = DatosLote.obtener(codigoc)
            if not lote:
                return _error(f"El lote {codigoc} no existe.")
            if lote["documento"] != documento:
                return _error("Todos los lotes del negocio deben ser del mismo productor.")
            if lote["estado"] != ACTIVO or lote["estado_finca"] != ACTIVO:
                return _error(f"El lote {codigoc} no está disponible (lote o finca inactivos).")
            cantidad, error = _entero(linea.get("cantidad"), f"cantidad del lote {codigoc}")
            if error:
                return _error(error)
            if cantidad <= 0:
                return _error(f"La cantidad del lote {codigoc} debe ser mayor que cero.")
            disponible = int(lote["cantidad"]) - int(lote["comprometida"])
            if cantidad > disponible:
                return _error(f"El lote {codigoc} solo tiene {disponible} empaque(s) disponible(s).")
            precio, error = _numero(str(linea.get("precio_kg")), f"precio por kg del lote {codigoc}")
            if error:
                return _error(error)
            if precio <= 0:
                return _error(f"El precio por kg del lote {codigoc} debe ser mayor que cero.")
            peso = float(lote["peso"])
            # Subtotal = cantidad × peso por empaque × precio por kg (lo calcula el sistema).
            subtotal = round(cantidad * peso * precio, 2)
            total += subtotal
            listas.append({"codigoc": codigoc, "cantidad": cantidad, "peso": peso, "precio_kg": round(precio, 2),
                           "subtotal": subtotal, "lote": lote["descripcion"], "variedad": lote["variedad"],
                           "empaque": lote["empaque"]})
        cabecera = {"documento": documento, "idmedio": int(idmedio), "medio": medios[int(idmedio)],
                    "descripcion": descripcion or None, "valor_total": round(total, 2)}
        return _ok("", {"cabecera": cabecera, "lineas": listas})

    @staticmethod
    def _notificar_productor(idnegocio, modificado=False):
        negocio = DatosNegocio.obtener(idnegocio)
        lineas = DatosNegocio.detalle(idnegocio)
        detalle = "\n".join(
            f"• {l['codigoc']} {l['variedad']}: {l['cantidad']} {l['empaque'].lower()} de {float(l['peso']):g} kg "
            f"a {whatsapp.pesos(l['precio_kg'])}/kg = {whatsapp.pesos(l['subtotal'])}" for l in lineas)
        titulo = "modificó el negocio" if modificado else "le propone un negocio"
        texto = (f"☕ Café Conecta\nHola {negocio['productor']}, la {negocio['cooperativa']} {titulo} "
                 f"{negocio['codigoe']}:\n{detalle}\nValor total: {whatsapp.pesos(negocio['valor_total'])}\n"
                 f"Medio de pago: {negocio['medio_pago']}\n"
                 f"Para aceptar o rechazar: {whatsapp.enlace('n', negocio['token'])}\n"
                 f"(o ingrese a Café Conecta › Negocios › {negocio['codigoe']})")
        return whatsapp.enviar(negocio["telefono_productor"], negocio["productor"],
                               "Negocio modificado" if modificado else "Negocio propuesto", negocio["codigoe"], texto)

    @staticmethod
    def _notificar_cooperativa(negocio, texto, tipo):
        return whatsapp.enviar(negocio["telefono_cooperativa"], negocio["cooperativa"], tipo, negocio["codigoe"],
                               "☕ Café Conecta\n" + texto)

    @staticmethod
    def _texto_resultado_envio(resultado):
        estado, detalle = resultado
        if estado == "Error":
            return f"\n\nAviso de WhatsApp no enviado: {detalle}"
        return f"\n\nWhatsApp: {detalle}"

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None):
        if es_administrador(sesion):
            filas = DatosNegocio.listar(filtro)
        elif _es(sesion, "Comprador"):
            filas = DatosNegocio.listar(filtro, nit=sesion.get("nit"))       # "Mis negocios"
        elif _es(sesion, "Productor"):
            filas = DatosNegocio.listar(filtro, documento=sesion.get("documento"))  # los que le proponen
        else:
            filas = []
        return _ok("", filas)

    @staticmethod
    @controlar_errores_bd
    def detalle(idnegocio, sesion=None):
        negocio = DatosNegocio.obtener(idnegocio)
        if not negocio or not puede_ver_negocio(negocio, sesion):
            return _error("No tiene acceso a ese negocio.")
        return _ok("", {"negocio": negocio, "lineas": DatosNegocio.detalle(idnegocio),
                        "entregas": DatosEntrega.de_negocio(idnegocio)})

    @staticmethod
    @controlar_errores_bd
    def lotes_de_productor(documento, sesion=None):
        """Lotes disponibles del productor para armar el detalle, marcando si está asociado a la cooperativa."""
        filas = DatosLote.de_productor_disponibles(documento)
        asociado = bool(sesion and sesion.get("nit") and DatosAsociacion.vigente(documento, sesion["nit"])
                        and DatosAsociacion.vigente(documento, sesion["nit"])["estado"] == ACTIVO)
        for fila in filas:
            fila["disponible"] = int(fila["disponible"])
            fila["asociado"] = asociado
        return _ok("", filas)

    @staticmethod
    @controlar_errores_bd
    def guardar(datos, sesion=None):
        if not _es(sesion, "Comprador"):
            return _error("Los negocios los propone un comprador de una cooperativa.")
        cooperativa = DatosCooperativa.obtener(sesion.get("nit"))
        if not cooperativa or cooperativa["estado"] != ACTIVO:
            return _error("Su cooperativa está inactiva.")
        validacion = LogicaNegocio._validar(datos, sesion)
        if not validacion["exito"]:
            return validacion
        cabecera = dict(validacion["datos"]["cabecera"], nit=sesion["nit"], idusuario=sesion["idusuario"],
                        token=_token())
        idnegocio = DatosNegocio.insertar(cabecera, validacion["datos"]["lineas"])
        negocio = DatosNegocio.obtener(idnegocio)
        envio = LogicaNegocio._notificar_productor(idnegocio)
        return _ok(f"Negocio {negocio['codigoe']} registrado en estado Propuesto por "
                   f"{whatsapp.pesos(negocio['valor_total'])}. El productor fue notificado para aceptarlo o "
                   f"rechazarlo." + LogicaNegocio._texto_resultado_envio(envio), idnegocio)

    @staticmethod
    @controlar_errores_bd
    def modificar(idnegocio, datos, sesion=None):
        negocio = DatosNegocio.obtener(idnegocio)
        if not negocio or not _es(sesion, "Comprador") or negocio["nit"] != sesion.get("nit"):
            return _error("Solo el comprador de la cooperativa puede modificar este negocio.")
        if negocio["estado_negocio"] != "Propuesto" or negocio["estado"] != ACTIVO:
            return _error("Solo se puede modificar un negocio en estado Propuesto.")
        datos = dict(datos, documento=negocio["documento"])
        validacion = LogicaNegocio._validar(datos, sesion)
        if not validacion["exito"]:
            return validacion
        DatosNegocio.actualizar(idnegocio, validacion["datos"]["cabecera"], validacion["datos"]["lineas"])
        envio = LogicaNegocio._notificar_productor(idnegocio, modificado=True)
        return _ok(f"Negocio {negocio['codigoe']} modificado. Se notificó de nuevo al productor."
                   + LogicaNegocio._texto_resultado_envio(envio), idnegocio)

    @staticmethod
    @controlar_errores_bd
    def cancelar(idnegocio, sesion=None):
        """Borrado lógico: el negocio pasa a Cancelado (estado Anulado) y lo reservado vuelve al inventario."""
        negocio = DatosNegocio.obtener(idnegocio)
        if not negocio:
            return _error("El negocio no existe.")
        es_suyo = _es(sesion, "Comprador") and negocio["nit"] == sesion.get("nit")
        if not (es_suyo or es_administrador(sesion)):
            return _error("Solo el comprador de la cooperativa puede cancelar este negocio.")
        if negocio["estado"] != ACTIVO or negocio["estado_negocio"] not in ("Propuesto", "Aceptado", "En entrega"):
            return _error(f"No se puede cancelar un negocio en estado {negocio['estado_negocio']}.")
        if DatosEntrega.recibidas_de_negocio(idnegocio):
            return _error("No se puede cancelar: el negocio ya tiene entregas recibidas.")
        DatosEntrega.cancelar_pendientes_de_negocio(idnegocio)
        DatosNegocio.cambiar_estado(idnegocio, "Cancelado", estado="Anulado")
        whatsapp.enviar(negocio["telefono_productor"], negocio["productor"], "Negocio cancelado", negocio["codigoe"],
                        f"☕ Café Conecta\nLa {negocio['cooperativa']} canceló el negocio {negocio['codigoe']}. "
                        "Las cantidades reservadas volvieron a su inventario.")
        return _ok(f"Negocio {negocio['codigoe']} cancelado (anulado). Las cantidades reservadas volvieron al "
                   "inventario y el negocio se conserva para la trazabilidad.")

    @staticmethod
    @controlar_errores_bd
    def aceptar(idnegocio, sesion=None):
        negocio = DatosNegocio.obtener(idnegocio)
        if not negocio or not _es(sesion, "Productor") or negocio["documento"] != sesion.get("documento"):
            return _error("Solo el productor del negocio puede aceptarlo.")
        if negocio["estado_negocio"] != "Propuesto" or negocio["estado"] != ACTIVO:
            return _error(f"Este negocio ya está {negocio['estado_negocio']}.")
        for linea in DatosNegocio.detalle(idnegocio):
            lote = DatosLote.obtener(linea["codigoc"])
            disponible = int(lote["cantidad"]) - int(lote["comprometida"])
            if lote["estado"] != ACTIVO or linea["cantidad"] > disponible:
                return _error(f"No se puede aceptar: el lote {linea['codigoc']} ya no tiene {linea['cantidad']} "
                              f"empaque(s) disponibles (quedan {max(disponible, 0)}).")
        DatosNegocio.cambiar_estado(idnegocio, "Aceptado", respuesta=True)
        LogicaNegocio._notificar_cooperativa(
            negocio, f"{negocio['productor']} aceptó el negocio {negocio['codigoe']} por "
                     f"{whatsapp.pesos(negocio['valor_total'])}. Pronto programará las entregas.", "Negocio aceptado")
        return _ok(f"Negocio {negocio['codigoe']} aceptado. Las cantidades se descontaron de lo disponible en "
                   "cada lote. Ahora puede programar las entregas.")

    @staticmethod
    @controlar_errores_bd
    def rechazar(idnegocio, motivo, sesion=None):
        negocio = DatosNegocio.obtener(idnegocio)
        if not negocio or not _es(sesion, "Productor") or negocio["documento"] != sesion.get("documento"):
            return _error("Solo el productor del negocio puede rechazarlo.")
        if negocio["estado_negocio"] != "Propuesto" or negocio["estado"] != ACTIVO:
            return _error(f"Este negocio ya está {negocio['estado_negocio']}.")
        motivo = " ".join((motivo or "").split())
        if len(motivo) < 5:
            return _error("Indique el motivo del rechazo.")
        DatosNegocio.cambiar_estado(idnegocio, "Rechazado", motivo=motivo[:250], respuesta=True)
        LogicaNegocio._notificar_cooperativa(
            negocio, f"{negocio['productor']} rechazó el negocio {negocio['codigoe']}. Motivo: {motivo}",
            "Negocio rechazado")
        return _ok(f"Negocio {negocio['codigoe']} rechazado.")

    @staticmethod
    def verificar_completado(idnegocio):
        """Cuando todas las cantidades del negocio están recibidas, pasa a Completado."""
        lineas = DatosNegocio.detalle(idnegocio)
        if lineas and all(l["recibida"] >= l["cantidad"] for l in lineas):
            DatosNegocio.cambiar_estado(idnegocio, "Completado")
            return True
        return False

    @staticmethod
    @controlar_errores_bd
    def desde_enlace(tipo, valor, sesion):
        """Resuelve un enlace o código de WhatsApp. Devuelve ('negocio', fila) o ('entrega', fila)."""
        if tipo == "n" or (tipo == "codigo" and str(valor).startswith("NEG-")):
            negocio = DatosNegocio.obtener(token=valor) if tipo == "n" else DatosNegocio.obtener(codigoe=valor)
            if not negocio:
                return _error("El enlace no corresponde a ningún negocio.")
            if not puede_ver_negocio(negocio, sesion):
                return _error("Este enlace es para otro usuario. Inicie sesión con la cuenta que recibió el mensaje.")
            return _ok("", ("negocio", negocio))
        entrega = DatosEntrega.obtener(token=valor) if tipo == "e" else DatosEntrega.obtener(code=valor)
        if not entrega:
            return _error("El enlace o código no corresponde a ningún negocio ni entrega.")
        if not puede_ver_negocio(entrega, sesion):
            return _error("Este enlace es para otro usuario. Inicie sesión con la cuenta que recibió el mensaje.")
        return _ok("", ("entrega", entrega))


# ---------------------------------------------------------------------
# HU-08 · Programación de entregas  ·  HU-09 · Confirmación de recibido
# ---------------------------------------------------------------------
class LogicaEntrega:

    @staticmethod
    def _validar(datos, negocio, actual=None):
        code = _texto(datos, "code").upper()
        if actual is None:
            if not code:
                return _error("El código de la entrega es obligatorio.")
            if not re.fullmatch(r"[A-Z0-9-]{2,20}", code):
                return _error("El código debe tener de 2 a 20 caracteres: letras, números o guion (ejemplo: E-001).")
            if DatosEntrega.obtener(code=code):
                return _error(f"Ya existe una entrega con el código {code}.")
        else:
            code = actual["code"]

        lineas = {l["iddetalle"]: l for l in DatosNegocio.detalle(negocio["idnegocio"])}
        iddetalle = datos.get("iddetalle")
        if not iddetalle or int(iddetalle) not in lineas:
            return _error("Seleccione la línea del negocio (el lote) que va a entregar.")
        linea = lineas[int(iddetalle)]

        try:
            fecha = datetime.strptime(_texto(datos, "fecha"), "%Y-%m-%d").date()
        except ValueError:
            return _error("La fecha debe tener el formato AAAA-MM-DD (ejemplo: 2026-12-05).")
        try:
            hora = datetime.strptime(_texto(datos, "hora"), "%H:%M").time()
        except ValueError:
            return _error("La hora debe tener el formato HH:MM en 24 horas (ejemplo: 14:30).")
        if datetime.combine(fecha, hora) <= datetime.now():
            return _error("La fecha y la hora de la entrega deben ser posteriores a este momento.")

        cantidad, error = _entero(datos.get("cantidad"), "cantidad de empaques")
        if error:
            return _error(error)
        if cantidad <= 0:
            return _error("La cantidad de empaques debe ser un entero mayor que cero.")
        ya = DatosEntrega.programado_linea(linea["iddetalle"], excluir_code=code if actual else None)
        if ya + cantidad > linea["cantidad"]:
            return _error(f"La línea {linea['codigoc']} tiene {linea['cantidad']} empaque(s) negociados y ya hay "
                          f"{ya} en otras entregas. Puede programar máximo {linea['cantidad'] - ya}.")

        lugar = " ".join(_texto(datos, "lugar").split())
        if not lugar:
            return _error("Indique el lugar de entrega (el punto de recibo de la cooperativa).")
        if len(lugar) > 150:
            return _error("El lugar no puede superar 150 caracteres.")
        descripcion = " ".join(_texto(datos, "descripcion").split())
        if len(descripcion) > 200:
            return _error("La descripción no puede superar 200 caracteres.")

        return _ok("", {"code": code, "iddetalle": linea["iddetalle"], "fecha": fecha.isoformat(),
                        "hora": hora.strftime("%H:%M:00"), "cantidad": cantidad, "lugar": lugar,
                        "descripcion": descripcion or None, "linea": linea})

    @staticmethod
    def _notificar_comprador(entrega, titulo, tipo):
        texto = (f"☕ Café Conecta\n{titulo}\nEntrega {entrega['code']} · negocio {entrega['codigoe']}\n"
                 f"Productor: {entrega['productor']}\nLote: {entrega['codigoc']} · {entrega['lote']}\n"
                 f"Fecha: {entrega['fecha']}  Hora: {entrega['hora']}\nCantidad: {entrega['cantidad']} empaque(s)\n"
                 f"Lugar: {entrega['lugar']}")
        return whatsapp.enviar(entrega["telefono_cooperativa"], entrega["cooperativa"], tipo, entrega["code"], texto)

    @staticmethod
    def _negocio_del_productor(idnegocio, sesion):
        negocio = DatosNegocio.obtener(idnegocio)
        if not negocio or not _es(sesion, "Productor") or negocio["documento"] != sesion.get("documento"):
            return None, _error("Solo el productor del negocio programa sus entregas.")
        return negocio, None

    @staticmethod
    @controlar_errores_bd
    def programar(idnegocio, datos, sesion=None):
        negocio, error = LogicaEntrega._negocio_del_productor(idnegocio, sesion)
        if error:
            return error
        if negocio["estado"] != ACTIVO or negocio["estado_negocio"] not in ("Aceptado", "En entrega"):
            return _error("Solo se programan entregas de negocios Aceptados o En entrega.")
        validacion = LogicaEntrega._validar(datos, negocio)
        if not validacion["exito"]:
            return validacion
        datos_entrega = dict(validacion["datos"], token=_token())
        DatosEntrega.insertar(datos_entrega)
        if negocio["estado_negocio"] == "Aceptado":
            DatosNegocio.cambiar_estado(idnegocio, "En entrega")   # al programar la primera entrega
        entrega = DatosEntrega.obtener(code=datos_entrega["code"])
        envio = LogicaEntrega._notificar_comprador(entrega, "Se programó una entrega de café:", "Entrega programada")
        return _ok(f"Entrega {entrega['code']} programada." + LogicaNegocio._texto_resultado_envio(envio),
                   entrega["code"])

    @staticmethod
    @controlar_errores_bd
    def modificar(code, datos, sesion=None):
        actual = DatosEntrega.obtener(code=code)
        if not actual:
            return _error("La entrega no existe.")
        negocio, error = LogicaEntrega._negocio_del_productor(actual["idnegocio"], sesion)
        if error:
            return error
        if actual["estado_entrega"] != "Programada":
            return _error("Solo se pueden modificar entregas Programadas.")
        validacion = LogicaEntrega._validar(datos, negocio, actual)
        if not validacion["exito"]:
            return validacion
        DatosEntrega.actualizar(code, validacion["datos"])
        entrega = DatosEntrega.obtener(code=code)
        envio = LogicaEntrega._notificar_comprador(entrega, "Se MODIFICÓ una entrega de café:", "Entrega modificada")
        return _ok(f"Entrega {code} modificada. Se notificó al comprador." +
                   LogicaNegocio._texto_resultado_envio(envio), code)

    @staticmethod
    @controlar_errores_bd
    def cancelar(code, sesion=None):
        """Borrado lógico: la entrega pasa a Cancelada (estado Anulado) y su cantidad queda por programar."""
        actual = DatosEntrega.obtener(code=code)
        if not actual:
            return _error("La entrega no existe.")
        _, error = LogicaEntrega._negocio_del_productor(actual["idnegocio"], sesion)
        if error:
            return error
        if actual["estado_entrega"] not in ("Programada", "En tránsito"):
            return _error(f"No se puede cancelar una entrega {actual['estado_entrega']}.")
        DatosEntrega.cambiar_estado(code, "Cancelada", estado="Anulado")
        LogicaEntrega._notificar_comprador(actual, "Se CANCELÓ una entrega de café:", "Entrega cancelada")
        return _ok(f"Entrega {code} cancelada. Sus {actual['cantidad']} empaque(s) quedan pendientes por programar.")

    @staticmethod
    @controlar_errores_bd
    def en_transito(code, sesion=None):
        actual = DatosEntrega.obtener(code=code)
        if not actual:
            return _error("La entrega no existe.")
        _, error = LogicaEntrega._negocio_del_productor(actual["idnegocio"], sesion)
        if error:
            return error
        if actual["estado_entrega"] != "Programada":
            return _error("Solo una entrega Programada se puede marcar En tránsito.")
        DatosEntrega.cambiar_estado(code, "En tránsito")
        return _ok(f"Entrega {code} marcada En tránsito. A la hora programada el comprador recibirá un "
                   "WhatsApp para confirmar el recibido.")

    @staticmethod
    @controlar_errores_bd
    def revisar_llegadas():
        """HU-09: a la hora programada, avisa por WhatsApp al comprador de cada entrega En tránsito."""
        enviados = 0
        for entrega in DatosEntrega.llegadas_pendientes():
            texto = (f"☕ Café Conecta\nLlegó la hora de la entrega {entrega['code']} (negocio {entrega['codigoe']}).\n"
                     f"Productor: {entrega['productor']}\nLote: {entrega['codigoc']} · {entrega['lote']}\n"
                     f"Cantidad esperada: {entrega['cantidad']} empaque(s)\n"
                     f"Confirme lo recibido aquí: {whatsapp.enlace('e', entrega['token'])}\n"
                     f"(o en Café Conecta › Negocios › Entregas › {entrega['code']})")
            DatosEntrega.marcar_aviso(entrega["code"])
            whatsapp.enviar(entrega["telefono_cooperativa"], entrega["cooperativa"], "Confirmar recibido",
                            entrega["code"], texto)
            enviados += 1
        return _ok(f"{enviados} aviso(s) de llegada enviados.", enviados)

    @staticmethod
    @controlar_errores_bd
    def confirmar(code, cantidad_recibida, novedad, sesion=None):
        entrega = DatosEntrega.obtener(code=code)
        if not entrega:
            return _error("La entrega no existe.")
        es_suyo = _es(sesion, "Comprador") and entrega["nit"] == sesion.get("nit")
        if not (es_suyo or es_administrador(sesion)):
            return _error("Solo el comprador de la cooperativa confirma el recibido.")
        if entrega["estado_entrega"] == "Cancelada":
            return _error("No se puede confirmar una entrega Cancelada.")
        if entrega["estado_entrega"] in ("Recibida", "Recibida con novedad"):
            return _error("Esta entrega ya fue confirmada. No se puede confirmar dos veces.")
        if entrega["estado_entrega"] != "En tránsito":
            return _error("La entrega todavía no está En tránsito.")
        recibida, error = _entero(cantidad_recibida, "cantidad recibida")
        if error:
            return _error(error)
        if recibida > entrega["cantidad"]:
            return _error(f"La cantidad recibida no puede superar lo programado ({entrega['cantidad']}).")
        novedad = " ".join((novedad or "").split())[:250] or None
        estado = "Recibida" if recibida == entrega["cantidad"] and not novedad else "Recibida con novedad"
        if not DatosEntrega.confirmar(code, recibida, novedad, estado, sesion["idusuario"]):
            return _error("Esta entrega ya fue confirmada. No se puede confirmar dos veces.")

        diferencia = entrega["cantidad"] - recibida
        texto = (f"☕ Café Conecta\nLa {entrega['cooperativa']} confirmó el recibido de la entrega {code} "
                 f"(negocio {entrega['codigoe']}): {recibida} de {entrega['cantidad']} empaque(s). Estado: {estado}.")
        if novedad:
            texto += f"\nNovedad: {novedad}"
        if diferencia:
            texto += f"\nQuedan {diferencia} empaque(s) pendientes por entregar en esa línea."
        envio = whatsapp.enviar(entrega["telefono_productor"], entrega["productor"], "Recibido confirmado", code, texto)
        completado = LogicaNegocio.verificar_completado(entrega["idnegocio"])
        mensaje = f"Entrega {code} confirmada como {estado}."
        if diferencia:
            mensaje += f" La diferencia ({diferencia} empaque(s)) queda pendiente por entregar en esa línea."
        if completado:
            mensaje += f" Todas las cantidades llegaron: el negocio {entrega['codigoe']} pasó a Completado."
        return _ok(mensaje + LogicaNegocio._texto_resultado_envio(envio))


class LogicaMensaje:

    @staticmethod
    @controlar_errores_bd
    def listar(filtro="", sesion=None, filtros=None):
        if not es_administrador(sesion):
            return _error("La bitácora de mensajes es solo para el administrador.")
        return _ok("", DatosMensaje.listar((filtro or "").strip()))
