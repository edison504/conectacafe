# Café Conecta

Sistema de escritorio (Python + Tkinter + MySQL) de Ingeniería de Software III, Equipo 5.

- **Parcial I:** acceso al sistema con recuperación por correo, menú principal y CRUD de Perfil, Persona y Usuario.
- **Parcial II:** HU-01 a HU-05: productores, fincas, cooperativas, asociaciones y variedades de café.
- **Final:** HU-06 a HU-10: lotes de café, negocios, entregas, confirmación de recibido por WhatsApp y
  listado de lotes disponibles con exportación a Excel y PDF.

## 1. Requisitos

- Python 3.10 o superior. En Mac use el de python.org, que trae un Tkinter actualizado.
- MAMP o XAMPP con MySQL encendido.
- Librerías: el conector de MySQL, Pillow (imágenes JPG), openpyxl (Excel) y reportlab (PDF).

```
pip install -r requirements.txt
```

En Mac basta con hacer doble clic en `instalar_y_ejecutar.command`: instala lo necesario,
prepara la base de datos y abre el programa.

## 2. Base de datos

Use **solo uno** de estos archivos según su caso:

| Su caso | Archivo a importar en phpMyAdmin |
|---|---|
| Tiene la base del Parcial I y quiere **conservar sus datos** | `actualizar_parcial2.sql` y después `actualizar_final.sql` |
| Tiene la base del Parcial II y quiere **conservar sus datos** | `actualizar_final.sql` (una sola vez) |
| Quiere **empezar de cero** con datos de ejemplo | `cafeconecta.sql` (borra y vuelve a crear la base) |

`python preparar_bd.py` hace esto solo: si la base no existe la crea, y si es de un parcial anterior la actualiza.

Usuarios de ejemplo de `cafeconecta.sql`:

| Usuario | Contraseña | Perfil |
|---|---|---|
| admin | admin123 | Administrador |
| productor1 | cafe2026 | Productor (Luis Martínez, finca La Esperanza) |
| productor2 | cafe2026 | Productor (Marta Ríos, finca Villa Marta, Pitalito, Huila) |
| comprador1 | cafe2026 | Comprador (Cooperativa Cafetera El Mirador) |

Los datos de ejemplo traen 4 lotes de café (L-001 a L-004) con su imagen, listos para negociar.

## 3. Configurar `config.py`

- **Puerto y contraseña de MySQL:** MAMP usa normalmente el puerto 8889 con contraseña `root`;
  XAMPP usa el 3306 (o 3307) sin contraseña.
- **Correo de recuperación (Gmail):** active la verificación en dos pasos, cree una contraseña de aplicación en
  <https://myaccount.google.com/apppasswords> y póngala en `contrasena_aplicacion`.

- **WhatsApp (Final):** en la sección `WHATSAPP` elija el modo de envío:
  - `whatsapp_web` (predeterminado): abre WhatsApp Web o la app con el mensaje ya escrito para el número
    del destinatario; solo hay que presionar *Enviar*. No necesita ninguna cuenta.
  - `cloud_api`: envío automático con la API oficial de WhatsApp de Meta. En <https://developers.facebook.com>
    cree una app de tipo *Business*, agregue *WhatsApp*, copie el *token temporal* y el *Phone number ID*, y
    registre como destinatarios de prueba los celulares del equipo.
  - `twilio`: envío automático con el *sandbox* de WhatsApp de Twilio (SID, token y número).
  - `simulado`: no envía nada; el mensaje queda solo en la bitácora.
  Todos los mensajes, en cualquier modo, quedan en **Gestión › Mensajes** con su resultado.

## 4. Ejecutar

```
python presentacion.py
```

En Mac: `python3 presentacion.py`.

## 5. Estructura (arquitectura por capas)

| Archivo | Capa | Qué hace |
|---|---|---|
| `presentacion.py` | Presentación | Acceso al sistema, recuperación, panel principal y menú |
| `formularios.py` | Presentación | Los formularios de gestión (CRUD), incluido el de lotes, y las ventanas de detalle |
| `ventanas_comercial.py` | Presentación | Listado de lotes, negocios, entregas, confirmación de recibido y bitácora |
| `estilos.py` | Presentación | Colores y dibujos con temática cafetera |
| `negocio.py` | Negocio | Validaciones de cada historia de usuario y permisos por perfil |
| `correo.py` | Negocio / servicio | Envío del correo de recuperación (SMTP) |
| `whatsapp.py` | Negocio / servicio | Envío de los avisos por WhatsApp y registro en la bitácora |
| `enlaces.py` | Servicio | Servidor local que recibe los enlaces de los mensajes y abre la pantalla indicada |
| `datos.py` | Datos | Todas las consultas SQL |
| `conexion.py` | Datos | Conexión a MySQL |
| `config.py` | Configuración | Base de datos, correo, WhatsApp y enlaces |
| `imagenes_ejemplo/` | — | Imágenes de variedades y de lotes para probar la HU-05 y la HU-06 |

