# Café Conecta

Sistema de escritorio (Python + Tkinter + MySQL) de Ingeniería de Software III, Equipo 5.

- **Parcial I:** acceso al sistema con recuperación por correo, menú principal y CRUD de Perfil, Persona y Usuario.
- **Parcial II:** HU-01 a HU-05: productores, fincas, cooperativas, asociaciones y variedades de café.

## 1. Requisitos

- Python 3.10 o superior. En Mac use el de python.org, que trae un Tkinter actualizado.
- MAMP o XAMPP con MySQL encendido.
- Librerías: el conector de MySQL y Pillow (para ver las imágenes JPG de las variedades).

```
pip install -r requirements.txt
```

En Mac basta con hacer doble clic en `instalar_y_ejecutar.command`: instala lo necesario,
prepara la base de datos y abre el programa.

## 2. Base de datos

Hay dos archivos SQL. Use **solo uno** según su caso:

| Su caso | Archivo a importar en phpMyAdmin |
|---|---|
| Ya tiene la base del Parcial I y quiere **conservar sus datos** | `actualizar_parcial2.sql` (una sola vez) |
| Quiere **empezar de cero** con datos de ejemplo | `cafeconecta.sql` (borra y vuelve a crear la base) |

`python preparar_bd.py` hace esto solo: si la base no existe la crea, y si es la del Parcial I la actualiza.

Usuarios de ejemplo de `cafeconecta.sql`:

| Usuario | Contraseña | Perfil |
|---|---|---|
| admin | admin123 | Administrador |
| productor1 | cafe2026 | Productor (Luis Martínez, finca La Esperanza) |
| comprador1 | cafe2026 | Comprador (Cooperativa Cafetera El Mirador) |

## 3. Configurar `config.py`

- **Puerto y contraseña de MySQL:** MAMP usa normalmente el puerto 8889 con contraseña `root`;
  XAMPP usa el 3306 (o 3307) sin contraseña.
- **Correo de recuperación (Gmail):** active la verificación en dos pasos, cree una contraseña de aplicación en
  <https://myaccount.google.com/apppasswords> y póngala en `contrasena_aplicacion`.

## 4. Ejecutar

```
python presentacion.py
```

En Mac: `python3 presentacion.py`.

## 5. Estructura (arquitectura por capas)

| Archivo | Capa | Qué hace |
|---|---|---|
| `presentacion.py` | Presentación | Acceso al sistema, recuperación, panel principal y menú |
| `formularios.py` | Presentación | Los 8 formularios de gestión (CRUD) y las ventanas de detalle |
| `estilos.py` | Presentación | Colores y dibujos con temática cafetera |
| `negocio.py` | Negocio | Validaciones de cada historia de usuario y permisos por perfil |
| `correo.py` | Negocio / servicio | Envío del correo de recuperación (SMTP) |
| `datos.py` | Datos | Todas las consultas SQL |
| `conexion.py` | Datos | Conexión a MySQL |
| `config.py` | Configuración | Datos de la base de datos y del correo |
| `imagenes_ejemplo/` | — | Imágenes de variedades para probar la HU-05 |

## 6. Perfiles y permisos

| Perfil | Qué puede hacer |
|---|---|
| Administrador | Todo: los 8 módulos con todas las acciones |
| Productor | Consultar y modificar sus propios datos (no el documento ni el estado), gestionar **sus** fincas y consultar las variedades activas |
| Comprador | Consultar su cooperativa, solicitar asociaciones de productores a su cooperativa y consultar las variedades activas |
| Persona | Gestión Persona (sus propios datos), como en el Parcial I |

Para que alguien entre como **Productor**: regístrelo en Gestión Productores y luego use el botón
*Crear usuario al productor*. Para un **Comprador**: cree la persona, y en Gestión Usuario elija el perfil
Comprador y su cooperativa.

## 7. Cómo se cumplen las historias de usuario del Parcial II

**HU-01 · Productores.** Usa la misma programación de Persona: los datos personales se guardan en `persona` y el
productor en `productor`, con el documento como llave primaria.
- Son obligatorios documento, nombres, teléfono, dirección y fecha de nacimiento. Nombre2, apellido2 y correo son opcionales.
- No se repiten documento ni correo. El teléfono debe ser un celular de 10 dígitos y el productor debe ser mayor de 18 años.
- Se busca por documento, nombre, apellido o cooperativa. La lista muestra sus cooperativas, el número de fincas y el estado.
- El documento no se modifica. El productor modifica sus propios datos, pero no el documento ni el estado.
- Inhabilitar es un borrado lógico. El botón *Ver cooperativas* muestra su historial de afiliaciones (HU-04).

**HU-02 · Fincas.**
- El código (`codigof`) no se repite y no se modifica.
- El área se registra en hectáreas y debe ser mayor que cero. La temperatura promedio debe estar entre 5 y 35 °C.
- Departamento y municipio se eligen de listas desplegables con los 33 departamentos y 1.103 municipios de
  Colombia. Al elegir el departamento se cargan solo sus municipios.
- El productor ve solo *Mis fincas*. El administrador ve todas y las filtra por departamento, municipio y productor.

**HU-03 · Cooperativas.**
- El NIT lleva el dígito de verificación separado por guion (900123456-7) y no se modifica.
- No se repiten NIT, nombre ni correo. El teléfono debe ser un celular de 10 dígitos.
- *Ver productores y compradores* muestra sus productores asociados y sus usuarios compradores.

**HU-04 · Asociaciones.**
- El administrador asocia un productor activo a una cooperativa activa. La asociación queda Activa con su fecha de afiliación.
- Un productor puede estar en varias cooperativas, pero no dos veces en la misma.
- El comprador solicita la asociación, que queda *Pendiente* hasta que el administrador la aprueba o la rechaza.
- *Desasociar* la deja Inactiva con fecha de retiro y conserva el historial.

**HU-05 · Variedades.**
- El código y la descripción no se repiten, y el código no se modifica.
- La imagen debe ser JPG o PNG de máximo 2 MB. Se reconoce por su contenido, no por el nombre del archivo.
- Productores y compradores ven solo las variedades activas, en orden alfabético.

**Reglas que dependen del Final.** Algunas reglas usan lotes y negocios (HU-06 y HU-07), que todavía no existen:
- no inhabilitar productores o cooperativas con negocios Aceptados o En entrega;
- no inhabilitar fincas con lotes;
- ocultar del catálogo los lotes de un productor inhabilitado.

Están marcadas en `negocio.py` y se completan en el Final.
