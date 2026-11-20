"""
Servidor local de enlaces de Café Conecta.

Los mensajes de WhatsApp llevan enlaces como http://127.0.0.1:8765/n/<token>.
Al abrirlos en el mismo computador (por ejemplo desde WhatsApp Web), este pequeño
servidor avisa a la aplicación, que pide iniciar sesión y abre la pantalla para
aceptar el negocio o confirmar la entrega.
"""
import queue
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PEDIDOS = queue.Queue()
PATRON = re.compile(r"/(n|e)/([A-Za-z0-9_-]{8,40})")

PAGINA = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Café Conecta</title>
<style>body{{font-family:Arial,sans-serif;background:#f6f1ea;color:#3e2723;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0}}div{{background:#fff;padding:32px 40px;border-radius:12px;
max-width:460px;box-shadow:0 2px 10px #0002}}h1{{margin-top:0}}</style></head><body><div>
<h1>&#9749; Café Conecta</h1><p>{texto}</p></div></body></html>"""


def interpretar(texto):
    """Convierte un enlace o un código en ('n'|'e'|'codigo', valor)."""
    texto = (texto or "").strip()
    encontrado = PATRON.search(texto)
    if encontrado:
        return encontrado.group(1), encontrado.group(2)
    return ("codigo", texto.upper()) if texto else (None, None)


class _Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        tipo, valor = interpretar(self.path)
        if tipo in ("n", "e"):
            PEDIDOS.put((tipo, valor))
            texto = ("Listo. Vuelva a la ventana de Café Conecta: allí debe iniciar sesión "
                     "(si aún no lo ha hecho) para continuar.")
            codigo = 200
        else:
            texto, codigo = "Este enlace no es válido.", 404
        contenido = PAGINA.format(texto=texto).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def log_message(self, *args):
        pass


def iniciar(puerto):
    """Inicia el servidor en segundo plano. Devuelve False si el puerto ya está en uso."""
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", int(puerto)), _Manejador)
    except OSError:
        return False
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return True
