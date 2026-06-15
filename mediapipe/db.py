import sqlite3
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'posture_history.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conexao_banco = get_connection()
    ponteiro = conexao_banco.cursor()

    # Usuários
    ponteiro.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    ''')

    # Calibração por usuário
    ponteiro.execute('''
        CREATE TABLE IF NOT EXISTS calibrations (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id              INTEGER NOT NULL UNIQUE,
            base_angle_shoulder  REAL,
            neck_ratio_base      REAL,
            base_head_roll       REAL,
            updated_at           TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Preferências do usuário (rigidez)
    ponteiro.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id  INTEGER PRIMARY KEY,
            rigidity TEXT    NOT NULL DEFAULT 'Normal',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Sessões
    ponteiro.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER REFERENCES users(id),
            start_time TEXT NOT NULL,
            end_time   TEXT
        )
    ''')

    try:
        ponteiro.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)")
    except sqlite3.OperationalError:
        pass

    try:
        ponteiro.execute("ALTER TABLE calibrations ADD COLUMN base_slump REAL")
    except sqlite3.OperationalError:
        pass

    try:
        ponteiro.execute("ALTER TABLE calibrations ADD COLUMN base_pitch REAL")
    except sqlite3.OperationalError:
        pass

    try:
        ponteiro.execute("ALTER TABLE calibrations ADD COLUMN base_head_pitch REAL")
    except sqlite3.OperationalError:
        pass
        
    try:
        ponteiro.execute("ALTER TABLE user_preferences ADD COLUMN calib_mode TEXT DEFAULT 'Usar Padrao do Sistema'")
    except sqlite3.OperationalError:
        pass

    try:
        ponteiro.execute("ALTER TABLE calibrations ADD COLUMN base_angle_neck REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass

    try:
        ponteiro.execute("ALTER TABLE user_preferences ADD COLUMN audio_alert BOOLEAN DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    # Logs de postura
    ponteiro.execute('''
        CREATE TABLE IF NOT EXISTS posture_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     INTEGER,
            timestamp      TEXT    NOT NULL,
            global_score   REAL,
            shoulder_score REAL,
            neck_score     REAL,
            is_bad_posture BOOLEAN,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    ''')

    conexao_banco.commit()
    conexao_banco.close()


# Autenticação ------
def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def register_user(username: str, password: str):
    """Cria novo usuário. Retorna user_id ou None se username já existir."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)',
            (username.strip(), _hash_password(password), now)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None  # username duplicado
    finally:
        conn.close()

def login_user(username: str, password: str):
    """Valida credenciais. Retorna user_id ou None se inválido."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, password_hash FROM users WHERE username = ?',
        (username.strip(),)
    )
    row = cursor.fetchone()
    conn.close()
    if row and row[1] == _hash_password(password):
        return row[0]
    return None

def delete_user(user_id: int):
    """Exclui permanentemente o usuário e todos os dados associados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM posture_logs WHERE session_id IN (SELECT id FROM sessions WHERE user_id = ?)', (user_id,))
    cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM user_preferences WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM calibrations WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

# Preferências ------
def save_preferences(user_id: int, rigidity: str, calib_mode: str = 'Usar Padrao do Sistema', audio_alert: bool = True):
    conn = get_connection()
    conn.execute('''
        INSERT INTO user_preferences (user_id, rigidity, calib_mode, audio_alert) VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            rigidity = excluded.rigidity,
            calib_mode = excluded.calib_mode,
            audio_alert = excluded.audio_alert
    ''', (user_id, rigidity, calib_mode, int(audio_alert)))
    conn.commit()
    conn.close()

def load_preferences(user_id: int):
    """Retorna dict com preferências ou None se o usuário nunca configurou."""
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT rigidity, calib_mode, audio_alert FROM user_preferences WHERE user_id = ?', (user_id,)
        ).fetchone()
        conn.close()
        return {'rigidity': row[0], 'calib_mode': row[1], 'audio_alert': bool(row[2])} if row else None
    except sqlite3.OperationalError:
        try:
            row = conn.execute('SELECT rigidity, calib_mode FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone()
            conn.close()
            return {'rigidity': row[0], 'calib_mode': row[1], 'audio_alert': True} if row else None
        except sqlite3.OperationalError:
            row = conn.execute('SELECT rigidity FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone()
            conn.close()
            return {'rigidity': row[0], 'calib_mode': 'Usar Padrao do Sistema', 'audio_alert': True} if row else None

# Calibração -----
def save_calibration(user_id: int, base_angle_shoulder: float,
                     neck_ratio_base: float, base_head_roll: float, base_angle_neck: float = 0.0,
                     base_slump: float = 0.0, base_pitch: float = 0.0):
    """Salva (ou atualiza) a calibração do usuário."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO calibrations (user_id, base_angle_shoulder, neck_ratio_base, base_head_roll, base_angle_neck, base_slump, base_pitch, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            base_angle_shoulder = excluded.base_angle_shoulder,
            neck_ratio_base     = excluded.neck_ratio_base,
            base_head_roll      = excluded.base_head_roll,
            base_angle_neck     = excluded.base_angle_neck,
            base_slump          = excluded.base_slump,
            base_pitch          = excluded.base_pitch,
            updated_at          = excluded.updated_at
    ''', (user_id, base_angle_shoulder, neck_ratio_base, base_head_roll, base_angle_neck, base_slump, base_pitch, now))
    conn.commit()
    conn.close()

def load_calibration(user_id: int):
    """Retorna dict com calibração do usuário ou None se não houver."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE calibrations ADD COLUMN base_slump REAL")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE calibrations ADD COLUMN base_pitch REAL")
    except sqlite3.OperationalError:
        pass
        
    cursor.execute('''
        SELECT base_angle_shoulder, neck_ratio_base, base_head_roll, base_angle_neck, base_slump, base_pitch, updated_at
        FROM calibrations WHERE user_id = ?
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'base_angle_shoulder': row[0],
            'neck_ratio_base':     row[1],
            'base_head_roll':      row[2],
            'base_angle_neck':     row[3] if len(row) > 3 and row[3] is not None else 0.0,
            'base_slump':          row[4] if len(row) > 4 and row[4] is not None else 0.0,
            'base_pitch':          row[5] if len(row) > 5 and row[5] is not None else 0.0,
            'updated_at':          row[6],
        }
    return None

# Sessões ------
def start_session(user_id=None):
    """Inicia nova sessão e retorna o ID."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        'INSERT INTO sessions (user_id, start_time) VALUES (?, ?)',
        (user_id, now)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def end_session(session_id):
    """Atualiza a sessão com o horário de término."""
    if session_id is None:
        return
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('UPDATE sessions SET end_time = ? WHERE id = ?', (now, session_id))
    conn.commit()
    conn.close()

def log_posture(session_id, global_score, shoulder_score, neck_score, is_bad_posture):
    """Insere um log de postura agregada no banco."""
    if session_id is None:
        return
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO posture_logs
            (session_id, timestamp, global_score, shoulder_score, neck_score, is_bad_posture)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session_id, now, global_score, shoulder_score, neck_score, is_bad_posture))
    conn.commit()
    conn.close()