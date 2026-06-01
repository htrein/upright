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
    suffix_map = {
        True:  ["Ubuntu-B.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"],
        False: ["Ubuntu-R.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
    }
    dirs = [
        "/usr/share/fonts/truetype/ubuntu",
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts/truetype/dejavu",
    ]
    for d, name in zip(dirs, suffix_map[bold]):
        path = os.path.join(d, name)
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

def _rounded_rect(draw, xy, radius, fill):
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
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

    f_sm = _get_font(11)
    f_md = _get_font(13)
    f_bd = _get_font(13, bold=True)
    
    cy_top  = 12
    cy_text = 40
    cy_bar  = 62

    x = PAD
    d.text((x, cy_top), "UPRIGHT", font=f_bd,  fill=(56, 189, 248, 255))
    x += d.textlength("UPRIGHT", font=f_bd) + 8
    u_txt = f"| {config.CURRENT_USERNAME}"
    d.text((x, cy_top + 2), u_txt, font=f_sm, fill=(100, 120, 150, 255))
    x += d.textlength(u_txt, font=f_sm) + 8
    r_txt = f"[{config.CURRENT_RIGIDITY}]"
    d.text((x, cy_top + 2), r_txt, font=f_sm, fill=(71, 85, 105, 200))

    rx = fw - PAD
    s_txt = "[S] Config"
    stw = d.textlength(s_txt, font=f_sm)
    d.text((rx - stw, cy_top + 2), s_txt, font=f_sm, fill=(71, 85, 105, 190))
    rx -= stw + 14
    if config.IS_PAUSED:
        p_txt = "|| PAUSADO  "
        ptw   = d.textlength(p_txt, font=f_sm)
        d.text((rx - ptw, cy_top + 2), p_txt, font=f_sm, fill=(0, 160, 255, 255))

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
    fh, fw = frame.shape[:2]
    pil_f = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay_c = Image.new("RGBA", pil_f.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(overlay_c)
    band_h = 72
    band_y0 = fh - band_h
    dc.rectangle([0, band_y0, fw, fh], fill=(8, 14, 35, 215))
    dc.rectangle([0, band_y0, fw, band_y0 + 2], fill=(56, 189, 248, 200))
    pil_f = Image.alpha_composite(pil_f, overlay_c)
    dc2 = ImageDraw.Draw(pil_f)
    f_calib_title = _get_font(22, bold=True)
    f_calib_sub = _get_font(14)
    title = "MODO DE CALIBRACAO"
    sub = "Sente-se com a postura ideal e pressione  [ C ]"
    tw_t = dc2.textlength(title, font=f_calib_title)
    tw_s = dc2.textlength(sub, font=f_calib_sub)
    dc2.text(((fw - tw_t) // 2, band_y0 + 8), title, font=f_calib_title, fill=(56, 189, 248, 255))
    dc2.text(((fw - tw_s) // 2, band_y0 + 38), sub, font=f_calib_sub, fill=(200, 215, 235, 255))
    return cv2.cvtColor(np.array(pil_f.convert("RGB")), cv2.COLOR_RGB2BGR)
