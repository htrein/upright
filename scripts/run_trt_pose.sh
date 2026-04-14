#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/run_trt_pose.sh [conda_env_name]
# Default env name is 'axis_monitor' to match your example; you can pass another name.
ENV_NAME="${1:-axis_monitor}"

# Ensure conda is available in this script (user should have run 'conda init' already)
if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found in PATH. Please ensure conda is installed and 'conda init' was run." >&2
  exit 2
fi

echo "Activating conda environment: $ENV_NAME"
# shellcheck disable=SC1091
source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Change to the trt_pose demo folder relative to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="$SCRIPT_DIR/trt_pose/tasks/human_pose"
echo "Changing to demo dir: $DEMO_DIR"
cd "$DEMO_DIR"

python3 camera_demo.py
