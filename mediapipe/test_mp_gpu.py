import cv2
import mediapipe as mp
import math
import collections
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import time
import os

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ====== CONFIG ======
VISIBILITY_THRESHOLD = 0.5 # Confiança mínima (0 a 1) para considerar a parte do corpo visível
EMA_ALPHA = 0.25 # Fator de suavização da reatividade das linhas. Valores menores deixam mais suave.
FPS_ESTIMATE = 30
POSTURE_WINDOW_SEC = 30
POSTURE_WINDOW = POSTURE_WINDOW_SEC * FPS_ESTIMATE
BAD_POSTURE_THRESHOLD = 0.45 # Limiar do Score Global abaixo do qual o alerta de má postura é disparado

# --- Variáveis Injetáveis pela UI ---
MAX_ANGLE_SHOULDER = 20.0 # Ângulo máximo (graus) de desnível aceitável para os ombros
MAX_ANGLE_NECK = 24.0     # Ângulo máximo (graus) de desvio lateral aceitável para o pescoço
NECK_RATIO_BASE = 0.25    # Proporção esperada do comprimento do pescoço em relação aos ombros (usado para inclinação para frente)

# --- Calibração Dinâmica ---
IS_CALIBRATED = False
BASE_ANGLE_SHOULDER = 0.0 

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

# ====== EMA (Média Móvel Exponencial) ======
def ema(key, value, alpha=EMA_ALPHA):
    prev = _ema_state.get(key, value)
    new = alpha * value + (1 - alpha) * prev
    _ema_state[key] = new
    return new

# ====== SCORE CONTÍNUO 0..1 ======
def angle_to_score(angle_deg, max_angle=45.0):
    x = max(0.0, min(angle_deg / max_angle, 1.0))
    return 1.0 - x

# ====== COR INTERPOLADA ======
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
    mask = cv2.GaussianBlur(seg_mask, (21, 21), 0)
    mask3 = mask[:, :, np.newaxis]

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

