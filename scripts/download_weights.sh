#!/usr/bin/env bash
set -euo pipefail

# Script simples para baixar o peso do modelo usado pelo demo trt_pose
# Uso: ./scripts/download_weights.sh [--verify] [DEST_PATH]
# Exemplo: ./scripts/download_weights.sh trt_pose/tasks/human_pose/resnet18_baseline_att_224x224_A_epoch_249.pth

DEST_PATH="${1:-trt_pose/tasks/human_pose/resnet18_baseline_att_224x224_A_epoch_249.pth}"
VERIFY="${2:-no}"

URL="https://raw.githubusercontent.com/make2explore/Real-Time-Hand-Pose-Estimation-on-Jetson-Nano/main/Pre-Trained%20Models/trt_pose/resnet18_baseline_att_224x224_A_epoch_249.pth"

mkdir -p "$(dirname "$DEST_PATH")"https://github.com/make2explore/Real-Time-Hand-Pose-Estimation-on-Jetson-Nano/blob/main/Pre-Trained%20Models/trt_pose/resnet18_baseline_att_224x224_A_epoch_249.pth

echo "Baixando pesos para: $DEST_PATH"
if command -v curl >/dev/null 2>&1; then
  curl -L -o "$DEST_PATH" "$URL"
else
  wget -O "$DEST_PATH" "$URL"
fi

echo "Download concluído. Tamanho: $(ls -lh "$DEST_PATH" | awk '{print $5}')"

if [ "$VERIFY" = "--verify" ] || [ "$VERIFY" = "yes" ]; then
  if command -v sha256sum >/dev/null 2>&1; then
    echo "SHA256:"
    sha256sum "$DEST_PATH"
  else
    echo "sha256sum não disponível para verificação. Instale coreutils ou verifique manualmente." >&2
  fi
fi

echo "Pronto. O arquivo deve estar em: $DEST_PATH"
