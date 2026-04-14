import json
import math
import collections
import torch
import torchvision.transforms as transforms
import cv2
import PIL.Image
from trt_pose.models import resnet18_baseline_att
from trt_pose.coco import coco_category_to_topology
from trt_pose.parse_objects import ParseObjects

# ====== Resolução esperada pelo modelo ======
MODEL_W, MODEL_H = 224, 224

# ====== Keypoints COCO-18 (trt_pose) ======
# 0:nose  1:neck  2:r_shoulder  3:r_elbow  4:r_wrist
# 5:l_shoulder  6:l_elbow  7:l_wrist  8:r_hip  9:r_knee
# 10:r_ankle  11:l_hip  12:l_knee  13:l_ankle  14:r_eye
# 15:l_eye  16:r_ear  17:l_ear
KP = {
    'nose':        0,
    'neck':        1,
    'r_shoulder':  2,
    'r_elbow':     3,
    'l_shoulder':  5,
    'l_elbow':     6,
}

# ====== Limiares do artigo (Tabela 1) — em graus ======
# Cada parâmetro: (Range0_max, Range1_max, Range2_max)  → acima = Range3
THRESHOLDS = {
    'shoulder_alignment': (5,  10, 20),   # desvio horizontal ombros
    'neck_lateral_bend':  (5,  12, 24),   # desvio nariz→pescoço da vertical
    'r_arm_abduction':    (13, 34, 67),   # ombro_dir → cotovelo_dir
    'l_arm_abduction':    (13, 34, 67),   # ombro_esq → cotovelo_esq
}

# Cores por range: 0=verde, 1=amarelo, 2=laranja, 3=vermelho
RANGE_COLORS = [
    (0, 220, 0),
    (0, 220, 220),
    (0, 140, 255),
    (0, 0, 255),
]
RANGE_LABELS = ['Bom', 'Atenção', 'Ruim', 'Critico']

# ====== Suavização temporal (média móvel) ======
SMOOTH_N = 8
_history = collections.defaultdict(lambda: collections.deque(maxlen=SMOOTH_N))

def smooth(key, value):
    _history[key].append(value)
    return sum(_history[key]) / len(_history[key])

# ====== Funções de ângulo ======
def angle_atan2(p1, p2):
    """Ângulo em graus da linha p1→p2 em relação ao eixo horizontal."""
    dy = p2[1] - p1[1]
    dx = p2[0] - p1[0]
    return math.degrees(math.atan2(dy, dx))

def classify_range(value_deg, thresholds):
    """Classifica o valor absoluto em Range 0-3 conforme o artigo."""
    v = abs(value_deg)
    r0, r1, r2 = thresholds
    if v <= r0: return 0
    if v <= r1: return 1
    if v <= r2: return 2
    return 3

# ====== Device ======
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Usando device: {device}")

# ====== Carregar config ======
with open('human_pose.json', 'r') as f:
    human_pose = json.load(f)

topology = coco_category_to_topology(human_pose)
skeleton = [(l[0] - 1, l[1] - 1) for l in human_pose['skeleton']]
num_parts = len(human_pose['keypoints'])
num_links = len(human_pose['skeleton'])

# ====== Modelo ======
model = resnet18_baseline_att(num_parts, 2 * num_links)
model = model.eval().to(device)
MODEL_WEIGHTS = 'resnet18_baseline_att_224x224_A_epoch_249.pth'
model.load_state_dict(torch.load(MODEL_WEIGHTS, map_location=device))
print("Modelo carregado.")

# ====== Parser ======
parse_objects = ParseObjects(topology, cmap_threshold=0.1, link_threshold=0.1)

# ====== Pré-processamento ======
mean = torch.Tensor([0.485, 0.456, 0.406]).to(device)
std  = torch.Tensor([0.229, 0.224, 0.225]).to(device)

def preprocess(image_bgr):
    image_resized = cv2.resize(image_bgr, (MODEL_W, MODEL_H))
    image_rgb = cv2.cvtColor(image_resized, cv2.COLOR_BGR2RGB)
    tensor = transforms.functional.to_tensor(image_rgb).to(device)
    tensor = (tensor - mean[:, None, None]) / std[:, None, None]
    return tensor.unsqueeze(0)

# ====== Extração de keypoints ======
def get_kp(obj, peaks, kp_idx, W, H):
    """Retorna (x_px, y_px) do keypoint ou None se não detectado."""
    k = int(obj[kp_idx])
    if k < 0 or k >= peaks[0][kp_idx].shape[0]:
        return None
    peak = peaks[0][kp_idx][k]
    return (int(peak[1] * W), int(peak[0] * H))

