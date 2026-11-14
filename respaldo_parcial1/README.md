# Café Conecta

Sistema de escritorio (Python + Tkinter + MySQL) para el Parcial I de Ingeniería de Software III:
acceso al sistema, menú principal y CRUD de **Perfil**, **Persona** y **Usuario** con borrado lógico.

## 1. Requisitos

- Python 3.10 o superior (en Windows, Tkinter ya viene incluido).
- XAMPP con MySQL/MariaDB encendido.
- Librería del conector:

```
pip install -r requirements.txt
```

## 2. Crear la base de datos

1. Abra phpMyAdmin (`http://localhost/phpmyadmin`).
2. Pestaña **Importar** → seleccione `cafeconecta.sql` → **Importar**.
   El script crea la base `cafeconecta` desde cero (si ya existía, la reemplaza).
3. En la tabla `persona`, cambie el correo de Carlos por uno real al que tengan acceso,
   para poder probar la recuperación de contraseña.

## 3. Configurar `config.py`

- **Puerto de MySQL:** si XAMPP muestra MySQL en el puerto 3307, cambie `"port": 3306` por `3307`.
- **Correo de recuperación (Gmail):**
  1. En la cuenta de Gmail que enviará los correos, active la verificación en dos pasos.
  2. Entre a <https://myaccount.google.com/apppasswords> y cree una contraseña de aplicación.
  3. Ponga ese correo en `remitente` y la contraseña de 16 letras (sin espacios) en `contrasena_aplicacion`.

## 4. Ejecutar

```
python presentacion.py
```

Usuario inicial: **admin** · Contraseña: **admin123** (perfil Administrador).

## 5. Estructura (arquitectura por capas)

| Archivo | Capa | Qué hace |
|---|---|---|
| `presentacion.py` | Presentación | Acceso al sistema, recuperación, panel principal y menú |
| `formularios.py` | Presentación | Formularios Gestión Perfil, Persona y Usuario (CRUD) |
| `estilos.py` | Presentación | Colores y dibujos con temática cafetera |
| `negocio.py` | Negocio | Validaciones, permisos por perfil y reglas |
| `correo.py` | Negocio / servicio | Envío del correo de recuperación (SMTP) |
| `datos.py` | Datos | Todas las consultas SQL |
| `conexion.py` | Datos | Conexión a MySQL |
| `config.py` | Configuración | Datos de la base de datos y del correo |

## 6. Cómo se cumplen los requisitos

- **Acceso al sistema:** Ingresar, Cancelar (limpia los campos), Recuperar y Registrarse.
  Mensajes para campos vacíos, usuario no registrado, contraseña incorrecta y usuario, perfil o persona inactivos.
- **Recuperación:** abre un campo para digitar usuario, correo o número de identificación (ID de la persona),
  envía un correo real con el usuario y la contraseña y muestra
  "Su usuario y contraseña fue enviado al correo registrado". Si no existe: "El usuario no se encuentra registrado".
- **Registrarse:** carga Gestión Persona (paso 1) y luego crea el usuario con perfil *Persona* (paso 2).
- **Panel principal:** diseño con temática del café (sector agropecuario), estadísticas y menú
  Gestión Perfil / Usuario / Persona.
- **Formularios:** botones Crear, Consultar, Modificar, Guardar, Inhabilitar y Salir, con todos los campos
  del modelo relacional.
- **Inhabilitar:** borrado lógico (cambia `estado` a *Inactivo*; el mismo botón permite *Activar*).
  Nunca se borra un registro.
- **Permisos (tabla de requisitos):** el *Administrador* usa los tres formularios con todas las acciones.
  El perfil *Persona* solo entra a Gestión Persona, ve únicamente sus propios datos y no puede inhabilitar.
- **Modelo relacional:** un perfil tiene muchos usuarios; una persona tiene un solo usuario
  (`usuario.idpersona` es UNIQUE).
- **Sin datos quemados:** todo se lee y se guarda en la base de datos.
