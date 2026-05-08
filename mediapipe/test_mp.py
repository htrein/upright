import cv2
import mediapipe as mp
import math
import collections
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox

mp_pose = mp.solutions.pose
mp_selfie = mp.solutions.selfie_segmentation

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
# Aplica um filtro aos valores dos ângulos para evitar tremulações abruptas das métricas na tela.
def ema(key, value, alpha=EMA_ALPHA):
    prev = _ema_state.get(key, value)
    new = alpha * value + (1 - alpha) * prev
    _ema_state[key] = new
    return new

# ====== SCORE CONTÍNUO 0..1 ======
# Converte o ângulo (desvio da postura ideal) em uma pontuação de 0.0 (péssimo) a 1.0 (perfeito).
# Quanto mais distante do zero ou do ângulo calibrado, menor a pontuação.
def angle_to_score(angle_deg, max_angle=45.0):
    x = max(0.0, min(angle_deg / max_angle, 1.0))
    return 1.0 - x

# ====== COR INTERPOLADA verde→amarelo→vermelho (BGR) ======
# Transforma uma pontuação de 0.0 a 1.0 em uma cor para feedback visual na tela.
# 1.0 = Verde, 0.5 = Amarelo, 0.0 = Vermelho.
def score_to_color(score):
    score = max(0.0, min(1.0, score))
    if score >= 0.5:
        # De amarelo (0.5) para verde (1.0)
        t = (score - 0.5) * 2.0
        r = int((1 - t) * 255)
        g = 220
        b = 0
    else:
        # De vermelho (0.0) para amarelo (0.5)
        t = score * 2.0
        r = 255
        g = int(t * 200)
        b = 0
    return (b, g, r)

# ====== ÂNGULOS ======
# Calcula o ângulo em graus entre dois pontos em relação à linha horizontal da imagem.
# Usado para saber se os ombros estão desnivelados.
def angle_horizontal(p1, p2):
    dx = p2[0] - p1[0]
    dy = p1[1] - p2[1] # Eixo Y cresce para baixo na imagem, por isso a inversão
    return math.degrees(math.atan2(dy, dx))

# ====== UTILS ======
# Converte as coordenadas normalizadas retornadas pelo MediaPipe (de 0 a 1) para pixels reais da imagem.
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

