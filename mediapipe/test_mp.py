import cv2
import mediapipe as mp
import math
import collections
import numpy as np

mp_pose = mp.solutions.pose
mp_selfie = mp.solutions.selfie_segmentation

# ====== CONFIG ======
VISIBILITY_THRESHOLD = 0.5
EMA_ALPHA = 0.25
FPS_ESTIMATE = 30
POSTURE_WINDOW_SEC = 30
POSTURE_WINDOW = POSTURE_WINDOW_SEC * FPS_ESTIMATE
BAD_POSTURE_THRESHOLD = 0.45

# --- Privacidade ---
PRIVACY_MODE = False
PRIVACY_STYLE = 'silhouette'  # 'silhouette', 'blur', 'mosaic' — pressione 'm' para ciclar
SILHOUETTE_COLOR = (30, 30, 30)   # BGR — quase preto; mude à vontade
BLUR_KSIZE = 55
MOSAIC_SCALE = 0.05
SEG_THRESHOLD = 0.6   # confiança mínima para pixel ser considerado "pessoa"

# ====== ESTADO GLOBAL ======
_ema_state = {}
_posture_history = collections.deque(maxlen=POSTURE_WINDOW)

# ====== EMA ======
def ema(key, value, alpha=EMA_ALPHA):
    prev = _ema_state.get(key, value)
    new = alpha * value + (1 - alpha) * prev
    _ema_state[key] = new
    return new

# ====== SCORE CONTÍNUO 0..1 ======
def angle_to_score(angle_deg, max_angle=45.0):
    x = max(0.0, min(angle_deg / max_angle, 1.0))
    return 1.0 - x

# ====== COR INTERPOLADA verde→amarelo→vermelho (BGR) ======
def score_to_color(score):
    score = max(0.0, min(1.0, score))
    if score >= 0.5:
        t = (score - 0.5) * 2.0
        r = int((1 - t) * 255)
        g = 220
        b = 0
    else:
        t = score * 2.0
        r = 255
        g = int(t * 200)
        b = 0
    return (b, g, r)

# ====== ÂNGULOS ======
def angle_horizontal(p1, p2):
    dx = p2[0] - p1[0]
    dy = p1[1] - p2[1]
    return math.degrees(math.atan2(dy, dx))

# ====== UTILS ======
def get_pixel(lm, w, h):
    return int(lm.x * w), int(lm.y * h)

# ====== BARRA HUD ======
def draw_bar(img, x, y, w, h, frac, color):
    cv2.rectangle(img, (x, y), (x + w, y + h), (50, 50, 50), -1)
    filled = int(w * max(0.0, min(1.0, frac)))
    if filled > 0:
        cv2.rectangle(img, (x, y), (x + filled, y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (120, 120, 120), 1)

# ====== PRIVACIDADE via máscara de segmentação ======
def apply_privacy_segmentation(frame, seg_mask, mode):
    """
    seg_mask: float32 H×W, valores 0..1 (1 = pessoa).
    O GaussianBlur na máscara suaviza as bordas para evitar corte duro.
    """
    mask = cv2.GaussianBlur(seg_mask, (21, 21), 0)
    mask3 = mask[:, :, np.newaxis]   # broadcast para H×W×3

    if mode == 'silhouette':
        bg = np.full_like(frame, SILHOUETTE_COLOR, dtype=np.uint8)
        result = (mask3 * bg + (1 - mask3) * frame).astype(np.uint8)

    elif mode == 'blur':
        k = BLUR_KSIZE if BLUR_KSIZE % 2 == 1 else BLUR_KSIZE + 1
        blurred = cv2.GaussianBlur(frame, (k, k), 0)
        result = (mask3 * blurred + (1 - mask3) * frame).astype(np.uint8)

    elif mode == 'mosaic':
        fh, fw = frame.shape[:2]
        sw = max(1, int(fw * MOSAIC_SCALE))
        sh = max(1, int(fh * MOSAIC_SCALE))
        small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_NEAREST)
        pixelated = cv2.resize(small, (fw, fh), interpolation=cv2.INTER_NEAREST)
        result = (mask3 * pixelated + (1 - mask3) * frame).astype(np.uint8)

    else:
        result = frame

    return result

