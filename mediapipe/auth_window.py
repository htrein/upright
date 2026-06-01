"""
auth_window.py — Tela de Login/Cadastro (CustomTkinter) para o Upright.
Retorna user_id (int) após autenticação bem-sucedida.
"""
import customtkinter as ctk
import db


def show_auth_window() -> int:
    """Exibe a janela de autenticação e retorna o user_id do usuário logado."""

    result = {"user_id": None, "username": None}

    # ── helpers ──────────────────────────────────────────────────────────────
    def _set_status(label: ctk.CTkLabel, msg: str, color: str = "#ef4444"):
        label.configure(text=msg, text_color=color)

    def _do_login():
        username = entry_l_user.get().strip()
        password = entry_l_pass.get()
        if not username or not password:
            _set_status(lbl_l_status, "Preencha todos os campos.")
            return
        uid = db.login_user(username, password)
        if uid is None:
            _set_status(lbl_l_status, "Usuario ou senha incorretos.")
            return
        result["user_id"]  = uid
        result["username"] = username
        root.destroy()

    def _do_register():
        username = entry_r_user.get().strip()
        password = entry_r_pass.get()
        confirm  = entry_r_conf.get()
        if not username or not password or not confirm:
            _set_status(lbl_r_status, "Preencha todos os campos.")
            return
        if len(username) < 3:
            _set_status(lbl_r_status, "Nome deve ter ao menos 3 caracteres.")
            return
        if len(password) < 4:
            _set_status(lbl_r_status, "Senha deve ter ao menos 4 caracteres.")
            return
        if password != confirm:
            _set_status(lbl_r_status, "As senhas nao coincidem.")
            return
        uid = db.register_user(username, password)
        if uid is None:
            _set_status(lbl_r_status, "Nome de usuario ja existe.")
            return
        result["user_id"]  = uid
        result["username"] = username
        root.destroy()

    # ── janela ───────────────────────────────────────────────────────────────
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Upright — Acesso")
    root.resizable(False, False)

    W, H = 480, 560
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw - W)//2}+{(sh - H)//2}")

    # Header
    hdr = ctk.CTkFrame(root, fg_color=("#0f172a", "#0f172a"), corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(hdr, text="UPRIGHT",
                 font=ctk.CTkFont(size=36, weight="bold"),
                 text_color="#38bdf8").pack(pady=(22, 4))
    ctk.CTkLabel(hdr, text="Monitor de Postura em Tempo Real",
                 font=ctk.CTkFont(size=14),
                 text_color="#64748b").pack(pady=(0, 18))

    # TabView
    tabs = ctk.CTkTabview(root, width=W - 40, height=H - 175,
                          fg_color="#1e293b",
                          segmented_button_fg_color="#0f172a",
                          segmented_button_selected_color="#1d4ed8",
                          segmented_button_selected_hover_color="#2563eb",
                          segmented_button_unselected_color="#0f172a",
                          segmented_button_unselected_hover_color="#1e3a5f",
                          text_color="#f1f5f9",
                          text_color_disabled="#64748b")
    tabs.pack(padx=20, pady=(16, 0), fill="both", expand=True)
    tabs.add("Entrar")
    tabs.add("Criar Conta")
    tabs._segmented_button.configure(font=ctk.CTkFont(size=14, weight="bold"))

    # ── Aba Login ────────────────────────────────────────────────────────────
    lf = tabs.tab("Entrar")

    ctk.CTkLabel(lf, text="Nome de usuario",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", padx=4, pady=(20, 4))
    entry_l_user = ctk.CTkEntry(lf, height=40, placeholder_text="seu_usuario",
                                font=ctk.CTkFont(size=14),
                                fg_color="#0f172a", border_color="#334155")
    entry_l_user.pack(fill="x", padx=4)

    ctk.CTkLabel(lf, text="Senha",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", padx=4, pady=(14, 4))
    entry_l_pass = ctk.CTkEntry(lf, height=40, show="*",
                                placeholder_text="••••••••",
                                font=ctk.CTkFont(size=14),
                                fg_color="#0f172a", border_color="#334155")
    entry_l_pass.pack(fill="x", padx=4)
    entry_l_pass.bind("<Return>", lambda e: _do_login())

    lbl_l_status = ctk.CTkLabel(lf, text="", font=ctk.CTkFont(size=12),
                                 text_color="#ef4444")
    lbl_l_status.pack(pady=(10, 0))

    ctk.CTkButton(lf, text="Entrar", command=_do_login,
                  height=44, font=ctk.CTkFont(size=15, weight="bold"),
                  fg_color="#1d4ed8", hover_color="#2563eb").pack(
        fill="x", padx=4, pady=(12, 0))

    # ── Aba Cadastro ─────────────────────────────────────────────────────────
    rf = tabs.tab("Criar Conta")

    ctk.CTkLabel(rf, text="Nome de usuario",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", padx=4, pady=(16, 4))
    entry_r_user = ctk.CTkEntry(rf, height=40, placeholder_text="escolha um nome",
                                font=ctk.CTkFont(size=14),
                                fg_color="#0f172a", border_color="#334155")
    entry_r_user.pack(fill="x", padx=4)

    ctk.CTkLabel(rf, text="Senha",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", padx=4, pady=(12, 4))
    entry_r_pass = ctk.CTkEntry(rf, height=40, show="*",
                                placeholder_text="minimo 4 caracteres",
                                font=ctk.CTkFont(size=14),
                                fg_color="#0f172a", border_color="#334155")
    entry_r_pass.pack(fill="x", padx=4)

    ctk.CTkLabel(rf, text="Confirmar senha",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", padx=4, pady=(12, 4))
    entry_r_conf = ctk.CTkEntry(rf, height=40, show="*",
                                placeholder_text="repita a senha",
                                font=ctk.CTkFont(size=14),
                                fg_color="#0f172a", border_color="#334155")
    entry_r_conf.pack(fill="x", padx=4)
    entry_r_conf.bind("<Return>", lambda e: _do_register())

    lbl_r_status = ctk.CTkLabel(rf, text="", font=ctk.CTkFont(size=12),
                                 text_color="#ef4444")
    lbl_r_status.pack(pady=(8, 0))

    ctk.CTkButton(rf, text="Criar Conta", command=_do_register,
                  height=44, font=ctk.CTkFont(size=15, weight="bold"),
                  fg_color="#1d4ed8", hover_color="#2563eb").pack(
        fill="x", padx=4, pady=(10, 0))

    root.mainloop()
    return result["user_id"], result.get("username", "")
