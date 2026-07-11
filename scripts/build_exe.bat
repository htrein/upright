@echo off
:: build_exe.bat — Gera o executável do Upright para Windows (modo onedir)
::
:: Uso:
::   scripts\build_exe.bat [nome_do_ambiente_conda]
::
:: Exemplo:
::   scripts\build_exe.bat mediapipe
::
:: Pré-requisitos:
::   - Anaconda/Miniconda instalado
::   - Ambiente conda com todas as dependências (ver environment-mediapipe.yml)
::   - Modelos baixados em mediapipe\models\ (rode scripts\download_mp_tasks.bat antes)

setlocal enabledelayedexpansion

:: ── Configurações ──────────────────────────────────────────────────────────────
if "%~1"=="" (set ENV_NAME=mediapipe) else (set ENV_NAME=%~1)

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set MEDIAPIPE_DIR=%ROOT_DIR%\mediapipe
set DIST_DIR=%ROOT_DIR%\dist
set BUILD_DIR=%ROOT_DIR%\build_pyinstaller

echo.
echo =============================================
echo   Upright -- Build de Executavel (Windows)
echo =============================================
echo.

:: ── 0. Verifica modelos ────────────────────────────────────────────────────────
if not exist "%MEDIAPIPE_DIR%\models\pose_landmarker_full.task" (
    echo ERRO: Modelos nao encontrados em mediapipe\models\
    echo       Execute primeiro: scripts\download_mp_tasks.bat
    exit /b 1
)
if not exist "%MEDIAPIPE_DIR%\models\selfie_segmenter.tflite" (
    echo ERRO: Modelos nao encontrados em mediapipe\models\
    echo       Execute primeiro: scripts\download_mp_tasks.bat
    exit /b 1
)
echo [OK] Modelos encontrados.

:: ── 1. Localiza e inicializa o conda ──────────────────────────────────────────
echo.
echo [1/4] Inicializando conda...

:: Tenta encontrar o conda em locais comuns
set CONDA_FOUND=0
for %%P in (
    "%USERPROFILE%\anaconda3\Scripts\conda.exe"
    "%USERPROFILE%\miniconda3\Scripts\conda.exe"
    "%LOCALAPPDATA%\anaconda3\Scripts\conda.exe"
    "%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
    "C:\ProgramData\anaconda3\Scripts\conda.exe"
    "C:\ProgramData\miniconda3\Scripts\conda.exe"
    "C:\anaconda3\Scripts\conda.exe"
    "C:\miniconda3\Scripts\conda.exe"
) do (
    if exist %%P (
        set CONDA_EXE=%%~P
        set CONDA_FOUND=1
        goto :found_conda
    )
)

:not_found_conda
echo ERRO: conda nao encontrado. Instale Anaconda ou Miniconda.
exit /b 2

:found_conda
echo       conda encontrado em: %CONDA_EXE%

:: Inicializa o conda para uso no script batch
call "%CONDA_EXE%" activate %ENV_NAME% 2>nul
if errorlevel 1 (
    echo ERRO: Ambiente conda '%ENV_NAME%' nao encontrado.
    echo       Crie-o com: conda env create -f environment-mediapipe.yml
    exit /b 3
)
echo       Ambiente '%ENV_NAME%' ativado.
python --version

:: ── 2. Instala / verifica PyInstaller ─────────────────────────────────────────
echo.
echo [2/4] Verificando PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo       Instalando PyInstaller...
    pip install pyinstaller --quiet
)
for /f "tokens=*" %%V in ('python -c "import PyInstaller; print(PyInstaller.__version__)"') do (
    echo       PyInstaller %%V
)

:: ── 3. Executa PyInstaller ────────────────────────────────────────────────────
echo.
echo [3/4] Executando PyInstaller ^(isso pode levar alguns minutos^)...

:: WORKAROUND: A pasta do projeto se chama "mediapipe", o que causa um conflito de nome
:: (name collision) com a biblioteca do python quando o PyInstaller tenta analisar.
:: Nos renomeamos temporariamente a pasta para 'src' para evitar o erro.
cd /d "%ROOT_DIR%"
ren mediapipe src

python -m PyInstaller ^
    --noconfirm ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    src\upright.spec

set BUILD_ERRORLEVEL=%errorlevel%

:: Restaura o nome original
ren src mediapipe

if %BUILD_ERRORLEVEL% neq 0 (
    echo.
    echo ERRO: PyInstaller falhou. Veja o log acima.
    exit /b 4
)

:: ── 4. Resultado ──────────────────────────────────────────────────────────────
echo.
echo [4/4] Build concluido!
echo.
echo =======================================================
echo   Executavel gerado em: %DIST_DIR%\upright\
echo =======================================================
echo.
echo   Como rodar:
echo     %DIST_DIR%\upright\upright.exe
echo.
echo   Para distribuir, compacte a pasta:
echo     Clique com botao direito em dist\upright ^> Enviar para ^> Pasta compactada
echo     (ou use 7-Zip / WinRAR)
echo.
echo   ATENCAO: posture_history.db e report.html sao criados
echo   no mesmo diretorio do executavel na primeira execucao.
echo.

endlocal