# ====== MAIN ======
cap = cv2.VideoCapture(0)
cv2.namedWindow("Upright Mediapipe", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("Upright Mediapipe", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

with (
    mp_pose.Pose(model_complexity=1, smooth_landmarks=True) as pose,
    mp_selfie.SelfieSegmentation(model_selection=1) as segmenter
):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        fh, fw = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        res = pose.process(rgb)
        seg_result = segmenter.process(rgb)

        posture = {}

        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark

            def valid(i):
                return lm[i].visibility > VISIBILITY_THRESHOLD

            l_sh = r_sh = None

            # ====== OMBROS ======
            if valid(11) and valid(12):
                l_sh = get_pixel(lm[11], fw, fh)
                r_sh = get_pixel(lm[12], fw, fh)
                angle_raw = angle_horizontal(l_sh, r_sh)
                angle = min(abs(angle_raw), abs(180 - abs(angle_raw)))
                score = ema('shoulder', angle_to_score(angle, max_angle=20.0))
                posture['shoulder'] = (l_sh, r_sh, score, f"{angle:.1f}°")

            # ====== PESCOÇO ======
            if valid(0) and valid(11) and valid(12):
                nose = get_pixel(lm[0], fw, fh)
                neck = (
                    int((lm[11].x + lm[12].x) / 2 * fw),
                    int((lm[11].y + lm[12].y) / 2 * fh)
                )
                dx = nose[0] - neck[0]
                dy = nose[1] - neck[1]
                angle_lat = min(abs(math.degrees(math.atan2(dx, -dy))),
                                abs(180 - abs(math.degrees(math.atan2(dx, -dy)))))
                score_lat = ema('neck_lat', angle_to_score(angle_lat, max_angle=24.0))

                score_fwd = score_lat
                if l_sh and r_sh:
                    sw = math.hypot(l_sh[0] - r_sh[0], l_sh[1] - r_sh[1])
                    if sw > 1e-6:
                        ratio = ema('neck_fwd_ratio',
                                    math.hypot(nose[0] - neck[0], nose[1] - neck[1]) / sw)
                        score_fwd = ema('neck_fwd',
                                        max(0.0, min((ratio - 0.25) / 0.40, 1.0)))

                posture['neck'] = (neck, nose, min(score_lat, score_fwd), f"lat:{angle_lat:.1f}°")

        # ====== PRIVACIDADE (antes de desenhar linhas sobre a pessoa) ======
        if PRIVACY_MODE and seg_result.segmentation_mask is not None:
            seg_mask = (seg_result.segmentation_mask > SEG_THRESHOLD).astype(np.float32)
            frame = apply_privacy_segmentation(frame, seg_mask, PRIVACY_STYLE)

        # ====== LINHAS POR SCORE (desenhadas por cima do efeito) ======
        for key, (p1, p2, score, _) in posture.items():
            color = score_to_color(score)
            cv2.line(frame, p1, p2, color, 4)
            cv2.circle(frame, p1, 7, (255, 255, 255), -1)
            cv2.circle(frame, p2, 7, (255, 255, 255), -1)

        # ====== MÉTRICA GLOBAL ======
        global_score = (sum(v[2] for v in posture.values()) / len(posture)) if posture else 1.0
        _posture_history.append(global_score < BAD_POSTURE_THRESHOLD)
        pct_bad = (sum(_posture_history) / len(_posture_history)) if _posture_history else 0.0

        # ====== HUD ======
        hud_x = fw - 310
        hud_y = 18
        bar_w = 180
        bar_h = 12
        n_rows = len(posture) + 3
        hud_h = 38 * n_rows + 20
        overlay = frame.copy()
        cv2.rectangle(overlay, (hud_x - 12, hud_y - 12), (fw - 8, hud_y + hud_h), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        y_cur = hud_y + 10
        label_map = {'shoulder': 'Ombros', 'neck': 'Pescoco'}

        for key, (p1, p2, score, _) in posture.items():
            color = score_to_color(score)
            cv2.putText(frame, f"{label_map.get(key, key)}", (hud_x, y_cur),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 200, 200), 1, cv2.LINE_AA)
            y_cur += 16
            draw_bar(frame, hud_x, y_cur, bar_w, bar_h, score, color)
            cv2.putText(frame, f"{score:.2f}", (hud_x + bar_w + 6, y_cur + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
            y_cur += bar_h + 10

        cv2.line(frame, (hud_x, y_cur), (fw - 12, y_cur), (60, 60, 60), 1)
        y_cur += 8

        gc = score_to_color(global_score)
        cv2.putText(frame, "Score Global", (hud_x, y_cur),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 200, 200), 1, cv2.LINE_AA)
        y_cur += 16
        draw_bar(frame, hud_x, y_cur, bar_w, bar_h, global_score, gc)
        cv2.putText(frame, f"{global_score:.2f}", (hud_x + bar_w + 6, y_cur + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, gc, 1, cv2.LINE_AA)
        y_cur += bar_h + 12

        pct_color = score_to_color(1.0 - pct_bad)
        cv2.putText(frame, f"Postura ruim (ult. {POSTURE_WINDOW_SEC}s): {pct_bad*100:.0f}%",
                    (hud_x, y_cur + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, pct_color, 1, cv2.LINE_AA)
        y_cur += 26

        priv_label = f"[P] {'ON (' + PRIVACY_STYLE + ')' if PRIVACY_MODE else 'OFF'}  [M] ciclar"
        cv2.putText(frame, priv_label, (hud_x, y_cur + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 140, 140), 1, cv2.LINE_AA)

        # Aviso piscante
        if global_score < BAD_POSTURE_THRESHOLD:
            tick = (cv2.getTickCount() // int(cv2.getTickFrequency() * 0.5)) % 2
            if tick == 0:
                cv2.rectangle(frame, (4, 4), (fw - 4, fh - 4), (0, 0, 220), 3)
                cv2.putText(frame, "! CORRIJA A POSTURA !", (fw // 2 - 160, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA)

        cv2.imshow("Upright Mediapipe", frame)

        key = cv2.waitKey(1)
        if key == 27:
            break
        elif key == ord('p'):
            PRIVACY_MODE = not PRIVACY_MODE
        elif key == ord('m'):
            modes = ['silhouette', 'blur', 'mosaic']
            PRIVACY_STYLE = modes[(modes.index(PRIVACY_STYLE) + 1) % len(modes)]

cap.release()
cv2.destroyAllWindows()