## 6. Perfiles y permisos

| Perfil | Qué puede hacer |
|---|---|
| Administrador | Todo: los 12 módulos. Ve todos los lotes y negocios, el listado con lotes inactivos o agotados y la bitácora de mensajes |
| Productor | Sus datos, **sus** fincas, **su** inventario de lotes, y los negocios que le proponen: aceptar, rechazar y programar entregas |
| Comprador | Su cooperativa, solicitar asociaciones, el listado de lotes disponibles, proponer negocios y confirmar lo recibido |
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

## 8. Cómo se cumplen las historias de usuario del Final

El ciclo completo es: **lote → listado → negocio → aceptación → entregas → confirmación de recibido**.

**HU-06 · Lotes de café (Gestión Lotes de café).**
- El productor registra en *sus* fincas activas: código único (no se modifica), descripción con tipo y calidad,
  variedad activa, tipo de empaque (lista: saco de fique, polipropileno, yute o bolsa de válvula), peso por
  empaque en kg (> 0), cantidad de empaques (entero > 0), precio de compra por kg (> 0) e imagen JPG o PNG de máximo 2 MB.
- El lote queda Activo. *Mi inventario* muestra por lote la cantidad, lo **comprometido** en negocios y lo **disponible**.
- No se puede bajar la cantidad por debajo de lo comprometido, ni cambiar peso o empaque si el lote ya tiene negocios.
  Un precio nuevo aplica solo a negocios nuevos. Inhabilitar es borrado lógico.

**HU-10 · Listado de lotes disponibles.**
- Muestra solo lotes activos con cantidad disponible, de productores y fincas activos: código, variedad, descripción,
  empaque, peso, disponibles, kg disponibles, precio por kg, finca, municipio, departamento, temperatura, productor y
  sus cooperativas. La estrella ★ marca a los productores asociados a la cooperativa del comprador.
- Filtros por texto, variedad, departamento → municipio, cooperativa y rango de precio; orden por precio, kg
  disponibles o fecha. Al pie, el total de kg disponibles por variedad. Al seleccionar un lote se ve su imagen.
- Exporta a **Excel** y **PDF**. El administrador puede incluir lotes inactivos o agotados.

**HU-07 · Negocios.**
- El comprador elige un productor (o un lote del listado) y arma el detalle con uno o varios lotes de ese mismo
  productor, sin repetir lote, con cantidad ≤ disponible y precio acordado por kg. El sistema calcula
  **subtotal = cantidad × peso por empaque × precio por kg** y el valor total. Medio de pago de una lista.
- El negocio queda **Propuesto** con código NEG-0001… y el productor recibe un **WhatsApp** con el resumen y un enlace.
- El productor lo **acepta** (las cantidades se descuentan de lo disponible) o lo **rechaza** con motivo; la
  cooperativa recibe el aviso. El comprador puede modificar un negocio Propuesto o cancelarlo (borrado lógico).

**HU-08 · Entregas.**
- Con el negocio Aceptado, el productor programa una o varias entregas por lote (entregas parciales): código único,
  fecha y hora posteriores al momento actual, cantidad entera y lugar. La suma no supera lo negociado.
- La primera entrega pasa el negocio a **En entrega**. Cada programación, cambio o cancelación avisa por WhatsApp
  a la cooperativa. Al despachar, la entrega pasa a **En tránsito**.

**HU-09 · Confirmación de recibido.**
- Cada 30 segundos el sistema revisa las entregas En tránsito; a la fecha y hora programadas envía al comprador un
  WhatsApp con el código, el productor, el lote, la cantidad y un **enlace** para confirmar.
- Al abrir el enlace, Café Conecta pide iniciar sesión (si hace falta) y abre la confirmación. También se puede
  pegar el enlace o escribir el código en *¿Le llegó un enlace por WhatsApp?* en la pantalla de acceso.
- El comprador registra la cantidad recibida y, si hay diferencia o problema, la novedad: queda **Recibida** o
  **Recibida con novedad**, con fecha, hora y usuario. No se puede confirmar dos veces. El productor recibe el
  aviso. La diferencia queda pendiente para otra entrega y, cuando todo llega, el negocio pasa a **Completado**.

**Reglas de HU-01 a HU-03 que se completan en el Final.**
- No se puede inhabilitar un productor ni una cooperativa con negocios Aceptados o En entrega.
- No se puede inhabilitar una finca con lotes que tengan café disponible o comprometido en negocios activos.
- Los lotes de un productor o una finca inhabilitados no aparecen en el listado de disponibles.
