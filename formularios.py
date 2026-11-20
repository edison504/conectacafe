import base64
import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import estilos as e
from negocio import (ACTIVO, LogicaAsociacion, LogicaCooperativa, LogicaFinca, LogicaListas, LogicaLote,
                     LogicaPerfil, LogicaPersona, LogicaProductor, LogicaUbicacion, LogicaUsuario, LogicaVariedad,
                     es_administrador)

try:  # Pillow permite ver imágenes JPG; sin Pillow solo se ven las PNG.
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None


def miniatura(contenido, ancho=170, alto=110):
    """Convierte los bytes de una imagen JPG o PNG en una imagen pequeña para Tkinter."""
    if not contenido:
        return None
    try:
        if Image is not None:
            imagen = Image.open(io.BytesIO(contenido))
            imagen.thumbnail((ancho, alto))
            return ImageTk.PhotoImage(imagen)
        if contenido.startswith(b"\x89PNG"):
            foto = tk.PhotoImage(data=base64.b64encode(contenido))
            factor = max(1, -(-foto.width() // ancho), -(-foto.height() // alto))
            return foto.subsample(factor, factor)
    except Exception:
        return None
    return None


class FormularioCRUD(tk.Toplevel):
    """
    campos: lista de diccionarios con
        clave, etiqueta, tipo ('texto' | 'clave' | 'combo' | 'imagen'), obligatorio, ayuda,
        opciones (combo: función que recibe el id del registro y devuelve [(id, texto)]),
        depende_de (combo que se llena según otro combo, ej.: municipio depende de departamento),
        llave (True si es la llave primaria: no se puede modificar),
        cargar (imagen: función que trae la imagen guardada del registro).
    columnas: lista de (clave_del_dato, titulo, ancho). La primera es la llave del registro.
    filtros: combos opcionales sobre la lista (ej.: departamento, municipio, productor).
    """

    def __init__(self, master, logica, titulo, descripcion, campos, columnas, sesion,
                 permitidas, icono="☕", valores_iniciales=None, bloqueados=(),
                 al_guardar=None, al_cerrar=None, botones_extra=(), columnas_form=1,
                 filtros=(), textos_estado=("⊘  Inhabilitar", "✓  Activar"), seleccionar_unico=False):
        super().__init__(master)
        self.logica = logica
        self.campos = campos
        self.columnas = columnas
        self.id_clave = columnas[0][0]
        self.nombre_id = columnas[0][1]
        self.sesion = sesion
        self.permitidas = permitidas
        self.valores_iniciales = valores_iniciales or {}
        self.bloqueados = set(bloqueados)
        self.al_guardar = al_guardar
        self.al_cerrar = al_cerrar
        self.filtros = list(filtros)
        self.textos_estado = textos_estado
        self.id_actual = None
        self.estado_actual = None
        self.filas = {}
        self.widgets = {}
        self.mapa_combo = {}
        self.mapa_filtro = {}
        self.combos_filtro = {}
        self.imagenes_nuevas = {}
        self.vistas_previas = {}

        self.title(f"Café Conecta - Gestión {titulo}")
        self.configure(bg=e.CREMA)
        self.protocol("WM_DELETE_WINDOW", self.f_salir)
        con_lista = "Consultar" in permitidas
        arriba = columnas_form > 1
        if arriba:
            e.centrar(self, 1180, (760 if len(campos) > 4 else 640) if con_lista else 500)
        else:
            e.centrar(self, 1120 if con_lista else 640, 680)
        self.minsize(860 if arriba else 600, 480)

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
                      ("Inhabilitar", textos_estado[0], self.f_inhabilitar, e.CEREZA),
                      ("Salir", "↩  Salir", self.f_salir, e.CAFE_OSCURO)]
        for accion, texto, comando, color in definicion:
            b = e.boton(barra, texto, comando, color)
            b.pack(side="left", padx=5, pady=10)
            if accion not in permitidas:
                e.deshabilitar(b)
            self.botones[accion] = b
        for texto, comando, color in reversed(list(botones_extra)):
            e.boton(barra, texto, comando, color).pack(side="right", padx=6, pady=10)

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

        normales = [c for c in campos if not c.get("lateral")]
        for campo in campos:
            if campo.get("lateral"):
                # Campo en una columna aparte, a la derecha de los demás (ej.: la imagen del lote).
                fila, col = 2, columnas_form * 2
            else:
                n = normales.index(campo)
                fila = 2 + (n // columnas_form) * 3
                col = (n % columnas_form) * 2
            texto = campo["etiqueta"] + (" *" if campo.get("obligatorio") else "")
            tk.Label(caja, text=texto, font=e.F_NEGRITA, bg=e.BLANCO, fg=e.TEXTO).grid(
                row=fila, column=col, sticky="w", padx=16, pady=(6, 0))
            if campo["tipo"] == "combo":
                w = ttk.Combobox(caja, state="readonly", width=ancho_campo - 2, font=e.F_NORMAL)
                w.bind("<<ComboboxSelected>>", lambda ev, c=campo["clave"]: self._al_cambiar_combo(c))
            elif campo["tipo"] == "imagen":
                w = self._crear_campo_imagen(caja, campo)
            else:
                w = tk.Entry(caja, width=ancho_campo, font=e.F_NORMAL, relief="solid", bd=1,
                             show="•" if campo["tipo"] == "clave" else "")
            if campo.get("lateral"):
                w.grid(row=fila + 1, column=col, rowspan=8, sticky="nw", padx=16, ipady=3)
            else:
                w.grid(row=fila + 1, column=col, sticky="we", padx=16, ipady=3)
            if campo["tipo"] == "clave":
                self.var_ver = tk.BooleanVar()
                tk.Checkbutton(caja, text="Ver", variable=self.var_ver, bg=e.BLANCO, font=e.F_PEQUENA,
                               command=lambda w=w: w.config(show="" if self.var_ver.get() else "•")
                               ).grid(row=fila + 1, column=col + 1, padx=(0, 10))
            if campo.get("ayuda") and campo.get("lateral"):
                w.ayuda = tk.Label(w, text=campo["ayuda"], font=(e.FUENTE, 8), bg=e.BLANCO, fg=e.GRIS)
                w.ayuda.pack(anchor="w")
            elif campo.get("ayuda"):
                tk.Label(caja, text=campo["ayuda"], font=(e.FUENTE, 8), bg=e.BLANCO, fg=e.GRIS).grid(
                    row=fila + 2, column=col, sticky="w", padx=16)
            self.widgets[campo["clave"]] = w
        ultima = 2 + ((len(normales) - 1) // columnas_form + 1) * 3
        tk.Label(caja, text="* Campos obligatorios", font=(e.FUENTE, 8, "italic"), bg=e.BLANCO,
                 fg=e.GRIS).grid(row=ultima, column=0, sticky="w", padx=16, pady=(8, 12))

        # Lista de registros (solo si puede consultar)
        if con_lista:
            derecha = tk.Frame(cuerpo, bg=e.CREMA)
            derecha.pack(side="top" if arriba else "left", fill="both", expand=True)
            busca = tk.Frame(derecha, bg=e.CREMA)
            busca.pack(fill="x", pady=(0, 6))
            tk.Label(busca, text="Buscar:", font=e.F_NEGRITA, bg=e.CREMA, fg=e.TEXTO).pack(side="left")
            self.txt_buscar = tk.Entry(busca, font=e.F_NORMAL, relief="solid", bd=1)
            self.txt_buscar.pack(side="left", fill="x", expand=True, padx=8, ipady=3)
            self.txt_buscar.bind("<Return>", lambda ev: self.f_consultar())

            if self.filtros:
                barra_filtros = tk.Frame(derecha, bg=e.CREMA)
                barra_filtros.pack(fill="x", pady=(0, 6))
                tk.Label(barra_filtros, text="Filtrar por:", font=e.F_NEGRITA, bg=e.CREMA,
                         fg=e.TEXTO).pack(side="left")
                for filtro in self.filtros:
                    tk.Label(barra_filtros, text=filtro["etiqueta"], font=e.F_PEQUENA, bg=e.CREMA,
                             fg=e.GRIS).pack(side="left", padx=(10, 4))
                    combo = ttk.Combobox(barra_filtros, state="readonly", width=filtro.get("ancho", 18),
                                         font=e.F_NORMAL)
                    combo.pack(side="left")
                    combo.bind("<<ComboboxSelected>>", lambda ev, c=filtro["clave"]: self._al_cambiar_filtro(c))
                    self.combos_filtro[filtro["clave"]] = combo
                for filtro in self.filtros:
                    if not filtro.get("depende_de"):
                        self._cargar_opciones_filtro(filtro)

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
            self.tabla.tag_configure("pendiente", foreground="#8d4a00", background="#fff3e0")
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
            datos = self.cargar_lista()
            # El productor ve solo su registro: se carga de una vez en el formulario.
            if seleccionar_unico and datos and len(datos) == 1:
                self.tabla.selection_set(str(datos[0][self.id_clave]))

    # ------------------------------------------------------------------
    # Campo de imagen (HU-05)
    # ------------------------------------------------------------------
    def _crear_campo_imagen(self, caja, campo):
        marco = tk.Frame(caja, bg=e.BLANCO)
        vista = tk.Label(marco, text="Sin imagen", width=24, height=6, bg=e.CREMA, fg=e.GRIS,
                         font=e.F_PEQUENA, relief="solid", bd=1)
        vista.pack(side="top" if campo.get("lateral") else "left", anchor="w")
        lado = tk.Frame(marco, bg=e.BLANCO)
        if campo.get("lateral"):
            lado.pack(side="top", anchor="w", pady=(8, 0))
        else:
            lado.pack(side="left", padx=10, anchor="n")
        boton = e.boton(lado, "Elegir imagen…", lambda: self._elegir_imagen(campo["clave"]), e.CAFE_CLARO,
                        fuente=e.F_PEQUENA)
        boton.pack(anchor="w")
        info = tk.Label(lado, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.GRIS, justify="left", wraplength=170)
        info.pack(anchor="w", pady=(6, 0))
        marco.vista, marco.boton, marco.info = vista, boton, info
        return marco

    def _elegir_imagen(self, clave):
        ruta = filedialog.askopenfilename(parent=self, title="Elegir imagen JPG o PNG",
                                          filetypes=[("Imágenes JPG o PNG", ("*.jpg", "*.jpeg", "*.png")),
                                                     ("Todos los archivos", "*.*")])
        if not ruta:
            return
        with open(ruta, "rb") as archivo:
            contenido = archivo.read()
        self.imagenes_nuevas[clave] = contenido
        self._mostrar_imagen(clave, contenido)
        tamano = len(contenido) / 1024
        texto = f"{os.path.basename(ruta)}\n{tamano / 1024:.1f} MB" if tamano >= 1024 else \
            f"{os.path.basename(ruta)}\n{tamano:.0f} KB"
        marco = self.widgets[clave]
        marco.info.config(text=texto + "\n(se guarda al presionar Guardar o Modificar)",
                          fg=e.CEREZA if len(contenido) > 2 * 1024 * 1024 else e.GRIS)

    def _mostrar_imagen(self, clave, contenido):
        marco = self.widgets[clave]
        foto = miniatura(contenido)
        self.vistas_previas[clave] = foto
        if foto is not None:
            marco.vista.config(image=foto, text="", width=170, height=110)
        else:
            texto = "Sin imagen" if not contenido else "Vista previa no disponible\n(instale Pillow)"
            marco.vista.config(image="", text=texto, width=24, height=6)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _mostrar(self, resultado, titulo):
        if resultado["exito"]:
            messagebox.showinfo(titulo, resultado["mensaje"], parent=self)
        else:
            messagebox.showwarning(titulo, resultado["mensaje"], parent=self)

    def _actualizar_modo(self):
        if self.id_actual is None:
            self.lbl_modo.config(text="Modo: nuevo registro (complete los datos y presione Guardar)", fg=e.VERDE)
            self.botones["Inhabilitar"].config(text=self.textos_estado[0])
        else:
            color = e.VERDE if self.estado_actual == ACTIVO else e.CEREZA
            self.lbl_modo.config(text=f"Modo: editando {self.nombre_id} {self.id_actual}  ·  "
                                      f"Estado: {self.estado_actual}", fg=color)
            self.botones["Inhabilitar"].config(
                text=self.textos_estado[0] if self.estado_actual == ACTIVO else self.textos_estado[1])

    def _valor_combo(self, clave):
        return self.mapa_combo.get(clave, {}).get(self.widgets[clave].get())

    def _cargar_opciones(self, campo):
        if campo.get("depende_de"):
            resultado = campo["opciones"](self.id_actual, self._valor_combo(campo["depende_de"]))
        else:
            resultado = campo["opciones"](self.id_actual)
        if not resultado["exito"]:
            messagebox.showwarning("Datos", resultado["mensaje"], parent=self)
            return
        opciones = resultado["datos"]
        self.mapa_combo[campo["clave"]] = {texto: id_ for id_, texto in opciones}
        self.widgets[campo["clave"]]["values"] = [texto for _, texto in opciones]

    def _refrescar_combos(self):
        for campo in self.campos:
            if campo["tipo"] == "combo":
                self._cargar_opciones(campo)

    def _al_cambiar_combo(self, clave):
        """Al elegir un departamento se cargan sus municipios (y se limpia el municipio anterior)."""
        for campo in self.campos:
            if campo.get("depende_de") == clave:
                self._cargar_opciones(campo)
                self.widgets[campo["clave"]].set("")
                self._al_cambiar_combo(campo["clave"])

    def _poner(self, clave, valor):
        w = self.widgets[clave]
        if isinstance(w, ttk.Combobox):
            texto = next((t for t, i in self.mapa_combo.get(clave, {}).items() if i == valor), "")
            w.set(texto)
        elif isinstance(w, tk.Entry):
            estado = w.cget("state")
            w.config(state="normal")
            w.delete(0, "end")
            w.insert(0, "" if valor is None else str(valor))
            w.config(state=estado)
        else:  # imagen
            self._mostrar_imagen(clave, valor)
            w.info.config(text="", fg=e.GRIS)

    def _llenar(self, valores):
        for campo in self.campos:
            if campo["tipo"] == "combo" and campo.get("depende_de"):
                self._cargar_opciones(campo)
            self._poner(campo["clave"], valores.get(campo["clave"]))

    def _leer(self):
        datos = {}
        for campo in self.campos:
            clave, w = campo["clave"], self.widgets[campo["clave"]]
            if isinstance(w, ttk.Combobox):
                datos[clave] = self._valor_combo(clave)
            elif isinstance(w, tk.Entry):
                datos[clave] = w.get()
            else:  # imagen: solo se envía si se eligió una nueva
                datos[clave] = self.imagenes_nuevas.get(clave)
        return datos

    def _habilitar(self, clave, habilitado):
        w = self.widgets[clave]
        if isinstance(w, ttk.Combobox):
            w.config(state="readonly" if habilitado else "disabled")
        elif isinstance(w, tk.Entry):
            w.config(state="normal" if habilitado else "disabled")
        elif habilitado:
            w.boton.config(state="normal", cursor="hand2")
        else:
            e.deshabilitar(w.boton)

    # ------------------------------------------------------------------
    # Filtros de la lista
    # ------------------------------------------------------------------
    def _cargar_opciones_filtro(self, filtro):
        padre = filtro.get("depende_de")
        if padre:
            valor_padre = self._valor_filtro(padre)
            resultado = filtro["opciones"](valor_padre) if valor_padre else {"exito": True, "datos": []}
        else:
            resultado = filtro["opciones"]()
        opciones = [(None, "(Todos)")] + (resultado["datos"] if resultado["exito"] else [])
        self.mapa_filtro[filtro["clave"]] = {texto: id_ for id_, texto in opciones}
        combo = self.combos_filtro[filtro["clave"]]
        combo["values"] = [texto for _, texto in opciones]
        combo.set("(Todos)")

    def _valor_filtro(self, clave):
        return self.mapa_filtro.get(clave, {}).get(self.combos_filtro[clave].get())

    def _al_cambiar_filtro(self, clave):
        for filtro in self.filtros:
            if filtro.get("depende_de") == clave:
                self._cargar_opciones_filtro(filtro)
        self.cargar_lista(self.txt_buscar.get().strip())

    def _valores_filtros(self):
        return {f["clave"]: self._valor_filtro(f["clave"]) for f in self.filtros}

    # ------------------------------------------------------------------
    # Lista
    # ------------------------------------------------------------------
    def cargar_lista(self, filtro="", seleccionar=None):
        if self.tabla is None:
            return
        resultado = self.logica.listar(filtro, self.sesion, self._valores_filtros())
        if not resultado["exito"]:
            messagebox.showerror("Consultar", resultado["mensaje"], parent=self)
            return
        self.tabla.delete(*self.tabla.get_children())
        self.filas = {}
        for fila in resultado["datos"]:
            valores = ["" if fila.get(c) is None else fila.get(c) for c, _, _ in self.columnas]
            iid = str(fila[self.id_clave])
            estado = fila.get("estado")
            etiqueta = () if estado == ACTIVO else (("pendiente",) if estado == "Pendiente" else ("inactivo",))
            self.tabla.insert("", "end", iid=iid, values=valores, tags=etiqueta)
            self.filas[iid] = fila
        total = len(resultado["datos"])
        self.lbl_total.config(text=f"{total} registro(s) encontrado(s)")
        if seleccionar is not None and str(seleccionar) in self.filas:
            self.tabla.selection_set(str(seleccionar))
            self.tabla.see(str(seleccionar))
        return resultado["datos"]

    def fila_actual(self):
        return self.filas.get(str(self.id_actual)) if self.id_actual is not None else None

    def _al_seleccionar(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        fila = self.filas[seleccion[0]]
        self.id_actual = fila[self.id_clave]
        self.estado_actual = fila.get("estado")
        self.imagenes_nuevas.clear()
        self._refrescar_combos()
        valores = dict(fila)
        for campo in self.campos:
            if campo["tipo"] == "imagen" and campo.get("cargar"):
                resultado = campo["cargar"](self.id_actual)
                valores[campo["clave"]] = resultado["datos"] if resultado["exito"] else None
        self._llenar(valores)
        # La llave primaria no se modifica.
        for campo in self.campos:
            if campo.get("llave"):
                self._habilitar(campo["clave"], False)
        self._actualizar_modo()

    # ------------------------------------------------------------------
    # Botones de comando
    # ------------------------------------------------------------------
    def f_crear(self):
        """Limpia el formulario para ingresar un registro nuevo."""
        self.id_actual = None
        self.estado_actual = None
        self.imagenes_nuevas.clear()
        if self.tabla is not None:
            self.tabla.selection_remove(self.tabla.selection())
        for campo in self.campos:
            self._habilitar(campo["clave"], True)
        self._refrescar_combos()
        self._llenar(self.valores_iniciales)
        for clave in self.bloqueados:
            self._habilitar(clave, False)
        self._actualizar_modo()
        primero = next((self.widgets[c["clave"]] for c in self.campos
                        if c["clave"] not in self.bloqueados and c["tipo"] in ("texto", "clave")), None)
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
        if not messagebox.askyesno("Modificar", f"¿Desea guardar los cambios de {self.nombre_id} "
                                                f"{self.id_actual}?", parent=self):
            return
        resultado = self.logica.modificar(self.id_actual, self._leer(), self.sesion)
        self._mostrar(resultado, "Modificar")
        if resultado["exito"]:
            self.cargar_lista(self.txt_buscar.get().strip(), seleccionar=self.id_actual)

    def f_inhabilitar(self):
        if self.id_actual is None:
            messagebox.showinfo("Inhabilitar", "Primero seleccione en la lista el registro.", parent=self)
            return
        texto_boton = self.botones["Inhabilitar"].cget("text").split()[-1]
        accion = texto_boton.lower()
        if not messagebox.askyesno(texto_boton, f"¿Desea {accion} {self.nombre_id} {self.id_actual}?\n\n"
                                                "No se borra de la base de datos: solo cambia su estado.",
                                   parent=self):
            return
        resultado = self.logica.cambiar_estado(self.id_actual, self.estado_actual, self.sesion)
        self._mostrar(resultado, texto_boton)
        if resultado["exito"]:
            self.cargar_lista(self.txt_buscar.get().strip(), seleccionar=self.id_actual)

    def f_salir(self):
        self.destroy()
        if self.al_cerrar:
            self.al_cerrar()


class VentanaDetalle(tk.Toplevel):
    """Ventana de solo lectura con una o varias tablas (ej.: cooperativas de un productor)."""

    def __init__(self, master, titulo, subtitulo, secciones):
        super().__init__(master)
        self.title(f"Café Conecta - {titulo}")
        self.configure(bg=e.CREMA)
        e.centrar(self, 860, 230 + 190 * len(secciones))
        self.transient(master)
        cab = tk.Frame(self, bg=e.CAFE_OSCURO)
        cab.pack(fill="x")
        tk.Label(cab, text=titulo, font=e.F_SUBTITULO, bg=e.CAFE_OSCURO, fg=e.BLANCO).pack(
            anchor="w", padx=20, pady=(12, 0))
        tk.Label(cab, text=subtitulo, font=e.F_NORMAL, bg=e.CAFE_OSCURO, fg=e.DORADO).pack(
            anchor="w", padx=20, pady=(0, 12))
        for nombre, columnas, filas in secciones:
            tk.Label(self, text=f"{nombre} ({len(filas)})", font=e.F_NEGRITA, bg=e.CREMA,
                     fg=e.CAFE_OSCURO).pack(anchor="w", padx=20, pady=(12, 4))
            tabla = ttk.Treeview(self, columns=[c[0] for c in columnas], show="headings", height=6)
            for clave, titulo_col, ancho in columnas:
                tabla.heading(clave, text=titulo_col)
                tabla.column(clave, width=ancho, anchor="w")
            tabla.tag_configure("inactivo", foreground="#9e9e9e")
            for fila in filas:
                tabla.insert("", "end", values=["" if fila.get(c) is None else fila.get(c) for c, _, _ in columnas],
                             tags=() if fila.get("estado") == ACTIVO else ("inactivo",))
            if not filas:
                tabla.insert("", "end", values=["(sin registros)"])
            tabla.pack(fill="x", padx=20)
        e.boton(self, "Cerrar", self.destroy, e.CAFE_OSCURO).pack(anchor="e", padx=20, pady=14)


def _necesita_seleccion(formulario, titulo):
    if formulario.id_actual is None:
        messagebox.showinfo(titulo, "Seleccione primero un registro en la lista.", parent=formulario)
        return True
    return False


# =====================================================================
# PARCIAL I
# =====================================================================
def abrir_perfil(master, sesion, permitidas, al_cerrar=None):
    campos = [{"clave": "descripc", "etiqueta": "Descripción del perfil", "tipo": "texto",
               "obligatorio": True, "ayuda": "Ej.: Administrador, Persona, Productor, Comprador"}]
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
        if _necesita_seleccion(formulario, "Crear usuario"):
            return
        abrir_usuario(master, sesion, ("Crear", "Consultar", "Modificar", "Guardar", "Inhabilitar", "Salir"),
                      persona_inicial=formulario.id_actual)

    if es_administrador(sesion):
        extra.append(("☺  Crear usuario a esta persona", crear_usuario, e.CAFE_CLARO))
    formulario = FormularioCRUD(master, LogicaPersona, "Persona", "Clientes, empleados y usuarios",
                                CAMPOS_PERSONA, COLUMNAS_PERSONA, sesion, permitidas, icono="☘",
                                al_cerrar=al_cerrar, botones_extra=extra, columnas_form=3)
    return formulario


def _campos_usuario(persona_fija=None, perfil_fijo=None, con_cooperativa=True):
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
    if con_cooperativa:
        campos.append({"clave": "nit", "etiqueta": "Cooperativa", "tipo": "combo",
                       "opciones": lambda _id: LogicaUsuario.opciones_cooperativa(),
                       "ayuda": "Solo para el perfil Comprador"})
    return campos, opciones_persona


def _id_perfil(descripcion):
    resultado = LogicaUsuario.opciones_perfil()
    if resultado["exito"]:
        return next((i for i, texto in resultado["datos"] if texto == descripcion), None)
    return None


def abrir_usuario(master, sesion, permitidas, persona_inicial=None, perfil_inicial=None, al_cerrar=None):
    campos, opciones_persona = _campos_usuario()
    columnas = [("Idusuario", "ID", 40), ("nombreu", "Usuario", 105), ("perfil", "Perfil", 100),
                ("persona", "Persona", 150), ("cooperativa", "Cooperativa", 165), ("estado", "Estado", 65)]
    iniciales = {}
    if persona_inicial:
        iniciales["idpersona"] = persona_inicial
    if perfil_inicial:
        iniciales["idperfil"] = perfil_inicial
    formulario = FormularioCRUD(master, LogicaUsuario, "Usuario", "Acceso al sistema de cada persona",
                                campos, columnas, sesion, permitidas, icono="☺",
                                valores_iniciales=iniciales, al_cerrar=al_cerrar)
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
        campos, _ = _campos_usuario(persona_fija=id_persona, perfil_fijo=perfil["datos"], con_cooperativa=False)
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


# =====================================================================
# PARCIAL II
# =====================================================================
COLUMNAS_COOPERATIVAS_DE_PRODUCTOR = [("nit", "NIT", 110), ("cooperativa", "Cooperativa", 300),
                                      ("fecha_afiliacion", "Afiliación", 110), ("fecha_retiro", "Retiro", 110),
                                      ("estado", "Estado", 100)]


def ver_cooperativas_de_productor(master, documento, nombre):
    resultado = LogicaProductor.cooperativas(documento)
    if not resultado["exito"]:
        messagebox.showwarning("Cooperativas", resultado["mensaje"], parent=master)
        return
    VentanaDetalle(master, "Cooperativas del productor", f"{nombre} · Documento {documento}",
                   [("Cooperativas", COLUMNAS_COOPERATIVAS_DE_PRODUCTOR, resultado["datos"])])


# ---------------------------------------------------------------------
# HU-01 · Gestión de Productores Cafeteros
# ---------------------------------------------------------------------
def abrir_productor(master, sesion, permitidas, al_cerrar=None):
    """Usa la misma programación de Persona, con las adaptaciones de la HU-01."""
    campos = [
        {"clave": "documento", "etiqueta": "Documento", "tipo": "texto", "obligatorio": True, "llave": True,
         "ayuda": "Solo números. Es la llave: no se modifica"},
        {"clave": "nom1", "etiqueta": "Primer nombre", "tipo": "texto", "obligatorio": True},
        {"clave": "nom2", "etiqueta": "Segundo nombre", "tipo": "texto"},
        {"clave": "apell1", "etiqueta": "Primer apellido", "tipo": "texto", "obligatorio": True},
        {"clave": "apell2", "etiqueta": "Segundo apellido", "tipo": "texto"},
        {"clave": "movil", "etiqueta": "Teléfono celular", "tipo": "texto", "obligatorio": True,
         "ayuda": "10 dígitos: allí recibe los avisos por WhatsApp"},
        {"clave": "direccion", "etiqueta": "Dirección", "tipo": "texto", "obligatorio": True},
        {"clave": "fecha_nac", "etiqueta": "Fecha de nacimiento", "tipo": "texto", "obligatorio": True,
         "ayuda": "AAAA-MM-DD · debe ser mayor de 18 años"},
        {"clave": "correo", "etiqueta": "Correo electrónico", "tipo": "texto", "ayuda": "Opcional"},
    ]
    columnas = [("documento", "Documento", 100), ("nombre", "Nombre completo", 210), ("movil", "Teléfono", 95),
                ("direccion", "Dirección", 180), ("cooperativas", "Cooperativas", 220),
                ("fincas", "Fincas", 55), ("estado", "Estado", 70)]
    formulario = None

    def ver_cooperativas():
        if _necesita_seleccion(formulario, "Cooperativas"):
            return
        fila = formulario.fila_actual()
        ver_cooperativas_de_productor(formulario, fila["documento"], fila["nombre"])

    def crear_usuario():
        if _necesita_seleccion(formulario, "Crear usuario"):
            return
        fila = formulario.fila_actual()
        abrir_usuario(master, sesion, permitidas_admin(), persona_inicial=fila["idpersona"],
                      perfil_inicial=_id_perfil("Productor"))

    extra = [("◎  Ver cooperativas", ver_cooperativas, e.CAFE_CLARO)]
    if es_administrador(sesion):
        extra.append(("☺  Crear usuario al productor", crear_usuario, e.CAFE_CLARO))
        descripcion = "Pequeños caficultores y sus datos de contacto"
    else:
        descripcion = "Mis datos (el documento y el estado no se modifican)"
    formulario = FormularioCRUD(master, LogicaProductor, "Productores", descripcion, campos, columnas, sesion,
                                permitidas, icono="☘", al_cerrar=al_cerrar, botones_extra=extra,
                                columnas_form=3, seleccionar_unico=not es_administrador(sesion))
    return formulario


def permitidas_admin():
    return ("Crear", "Consultar", "Modificar", "Guardar", "Inhabilitar", "Salir")


# ---------------------------------------------------------------------
# HU-02 · Gestión de Fincas
# ---------------------------------------------------------------------
def abrir_finca(master, sesion, permitidas, al_cerrar=None):
    admin = es_administrador(sesion)

    def opciones_productor(_id):
        resultado = LogicaProductor.opciones(solo_activos=False)
        if resultado["exito"] and not admin:
            resultado["datos"] = [o for o in resultado["datos"] if o[0] == (sesion or {}).get("documento")]
        return resultado

    campos = [
        {"clave": "codigof", "etiqueta": "Código de la finca", "tipo": "texto", "obligatorio": True, "llave": True,
         "ayuda": "Ej.: F-001 · no se modifica"},
        {"clave": "nombre", "etiqueta": "Nombre", "tipo": "texto", "obligatorio": True},
        {"clave": "documento", "etiqueta": "Productor", "tipo": "combo", "obligatorio": True,
         "opciones": opciones_productor},
        {"clave": "area", "etiqueta": "Área (hectáreas)", "tipo": "texto", "obligatorio": True,
         "ayuda": "Mayor que cero (ej.: 4.5)"},
        {"clave": "temperatura", "etiqueta": "Temperatura promedio (°C)", "tipo": "texto", "obligatorio": True,
         "ayuda": "Entre 5 y 35"},
        {"clave": "telefono", "etiqueta": "Teléfono", "tipo": "texto", "obligatorio": True,
         "ayuda": "10 dígitos"},
        {"clave": "iddepartamento", "etiqueta": "Departamento", "tipo": "combo", "obligatorio": True,
         "opciones": lambda _id: LogicaUbicacion.departamentos(), "ayuda": "Primero elija el departamento"},
        {"clave": "idmunicipio", "etiqueta": "Municipio", "tipo": "combo", "obligatorio": True,
         "depende_de": "iddepartamento",
         "opciones": lambda _id, iddep: LogicaUbicacion.municipios(iddep),
         "ayuda": "Municipios del departamento elegido"},
        {"clave": "direccion", "etiqueta": "Dirección / vereda", "tipo": "texto", "obligatorio": True},
    ]
    columnas = [("codigof", "Código", 70), ("nombre", "Finca", 150), ("productor", "Productor", 150),
                ("municipio", "Municipio", 130), ("departamento", "Departamento", 130),
                ("area", "Área (ha)", 70), ("temperatura", "Temp. (°C)", 70), ("lotes", "Lotes", 50),
                ("estado", "Estado", 70)]
    filtros = []
    if admin:
        # El administrador consulta todas las fincas y las filtra por departamento, municipio y productor.
        filtros = [
            {"clave": "iddepartamento", "etiqueta": "Departamento", "opciones": LogicaUbicacion.departamentos},
            {"clave": "idmunicipio", "etiqueta": "Municipio", "depende_de": "iddepartamento",
             "opciones": LogicaUbicacion.municipios},
            {"clave": "documento", "etiqueta": "Productor", "ancho": 24,
             "opciones": lambda: LogicaProductor.opciones(solo_activos=False)},
        ]
        iniciales, bloqueados, descripcion = None, (), "Todas las fincas cafeteras"
    else:
        iniciales = {"documento": (sesion or {}).get("documento")}
        bloqueados, descripcion = ("documento",), "Mis fincas: dónde se produce mi café"
    return FormularioCRUD(master, LogicaFinca, "Fincas", descripcion, campos, columnas, sesion, permitidas,
                          icono="⛰", al_cerrar=al_cerrar, columnas_form=3, filtros=filtros,
                          valores_iniciales=iniciales, bloqueados=bloqueados)


# ---------------------------------------------------------------------
# HU-03 · Gestión de Cooperativas
# ---------------------------------------------------------------------
def abrir_cooperativa(master, sesion, permitidas, al_cerrar=None):
    campos = [
        {"clave": "nit", "etiqueta": "NIT", "tipo": "texto", "obligatorio": True, "llave": True,
         "ayuda": "Con dígito de verificación: 900123456-7"},
        {"clave": "nombre", "etiqueta": "Nombre", "tipo": "texto", "obligatorio": True},
        {"clave": "direccion", "etiqueta": "Dirección", "tipo": "texto", "obligatorio": True},
        {"clave": "telefono", "etiqueta": "Teléfono celular", "tipo": "texto", "obligatorio": True,
         "ayuda": "10 dígitos: recibe los avisos por WhatsApp"},
        {"clave": "correo", "etiqueta": "Correo electrónico", "tipo": "texto", "obligatorio": True},
    ]
    columnas = [("nit", "NIT", 100), ("nombre", "Cooperativa", 220), ("telefono", "Teléfono", 95),
                ("correo", "Correo", 190), ("productores", "Productores", 80),
                ("compradores", "Compradores", 85), ("estado", "Estado", 70)]
    formulario = None

    def ver_detalle():
        if _necesita_seleccion(formulario, "Detalle"):
            return
        fila = formulario.fila_actual()
        resultado = LogicaCooperativa.detalle(fila["nit"], sesion)
        if not resultado["exito"]:
            messagebox.showwarning("Detalle", resultado["mensaje"], parent=formulario)
            return
        VentanaDetalle(formulario, fila["nombre"], f"NIT {fila['nit']} · {fila['direccion']} · {fila['telefono']}",
                       [("Productores asociados",
                         [("documento", "Documento", 110), ("productor", "Productor", 210),
                          ("movil", "Teléfono", 100), ("fecha_afiliacion", "Afiliación", 100),
                          ("fecha_retiro", "Retiro", 100), ("estado", "Estado", 90)],
                         resultado["datos"]["productores"]),
                        ("Usuarios compradores",
                         [("nombreu", "Usuario", 140), ("persona", "Persona", 220),
                          ("correo", "Correo", 250), ("estado", "Estado", 90)],
                         resultado["datos"]["compradores"])])

    descripcion = ("Organizaciones que compran el café a los productores" if es_administrador(sesion)
                   else "Mi cooperativa")
    formulario = FormularioCRUD(master, LogicaCooperativa, "Cooperativas", descripcion, campos, columnas, sesion,
                                permitidas, icono="⌂", al_cerrar=al_cerrar, columnas_form=3,
                                botones_extra=[("◎  Ver productores y compradores", ver_detalle, e.CAFE_CLARO)],
                                seleccionar_unico=not es_administrador(sesion))
    return formulario


# ---------------------------------------------------------------------
# HU-04 · Asociación de Productores a Cooperativas
# ---------------------------------------------------------------------
def abrir_asociacion(master, sesion, permitidas, al_cerrar=None):
    admin = es_administrador(sesion)
    campos = [
        {"clave": "documento", "etiqueta": "Productor", "tipo": "combo", "obligatorio": True,
         "opciones": lambda _id: LogicaProductor.opciones(solo_activos=True),
         "ayuda": "Solo productores activos"},
        {"clave": "nit", "etiqueta": "Cooperativa", "tipo": "combo", "obligatorio": True,
         "opciones": lambda _id: LogicaCooperativa.opciones(sesion), "ayuda": "Solo cooperativas activas"},
    ]
    columnas = [("idasociacion", "N.º", 45), ("productor", "Productor", 160), ("documento", "Documento", 95),
                ("cooperativa", "Cooperativa", 210), ("fecha_solicitud", "Solicitud", 85),
                ("fecha_afiliacion", "Afiliación", 85), ("fecha_retiro", "Retiro", 85),
                ("solicitado_por", "Registró", 90), ("estado", "Estado", 80)]
    formulario = None

    def resolver(accion):
        if _necesita_seleccion(formulario, accion):
            return
        if formulario.estado_actual != "Pendiente":
            messagebox.showinfo(accion, "Solo se pueden aprobar o rechazar solicitudes Pendientes.", parent=formulario)
            return
        if not messagebox.askyesno(accion, f"¿Desea {accion.lower()} la solicitud N.º {formulario.id_actual}?",
                                   parent=formulario):
            return
        funcion = LogicaAsociacion.aprobar if accion == "Aprobar" else LogicaAsociacion.rechazar
        resultado = funcion(formulario.id_actual, sesion)
        formulario._mostrar(resultado, accion)
        if resultado["exito"]:
            formulario.cargar_lista(formulario.txt_buscar.get().strip(), seleccionar=formulario.id_actual)

    extra, iniciales, bloqueados = [], None, ()
    if admin:
        extra = [("✓  Aprobar", lambda: resolver("Aprobar"), e.VERDE),
                 ("✕  Rechazar", lambda: resolver("Rechazar"), e.CAFE_CLARO)]
        descripcion = "Afiliaciones de cada caficultor"
    else:
        # El comprador solicita asociar productores a su propia cooperativa.
        iniciales, bloqueados = {"nit": (sesion or {}).get("nit")}, ("nit",)
        descripcion = "Solicitar asociación (la aprueba el administrador)"
    permitidas = tuple(a for a in permitidas if a != "Modificar")
    formulario = FormularioCRUD(master, LogicaAsociacion, "Asociaciones", descripcion, campos, columnas, sesion,
                                permitidas, icono="⇄", al_cerrar=al_cerrar, botones_extra=extra,
                                valores_iniciales=iniciales, bloqueados=bloqueados, columnas_form=2,
                                textos_estado=("⊘  Desasociar", "⊘  Desasociar"))
    return formulario


# ---------------------------------------------------------------------
# HU-05 · Gestión de Tipos de Variedades
# ---------------------------------------------------------------------
def abrir_variedad(master, sesion, permitidas, al_cerrar=None):
    campos = [
        {"clave": "codigotv", "etiqueta": "Código", "tipo": "texto", "obligatorio": True, "llave": True,
         "ayuda": "Ej.: CAS · no se modifica"},
        {"clave": "descripcion", "etiqueta": "Descripción", "tipo": "texto", "obligatorio": True,
         "ayuda": "Ej.: Castillo, Caturra, Geisha"},
        {"clave": "imagen", "etiqueta": "Imagen", "tipo": "imagen", "obligatorio": True,
         "cargar": LogicaVariedad.imagen, "ayuda": "JPG o PNG, máximo 2 MB"},
    ]
    columnas = [("codigotv", "Código", 80), ("descripcion", "Variedad", 220), ("imagen_tipo", "Formato", 70),
                ("imagen_kb", "Tamaño (KB)", 90), ("estado", "Estado", 80)]
    descripcion = ("Variedades de café para clasificar los lotes" if es_administrador(sesion)
                   else "Variedades activas, en orden alfabético")
    return FormularioCRUD(master, LogicaVariedad, "Variedades", descripcion, campos, columnas, sesion,
                          permitidas, icono="❦", al_cerrar=al_cerrar)


# =====================================================================
# FINAL
# =====================================================================
# ---------------------------------------------------------------------
# HU-06 · Gestión de Inventario y Catálogo de Café (lotes)
# ---------------------------------------------------------------------
def abrir_lote(master, sesion, permitidas, al_cerrar=None):
    admin = es_administrador(sesion)
    campos = [
        {"clave": "codigoc", "etiqueta": "Código del lote", "tipo": "texto", "obligatorio": True, "llave": True,
         "ayuda": "Ej.: L-001 · no se modifica"},
        {"clave": "descripcion", "etiqueta": "Descripción (tipo y calidad)", "tipo": "texto", "obligatorio": True,
         "ayuda": "Ej.: pergamino seco, factor 92, cosecha 2026"},
        {"clave": "codigof", "etiqueta": "Finca", "tipo": "combo", "obligatorio": True,
         "opciones": lambda codigo: LogicaLote.opciones_finca(sesion, codigo),
         "ayuda": "Solo sus fincas activas"},
        {"clave": "codigotv", "etiqueta": "Variedad", "tipo": "combo", "obligatorio": True,
         "opciones": LogicaLote.opciones_variedad, "ayuda": "Variedades activas (HU-05)"},
        {"clave": "idempaque", "etiqueta": "Tipo de empaque", "tipo": "combo", "obligatorio": True,
         "opciones": lambda _id: LogicaListas.empaques()},
        {"clave": "peso", "etiqueta": "Peso por empaque (kg)", "tipo": "texto", "obligatorio": True,
         "ayuda": "Mayor que cero (ej.: 70)"},
        {"clave": "cantidad", "etiqueta": "Cantidad de empaques", "tipo": "texto", "obligatorio": True,
         "ayuda": "Número entero mayor que cero"},
        {"clave": "precio", "etiqueta": "Precio de compra por kg ($)", "tipo": "texto", "obligatorio": True,
         "ayuda": "Mayor que cero · solo aplica a negocios nuevos"},
        {"clave": "imagen", "etiqueta": "Imagen del café", "tipo": "imagen", "obligatorio": True,
         "cargar": LogicaLote.imagen, "ayuda": "JPG o PNG, máximo 2 MB", "lateral": True},
    ]
    columnas = [("codigoc", "Código", 70), ("descripcion", "Descripción", 210), ("finca", "Finca", 120),
                ("variedad", "Variedad", 85), ("empaque", "Empaque", 150), ("peso", "Peso (kg)", 70),
                ("cantidad", "Cantidad", 65), ("comprometida", "Comprometida", 90),
                ("disponible", "Disponible", 75), ("precio", "Precio/kg", 80), ("estado", "Estado", 65)]
    descripcion = "Todos los lotes de café" if admin else "Mi inventario: mis lotes de café"
    return FormularioCRUD(master, LogicaLote, "Lotes de café", descripcion, campos, columnas, sesion, permitidas,
                          icono="▦", al_cerrar=al_cerrar, columnas_form=3)
