#!/usr/bin/env bash
set -euo pipefail

# Cria a pasta de modelos se não existir
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$SCRIPT_DIR/../mediapipe/models"
mkdir -p "$MODELS_DIR"

echo "Baixando modelos do MediaPipe (Tasks API)..."

POSE_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
SEG_URL="https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"

POSE_DEST="$MODELS_DIR/pose_landmarker_full.task"
SEG_DEST="$MODELS_DIR/selfie_segmenter.tflite"

download_file() {
  local url=$1
  local dest=$2
  echo "Baixando $dest..."
  if command -v curl >/dev/null 2>&1; then
    curl -# -L -o "$dest" "$url"
  else
    wget -q --show-progress -O "$dest" "$url"
  fi
}

if [ ! -f "$POSE_DEST" ]; then
  download_file "$POSE_URL" "$POSE_DEST"
else
  echo "Modelo Pose Landmarker já existe: $POSE_DEST"
fi

if [ ! -f "$SEG_DEST" ]; then
  download_file "$SEG_URL" "$SEG_DEST"
else
  echo "Modelo Selfie Segmenter já existe: $SEG_DEST"
fi

echo "Pronto! Modelos salvos em: $MODELS_DIR"
