@echo off
:: download_mp_tasks.bat — Baixa os modelos do MediaPipe no Windows
::
:: Uso:
::   scripts\download_mp_tasks.bat
::

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set MODELS_DIR=%ROOT_DIR%\mediapipe\models

if not exist "%MODELS_DIR%" (
    mkdir "%MODELS_DIR%"
)

echo Baixando modelos do MediaPipe (Tasks API)...
echo.

set POSE_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
set SEG_URL="https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"

set POSE_DEST=%MODELS_DIR%\pose_landmarker_full.task
set SEG_DEST=%MODELS_DIR%\selfie_segmenter.tflite

:: Função de download usando PowerShell
:: Parâmetros: <URL> <Destino>
goto :main

:download_file
set url=%~1
set dest=%~2
echo Baixando %dest%...
powershell -Command "Invoke-WebRequest -Uri '%url%' -OutFile '%dest%'"
exit /b

:main
if not exist "%POSE_DEST%" (
    call :download_file %POSE_URL% "%POSE_DEST%"
) else (
    echo Modelo Pose Landmarker ja existe: %POSE_DEST%
)

if not exist "%SEG_DEST%" (
    call :download_file %SEG_URL% "%SEG_DEST%"
) else (
    echo Modelo Selfie Segmenter ja existe: %SEG_DEST%
)

echo.
echo Pronto! Modelos salvos em: %MODELS_DIR%

endlocal
