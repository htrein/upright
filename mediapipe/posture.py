import math
import cv2
import config

def angle_to_score(angle_deg, max_angle=45.0):
    x = max(0.0, min(angle_deg / max_angle, 1.0))
    return 1.0 - x

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

# Método de Extração 2D (Fotogrametria)
# Referência: Projeto SAPO (Ferreira et al., 2010).
# Valida cientificamente a extração de ângulos posturais a partir do alinhamento
# de pontos anatômicos bidimensionais usando trigonometria no plano frontal.
def angle_horizontal(p1, p2):
    dx = p2[0] - p1[0]
    dy = p1[1] - p2[1]
    return math.degrees(math.atan2(dy, dx))

def norm_angle(a):
    a = a % 180
    if a > 90:
        a -= 180
    return a

def get_pixel(lm, w, h):
    return int(lm.x * w), int(lm.y * h)

# Cálculo principal do sistema de postura
# Referência de Rastreamento: Albert et al. (2020) - Avaliação de desempenho de
# rastreamento de pose do Azure Kinect e Kinect v2 para análise de marcha em
# comparação com padrão ouro (Vicon). Valida sistemas markerless de captura de
# movimento para análise biomecânica. Sensors, 20(18), 5104.
# Nota: A validação específica de MediaPipe para avaliação ergonômica é suportada
# por literatura independente (e.g., Ota et al., 2020; Stenum et al., 2021).
def evaluate_posture(lm, fw, fh):
    dicionario_postura = {}
    desenhos_extras = []
    angulo_ombro_cru = None
    angulo_ratio_cru = None
    angulo_cabeca_cru = None
    angulo_pescoco_cru = None

    def valid(i):
        v = getattr(lm[i], 'visibility', None)
        if v is None:
            return True
        return v > config.VISIBILITY_THRESHOLD

    l_sh = r_sh = None

    # Ombros (Assimetria Horizontal)
    # Referência Biomecânica: O cálculo da assimetria de ombros no plano frontal é
    # embasado na fotogrametria clássica (Ferreira et al., 2010), onde a extração
    # bidimensional do ângulo absoluto entre os acrômios indica o desvio postural
    # da cintura escapular.
    # Limiares de Alerta (Adaptação heurística inspirada em diretrizes de assimetria,
    # como SOSORT):
    #   <= 2°    : Normal (Tolerância anatômica)
    #   2° a 10° : Atenção (Assimetria tônica ou fadiga postural)
    #   > 10°    : Perigo (Indicador clínico que exige investigação para desvios
    #              estruturais como escoliose).
    if valid(11) and valid(12):
        l_sh = get_pixel(lm[11], fw, fh)
        r_sh = get_pixel(lm[12], fw, fh)
        
        angulo_cru = angle_horizontal(l_sh, r_sh)
        angulo = norm_angle(angulo_cru)
        angulo_ombro_cru = angulo
        
        if config.IS_CALIBRATED:
            angulo_ajustado = abs(angulo - config.BASE_ANGLE_SHOULDER)
        else:
            angulo_ajustado = angulo
            
        nota_ombro = config.get_ema('shoulder', angle_to_score(angulo_ajustado, max_angle=config.MAX_ANGLE_SHOULDER))
        dicionario_postura['shoulder'] = (l_sh, r_sh, nota_ombro, f"{angulo:.1f}°")

    # Pescoço (Desvio Lateral)
    # Referência Ergonômica: Inspirado no método RULA (McAtamney & Corlett, 1993)
    # e ISO 11226:2000. O RULA penaliza (+1 score) qualquer flexão lateral do
    # pescoço, enquanto a ISO 11226 estabelece limite estrito de 10° para
    # inclinação estática.
    # Limiar do Código (config.MAX_ANGLE_NECK): Adota-se 15° como limiar heurístico
    # de software para equilibrar a tolerância prática com a fadiga de alertas.
    if valid(0) and valid(11) and valid(12):
        nose = get_pixel(lm[0], fw, fh)
        neck = (
            int((lm[11].x + lm[12].x) / 2 * fw),
            int((lm[11].y + lm[12].y) / 2 * fh)
        )
        
        dx = nose[0] - neck[0]
        dy = nose[1] - neck[1]
        angulo_pescoco_cru_bruto = math.degrees(math.atan2(dx, -dy))
        angulo_pescoco_lat = norm_angle(angulo_pescoco_cru_bruto)
        angulo_pescoco_cru = angulo_pescoco_lat
        
        if config.IS_CALIBRATED:
            angulo_pescoco_ajustado = abs(angulo_pescoco_lat - config.BASE_ANGLE_NECK)
        else:
            angulo_pescoco_ajustado = angulo_pescoco_lat
            
        nota_lateral = config.get_ema('neck_lat', angle_to_score(angulo_pescoco_ajustado, max_angle=config.MAX_ANGLE_NECK))

        # Pescoço (Forward Head Posture - Abordagem 2D Pura: Slump e Pitch)
        # Ignora profundidade (eixo Z) e foca na compressão vertical e inclinação
        # do rosto — proxy 2D para o Ângulo Craniovertebral (CVA).
        # Referência Clínica: Yip et al. (2008) estabelecem CVA < 50° como
        # indicador de risco severo de FHP; Ruivo et al. (2014) validam o método
        # fotogramétrico para avaliação cervical e reportam prevalência de FHP
        # em adolescentes.
        # Referência de Carga Biomecânica: Hansraj (2014) demonstra que a flexão
        # da cabeça aumenta progressivamente a carga na coluna cervical: ~12 kg a
        # 15°, ~18 kg a 30°, ~22 kg a 45° e ~27 kg a 60° de flexão.
        nota_frente = nota_lateral
        taxa_queda = 0.0
        taxa_rosto = 0.0
        
        if l_sh and r_sh and valid(2) and valid(5) and valid(7) and valid(8):
            # 1. Referência de Largura (para tornar a medição independente da
            #    distância da câmera)
            sw = math.hypot(lm[11].x - lm[12].x, lm[11].y - lm[12].y)
            
            if sw > 1e-6:
                # --- MÉTRICA 1: Desabamento Vertical (Slump) ---
                # Distância vertical pura (Y) entre a média dos ombros e a média
                # dos olhos. Quando o usuário curva o pescoço para a frente/baixo,
                # essa distância encolhe.
                shoulder_y_avg = (lm[11].y + lm[12].y) / 2.0
                eye_y_avg = (lm[2].y + lm[5].y) / 2.0
                raw_slump = (shoulder_y_avg - eye_y_avg) / sw
                
                # --- MÉTRICA 2: Inclinação do Queixo (Pitch) ---
                # Distância vertical entre as orelhas e o nariz.
                # Quando a cabeça vai para a frente, o queixo sobe para olhar a
                # tela. No OpenCV, Y cresce para baixo. Se o nariz sobe (menor Y),
                # a diferença aumenta.
                ear_y_avg = (lm[7].y + lm[8].y) / 2.0
                nose_y = lm[0].y
                raw_pitch = (ear_y_avg - nose_y) / sw
                
                # Suavização para evitar tremores
                taxa_queda = config.get_ema('neck_slump', raw_slump)
                taxa_rosto = config.get_ema('neck_pitch', raw_pitch)
                
                if getattr(config, 'IS_CALIBRATED', False):
                    # SLUMP DEVIATION: Positivo se o pescoço "encolheu"
                    # (Slump atual < Base)
                    desvio_queda = getattr(config, 'BASE_SLUMP', 0.0) - taxa_queda
                    
                    # PITCH DEVIATION: Positivo se o queixo "levantou"
                    # (Pitch atual > Base)
                    desvio_rosto = taxa_rosto - getattr(config, 'BASE_PITCH', 0.0)
                    
                    max_desvio = getattr(config, 'MAX_RATIO_DEVIATION', 0.15)
                    
                    # Calcula o nível de alerta para ambas as heurísticas
                    if desvio_queda > 0:
                        penalidade_queda = max(0.0, min(desvio_queda / max_desvio, 1.0))
                    else:
                        penalidade_queda = 0.0
                        
                    if desvio_rosto > 0:
                        penalidade_rosto = max(0.0, min(desvio_rosto / max_desvio, 1.0))
                    else:
                        penalidade_rosto = 0.0
                    
                    # Pega a penalidade mais severa (dispara se a pessoa encolher
                    # muito OU levantar muito o queixo)
                    pior_erro = max(penalidade_queda, penalidade_rosto)
                    nota_frente = config.get_ema('neck_fwd', 1.0 - pior_erro)

        # Atualiza o dicionário de informações para a UI desenhar as setas
        menor_nota = min(nota_lateral, nota_frente)
        dicionario_postura['neck'] = (neck, nose, menor_nota, {
            'score_lat': nota_lateral, 
            'score_fwd': nota_frente, 
            'slump_ratio': taxa_queda,
            'pitch_ratio': taxa_rosto
        })

    # Cabeça (Inclinação Lateral / Head Roll)
    # Referências Clínicas: ISO 11226:2000 (Princípio de Simetria) e Kapandji
    # (Fisiologia Articular, v.3). Kapandji define a amplitude total (ROM) do
    # pescoço. Os limiares de software (4° a 15°) garantem a permanência na
    # "zona neutra" segura, prevenindo o desgaste dos discos cervicais.
    # Métrica de Engenharia: Média do alinhamento horizontal ocular, auricular e
    # bucal para redução de ruído (jitter).
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
        
        angulo_olho = norm_angle(angle_eye_raw)
        angulo_orelha = norm_angle(angle_ear_raw)
        angulo_boca = norm_angle(angle_mouth_raw)
        
        angulo_medio = (angulo_olho + angulo_orelha + angulo_boca) / 3.0
        angulo_cabeca_cru = angulo_medio
        
        if config.IS_CALIBRATED:
            rolamento_ajustado = abs(angulo_medio - config.BASE_HEAD_ROLL)
        else:
            rolamento_ajustado = angulo_medio
            
        nota_cabeca = config.get_ema('head_roll', angle_to_score(rolamento_ajustado, max_angle=config.MAX_HEAD_ROLL_ANGLE))
        
        dicionario_postura['head'] = (l_eye, r_eye, nota_cabeca, f"{angulo_medio:.1f}°")

        cor_cabeca = (255, 255, 255) if not getattr(config, 'IS_CALIBRATED', True) else score_to_color(nota_cabeca)
        desenhos_extras.append(('line', l_mouth, r_mouth, cor_cabeca, 4))
        desenhos_extras.append(('circle', l_mouth, 7, (255, 255, 255), -1))
        desenhos_extras.append(('circle', r_mouth, 7, (255, 255, 255), -1))
        desenhos_extras.append(('line', l_ear, r_ear, cor_cabeca, 4))
        desenhos_extras.append(('circle', l_ear, 7, (255, 255, 255), -1))
        desenhos_extras.append(('circle', r_ear, 7, (255, 255, 255), -1))

    return dicionario_postura, desenhos_extras, angulo_ombro_cru, angulo_ratio_cru, angulo_cabeca_cru, angulo_pescoco_cru


