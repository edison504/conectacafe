"""Colores, fuentes y dibujos (temática cafetera) compartidos por todas las ventanas."""
import math
import tkinter as tk
from tkinter import ttk

# Paleta inspirada en el café: grano tostado, hoja de cafeto y cereza madura.
CAFE_OSCURO = "#3e2723"
CAFE = "#6d4c41"
CAFE_CLARO = "#a1887f"
CREMA = "#f6f1ea"
CREMA_OSCURO = "#ece3d6"
VERDE = "#2e7d32"
VERDE_OSCURO = "#1b5e20"
VERDE_CLARO = "#a5d6a7"
CEREZA = "#c62828"
DORADO = "#d4a373"
BLANCO = "#ffffff"
GRIS = "#757575"
TEXTO = "#3b2f2a"

FUENTE = "Segoe UI"
F_TITULO = (FUENTE, 22, "bold")
F_SUBTITULO = (FUENTE, 13, "bold")
F_NORMAL = (FUENTE, 10)
F_NEGRITA = (FUENTE, 10, "bold")
F_PEQUENA = (FUENTE, 9)


def configurar_estilos(raiz):
    estilo = ttk.Style(raiz)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass
    estilo.configure("Treeview", font=F_NORMAL, rowheight=26, background=BLANCO,
                     fieldbackground=BLANCO, foreground=TEXTO)
    estilo.configure("Treeview.Heading", font=F_NEGRITA, background=CAFE, foreground=BLANCO, relief="flat")
    estilo.map("Treeview.Heading", background=[("active", CAFE_OSCURO)])
    estilo.map("Treeview", background=[("selected", VERDE)], foreground=[("selected", BLANCO)])
    estilo.configure("TCombobox", padding=4)


def boton(padre, texto, comando, color=VERDE, color_texto=BLANCO, ancho=None, fuente=F_NEGRITA):
    """Botón plano con efecto al pasar el mouse."""
    b = tk.Button(padre, text=texto, command=comando, bg=color, fg=color_texto, font=fuente,
                  activebackground=_oscurecer(color), activeforeground=color_texto,
                  relief="flat", bd=0, cursor="hand2", padx=14, pady=7,
                  disabledforeground="#d7ccc8")
    if ancho:
        b.config(width=ancho)
    b.bind("<Enter>", lambda e: b.config(bg=_oscurecer(color)) if str(b["state"]) != "disabled" else None)
    b.bind("<Leave>", lambda e: b.config(bg=color) if str(b["state"]) != "disabled" else None)
    return b


def deshabilitar(b):
    b.config(state="disabled", bg="#bcaaa4", cursor="arrow")


def _oscurecer(color, factor=0.82):
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))


