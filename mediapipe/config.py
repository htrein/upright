import collections

# Definido em runtime pelo argumento --gpu / --cpu (padrão: CPU para máxima compatibilidade)
USE_GPU = False

VISIBILITY_THRESHOLD = 0.5  # Confiança mínima (0 a 1) do MediaPipe

# Filtro Passa-Baixa
# Referência: Winter, D. A. (2009). Biomechanics and Motor Control of Human Movement.
# Este filtro suaviza tremores de tracking e oscilações articulares invisíveis a olho nu,
# garantindo que o alerta não dispare por causa de micro-movimentos.
EMA_ALPHA = 0.25            

# Janela de Postura Estática (ISO 11226)
# A ISO classifica posturas como prejudiciais quando mantidas por vários segundos.
# O sistema avalia a sustentação da má postura na janela móvel de 30 segundos.
FPS_ESTIMATE = 30
POSTURE_WINDOW_SEC = 30
POSTURE_WINDOW = POSTURE_WINDOW_SEC * FPS_ESTIMATE
LOG_INTERVAL_FRAMES = 30   

# Estas variáveis podem ser alteradas pela tela de configuração ou pela calibração
# O disparo do alerta ocorre quando (score < THRESHOLD).
# Sendo score = 1.0 - (angle / MAX_ANGLE), o alerta dispara no ângulo = MAX_ANGLE * (1.0 - THRESHOLD).
BAD_POSTURE_THRESHOLD = 0.50 
MAX_ANGLE_SHOULDER = 10.0 
MAX_ANGLE_NECK = 15.0    
BASE_SLUMP = 0.0          # Distância vertical Ombros -> Olhos (Calibrado em runtime)
BASE_PITCH = 0.0          # Distância vertical Orelhas -> Nariz (Calibrado em runtime)
MAX_HEAD_ROLL_ANGLE = 8.0 
MAX_RATIO_DEVIATION = 0.15 

# Estado de Usuário Atual
CURRENT_USER_ID = None
CURRENT_USERNAME = None
CURRENT_RIGIDITY = "Normal"
CURRENT_CALIB_MODE = "Usar Padrao do Sistema"

# Calibração Dinâmica 
IS_CALIBRATED = False
BASE_ANGLE_SHOULDER = 0.0 
BASE_ANGLE_NECK = 0.0
BASE_HEAD_ROLL = 0.0

# Privacidade 
PRIVACY_MODE = False
PRIVACY_STYLE = 'silhouette'  # 'silhouette', 'blur', 'mosaic'
SILHOUETTE_COLOR = (30, 30, 30)   
BLUR_KSIZE = 55
MOSAIC_SCALE = 0.05
SEG_THRESHOLD = 0.6   

# ESTADO GLOBAL DA SESSÃO 
memoria_suavizacao = {}
_posture_history = collections.deque(maxlen=POSTURE_WINDOW)
IS_PAUSED = False
AUDIO_ALERT_ENABLED = True

# Funções auxiliares para estado que precisam acessar globals
def reset_ema():
    global memoria_suavizacao
    memoria_suavizacao = {}

def get_ema(key, current_value, alpha=EMA_ALPHA):
    if key not in memoria_suavizacao:
        memoria_suavizacao[key] = current_value
        return current_value
    
    # Mistura o valor antigo com o novo para não dar saltos bruscos
    novo_valor = alpha * current_value + (1.0 - alpha) * memoria_suavizacao[key]
    memoria_suavizacao[key] = novo_valor
    return novo_valor
