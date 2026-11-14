import tkinter as tk
from tkinter import messagebox

import estilos as e
import formularios
from negocio import LogicaAcceso, PERMISOS, permisos_de


class Aplicacion(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Café Conecta")
        self.configure(bg=e.CREMA)
        e.configurar_estilos(self)
        self.sesion = None
        self.mostrar_login()

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

        self.bind("<Return>", lambda ev: self.f_ingresar())
        (self.txt_contrasena if usuario_sugerido else self.txt_usuario).focus_set()

    def f_ingresar(self):
        resultado = LogicaAcceso.autenticar_usuario(self.txt_usuario.get(), self.txt_contrasena.get())
        if not resultado["exito"]:
            messagebox.showwarning("Acceso al sistema", resultado["mensaje"], parent=self)
            return
        self.unbind("<Return>")
        self.mostrar_panel(resultado["datos"])

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
        e.centrar(self, 1120, 720)
        self.minsize(980, 660)

        # Menú superior
        barra_menu = tk.Menu(self)
        menu_gestion = tk.Menu(barra_menu, tearoff=0)
        for nombre in ("Perfil", "Usuario", "Persona"):
            menu_gestion.add_command(label=f"Gestión {nombre}", command=lambda n=nombre: self.abrir_gestion(n),
                                     state="normal" if nombre in permisos else "disabled")
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
        banner = tk.Canvas(self, height=210, highlightthickness=0, bg=e.CREMA)
        banner.pack(fill="x")

        def dibujar_banner(_evento=None):
            ancho = max(banner.winfo_width(), 900)
            e.paisaje_cafetero(banner, ancho, 210, con_taza=False, nivel=0.28)
            e.rama_cafeto(banner, ancho - 10, 205, 0.9, invertir=True)
            e.taza(banner, ancho * 0.56, 100, 0.75)
            banner.create_text(32, 50, anchor="w", text=f"¡Bienvenido(a), {sesion['nombre'].split()[0]}!",
                               font=(e.FUENTE, 24, "bold"), fill=e.CAFE_OSCURO)
            banner.create_text(34, 86, anchor="w", font=(e.FUENTE, 12),
                               fill=e.CAFE_OSCURO,
                               text="Panel de gestión cafetera · Sector agropecuario")
            banner.create_text(34, 110, anchor="w", font=(e.FUENTE, 10, "italic"), fill=e.CAFE,
                               text="Seleccione un módulo en las tarjetas de abajo o en el menú Gestión.")
        banner.bind("<Configure>", dibujar_banner)

        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=24, pady=16)

        # Tarjetas de estadísticas
        self.frame_stats = tk.Frame(cuerpo, bg=e.CREMA)
        self.frame_stats.pack(fill="x")
        self.actualizar_estadisticas()

        # Tarjetas de módulos
        tk.Label(cuerpo, text="Módulos de gestión", font=e.F_SUBTITULO, bg=e.CREMA,
                 fg=e.CAFE_OSCURO).pack(anchor="w", pady=(18, 8))
        modulos = tk.Frame(cuerpo, bg=e.CREMA)
        modulos.pack(fill="x")
        datos_modulos = [
            ("Perfil", "⚙", "Gestión Perfil", "Tipos de usuario: administrador,\ncaficultor, catador, cliente…"),
            ("Persona", "☘", "Gestión Persona", "Caficultores, recolectores,\nempleados y clientes."),
            ("Usuario", "☺", "Gestión Usuario", "Cuentas de acceso al sistema\npara cada persona registrada."),
        ]
        for columna, (entidad, icono, titulo, texto) in enumerate(datos_modulos):
            permitido = entidad in permisos
            tarjeta = tk.Frame(modulos, bg=e.BLANCO, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
            tarjeta.grid(row=0, column=columna, sticky="nsew", padx=(0 if columna == 0 else 12, 0))
            modulos.columnconfigure(columna, weight=1)
            tk.Label(tarjeta, text=icono, font=(e.FUENTE, 26), bg=e.BLANCO,
                     fg=e.VERDE if permitido else e.GRIS).pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(tarjeta, text=titulo, font=e.F_SUBTITULO, bg=e.BLANCO, fg=e.CAFE_OSCURO).pack(
                anchor="w", padx=16)
            tk.Label(tarjeta, text=texto, font=e.F_PEQUENA, bg=e.BLANCO, fg=e.GRIS, justify="left").pack(
                anchor="w", padx=16, pady=(2, 10))
            b = e.boton(tarjeta, "Abrir" if permitido else "Sin permiso",
                        lambda n=entidad: self.abrir_gestion(n), e.VERDE if permitido else e.GRIS)
            b.pack(anchor="w", padx=16, pady=(0, 14))
            if not permitido:
                e.deshabilitar(b)

        # Ciclo del café (franja informativa)
        ciclo = tk.Canvas(cuerpo, height=66, bg=e.CREMA, highlightthickness=0)
        ciclo.pack(fill="x", pady=(18, 0))

        def dibujar_ciclo(_evento=None):
            ciclo.delete("all")
            pasos = ["Siembra", "Cultivo", "Cosecha", "Beneficio", "Secado", "Tostión", "Taza"]
            ancho = max(ciclo.winfo_width(), 800)
            paso_x = ancho / len(pasos)
            ciclo.create_line(paso_x / 2, 24, ancho - paso_x / 2, 24, fill=e.CAFE_CLARO, width=3, dash=(6, 4))
            for i, nombre in enumerate(pasos):
                x = paso_x * i + paso_x / 2
                color = e.CEREZA if nombre == "Cosecha" else (e.CAFE_OSCURO if i >= 5 else e.VERDE)
                ciclo.create_oval(x - 14, 10, x + 14, 38, fill=color, outline=e.BLANCO, width=3)
                ciclo.create_text(x, 24, text=str(i + 1), fill=e.BLANCO, font=e.F_NEGRITA)
                ciclo.create_text(x, 54, text=nombre, fill=e.CAFE_OSCURO, font=e.F_PEQUENA)
        ciclo.bind("<Configure>", dibujar_ciclo)

    def actualizar_estadisticas(self):
        if not getattr(self, "frame_stats", None) or not self.frame_stats.winfo_exists():
            return
        for hijo in self.frame_stats.winfo_children():
            hijo.destroy()
        resultado = LogicaAcceso.resumen_panel()
        datos = resultado["datos"] if resultado["exito"] else {}
        tarjetas = [("Personas activas", datos.get("personas", "—"), e.VERDE),
                    ("Usuarios activos", datos.get("usuarios", "—"), e.CAFE),
                    ("Perfiles activos", datos.get("perfiles", "—"), e.DORADO)]
        for columna, (titulo, valor, color) in enumerate(tarjetas):
            t = tk.Frame(self.frame_stats, bg=color)
            t.grid(row=0, column=columna, sticky="nsew", padx=(0 if columna == 0 else 12, 0))
            self.frame_stats.columnconfigure(columna, weight=1)
            tk.Label(t, text=str(valor), font=(e.FUENTE, 24, "bold"), bg=color, fg=e.BLANCO).pack(
                anchor="w", padx=16, pady=(8, 0))
            tk.Label(t, text=titulo, font=e.F_NORMAL, bg=color, fg=e.BLANCO).pack(anchor="w", padx=16,
                                                                                  pady=(0, 10))

    def abrir_gestion(self, entidad):
        permitidas = permisos_de(self.sesion["perfil"]).get(entidad)
        if not permitidas:
            messagebox.showwarning("Permisos", f"Su perfil no tiene acceso a Gestión {entidad}.", parent=self)
            return
        abrir = {"Perfil": formularios.abrir_perfil, "Persona": formularios.abrir_persona,
                 "Usuario": formularios.abrir_usuario}[entidad]
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
