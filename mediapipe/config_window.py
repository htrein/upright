import customtkinter as ctk
import webbrowser
import threading
import sys
import config
import db

def show_config_window():
    def apply_settings():
        rigidez    = var_rigidez.get()
        calibracao = var_calib.get()
        audio_alert = var_audio.get()

        if rigidez == "Rigoroso":
            config.BAD_POSTURE_THRESHOLD = 0.60 # Fator de disparo: 40% do MAX_ANGLE
            
            # Ombros: Dispara em 2.0°
            config.MAX_ANGLE_SHOULDER = 5.0  
            # Pescoço: Dispara em 3.2° 
            config.MAX_ANGLE_NECK = 8.0      
            # Head Roll: Dispara em 2.0° 
            config.MAX_HEAD_ROLL_ANGLE = 5.0
            #Penaliza desvios verticais em 10%
            config.MAX_RATIO_DEVIATION = 0.10
            
        elif rigidez == "Relaxado":
            config.BAD_POSTURE_THRESHOLD = 0.35 # Fator de disparo: 65% do MAX_ANGLE
            # Ombros: Dispara em 9.75° 
            config.MAX_ANGLE_SHOULDER = 15.0 
            # Pescoço: Dispara em 16.25° 
            config.MAX_ANGLE_NECK = 25.0     
            # Head Roll: Dispara em 9.75° 
            config.MAX_HEAD_ROLL_ANGLE = 15.0
            #Penaliza desvios verticais em 20%
            config.MAX_RATIO_DEVIATION = 0.20
            
        else: # Normal
            config.BAD_POSTURE_THRESHOLD = 0.50 # Fator de disparo: 50% do MAX_ANGLE
            # Ombros: Dispara em 5.0° 
            config.MAX_ANGLE_SHOULDER = 10.0 
            # Pescoço: Dispara em 7.5° 
            config.MAX_ANGLE_NECK = 15.0     
            # Head Roll: Dispara em 4.0° 
            config.MAX_HEAD_ROLL_ANGLE = 8.0 
            #Penaliza desvios verticais em 15%
            config.MAX_RATIO_DEVIATION = 0.15
            
        config.CURRENT_RIGIDITY = rigidez
        config.CURRENT_CALIB_MODE = calibracao
        config.AUDIO_ALERT_ENABLED = audio_alert
        
        if calibracao == "Usar Padrao do Sistema":
            config.IS_CALIBRATED = True
            config.BASE_ANGLE_SHOULDER = 0.0
            config.BASE_HEAD_ROLL = 0.0
            config.BASE_ANGLE_NECK = 0.0
            config.BASE_SLUMP = 1.22
            config.BASE_PITCH = -0.05
        elif calibracao in ["Calibrar Manualmente", "Recalibrar Manualmente"]:
            config.IS_CALIBRATED = False
            calibracao = "Calibrar Manualmente"
        elif calibracao == "Manter Calibração Atual":
            config.IS_CALIBRATED = True
            calibracao = "Calibrar Manualmente"

        if config.CURRENT_USER_ID:
            db.save_preferences(config.CURRENT_USER_ID, rigidez, calibracao, audio_alert)
            
        root.destroy()

    def show_tutorial():
        win = ctk.CTkToplevel(root)
        win.title("Tutorial de Ambientação")
        win.geometry("540x440")
        win.resizable(False, False)
        win.after(150, win.grab_set)
        lines = (
            "Tutorial de Ambientação — Upright\n\n"
            "1. Distância: fique a 40–60 cm da webcam.\n\n"
            "2. Câmera: posicione na altura dos olhos ou levemente acima.\n\n"
            "3. Enquadramento: ombros e rosto devem estar visíveis.\n\n"
            "4. Iluminação: evite contra-luz forte atrás de você.\n\n"
            "5. Postura: pés no chão e costas bem apoiadas."
        )
        ctk.CTkLabel(win, text=lines, justify="left", wraplength=460,
                     font=ctk.CTkFont(family="Arial", size=15)).pack(padx=24, pady=28)
        ctk.CTkButton(win, text="Fechar", command=win.destroy,
                      width=140, height=38,
                      font=ctk.CTkFont(family="Arial", size=14, weight="bold")).pack(pady=(0, 20))

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Upright")
    root.resizable(False, False)

    W, H = 760, 600
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
    btn_rigidez_dict = {}
    def update_rigidez(new_val):
        var_rigidez.set(new_val)
        for val, btn in btn_rigidez_dict.items():
            if val == new_val:
                btn.configure(fg_color="#1d4ed8", hover_color="#2563eb")
            else:
                btn.configure(fg_color="#334155", hover_color="#475569")

    for val, desc in radio_cfg:
        row = ctk.CTkFrame(radio_frame_r, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        btn = ctk.CTkButton(row, text=val, font=ctk.CTkFont(size=14, weight="bold"),
                            width=120, height=32, command=lambda v=val: update_rigidez(v))
        btn.pack(side="left")
        btn_rigidez_dict[val] = btn
        ctk.CTkLabel(row, text=f"  —  {desc}",
                     font=ctk.CTkFont(family="Arial", size=14),
                     text_color="#94a3b8").pack(side="left")
    update_rigidez(var_rigidez.get())

    ctk.CTkLabel(inner, text="Calibração Inicial",
                 font=ctk.CTkFont(size=15, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", pady=(0, 8))

    calib_val = getattr(config, 'CURRENT_CALIB_MODE', "Usar Padrao do Sistema")
    
    has_manual_calib = False
    if getattr(config, 'CURRENT_USER_ID', None):
        _cal = db.load_calibration(config.CURRENT_USER_ID)
        if _cal and (_cal['base_angle_shoulder'] != 0.0 or _cal['base_angle_neck'] != 0.0):
            has_manual_calib = True
            
    if has_manual_calib:
        calib_cfg = [
            ("Manter Calibração Atual", "Continuar usando sua calibração salva"),
            ("Recalibrar Manualmente",  "Assumir postura ideal e pressionar [C]"),
            ("Usar Padrao do Sistema",  "Usar limiares angulares fixos"),
        ]
        if calib_val == "Calibrar Manualmente" and getattr(config, 'IS_CALIBRATED', False):
            calib_val = "Manter Calibração Atual"
    else:
        calib_cfg = [
            ("Calibrar Manualmente",    "Assumir postura ideal e pressionar [C]"),
            ("Usar Padrao do Sistema",  "Usar limiares angulares fixos"),
        ]
        if calib_val == "Manter Calibração Atual":
            calib_val = "Calibrar Manualmente"

    var_calib = ctk.StringVar(value=calib_val)
    radio_frame_c = ctk.CTkFrame(inner, fg_color="#0f172a", corner_radius=12)
    radio_frame_c.pack(fill="x", pady=(0, 24))
    btn_calib_dict = {}
    def update_calib(new_val):
        var_calib.set(new_val)
        for val, btn in btn_calib_dict.items():
            if val == new_val:
                btn.configure(fg_color="#1d4ed8", hover_color="#2563eb")
            else:
                btn.configure(fg_color="#334155", hover_color="#475569")

    for val, desc in calib_cfg:
        row = ctk.CTkFrame(radio_frame_c, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        btn = ctk.CTkButton(row, text=val, font=ctk.CTkFont(size=14, weight="bold"),
                            width=200, height=32, command=lambda v=val: update_calib(v))
        btn.pack(side="left")
        btn_calib_dict[val] = btn
        ctk.CTkLabel(row, text=f"  —  {desc}",
                     font=ctk.CTkFont(family="Arial", size=14),
                     text_color="#94a3b8").pack(side="left")
    update_calib(var_calib.get())
    
    var_audio = ctk.BooleanVar(value=getattr(config, 'AUDIO_ALERT_ENABLED', True))
    switch_audio = ctk.CTkSwitch(inner, text="Aviso Sonoro de Má Postura", variable=var_audio, 
                                 font=ctk.CTkFont(size=15, weight="bold"), text_color="#94a3b8",
                                 progress_color="#38bdf8")
    switch_audio.pack(anchor="w", pady=(0, 24))

    btns = ctk.CTkFrame(inner, fg_color="transparent")
    btns.pack(fill="x")

    def open_report():
        import generate_report as gr
        data = gr.get_data(config.CURRENT_USER_ID, config.CURRENT_USERNAME)
        path = gr.generate_html(data, config.CURRENT_USERNAME if config.CURRENT_USERNAME else 'Todos')
        webbrowser.open(f"file://{path}")
        
    def delete_account():
        win = ctk.CTkToplevel(root)
        win.title("Atenção")
        win.geometry("400x200")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.after(150, win.grab_set)
        ctk.CTkLabel(win, text="Tem certeza que deseja excluir permanentemente sua conta e histórico?",
                     wraplength=350, font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#ef4444").pack(pady=(30, 20))
        
        def confirm():
            if config.CURRENT_USER_ID:
                db.delete_user(config.CURRENT_USER_ID)
            sys.exit(0)
            
        f = ctk.CTkFrame(win, fg_color="transparent")
        f.pack()
        ctk.CTkButton(f, text="Cancelar", command=win.destroy, fg_color="#64748b", hover_color="#475569").pack(side="left", padx=10)
        ctk.CTkButton(f, text="Sim, Excluir", command=confirm, fg_color="#ef4444", hover_color="#dc2626").pack(side="left", padx=10)

    ctk.CTkButton(btns, text="Ver Relatorio", fg_color="#10b981", hover_color="#059669", text_color="#ffffff",
                  command=lambda: threading.Thread(target=open_report, daemon=True).start(),
                  width=150, height=42, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
                  
    ctk.CTkButton(btns, text="Excluir Conta", fg_color="#ef4444", hover_color="#dc2626", text_color="#ffffff",
                  command=delete_account,
                  width=120, height=42, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=(10, 0))
                  
    ctk.CTkButton(btns, text="Como Usar?", fg_color="#38bdf8", hover_color="#0ea5e9", text_color="#0f172a",
                  command=show_tutorial,
                  width=150, height=42, font=ctk.CTkFont(size=14, weight="bold")).pack(side="right")
                  
    ctk.CTkButton(btns, text="Iniciar Avaliação", fg_color="#1d4ed8", hover_color="#2563eb",
                  command=apply_settings,
                  width=240, height=42, font=ctk.CTkFont(size=15, weight="bold")).pack(side="right", padx=(0, 16))

    root.mainloop()
