"""
Pantallas del ciclo comercial (Final):

  HU-10  VentanaCatalogo   Listado detallado de lotes disponibles, con filtros, orden y exportación.
  HU-07  VentanaNegocios   Negocios (emparejamiento comercial) y su detalle.
         EditorNegocio     Proponer o modificar un negocio con varias líneas de lotes.
  HU-08  VentanaEntregas   Programar, modificar, cancelar y despachar entregas.
  HU-09  DialogoConfirmar  Confirmar lo recibido de una entrega.
         VentanaMensajes   Bitácora de mensajes de WhatsApp (administrador).
"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, simpledialog, ttk

import estilos as e
from formularios import miniatura
from negocio import (ACTIVO, LogicaCatalogo, LogicaCooperativa, LogicaEntrega, LogicaListas, LogicaLote,
                     LogicaMensaje, LogicaNegocio, LogicaProductor, LogicaUbicacion, es_administrador)
from whatsapp import pesos

COLORES_ESTADO = {
    "Propuesto": ("#8d4a00", "#fff3e0"), "Aceptado": ("#1b5e20", "#e8f5e9"), "En entrega": ("#0d47a1", "#e3f2fd"),
    "Completado": ("#33691e", "#f1f8e9"), "Rechazado": ("#b71c1c", "#ffebee"), "Cancelado": ("#9e9e9e", "#f5f5f5"),
    "Programada": ("#8d4a00", "#fff3e0"), "En tránsito": ("#0d47a1", "#e3f2fd"), "Recibida": ("#1b5e20", "#e8f5e9"),
    "Recibida con novedad": ("#e65100", "#fff8e1"), "Cancelada": ("#9e9e9e", "#f5f5f5"),
}


def _es(sesion, perfil):
    return bool(sesion) and sesion.get("perfil") == perfil


def _numero_bonito(valor):
    try:
        return f"{float(valor):g}"
    except (TypeError, ValueError):
        return valor


def encabezado(ventana, icono, titulo, descripcion):
    cab = tk.Frame(ventana, bg=e.CAFE_OSCURO)
    cab.pack(fill="x")
    tk.Label(cab, text=f"{icono}  {titulo}", font=e.F_TITULO, bg=e.CAFE_OSCURO, fg=e.BLANCO).pack(
        side="left", padx=20, pady=12)
    etiqueta = tk.Label(cab, text=descripcion, font=e.F_NORMAL, bg=e.CAFE_OSCURO, fg=e.DORADO)
    etiqueta.pack(side="left", padx=4, pady=18)
    return etiqueta


def tabla(padre, columnas, alto=8):
    """Treeview con barra de desplazamiento. columnas: [(clave, título, ancho)]."""
    marco = tk.Frame(padre)
    arbol = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", selectmode="browse", height=alto)
    for clave, titulo, ancho in columnas:
        arbol.heading(clave, text=titulo)
        arbol.column(clave, width=ancho, minwidth=ancho, anchor="w", stretch=True)
    for estado, (letra, fondo) in COLORES_ESTADO.items():
        arbol.tag_configure(estado, foreground=letra, background=fondo)
    arbol.tag_configure("inactivo", foreground="#9e9e9e", background="#f5f5f5")
    barra = ttk.Scrollbar(marco, orient="vertical", command=arbol.yview)
    barra_h = ttk.Scrollbar(marco, orient="horizontal", command=arbol.xview)
    arbol.configure(yscrollcommand=barra.set, xscrollcommand=barra_h.set)
    arbol.grid(row=0, column=0, sticky="nsew")
    barra.grid(row=0, column=1, sticky="ns")
    barra_h.grid(row=1, column=0, sticky="we")
    marco.rowconfigure(0, weight=1)
    marco.columnconfigure(0, weight=1)
    return marco, arbol


def llenar(arbol, columnas, filas, clave_id, etiqueta=None):
    arbol.delete(*arbol.get_children())
    for fila in filas:
        valores = ["" if fila.get(c) is None else fila.get(c) for c, _, _ in columnas]
        etiquetas = (etiqueta(fila),) if etiqueta and etiqueta(fila) else ()
        arbol.insert("", "end", iid=str(fila[clave_id]), values=valores, tags=etiquetas)


class ComboMapa(ttk.Combobox):
    """Combobox que guarda (id, texto) y devuelve el id elegido."""

    def __init__(self, padre, ancho=22, con_todos=False):
        super().__init__(padre, state="readonly", width=ancho, font=e.F_NORMAL)
        self.con_todos = con_todos
        self.mapa = {}

    def opciones(self, pares):
        pares = ([(None, "(Todos)")] if self.con_todos else []) + list(pares)
        self.mapa = {texto: id_ for id_, texto in pares}
        self["values"] = [texto for _, texto in pares]
        self.set("(Todos)" if self.con_todos else "")

    def valor(self):
        return self.mapa.get(self.get())

    def poner(self, valor):
        self.set(next((t for t, i in self.mapa.items() if i == valor), ""))


def _datos(resultado, ventana, titulo):
    if not resultado["exito"]:
        messagebox.showwarning(titulo, resultado["mensaje"], parent=ventana)
        return None
    return resultado["datos"]


def _mostrar(resultado, ventana, titulo):
    (messagebox.showinfo if resultado["exito"] else messagebox.showwarning)(titulo, resultado["mensaje"],
                                                                            parent=ventana)
    return resultado["exito"]


# =====================================================================
# HU-10 · Listado detallado de lotes disponibles
# =====================================================================
class VentanaCatalogo(tk.Toplevel):
    COLUMNAS = [("codigoc", "Lote", 60), ("asociado_txt", "", 24), ("variedad", "Variedad", 80),
                ("descripcion", "Descripción", 200), ("empaque", "Empaque", 140), ("peso_txt", "Peso (kg)", 65),
                ("disponible", "Disp.", 50), ("kg_txt", "Kg disp.", 70), ("precio_txt", "Precio/kg", 80),
                ("finca", "Finca", 110), ("municipio", "Municipio", 95), ("departamento", "Departamento", 90),
                ("temp_txt", "Temp.", 50), ("productor", "Productor", 120), ("cooperativas", "Cooperativas", 180)]
    ORDENES = {"Más recientes": "fecha", "Precio por kg": "precio", "Kg disponibles": "kg"}

    def __init__(self, master, sesion, al_cerrar=None, al_negocio=None):
        super().__init__(master)
        self.sesion = sesion
        self.al_cerrar = al_cerrar
        self.al_negocio = al_negocio
        self.admin = es_administrador(sesion)
        self.filas = {}
        self.foto = None
        self.title("Café Conecta - Lotes disponibles")
        self.configure(bg=e.CREMA)
        e.centrar(self, 1280, 780)
        self.minsize(1000, 600)
        self.protocol("WM_DELETE_WINDOW", self.f_salir)
        encabezado(self, "▤", "Lotes disponibles",
                   "Café disponible para negociar · ★ = productor asociado a su cooperativa"
                   if not self.admin else "Café disponible de todos los productores")

        # Botones
        barra = tk.Frame(self, bg=e.CREMA_OSCURO)
        barra.pack(fill="x")
        e.boton(barra, "⌕  Buscar", self.cargar, e.CAFE).pack(side="left", padx=5, pady=10)
        e.boton(barra, "⟲  Limpiar filtros", self.limpiar, e.CAFE_CLARO).pack(side="left", padx=5)
        if _es(sesion, "Comprador"):
            e.boton(barra, "✚  Iniciar negocio con este lote", self.f_negociar, e.VERDE).pack(side="left", padx=5)
        e.boton(barra, "↩  Salir", self.f_salir, e.CAFE_OSCURO).pack(side="right", padx=6)
        e.boton(barra, "⎙  Exportar PDF", self.exportar_pdf, e.CEREZA).pack(side="right", padx=6)
        e.boton(barra, "▦  Exportar Excel", self.exportar_excel, e.VERDE_OSCURO).pack(side="right", padx=6)

        # Filtros
        filtros = tk.Frame(self, bg=e.BLANCO, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
        filtros.pack(fill="x", padx=16, pady=(12, 6))

        def etiqueta(texto, fila, col):
            tk.Label(filtros, text=texto, font=e.F_PEQUENA, bg=e.BLANCO, fg=e.GRIS).grid(
                row=fila, column=col, sticky="w", padx=(12, 4), pady=(8, 0))

        etiqueta("Buscar (código, descripción, finca, productor)", 0, 0)
        self.txt_texto = tk.Entry(filtros, font=e.F_NORMAL, relief="solid", bd=1, width=34)
        self.txt_texto.grid(row=1, column=0, sticky="we", padx=12, ipady=2)
        self.txt_texto.bind("<Return>", lambda ev: self.cargar())
        etiqueta("Variedad", 0, 1)
        self.cmb_variedad = ComboMapa(filtros, 16, con_todos=True)
        self.cmb_variedad.grid(row=1, column=1, padx=12, sticky="w")
        etiqueta("Departamento", 0, 2)
        self.cmb_departamento = ComboMapa(filtros, 18, con_todos=True)
        self.cmb_departamento.grid(row=1, column=2, padx=12, sticky="w")
        etiqueta("Municipio", 0, 3)
        self.cmb_municipio = ComboMapa(filtros, 18, con_todos=True)
        self.cmb_municipio.grid(row=1, column=3, padx=12, sticky="w")
        etiqueta("Cooperativa del productor", 0, 4)
        self.cmb_cooperativa = ComboMapa(filtros, 28, con_todos=True)
        self.cmb_cooperativa.grid(row=1, column=4, padx=12, sticky="w")

        etiqueta("Precio por kg: desde", 2, 0)
        precios = tk.Frame(filtros, bg=e.BLANCO)
        precios.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 10))
        self.txt_min = tk.Entry(precios, font=e.F_NORMAL, relief="solid", bd=1, width=12)
        self.txt_min.pack(side="left", ipady=2)
        tk.Label(precios, text="  hasta  ", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.GRIS).pack(side="left")
        self.txt_max = tk.Entry(precios, font=e.F_NORMAL, relief="solid", bd=1, width=12)
        self.txt_max.pack(side="left", ipady=2)
        etiqueta("Ordenar por", 2, 1)
        self.cmb_orden = ttk.Combobox(filtros, state="readonly", width=16, font=e.F_NORMAL,
                                      values=list(self.ORDENES))
        self.cmb_orden.set("Más recientes")
        self.cmb_orden.grid(row=3, column=1, padx=12, sticky="w", pady=(0, 10))
        self.var_desc = tk.BooleanVar(value=True)
        tk.Checkbutton(filtros, text="De mayor a menor", variable=self.var_desc, bg=e.BLANCO, font=e.F_PEQUENA,
                       command=self.cargar).grid(row=3, column=2, sticky="w", padx=8, pady=(0, 10))
        self.var_todos = tk.BooleanVar(value=False)
        if self.admin:
            tk.Checkbutton(filtros, text="Incluir lotes inactivos o agotados", variable=self.var_todos,
                           bg=e.BLANCO, font=e.F_PEQUENA, command=self.cargar).grid(
                row=3, column=3, columnspan=2, sticky="w", padx=8, pady=(0, 10))
        for combo in (self.cmb_variedad, self.cmb_municipio, self.cmb_cooperativa, self.cmb_orden):
            combo.bind("<<ComboboxSelected>>", lambda ev: self.cargar())
        self.cmb_departamento.bind("<<ComboboxSelected>>", lambda ev: self._al_departamento())

        # Lista + vista previa
        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        lado = tk.Frame(cuerpo, bg=e.BLANCO, width=260, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
        lado.pack(side="right", fill="y", padx=(10, 0))
        lado.pack_propagate(False)
        tk.Label(lado, text="Lote seleccionado", font=e.F_SUBTITULO, bg=e.BLANCO, fg=e.CAFE_OSCURO).pack(
            anchor="w", padx=12, pady=(12, 6))
        self.lbl_foto = tk.Label(lado, text="Seleccione un lote\npara ver su imagen", bg=e.CREMA, fg=e.GRIS,
                                 font=e.F_PEQUENA, width=30, height=9)
        self.lbl_foto.pack(padx=12)
        self.lbl_info = tk.Label(lado, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.TEXTO, justify="left",
                                 wraplength=230, anchor="nw")
        self.lbl_info.pack(fill="both", expand=True, padx=12, pady=8)

        izq = tk.Frame(cuerpo, bg=e.CREMA)
        izq.pack(side="left", fill="both", expand=True)
        marco, self.arbol = tabla(izq, self.COLUMNAS, alto=14)
        marco.pack(fill="both", expand=True)
        self.arbol.bind("<<TreeviewSelect>>", self._al_seleccionar)
        self.arbol.bind("<Double-1>", lambda ev: self.f_negociar() if _es(sesion, "Comprador") else None)
        self.lbl_totales = tk.Label(izq, text="", font=e.F_NEGRITA, bg=e.CREMA, fg=e.CAFE_OSCURO, justify="left",
                                    anchor="w")
        self.lbl_totales.pack(fill="x", pady=(6, 0))

        self._cargar_opciones()
        self.cargar()

    def _cargar_opciones(self):
        for combo, resultado in ((self.cmb_variedad, LogicaCatalogo.opciones_variedad()),
                                 (self.cmb_departamento, LogicaUbicacion.departamentos()),
                                 (self.cmb_cooperativa, LogicaCooperativa.opciones())):
            combo.opciones(resultado["datos"] if resultado["exito"] else [])
        self.cmb_municipio.opciones([])

    def _al_departamento(self):
        iddep = self.cmb_departamento.valor()
        resultado = LogicaUbicacion.municipios(iddep) if iddep else {"exito": True, "datos": []}
        self.cmb_municipio.opciones(resultado["datos"] if resultado["exito"] else [])
        self.cargar()

    def limpiar(self):
        self.txt_texto.delete(0, "end")
        self.txt_min.delete(0, "end")
        self.txt_max.delete(0, "end")
        self.cmb_orden.set("Más recientes")
        self.var_desc.set(True)
        self.var_todos.set(False)
        self._cargar_opciones()
        self.cargar()

    def consultar(self):
        return LogicaCatalogo.listar(
            self.sesion, texto=self.txt_texto.get(), codigotv=self.cmb_variedad.valor(),
            iddepartamento=self.cmb_departamento.valor(), idmunicipio=self.cmb_municipio.valor(),
            nit=self.cmb_cooperativa.valor(), precio_min=self.txt_min.get(), precio_max=self.txt_max.get(),
            orden=self.ORDENES[self.cmb_orden.get()], descendente=self.var_desc.get(),
            incluir_todos=self.var_todos.get())

    def cargar(self):
        datos = _datos(self.consultar(), self, "Lotes disponibles")
        if datos is None:
            return
        self.filas = {}
        for fila in datos["filas"]:
            fila["asociado_txt"] = "★" if fila["asociado"] else ""
            fila["peso_txt"] = _numero_bonito(fila["peso"])
            fila["kg_txt"] = f"{fila['kg_disponibles']:,.0f}".replace(",", ".")
            fila["precio_txt"] = pesos(fila["precio"])
            fila["temp_txt"] = f"{_numero_bonito(fila['temperatura'])} °C"
            self.filas[fila["codigoc"]] = fila
        llenar(self.arbol, self.COLUMNAS, datos["filas"], "codigoc",
               lambda f: None if f["estado"] == ACTIVO and f["disponible"] > 0 else "inactivo")
        totales = "   ·   ".join(f"{v}: {kg:,.0f} kg".replace(",", ".") for v, kg in datos["totales"].items())
        self.lbl_totales.config(text=f"{len(datos['filas'])} lote(s).   Total disponible por variedad:   "
                                     + (totales or "—"))
        self.datos_actuales = datos

    def _al_seleccionar(self, _evento=None):
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        fila = self.filas[seleccion[0]]
        resultado = LogicaLote.imagen(fila["codigoc"])
        self.foto = miniatura(resultado["datos"], 230, 160) if resultado["exito"] else None
        if self.foto is not None:
            self.lbl_foto.config(image=self.foto, text="", width=230, height=160)
        else:
            self.lbl_foto.config(image="", text="Sin vista previa", width=30, height=9)
        estado = "" if fila["estado"] == ACTIVO and fila["disponible"] > 0 else \
            f"\nEstado: {fila['estado']}{' · agotado' if fila['disponible'] <= 0 else ''}"
        self.lbl_info.config(text=(
            f"{fila['codigoc']} · {fila['variedad']}\n{fila['descripcion']}\n\n"
            f"Empaque: {fila['empaque']} de {fila['peso_txt']} kg\n"
            f"Disponibles: {fila['disponible']} empaque(s) = {fila['kg_txt']} kg\n"
            f"Precio: {fila['precio_txt']} por kg\n\n"
            f"Finca {fila['finca']} · {fila['municipio']}, {fila['departamento']} · {fila['temp_txt']}\n"
            f"Productor: {fila['productor']}\nCooperativas: {fila['cooperativas'] or '—'}"
            + ("\n★ Asociado a su cooperativa" if fila["asociado"] else "") + estado))

    def f_negociar(self):
        seleccion = self.arbol.selection()
        if not seleccion:
            messagebox.showinfo("Iniciar negocio", "Seleccione primero un lote de la lista.", parent=self)
            return
        fila = self.filas[seleccion[0]]
        EditorNegocio(self, self.sesion, documento=fila["documento"], lote_inicial=fila["codigoc"],
                      al_guardar=lambda _id: (self.cargar(), self.al_negocio and self.al_negocio()))

    # ---------------- Exportación ----------------
    def _filas_exportar(self):
        encabezados = ["Lote", "Asociado", "Variedad", "Descripción", "Empaque", "Peso (kg)", "Disponibles",
                       "Kg disponibles", "Precio/kg", "Finca", "Municipio", "Departamento", "Temp. (°C)",
                       "Productor", "Cooperativas"]
        filas = [[f["codigoc"], "Sí" if f["asociado"] else "", f["variedad"], f["descripcion"], f["empaque"],
                  float(f["peso"]), f["disponible"], f["kg_disponibles"], float(f["precio"]), f["finca"],
                  f["municipio"], f["departamento"], float(f["temperatura"]), f["productor"], f["cooperativas"] or ""]
                 for f in self.datos_actuales["filas"]]
        return encabezados, filas

    def _ruta(self, extension, tipo):
        return filedialog.asksaveasfilename(parent=self, defaultextension=extension, filetypes=[(tipo, "*" + extension)],
                                            initialfile=f"lotes_disponibles_{datetime.now():%Y%m%d_%H%M}{extension}")

    def exportar_excel(self):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            messagebox.showwarning("Exportar", "Falta la librería openpyxl.\nInstálela con: pip install openpyxl",
                                   parent=self)
            return
        ruta = self._ruta(".xlsx", "Libro de Excel")
        if not ruta:
            return
        encabezados, filas = self._filas_exportar()
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Lotes disponibles"
        hoja.append([f"Café Conecta · Lotes disponibles · {datetime.now():%Y-%m-%d %H:%M}"])
        hoja["A1"].font = Font(bold=True, size=14, color="3E2723")
        hoja.append([])
        hoja.append(encabezados)
        for celda in hoja[3]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="3E2723")
            celda.alignment = Alignment(vertical="center")
        for fila in filas:
            hoja.append(fila)
        for n in range(4, 4 + len(filas)):
            hoja[f"I{n}"].number_format = '"$"#,##0'
            hoja[f"H{n}"].number_format = "#,##0"
        hoja.append([])
        hoja.append(["Total disponible por variedad"])
        hoja.cell(hoja.max_row, 1).font = Font(bold=True)
        for variedad, kg in self.datos_actuales["totales"].items():
            hoja.append([variedad, "", "", "", "", "", "", kg])
            hoja.cell(hoja.max_row, 8).number_format = "#,##0"
        anchos = [8, 9, 11, 40, 26, 9, 11, 13, 12, 18, 16, 15, 10, 22, 34]
        for i, ancho in enumerate(anchos):
            hoja.column_dimensions[chr(65 + i)].width = ancho
        hoja.freeze_panes = "A4"
        libro.save(ruta)
        messagebox.showinfo("Exportar", f"Listado exportado a Excel:\n{ruta}", parent=self)

    def exportar_pdf(self):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import landscape, letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            messagebox.showwarning("Exportar", "Falta la librería reportlab.\nInstálela con: pip install reportlab",
                                   parent=self)
            return
        ruta = self._ruta(".pdf", "Documento PDF")
        if not ruta:
            return
        estilos = getSampleStyleSheet()
        chico = estilos["BodyText"].clone("chico", fontSize=7, leading=8.5)
        _, filas = self._filas_exportar()
        datos = [["Lote", "Variedad", "Descripción", "Empaque", "Disp.", "Kg disp.", "Precio/kg", "Finca / ubicación",
                  "Productor", "Cooperativas"]]
        for f in filas:
            datos.append([f[0] + (" ★" if f[1] else ""), f[2], Paragraph(f[3], chico), Paragraph(f"{f[4]} de {f[5]:g} kg", chico),
                          f[6], f"{f[7]:,.0f}".replace(",", "."), pesos(f[8]),
                          Paragraph(f"{f[9]} · {f[10]}, {f[11]} · {f[12]:g} °C", chico), Paragraph(f[13], chico),
                          Paragraph(f[14], chico)])
        documento = SimpleDocTemplate(ruta, pagesize=landscape(letter), leftMargin=1 * cm, rightMargin=1 * cm,
                                      topMargin=1 * cm, bottomMargin=1 * cm, title="Lotes disponibles")
        tabla_pdf = Table(datos, repeatRows=1, colWidths=[1.6 * cm, 1.9 * cm, 4.6 * cm, 3.2 * cm, 1.1 * cm, 1.6 * cm,
                                                          1.9 * cm, 4.4 * cm, 2.8 * cm, 3.0 * cm])
        tabla_pdf.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3e2723")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f1ea")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d7ccc8"))]))
        totales = "   ·   ".join(f"{v}: {kg:,.0f} kg".replace(",", ".") for v, kg in self.datos_actuales["totales"].items())
        documento.build([Paragraph("Café Conecta · Lotes disponibles", estilos["Title"]),
                         Paragraph(f"Generado el {datetime.now():%Y-%m-%d %H:%M} por {self.sesion['usuario']}. "
                                   f"{len(filas)} lote(s). ★ = productor asociado a su cooperativa.", estilos["BodyText"]),
                         Spacer(1, 8), tabla_pdf, Spacer(1, 10),
                         Paragraph(f"<b>Total disponible por variedad:</b> {totales or '—'}", estilos["BodyText"])])
        messagebox.showinfo("Exportar", f"Listado exportado a PDF:\n{ruta}", parent=self)

    def f_salir(self):
        self.destroy()
        if self.al_cerrar:
            self.al_cerrar()


# =====================================================================
# HU-07 · Editor de negocio (cabecera + detalle de lotes)
# =====================================================================
class EditorNegocio(tk.Toplevel):
    COL_LOTES = [("codigoc", "Lote", 60), ("variedad", "Variedad", 80), ("descripcion", "Descripción", 230),
                 ("empaque", "Empaque", 150), ("peso_txt", "Peso (kg)", 65), ("disponible", "Disponibles", 75),
                 ("precio_txt", "Precio/kg", 85)]
    COL_LINEAS = [("codigoc", "Lote", 60), ("variedad", "Variedad", 80), ("empaque", "Empaque", 150),
                  ("cantidad", "Cantidad", 65), ("peso_txt", "Peso (kg)", 65), ("kg", "Kg", 65),
                  ("precio_txt", "Precio acordado/kg", 115), ("subtotal_txt", "Subtotal", 110)]

    def __init__(self, master, sesion, idnegocio=None, documento=None, lote_inicial=None, al_guardar=None):
        super().__init__(master)
        self.sesion = sesion
        self.idnegocio = idnegocio
        self.al_guardar = al_guardar
        self.lotes = {}
        self.lineas = []        # [{codigoc, cantidad, precio_kg, ...}]
        self.title("Café Conecta - " + ("Modificar negocio" if idnegocio else "Nuevo negocio"))
        self.configure(bg=e.CREMA)
        e.centrar(self, 1040, 760)
        self.minsize(900, 640)
        self.transient(master)
        negocio = None
        if idnegocio:
            detalle = LogicaNegocio.detalle(idnegocio, sesion)
            if not detalle["exito"]:
                messagebox.showwarning("Negocio", detalle["mensaje"], parent=master)
                self.destroy()
                return
            negocio = detalle["datos"]["negocio"]
            documento = negocio["documento"]
        encabezado(self, "⇆", f"Modificar negocio {negocio['codigoe']}" if negocio else "Nuevo negocio",
                   f"Comprador: {sesion.get('cooperativa') or ''}")

        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=10)

        # Cabecera
        cab = tk.Frame(cuerpo, bg=e.BLANCO, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
        cab.pack(fill="x")
        tk.Label(cab, text="Productor *", font=e.F_NEGRITA, bg=e.BLANCO).grid(row=0, column=0, sticky="w",
                                                                            padx=12, pady=(10, 0))
        self.cmb_productor = ComboMapa(cab, 38)
        self.cmb_productor.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))
        self.cmb_productor.bind("<<ComboboxSelected>>", lambda ev: self._al_productor(limpiar=True))
        tk.Label(cab, text="Medio de pago *", font=e.F_NEGRITA, bg=e.BLANCO).grid(row=0, column=1, sticky="w",
                                                                                padx=12, pady=(10, 0))
        self.cmb_medio = ComboMapa(cab, 24)
        self.cmb_medio.grid(row=1, column=1, sticky="w", padx=12, pady=(0, 4))
        tk.Label(cab, text="Descripción u observaciones", font=e.F_NEGRITA, bg=e.BLANCO).grid(
            row=0, column=2, sticky="w", padx=12, pady=(10, 0))
        self.txt_descripcion = tk.Entry(cab, font=e.F_NORMAL, relief="solid", bd=1, width=40)
        self.txt_descripcion.grid(row=1, column=2, sticky="we", padx=12, pady=(0, 4), ipady=2)
        self.lbl_asociado = tk.Label(cab, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.VERDE)
        self.lbl_asociado.grid(row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 8))

        # Lotes disponibles del productor
        tk.Label(cuerpo, text="1. Lotes disponibles del productor (todos los lotes deben ser del mismo productor)",
                 font=e.F_NEGRITA, bg=e.CREMA, fg=e.CAFE_OSCURO).pack(anchor="w", pady=(10, 4))
        marco, self.arbol_lotes = tabla(cuerpo, self.COL_LOTES, alto=5)
        marco.pack(fill="x")
        self.arbol_lotes.bind("<<TreeviewSelect>>", lambda ev: self._al_lote())

        agregar = tk.Frame(cuerpo, bg=e.CREMA)
        agregar.pack(fill="x", pady=6)
        tk.Label(agregar, text="Cantidad de empaques", font=e.F_PEQUENA, bg=e.CREMA).pack(side="left")
        self.txt_cantidad = tk.Entry(agregar, font=e.F_NORMAL, relief="solid", bd=1, width=8)
        self.txt_cantidad.pack(side="left", padx=(4, 14), ipady=2)
        tk.Label(agregar, text="Precio acordado por kg ($)", font=e.F_PEQUENA, bg=e.CREMA).pack(side="left")
        self.txt_precio = tk.Entry(agregar, font=e.F_NORMAL, relief="solid", bd=1, width=12)
        self.txt_precio.pack(side="left", padx=(4, 14), ipady=2)
        e.boton(agregar, "⬇  Agregar al detalle", self.agregar_linea, e.VERDE, fuente=e.F_PEQUENA).pack(side="left")
        self.lbl_previo = tk.Label(agregar, text="", font=e.F_PEQUENA, bg=e.CREMA, fg=e.GRIS)
        self.lbl_previo.pack(side="left", padx=10)
        for caja in (self.txt_cantidad, self.txt_precio):
            caja.bind("<KeyRelease>", lambda ev: self._previo())

        # Detalle
        tk.Label(cuerpo, text="2. Detalle del negocio (subtotal = cantidad × peso por empaque × precio por kg)",
                 font=e.F_NEGRITA, bg=e.CREMA, fg=e.CAFE_OSCURO).pack(anchor="w", pady=(8, 4))
        marco, self.arbol_lineas = tabla(cuerpo, self.COL_LINEAS, alto=5)
        marco.pack(fill="both", expand=True)
        abajo = tk.Frame(cuerpo, bg=e.CREMA)
        abajo.pack(fill="x", pady=(6, 0))
        e.boton(abajo, "✕  Quitar línea", self.quitar_linea, e.CAFE_CLARO, fuente=e.F_PEQUENA).pack(side="left")
        self.lbl_total = tk.Label(abajo, text="Valor total: $0", font=(e.FUENTE, 15, "bold"), bg=e.CREMA,
                                  fg=e.VERDE_OSCURO)
        self.lbl_total.pack(side="right")

        botones = tk.Frame(self, bg=e.CREMA_OSCURO)
        botones.pack(fill="x", side="bottom")
        e.boton(botones, "↩  Cerrar sin guardar", self.destroy, e.CAFE_OSCURO).pack(side="right", padx=8, pady=10)
        e.boton(botones, "✔  " + ("Guardar cambios y notificar" if idnegocio else "Proponer negocio y notificar"),
                self.f_guardar, e.VERDE_OSCURO).pack(side="right", padx=8, pady=10)
        tk.Label(botones, text="El productor recibirá un WhatsApp con el resumen y un enlace para aceptar o rechazar.",
                 font=e.F_PEQUENA, bg=e.CREMA_OSCURO, fg=e.GRIS).pack(side="left", padx=12)

        # Datos iniciales
        medios = LogicaListas.medios_pago()
        self.cmb_medio.opciones(medios["datos"] if medios["exito"] else [])
        productores = LogicaProductor.opciones(solo_activos=True)
        self.cmb_productor.opciones(productores["datos"] if productores["exito"] else [])
        if negocio:
            self.cmb_productor.poner(documento)
            self.cmb_productor.config(state="disabled")
            self.cmb_medio.poner(negocio["idmedio"])
            self.txt_descripcion.insert(0, negocio["descripcion"] or "")
            self._al_productor(limpiar=True)
            for linea in detalle["datos"]["lineas"]:
                self._agregar(linea["codigoc"], int(linea["cantidad"]), float(linea["precio_kg"]))
        elif documento:
            self.cmb_productor.poner(documento)
            self._al_productor(limpiar=True)
            if lote_inicial in self.lotes:
                self.arbol_lotes.selection_set(lote_inicial)
                self.arbol_lotes.see(lote_inicial)
                self.txt_cantidad.focus_set()

    def _al_productor(self, limpiar=False):
        documento = self.cmb_productor.valor()
        if limpiar:
            self.lineas = []
            self._pintar_lineas()
        resultado = LogicaNegocio.lotes_de_productor(documento, self.sesion) if documento else \
            {"exito": True, "datos": []}
        filas = resultado["datos"] if resultado["exito"] else []
        self.lotes = {}
        for fila in filas:
            fila["peso_txt"] = _numero_bonito(fila["peso"])
            fila["precio_txt"] = pesos(fila["precio"])
            self.lotes[fila["codigoc"]] = fila
        llenar(self.arbol_lotes, self.COL_LOTES, filas, "codigoc")
        asociado = bool(filas and filas[0]["asociado"])
        self.lbl_asociado.config(
            text=("★ Productor asociado a su cooperativa" if asociado else
                  "Este productor no está asociado a su cooperativa (puede negociar igual).") if documento else "",
            fg=e.VERDE if asociado else e.GRIS)
        if documento and not filas:
            self.lbl_asociado.config(text="Este productor no tiene lotes con café disponible.", fg=e.CEREZA)

    def _al_lote(self):
        seleccion = self.arbol_lotes.selection()
        if not seleccion:
            return
        lote = self.lotes[seleccion[0]]
        self.txt_precio.delete(0, "end")
        self.txt_precio.insert(0, _numero_bonito(lote["precio"]))
        self.txt_cantidad.delete(0, "end")
        self._previo()

    def _previo(self):
        seleccion = self.arbol_lotes.selection()
        try:
            lote = self.lotes[seleccion[0]]
            cantidad = int(self.txt_cantidad.get())
            precio = float(self.txt_precio.get().replace(",", "."))
            self.lbl_previo.config(text=f"= {cantidad} × {lote['peso_txt']} kg × {pesos(precio)} = "
                                        f"{pesos(cantidad * float(lote['peso']) * precio)}")
        except (ValueError, IndexError, KeyError):
            self.lbl_previo.config(text="")

    def _agregar(self, codigoc, cantidad, precio):
        lote = self.lotes.get(codigoc, {})
        peso = float(lote.get("peso", 0))
        self.lineas.append({"codigoc": codigoc, "cantidad": cantidad, "precio_kg": precio, "peso": peso,
                            "variedad": lote.get("variedad", ""), "empaque": lote.get("empaque", "")})
        self._pintar_lineas()

    def agregar_linea(self):
        seleccion = self.arbol_lotes.selection()
        if not seleccion:
            messagebox.showinfo("Agregar", "Seleccione un lote en la lista de lotes disponibles.", parent=self)
            return
        codigoc = seleccion[0]
        if any(l["codigoc"] == codigoc for l in self.lineas):
            messagebox.showwarning("Agregar", f"El lote {codigoc} ya está en el detalle. Un lote no se repite: "
                                              "quítelo y agréguelo de nuevo para cambiarlo.", parent=self)
            return
        try:
            cantidad = int(self.txt_cantidad.get())
        except ValueError:
            messagebox.showwarning("Agregar", "La cantidad debe ser un número entero de empaques.", parent=self)
            return
        try:
            precio = float(self.txt_precio.get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Agregar", "El precio por kg debe ser un número.", parent=self)
            return
        disponible = self.lotes[codigoc]["disponible"]
        if cantidad <= 0 or cantidad > disponible:
            messagebox.showwarning("Agregar", f"La cantidad debe estar entre 1 y {disponible} (disponibles).",
                                   parent=self)
            return
        if precio <= 0:
            messagebox.showwarning("Agregar", "El precio por kg debe ser mayor que cero.", parent=self)
            return
        self._agregar(codigoc, cantidad, precio)
        self.txt_cantidad.delete(0, "end")
        self.lbl_previo.config(text="")

    def quitar_linea(self):
        seleccion = self.arbol_lineas.selection()
        if not seleccion:
            messagebox.showinfo("Quitar", "Seleccione la línea del detalle que desea quitar.", parent=self)
            return
        self.lineas = [l for l in self.lineas if l["codigoc"] != seleccion[0]]
        self._pintar_lineas()

    def _pintar_lineas(self):
        total = 0
        for linea in self.lineas:
            linea["subtotal"] = round(linea["cantidad"] * linea["peso"] * linea["precio_kg"], 2)
            linea["kg"] = f"{linea['cantidad'] * linea['peso']:g}"
            linea["peso_txt"] = f"{linea['peso']:g}"
            linea["precio_txt"] = pesos(linea["precio_kg"])
            linea["subtotal_txt"] = pesos(linea["subtotal"])
            total += linea["subtotal"]
        llenar(self.arbol_lineas, self.COL_LINEAS, self.lineas, "codigoc")
        self.lbl_total.config(text=f"Valor total: {pesos(total)}")

    def f_guardar(self):
        datos = {"documento": self.cmb_productor.valor(), "idmedio": self.cmb_medio.valor(),
                 "descripcion": self.txt_descripcion.get(),
                 "lineas": [{"codigoc": l["codigoc"], "cantidad": l["cantidad"], "precio_kg": l["precio_kg"]}
                            for l in self.lineas]}
        self.config(cursor="watch")
        self.update()
        if self.idnegocio:
            resultado = LogicaNegocio.modificar(self.idnegocio, datos, self.sesion)
        else:
            resultado = LogicaNegocio.guardar(datos, self.sesion)
        self.config(cursor="")
        if _mostrar(resultado, self, "Negocio"):
            self.destroy()
            if self.al_guardar:
                self.al_guardar(resultado["datos"])


# =====================================================================
# HU-07 · Negocios
# =====================================================================
class VentanaNegocios(tk.Toplevel):
    COLUMNAS = [("codigoe", "Negocio", 80), ("fecha_hora", "Fecha y hora", 130), ("cooperativa", "Cooperativa", 200),
                ("productor", "Productor", 150), ("medio_pago", "Medio de pago", 120), ("total_txt", "Valor total", 110),
                ("estado_negocio", "Estado", 95)]
    COL_DETALLE = [("codigoc", "Lote", 60), ("variedad", "Variedad", 80), ("empaque", "Empaque", 150),
                   ("cantidad", "Cantidad", 60), ("peso_txt", "Peso (kg)", 65), ("precio_txt", "Precio/kg", 90),
                   ("subtotal_txt", "Subtotal", 105), ("recibida", "Recibida", 65), ("pendiente", "Por programar", 90)]

    def __init__(self, master, sesion, permitidas=(), al_cerrar=None, abrir_id=None):
        super().__init__(master)
        self.sesion = sesion
        self.al_cerrar = al_cerrar
        self.filas = {}
        self.id_actual = None
        self.title("Café Conecta - Negocios")
        self.configure(bg=e.CREMA)
        e.centrar(self, 1180, 780)
        self.minsize(960, 620)
        self.protocol("WM_DELETE_WINDOW", self.f_salir)
        comprador, productor = _es(sesion, "Comprador"), _es(sesion, "Productor")
        encabezado(self, "⇆", "Negocios", "Mis negocios con productores" if comprador else
                   ("Negocios que me proponen las cooperativas" if productor else "Todos los negocios"))

        barra = tk.Frame(self, bg=e.CREMA_OSCURO)
        barra.pack(fill="x")
        if comprador:
            e.boton(barra, "✚  Nuevo negocio", self.f_nuevo, e.VERDE).pack(side="left", padx=5, pady=10)
            e.boton(barra, "✎  Modificar", self.f_modificar, "#ef6c00").pack(side="left", padx=5)
        if comprador or es_administrador(sesion):
            e.boton(barra, "⊘  Cancelar negocio", self.f_cancelar, e.CEREZA).pack(side="left", padx=5, pady=10)
        if productor:
            e.boton(barra, "✓  Aceptar", self.f_aceptar, e.VERDE).pack(side="left", padx=5, pady=10)
            e.boton(barra, "✕  Rechazar", self.f_rechazar, e.CEREZA).pack(side="left", padx=5)
        e.boton(barra, "⛟  Entregas del negocio", self.f_entregas, e.CAFE).pack(side="left", padx=5, pady=10)
        e.boton(barra, "↩  Salir", self.f_salir, e.CAFE_OSCURO).pack(side="right", padx=6)

        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=10)
        busca = tk.Frame(cuerpo, bg=e.CREMA)
        busca.pack(fill="x", pady=(0, 6))
        tk.Label(busca, text="Buscar:", font=e.F_NEGRITA, bg=e.CREMA).pack(side="left")
        self.txt_buscar = tk.Entry(busca, font=e.F_NORMAL, relief="solid", bd=1)
        self.txt_buscar.pack(side="left", fill="x", expand=True, padx=8, ipady=3)
        self.txt_buscar.bind("<Return>", lambda ev: self.cargar())
        e.boton(busca, "⌕  Consultar", self.cargar, e.CAFE, fuente=e.F_PEQUENA).pack(side="left")
        marco, self.arbol = tabla(cuerpo, self.COLUMNAS, alto=8)
        marco.pack(fill="both", expand=True)
        self.arbol.bind("<<TreeviewSelect>>", lambda ev: self._al_seleccionar())

        caja = tk.Frame(cuerpo, bg=e.BLANCO, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
        caja.pack(fill="both", expand=True, pady=(10, 0))
        self.lbl_titulo = tk.Label(caja, text="Seleccione un negocio para ver su detalle", font=e.F_SUBTITULO,
                                   bg=e.BLANCO, fg=e.CAFE_OSCURO)
        self.lbl_titulo.pack(anchor="w", padx=12, pady=(10, 0))
        self.lbl_info = tk.Label(caja, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.TEXTO, justify="left")
        self.lbl_info.pack(anchor="w", padx=12, pady=(2, 6))
        marco, self.arbol_detalle = tabla(caja, self.COL_DETALLE, alto=5)
        marco.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.cargar(seleccionar=abrir_id)

    def cargar(self, seleccionar=None):
        datos = _datos(LogicaNegocio.listar(self.txt_buscar.get().strip(), self.sesion), self, "Negocios")
        if datos is None:
            return
        self.filas = {}
        for fila in datos:
            fila["total_txt"] = pesos(fila["valor_total"])
            self.filas[str(fila["idnegocio"])] = fila
        llenar(self.arbol, self.COLUMNAS, datos, "idnegocio", lambda f: f["estado_negocio"])
        objetivo = seleccionar if seleccionar is not None else self.id_actual
        if objetivo is not None and str(objetivo) in self.filas:
            self.id_actual = int(objetivo)
            self.arbol.selection_set(str(objetivo))
            self.arbol.see(str(objetivo))
        else:
            self.id_actual = None

    def _al_seleccionar(self):
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        self.id_actual = int(seleccion[0])
        datos = _datos(LogicaNegocio.detalle(self.id_actual, self.sesion), self, "Negocio")
        if datos is None:
            return
        n = datos["negocio"]
        self.lbl_titulo.config(text=f"{n['codigoe']} · {n['estado_negocio']} · {pesos(n['valor_total'])}",
                               fg=COLORES_ESTADO.get(n["estado_negocio"], (e.CAFE_OSCURO,))[0])
        info = (f"Cooperativa: {n['cooperativa']} (comprador {n['comprador']})   ·   Productor: {n['productor']} "
                f"(doc. {n['documento']})\nFecha: {n['fecha_hora']}   ·   Medio de pago: {n['medio_pago']}"
                + (f"   ·   Respuesta: {n['fecha_respuesta']}" if n["fecha_respuesta"] else ""))
        if n["descripcion"]:
            info += f"\nDescripción: {n['descripcion']}"
        if n["motivo_rechazo"]:
            info += f"\nMotivo del rechazo: {n['motivo_rechazo']}"
        entregas = datos["entregas"]
        if entregas:
            info += f"\nEntregas: {len(entregas)} (" + ", ".join(f"{x['code']} {x['estado_entrega']}"
                                                              for x in entregas) + ")"
        self.lbl_info.config(text=info)
        for linea in datos["lineas"]:
            linea["peso_txt"] = _numero_bonito(linea["peso"])
            linea["precio_txt"] = pesos(linea["precio_kg"])
            linea["subtotal_txt"] = pesos(linea["subtotal"])
        llenar(self.arbol_detalle, self.COL_DETALLE, datos["lineas"], "iddetalle")

    def _necesita(self, titulo):
        if self.id_actual is None:
            messagebox.showinfo(titulo, "Seleccione primero un negocio en la lista.", parent=self)
            return True
        return False

    def _refrescar(self, *_):
        self.cargar()
        self._al_seleccionar()

    def f_nuevo(self):
        EditorNegocio(self, self.sesion, al_guardar=lambda idn: self.cargar(seleccionar=idn))

    def f_modificar(self):
        if self._necesita("Modificar"):
            return
        if self.filas[str(self.id_actual)]["estado_negocio"] != "Propuesto":
            messagebox.showinfo("Modificar", "Solo se puede modificar un negocio en estado Propuesto.", parent=self)
            return
        EditorNegocio(self, self.sesion, idnegocio=self.id_actual, al_guardar=self._refrescar)

    def f_cancelar(self):
        if self._necesita("Cancelar"):
            return
        fila = self.filas[str(self.id_actual)]
        if not messagebox.askyesno("Cancelar negocio", f"¿Desea cancelar el negocio {fila['codigoe']}?\n\n"
                                   "No se borra: queda Cancelado (anulado) y lo reservado vuelve al inventario.",
                                   parent=self):
            return
        if _mostrar(LogicaNegocio.cancelar(self.id_actual, self.sesion), self, "Cancelar negocio"):
            self._refrescar()

    def f_aceptar(self):
        if self._necesita("Aceptar"):
            return
        fila = self.filas[str(self.id_actual)]
        if not messagebox.askyesno("Aceptar negocio", f"¿Acepta el negocio {fila['codigoe']} de {fila['cooperativa']} "
                                   f"por {fila['total_txt']}?\n\nLas cantidades se descontarán de lo disponible.",
                                   parent=self):
            return
        if _mostrar(LogicaNegocio.aceptar(self.id_actual, self.sesion), self, "Aceptar negocio"):
            self._refrescar()
            if messagebox.askyesno("Entregas", "¿Desea programar ahora las entregas de este negocio?", parent=self):
                self.f_entregas()

    def f_rechazar(self):
        if self._necesita("Rechazar"):
            return
        fila = self.filas[str(self.id_actual)]
        if fila["estado_negocio"] != "Propuesto":
            messagebox.showinfo("Rechazar", f"Este negocio ya está {fila['estado_negocio']}.", parent=self)
            return
        motivo = simpledialog.askstring("Rechazar negocio", f"Motivo del rechazo del negocio {fila['codigoe']}:",
                                        parent=self)
        if motivo is None:
            return
        if _mostrar(LogicaNegocio.rechazar(self.id_actual, motivo, self.sesion), self, "Rechazar negocio"):
            self._refrescar()

    def f_entregas(self, code_inicial=None):
        if self._necesita("Entregas"):
            return
        fila = self.filas[str(self.id_actual)]
        if fila["estado_negocio"] in ("Propuesto", "Rechazado") or \
                (fila["estado_negocio"] == "Cancelado" and not code_inicial):
            messagebox.showinfo("Entregas", f"El negocio está {fila['estado_negocio']}: las entregas se programan "
                                            "cuando el productor lo acepta.", parent=self)
            return
        return VentanaEntregas(self, self.sesion, self.id_actual, code_inicial=code_inicial,
                               al_cambiar=self._refrescar)

    def f_salir(self):
        self.destroy()
        if self.al_cerrar:
            self.al_cerrar()


# =====================================================================
# HU-08 · Programación de entregas  ·  HU-09 · Confirmación de recibido
# =====================================================================
class VentanaEntregas(tk.Toplevel):
    COL_LINEAS = [("codigoc", "Lote", 60), ("variedad", "Variedad", 80), ("empaque", "Empaque", 150),
                  ("cantidad", "Negociada", 70), ("programada", "Programada", 80), ("recibida", "Recibida", 70),
                  ("pendiente", "Por programar", 90)]
    COL_ENTREGAS = [("code", "Entrega", 70), ("codigoc", "Lote", 60), ("fecha", "Fecha", 85), ("hora", "Hora", 50),
                    ("cantidad", "Cantidad", 60), ("lugar", "Lugar", 200), ("estado_entrega", "Estado", 130),
                    ("cantidad_recibida", "Recibida", 60), ("novedad", "Novedad", 170),
                    ("confirmado_por", "Confirmó", 90)]

    def __init__(self, master, sesion, idnegocio, code_inicial=None, al_cambiar=None):
        super().__init__(master)
        self.sesion = sesion
        self.idnegocio = idnegocio
        self.al_cambiar = al_cambiar
        self.productor = _es(sesion, "Productor")
        self.puede_confirmar = _es(sesion, "Comprador") or es_administrador(sesion)
        self.code_actual = None
        self.entregas = {}
        self.lineas = {}
        self.title("Café Conecta - Entregas")
        self.configure(bg=e.CREMA)
        e.centrar(self, 1180, 800 if self.productor else 640)
        self.minsize(960, 560)
        self.transient(master)
        self.lbl_desc = encabezado(self, "⛟", "Entregas", "")

        barra = tk.Frame(self, bg=e.CREMA_OSCURO)
        barra.pack(fill="x")
        if self.productor:
            for texto, comando, color in (("✚  Nueva", self.f_nueva, e.VERDE),
                                          ("✔  Programar", self.f_programar, e.VERDE_OSCURO),
                                          ("✎  Modificar", self.f_modificar, "#ef6c00"),
                                          ("⊘  Cancelar entrega", self.f_cancelar, e.CEREZA),
                                          ("⛟  Despachar (En tránsito)", self.f_transito, e.CAFE)):
                e.boton(barra, texto, comando, color).pack(side="left", padx=5, pady=10)
        if self.puede_confirmar:
            e.boton(barra, "✓  Confirmar recibido", self.f_confirmar, e.VERDE).pack(side="left", padx=5, pady=10)
        e.boton(barra, "↩  Salir", self.destroy, e.CAFE_OSCURO).pack(side="right", padx=6, pady=10)

        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=10)
        tk.Label(cuerpo, text="Líneas del negocio", font=e.F_NEGRITA, bg=e.CREMA, fg=e.CAFE_OSCURO).pack(anchor="w")
        marco, self.arbol_lineas = tabla(cuerpo, self.COL_LINEAS, alto=3)
        marco.pack(fill="x", pady=(2, 8))

        if self.productor:
            caja = tk.Frame(cuerpo, bg=e.BLANCO, highlightbackground=e.CREMA_OSCURO, highlightthickness=1)
            caja.pack(fill="x", pady=(0, 8))
            self.lbl_modo = tk.Label(caja, text="", font=e.F_PEQUENA, bg=e.BLANCO, fg=e.VERDE)
            self.lbl_modo.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(8, 0))
            self.campos = {}
            definicion = [("code", "Código de la entrega *", "Ej.: E-001 · no se modifica"),
                          ("iddetalle", "Lote (línea del negocio) *", "La suma no supera lo negociado"),
                          ("fecha", "Fecha *", "AAAA-MM-DD · posterior a hoy"),
                          ("hora", "Hora *", "HH:MM en 24 horas"),
                          ("cantidad", "Cantidad de empaques *", "Entero mayor que cero"),
                          ("lugar", "Lugar de entrega *", "Punto de recibo de la cooperativa"),
                          ("descripcion", "Descripción", "Opcional: vehículo, conductor…")]
            for n, (clave, etiqueta, ayuda) in enumerate(definicion):
                fila, col = 1 + (n // 4) * 3, n % 4
                tk.Label(caja, text=etiqueta, font=e.F_NEGRITA, bg=e.BLANCO).grid(row=fila, column=col, sticky="w",
                                                                                padx=12, pady=(6, 0))
                if clave == "iddetalle":
                    w = ComboMapa(caja, 26)
                else:
                    w = tk.Entry(caja, font=e.F_NORMAL, relief="solid", bd=1, width=28)
                w.grid(row=fila + 1, column=col, sticky="we", padx=12, ipady=2)
                tk.Label(caja, text=ayuda, font=(e.FUENTE, 8), bg=e.BLANCO, fg=e.GRIS).grid(
                    row=fila + 2, column=col, sticky="w", padx=12, pady=(0, 4))
                self.campos[clave] = w

        tk.Label(cuerpo, text="Entregas programadas (clic para cargarla)", font=e.F_NEGRITA, bg=e.CREMA,
                 fg=e.CAFE_OSCURO).pack(anchor="w")
        marco, self.arbol = tabla(cuerpo, self.COL_ENTREGAS, alto=6)
        marco.pack(fill="both", expand=True, pady=(2, 0))
        self.arbol.bind("<<TreeviewSelect>>", lambda ev: self._al_seleccionar())
        self.arbol.bind("<Double-1>", lambda ev: self.f_confirmar() if self.puede_confirmar else None)
        self.cargar(code_inicial)
        if self.productor and code_inicial is None:
            self.f_nueva()

    def cargar(self, seleccionar=None):
        datos = _datos(LogicaNegocio.detalle(self.idnegocio, self.sesion), self, "Entregas")
        if datos is None:
            return
        n = self.negocio = datos["negocio"]
        self.lbl_desc.config(text=f"Negocio {n['codigoe']} ({n['estado_negocio']}) · {n['productor']} → "
                                  f"{n['cooperativa']}")
        self.lineas = {str(l["iddetalle"]): l for l in datos["lineas"]}
        llenar(self.arbol_lineas, self.COL_LINEAS, datos["lineas"], "iddetalle")
        self.entregas = {x["code"]: x for x in datos["entregas"]}
        llenar(self.arbol, self.COL_ENTREGAS, datos["entregas"], "code", lambda x: x["estado_entrega"])
        if self.productor:
            self.campos["iddetalle"].opciones(
                [(l["iddetalle"], f"{l['codigoc']} · {l['variedad']} (por programar: {l['pendiente']})")
                 for l in datos["lineas"]])
        objetivo = seleccionar or self.code_actual
        if objetivo and objetivo in self.entregas:
            self.code_actual = objetivo
            self.arbol.selection_set(objetivo)
            self.arbol.see(objetivo)

    def _poner(self, clave, valor):
        w = self.campos[clave]
        if isinstance(w, ComboMapa):
            w.poner(valor)
            return
        estado = w.cget("state")
        w.config(state="normal")
        w.delete(0, "end")
        w.insert(0, "" if valor is None else str(valor))
        w.config(state=estado)

    def _leer(self):
        return {clave: (w.valor() if isinstance(w, ComboMapa) else w.get()) for clave, w in self.campos.items()}

    def _al_seleccionar(self):
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        self.code_actual = seleccion[0]
        if self.productor:
            entrega = self.entregas[self.code_actual]
            for clave in self.campos:
                self._poner(clave, entrega.get(clave))
            self.campos["code"].config(state="disabled")
            self.lbl_modo.config(text=f"Modo: editando la entrega {self.code_actual} · {entrega['estado_entrega']}",
                                 fg=COLORES_ESTADO.get(entrega["estado_entrega"], (e.CAFE,))[0])

    def f_nueva(self):
        self.code_actual = None
        self.arbol.selection_remove(self.arbol.selection())
        self.campos["code"].config(state="normal")
        manana = datetime.now() + timedelta(days=1)
        siguiente = len(self.entregas) + 1
        valores = {"code": f"E-{self.negocio['codigoe'][4:]}-{siguiente}", "fecha": f"{manana:%Y-%m-%d}",
                   "hora": "08:00", "cantidad": "", "lugar": "", "descripcion": "", "iddetalle": None}
        pendientes = [l for l in self.lineas.values() if l["pendiente"] > 0]
        if pendientes:
            valores["iddetalle"] = pendientes[0]["iddetalle"]
            valores["cantidad"] = pendientes[0]["pendiente"]
        anteriores = [x["lugar"] for x in self.entregas.values() if x["lugar"]]
        if anteriores:
            valores["lugar"] = anteriores[-1]
        for clave, valor in valores.items():
            self._poner(clave, valor)
        self.lbl_modo.config(text="Modo: nueva entrega (complete los datos y presione Programar)", fg=e.VERDE)
        self.campos["code"].focus_set()

    def _hecho(self, resultado, titulo, seleccionar=None):
        if _mostrar(resultado, self, titulo):
            self.cargar(seleccionar)
            if self.al_cambiar:
                self.al_cambiar()
            return True
        return False

    def f_programar(self):
        if self.code_actual is not None:
            messagebox.showinfo("Programar", "Esa entrega ya existe. Para cambiarla use Modificar, o presione "
                                             "Nueva para programar otra.", parent=self)
            return
        datos = self._leer()
        if self._hecho(LogicaEntrega.programar(self.idnegocio, datos, self.sesion), "Programar entrega",
                       datos["code"].strip().upper()):
            self.f_nueva()

    def _necesita(self, titulo):
        if self.code_actual is None:
            messagebox.showinfo(titulo, "Seleccione primero una entrega en la lista.", parent=self)
            return True
        return False

    def f_modificar(self):
        if self._necesita("Modificar") or not messagebox.askyesno(
                "Modificar", f"¿Guardar los cambios de la entrega {self.code_actual} y avisar al comprador?",
                parent=self):
            return
        self._hecho(LogicaEntrega.modificar(self.code_actual, self._leer(), self.sesion), "Modificar entrega")

    def f_cancelar(self):
        if self._necesita("Cancelar") or not messagebox.askyesno(
                "Cancelar entrega", f"¿Desea cancelar la entrega {self.code_actual}?\n\nNo se borra: queda Cancelada "
                                    "y su cantidad vuelve a quedar por programar.", parent=self):
            return
        self._hecho(LogicaEntrega.cancelar(self.code_actual, self.sesion), "Cancelar entrega")

    def f_transito(self):
        if self._necesita("Despachar") or not messagebox.askyesno(
                "Despachar", f"¿Marcar la entrega {self.code_actual} como En tránsito (el café ya salió)?", parent=self):
            return
        self._hecho(LogicaEntrega.en_transito(self.code_actual, self.sesion), "En tránsito")

    def f_confirmar(self):
        if self._necesita("Confirmar recibido"):
            return
        entrega = self.entregas[self.code_actual]
        if entrega["estado_entrega"] != "En tránsito":
            textos = {"Programada": "Esta entrega todavía no ha salido (está Programada).",
                      "Cancelada": "No se puede confirmar una entrega Cancelada."}
            messagebox.showinfo("Confirmar recibido", textos.get(
                entrega["estado_entrega"], "Esta entrega ya fue confirmada. No se puede confirmar dos veces."),
                parent=self)
            return
        DialogoConfirmar(self, self.sesion, entrega, al_confirmar=lambda: (self.cargar(),
                                                                           self.al_cambiar and self.al_cambiar()))


class DialogoConfirmar(tk.Toplevel):
    """HU-09: el comprador registra la cantidad recibida y, si hay diferencia o problema, la novedad."""

    def __init__(self, master, sesion, entrega, al_confirmar=None):
        super().__init__(master)
        self.sesion = sesion
        self.entrega = entrega
        self.al_confirmar = al_confirmar
        self.title("Confirmar recibido")
        self.configure(bg=e.BLANCO)
        self.resizable(False, False)
        e.centrar(self, 520, 470)
        self.transient(master)
        self.grab_set()
        tk.Label(self, text=f"✓  Confirmar recibido · {entrega['code']}", font=e.F_SUBTITULO, bg=e.BLANCO,
                 fg=e.CAFE_OSCURO).pack(anchor="w", padx=24, pady=(20, 6))
        tk.Label(self, text=(f"Negocio {entrega['codigoe']}\nProductor: {entrega['productor']}\n"
                             f"Lote: {entrega['codigoc']} · {entrega['lote']}\n"
                             f"Programada: {entrega['fecha']} a las {entrega['hora']} en {entrega['lugar']}\n"
                             f"Cantidad esperada: {entrega['cantidad']} empaque(s)"),
                 font=e.F_NORMAL, bg=e.CREMA, fg=e.TEXTO, justify="left", padx=12, pady=10, wraplength=450,
                 anchor="w").pack(fill="x", padx=24)
        tk.Label(self, text="Cantidad recibida (empaques) *", font=e.F_NEGRITA, bg=e.BLANCO).pack(
            anchor="w", padx=24, pady=(14, 2))
        self.txt_cantidad = tk.Entry(self, font=(e.FUENTE, 12), width=10, relief="solid", bd=1)
        self.txt_cantidad.pack(anchor="w", padx=24, ipady=3)
        self.txt_cantidad.insert(0, str(entrega["cantidad"]))
        tk.Label(self, text="Novedad (obligatoria si hay diferencia o algún problema: humedad, sacos rotos…)",
                 font=e.F_NEGRITA, bg=e.BLANCO, wraplength=470, justify="left").pack(anchor="w", padx=24, pady=(12, 2))
        self.txt_novedad = tk.Text(self, font=e.F_NORMAL, width=56, height=4, relief="solid", bd=1, wrap="word")
        self.txt_novedad.pack(anchor="w", padx=24)
        botones = tk.Frame(self, bg=e.BLANCO)
        botones.pack(fill="x", padx=24, pady=16)
        e.boton(botones, "✓  Confirmar", self.f_confirmar, e.VERDE).pack(side="left")
        e.boton(botones, "Cancelar", self.destroy, e.CAFE_CLARO).pack(side="left", padx=10)
        self.txt_cantidad.focus_set()
        self.txt_cantidad.select_range(0, "end")

    def f_confirmar(self):
        cantidad = self.txt_cantidad.get().strip()
        novedad = self.txt_novedad.get("1.0", "end").strip()
        try:
            diferente = int(cantidad) != int(self.entrega["cantidad"])
        except ValueError:
            diferente = False
        if diferente and not novedad:
            messagebox.showwarning("Confirmar recibido", "La cantidad recibida es diferente a la esperada: describa "
                                                         "la novedad.", parent=self)
            return
        if not messagebox.askyesno("Confirmar recibido", f"¿Confirmar {cantidad} empaque(s) recibidos de la entrega "
                                   f"{self.entrega['code']}?\n\nLa confirmación no se puede repetir.", parent=self):
            return
        resultado = LogicaEntrega.confirmar(self.entrega["code"], cantidad, novedad, self.sesion)
        if _mostrar(resultado, self, "Confirmar recibido"):
            self.destroy()
            if self.al_confirmar:
                self.al_confirmar()


# =====================================================================
# Bitácora de mensajes de WhatsApp
# =====================================================================
class VentanaMensajes(tk.Toplevel):
    COLUMNAS = [("idmensaje", "N.º", 45), ("fecha_hora", "Fecha y hora", 135), ("tipo", "Tipo", 140),
                ("referencia", "Referencia", 85), ("destinatario", "Destinatario", 210), ("telefono", "Teléfono", 105),
                ("medio", "Medio", 100), ("resultado", "Resultado", 80)]

    def __init__(self, master, sesion, al_cerrar=None):
        super().__init__(master)
        self.sesion = sesion
        self.al_cerrar = al_cerrar
        self.filas = {}
        self.title("Café Conecta - Mensajes de WhatsApp")
        self.configure(bg=e.CREMA)
        e.centrar(self, 1100, 720)
        self.protocol("WM_DELETE_WINDOW", self.f_salir)
        encabezado(self, "✉", "Mensajes de WhatsApp", "Bitácora: cada aviso enviado y su resultado")
        barra = tk.Frame(self, bg=e.CREMA_OSCURO)
        barra.pack(fill="x")
        e.boton(barra, "⌕  Consultar", self.cargar, e.CAFE).pack(side="left", padx=5, pady=10)
        e.boton(barra, "⏱  Revisar llegadas ahora", self.f_revisar, e.VERDE).pack(side="left", padx=5)
        e.boton(barra, "↩  Salir", self.f_salir, e.CAFE_OSCURO).pack(side="right", padx=6)
        cuerpo = tk.Frame(self, bg=e.CREMA)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=10)
        busca = tk.Frame(cuerpo, bg=e.CREMA)
        busca.pack(fill="x", pady=(0, 6))
        tk.Label(busca, text="Buscar:", font=e.F_NEGRITA, bg=e.CREMA).pack(side="left")
        self.txt_buscar = tk.Entry(busca, font=e.F_NORMAL, relief="solid", bd=1)
        self.txt_buscar.pack(side="left", fill="x", expand=True, padx=8, ipady=3)
        self.txt_buscar.bind("<Return>", lambda ev: self.cargar())
        marco, self.arbol = tabla(cuerpo, self.COLUMNAS, alto=12)
        marco.pack(fill="both", expand=True)
        self.arbol.tag_configure("Error", foreground="#b71c1c", background="#ffebee")
        self.arbol.bind("<<TreeviewSelect>>", lambda ev: self._al_seleccionar())
        self.txt_mensaje = tk.Text(cuerpo, height=9, font=e.F_NORMAL, relief="solid", bd=1, wrap="word",
                                   bg=e.BLANCO)
        self.txt_mensaje.pack(fill="x", pady=(8, 0))
        self.cargar()

    def cargar(self):
        datos = _datos(LogicaMensaje.listar(self.txt_buscar.get(), self.sesion), self, "Mensajes")
        if datos is None:
            return
        self.filas = {str(f["idmensaje"]): f for f in datos}
        llenar(self.arbol, self.COLUMNAS, datos, "idmensaje", lambda f: "Error" if f["resultado"] == "Error" else None)

    def _al_seleccionar(self):
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        fila = self.filas[seleccion[0]]
        self.txt_mensaje.delete("1.0", "end")
        self.txt_mensaje.insert("1.0", f"{fila['texto']}\n\n— Resultado: {fila['resultado']} · {fila['detalle'] or ''}")

    def f_revisar(self):
        _mostrar(LogicaEntrega.revisar_llegadas(), self, "Revisar llegadas")
        self.cargar()

    def f_salir(self):
        self.destroy()
        if self.al_cerrar:
            self.al_cerrar()


# ---------------------------------------------------------------------
# Funciones que usa el panel principal
# ---------------------------------------------------------------------
def abrir_catalogo(master, sesion, permitidas, al_cerrar=None):
    return VentanaCatalogo(master, sesion, al_cerrar=al_cerrar, al_negocio=al_cerrar)


def abrir_negocios(master, sesion, permitidas, al_cerrar=None, abrir_id=None):
    return VentanaNegocios(master, sesion, permitidas, al_cerrar=al_cerrar, abrir_id=abrir_id)


def abrir_mensajes(master, sesion, permitidas, al_cerrar=None):
    return VentanaMensajes(master, sesion, al_cerrar=al_cerrar)