# ====== TELA INICIAL ======
def show_config_window():
    def apply_settings():
        global BAD_POSTURE_THRESHOLD
        global MAX_ANGLE_SHOULDER, MAX_ANGLE_NECK
        global IS_CALIBRATED
        
        rigidez = combo_rigidez.get()
        calibracao = combo_calibracao.get()
        
        if rigidez == "Rigoroso":
            BAD_POSTURE_THRESHOLD = 0.60
            MAX_ANGLE_SHOULDER = 12.0
            MAX_ANGLE_NECK = 15.0
        elif rigidez == "Relaxado":
            BAD_POSTURE_THRESHOLD = 0.30
            MAX_ANGLE_SHOULDER = 28.0
            MAX_ANGLE_NECK = 35.0
        else: # Normal
            BAD_POSTURE_THRESHOLD = 0.45
            MAX_ANGLE_SHOULDER = 20.0
            MAX_ANGLE_NECK = 24.0

        if calibracao == "Usar Padrão do Sistema":
            IS_CALIBRATED = True
        else: # Calibrar Manualmente
            IS_CALIBRATED = False

        root.destroy()

    def show_tutorial():
        tutorial_text = (
            "Tutorial de Ambientação - Upright\n\n"
            "Para o melhor funcionamento do sistema, siga estas dicas:\n\n"
            "1. Distância da Tela: Mantenha-se a cerca de 50 a 70 cm da sua webcam.\n"
            "2. Posição da Câmera: A câmera deve estar na altura dos seus olhos ou levemente acima.\n"
            "3. Enquadramento: Certifique-se de que seus ombros e rosto estejam claramente visíveis na câmera.\n"
            "4. Iluminação: Evite luz forte diretamente atrás de você (contra-luz) para não escurecer seu rosto.\n"
            "5. Postura: Sente-se confortavelmente, com os pés no chão e as costas bem apoiadas."
        )
        messagebox.showinfo("Tutorial de Ambientação", tutorial_text)

    root = tk.Tk()
    root.title("Configurações Iniciais - Upright GPU")
    
    window_width = 380
    window_height = 200
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width / 2)
    center_y = int(screen_height/2 - window_height / 2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    frame = ttk.Frame(root, padding="20")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    ttk.Label(frame, text="Rigidez da Avaliação:").grid(column=0, row=0, sticky=tk.W, pady=5)
    combo_rigidez = ttk.Combobox(frame, values=["Relaxado", "Normal", "Rigoroso"], state="readonly")
    combo_rigidez.set("Normal")
    combo_rigidez.grid(column=1, row=0, sticky=tk.W, pady=5)

    ttk.Label(frame, text="Calibração Inicial:").grid(column=0, row=1, sticky=tk.W, pady=5)
    combo_calibracao = ttk.Combobox(frame, values=["Calibrar Manualmente", "Usar Padrão do Sistema"], state="readonly")
    combo_calibracao.set("Calibrar Manualmente")
    combo_calibracao.grid(column=1, row=1, sticky=tk.W, pady=5)

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(column=0, row=3, columnspan=2, pady=20)
    
    btn_tutorial = ttk.Button(btn_frame, text="Tutorial de Ambientação", command=show_tutorial)
    btn_tutorial.grid(column=0, row=0, padx=5)

    btn_start = ttk.Button(btn_frame, text="Iniciar Câmera", command=apply_settings)
    btn_start.grid(column=1, row=0, padx=5)
    
    for child in frame.winfo_children(): 
        child.grid_configure(padx=5)
        
    root.mainloop()

# ====== MAIN ======
show_config_window()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cv2.namedWindow("Upright Mediapipe GPU", cv2.WINDOW_NORMAL)

# Setup MediaPipe Tasks para GPU
model_dir = os.path.join(os.path.dirname(__file__), 'models')
pose_model_path = os.path.join(model_dir, 'pose_landmarker_full.task')
seg_model_path = os.path.join(model_dir, 'selfie_segmenter.tflite')

if not os.path.exists(pose_model_path) or not os.path.exists(seg_model_path):
    print("Modelos nao encontrados! Rode o script scripts/download_mp_tasks.sh primeiro.")
    exit(1)

base_options_pose = python.BaseOptions(
    model_asset_path=pose_model_path,
    delegate=python.BaseOptions.Delegate.GPU)

options_pose = vision.PoseLandmarkerOptions(
    base_options=base_options_pose,
    running_mode=vision.RunningMode.VIDEO,
    output_segmentation_masks=False)

base_options_seg = python.BaseOptions(
    model_asset_path=seg_model_path,
    delegate=python.BaseOptions.Delegate.GPU)

options_seg = vision.ImageSegmenterOptions(
    base_options=base_options_seg,
    running_mode=vision.RunningMode.VIDEO,
    output_confidence_masks=True,
    output_category_mask=False)

with vision.PoseLandmarker.create_from_options(options_pose) as pose, \
     vision.ImageSegmenter.create_from_options(options_seg) as segmenter:
    
    start_time_ns = time.time_ns()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        fh, fw = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        timestamp_ms = (time.time_ns() - start_time_ns) // 1_000_000
        
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        pose_res = pose.detect_for_video(mp_image, timestamp_ms)
        seg_res = segmenter.segment_for_video(mp_image, timestamp_ms)

        posture = {}
        current_raw_angle = None
        current_raw_ratio = None

        if pose_res.pose_landmarks and len(pose_res.pose_landmarks) > 0:
            lm = pose_res.pose_landmarks[0]

            def valid(i):
                return hasattr(lm[i], 'visibility') and lm[i].visibility > VISIBILITY_THRESHOLD

            l_sh = r_sh = None

            if valid(11) and valid(12):
                l_sh = get_pixel(lm[11], fw, fh)
                r_sh = get_pixel(lm[12], fw, fh)
                
                angle_raw = angle_horizontal(l_sh, r_sh)
                angle = min(abs(angle_raw), abs(180 - abs(angle_raw)))
                current_raw_angle = angle
                
                if IS_CALIBRATED:
                    adjusted_angle = abs(angle - BASE_ANGLE_SHOULDER)
                else:
                    adjusted_angle = angle
                    
                score = ema('shoulder', angle_to_score(adjusted_angle, max_angle=MAX_ANGLE_SHOULDER))
                posture['shoulder'] = (l_sh, r_sh, score, f"{angle:.1f}°")

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
                score_lat = ema('neck_lat', angle_to_score(angle_lat, max_angle=MAX_ANGLE_NECK))

                score_fwd = score_lat
                if l_sh and r_sh:
                    sw = math.hypot(l_sh[0] - r_sh[0], l_sh[1] - r_sh[1])
                    if sw > 1e-6:
                        raw_ratio = math.hypot(nose[0] - neck[0], nose[1] - neck[1]) / sw
                        current_raw_ratio = raw_ratio
                        ratio = ema('neck_fwd_ratio', raw_ratio)
                        
                        score_fwd = ema('neck_fwd',
                                        max(0.0, min((ratio - NECK_RATIO_BASE) / 0.40, 1.0)))

                posture['neck'] = (neck, nose, min(score_lat, score_fwd), f"lat:{angle_lat:.1f}°")

        if PRIVACY_MODE and seg_res.confidence_masks is not None:
            mask_idx = 1 if len(seg_res.confidence_masks) > 1 else 0
            seg_mask = (seg_res.confidence_masks[mask_idx].numpy_view() > SEG_THRESHOLD).astype(np.float32)
            frame = apply_privacy_segmentation(frame, seg_mask, PRIVACY_STYLE)

        for key, (p1, p2, score, _) in posture.items():
            color = score_to_color(score)
            cv2.line(frame, p1, p2, color, 4)
            cv2.circle(frame, p1, 7, (255, 255, 255), -1)
            cv2.circle(frame, p2, 7, (255, 255, 255), -1)

        if IS_CALIBRATED:
            global_score = (sum(v[2] for v in posture.values()) / len(posture)) if posture else 1.0
            _posture_history.append(global_score < BAD_POSTURE_THRESHOLD)
            pct_bad = (sum(_posture_history) / len(_posture_history)) if _posture_history else 0.0

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

            if global_score < BAD_POSTURE_THRESHOLD:
                tick = (cv2.getTickCount() // int(cv2.getTickFrequency() * 0.5)) % 2
                if tick == 0:
                    cv2.rectangle(frame, (4, 4), (fw - 4, fh - 4), (0, 0, 220), 3)
                    cv2.putText(frame, "! CORRIJA A POSTURA !", (fw // 2 - 160, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA)
        else:
            cv2.rectangle(frame, (0, fh // 2 - 60), (fw, fh // 2 + 60), (0, 0, 0), -1)
            cv2.putText(frame, "MODO DE CALIBRACAO", (fw // 2 - 200, fh // 2 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(frame, "Sente-se com a postura ideal e pressione [ C ]", (fw // 2 - 280, fh // 2 + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow("Upright Mediapipe GPU", frame)

        key = cv2.waitKey(1)
        if key == 27:
            break
        elif key == ord('c') and not IS_CALIBRATED:
            if current_raw_angle is not None and current_raw_ratio is not None:
                BASE_ANGLE_SHOULDER = current_raw_angle
                NECK_RATIO_BASE = current_raw_ratio
                IS_CALIBRATED = True
                print(f"Calibrado! Shoulder Base: {BASE_ANGLE_SHOULDER:.2f}, Neck Ratio Base: {NECK_RATIO_BASE:.3f}")
        elif key == ord('p'):
            PRIVACY_MODE = not PRIVACY_MODE
        elif key == ord('m'):
            modes = ['silhouette', 'blur', 'mosaic']
            PRIVACY_STYLE = modes[(modes.index(PRIVACY_STYLE) + 1) % len(modes)]

cap.release()
cv2.destroyAllWindows()