# ====== TELA INICIAL ======
def show_config_window():
    def apply_settings():
        global BAD_POSTURE_THRESHOLD
        global MAX_ANGLE_SHOULDER, MAX_ANGLE_NECK
        global IS_CALIBRATED
        
        rigidez = combo_rigidez.get()
        calibracao = combo_calibracao.get()
        
        # Ajustes de Rigidez
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

        # Ajuste de Calibração
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
    root.title("Configurações Iniciais - Upright")
    
    # Centralizar a janela
    window_width = 380
    window_height = 200
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width / 2)
    center_y = int(screen_height/2 - window_height / 2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    frame = ttk.Frame(root, padding="20")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Rigidez
    ttk.Label(frame, text="Rigidez da Avaliação:").grid(column=0, row=0, sticky=tk.W, pady=5)
    combo_rigidez = ttk.Combobox(frame, values=["Relaxado", "Normal", "Rigoroso"], state="readonly")
    combo_rigidez.set("Normal")
    combo_rigidez.grid(column=1, row=0, sticky=tk.W, pady=5)

    # Calibração
    ttk.Label(frame, text="Calibração Inicial:").grid(column=0, row=1, sticky=tk.W, pady=5)
    combo_calibracao = ttk.Combobox(frame, values=["Calibrar Manualmente", "Usar Padrão do Sistema"], state="readonly")
    combo_calibracao.set("Calibrar Manualmente")
    combo_calibracao.grid(column=1, row=1, sticky=tk.W, pady=5)

    # Botões
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(column=0, row=3, columnspan=2, pady=20)
    
    btn_tutorial = ttk.Button(btn_frame, text="Tutorial de Ambientação", command=show_tutorial)
    btn_tutorial.grid(column=0, row=0, padx=5)

    btn_start = ttk.Button(btn_frame, text="Iniciar Câmera", command=apply_settings)
    btn_start.grid(column=1, row=0, padx=5)
    
    # Ajuste de layout
    for child in frame.winfo_children(): 
        child.grid_configure(padx=5)
        
    root.mainloop()

# ====== MAIN ======
show_config_window()

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
        current_raw_angle = None
        current_raw_ratio = None

        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark

            # Função auxiliar: verifica se a parte do corpo tem a confiança mínima exigida para cálculo
            def valid(i):
                return lm[i].visibility > VISIBILITY_THRESHOLD

            l_sh = r_sh = None

            # ====== OMBROS ======
            # Landmarks MediaPipe: 11 = Ombro esquerdo, 12 = Ombro direito
            if valid(11) and valid(12):
                l_sh = get_pixel(lm[11], fw, fh)
                r_sh = get_pixel(lm[12], fw, fh)
                
                # Desnível dos ombros em relação à horizontal
                angle_raw = angle_horizontal(l_sh, r_sh)
                # Mantém sempre como ângulo agudo (em módulo)
                angle = min(abs(angle_raw), abs(180 - abs(angle_raw)))
                current_raw_angle = angle
                
                # Subtrai o valor base caso o sistema esteja operando em modo calibrado
                if IS_CALIBRATED:
                    adjusted_angle = abs(angle - BASE_ANGLE_SHOULDER)
                else:
                    adjusted_angle = angle
                    
                # Converte o ângulo numa pontuação de 0 a 1 e aplica o filtro de suavização (EMA)
                score = ema('shoulder', angle_to_score(adjusted_angle, max_angle=MAX_ANGLE_SHOULDER))
                posture['shoulder'] = (l_sh, r_sh, score, f"{angle:.1f}°")

            # ====== PESCOÇO ======
            # Landmarks: 0 = Nariz, 11 = Ombro Esq., 12 = Ombro Dir.
            if valid(0) and valid(11) and valid(12):
                nose = get_pixel(lm[0], fw, fh)
                # O pescoço é estimado como o ponto médio entre os dois ombros
                neck = (
                    int((lm[11].x + lm[12].x) / 2 * fw),
                    int((lm[11].y + lm[12].y) / 2 * fh)
                )
                
                # Desvio Lateral: ângulo entre o nariz e a base do pescoço em relação à vertical
                dx = nose[0] - neck[0]
                dy = nose[1] - neck[1]
                angle_lat = min(abs(math.degrees(math.atan2(dx, -dy))),
                                abs(180 - abs(math.degrees(math.atan2(dx, -dy)))))
                score_lat = ema('neck_lat', angle_to_score(angle_lat, max_angle=MAX_ANGLE_NECK))

                # Desvio Frontal: O usuário está projetando o pescoço para perto da tela?
                score_fwd = score_lat
                if l_sh and r_sh:
                    sw = math.hypot(l_sh[0] - r_sh[0], l_sh[1] - r_sh[1]) # Largura dos ombros como referência
                    if sw > 1e-6:
                        # Se o pescoço estiver muito projetado para a frente, o nariz e os ombros
                        # ficam mais alinhados horizontalmente (encolhe a proporção pescoço/ombro)
                        raw_ratio = math.hypot(nose[0] - neck[0], nose[1] - neck[1]) / sw
                        current_raw_ratio = raw_ratio
                        ratio = ema('neck_fwd_ratio', raw_ratio)
                        
                        # Calcula a pontuação baseando-se no distanciamento da proporção calibrada
                        score_fwd = ema('neck_fwd',
                                        max(0.0, min((ratio - NECK_RATIO_BASE) / 0.40, 1.0)))

                # O score final do pescoço é o pior caso entre a inclinação lateral e frontal
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

        # ====== MÉTRICA GLOBAL & HUD ======
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

            # Aviso piscante
            if global_score < BAD_POSTURE_THRESHOLD:
                tick = (cv2.getTickCount() // int(cv2.getTickFrequency() * 0.5)) % 2
                if tick == 0:
                    cv2.rectangle(frame, (4, 4), (fw - 4, fh - 4), (0, 0, 220), 3)
                    cv2.putText(frame, "! CORRIJA A POSTURA !", (fw // 2 - 160, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA)
        else:
            # Modo calibração visual
            cv2.rectangle(frame, (0, fh // 2 - 60), (fw, fh // 2 + 60), (0, 0, 0), -1)
            cv2.putText(frame, "MODO DE CALIBRACAO", (fw // 2 - 200, fh // 2 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(frame, "Sente-se com a postura ideal e pressione [ C ]", (fw // 2 - 280, fh // 2 + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow("Upright Mediapipe", frame)

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