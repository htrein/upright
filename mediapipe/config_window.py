import customtkinter as ctk
import webbrowser
import threading
import config
import db

def show_config_window():
    def apply_settings():
        rigidez    = var_rigidez.get()
        calibracao = var_calib.get()
        
        if rigidez == "Rigoroso":
            config.BAD_POSTURE_THRESHOLD = 0.60
            config.MAX_ANGLE_SHOULDER = 12.0
            config.MAX_ANGLE_NECK = 15.0
        elif rigidez == "Relaxado":
            config.BAD_POSTURE_THRESHOLD = 0.30
            config.MAX_ANGLE_SHOULDER = 28.0
            config.MAX_ANGLE_NECK = 35.0
        else:
            config.BAD_POSTURE_THRESHOLD = 0.45
            config.MAX_ANGLE_SHOULDER = 20.0
            config.MAX_ANGLE_NECK = 24.0
            
        config.CURRENT_RIGIDITY = rigidez
        config.CURRENT_CALIB_MODE = calibracao
        
        if calibracao == "Usar Padrao do Sistema":
            config.IS_CALIBRATED = True
            config.BASE_ANGLE_SHOULDER = 0.0
            config.NECK_RATIO_BASE = 0.25
            config.BASE_HEAD_ROLL = 0.0
            if config.CURRENT_USER_ID:
                db.save_calibration(config.CURRENT_USER_ID, 0.0, 0.25, 0.0)
        elif calibracao == "Calibrar Manualmente":
            config.IS_CALIBRATED = False
            

        if config.CURRENT_USER_ID:
            db.save_preferences(config.CURRENT_USER_ID, rigidez, calibracao)
            
        root.destroy()

    def show_tutorial():
        win = ctk.CTkToplevel(root)
        win.title("Tutorial de Ambientação")
        win.geometry("500x340")
        win.resizable(False, False)
        win.after(150, win.grab_set)
        lines = (
            "Tutorial de Ambientação — Upright\n\n"
            "1. Distância: fique a 40–60 cm da webcam.\n"
            "2. Câmera: posicione na altura dos olhos ou levemente acima.\n"
            "3. Enquadramento: ombros e rosto devem estar visíveis.\n"
            "4. Iluminação: evite contra-luz forte atrás de você.\n"
            "5. Postura: pés no chão e costas bem apoiadas."
        )
        ctk.CTkLabel(win, text=lines, justify="left", wraplength=460,
                     font=ctk.CTkFont(size=14)).pack(padx=24, pady=28)
        ctk.CTkButton(win, text="Fechar", command=win.destroy,
                      width=140, height=38,
                      font=ctk.CTkFont(size=14)).pack(pady=(0, 20))

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Upright")
    root.resizable(False, False)

    W, H = 680, 530
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw - W)//2}+{(sh - H)//2}")

    hdr = ctk.CTkFrame(root, fg_color=("#0f172a", "#0f172a"), corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(hdr, text="UPRIGHT",
                 font=ctk.CTkFont(size=36, weight="bold"),
                 text_color="#38bdf8").pack(pady=(22, 4))
    ctk.CTkLabel(hdr, text="Monitor de Postura em Tempo Real",
                 font=ctk.CTkFont(size=15),
                 text_color="#64748b").pack(pady=(0, 18))

    body = ctk.CTkFrame(root, fg_color=("#1e293b", "#1e293b"), corner_radius=0)
    body.pack(fill="both", expand=True)

    inner = ctk.CTkFrame(body, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=32, pady=20)

    ctk.CTkLabel(inner, text="Rigidez da Avaliação",
                 font=ctk.CTkFont(size=15, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", pady=(0, 8))

    rigidity_val = getattr(config, 'CURRENT_RIGIDITY', 'Normal')
    var_rigidez = ctk.StringVar(value=rigidity_val)
    radio_frame_r = ctk.CTkFrame(inner, fg_color="#0f172a", corner_radius=12)
    radio_frame_r.pack(fill="x", pady=(0, 20))

    radio_cfg = [
        ("Relaxado",  "Ângulos amplos, menos alertas"),
        ("Normal",    "Configuração padrão recomendada"),
        ("Rigoroso",  "Ângulos restritos, mais alertas"),
    ]
    for val, desc in radio_cfg:
        row = ctk.CTkFrame(radio_frame_r, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        ctk.CTkRadioButton(row, text=val, variable=var_rigidez, value=val,
                           font=ctk.CTkFont(size=15, weight="bold"),
                           radiobutton_width=20, radiobutton_height=20,
                           fg_color="#1d4ed8", hover_color="#2563eb").pack(side="left")
        ctk.CTkLabel(row, text=f"  —  {desc}",
                     font=ctk.CTkFont(size=13),
                     text_color="#64748b").pack(side="left")

    ctk.CTkLabel(inner, text="Calibração Inicial",
                 font=ctk.CTkFont(size=15, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", pady=(0, 8))

    calib_val = getattr(config, 'CURRENT_CALIB_MODE', "Usar Padrao do Sistema")
        
    var_calib = ctk.StringVar(value=calib_val)
    radio_frame_c = ctk.CTkFrame(inner, fg_color="#0f172a", corner_radius=12)
    radio_frame_c.pack(fill="x", pady=(0, 24))

    calib_cfg = [
        ("Calibrar Manualmente",    "Assumir postura ideal e pressionar [C]"),
        ("Usar Padrao do Sistema",  "Usar limiares angulares fixos"),
    ]
    for val, desc in calib_cfg:
        row = ctk.CTkFrame(radio_frame_c, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        ctk.CTkRadioButton(row, text=val, variable=var_calib, value=val,
                           font=ctk.CTkFont(size=15, weight="bold"),
                           radiobutton_width=20, radiobutton_height=20,
                           fg_color="#1d4ed8", hover_color="#2563eb").pack(side="left")
        ctk.CTkLabel(row, text=f"  —  {desc}",
                     font=ctk.CTkFont(size=13),
                     text_color="#64748b").pack(side="left")

    btns = ctk.CTkFrame(inner, fg_color="transparent")
    btns.pack(fill="x")

    def open_report():
        import generate_report as gr
        data = gr.get_data(config.CURRENT_USER_ID)
        path = gr.generate_html(data, config.CURRENT_USERNAME if config.CURRENT_USERNAME else 'Todos')
        webbrowser.open(f"file://{path}")

    ctk.CTkButton(btns, text="Ver Relatorio", fg_color="#475569", hover_color="#334155",
                  command=lambda: threading.Thread(target=open_report, daemon=True).start(),
                  width=150, height=42, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
                  
    ctk.CTkButton(btns, text="Como Usar?", fg_color="#38bdf8", hover_color="#0ea5e9", text_color="#0f172a",
                  command=show_tutorial,
                  width=150, height=42, font=ctk.CTkFont(size=14, weight="bold")).pack(side="right")
                  
    ctk.CTkButton(btns, text="Iniciar Avaliação", fg_color="#1d4ed8", hover_color="#2563eb",
                  command=apply_settings,
                  width=240, height=42, font=ctk.CTkFont(size=15, weight="bold")).pack(side="right", padx=(0, 16))

    root.mainloop()
