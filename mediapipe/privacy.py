import cv2
import numpy as np
import config

def apply_privacy_segmentation(frame, seg_mask, mode):
    mask = cv2.GaussianBlur(seg_mask, (21, 21), 0)
    mask3 = mask[:, :, np.newaxis]   

    if mode == 'silhouette':
        bg = np.full_like(frame, config.SILHOUETTE_COLOR, dtype=np.uint8)
        result = (mask3 * bg + (1 - mask3) * frame).astype(np.uint8)

    elif mode == 'blur':
        k = config.BLUR_KSIZE if config.BLUR_KSIZE % 2 == 1 else config.BLUR_KSIZE + 1
        blurred = cv2.GaussianBlur(frame, (k, k), 0)
        result = (mask3 * blurred + (1 - mask3) * frame).astype(np.uint8)

    elif mode == 'mosaic':
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (int(w * config.MOSAIC_SCALE), int(h * config.MOSAIC_SCALE)), interpolation=cv2.INTER_LINEAR)
        mosaic = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        result = (mask3 * mosaic + (1 - mask3) * frame).astype(np.uint8)
    else:
        result = frame
        
    return result
