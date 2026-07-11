#!/usr/bin/env bash
# build_exe.sh — Gera o executável do Upright para Linux (modo onedir)
#
# Uso:
#   bash scripts/build_exe.sh [nome_do_ambiente_conda]
#
# Exemplo:
#   bash scripts/build_exe.sh mediapipe
#
# Pré-requisitos:
#   - Conda instalado e no PATH
#   - Ambiente conda com todas as dependências (ver environment-mediapipe.yml)
#   - Modelos baixados em mediapipe/models/ (rode scripts/download_mp_tasks.sh antes)

set -euo pipefail

ENV_NAME="${1:-mediapipe}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MEDIAPIPE_DIR="$ROOT_DIR/mediapipe"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build_pyinstaller"

echo "============================================="
echo "  Upright — Build de Executável (Linux)"
echo "============================================="
echo ""

# ── 0. Verifica modelos ────────────────────────────────────────────────────────
if [ ! -f "$MEDIAPIPE_DIR/models/pose_landmarker_full.task" ] || \
   [ ! -f "$MEDIAPIPE_DIR/models/selfie_segmenter.tflite" ]; then
    echo "ERRO: Modelos não encontrados em mediapipe/models/"
    echo "      Execute primeiro: bash scripts/download_mp_tasks.sh"
    exit 1
fi
echo "[OK] Modelos encontrados."

# ── 1. Ativa o ambiente conda ──────────────────────────────────────────────────
echo ""
echo "[1/4] Preparando ambiente..."
if command -v conda > /dev/null 2>&1; then
    # shellcheck disable=SC1091
    source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh"
    conda activate "$ENV_NAME"
    echo "      Conda ativado ($ENV_NAME): $(python --version)"
elif [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
    echo "      Venv ativado: $(python --version)"
else
    echo "      Conda/Venv não encontrado, usando python global: $(python3 --version || echo 'Python ausente')"
    # Alias python para python3 se necessário
    if ! command -v python >/dev/null 2>&1; then
        alias python=python3
        shopt -s expand_aliases
    fi
fi

# ── 2. Instala / verifica PyInstaller ─────────────────────────────────────────
echo ""
echo "[2/4] Verificando PyInstaller..."
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "      Instalando PyInstaller..."
    pip install pyinstaller --quiet
fi
echo "      PyInstaller $(python -c 'import PyInstaller; print(PyInstaller.__version__)')"

# ── 3. Executa PyInstaller via .spec ─────────────────────────────────────────
echo ""
echo "[3/4] Executando PyInstaller (isso pode levar alguns minutos)..."

# WORKAROUND: A pasta do projeto se chama "mediapipe", o que causa um conflito de nome
# (name collision) com a biblioteca do python quando o PyInstaller tenta analisar.
# Nós renomeamos temporariamente a pasta para 'src' para evitar o erro.
cd "$ROOT_DIR"
mv mediapipe src

python -m PyInstaller \
    --noconfirm \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    src/upright.spec

# Restaura o nome original
mv src mediapipe

# ── 4. Resultado ──────────────────────────────────────────────────────────────
echo ""
echo "[4/4] Build concluído!"
echo ""
echo "======================================================="
echo "  Executável gerado em: $DIST_DIR/upright/"
echo "======================================================="
echo ""
echo "  Como rodar:"
echo "    $DIST_DIR/upright/upright"
echo "    $DIST_DIR/upright/upright --gpu   (se GPU disponível)"
echo ""
echo "  Para distribuir, compacte a pasta:"
echo "    tar -czf upright-linux.tar.gz -C $DIST_DIR upright"
echo ""
echo "  ATENÇÃO: posture_history.db e report.html são criados"
echo "  no mesmo diretório do executável na primeira execução."
echo ""
