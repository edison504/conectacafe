"""
Capa de negocio: reglas, validaciones y permisos de Café Conecta.

Cada método devuelve un diccionario {"exito": bool, "mensaje": str, "datos": ...}
para que la capa de presentación solo tenga que mostrar el resultado.
"""
import re
from datetime import date, datetime
from functools import wraps

import mysql.connector

import correo
from conexion import ErrorConexion
from datos import DatosAcceso, DatosPerfil, DatosPersona, DatosUsuario

ACTIVO, INACTIVO = "Activo", "Inactivo"
ACCIONES = ("Crear", "Consultar", "Modificar", "Guardar", "Inhabilitar", "Salir")

# Permisos según la tabla de requisitos funcionales del parcial.
PERMISOS = {
    "Administrador": {
        "Perfil": set(ACCIONES),
        "Usuario": set(ACCIONES),
        "Persona": set(ACCIONES),
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

        sesion = {
            "idusuario": fila["Idusuario"],
            "usuario": fila["nombreu"],
            "perfil": fila["perfil"],
            "idperfil": fila["idperfil"],
            "idpersona": fila["idpersona"],
            "nombre": f"{fila['nom1']} {fila['apell1']}",
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
    def listar(filtro="", sesion=None):
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
    def listar(filtro="", sesion=None):
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

        return _ok("", {"nombreu": nombreu, "contrasena": contrasena,
                        "idperfil": int(idperfil), "idpersona": int(idpersona)})

    @staticmethod
    @controlar_errores_bd
    def opciones_perfil():
        return _ok("", [(f["Idperfil"], f["descripc"]) for f in DatosPerfil.listar_activos()])

    @staticmethod
    @controlar_errores_bd
    def opciones_persona(incluir_id=None):
        filas = DatosPersona.listar_sin_usuario(incluir_id)
        return _ok("", [(f["Idpersona"], f"{f['nom1']} {f['apell1']} ({f['correo']})") for f in filas])

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
    def listar(filtro="", sesion=None):
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
