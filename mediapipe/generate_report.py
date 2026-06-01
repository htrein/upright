import sqlite3
import os
import sys
import json
import csv
import webbrowser
from datetime import datetime

DB_PATH     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'posture_history.db')
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report.html')


def get_users():
    """Retorna lista de (id, username) cadastrados."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT id, username FROM users ORDER BY username').fetchall()
    conn.close()
    return rows


def get_data(user_id=None):
    """
    Coleta dados de postura do banco.
    Se user_id for informado, filtra apenas as sessões daquele usuário.
    """
    if not os.path.exists(DB_PATH):
        return None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Filtro de user_id
    user_filter      = "AND s.user_id = ?" if user_id else ""
    user_filter_args = (user_id,)          if user_id else ()

    # Resumo de sessões
    cursor.execute(f'''
        SELECT s.id, s.start_time, s.end_time
        FROM sessions s
        WHERE 1=1 {user_filter}
        ORDER BY s.start_time ASC
    ''', user_filter_args)
    sessions = cursor.fetchall()

    # Evolução histórica (média por minuto)
    cursor.execute(f'''
        SELECT
            strftime('%Y-%m-%d %H:%M', pl.timestamp) AS minute,
            AVG(pl.global_score),
            AVG(pl.shoulder_score),
            AVG(pl.neck_score),
            SUM(pl.is_bad_posture),
            COUNT(*)
        FROM posture_logs pl
        JOIN sessions s ON pl.session_id = s.id
        WHERE 1=1 {user_filter}
        GROUP BY minute
        ORDER BY minute ASC
    ''', user_filter_args)
    daily_stats = cursor.fetchall()

    # % má postura total
    cursor.execute(f'''
        SELECT COUNT(*), SUM(pl.is_bad_posture)
        FROM posture_logs pl
        JOIN sessions s ON pl.session_id = s.id
        WHERE 1=1 {user_filter}
    ''', user_filter_args)
    total_logs, total_bad = cursor.fetchone()

    conn.close()

    if not daily_stats or not total_logs:
        return None

    pct_bad            = (total_bad / total_logs) * 100
    avg_global_overall = sum(r[1] for r in daily_stats) / len(daily_stats)

    # Pegada de Carbono (CodeCarbon)
    carbon_data = None
    csv_path = os.path.join(os.path.dirname(DB_PATH), 'emissions.csv')
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_duration, total_emissions, total_energy = 0.0, 0.0, 0.0
                for row in reader:
                    total_duration  += float(row.get('duration', 0))
                    total_emissions += float(row.get('emissions', 0))
                    total_energy    += float(row.get('energy_consumed', 0))
                
                # Conversões mais legíveis (mg de CO2, Wh de energia)
                emissions_mg = total_emissions * 1_000_000
                energy_wh = total_energy * 1000
                
                # Equivalência inteligente
                # Carregar um smartphone = ~8 Wh
                smartphones = energy_wh / 8.0
                
                carbon_data = {
                    'emissions_mg': round(emissions_mg, 2),
                    'energy_wh': round(energy_wh, 2),
                    'smartphones': round(smartphones, 1)
                }
        except Exception as e:
            print(f"Erro lendo emissions.csv: {e}")

    return {
        'total_sessions': len(sessions),
        'pct_bad':        round(pct_bad, 1),
        'avg_score':      round(avg_global_overall * 100, 1),
        'chart_data': {
            'labels':   [r[0] for r in daily_stats],
            'global':   [round(r[1] * 100, 2) for r in daily_stats],
            'shoulder': [round(r[2] * 100, 2) for r in daily_stats],
            'neck':     [round(r[3] * 100, 2) for r in daily_stats],
        },
        'carbon_data': carbon_data
    }


def generate_html(data, username: str = "Todos"):
    chart_json = json.dumps(data['chart_data']) if data else "{}"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upright - Posture Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg:      #0f172a;
            --glass:   rgba(30,41,59,0.7);
            --border:  rgba(255,255,255,0.1);
            --txt:     #f8fafc;
            --muted:   #94a3b8;
            --a1:      #38bdf8;
            --a2:      #818cf8;
            --a3:      #c084fc;
            --danger:  #fb7185;
            --success: #34d399;
        }}
        * {{ margin:0; padding:0; box-sizing:border-box; font-family:'Outfit',sans-serif; }}
        body {{
            background: var(--bg);
            background-image:
                radial-gradient(at 0% 0%,   rgba(56,189,248,.15) 0, transparent 50%),
                radial-gradient(at 100% 100%,rgba(192,132,252,.15) 0, transparent 50%);
            color: var(--txt);
            min-height: 100vh;
            padding: 2rem;
            display: flex; flex-direction: column; align-items: center;
        }}
        .container {{ max-width:1200px; width:100%; }}
        header {{ text-align:center; margin-bottom:3rem; animation:fadeInDown .8s ease-out; }}
        h1 {{
            font-size:3rem; font-weight:800;
            background:linear-gradient(to right,var(--a1),var(--a3));
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;
            margin-bottom:.25rem;
        }}
        .user-badge {{
            display:inline-block;
            background:rgba(56,189,248,.15);
            border:1px solid rgba(56,189,248,.3);
            color:var(--a1);
            font-size:.95rem;
            padding:.3rem .9rem;
            border-radius:999px;
            margin-top:.5rem;
        }}
        header p {{ color:var(--muted); font-size:1.1rem; margin-top:.4rem; }}
        .glass-card {{
            background:var(--glass);
            backdrop-filter:blur(12px);
            border:1px solid var(--border);
            border-radius:24px;
            padding:2rem;
            box-shadow:0 4px 30px rgba(0,0,0,.1);
            transition:transform .3s ease, box-shadow .3s ease;
        }}
        .glass-card:hover {{ transform:translateY(-5px); box-shadow:0 10px 40px rgba(0,0,0,.2); }}
        .metrics-grid {{
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
            gap:2rem; margin-bottom:3rem;
            animation:fadeInUp .8s ease-out .2s both;
        }}
        .metric {{ text-align:center; }}
        .metric h3 {{ color:var(--muted); font-size:1rem; font-weight:400; margin-bottom:1rem; text-transform:uppercase; letter-spacing:2px; }}
        .metric .value {{ font-size:3.5rem; font-weight:800; line-height:1; }}
        .metric .value.good  {{ color:var(--success); }}
        .metric .value.bad   {{ color:var(--danger); }}
        .metric .value.neutral {{ color:var(--a1); }}
        .charts-section {{ animation:fadeInUp .8s ease-out .4s both; }}
        .chart-container {{ position:relative; height:400px; width:100%; }}
        .no-data {{ text-align:center; font-size:1.5rem; color:var(--muted); padding:5rem 0; }}
        .download-btn {{
            background:linear-gradient(135deg,var(--a1),var(--a2));
            color:#fff; border:none;
            padding:.8rem 1.5rem; border-radius:12px;
            font-size:1rem; font-weight:600; cursor:pointer;
            transition:all .3s ease;
            box-shadow:0 4px 15px rgba(56,189,248,.3);
            margin-top:1rem;
            display:inline-flex; align-items:center; gap:.5rem;
        }}
        .download-btn:hover {{ transform:translateY(-2px); box-shadow:0 6px 20px rgba(56,189,248,.4); }}
        @keyframes fadeInDown {{ from{{opacity:0;transform:translateY(-30px)}} to{{opacity:1;transform:translateY(0)}} }}
        @keyframes fadeInUp   {{ from{{opacity:0;transform:translateY(30px)}}  to{{opacity:1;transform:translateY(0)}} }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>Upright Dashboard</h1>
        <div class="user-badge">Usuario: {username}</div>
        <p>Historico detalhado de saude postural</p>
        <button class="download-btn" onclick="downloadCSV()">
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            Baixar Relatorio (CSV)
        </button>
    </header>
"""

    content_html = ""
    if data:
        # Pega as métricas normais
        content_html += f'''
        <div class="metrics-grid">
            <div class="glass-card metric">
                <h3>Score Global Medio</h3>
                <div class="value {'good' if data['avg_score'] >= 50 else 'bad'}">{data['avg_score']}%</div>
            </div>
            <div class="glass-card metric">
                <h3>Tempo em Ma Postura</h3>
                <div class="value {'bad' if data['pct_bad'] >= 30 else 'good'}">{data['pct_bad']}%</div>
            </div>
            <div class="glass-card metric">
                <h3>Total de Sessoes</h3>
                <div class="value neutral">{data['total_sessions']}</div>
            </div>
        </div>
        <div class="glass-card charts-section">
            <h3 style="color:var(--muted);margin-bottom:1.5rem;text-align:center;
                       font-weight:400;text-transform:uppercase;letter-spacing:2px;">
                Evolucao Historica
            </h3>
            <div class="chart-container"><canvas id="postureChart"></canvas></div>
        </div>
        '''

        # Pega as métricas do CodeCarbon se existirem
        if data.get('carbon_data'):
            cdata = data['carbon_data']
            content_html += f'''
            <div class="glass-card" style="margin-top:2rem; animation:fadeInUp .8s ease-out .6s both; border-color: rgba(52, 211, 153, 0.3);">
                <h3 style="color:var(--success);margin-bottom:1rem;text-align:center;
                           font-weight:600;text-transform:uppercase;letter-spacing:2px; display:flex; justify-content:center; align-items:center; gap:10px;">
                    <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Pegada Ecologica do Sistema
                </h3>
                <div style="display:flex; justify-content:space-around; flex-wrap:wrap; gap:1rem; text-align:center;">
                    <div>
                        <p style="color:var(--muted); font-size:0.9rem; margin-bottom:0.5rem; text-transform:uppercase; letter-spacing:1px;">Emissão Estimada (CO₂)</p>
                        <p style="font-size:2.5rem; font-weight:800; color:var(--txt); line-height:1;">{cdata['emissions_mg']} <span style="font-size:1.2rem; color:var(--muted);">mg</span></p>
                    </div>
                    <div>
                        <p style="color:var(--muted); font-size:0.9rem; margin-bottom:0.5rem; text-transform:uppercase; letter-spacing:1px;">Energia Consumida</p>
                        <p style="font-size:2.5rem; font-weight:800; color:var(--txt); line-height:1;">{cdata['energy_wh']} <span style="font-size:1.2rem; color:var(--muted);">Wh</span></p>
                    </div>

                    <div>
                        <p style="color:var(--muted); font-size:0.9rem; margin-bottom:0.5rem; text-transform:uppercase; letter-spacing:1px;">Equivalencia Inteligente</p>
                        <p style="font-size:2.5rem; font-weight:800; color:var(--success); line-height:1;">{cdata['smartphones']} <span style="font-size:1.2rem; color:var(--muted);">Cargas 📱</span></p>
                        <p style="font-size:0.8rem; color:var(--muted); margin-top:0.3rem;">(equiv. a carregar o celular)</p>
                    </div>
                </div>
                <div style="text-align:right; margin-top:1.5rem;">
                    <a href="https://codecarbon.io/" target="_blank" style="color:rgba(148, 163, 184, 0.6); font-size:0.75rem; text-decoration:none; transition:color 0.3s;" onmouseover="this.style.color='rgba(148, 163, 184, 1)'" onmouseout="this.style.color='rgba(148, 163, 184, 0.6)'">
                        Métricas estimadas via CodeCarbon
                    </a>
                </div>
            </div>
            '''
    else:
        content_html = '''
        <div class="glass-card">
            <div class="no-data">
                Nenhum dado encontrado para este usuario.<br>
                <span style="font-size:1rem;margin-top:10px;display:block;">
                    Use o Upright por alguns minutos para gerar relatorios.
                </span>
            </div>
        </div>
        '''

    html += content_html + "\n</div>"

    html += f"""
<script>
const data = {chart_json};
function downloadCSV() {{
    if (!data.labels || data.labels.length === 0) {{ alert('Sem dados.'); return; }}
    const rows = ['Horario,Score Global (%),Score Ombros (%),Score Pescoco (%)'];
    for (let i = 0; i < data.labels.length; i++)
        rows.push(data.labels[i]+','+data.global[i]+','+data.shoulder[i]+','+data.neck[i]);
    const blob = new Blob([rows.join('\\n')], {{type:'text/csv'}});
    const a    = Object.assign(document.createElement('a'), {{
        href:     URL.createObjectURL(blob),
        download: 'upright_historico.csv'
    }});
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}}
if (Object.keys(data).length > 0) {{
    const ctx = document.getElementById('postureChart').getContext('2d');
    const g   = ctx.createLinearGradient(0,0,0,400);
    g.addColorStop(0,'rgba(56,189,248,.5)'); g.addColorStop(1,'rgba(56,189,248,0)');
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = 'Outfit';
    new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: data.labels,
            datasets: [
                {{ label:'Score Global (%)', data:data.global,
                   borderColor:'#38bdf8', backgroundColor:g,
                   borderWidth:3, tension:.4, fill:true,
                   pointBackgroundColor:'#0f172a', pointBorderColor:'#38bdf8',
                   pointBorderWidth:2, pointRadius:4, pointHoverRadius:6 }},
                {{ label:'Score Ombros (%)', data:data.shoulder,
                   borderColor:'#818cf8', borderWidth:2, borderDash:[5,5],
                   tension:.4, pointRadius:0, pointHoverRadius:4 }},
                {{ label:'Score Pescoco (%)', data:data.neck,
                   borderColor:'#c084fc', borderWidth:2, borderDash:[5,5],
                   tension:.4, pointRadius:0, pointHoverRadius:4 }}
            ]
        }},
        options: {{
            responsive:true, maintainAspectRatio:false,
            plugins: {{
                legend: {{ position:'top', labels:{{ usePointStyle:true, padding:20, font:{{size:14}} }} }},
                tooltip: {{
                    backgroundColor:'rgba(15,23,42,.9)',
                    titleFont:{{size:16,family:'Outfit',weight:'bold'}},
                    bodyFont:{{size:14,family:'Outfit'}},
                    padding:15, borderColor:'rgba(255,255,255,.1)', borderWidth:1,
                    displayColors:true, boxPadding:6
                }}
            }},
            scales: {{
                y: {{ beginAtZero:true, max:100,
                      grid:{{color:'rgba(255,255,255,.05)',drawBorder:false}} }},
                x: {{ grid:{{display:false,drawBorder:false}} }}
            }},
            interaction: {{ mode:'index', intersect:false }}
        }}
    }});
}}
</script>
</body>
</html>"""

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Relatorio gerado: {REPORT_PATH}")
    return REPORT_PATH


