#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/run_mediapipe.sh [conda_env_name] [--gpu|--cpu]
#   conda_env_name : nome do ambiente conda (padrão: mp_fix)
#   --gpu          : usa GPU para inferência (requer Linux + OpenGL ES)
#   --cpu          : usa CPU (padrão, compatível com todos os sistemas)
ENV_NAME="${1:-mp_fix}"
DEVICE_FLAG="${2:---cpu}"   # segundo argumento: --gpu ou --cpu (padrão: --cpu)

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found in PATH. Please ensure conda is installed and 'conda init' was run." >&2
  exit 2
fi

echo "Activating conda environment: $ENV_NAME"
source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="$SCRIPT_DIR/mediapipe"
echo "Changing to demo dir: $DEMO_DIR"
cd "$DEMO_DIR"

echo "Iniciando com modo: $DEVICE_FLAG"
python3 main.py "$DEVICE_FLAG"
