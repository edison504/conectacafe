#!/bin/bash
# Sube los cambios del Parcial II a la rama parcial-2 de github.com/edison504/conectacafe
cd "$(dirname "$0")" || exit 1
echo "=== Subiendo el Parcial II a GitHub ==="
set -e
if [ ! -d .git ]; then
  git init -b main
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin https://github.com/edison504/conectacafe.git
echo "--- Descargando la versión de GitHub..."
git fetch origin
if ! git rev-parse --verify -q HEAD >/dev/null; then
  git reset -q origin/main      # toma main como base; no cambia los archivos de la carpeta
fi
git checkout -B parcial-2
git add -A      # todos los archivos de la carpeta (menos __pycache__ y .DS_Store)
echo "--- Archivos que se suben:"
git status --short
if git diff --cached --quiet; then
  echo "No hay cambios nuevos para guardar."
else
  git commit -q -m "Parcial II: HU-01 a HU-05 (productores, fincas, cooperativas, asociaciones y variedades)" \
             -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  echo "--- Commit creado:"
  git log --oneline -1
fi
echo "--- Subiendo la rama parcial-2..."
set +e
git push -u origin parcial-2
RESULTADO=$?
echo
if [ $RESULTADO -eq 0 ]; then
  echo "LISTO: la rama parcial-2 quedó en https://github.com/edison504/conectacafe/tree/parcial-2"
else
  echo "ERROR AL SUBIR (código $RESULTADO). Revise el mensaje de arriba."
fi
read -p "Presione Enter para cerrar..."
