import cv2
import os
import argparse
# Referência do Modelo de ML: Bazarevsky, V., et al. (2020). "BlazePose: On-device Real-time Body Pose tracking."
# Documenta como a rede neural extrai coordenadas corporais em tempo real com alta precisão.
import mediapipe as mp
import numpy as np
import db
import config
from auth_window import show_auth_window
from config_window import show_config_window
import posture
import privacy
import hud
try:
    # Referência de Sustentabilidade: Schwartz, R., et al. (2020). "Green AI."
    # Justifica a importância de mensurar e reportar a pegada de carbono (CO2) 
    # gerada pelo custo computacional de inferências contínuas de IA no client-side.
    from codecarbon import OfflineEmissionsTracker as _ETracker
    _HAS_CARBON = True
except ImportError:
    _HAS_CARBON = False
import time
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def main():
    parser = argparse.ArgumentParser(description="Upright Posture Tracking")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--gpu', action='store_true', help='Usa GPU para inferência (requer Linux com OpenGL ES)')
    group.add_argument('--cpu', action='store_true', help='Usa CPU para inferência (compatível com todos os sistemas)')
    args = parser.parse_args()

    if args.gpu:
        config.USE_GPU = True
        print("[INFO] Modo de processamento: GPU")
    else:
        config.USE_GPU = False
        print("[INFO] Modo de processamento: CPU (use --gpu para ativar GPU)")

    db.init_db()

    # Autenticação
    user_id, username = show_auth_window()
    if user_id is None:
        raise SystemExit("Nenhum usuario autenticado. Encerrando.")

    config.CURRENT_USER_ID = user_id
    config.CURRENT_USERNAME = username
    config.CURRENT_RIGIDITY = "Normal"  
    
    # Carrega preferências salvas
    _saved_prefs = db.load_preferences(user_id)
    _saved_cal   = db.load_calibration(user_id)

    if _saved_cal:
        config.BASE_ANGLE_SHOULDER = _saved_cal['base_angle_shoulder']
        # mantemos neck_ratio_base ignorado e extraimos slump e pitch
        config.BASE_HEAD_ROLL      = _saved_cal['base_head_roll']
        config.BASE_ANGLE_NECK     = _saved_cal.get('base_angle_neck', 0.0)
        config.BASE_SLUMP          = _saved_cal.get('base_slump', 0.0)
        config.BASE_PITCH          = _saved_cal.get('base_pitch', 0.0)
        config.IS_CALIBRATED       = True
        print(f"Calibracao carregada para '{username}'.")

    if _saved_prefs:
        config.CURRENT_RIGIDITY = _saved_prefs['rigidity']
        config.CURRENT_CALIB_MODE = _saved_prefs.get('calib_mode', 'Usar Padrao do Sistema')
        config.AUDIO_ALERT_ENABLED = _saved_prefs.get('audio_alert', True)
        if config.CURRENT_RIGIDITY == 'Rigoroso':
            config.BAD_POSTURE_THRESHOLD = 0.60 # Fator de disparo: 40% do MAX_ANGLE
            config.MAX_ANGLE_SHOULDER = 5.0  
            config.MAX_ANGLE_NECK = 8.0      
            config.MAX_HEAD_ROLL_ANGLE = 5.0
            config.MAX_RATIO_DEVIATION = 0.15
        elif config.CURRENT_RIGIDITY == 'Relaxado':
            config.BAD_POSTURE_THRESHOLD = 0.35 # Fator de disparo: 65% do MAX_ANGLE
            config.MAX_ANGLE_SHOULDER = 15.0 
            config.MAX_ANGLE_NECK = 25.0     
            config.MAX_HEAD_ROLL_ANGLE = 15.0
            config.MAX_RATIO_DEVIATION = 0.30
        else: # Normal
            config.BAD_POSTURE_THRESHOLD = 0.50 # Fator de disparo: 50% do MAX_ANGLE
            config.MAX_ANGLE_SHOULDER = 10.0 
            config.MAX_ANGLE_NECK = 15.0     
            config.MAX_HEAD_ROLL_ANGLE = 8.0 
            config.MAX_RATIO_DEVIATION = 0.20
            
        if config.CURRENT_CALIB_MODE == 'Usar Padrao do Sistema':
            config.BASE_ANGLE_SHOULDER = 0.0
            config.BASE_HEAD_ROLL = 0.0
            config.BASE_ANGLE_NECK = 0.0
            config.BASE_SLUMP = 1.22
            config.BASE_PITCH = -0.05
            config.IS_CALIBRATED = True
    else:
        show_config_window()

    time.sleep(0.2)

    session_id = db.start_session(user_id)
    log_counter = 0
    window_counter = 0
    acc_global = 0.0
    acc_shoulder = 0.0
    acc_neck = 0.0
    acc_valid_frames = 0

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cv2.namedWindow("Upright Mediapipe", cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_NORMAL)

    _tracker = None
    if _HAS_CARBON:
        try:
            _tracker = _ETracker(project_name=f"upright_{config.CURRENT_USERNAME}", save_to_file=True,
                                 output_dir=os.path.dirname(os.path.abspath(__file__)),
                                 log_level="error",
                                 tracking_mode="process",
                                 country_iso_code="BRA")
            _tracker.start()
        except Exception:
            _tracker = None

    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    pose_model_path = os.path.join(model_dir, 'pose_landmarker_full.task')
    seg_model_path = os.path.join(model_dir, 'selfie_segmenter.tflite')

    if not os.path.exists(pose_model_path) or not os.path.exists(seg_model_path):
        print("Modelos GPU não encontrados! Por favor rode 'scripts/download_mp_tasks.sh' primeiro.")
        raise SystemExit(1)

    _delegate = python.BaseOptions.Delegate.GPU if config.USE_GPU else python.BaseOptions.Delegate.CPU

    try:
        base_options_pose = python.BaseOptions(
            model_asset_path=pose_model_path,
            delegate=_delegate)

        options_pose = vision.PoseLandmarkerOptions(
            base_options=base_options_pose,
            running_mode=vision.RunningMode.VIDEO,
            output_segmentation_masks=False)

        base_options_seg = python.BaseOptions(
            model_asset_path=seg_model_path,
            delegate=_delegate)

        options_seg = vision.ImageSegmenterOptions(
            base_options=base_options_seg,
            running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True,
            output_category_mask=False)

    except Exception as e:
        if config.USE_GPU:
            print(f"[AVISO] Falha ao iniciar GPU delegate ({e}). Usando CPU como fallback.")
            config.USE_GPU = False
            base_options_pose = python.BaseOptions(
                model_asset_path=pose_model_path,
                delegate=python.BaseOptions.Delegate.CPU)
            options_pose = vision.PoseLandmarkerOptions(
                base_options=base_options_pose,
                running_mode=vision.RunningMode.VIDEO,
                output_segmentation_masks=False)
            base_options_seg = python.BaseOptions(
                model_asset_path=seg_model_path,
                delegate=python.BaseOptions.Delegate.CPU)
            options_seg = vision.ImageSegmenterOptions(
                base_options=base_options_seg,
                running_mode=vision.RunningMode.VIDEO,
                output_confidence_masks=True,
                output_category_mask=False)
        else:
            raise

    with vision.PoseLandmarker.create_from_options(options_pose) as pose_mp, \
         vision.ImageSegmenter.create_from_options(options_seg) as segmenter:
        start_time_ns = time.time_ns()
        last_timestamp_ms = -1
        fullscreen_set = False
        
        try:
            frozen_frame = None
            frozen_posture_dict = {}
            frozen_global_score = 1.0
            frozen_pct_bad = 0.0
            frozen_ang_ombro = None
            frozen_ang_roll = None
            frozen_ang_pescoco = None
            was_bad_posture = False

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                if not config.IS_PAUSED:
                    frame = cv2.flip(frame, 1)
                    fh, fw = frame.shape[:2]
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    timestamp_ms = (time.time_ns() - start_time_ns) // 1_000_000
                    if timestamp_ms <= last_timestamp_ms:
                        timestamp_ms = last_timestamp_ms + 1
                    last_timestamp_ms = timestamp_ms
                    
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                    res = pose_mp.detect_for_video(mp_image, timestamp_ms)
                    seg_result = segmenter.segment_for_video(mp_image, timestamp_ms)

                    dicionario_postura = {}
                    nota_global = 1.0
                    porcentagem_ruim = 0.0
                    ang_ombro_cru = None
                    ang_roll_cru = None
                    ang_pescoco_cru = None
                    
                    if res.pose_landmarks and len(res.pose_landmarks) > 0:
                        lm_list = res.pose_landmarks[0]
                        # A função avalia a postura e já embute o slump_ratio e pitch_ratio no dicionário
                        dicionario_postura, desenhos_extras, ang_ombro_cru, _, ang_roll_cru, ang_pescoco_cru = posture.evaluate_posture(lm_list, fw, fh)
                        
                        if config.PRIVACY_MODE and seg_result.confidence_masks:
                            mask_idx = 1 if len(seg_result.confidence_masks) > 1 else 0
                            seg_mask = (seg_result.confidence_masks[mask_idx].numpy_view() > config.SEG_THRESHOLD).astype(np.float32)
                            frame = privacy.apply_privacy_segmentation(frame, seg_mask, config.PRIVACY_STYLE)
                        
                        posture.draw_posture_lines(frame, dicionario_postura, desenhos_extras)

                        if config.IS_CALIBRATED:
                            # Soma os itens do dicionário usando um loop simples em vez de list comprehension (estilo amador)
                            soma_notas = 0.0
                            qtd_itens = 0
                            for item in dicionario_postura.values():
                                soma_notas = soma_notas + item[2]
                                qtd_itens = qtd_itens + 1
                                
                            if qtd_itens > 0:
                                nota_global = soma_notas / qtd_itens
                            else:
                                nota_global = 1.0
                                
                            is_bad_posture = (nota_global < config.BAD_POSTURE_THRESHOLD)
                            if is_bad_posture and not was_bad_posture:
                                if getattr(config, 'AUDIO_ALERT_ENABLED', True):
                                    import threading
                                    threading.Thread(target=lambda: os.system("paplay /usr/share/sounds/freedesktop/stereo/message.oga 2>/dev/null"), daemon=True).start()
                            was_bad_posture = is_bad_posture
                                
                            config._posture_history.append(nota_global < config.BAD_POSTURE_THRESHOLD)
                                
                            if config._posture_history:
                                soma_historico = 0
                                for item in config._posture_history:
                                    soma_historico = soma_historico + item
                                porcentagem_ruim = soma_historico / len(config._posture_history)
                            else:
                                porcentagem_ruim = 0.0

                            acc_global += nota_global
                            
                            ombro_data = dicionario_postura.get('shoulder', [None, None, 1.0])
                            acc_shoulder += ombro_data[2]
                            
                            pescoco_data = dicionario_postura.get('neck', [None, None, 1.0])
                            acc_neck += pescoco_data[2]
                            
                            acc_valid_frames += 1
                            log_counter += 1
                            
                            if log_counter >= config.LOG_INTERVAL_FRAMES:
                                import threading
                                if acc_valid_frames > 0:
                                    avg_global = acc_global / acc_valid_frames
                                    avg_shoulder = acc_shoulder / acc_valid_frames
                                    avg_neck = acc_neck / acc_valid_frames
                                else:
                                    avg_global = nota_global
                                    avg_shoulder = 1.0
                                    avg_neck = 1.0
                                
                                bool_ruim = False
                                if porcentagem_ruim >= 0.3:
                                    bool_ruim = True
                                    
                                threading.Thread(target=db.log_posture, args=(
                                    session_id,
                                    avg_global,
                                    avg_shoulder,
                                    avg_neck,
                                    bool_ruim
                                )).start()
                                log_counter = 0
                                acc_global = 0.0
                                acc_shoulder = 0.0
                                acc_neck = 0.0
                                acc_valid_frames = 0
                    else:
                        if config._posture_history:
                            soma_historico = 0
                            for item in config._posture_history:
                                soma_historico = soma_historico + item
                            porcentagem_ruim = soma_historico / len(config._posture_history)
                        else:
                            porcentagem_ruim = 0.0

                    frozen_frame = frame.copy()
                    frozen_posture_dict = dicionario_postura
                    frozen_global_score = nota_global
                    frozen_pct_bad = porcentagem_ruim
                    frozen_ang_ombro = ang_ombro_cru
                    frozen_ang_roll = ang_roll_cru
                    frozen_ang_pescoco = ang_pescoco_cru
                else:
                    if frozen_frame is not None:
                        frame = frozen_frame.copy()
                        dicionario_postura = frozen_posture_dict
                        nota_global = frozen_global_score
                        porcentagem_ruim = frozen_pct_bad
                        ang_ombro_cru = frozen_ang_ombro
                        ang_roll_cru = frozen_ang_roll
                        ang_pescoco_cru = frozen_ang_pescoco
                    else:
                        frame = cv2.flip(frame, 1)
                        dicionario_postura = {}
                        nota_global = 1.0
                        porcentagem_ruim = 0.0
                        ang_ombro_cru = None
                        ang_roll_cru = None
                        ang_pescoco_cru = None

                if config.IS_CALIBRATED:
                    frame = hud.draw_hud_strip(frame, dicionario_postura, nota_global, porcentagem_ruim)
                else:
                    frame = hud.draw_calibration_hud(frame)

                cv2.imshow("Upright Mediapipe", frame)

                window_counter += 1
                if not fullscreen_set and window_counter > 5:
                    if config.get_ema('is_fullscreen', 1.0) == 1.0:
                        cv2.setWindowProperty("Upright Mediapipe", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    fullscreen_set = True

                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q') or key == ord('Q'):
                    break
                elif key == ord('p'):
                    config.PRIVACY_MODE = not config.PRIVACY_MODE
                elif key == ord('m'):
                    styles = ['silhouette', 'blur', 'mosaic']
                    idx = styles.index(config.PRIVACY_STYLE)
                    config.PRIVACY_STYLE = styles[(idx + 1) % len(styles)]
                elif key == 32: 
                    config.IS_PAUSED = not config.IS_PAUSED
                elif key == ord('r'):
                    import generate_report as gr, webbrowser, threading
                    def _open_report():
                        data = gr.get_data(config.CURRENT_USER_ID, config.CURRENT_USERNAME)
                        path = gr.generate_html(data, config.CURRENT_USERNAME)
                        print(f"Relatorio gerado: {path}")
                        webbrowser.open(f"file://{path}")
                    threading.Thread(target=_open_report, daemon=True).start()
                elif key == ord('f'):
                    current = config.get_ema('is_fullscreen', 1.0)
                    new_state = 0.0 if current == 1.0 else 1.0
                    config.memoria_suavizacao['is_fullscreen'] = new_state
                    if new_state == 1.0:
                        cv2.setWindowProperty("Upright Mediapipe", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    else:
                        cv2.setWindowProperty("Upright Mediapipe", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                elif key == ord('s'):
                    cv2.destroyAllWindows()
                    cv2.waitKey(1)
                    show_config_window()
                    time.sleep(0.2)  # Delay para o gerenciador do Wayland/Gnome processar a destruição do Tkinter
                    cv2.namedWindow("Upright Mediapipe", cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_NORMAL)
                    cv2.setWindowProperty("Upright Mediapipe", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                    fullscreen_set = False
                    window_counter = 0
                elif key == ord('c'):
                    # Só permite calibrar se o sistema explicitamente estiver no modo de calibração
                    if not config.IS_CALIBRATED:
                        if dicionario_postura and ang_ombro_cru is not None and ang_roll_cru is not None and ang_pescoco_cru is not None:
                            info = dicionario_postura.get('neck', [None, None, None, {}])[3]
                            slump_val = info.get('slump_ratio', 0.0)
                            pitch_val = info.get('pitch_ratio', 0.0)
                            
                            config.BASE_ANGLE_SHOULDER = ang_ombro_cru
                            config.BASE_HEAD_ROLL = ang_roll_cru
                            config.BASE_ANGLE_NECK = ang_pescoco_cru
                            config.BASE_SLUMP = slump_val
                            config.BASE_PITCH = pitch_val
                            config.IS_CALIBRATED = True
                            config.reset_ema()
                            config._posture_history.clear()
                            db.save_calibration(user_id, ang_ombro_cru, 0.0, ang_roll_cru, ang_pescoco_cru, slump_val, pitch_val)
                            print("--- CALIBRADO COM SUCESSO ---")

        finally:
            cap.release()
            cv2.destroyAllWindows()

            if session_id:
                db.end_session(session_id)

            if _tracker:
                try:
                    emissions = _tracker.stop()
                    if emissions:
                        kwh = _tracker._total_energy.kWh if hasattr(_tracker, '_total_energy') else 0
                        print(f"Consumo estimado: {emissions:.4f} kgCO2 | {kwh * 1000:.2f} Wh")
                except Exception as e:
                    pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Sessão finalizada com sucesso (fechamento manual).")