def draw_posture_lines(frame, posture, extra_drawings):
    is_calibrated = getattr(config, 'IS_CALIBRATED', True)
    for key, (p1, p2, score, _) in posture.items():
        color = (255, 255, 255) if not is_calibrated else score_to_color(score)
        cv2.line(frame, p1, p2, color, 4)
        cv2.circle(frame, p1, 7, (255, 255, 255), -1)
        cv2.circle(frame, p2, 7, (255, 255, 255), -1)
        
        if not is_calibrated:
            continue
            
        # Setas de feedback para ombros e cabeça:
        # Detecta qual lado está mais baixo (p1 ou p2) e aponta setas
        # indicando a direção de correção para cada ponto.
        if score < 0.55 and key in ['shoulder', 'head']:
            offset = 15
            arrow_len = 25
            arrow_color = (255, 0, 150) 
            
            if p1[1] > p2[1]:  # p1 está mais baixo: sobe p1, desce p2
                cv2.arrowedLine(frame, (p1[0], p1[1] - offset), (p1[0], p1[1] - offset - arrow_len), arrow_color, 4, tipLength=0.4)
                cv2.arrowedLine(frame, (p2[0], p2[1] + offset), (p2[0], p2[1] + offset + arrow_len), arrow_color, 4, tipLength=0.4)
            else:              # p2 está mais baixo: sobe p2, desce p1
                cv2.arrowedLine(frame, (p2[0], p2[1] - offset), (p2[0], p2[1] - offset - arrow_len), arrow_color, 4, tipLength=0.4)
                cv2.arrowedLine(frame, (p1[0], p1[1] + offset), (p1[0], p1[1] + offset + arrow_len), arrow_color, 4, tipLength=0.4)
                
        # Setas de feedback para o pescoço: Heurística visual de UI/UX.
        # dx (horizontal): score_lat ruim -> aponta para centralizar a cabeça lateralmente.
        # dy (vertical):   score_fwd ruim -> orienta o usuário a recolher ou estender o pescoço.
        elif score < 0.55 and key == 'neck':
            arrow_len = 30
            arrow_color = (255, 0, 150)
            mid_x = int((p1[0] + p2[0]) / 2)
            mid_y = int((p1[1] + p2[1]) / 2)
            
            info_dict = posture['neck'][3]
            score_lat = info_dict['score_lat']
            score_fwd = info_dict['score_fwd']
            
            dx = dy = 0
            
            if score_lat < 0.55:  # cabeça inclinada lateralmente
                if p2[0] < p1[0]:
                    dx = arrow_len // 2  # nariz à esquerda do pescoço: aponta para direita
                else:
                    dx = -arrow_len // 2  # nariz à direita: aponta para esquerda
                    
            if score_fwd < 0.55 and config.IS_CALIBRATED:
                # Com a nova heurística, sabemos exatamente o que o usuário fez de errado:
                slump_dev = config.BASE_SLUMP - info_dict['slump_ratio']
                pitch_dev = info_dict['pitch_ratio'] - config.BASE_PITCH
                
                if slump_dev > pitch_dev:
                    # O pescoço encolheu / desabou. Seta apontando para CIMA (Cresça a postura)
                    dy = -arrow_len // 2  
                else:
                    # O queixo está muito levantado. Seta apontando para BAIXO (Abaixe o queixo / Retraia a cabeça)
                    dy = arrow_len // 2
                    
            if dx != 0:
                cv2.arrowedLine(frame, (mid_x - dx, mid_y), (mid_x + dx, mid_y), arrow_color, 4, tipLength=0.4)
                
            if dy != 0:
                cv2.arrowedLine(frame, (mid_x, mid_y - dy), (mid_x, mid_y + dy), arrow_color, 4, tipLength=0.4)
        
    for shape, *args in extra_drawings:
        if shape == 'line':
            cv2.line(frame, *args)
        elif shape == 'circle':
            cv2.circle(frame, *args)