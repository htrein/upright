# upright.spec  —  Arquivo de build PyInstaller para o Upright Posture Tracking
# Gerado para: Linux e Windows (onedir)
#
# Como usar:
#   Linux  : bash ../scripts/build_exe.sh
#   Windows: ..\scripts\build_exe.bat

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# ── Coleta completa de pacotes com assets próprios ─────────────────────────────
mp_datas, mp_bins, mp_hidden = collect_all('mediapipe')
ctk_datas, ctk_bins, ctk_hidden = collect_all('customtkinter')
cv2_datas, cv2_bins, cv2_hidden = collect_all('cv2')

# ── Análise principal ──────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=mp_bins + ctk_bins + cv2_bins,
    datas=[
        # Modelos MediaPipe (pose + segmentação)
        ('models', 'models'),
        # Dados dos pacotes Python
        *mp_datas,
        *ctk_datas,
        *cv2_datas,
    ],
    hiddenimports=[
        # Módulos locais do projeto
        'db', 'config', 'posture', 'privacy', 'hud',
        'auth_window', 'config_window', 'generate_report',
        # MediaPipe
        'mediapipe',
        'mediapipe.tasks',
        'mediapipe.tasks.python',
        'mediapipe.tasks.python.vision',
        'mediapipe.tasks.python.components',
        'mediapipe.tasks.python.components.containers',
        'mediapipe.tasks.python.components.processors',
        # OpenCV
        'cv2',
        # Imagem
        'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
        # UI
        'customtkinter',
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox',
        # Dados e sistema
        'sqlite3', 'numpy', 'webbrowser', 'threading',
        'pathlib', 'platform', 'collections',
        # Áudio (Windows — não causa erro se ausente em Linux)
        'winsound',
        # CodeCarbon (opcional — silencioso se não instalado)
        'codecarbon',
        # Propagados das coletas automáticas
        *mp_hidden,
        *ctk_hidden,
        *cv2_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Remove pacotes pesados desnecessários
        'IPython', 'jupyter', 'notebook',
        'scipy', 'pandas', 'sklearn',
        'PyQt5', 'PyQt6', 'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='upright',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # console=False oculta a janela de terminal no Windows.
    # No Linux não tem efeito.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='upright',
)
