import cv2
import numpy as np
import config

def apply_privacy_segmentation(frame, seg_mask, mode):
    # Converte a máscara suave do MediaPipe em booleana para indexação direta.
    # O uso de indexação numpy (frame[mask]) elimina multiplicações de ponto flutuante, 
    # Garantir que a máscara seja estritamente 2D (H, W), eliminando possíveis canais unitários (H, W, 1)
    mask_bool = np.squeeze(seg_mask > 0.5)

    if mode == 'silhouette':
        bg = np.full_like(frame, config.SILHOUETTE_COLOR, dtype=np.uint8)
        frame[mask_bool] = bg[mask_bool]

    elif mode == 'blur':
        k = config.BLUR_KSIZE if config.BLUR_KSIZE % 2 == 1 else config.BLUR_KSIZE + 1
        blurred = cv2.GaussianBlur(frame, (k, k), 0)
        frame[mask_bool] = blurred[mask_bool]

    elif mode == 'mosaic':
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (int(w * config.MOSAIC_SCALE), int(h * config.MOSAIC_SCALE)), interpolation=cv2.INTER_LINEAR)
        mosaic = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        frame[mask_bool] = mosaic[mask_bool]
        
    return frame
