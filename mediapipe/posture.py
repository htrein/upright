import math
import cv2
import config

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

def get_pixel(lm, w, h):
    return int(lm.x * w), int(lm.y * h)

# ====== CÁLCULO PRINCIPAL ======
def evaluate_posture(lm, fw, fh):
    posture = {}
    extra_drawings = []
    current_raw_angle = None
    current_raw_ratio = None
    current_raw_roll = None

    def valid(i):
        v = getattr(lm[i], 'visibility', None)
        if v is None:
            return True
        return v > config.VISIBILITY_THRESHOLD

    l_sh = r_sh = None

    # ====== OMBROS ======
    if valid(11) and valid(12):
        l_sh = get_pixel(lm[11], fw, fh)
        r_sh = get_pixel(lm[12], fw, fh)
        
        angle_raw = angle_horizontal(l_sh, r_sh)
        angle = min(abs(angle_raw), abs(180 - abs(angle_raw)))
        current_raw_angle = angle
        
        if config.IS_CALIBRATED:
            adjusted_angle = abs(angle - config.BASE_ANGLE_SHOULDER)
        else:
            adjusted_angle = angle
            
        score = config.get_ema('shoulder', angle_to_score(adjusted_angle, max_angle=config.MAX_ANGLE_SHOULDER))
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
        score_lat = config.get_ema('neck_lat', angle_to_score(angle_lat, max_angle=config.MAX_ANGLE_NECK))

        score_fwd = score_lat
        ratio = 0
        if l_sh and r_sh:
            sw = math.hypot(l_sh[0] - r_sh[0], l_sh[1] - r_sh[1]) 
            if sw > 1e-6:
                raw_ratio = math.hypot(nose[0] - neck[0], nose[1] - neck[1]) / sw
                current_raw_ratio = raw_ratio
                ratio = config.get_ema('neck_fwd_ratio', raw_ratio)
                score_fwd = config.get_ema('neck_fwd',
                                           max(0.0, min((ratio - config.NECK_RATIO_BASE) / 0.40, 1.0)))

        posture['neck'] = (neck, nose, min(score_lat, score_fwd), {'score_lat': score_lat, 'score_fwd': score_fwd, 'ratio': ratio})

    # ====== CABEÇA (Inclinação Lateral) ======
    if valid(2) and valid(5) and valid(7) and valid(8) and valid(9) and valid(10):
        l_eye = get_pixel(lm[2], fw, fh)
        r_eye = get_pixel(lm[5], fw, fh)
        l_ear = get_pixel(lm[7], fw, fh)
        r_ear = get_pixel(lm[8], fw, fh)
        l_mouth = get_pixel(lm[9], fw, fh)
        r_mouth = get_pixel(lm[10], fw, fh)
        
        angle_eye_raw = angle_horizontal(l_eye, r_eye)
        angle_ear_raw = angle_horizontal(l_ear, r_ear)
        angle_mouth_raw = angle_horizontal(l_mouth, r_mouth)
        
        angle_eye = min(abs(angle_eye_raw), abs(180 - abs(angle_eye_raw)))
        angle_ear = min(abs(angle_ear_raw), abs(180 - abs(angle_ear_raw)))
        angle_mouth = min(abs(angle_mouth_raw), abs(180 - abs(angle_mouth_raw)))
        
        avg_angle = (angle_eye + angle_ear + angle_mouth) / 3.0
        current_raw_roll = avg_angle
        
        if config.IS_CALIBRATED:
            adjusted_roll = abs(avg_angle - config.BASE_HEAD_ROLL)
        else:
            adjusted_roll = avg_angle
            
        score_head = config.get_ema('head_roll', angle_to_score(adjusted_roll, max_angle=config.MAX_HEAD_ROLL_ANGLE))
        
        posture['head'] = (l_eye, r_eye, score_head, f"{avg_angle:.1f}°")

        head_color = score_to_color(score_head)
        extra_drawings.extend([
            ('line', l_mouth, r_mouth, head_color, 4),
            ('circle', l_mouth, 7, (255, 255, 255), -1),
            ('circle', r_mouth, 7, (255, 255, 255), -1),
            ('line', l_ear, r_ear, head_color, 4),
            ('circle', l_ear, 7, (255, 255, 255), -1),
            ('circle', r_ear, 7, (255, 255, 255), -1)
        ])

    return posture, extra_drawings, current_raw_angle, current_raw_ratio, current_raw_roll


def draw_posture_lines(frame, posture, extra_drawings):
    for key, (p1, p2, score, _) in posture.items():
        color = score_to_color(score)
        cv2.line(frame, p1, p2, color, 4)
        cv2.circle(frame, p1, 7, (255, 255, 255), -1)
        cv2.circle(frame, p2, 7, (255, 255, 255), -1)
        
        if score < 0.8 and key in ['shoulder', 'head']:
            offset = 15
            arrow_len = 25
            arrow_color = (255, 0, 150) 
            
            if p1[1] > p2[1]:
                cv2.arrowedLine(frame, (p1[0], p1[1] - offset), (p1[0], p1[1] - offset - arrow_len), arrow_color, 4, tipLength=0.4)
                cv2.arrowedLine(frame, (p2[0], p2[1] + offset), (p2[0], p2[1] + offset + arrow_len), arrow_color, 4, tipLength=0.4)
            else:
                cv2.arrowedLine(frame, (p2[0], p2[1] - offset), (p2[0], p2[1] - offset - arrow_len), arrow_color, 4, tipLength=0.4)
                cv2.arrowedLine(frame, (p1[0], p1[1] + offset), (p1[0], p1[1] + offset + arrow_len), arrow_color, 4, tipLength=0.4)
                
        elif score < 0.8 and key == 'neck':
            arrow_len = 30
            arrow_color = (255, 0, 150)
            mid_x = int((p1[0] + p2[0]) / 2)
            mid_y = int((p1[1] + p2[1]) / 2)
            
            info_dict = posture['neck'][3]
            score_lat = info_dict['score_lat']
            score_fwd = info_dict['score_fwd']
            ratio = info_dict['ratio']
            
            dx = dy = 0
            
            if score_lat < 0.8:
                if p2[0] < p1[0]:
                    dx = arrow_len // 2 
                else:
                    dx = -arrow_len // 2 
                    
            if score_fwd < 0.8 and config.IS_CALIBRATED:
                if ratio < config.NECK_RATIO_BASE:
                    dy = arrow_len // 2 
                else:
                    dy = -arrow_len // 2
                    
            if dx != 0:
                cv2.arrowedLine(frame, (mid_x - dx, mid_y), (mid_x + dx, mid_y), arrow_color, 4, tipLength=0.4)
                
            if dy != 0:
                cv2.arrowedLine(frame, (mid_x, mid_y - dy), (mid_x, mid_y + dy), arrow_color, 4, tipLength=0.4)
        
    for shape, *args in extra_drawings:
        if shape == 'line':
            cv2.line(frame, *args)
        elif shape == 'circle':
            cv2.circle(frame, *args)
