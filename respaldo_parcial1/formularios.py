import tkinter as tk
from tkinter import messagebox, ttk

import estilos as e
from negocio import ACTIVO, LogicaPerfil, LogicaPersona, LogicaUsuario, es_administrador


class FormularioCRUD(tk.Toplevel):
  
    def __init__(self, master, logica, titulo, descripcion, campos, columnas, sesion,
                 permitidas, icono="☕", valores_iniciales=None, bloqueados=(),
                 al_guardar=None, al_cerrar=None, botones_extra=(), columnas_form=1):
        super().__init__(master)
        self.logica = logica
        self.campos = campos
        self.columnas = columnas
        self.id_clave = columnas[0][0]
        self.sesion = sesion
        self.permitidas = permitidas
        self.valores_iniciales = valores_iniciales or {}
        self.bloqueados = set(bloqueados)
        self.al_guardar = al_guardar
        self.al_cerrar = al_cerrar
        self.id_actual = None
        self.estado_actual = None
        self.filas = {}
        self.widgets = {}
        self.mapa_combo = {}

        self.title(f"Café Conecta - Gestión {titulo}")
        self.configure(bg=e.CREMA)
        self.protocol("WM_DELETE_WINDOW", self.f_salir)
        con_lista = "Consultar" in permitidas
        arriba = columnas_form > 1
        if arriba:
            e.centrar(self, 1120, 740 if con_lista else 480)
        else:
            e.centrar(self, 1080 if con_lista else 640, 640)
        self.minsize(820 if arriba else 600, 460)

        # Encabezado
        cab = tk.Frame(self, bg=e.CAFE_OSCURO, height=70)
        cab.pack(fill="x")
        tk.Label(cab, text=f"{icono}  Gestión {titulo}", font=e.F_TITULO, bg=e.CAFE_OSCURO,
                 fg=e.BLANCO).pack(side="left", padx=20, pady=12)
        tk.Label(cab, text=descripcion, font=e.F_NORMAL, bg=e.CAFE_OSCURO,
                 fg=e.DORADO).pack(side="left", padx=4, pady=18)

        # Botones de comando
        barra = tk.Frame(self, bg=e.CREMA_OSCURO)
        barra.pack(fill="x")
        self.botones = {}
        definicion = [("Crear", "✚  Crear", self.f_crear, e.VERDE),
                      ("Consultar", "☰  Consultar", self.f_consultar, e.CAFE),
                      ("Modificar", "✎  Modificar", self.f_modificar, "#ef6c00"),
                      ("Guardar", "✔  Guardar", self.f_guardar, e.VERDE_OSCURO),
                      ("Inhabilitar", "⊘  Inhabilitar", self.f_inhabilitar, e.CEREZA),
                      ("Salir", "↩  Salir", self.f_salir, e.CAFE_OSCURO)]
        for accion, texto, comando, color in definicion:
            b = e.boton(barra, texto, comando, color)
            b.pack(side="left", padx=5, pady=10)
            if accion not in permitidas:
                e.deshabilitar(b)
            self.botones[accion] = b
        for texto, comando, color in botones_extra:
            e.boton(barra, texto, comando, color).pack(side="right", padx=8, pady=10)

        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)

        # Formulario
        caja = tk.Frame(cuerpo, bg=e.BLANCO, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
        if arriba:
            caja.pack(side="top", fill="x", pady=(0, 12))
        else:
            caja.pack(side="left", fill="y", padx=(0, 14))
        ancho_campo = 34 if columnas_form == 1 else 30
        tk.Label(caja, text="Datos del registro", font=e.F_SUBTITULO, bg=e.BLANCO,
                 fg=e.CAFE_OSCURO).grid(row=0, column=0, columnspan=columnas_form * 2, sticky="w",
                                        padx=16, pady=(14, 2))
        self.lbl_modo = tk.Label(caja, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.GRIS)
        self.lbl_modo.grid(row=1, column=0, columnspan=columnas_form * 2, sticky="w", padx=16, pady=(0, 4))

        for n, campo in enumerate(campos):
            fila = 2 + (n // columnas_form) * 3
            col = (n % columnas_form) * 2
            texto = campo["etiqueta"] + (" *" if campo.get("obligatorio") else "")
            tk.Label(caja, text=texto, font=e.F_NEGRITA, bg=e.BLANCO, fg=e.TEXTO).grid(
                row=fila, column=col, sticky="w", padx=16, pady=(6, 0))
            if campo["tipo"] == "combo":
                w = ttk.Combobox(caja, state="readonly", width=ancho_campo - 2, font=e.F_NORMAL)
            else:
                w = tk.Entry(caja, width=ancho_campo, font=e.F_NORMAL, relief="solid", bd=1,
                             show="•" if campo["tipo"] == "clave" else "")
            w.grid(row=fila + 1, column=col, sticky="we", padx=16, ipady=3)
            if campo["tipo"] == "clave":
                self.var_ver = tk.BooleanVar()
                tk.Checkbutton(caja, text="Ver", variable=self.var_ver, bg=e.BLANCO, font=e.F_PEQUENA,
                               command=lambda w=w: w.config(show="" if self.var_ver.get() else "•")
                               ).grid(row=fila + 1, column=col + 1, padx=(0, 10))
            if campo.get("ayuda"):
                tk.Label(caja, text=campo["ayuda"], font=(e.FUENTE, 8), bg=e.BLANCO, fg=e.GRIS).grid(
                    row=fila + 2, column=col, sticky="w", padx=16)
            self.widgets[campo["clave"]] = w
        ultima = 2 + ((len(campos) - 1) // columnas_form + 1) * 3
        tk.Label(caja, text="* Campos obligatorios", font=(e.FUENTE, 8, "italic"), bg=e.BLANCO,
                 fg=e.GRIS).grid(row=ultima, column=0, sticky="w", padx=16, pady=(8, 12))

        # Lista de registros (solo si puede consultar)
        if con_lista:
            derecha = tk.Frame(cuerpo, bg=e.CREMA)
            derecha.pack(side="top" if arriba else "left", fill="both", expand=True)
            busca = tk.Frame(derecha, bg=e.CREMA)
            busca.pack(fill="x", pady=(0, 8))
            tk.Label(busca, text="Buscar:", font=e.F_NEGRITA, bg=e.CREMA, fg=e.TEXTO).pack(side="left")
            self.txt_buscar = tk.Entry(busca, font=e.F_NORMAL, relief="solid", bd=1)
            self.txt_buscar.pack(side="left", fill="x", expand=True, padx=8, ipady=3)
            self.txt_buscar.bind("<Return>", lambda ev: self.f_consultar())
            tk.Label(derecha, text="Clic sobre un registro para cargarlo en el formulario. "
                                   "Los registros inactivos aparecen en gris.",
                     font=e.F_PEQUENA, bg=e.CREMA, fg=e.GRIS).pack(anchor="w")

            marco = tk.Frame(derecha)
            marco.pack(fill="both", expand=True, pady=(4, 0))
            self.tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings",
                                      selectmode="browse")
            for clave, titulo_col, ancho in columnas:
                self.tabla.heading(clave, text=titulo_col)
                self.tabla.column(clave, width=ancho, anchor="w", stretch=True)
            self.tabla.tag_configure("inactivo", foreground="#9e9e9e", background="#f5f5f5")
            barra_v = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
            self.tabla.configure(yscrollcommand=barra_v.set)
            self.tabla.pack(side="left", fill="both", expand=True)
            barra_v.pack(side="right", fill="y")
            self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar)
            self.lbl_total = tk.Label(derecha, text="", font=e.F_PEQUENA, bg=e.CREMA, fg=e.GRIS)
            self.lbl_total.pack(anchor="e", pady=(4, 0))
        else:
            self.tabla = None

        self.f_crear()
        if self.tabla is not None:
            self.cargar_lista()

   
    def _mostrar(self, resultado, titulo):
        if resultado["exito"]:
            messagebox.showinfo(titulo, resultado["mensaje"], parent=self)
        else:
            messagebox.showwarning(titulo, resultado["mensaje"], parent=self)

    def _actualizar_modo(self):
        if self.id_actual is None:
            self.lbl_modo.config(text="Modo: nuevo registro (complete los datos y presione Guardar)", fg=e.VERDE)
            self.botones["Inhabilitar"].config(text="⊘  Inhabilitar")
        else:
            color = e.VERDE if self.estado_actual == ACTIVO else e.CEREZA
            self.lbl_modo.config(text=f"Modo: editando ID {self.id_actual}  ·  Estado: {self.estado_actual}", fg=color)
            self.botones["Inhabilitar"].config(
                text="⊘  Inhabilitar" if self.estado_actual == ACTIVO else "✓  Activar")

    def _refrescar_combos(self):
        for campo in self.campos:
            if campo["tipo"] != "combo":
                continue
            resultado = campo["opciones"](self.id_actual)
            if not resultado["exito"]:
                messagebox.showwarning("Datos", resultado["mensaje"], parent=self)
                continue
            opciones = resultado["datos"]
            self.mapa_combo[campo["clave"]] = {texto: id_ for id_, texto in opciones}
            self.widgets[campo["clave"]]["values"] = [texto for _, texto in opciones]

    def _poner(self, clave, valor):
        w = self.widgets[clave]
        if isinstance(w, ttk.Combobox):
            texto = next((t for t, i in self.mapa_combo.get(clave, {}).items() if i == valor), "")
            w.set(texto)
        else:
            estado = w.cget("state")
            w.config(state="normal")
            w.delete(0, "end")
            w.insert(0, "" if valor is None else str(valor))
            w.config(state=estado)

    def _leer(self):
        datos = {}
        for clave, w in self.widgets.items():
            if isinstance(w, ttk.Combobox):
                datos[clave] = self.mapa_combo.get(clave, {}).get(w.get())
            else:
                datos[clave] = w.get()
        return datos

    def _aplicar_bloqueos(self):
        for clave in self.bloqueados:
            self.widgets[clave].config(state="disabled")

    def cargar_lista(self, filtro="", seleccionar=None):
        if self.tabla is None:
            return
        resultado = self.logica.listar(filtro, self.sesion)
        if not resultado["exito"]:
            messagebox.showerror("Consultar", resultado["mensaje"], parent=self)
            return
        self.tabla.delete(*self.tabla.get_children())
        self.filas = {}
        for fila in resultado["datos"]:
            valores = ["" if fila.get(c) is None else fila.get(c) for c, _, _ in self.columnas]
            iid = str(fila[self.id_clave])
            etiqueta = () if fila.get("estado") == ACTIVO else ("inactivo",)
            self.tabla.insert("", "end", iid=iid, values=valores, tags=etiqueta)
            self.filas[iid] = fila
        total = len(resultado["datos"])
        self.lbl_total.config(text=f"{total} registro(s) encontrado(s)")
        if seleccionar is not None and str(seleccionar) in self.filas:
            self.tabla.selection_set(str(seleccionar))
            self.tabla.see(str(seleccionar))
        return resultado["datos"]

    def _al_seleccionar(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        fila = self.filas[seleccion[0]]
        self.id_actual = fila[self.id_clave]
        self.estado_actual = fila.get("estado")
        self._refrescar_combos()
        for campo in self.campos:
            self._poner(campo["clave"], fila.get(campo["clave"]))
        self._actualizar_modo()

   
    def f_crear(self):
        """Limpia el formulario para ingresar un registro nuevo."""
        self.id_actual = None
        self.estado_actual = None
        if self.tabla is not None:
            self.tabla.selection_remove(self.tabla.selection())
        for w in self.widgets.values():
            w.config(state="normal" if isinstance(w, tk.Entry) else "readonly")
        self._refrescar_combos()
        for campo in self.campos:
            self._poner(campo["clave"], self.valores_iniciales.get(campo["clave"]))
        self._aplicar_bloqueos()
        self._actualizar_modo()
        primero = next((w for c, w in self.widgets.items() if c not in self.bloqueados), None)
        if primero is not None:
            primero.focus_set()

    def f_consultar(self):
        filtro = self.txt_buscar.get().strip()
        datos = self.cargar_lista(filtro)
        if datos is None:
            return
        if not datos:
            messagebox.showinfo("Consultar", "No se encontraron registros con ese criterio.", parent=self)
        elif len(datos) == 1 and filtro:
            iid = str(datos[0][self.id_clave])
            self.tabla.selection_set(iid)

    def f_guardar(self):
        if self.id_actual is not None:
            messagebox.showinfo("Guardar", "Este registro ya existe.\nPara cambiar sus datos use Modificar, "
                                           "o presione Crear para ingresar uno nuevo.", parent=self)
            return
        resultado = self.logica.guardar(self._leer(), self.sesion)
        self._mostrar(resultado, "Guardar")
        if resultado["exito"]:
            nuevo_id = resultado["datos"]
            if self.al_guardar:
                self.al_guardar(nuevo_id, self)
                return
            self.f_crear()
            self.cargar_lista(seleccionar=nuevo_id)

    def f_modificar(self):
        if self.id_actual is None:
            messagebox.showinfo("Modificar", "Primero seleccione en la lista el registro que desea modificar.",
                                parent=self)
            return
        if not messagebox.askyesno("Modificar", f"¿Desea guardar los cambios del registro ID {self.id_actual}?",
                                   parent=self):
            return
        resultado = self.logica.modificar(self.id_actual, self._leer(), self.sesion)
        self._mostrar(resultado, "Modificar")
        if resultado["exito"]:
            self.cargar_lista(self.txt_buscar.get().strip(), seleccionar=self.id_actual)

    def f_inhabilitar(self):
        if self.id_actual is None:
            messagebox.showinfo("Inhabilitar", "Primero seleccione en la lista el registro.", parent=self)
            return
        accion = "inhabilitar" if self.estado_actual == ACTIVO else "activar"
        if not messagebox.askyesno(accion.capitalize(),
                                   f"¿Desea {accion} el registro ID {self.id_actual}?\n\n"
                                   "No se borra de la base de datos: solo cambia su estado.", parent=self):
            return
        resultado = self.logica.cambiar_estado(self.id_actual, self.estado_actual, self.sesion)
        self._mostrar(resultado, accion.capitalize())
        if resultado["exito"]:
            self.cargar_lista(self.txt_buscar.get().strip(), seleccionar=self.id_actual)

    def f_salir(self):
        self.destroy()
        if self.al_cerrar:
            self.al_cerrar()



def abrir_perfil(master, sesion, permitidas, al_cerrar=None):
    campos = [{"clave": "descripc", "etiqueta": "Descripción del perfil", "tipo": "texto",
               "obligatorio": True, "ayuda": "Ej.: Administrador, Persona, Caficultor, Catador"}]
    columnas = [("Idperfil", "ID", 60), ("descripc", "Descripción", 300), ("estado", "Estado", 100)]
    return FormularioCRUD(master, LogicaPerfil, "Perfil", "Tipos de usuario y sus permisos", campos,
                          columnas, sesion, permitidas, icono="⚙", al_cerrar=al_cerrar)


CAMPOS_PERSONA = [
    {"clave": "nom1", "etiqueta": "Primer nombre", "tipo": "texto", "obligatorio": True},
    {"clave": "nom2", "etiqueta": "Segundo nombre", "tipo": "texto"},
    {"clave": "apell1", "etiqueta": "Primer apellido", "tipo": "texto", "obligatorio": True},
    {"clave": "apell2", "etiqueta": "Segundo apellido", "tipo": "texto"},
    {"clave": "direccion", "etiqueta": "Dirección / Finca", "tipo": "texto"},
    {"clave": "tele", "etiqueta": "Teléfono fijo", "tipo": "texto"},
    {"clave": "movil", "etiqueta": "Celular", "tipo": "texto", "obligatorio": True,
     "ayuda": "10 números, empieza por 3"},
    {"clave": "correo", "etiqueta": "Correo electrónico", "tipo": "texto", "obligatorio": True},
    {"clave": "fecha_nac", "etiqueta": "Fecha de nacimiento", "tipo": "texto",
     "ayuda": "Formato AAAA-MM-DD (ej.: 1995-08-21)"},
]
COLUMNAS_PERSONA = [("Idpersona", "ID", 45), ("nom1", "Nombre", 95), ("nom2", "2º nombre", 90),
                    ("apell1", "Apellido", 95), ("apell2", "2º apellido", 90), ("direccion", "Dirección", 140),
                    ("movil", "Celular", 95), ("correo", "Correo", 180), ("fecha_nac", "Nacimiento", 90),
                    ("estado", "Estado", 70)]


def abrir_persona(master, sesion, permitidas, al_cerrar=None):
    extra = []
    formulario = None

    def crear_usuario():
        if formulario.id_actual is None:
            messagebox.showinfo("Crear usuario", "Seleccione primero la persona en la lista.", parent=formulario)
            return
        abrir_usuario(master, sesion, ("Crear", "Consultar", "Modificar", "Guardar", "Inhabilitar", "Salir"),
                      persona_inicial=formulario.id_actual)

    if es_administrador(sesion):
        extra.append(("☺  Crear usuario a esta persona", crear_usuario, e.CAFE_CLARO))
    formulario = FormularioCRUD(master, LogicaPersona, "Persona", "Productores, clientes y empleados",
                                CAMPOS_PERSONA, COLUMNAS_PERSONA, sesion, permitidas, icono="☘",
                                al_cerrar=al_cerrar, botones_extra=extra, columnas_form=3)
    return formulario


def _campos_usuario(persona_fija=None, perfil_fijo=None):
    def opciones_perfil(_id):
        if perfil_fijo is not None:
            r = LogicaUsuario.opciones_perfil()
            if r["exito"]:
                r["datos"] = [o for o in r["datos"] if o[0] == perfil_fijo]
            return r
        return LogicaUsuario.opciones_perfil()

    def opciones_persona(id_usuario_actual):
        # Al modificar se incluye la persona que ya tiene asignada el usuario.
        incluir = persona_fija
        if id_usuario_actual is not None and opciones_persona.formulario is not None:
            fila = opciones_persona.formulario.filas.get(str(id_usuario_actual))
            incluir = fila["idpersona"] if fila else incluir
        resultado = LogicaUsuario.opciones_persona(incluir)
        if persona_fija is not None and resultado["exito"]:
            resultado["datos"] = [o for o in resultado["datos"] if o[0] == persona_fija]
        return resultado
    opciones_persona.formulario = None

    campos = [
        {"clave": "nombreu", "etiqueta": "Nombre de usuario", "tipo": "texto", "obligatorio": True,
         "ayuda": "4 a 20 caracteres, sin espacios"},
        {"clave": "contrasena", "etiqueta": "Contraseña", "tipo": "clave", "obligatorio": True,
         "ayuda": "Mínimo 6 caracteres, con letras y números"},
        {"clave": "idperfil", "etiqueta": "Perfil", "tipo": "combo", "obligatorio": True,
         "opciones": opciones_perfil},
        {"clave": "idpersona", "etiqueta": "Persona", "tipo": "combo", "obligatorio": True,
         "opciones": opciones_persona, "ayuda": "Solo aparecen personas activas que aún no tienen usuario"},
    ]
    return campos, opciones_persona


def abrir_usuario(master, sesion, permitidas, persona_inicial=None, al_cerrar=None):
    campos, opciones_persona = _campos_usuario()
    columnas = [("Idusuario", "ID", 50), ("nombreu", "Usuario", 130), ("perfil", "Perfil", 130),
                ("persona", "Persona", 200), ("estado", "Estado", 80)]
    formulario = FormularioCRUD(master, LogicaUsuario, "Usuario", "Acceso al sistema de cada persona",
                                campos, columnas, sesion, permitidas, icono="☺",
                                valores_iniciales={"idpersona": persona_inicial} if persona_inicial else None,
                                al_cerrar=al_cerrar)
    opciones_persona.formulario = formulario
    return formulario


def abrir_registro(master, permisos_registro, al_terminar):
    """Gestión Persona en modo registro y, al guardar, la creación de su usuario."""

    def persona_guardada(id_persona, form_persona):
        form_persona.destroy()
        perfil = LogicaUsuario.id_perfil_registro()
        if not perfil["exito"]:
            messagebox.showwarning("Registro", perfil["mensaje"], parent=master)
            return
        campos, _ = _campos_usuario(persona_fija=id_persona, perfil_fijo=perfil["datos"])
        messagebox.showinfo("Registro", "Ahora cree su usuario y contraseña para ingresar al sistema.",
                            parent=master)
        FormularioCRUD(master, LogicaUsuario, "Usuario", "Paso 2 de 2: cree su acceso", campos,
                       [("Idusuario", "ID", 50)], None, permisos_registro["Usuario"], icono="☺",
                       valores_iniciales={"idperfil": perfil["datos"], "idpersona": id_persona},
                       bloqueados=("idperfil", "idpersona"), al_guardar=usuario_guardado)

    def usuario_guardado(_id_usuario, form_usuario):
        nombre = form_usuario.widgets["nombreu"].get().strip()
        form_usuario.destroy()
        messagebox.showinfo("Registro", "¡Registro completo! Ya puede ingresar con su usuario y contraseña.",
                            parent=master)
        al_terminar(nombre)

    return FormularioCRUD(master, LogicaPersona, "Persona", "Paso 1 de 2: sus datos personales",
                          CAMPOS_PERSONA, COLUMNAS_PERSONA, None, permisos_registro["Persona"],
                          icono="☘", al_guardar=persona_guardada, columnas_form=3)
