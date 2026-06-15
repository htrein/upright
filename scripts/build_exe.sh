#!/usr/bin/env bash
# =============================================================================
# build_exe.sh — Gera um executável único do Upright Posture Tracking
# usando PyInstaller dentro do ambiente conda especificado.
#
# Uso:
#   ./scripts/build_exe.sh [conda_env_name]
#
# O executável será gerado em: dist/upright
# =============================================================================
set -euo pipefail

ENV_NAME="${1:-mp_fix}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MEDIAPIPE_DIR="$SCRIPT_DIR/mediapipe"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build_pyinstaller"

echo "============================================="
echo " Upright Posture Tracking - Build de Executável"
echo "============================================="
echo ""

# Ativa o conda
if ! command -v conda > /dev/null 2>&1; then
  echo "ERRO: conda não encontrado no PATH." >&2
  exit 2
fi
source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

# Instala PyInstaller no ambiente (se não estiver instalado)
echo "[1/4] Verificando PyInstaller..."
if ! python3 -c "import PyInstaller" 2>/dev/null; then
  echo "      Instalando PyInstaller..."
  pip install pyinstaller --quiet
fi
echo "      PyInstaller OK."

# Descobre onde o mediapipe está instalado para incluir seus dados binários
echo "[2/4] Localizando dados do MediaPipe..."
MP_DATA_PATH=$(python3 -c "import mediapipe, os; print(os.path.dirname(mediapipe.__file__))")
echo "      MediaPipe encontrado em: $MP_DATA_PATH"

# Descobre onde o cv2 está instalado
CV2_PATH=$(python3 -c "import cv2, os; print(os.path.dirname(cv2.__file__))")
echo "      OpenCV encontrado em: $CV2_PATH"

echo "[3/4] Executando PyInstaller..."
cd "$MEDIAPIPE_DIR"

pyinstaller \
  --noconfirm \
  --onefile \
  --name "upright" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR" \
  --add-data "$MP_DATA_PATH:mediapipe" \
  --add-data "$CV2_PATH:cv2" \
  --add-data "models:models" \
  --hidden-import "mediapipe" \
  --hidden-import "mediapipe.tasks" \
  --hidden-import "mediapipe.tasks.python" \
  --hidden-import "mediapipe.tasks.python.vision" \
  --hidden-import "cv2" \
  --hidden-import "numpy" \
  --hidden-import "sqlite3" \
  --hidden-import "tkinter" \
  --hidden-import "codecarbon" \
  --collect-all "mediapipe" \
  main.py

echo ""
echo "[4/4] Build concluído!"
echo ""
echo "======================================================"
echo " Executável gerado em: $DaIST_DIR/upright"
echo "======================================================"
echo ""
echo "Como usar:"
echo "  ./dist/upright            # Roda em modo CPU (padrão, compatível com tudo)"
echo "  ./dist/upright --gpu      # Roda em modo GPU (requer Linux com OpenGL ES)"
echo ""
echo "ATENÇÃO: O executável inclui todos os binários Python/MediaPipe."
echo "O arquivo posture_history.db e a pasta models/ são criados/lidos"
echo "no mesmo diretório de onde o executável for executado."
echo ""
