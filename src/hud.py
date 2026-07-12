import cv2
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFont
import config

_font_cache = {}

def _get_font(size: int, bold: bool = False):
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    import platform
    _os = platform.system()

    if _os == 'Windows':
        # Fontes disponíveis nativamente no Windows
        candidates = [
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts',
                         'arialbd.ttf' if bold else 'arial.ttf'),
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts',
                         'calibrib.ttf' if bold else 'calibri.ttf'),
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts',
                         'segoeuib.ttf' if bold else 'segoeui.ttf'),
        ]
    else:
        # Linux / macOS
        suffix_map = {
            True:  ["Ubuntu-B.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"],
            False: ["Ubuntu-R.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
        }
        dirs = [
            "/usr/share/fonts/truetype/ubuntu",
            "/usr/share/fonts/truetype/liberation",
            "/usr/share/fonts/truetype/dejavu",
        ]
        candidates = [os.path.join(d, n) for d, n in zip(dirs, suffix_map[bold])]

    for path in candidates:
        if os.path.exists(path):
            font = ImageFont.truetype(path, size)
            _font_cache[key] = font
            return font

    font = ImageFont.load_default()
    _font_cache[key] = font
    return font

def _score_color_rgba(score: float) -> tuple:
    score = max(0.0, min(1.0, score))
    if score >= 0.5:
        t = (score - 0.5) * 2.0
        r, g, b = int((1 - t) * 255), 220, 0
    else:
        t = score * 2.0
        r, g, b = 255, int(t * 200), 0
    return (r, g, b, 255)

def _rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    except AttributeError:
        x0, y0, x1, y1 = xy
        draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
        draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
        draw.ellipse([x0, y0, x0 + 2*radius, y0 + 2*radius], fill=fill)
        draw.ellipse([x1 - 2*radius, y0, x1, y0 + 2*radius], fill=fill)
        draw.ellipse([x0, y1 - 2*radius, x0 + 2*radius, y1], fill=fill)
        draw.ellipse([x1 - 2*radius, y1 - 2*radius, x1, y1], fill=fill)

STRIP_H = 90  

def draw_hud_strip(frame, posture, global_score, pct_bad):
    fh, fw = frame.shape[:2]
    PAD = 14
    label_map = {'shoulder': 'Ombros', 'neck': 'Pescoco', 'head': 'Cabeca'}

    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    strip   = Image.new("RGBA", (fw, STRIP_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)

    d.rectangle([0, 0, fw, STRIP_H],          fill=(8, 14, 35, 215))
    d.rectangle([0, STRIP_H - 2, fw, STRIP_H], fill=(56, 189, 248, 180))

    f_sm = _get_font(12)
    f_md = _get_font(13)
    f_bd = _get_font(13, bold=True)
    f_title = _get_font(24, bold=True)
    
    cy_top  = 12
    cy_text = 40
    cy_bar  = 62

    x = PAD
    d.text((x, cy_top - 4), "UPRIGHT", font=f_title,  fill=(56, 189, 248, 255))
    x += d.textlength("UPRIGHT", font=f_title) + 12
    u_txt = f"{config.CURRENT_USERNAME}"
    d.text((x, cy_top + 6), u_txt, font=f_sm, fill=(100, 120, 150, 255))

    rx = fw - PAD
    
    options = [
        ("[S]", "Config"),
        ("[R]", "Relatório"),
        ("[Espaco]", "Retomar" if config.IS_PAUSED else "Pausar"),
        ("[P]", "Filtro ON" if config.PRIVACY_MODE else "Filtro OFF"),
    ]
    if config.PRIVACY_MODE:
        options.append(("[M]", config.PRIVACY_STYLE.title()))
        
    options.append(("[F]", "Tela Normal" if config.get_ema('is_fullscreen', 1.0) == 1.0 else "Tela Cheia"))
    options.append(("[Q] / [ESC]", "Sair"))

    for key_txt, val_txt in options:
        kw = d.textlength(key_txt, font=f_bd)
        vw = d.textlength(val_txt, font=f_sm)
        total_w = kw + vw + 8 + 16 # padding
        
        if val_txt == "Sair":
            _rounded_rect(d, [rx - total_w, cy_top - 4, rx, cy_top + 18], 4, (30, 41, 59, 200), outline=(239, 68, 68, 255), width=1)
            d.text((rx - total_w + 8, cy_top - 1), key_txt, font=f_bd, fill=(239, 68, 68, 255))
        else:
            _rounded_rect(d, [rx - total_w, cy_top - 4, rx, cy_top + 18], 4, (30, 41, 59, 200))
            d.text((rx - total_w + 8, cy_top - 1), key_txt, font=f_bd, fill=(56, 189, 248, 255))
            
        d.text((rx - total_w + 8 + kw + 8, cy_top + 1), val_txt, font=f_sm, fill=(200, 215, 235, 255))
        
        rx -= total_w + 8 # gap entre os chips

    pieces = []
    for key, (_, _, score, _) in posture.items():
        pieces.append((label_map.get(key, key), score))
    pieces.append(("Global", global_score))

    block_w = 110 
    gap = 25
    total_w = len(pieces) * block_w + (len(pieces) - 1) * gap
    
    mx = max(int((fw - total_w) / 2), x + 20)
    
    for label, score in pieces:
        clr = _score_color_rgba(score)
        
        d.text((mx, cy_text), label, font=f_md, fill=(180, 195, 215, 255))
        pct_txt = f"{score*100:.0f}%"
        tw = d.textlength(pct_txt, font=f_md)
        d.text((mx + block_w - tw, cy_text), pct_txt, font=f_md, fill=clr)
        
        bar_h = 7
        _rounded_rect(d, [mx, cy_bar, mx + block_w, cy_bar + bar_h], 3, (35, 48, 70, 220))
        filled = max(2, int(block_w * score))
        _rounded_rect(d, [mx, cy_bar, mx + filled, cy_bar + bar_h], 3, clr)
        
        mx += block_w + gap

    pil_img.paste(strip, (0, 0), strip)
    return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)

def draw_calibration_hud(frame):
    altura_tela, largura_tela = frame.shape[:2]
    imagem_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    camada_fundo = Image.new("RGBA", imagem_pil.size, (0, 0, 0, 0))
    desenho_camada = ImageDraw.Draw(camada_fundo)
    band_h = 72
    band_y0 = altura_tela - band_h
    desenho_camada.rectangle([0, band_y0, largura_tela, altura_tela], fill=(8, 14, 35, 215))
    desenho_camada.rectangle([0, band_y0, largura_tela, band_y0 + 2], fill=(56, 189, 248, 200))
    imagem_pil = Image.alpha_composite(imagem_pil, camada_fundo)
    desenho = ImageDraw.Draw(imagem_pil)
    f_calib_title = _get_font(22, bold=True)
    f_calib_sub = _get_font(14)
    title = "MODO DE CALIBRACAO"
    sub = "Postura ideal: [ C ] Calibrar  |  [ ESC ] ou [ Q ] Sair"
    tw_t = desenho.textlength(title, font=f_calib_title)
    tw_s = desenho.textlength(sub, font=f_calib_sub)
    desenho.text(((largura_tela - tw_t) // 2, band_y0 + 8), title, font=f_calib_title, fill=(56, 189, 248, 255))
    desenho.text(((largura_tela - tw_s) // 2, band_y0 + 38), sub, font=f_calib_sub, fill=(200, 215, 235, 255))
    return cv2.cvtColor(np.array(imagem_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
