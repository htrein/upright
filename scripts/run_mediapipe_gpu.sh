#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/run_mediapipe_gpu.sh [conda_env_name]
# Default env name is 'mp_fix' to match your example; you can pass another name.
ENV_NAME="${1:-mp_fix}"

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

python3 test_mp_gpu.py
