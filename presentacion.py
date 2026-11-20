import queue
import tkinter as tk
from tkinter import messagebox, simpledialog

import enlaces
import estilos as e
import formularios
import ventanas_comercial
import whatsapp
from negocio import LogicaAcceso, LogicaEntrega, LogicaNegocio, PERMISOS, permisos_de

REVISAR_LLEGADAS_MS = 30_000   # HU-09: cada 30 segundos se revisa si llegó la hora de alguna entrega


# Módulos del panel principal: (entidad, ícono, título, descripción)
MODULOS = [
    ("Gestión cafetera", [
        ("Productor", "☘", "Productores", "Caficultores: datos de contacto, cooperativas y fincas."),
        ("Finca", "⛰", "Fincas", "Dónde se produce el café: área, clima y ubicación."),
        ("Cooperativa", "⌂", "Cooperativas", "Organizaciones que compran el café."),
        ("Asociacion", "⇄", "Asociaciones", "Afiliación de productores a cooperativas."),
        ("Variedad", "❦", "Variedades", "Castillo, Caturra, Geisha… con su imagen."),
    ]),
    ("Ciclo comercial", [
        ("Lote", "▦", "Lotes de café", "Inventario: café listo para vender, con su imagen."),
        ("Catalogo", "▤", "Lotes disponibles", "Buscar café por variedad, zona y precio."),
        ("Negocio", "⇆", "Negocios", "Proponer, aceptar y seguir negocios."),
        ("Mensaje", "✉", "Mensajes", "Bitácora de avisos por WhatsApp."),
    ]),
    ("Administración del sistema", [
        ("Persona", "☺", "Personas", "Datos personales de quienes usan el sistema."),
        ("Usuario", "⚿", "Usuarios", "Cuentas de acceso, perfiles y compradores."),
        ("Perfil", "⚙", "Perfiles", "Tipos de usuario y sus permisos."),
    ]),
]


