import cv2
import mediapipe as mp
import math
import collections
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# ====== CONFIG ======
VISIBILITY_THRESHOLD = 0.5
SMOOTH_N = 8

_history = collections.defaultdict(lambda: collections.deque(maxlen=SMOOTH_N))
def smooth(key, value):
    _history[key].append(value)
    return sum(_history[key]) / len(_history[key])
    
# ====== ANGULOS ======
def angle_horizontal(p1, p2):
    dx = p2[0] - p1[0]
    dy = p1[1] - p2[1]
    return math.degrees(math.atan2(dy, dx))
    
def deviation_from_horizontal(p1, p2):
    return abs(angle_horizontal(p1, p2))
    
def deviation_from_vertical(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return abs(math.degrees(math.atan2(dx, dy)))
    
# ====== CLASSIFICAÇÃO ======
# customizável
THRESHOLDS = {
    'shoulder': (5, 10, 20),
    'neck': (5, 12, 24),
    'arm': (13, 34, 67),
}

COLORS = [(0,220,0),(0,220,220),(0,140,255),(0,0,255)]

def classify(v, t):
    if v <= t[0]: return 0
    if v <= t[1]: return 1
    if v <= t[2]: return 2
    return 3
    
# ====== UTILS ======
def get_pixel(lm, w, h):
    return int(lm.x * w), int(lm.y * h)
    
# ====== WEBCAM ======
cap = cv2.VideoCapture(0)
cv2.namedWindow("Upright Mediapipe", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("Upright Mediapipe", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
with mp_pose.Pose(
    model_complexity=1,
    smooth_landmarks=True
) as pose:
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)
        posture = {}
        if res.pose_landmarks:
            lm = res.pose_landmarks.landmark
            def valid(i):
                return lm[i].visibility > VISIBILITY_THRESHOLD
                
            # ====== PONTOS ======
            if valid(11) and valid(12):
                l_sh = get_pixel(lm[11], w, h)
                r_sh = get_pixel(lm[12], w, h)
                angle_raw = angle_horizontal(l_sh, r_sh)
                angle = min(abs(angle_raw), abs(180 - abs(angle_raw)))
                r = classify(angle, THRESHOLDS['shoulder'])
                posture['shoulder'] = (l_sh, r_sh, angle, r)
            if valid(0) and valid(11) and valid(12):
                nose = get_pixel(lm[0], w, h)
                neck = (
                    int((lm[11].x + lm[12].x)/2 * w),
                    int((lm[11].y + lm[12].y)/2 * h)
                )
                
                # --- curvatura lateral ---
                dx = nose[0] - neck[0]
                dy = nose[1] - neck[1]
                angle_raw = math.degrees(math.atan2(dx, -dy))
                angle = min(abs(angle_raw), abs(180 - abs(angle_raw)))
                r = classify(angle, THRESHOLDS['neck'])
                posture['neck'] = (neck, nose, angle, r)
                
                # --- curvatura frontal ---
                dist_nose = math.hypot(nose[0] - neck[0], nose[1] - neck[1])
                shoulder_width = math.hypot(l_sh[0] - r_sh[0], l_sh[1] - r_sh[1])
                if shoulder_width > 1e-6:
                    ratio = dist_nose / shoulder_width
                    ratio = smooth('neck_forward', ratio)
                    NECK_FWD_T = (0.6, 0.4, 0.3) # customizável
                    if ratio >= NECK_FWD_T[0]: rf = 0
                    elif ratio >= NECK_FWD_T[1]: rf = 1
                    elif ratio >= NECK_FWD_T[2]: rf = 2
                    else: rf = 3
                    posture['neck_fwd'] = (neck, nose, ratio, rf)
            for side, sh_i, el_i in [('r',12,14),('l',11,13)]:
                if valid(sh_i) and valid(el_i):
                    sh = get_pixel(lm[sh_i], w, h)
                    el = get_pixel(lm[el_i], w, h)
                    dx = el[0] - sh[0]
                    dy = el[1] - sh[1]
                    angle = abs(math.degrees(math.atan2(abs(dx), abs(dy))))
                    angle = smooth(f'arm_{side}', angle)
                    r = classify(angle, THRESHOLDS['arm'])
                    posture[f'arm_{side}'] = (sh, el, angle, r)
                    
            # ====== ESQUELETO ======
            mp_drawing.draw_landmarks(frame, res.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            
            # ====== DESENHO ======
            print("-"*30)
            for key, (p1, p2, ang, r) in posture.items():
                print(f"{key}: {ang:.2f}")
                if key == 'neck_fwd':
                    continue  # aresta controlada junto com 'neck' abaixo
                color = COLORS[r]
                # se for a aresta do pescoço, combina com neck_fwd
                if key == 'neck' and 'neck_fwd' in posture:
                # como só tem uma aresta para medir angulo lateral e frontal do pescoço, usa a cor da que está mais errada
                    worst_r = max(r, posture['neck_fwd'][3])
                    color = COLORS[worst_r]
                cv2.line(frame, p1, p2, color, 3)
                cv2.circle(frame, p1, 6, (255,255,255), -1)
                cv2.circle(frame, p2, 6, (255,255,255), -1)
                
        # ====== HUD ======
        x0 = w - 300
        y0 = 20
        cv2.rectangle(frame, (x0-10,y0-10),(w-10,y0+180),(20,20,20),-1)
        for i,(key,(p1,p2,ang,r)) in enumerate(posture.items()):
            if key == 'neck_fwd':
                text = f"{key}: {ang:.2f} ratio"
            else:
                text = f"{key}: {ang:.1f} deg"
            cv2.putText(frame,text,(x0,y0+30*i),
                        cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),1)
        cv2.imshow("Upright Mediapipe", frame)
        if cv2.waitKey(1) == 27:
            break
cap.release()
cv2.destroyAllWindows()
