cd "$(dirname "$0")"
echo "=== Café Conecta ==="
for p in /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if [ -x "$p" ]; then PATH="$(dirname "$p"):$PATH"; break; fi
done
if ! command -v python3 >/dev/null 2>&1; then
  echo "No se encontró Python 3. Instálelo desde https://www.python.org/downloads/ y vuelva a ejecutar."
  read -p "Presione Enter para cerrar..."; exit 1
fi
echo "Python: $(python3 --version)"
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "Este Python no tiene Tkinter. Instale Python desde https://www.python.org/downloads/ (incluye Tkinter)."
  read -p "Presione Enter para cerrar..."; exit 1
fi
echo "Instalando requerimientos..."
python3 -m pip install -q -r requirements.txt 2>/dev/null \
  || python3 -m pip install --user -q -r requirements.txt 2>/dev/null \
  || python3 -m pip install --user -q --break-system-packages -r requirements.txt
python3 -c "import mysql.connector" || { echo "No se pudo instalar mysql-connector-python."; read -p "Enter para cerrar..."; exit 1; }
echo "Requerimientos listos."
echo
python3 preparar_bd.py || { read -p "Presione Enter para cerrar..."; exit 1; }
echo
echo "Abriendo Café Conecta..."
python3 presentacion.py