def pick_user():
    """Janela simples CTk para escolher o usuário cujo relatório será gerado."""
    import customtkinter as ctk

    users = get_users()
    if not users:
        print("Nenhum usuario cadastrado.")
        return None, "Todos"

    result = {"id": None, "name": "Todos"}

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.title("Upright — Relatorio")
    root.resizable(False, False)
    W, H = 420, 300
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

    hdr = ctk.CTkFrame(root, fg_color="#0f172a", corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(hdr, text="Upright — Relatorio",
                 font=ctk.CTkFont(size=22, weight="bold"),
                 text_color="#38bdf8").pack(pady=18)

    body = ctk.CTkFrame(root, fg_color="#1e293b", corner_radius=0)
    body.pack(fill="both", expand=True, padx=0)
    inner = ctk.CTkFrame(body, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=28, pady=20)

    ctk.CTkLabel(inner, text="Selecione o usuario:",
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color="#94a3b8").pack(anchor="w", pady=(0, 8))

    names = ["Todos os usuarios"] + [u[1] for u in users]
    opt = ctk.CTkOptionMenu(inner, values=names, height=40,
                            fg_color="#0f172a", button_color="#1d4ed8",
                            button_hover_color="#2563eb",
                            font=ctk.CTkFont(size=14),
                            dropdown_font=ctk.CTkFont(size=14))
    opt.set(names[0])
    opt.pack(fill="x", pady=(0, 20))

    def _go():
        sel = opt.get()
        if sel == "Todos os usuarios":
            result["id"]   = None
            result["name"] = "Todos"
        else:
            for uid, uname in users:
                if uname == sel:
                    result["id"]   = uid
                    result["name"] = uname
                    break
        root.destroy()

    ctk.CTkButton(inner, text="Gerar Relatorio", command=_go,
                  height=42, fg_color="#1d4ed8", hover_color="#2563eb",
                  font=ctk.CTkFont(size=14, weight="bold")).pack(fill="x")

    root.mainloop()
    return result["id"], result["name"]


if __name__ == "__main__":
    print("Selecione o usuario para o relatorio...")
    user_id, username = pick_user()
    if user_id is not None or username == "Todos":
        print(f"Coletando dados para: {username}")
        data = get_data(user_id)
        report_file = generate_html(data, username)
        print("Abrindo no navegador...")
        webbrowser.open(f"file://{report_file}")