def centrar(ventana, ancho, alto):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = max((ventana.winfo_screenheight() - alto) // 2 - 30, 0)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")



def _mezclar(c1, c2, t):
    c1, c2 = c1.lstrip("#"), c2.lstrip("#")
    a = [int(c1[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hoja(canvas, x, y, largo, ancho, angulo, color=VERDE):
    """Hoja de cafeto: forma ovalada con punta, rotada `angulo` grados."""
    rad = math.radians(angulo)
    puntos = []
    for i in range(0, 361, 20):
        t = math.radians(i)
        px = largo / 2 * (1 + math.cos(t))
        py = ancho / 2 * math.sin(t) * (1 - 0.35 * math.cos(t))
        puntos += [x + px * math.cos(rad) - py * math.sin(rad), y + px * math.sin(rad) + py * math.cos(rad)]
    canvas.create_polygon(puntos, fill=color, outline=_oscurecer(color, 0.7), smooth=True)
    canvas.create_line(x, y, x + largo * math.cos(rad), y + largo * math.sin(rad),
                       fill=_oscurecer(color, 0.6), width=1)


def cereza(canvas, x, y, r=6, color=CEREZA):
    canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline=_oscurecer(color, 0.7))
    canvas.create_oval(x - r * 0.45, y - r * 0.55, x - r * 0.05, y - r * 0.15, fill="#ef9a9a", outline="")


def rama_cafeto(canvas, x, y, escala=1.0, invertir=False):
    """Rama con hojas y cerezas de café."""
    s = -1 if invertir else 1
    canvas.create_line(x, y, x + s * 170 * escala, y - 60 * escala, fill="#5d4037",
                       width=max(int(4 * escala), 2), smooth=True)
    for i, (dx, dy, ang) in enumerate([(30, -12, -70), (60, -22, 40), (95, -34, -60),
                                       (125, -44, 35), (155, -55, -40)]):
        px, py = x + s * dx * escala, y + dy * escala
        angulo = ang if not invertir else 180 - ang
        hoja(canvas, px, py, 62 * escala, 24 * escala, angulo, VERDE if i % 2 else VERDE_OSCURO)
    for dx, dy in [(45, -8), (52, -2), (40, 0), (110, -30), (116, -24), (104, -24)]:
        cereza(canvas, x + s * dx * escala, y + dy * escala, 6 * escala,
               CEREZA if dx % 2 == 0 else "#e53935")


def taza(canvas, x, y, escala=1.0):
    """Taza de café humeante centrada en (x, y)."""
    e = escala
    canvas.create_oval(x - 62 * e, y + 38 * e, x + 62 * e, y + 56 * e, fill="#d7ccc8", outline="")
    canvas.create_arc(x - 45 * e, y - 30 * e, x + 45 * e, y + 50 * e, start=180, extent=180,
                      fill=BLANCO, outline="#bcaaa4", width=2)
    canvas.create_rectangle(x - 45 * e, y - 12 * e, x + 45 * e, y + 10 * e, fill=BLANCO, outline="")
    canvas.create_oval(x - 45 * e, y - 22 * e, x + 45 * e, y - 2 * e, fill=CAFE_OSCURO, outline="#bcaaa4", width=2)
    canvas.create_oval(x + 38 * e, y - 6 * e, x + 66 * e, y + 22 * e, outline=BLANCO, width=int(6 * e))
    for dx in (-18, 0, 18):
        canvas.create_line(x + dx * e, y - 30 * e, x + (dx - 8) * e, y - 48 * e, x + (dx + 6) * e,
                           y - 64 * e, x + (dx - 4) * e, y - 80 * e, fill=BLANCO, width=3, smooth=True)


def paisaje_cafetero(canvas, ancho, alto, con_taza=True, nivel=0.0):
    """Montañas con surcos de cafetales al amanecer."""
    canvas.delete("all")
    for i in range(alto):
        canvas.create_line(0, i, ancho, i, fill=_mezclar("#ffcc80", "#fff3e0", i / alto))
    canvas.create_oval(ancho * 0.70, alto * 0.10, ancho * 0.70 + 70, alto * 0.10 + 70,
                       fill="#ffb74d", outline="")

    capas = [("#81c784", 0.42 + nivel), ("#4caf50", 0.55 + nivel), ("#2e7d32", 0.68 + nivel)]
    for n, (color, base) in enumerate(capas):
        puntos = [0, alto]
        for x in range(0, ancho + 40, 40):
            onda = math.sin(x / (ancho / (2.2 + n)) + n * 1.7) * alto * 0.08
            puntos += [x, alto * base + onda]
        puntos += [ancho, alto]
        canvas.create_polygon(puntos, fill=color, outline="", smooth=True)
        # surcos de cafetal
        for fila in range(4):
            y0 = alto * base + 18 + fila * 16 + n * 4
            if y0 > alto:
                break
            for x in range(10 + (fila % 2) * 12, ancho, 24):
                onda = math.sin(x / (ancho / (2.2 + n)) + n * 1.7) * alto * 0.08
                yy = y0 + onda
                if yy < alto - 4:
                    canvas.create_oval(x - 5, yy - 4, x + 5, yy + 4, fill=_oscurecer(color, 0.75), outline="")
                    if (x + fila) % 3 == 0:
                        canvas.create_oval(x - 1, yy - 1, x + 2, yy + 2, fill=CEREZA, outline="")

    if con_taza:
        taza(canvas, ancho * 0.22, alto * 0.30, 0.8)
