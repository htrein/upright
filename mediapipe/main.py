import cv2
import os
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
    from codecarbon import EmissionsTracker as _ETracker
    _HAS_CARBON = True
except ImportError:
    _HAS_CARBON = False
import time
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def main():
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
        config.NECK_RATIO_BASE     = _saved_cal['neck_ratio_base']
        config.BASE_HEAD_ROLL      = _saved_cal['base_head_roll']
        config.IS_CALIBRATED       = True
        print(f"Calibracao carregada para '{username}'.")

    if _saved_prefs:
        config.CURRENT_RIGIDITY = _saved_prefs['rigidity']
        config.CURRENT_CALIB_MODE = _saved_prefs.get('calib_mode', 'Usar Padrao do Sistema')
        if config.CURRENT_RIGIDITY == 'Rigoroso':
            config.BAD_POSTURE_THRESHOLD = 0.60
            config.MAX_ANGLE_SHOULDER = 12.0
            config.MAX_ANGLE_NECK = 15.0
        elif config.CURRENT_RIGIDITY == 'Relaxado':
            config.BAD_POSTURE_THRESHOLD = 0.30
            config.MAX_ANGLE_SHOULDER = 28.0
            config.MAX_ANGLE_NECK = 35.0
        else:
            config.BAD_POSTURE_THRESHOLD = 0.45
            config.MAX_ANGLE_SHOULDER = 20.0
            config.MAX_ANGLE_NECK = 24.0
    else:
        show_config_window()

    while True:
        config.WANTS_RECONFIG = False
        session_id = db.start_session(user_id)
        frame_counter = 0
        acc_global = 0.0
        acc_shoulder = 0.0
        acc_neck = 0.0
        acc_valid_frames = 0

        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cv2.namedWindow("Upright Mediapipe", cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Upright Mediapipe", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        _tracker = None
        if _HAS_CARBON:
            try:
                _tracker = _ETracker(project_name="upright", save_to_file=True,
                                     output_dir=os.path.dirname(os.path.abspath(__file__)),
                                     log_level="error",
                                     offline_mode=True, country_iso_code="BRA")
                _tracker.start()
            except Exception:
                _tracker = None

        model_dir = os.path.join(os.path.dirname(__file__), 'models')
        pose_model_path = os.path.join(model_dir, 'pose_landmarker_full.task')
        seg_model_path = os.path.join(model_dir, 'selfie_segmenter.tflite')

        if not os.path.exists(pose_model_path) or not os.path.exists(seg_model_path):
            print("Modelos GPU não encontrados! Por favor rode 'scripts/download_mp_tasks.sh' primeiro.")
            raise SystemExit(1)

        base_options_pose = python.BaseOptions(
            model_asset_path=pose_model_path,
            delegate=python.BaseOptions.Delegate.GPU)

        options_pose = vision.PoseLandmarkerOptions(
            base_options=base_options_pose,
            running_mode=vision.RunningMode.VIDEO,
            output_segmentation_masks=False)

        base_options_seg = python.BaseOptions(
            model_asset_path=seg_model_path,
            delegate=python.BaseOptions.Delegate.GPU)

        options_seg = vision.ImageSegmenterOptions(
            base_options=base_options_seg,
            running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True,
            output_category_mask=False)

        with vision.PoseLandmarker.create_from_options(options_pose) as pose_mp, \
             vision.ImageSegmenter.create_from_options(options_seg) as segmenter:
            
            start_time_ns = time.time_ns()
            last_timestamp_ms = -1
            
            try:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                        
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

                    posture_dict = {}
                    global_score = 1.0
                    
                    if res.pose_landmarks and len(res.pose_landmarks) > 0:
                        lm_list = res.pose_landmarks[0]
                        posture_dict, extra_drawings, raw_ang, raw_ratio, raw_roll = posture.evaluate_posture(lm_list, fw, fh)
                        
                        if config.PRIVACY_MODE and seg_result.confidence_masks:
                            mask_idx = 1 if len(seg_result.confidence_masks) > 1 else 0
                            seg_mask = (seg_result.confidence_masks[mask_idx].numpy_view() > config.SEG_THRESHOLD).astype(np.float32)
                            frame = privacy.apply_privacy_segmentation(frame, seg_mask, config.PRIVACY_STYLE)
                        
                        posture.draw_posture_lines(frame, posture_dict, extra_drawings)

                        if config.IS_CALIBRATED:
                            global_score = (sum(v[2] for v in posture_dict.values()) / len(posture_dict)) if posture_dict else 1.0
                            
                            if not config.IS_PAUSED:
                                config._posture_history.append(global_score < config.BAD_POSTURE_THRESHOLD)
                                
                            pct_bad = (sum(config._posture_history) / len(config._posture_history)) if config._posture_history else 0.0

                            if not config.IS_PAUSED:
                                frame_counter += 1
                                acc_global += global_score
                                acc_shoulder += posture_dict.get('shoulder', (0,0,1.0))[2]
                                acc_neck += posture_dict.get('neck', (0,0,1.0))[2]
                                acc_valid_frames += 1

                                if frame_counter >= config.LOG_INTERVAL_FRAMES:
                                    if acc_valid_frames > 0:
                                        db.log_posture(
                                            session_id=session_id,
                                            global_score=acc_global / acc_valid_frames,
                                            shoulder_score=acc_shoulder / acc_valid_frames,
                                            neck_score=acc_neck / acc_valid_frames,
                                            is_bad_posture=bool(pct_bad >= 0.3)
                                        )
                                    frame_counter = 0
                                    acc_global = acc_shoulder = acc_neck = 0.0
                                    acc_valid_frames = 0
                                    
                            frame = hud.draw_hud_strip(frame, posture_dict, global_score, pct_bad)
                        else:
                            frame = hud.draw_calibration_hud(frame)

                    cv2.imshow("Upright Mediapipe", frame)

                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:
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
                            data = gr.get_data(config.CURRENT_USER_ID)
                            path = gr.generate_html(data, config.CURRENT_USERNAME)
                            print(f"Relatorio gerado: {path}")
                            webbrowser.open(f"file://{path}")
                        threading.Thread(target=_open_report, daemon=True).start()
                    elif key == ord('s'):
                        config.WANTS_RECONFIG = True
                        break
                    elif key == ord('c'):
                        if posture_dict and raw_ang is not None and raw_ratio is not None and raw_roll is not None:
                            config.BASE_ANGLE_SHOULDER = raw_ang
                        config.NECK_RATIO_BASE = raw_ratio
                        config.BASE_HEAD_ROLL = raw_roll
                        config.IS_CALIBRATED = True
                        config.reset_ema()
                        config._posture_history.clear()
                        db.save_calibration(user_id, raw_ang, raw_ratio, raw_roll)
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

        if config.WANTS_RECONFIG:
            show_config_window()
        else:
            break

if __name__ == "__main__":
    main()