class Aplicacion(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Café Conecta")
        self.configure(bg=e.CREMA)
        e.configurar_estilos(self)
        self.sesion = None
        self.pedido_pendiente = None    # enlace de WhatsApp que llegó antes de iniciar sesión
        self.servidor_enlaces = enlaces.iniciar(whatsapp.configuracion_enlaces()["puerto"])
        self.mostrar_login()
        self.after(500, self._revisar_pedidos)
        self.after(5_000, self._revisar_llegadas)

    # ------------------------------------------------------------------
    # Enlaces de WhatsApp y avisos de llegada (HU-07 y HU-09)
    # ------------------------------------------------------------------
    def _revisar_pedidos(self):
        try:
            while True:
                pedido = enlaces.PEDIDOS.get_nowait()
                self.deiconify()
                self.lift()
                self.focus_force()
                if self.sesion:
                    self._abrir_pedido(pedido)
                else:
                    self._dejar_pendiente(pedido)
        except queue.Empty:
            pass
        self.after(500, self._revisar_pedidos)

    def _revisar_llegadas(self):
        try:
            LogicaEntrega.revisar_llegadas()
        except Exception:
            pass
        self.after(REVISAR_LLEGADAS_MS, self._revisar_llegadas)

    def _dejar_pendiente(self, pedido):
        self.pedido_pendiente = pedido
        if getattr(self, "lbl_pedido", None) and self.lbl_pedido.winfo_exists():
            self.lbl_pedido.config(text="🔗 Tiene un enlace de WhatsApp pendiente.\n"
                                        "Inicie sesión con su cuenta para continuar.")

    def _abrir_pedido(self, pedido):
        tipo, valor = pedido
        resultado = LogicaNegocio.desde_enlace(tipo, valor, self.sesion)
        if not resultado["exito"]:
            messagebox.showwarning("Enlace de WhatsApp", resultado["mensaje"], parent=self)
            return
        clase, fila = resultado["datos"]
        if clase == "negocio":
            ventanas_comercial.abrir_negocios(self, self.sesion, (), al_cerrar=self.actualizar_estadisticas,
                                              abrir_id=fila["idnegocio"])
        else:
            ventana = ventanas_comercial.abrir_negocios(self, self.sesion, (), al_cerrar=self.actualizar_estadisticas,
                                                        abrir_id=fila["idnegocio"])
            entregas = ventana.f_entregas(code_inicial=fila["code"])
            # El comprador llega desde el aviso de llegada: se abre de una vez la confirmación.
            if entregas and entregas.puede_confirmar and fila["estado_entrega"] == "En tránsito":
                self.after(300, entregas.f_confirmar)

    def f_pegar_enlace(self):
        texto = simpledialog.askstring("Enlace de WhatsApp", "Pegue el enlace que recibió por WhatsApp\n"
                                       "o escriba el código (ej.: NEG-0001 o E-001):", parent=self)
        tipo, valor = enlaces.interpretar(texto)
        if not tipo:
            return
        self._dejar_pendiente((tipo, valor))
        self.txt_usuario.focus_set()

    def _limpiar(self):
        for hijo in self.winfo_children():
            hijo.destroy()
        self.config(menu="")

  
    def mostrar_login(self, usuario_sugerido=""):
        self._limpiar()
        self.sesion = None
        self.title("Café Conecta - Acceso al Sistema")
        e.centrar(self, 900, 560)
        self.resizable(False, False)

        # Lado izquierdo: ilustración cafetera
        lienzo = tk.Canvas(self, width=430, height=560, highlightthickness=0)
        lienzo.pack(side="left", fill="y")
        e.paisaje_cafetero(lienzo, 430, 560, con_taza=False, nivel=0.20)
        e.taza(lienzo, 215, 120, 1.0)
        e.rama_cafeto(lienzo, 10, 540, 1.1)
        e.rama_cafeto(lienzo, 420, 520, 0.9, invertir=True)
        lienzo.create_text(215, 228, text="Café Conecta", font=(e.FUENTE, 30, "bold"), fill=e.CAFE_OSCURO)
        lienzo.create_text(215, 264, text="Del cultivo a tu taza", font=(e.FUENTE, 13, "italic"),
                           fill=e.CAFE)
        lienzo.create_text(215, 290, text="Conectando caficultores, cosechas y clientes",
                           font=e.F_PEQUENA, fill=e.CAFE_OSCURO)

        # Lado derecho: formulario
        panel = tk.Frame(self, bg=e.BLANCO)
        panel.pack(side="left", fill="both", expand=True)
        caja = tk.Frame(panel, bg=e.BLANCO)
        caja.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(caja, text="Acceso al sistema", font=e.F_TITULO, bg=e.BLANCO, fg=e.CAFE_OSCURO).pack(anchor="w")
        tk.Label(caja, text="Ingrese con su usuario y contraseña", font=e.F_NORMAL, bg=e.BLANCO,
                 fg=e.GRIS).pack(anchor="w", pady=(0, 22))

        tk.Label(caja, text="Usuario", font=e.F_NEGRITA, bg=e.BLANCO, fg=e.TEXTO).pack(anchor="w")
        self.txt_usuario = tk.Entry(caja, font=(e.FUENTE, 12), width=30, relief="solid", bd=1)
        self.txt_usuario.pack(ipady=6, pady=(2, 12))
        self.txt_usuario.insert(0, usuario_sugerido)

        tk.Label(caja, text="Contraseña", font=e.F_NEGRITA, bg=e.BLANCO, fg=e.TEXTO).pack(anchor="w")
        self.txt_contrasena = tk.Entry(caja, font=(e.FUENTE, 12), width=30, show="•", relief="solid", bd=1)
        self.txt_contrasena.pack(ipady=6, pady=(2, 4))
        self.var_ver = tk.BooleanVar()
        tk.Checkbutton(caja, text="Mostrar contraseña", variable=self.var_ver, bg=e.BLANCO, font=e.F_PEQUENA,
                       activebackground=e.BLANCO,
                       command=lambda: self.txt_contrasena.config(show="" if self.var_ver.get() else "•")
                       ).pack(anchor="w")

        botones = tk.Frame(caja, bg=e.BLANCO)
        botones.pack(fill="x", pady=(18, 10))
        e.boton(botones, "Ingresar", self.f_ingresar, e.VERDE, ancho=12).pack(side="left", expand=True, fill="x")
        tk.Frame(botones, width=10, bg=e.BLANCO).pack(side="left")
        e.boton(botones, "Cancelar", self.f_cancelar, e.CAFE_CLARO, ancho=12).pack(side="left", expand=True,
                                                                                   fill="x")

        enlaces = tk.Frame(caja, bg=e.BLANCO)
        enlaces.pack(fill="x", pady=(8, 0))
        for texto, comando in (("¿Olvidó su usuario o contraseña?", self.f_recuperar),
                               ("¿No tiene cuenta? Registrarse", self.f_registrarse)):
            enlace = tk.Label(enlaces, text=texto, font=(e.FUENTE, 10, "underline"), bg=e.BLANCO,
                              fg=e.VERDE, cursor="hand2")
            enlace.pack(anchor="w", pady=3)
            enlace.bind("<Button-1>", lambda ev, c=comando: c())
        enlace = tk.Label(enlaces, text="¿Le llegó un enlace por WhatsApp?", font=(e.FUENTE, 10, "underline"),
                          bg=e.BLANCO, fg=e.CAFE, cursor="hand2")
        enlace.pack(anchor="w", pady=3)
        enlace.bind("<Button-1>", lambda ev: self.f_pegar_enlace())
        self.lbl_pedido = tk.Label(caja, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.CEREZA, justify="left")
        self.lbl_pedido.pack(anchor="w", pady=(6, 0))
        if self.pedido_pendiente:
            self._dejar_pendiente(self.pedido_pendiente)

        self.bind("<Return>", lambda ev: self.f_ingresar())
        (self.txt_contrasena if usuario_sugerido else self.txt_usuario).focus_set()

    def f_ingresar(self):
        resultado = LogicaAcceso.autenticar_usuario(self.txt_usuario.get(), self.txt_contrasena.get())
        if not resultado["exito"]:
            messagebox.showwarning("Acceso al sistema", resultado["mensaje"], parent=self)
            return
        self.unbind("<Return>")
        self.mostrar_panel(resultado["datos"])
        if self.pedido_pendiente:
            pedido, self.pedido_pendiente = self.pedido_pendiente, None
            self.after(300, lambda: self._abrir_pedido(pedido))

    def f_cancelar(self):
        """Limpia los campos del formulario."""
        self.txt_usuario.delete(0, "end")
        self.txt_contrasena.delete(0, "end")
        self.txt_usuario.focus_set()

    def f_registrarse(self):
        formularios.abrir_registro(self, PERMISOS["Registro"], al_terminar=self._registro_terminado)

    def _registro_terminado(self, nombre_usuario):
        self.txt_usuario.delete(0, "end")
        self.txt_usuario.insert(0, nombre_usuario)
        self.txt_contrasena.delete(0, "end")
        self.txt_contrasena.focus_set()

    def f_recuperar(self):
        VentanaRecuperacion(self, self.txt_usuario.get().strip())

   
    def mostrar_panel(self, sesion):
        self._limpiar()
        self.sesion = sesion
        permisos = permisos_de(sesion["perfil"])
        self.title("Café Conecta - Panel Principal")
        self.resizable(True, True)
        e.centrar(self, 1180, 790)
        self.minsize(1040, 740)

        # Menú superior
        barra_menu = tk.Menu(self)
        menu_gestion = tk.Menu(barra_menu, tearoff=0)
        for grupo, modulos_grupo in MODULOS:
            if grupo != MODULOS[0][0]:
                menu_gestion.add_separator()
            for entidad, _icono, titulo, _texto in modulos_grupo:
                menu_gestion.add_command(label=f"Gestión {titulo}", command=lambda n=entidad: self.abrir_gestion(n),
                                         state="normal" if entidad in permisos else "disabled")
        barra_menu.add_cascade(label="Gestión", menu=menu_gestion)
        menu_sesion = tk.Menu(barra_menu, tearoff=0)
        menu_sesion.add_command(label="Cerrar sesión", command=self.cerrar_sesion)
        menu_sesion.add_separator()
        menu_sesion.add_command(label="Salir del sistema", command=self.destroy)
        barra_menu.add_cascade(label="Sesión", menu=menu_sesion)
        self.config(menu=barra_menu)

        # Encabezado
        cab = tk.Frame(self, bg=e.CAFE_OSCURO)
        cab.pack(fill="x")
        tk.Label(cab, text="☕  Café Conecta", font=(e.FUENTE, 18, "bold"), bg=e.CAFE_OSCURO,
                 fg=e.BLANCO).pack(side="left", padx=20, pady=12)
        e.boton(cab, "Cerrar sesión", self.cerrar_sesion, e.CEREZA).pack(side="right", padx=16)
        tk.Label(cab, text=f"{sesion['nombre']}  ·  Perfil: {sesion['perfil']}", font=e.F_NORMAL,
                 bg=e.CAFE_OSCURO, fg=e.DORADO).pack(side="right", padx=10)

        # Banner con paisaje cafetero
        banner = tk.Canvas(self, height=112, highlightthickness=0, bg=e.CREMA)
        banner.pack(fill="x")
        subtitulo = {"Productor": "Mis datos, mis fincas, mis lotes y los negocios que me proponen",
                     "Comprador": f"Comprador de {sesion.get('cooperativa') or 'su cooperativa'}"}.get(
            sesion["perfil"], "Panel de gestión cafetera · Sector agropecuario")

        def dibujar_banner(_evento=None):
            ancho = max(banner.winfo_width(), 900)
            e.paisaje_cafetero(banner, ancho, 112, con_taza=False, nivel=0.30)
            e.rama_cafeto(banner, ancho - 10, 110, 0.65, invertir=True)
            e.taza(banner, ancho * 0.58, 56, 0.5)
            banner.create_text(32, 30, anchor="w", text=f"¡Bienvenido(a), {sesion['nombre'].split()[0]}!",
                               font=(e.FUENTE, 24, "bold"), fill=e.CAFE_OSCURO)
            banner.create_text(34, 60, anchor="w", font=(e.FUENTE, 12), fill=e.CAFE_OSCURO, text=subtitulo)
            banner.create_text(34, 82, anchor="w", font=(e.FUENTE, 10, "italic"), fill=e.CAFE,
                               text="Seleccione un módulo en las tarjetas de abajo o en el menú Gestión.")
        banner.bind("<Configure>", dibujar_banner)

        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=24, pady=8)

        # Tarjetas de estadísticas
        self.frame_stats = tk.Frame(cuerpo, bg=e.CREMA)
        self.frame_stats.pack(fill="x")
        self.actualizar_estadisticas()

        # Tarjetas de módulos, en dos grupos
        for grupo, modulos_grupo in MODULOS:
            tk.Label(cuerpo, text=grupo, font=e.F_SUBTITULO, bg=e.CREMA,
                     fg=e.CAFE_OSCURO).pack(anchor="w", pady=(8, 3))
            fila_tarjetas = tk.Frame(cuerpo, bg=e.CREMA)
            fila_tarjetas.pack(fill="x")
            for columna in range(5):
                fila_tarjetas.columnconfigure(columna, weight=1, uniform="tarjetas")
            for columna, (entidad, icono, titulo, texto) in enumerate(modulos_grupo):
                self._tarjeta_modulo(fila_tarjetas, columna, entidad, icono, titulo, texto, entidad in permisos)

    def _tarjeta_modulo(self, contenedor, columna, entidad, icono, titulo, texto, permitido):
        tarjeta = tk.Frame(contenedor, bg=e.BLANCO, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
        tarjeta.grid(row=0, column=columna, sticky="nsew", padx=(0 if columna == 0 else 10, 0))
        cabeza = tk.Frame(tarjeta, bg=e.BLANCO)
        cabeza.pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(cabeza, text=icono, font=(e.FUENTE, 18), bg=e.BLANCO,
                 fg=e.VERDE if permitido else e.GRIS).pack(side="left")
        tk.Label(cabeza, text=titulo, font=e.F_SUBTITULO, bg=e.BLANCO, fg=e.CAFE_OSCURO).pack(side="left", padx=6)
        tk.Label(tarjeta, text=texto, font=e.F_PEQUENA, bg=e.BLANCO, fg=e.GRIS, justify="left",
                 wraplength=190).pack(anchor="w", padx=12, pady=(2, 6))
        b = e.boton(tarjeta, "Abrir" if permitido else "Sin permiso", lambda n=entidad: self.abrir_gestion(n),
                    e.VERDE if permitido else e.GRIS, fuente=e.F_PEQUENA)
        b.pack(anchor="w", padx=12, pady=(0, 8))
        if not permitido:
            e.deshabilitar(b)

    def actualizar_estadisticas(self):
        if not getattr(self, "frame_stats", None) or not self.frame_stats.winfo_exists():
            return
        for hijo in self.frame_stats.winfo_children():
            hijo.destroy()
        resultado = LogicaAcceso.resumen_panel()
        datos = resultado["datos"] if resultado["exito"] else {}
        tarjetas = [("Productores activos", datos.get("productores", "—"), e.VERDE),
                    ("Fincas activas", datos.get("fincas", "—"), e.VERDE_OSCURO),
                    ("Cooperativas activas", datos.get("cooperativas", "—"), e.CAFE),
                    ("Variedades de café", datos.get("variedades", "—"), e.DORADO),
                    ("Lotes con café", datos.get("lotes", "—"), "#827717"),
                    ("Negocios en curso", datos.get("negocios", "—"), e.CEREZA),
                    ("Usuarios activos", datos.get("usuarios", "—"), e.CAFE_CLARO)]
        for columna, (titulo, valor, color) in enumerate(tarjetas):
            t = tk.Frame(self.frame_stats, bg=color)
            t.grid(row=0, column=columna, sticky="nsew", padx=(0 if columna == 0 else 12, 0))
            self.frame_stats.columnconfigure(columna, weight=1)
            tk.Label(t, text=str(valor), font=(e.FUENTE, 20, "bold"), bg=color, fg=e.BLANCO).pack(
                anchor="w", padx=14, pady=(6, 0))
            tk.Label(t, text=titulo, font=e.F_NORMAL, bg=color, fg=e.BLANCO).pack(anchor="w", padx=14,
                                                                                  pady=(0, 8))

    def abrir_gestion(self, entidad):
        permitidas = permisos_de(self.sesion["perfil"]).get(entidad)
        if not permitidas:
            messagebox.showwarning("Permisos", f"Su perfil no tiene acceso a Gestión {entidad}.", parent=self)
            return
        abrir = {"Perfil": formularios.abrir_perfil, "Persona": formularios.abrir_persona,
                 "Usuario": formularios.abrir_usuario,
                 "Productor": formularios.abrir_productor, "Finca": formularios.abrir_finca,
                 "Cooperativa": formularios.abrir_cooperativa, "Asociacion": formularios.abrir_asociacion,
                 "Variedad": formularios.abrir_variedad, "Lote": formularios.abrir_lote,
                 "Catalogo": ventanas_comercial.abrir_catalogo, "Negocio": ventanas_comercial.abrir_negocios,
                 "Mensaje": ventanas_comercial.abrir_mensajes}[entidad]
        abrir(self, self.sesion, permitidas, al_cerrar=self.actualizar_estadisticas)

    def cerrar_sesion(self):
        if messagebox.askyesno("Cerrar sesión", "¿Desea cerrar la sesión?", parent=self):
            self.mostrar_login()


class VentanaRecuperacion(tk.Toplevel):
    """Activa un campo para digitar el usuario, el correo o la identificación."""

    def __init__(self, master, dato_inicial=""):
        super().__init__(master)
        self.title("Recuperar usuario / contraseña")
        self.configure(bg=e.BLANCO)
        self.resizable(False, False)
        e.centrar(self, 470, 300)
        self.transient(master)
        self.grab_set()

        tk.Label(self, text="Recuperar usuario y contraseña", font=e.F_SUBTITULO, bg=e.BLANCO,
                 fg=e.CAFE_OSCURO).pack(anchor="w", padx=24, pady=(22, 4))
        tk.Label(self, text="Digite su nombre de usuario, su correo electrónico o su número de\n"
                            "identificación. Le enviaremos sus datos al correo registrado.",
                 font=e.F_PEQUENA, bg=e.BLANCO, fg=e.GRIS, justify="left").pack(anchor="w", padx=24)
        tk.Label(self, text="Usuario, correo o identificación", font=e.F_NEGRITA, bg=e.BLANCO,
                 fg=e.TEXTO).pack(anchor="w", padx=24, pady=(16, 2))
        self.txt_dato = tk.Entry(self, font=(e.FUENTE, 12), width=36, relief="solid", bd=1)
        self.txt_dato.pack(padx=24, ipady=5, anchor="w")
        self.txt_dato.insert(0, dato_inicial)
        self.txt_dato.focus_set()
        self.txt_dato.bind("<Return>", lambda ev: self.f_enviar())

        self.lbl_estado = tk.Label(self, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.CAFE)
        self.lbl_estado.pack(anchor="w", padx=24, pady=(6, 0))

        botones = tk.Frame(self, bg=e.BLANCO)
        botones.pack(fill="x", padx=24, pady=12)
        self.btn_enviar = e.boton(botones, "Enviar al correo", self.f_enviar, e.VERDE)
        self.btn_enviar.pack(side="left")
        e.boton(botones, "Cancelar", self.destroy, e.CAFE_CLARO).pack(side="left", padx=10)

    def f_enviar(self):
        self.lbl_estado.config(text="Enviando correo, espere un momento…")
        self.config(cursor="watch")
        self.btn_enviar.config(state="disabled")
        self.update()
        resultado = LogicaAcceso.procesar_recuperacion(self.txt_dato.get())
        self.config(cursor="")
        self.btn_enviar.config(state="normal")
        self.lbl_estado.config(text="")
        if resultado["exito"]:
            messagebox.showinfo("Recuperación de credenciales",
                                f"{resultado['mensaje']}\n\n({resultado['datos']['correo']})", parent=self)
            self.destroy()
        else:
            messagebox.showwarning("Recuperación de credenciales", resultado["mensaje"], parent=self)


if __name__ == "__main__":
    Aplicacion().mainloop()
