import collections

# ====== CONFIGURAÇÕES ESTÁTICAS ======
VISIBILITY_THRESHOLD = 0.5  # Confiança mínima (0 a 1) para considerar a parte do corpo visível
EMA_ALPHA = 0.25            # Fator de suavização da reatividade das linhas
FPS_ESTIMATE = 30
POSTURE_WINDOW_SEC = 30
POSTURE_WINDOW = POSTURE_WINDOW_SEC * FPS_ESTIMATE
LOG_INTERVAL_FRAMES = 30    # Aprox 1 segundo

# ====== VARIÁVEIS INJETÁVEIS / MUTÁVEIS ======
# Estas variáveis podem ser alteradas pela tela de configuração ou pela calibração
BAD_POSTURE_THRESHOLD = 0.45 
MAX_ANGLE_SHOULDER = 20.0 
MAX_ANGLE_NECK = 24.0     
NECK_RATIO_BASE = 0.25    
MAX_HEAD_ROLL_ANGLE = 15.0 

# Estado de Usuário Atual
CURRENT_USER_ID = None
CURRENT_USERNAME = None
CURRENT_RIGIDITY = "Normal"
CURRENT_CALIB_MODE = "Usar Padrao do Sistema"

# --- Calibração Dinâmica ---
IS_CALIBRATED = False
BASE_ANGLE_SHOULDER = 0.0 
BASE_HEAD_ROLL = 0.0

# --- Privacidade ---
PRIVACY_MODE = False
PRIVACY_STYLE = 'silhouette'  # 'silhouette', 'blur', 'mosaic'
SILHOUETTE_COLOR = (30, 30, 30)   
BLUR_KSIZE = 55
MOSAIC_SCALE = 0.05
SEG_THRESHOLD = 0.6   

# ====== ESTADO GLOBAL DA SESSÃO ======
_ema_state = {}
_posture_history = collections.deque(maxlen=POSTURE_WINDOW)
IS_PAUSED = False
WANTS_RECONFIG = False

# Funções auxiliares para estado que precisam acessar globals
def reset_ema():
    global _ema_state
    _ema_state = {}

def get_ema(key, value, alpha=EMA_ALPHA):
    prev = _ema_state.get(key, value)
    new = alpha * value + (1 - alpha) * prev
    _ema_state[key] = new
    return new