# ====== Análise de postura (artigo — Tabela 3) ======
def angle_between(v1, v2):
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    norm1 = math.hypot(v1[0], v1[1])
    norm2 = math.hypot(v2[0], v2[1])
    if norm1 < 1e-6 or norm2 < 1e-6:
        return None
    cos = max(-1.0, min(1.0, dot / (norm1 * norm2)))
    return math.degrees(math.acos(cos))


def analyze_posture(obj, peaks, W, H):
    results = {}

    nose = get_kp(obj, peaks, KP['nose'], W, H)
    neck = get_kp(obj, peaks, KP['neck'], W, H)
    r_sh = get_kp(obj, peaks, KP['r_shoulder'], W, H)
    l_sh = get_kp(obj, peaks, KP['l_shoulder'], W, H)
    r_el = get_kp(obj, peaks, KP['r_elbow'], W, H)
    l_el = get_kp(obj, peaks, KP['l_elbow'], W, H)

    # =========================
    # REFERENCIAL DO CORPO
    # =========================
    if neck and l_sh and r_sh:
        mid_sh = ((l_sh[0] + r_sh[0]) // 2,
                  (l_sh[1] + r_sh[1]) // 2)

        torso_vec = (mid_sh[0] - neck[0],
                     mid_sh[1] - neck[1])
    else:
        return results

    # =========================
    # 1. OMBROS
    # =========================
    if l_sh and r_sh:
        shoulder_vec = (r_sh[0] - l_sh[0],
                        r_sh[1] - l_sh[1])

        horizontal = (1, 0)

        ang = angle_between(shoulder_vec, horizontal)
        if ang is not None:
            deviation = min(ang, 180 - ang)

            ang_sm = smooth('shoulder_alignment', deviation)
            rng = classify_range(ang_sm, THRESHOLDS['shoulder_alignment'])

            results['shoulder_alignment'] = {
                'angle': ang_sm, 'range': rng,
                'color': RANGE_COLORS[rng],
                'p1': l_sh, 'p2': r_sh
            }

    # =========================
    # 2. PESCOÇO (FIX REAL)
    # =========================
    if neck and nose:
        head_vec = (nose[0] - neck[0],
                    nose[1] - neck[1])

        ang = angle_between(head_vec, torso_vec)

        if ang is not None:
            deviation = ang  # 0° = alinhado com tronco

            ang_sm = smooth('neck_lateral_bend', deviation)
            rng = classify_range(ang_sm, THRESHOLDS['neck_lateral_bend'])

            results['neck_lateral_bend'] = {
                'angle': ang_sm, 'range': rng,
                'color': RANGE_COLORS[rng],
                'p1': neck, 'p2': nose
            }

    # =========================
    # 3. BRAÇOS (FIX REAL)
    # =========================
    for side, sh, el in [('r', r_sh, r_el), ('l', l_sh, l_el)]:
        if sh and el:
            arm_vec = (el[0] - sh[0],
                       el[1] - sh[1])

            ang = angle_between(arm_vec, torso_vec)

            if ang is not None:
                deviation = ang

                dev_sm = smooth(f'{side}_arm_abduction', deviation)
                rng = classify_range(dev_sm, THRESHOLDS[f'{side}_arm_abduction'])

                results[f'{side}_arm_abduction'] = {
                    'angle': dev_sm, 'range': rng,
                    'color': RANGE_COLORS[rng],
                    'p1': sh, 'p2': el
                }

    return results
# ====== Desenho do esqueleto ======
def draw_skeleton(frame, counts, objects, peaks):
    H, W = frame.shape[:2]
    for person_idx in range(int(counts[0])):
        obj = objects[0][person_idx]
        for part_idx in range(num_parts):
            kp_idx = int(obj[part_idx])
            if kp_idx < 0 or kp_idx >= peaks[0][part_idx].shape[0]:
                continue
            peak = peaks[0][part_idx][kp_idx]
            x = int(peak[1] * W)
            y = int(peak[0] * H)
            cv2.circle(frame, (x, y), 4, (200, 200, 200), -1)
        for j1, j2 in skeleton:
            if j1 >= num_parts or j2 >= num_parts:
                continue
            k1, k2 = int(obj[j1]), int(obj[j2])
            if k1 < 0 or k2 < 0:
                continue
            if k1 >= peaks[0][j1].shape[0] or k2 >= peaks[0][j2].shape[0]:
                continue
            p1 = peaks[0][j1][k1]
            p2 = peaks[0][j2][k2]
            cv2.line(frame,
                     (int(p1[1]*W), int(p1[0]*H)),
                     (int(p2[1]*W), int(p2[0]*H)),
                     (180, 180, 180), 1)

# ====== Desenho dos parâmetros posturais ======
# ====== Desenho dos parâmetros posturais (VERSÃO DEBUG) ======
def draw_posture(frame, posture):
    H, W = frame.shape[:2]

    PARAM_NAMES = {
        'shoulder_alignment': 'Ombros',
        'neck_lateral_bend':  'Cervical',
        'r_arm_abduction':    'Braco Dir',
        'l_arm_abduction':    'Braco Esq',
    }

    # Debug no console para verificar estabilidade dos pontos
    print("-" * 30)
    for key, data in posture.items():
        p1, p2 = data['p1'], data['p2']
        color = data['color']
        ang = data['angle']
        
        # Log de coordenadas para ver se os pontos não estão "pulando"
        print(f"DEBUG [{key}]: P1={p1}, P2={p2} | Angulo Calculado: {ang:.2f}°")

        # Desenho visual no frame
        cv2.line(frame, p1, p2, color, 3)
        cv2.circle(frame, p1, 6, (255, 255, 255), -1) # Ponto branco para contraste
        cv2.circle(frame, p2, 6, (255, 255, 255), -1)

    # Painel HUD lateral
    panel_x = W - 320 # Aumentado para caber mais texto
    panel_y = 20
    cv2.rectangle(frame, (panel_x - 10, panel_y - 15),
                  (W - 5, panel_y + len(posture) * 40 + 10),
                  (20, 20, 20), -1)

    for i, (key, data) in enumerate(posture.items()):
        color = data['color']
        rng   = data['range']
        ang   = data['angle']
        name  = PARAM_NAMES.get(key, key)
        y_pos = panel_y + i * 40

        # Barra de range
        bar_full = 100
        bar_w = int(bar_full * (rng + 1) / 4)
        cv2.rectangle(frame, (panel_x + 180, y_pos + 4),
                      (panel_x + 180 + bar_full, y_pos + 18), (60, 60, 60), -1)
        cv2.rectangle(frame, (panel_x + 180, y_pos + 4),
                      (panel_x + 180 + bar_w, y_pos + 18), color, -1)

        # TEXTO DE DEBUG: Nome, Range e o Ângulo exato
        # Se 'Cervical' estiver longe de 0.0, sua câmera ou cabeça estão inclinadas lateralmente
        label = f"{name}: R{rng} | {ang:+.1f} deg"
        cv2.putText(frame, label, (panel_x, y_pos + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # Indicador de Status Geral
    if posture:
        worst = max(posture.values(), key=lambda d: d['range'])
        wr = worst['range']
        wc = RANGE_COLORS[wr]
        cv2.putText(frame, f"STATUS: {RANGE_LABELS[wr].upper()}",
                    (20, H - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.2, wc, 3, cv2.LINE_AA)

# ====== Webcam ======
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Não foi possível abrir a webcam.")

cv2.namedWindow('AxisMonitor - trt_pose', cv2.WINDOW_NORMAL)
cv2.setWindowProperty('AxisMonitor - trt_pose', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

print("Pressione ESC para sair | F para alternar tela cheia.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    H, W = frame.shape[:2]
    data = preprocess(frame)

    with torch.no_grad():
        cmap, paf = model(data)

    cmap_cpu = cmap.detach().cpu()
    paf_cpu  = paf.detach().cpu()
    counts, objects, peaks = parse_objects(cmap_cpu, paf_cpu)

    draw_skeleton(frame, counts, objects, peaks)

    # Analisa e desenha postura apenas da primeira pessoa detectada
    if int(counts[0]) > 0:
        posture = analyze_posture(objects[0][0], peaks, W, H)
        if posture:
            draw_posture(frame, posture)
    else:
        cv2.putText(frame, "Nenhuma pessoa detectada", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    cv2.imshow('AxisMonitor - trt_pose', frame)
    key = cv2.waitKey(1)
    if key == 27:
        break
    if key == ord('f'):
        prop = cv2.getWindowProperty('AxisMonitor - trt_pose', cv2.WND_PROP_FULLSCREEN)
        new = cv2.WINDOW_NORMAL if prop == cv2.WINDOW_FULLSCREEN else cv2.WINDOW_FULLSCREEN
        cv2.setWindowProperty('AxisMonitor - trt_pose', cv2.WND_PROP_FULLSCREEN, new)

cap.release()
cv2.destroyAllWindows()
