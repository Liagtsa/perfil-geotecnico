# ==============================================================================
# MODULO: generador_memoria_sict.py
# VERSION: 1.0.0-SICT-AASHTO-MEMORIA-ANEXO
# DESCRIPCION:
#   Generador ejecutivo en PDF de la Memoria de Calculo Geotecnica para Puentes,
#   Pasos Superiores/Inferiores (PFFCC, PSV, PIV) y Viaductos bajo normativa
#   SICT (TdR Etapa V y VI) y AASHTO, incluyendo la Cedula Oficial "ANEXO
#   ESTUDIO DE CIMENTACION" lista para firma del Responsable Tecnico.
# ==============================================================================

import io
import os
import math
import textwrap
import datetime
import urllib.request
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image

try:
    import requests
except ImportError:
    requests = None


# ==========================================================
# 0. UTILIDAD DE CARGA DE LOGOTIPO (URL REMOTA O LOCAL)
# ==========================================================
_CACHE_LOGOS_SICT = {}

def _normalizar_url_imagen(url):
    u = url.strip()
    if 'drive.google.com' in u:
        if '/file/d/' in u:
            file_id = u.split('/file/d/')[1].split('/')[0].split('?')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        if 'id=' in u:
            file_id = u.split('id=')[1].split('&')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    if 'dropbox.com' in u:
        if '?dl=0' in u:
            return u.replace('?dl=0', '?raw=1')
        if '&dl=0' in u:
            return u.replace('&dl=0', '&raw=1')
    if 'github.com/' in u and '/blob/' in u:
        return u.replace('github.com/', 'raw.githubusercontent.com/').replace('/blob/', '/')
    return u


def cargar_imagen_logo_sict(logo_source):
    key = str(logo_source).strip() if (logo_source is not None and not pd.isna(logo_source)) else ''
    if key.lower() in ('', 'nan', 'none', 'null'):
        key = 'logo_empresa.png'
    if key in _CACHE_LOGOS_SICT:
        return _CACHE_LOGOS_SICT[key]

    candidatos = [key]
    if key != 'logo_empresa.png':
        candidatos.append('logo_empresa.png')

    headers_http = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for src in candidatos:
        if not src:
            continue
        if src.lower().startswith(('http://', 'https://')):
            url_directa = _normalizar_url_imagen(src)
            try:
                if requests is not None:
                    resp = requests.get(url_directa, headers=headers_http, timeout=8)
                    resp.raise_for_status()
                    raw_bytes = resp.content
                else:
                    req = urllib.request.Request(url_directa, headers=headers_http)
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        raw_bytes = resp.read()
                arr = np.asarray(Image.open(io.BytesIO(raw_bytes)).convert('RGBA'))
                _CACHE_LOGOS_SICT[key] = arr
                return arr
            except Exception:
                continue

        if os.path.exists(src):
            try:
                arr = np.asarray(Image.open(src).convert('RGBA'))
                _CACHE_LOGOS_SICT[key] = arr
                return arr
            except Exception:
                continue

    _CACHE_LOGOS_SICT[key] = None
    return None


# ==========================================================
# 1. ENCABEZADO Y PIE DE PÁGINA CON ANTEFIRMA (TdR 1.5.12)
# ==========================================================
def crear_encabezado_sict(fig, titulo_pagina, num_pagina, total_paginas,
                          p_proy, p_elem, p_sondeo, p_fecha, logo_url='logo_empresa.png',
                          mostrar_antefirma=True):
    ax_logo = fig.add_axes([0.05, 0.88, 0.22, 0.08])
    ax_logo.axis('off')

    img_arr = cargar_imagen_logo_sict(logo_url)
    if img_arr is not None:
        ax_logo.imshow(img_arr, aspect='equal')
    else:
        ax_logo.text(0.5, 0.5, '[ LOGO EMPRESA ]', ha='center', va='center', fontsize=8, color='navy', weight='bold')

    fig.text(0.30, 0.940, f"PROYECTO: {p_proy[:58]}", fontsize=9.5, weight='bold', color='navy')
    fig.text(0.30, 0.922, f"ESTRUCTURA / CRUCE: {p_elem[:62]}", fontsize=8.3)
    fig.text(0.30, 0.904, f"EXPLORACIÓN: {p_sondeo[:62]}", fontsize=8.3)
    fig.text(0.30, 0.884, f"MEMORIA SICT / AASHTO: {titulo_pagina}", fontsize=7.8, color='dimgray')

    if not p_fecha or str(p_fecha).strip().lower() == 'nan':
        p_fecha = datetime.datetime.now().strftime("%B %Y").upper()
    fig.text(0.95, 0.940, f"FECHA: {p_fecha}", ha='right', fontsize=8.3)
    fig.text(0.95, 0.904, f"PÁGINA: {num_pagina} / {total_paginas}", ha='right', fontsize=8.8, weight='bold')
    fig.lines.append(plt.Line2D([0.05, 0.95], [0.870, 0.870], transform=fig.transFigure, color='black', lw=1.5))

    if mostrar_antefirma:
        fig.lines.append(plt.Line2D([0.05, 0.95], [0.042, 0.042], transform=fig.transFigure, color='gray', lw=0.6))
        fig.text(0.05, 0.024, "NORMATIVA APLICABLE: TdR SICT (Etapa V y VI) | Normas N-PRY-CAR-6-01 | AASHTO Standard / LRFD",
                 fontsize=6.8, color='dimgray')
        fig.text(0.95, 0.024, "ANTEFIRMA RESP. TÉCNICO: ______________________",
                 ha='right', fontsize=6.8, color='black')


# ==========================================================
# 2. ESQUEMAS GRÁFICOS DE INGENIERÍA (DAVISSON Y MONONOBE)
# ==========================================================
def dibujar_esquemas_sict(fig, resultados):
    r_soc = resultados.get('socavacion', {})
    r_dr = resultados.get('davisson_pandeo', {})
    r_emp = resultados.get('empujes_muros', {})

    # Panel Izquierdo: Modelo de Empotramiento y Pandeo (Davisson y Robinson)
    ax1 = fig.add_axes([0.07, 0.44, 0.41, 0.37])
    ax1.set_title("Modelo de Fijación Equivalente y Pandeo\n(Método de Davisson y Robinson, TdR 1.5.8)", fontsize=8.8, weight='bold')

    if r_dr.get('aplica', False):
        D_v = r_dr['D_m']
        L_ent = r_dr['L_enterrada_m']
        z_soc = r_soc.get('soc_total_m', 0.0) if r_soc.get('aplica', False) else 0.0
        L_u = r_dr['L_libre_total_Lu_m']
        L_col = max(0.0, L_u - z_soc)
        zf = r_dr['zf_fijacion_m']

        y_top_col = L_col
        y_bot_pila = -L_ent
        ax1.set_xlim(-4.2, 4.2)
        ax1.set_ylim(y_bot_pila - 2.0, max(y_top_col + 2.5, 3.0))

        ax1.axhline(0.0, color='saddlebrown', lw=1.8)
        ax1.text(3.9, 0.3, "N.T.N. (±0.00 m)", ha='right', fontsize=7.2, color='saddlebrown', weight='bold')

        if r_soc.get('aplica', False) and z_soc > 0.01:
            ax1.axhline(-z_soc, color='dodgerblue', lw=1.3, linestyle='--')
            ax1.text(3.9, -z_soc - 0.5, f"Nivel Socavado (-{z_soc:.2f} m)", ha='right', fontsize=7.0, color='dodgerblue', weight='bold')

        w_vis = max(0.65, min(1.3, D_v))
        rect_pila = patches.Rectangle((-w_vis / 2, y_bot_pila), w_vis, L_ent + L_col,
                                      facecolor='#d9d9d9', edgecolor='black', lw=1.4, zorder=3)
        ax1.add_patch(rect_pila)

        y_fij = -(z_soc + zf)
        ax1.axhline(y_fij, color='crimson', lw=1.3, linestyle='-.')
        ax1.plot([0], [y_fij], marker='s', color='crimson', markersize=6, zorder=5)
        ax1.text(3.9, y_fij + 0.3, f"Fijación Aparente zf ({y_fij:.2f} m)", ha='right', fontsize=7.0, color='crimson', weight='bold')

        x_c = -w_vis / 2 - 0.55
        ax1.annotate('', xy=(x_c, y_top_col), xytext=(x_c, y_fij),
                     arrowprops=dict(arrowstyle='<->', color='navy', lw=1.4))
        ax1.text(x_c - 0.15, (y_top_col + y_fij) / 2.0,
                 f"Lu + zf =\n{(L_u + zf):.2f} m\n(Leq = {r_dr['L_eq_pandeo_m']:.2f} m)",
                 ha='right', va='center', fontsize=7.0, color='navy', weight='bold')

        ax1.annotate('', xy=(0, y_top_col), xytext=(0, y_top_col + 1.6),
                     arrowprops=dict(arrowstyle='->', color='darkred', lw=2.0))
        ax1.text(0.2, y_top_col + 1.0, f"P_act = {r_dr['P_act_ton']:.0f} t\nP_cr = {r_dr['P_cr_euler_ton']:.0f} t",
                 fontsize=7.2, color='darkred', weight='bold')
        ax1.axis('off')
    else:
        ax1.text(0.5, 0.5, "Módulo de Pandeo en Pilas\n(Deshabilitado para este proyecto)",
                 ha='center', va='center', fontsize=8.5, color='gray', style='italic')
        ax1.axis('off')

    # Panel Derecho: Diagrama de Empujes en Estribos / Muros (Rankine + Mononobe-Okabe)
    ax2 = fig.add_axes([0.55, 0.44, 0.39, 0.37])
    ax2.set_title("Diagrama de Empujes en Estribos / Muros\n(Rankine + Sismo Mononobe-Okabe, SICT)", fontsize=8.8, weight='bold')

    if r_emp.get('aplica', False):
        Hm = r_emp['H_muro_m']
        ax2.set_xlim(-2.0, 5.2)
        ax2.set_ylim(-1.0, Hm + 1.5)

        zap_m = patches.Rectangle((-1.2, 0.0), 2.2, 0.6, facecolor='#cccccc', edgecolor='black', lw=1.3)
        vast_m = patches.Rectangle((-0.2, 0.6), 0.55, Hm - 0.6, facecolor='#cccccc', edgecolor='black', lw=1.3)
        ax2.add_patch(zap_m)
        ax2.add_patch(vast_m)

        ax2.plot([0.35, 4.8], [Hm, Hm], color='saddlebrown', lw=1.6)
        ax2.text(2.6, Hm + 0.35, f"Sobrecarga q_sc = {r_emp['q_sobrecarga_kpa']:.1f} kPa", ha='center', fontsize=7.0, color='darkgreen', weight='bold')

        poly_ea = patches.Polygon([[0.6, Hm], [0.6, 0.0], [2.6, 0.0]], closed=True,
                                  facecolor='#d9eaf7', edgecolor='navy', lw=1.2, alpha=0.85)
        ax2.add_patch(poly_ea)
        ax2.text(1.35, Hm * 0.22, f"Ea estático\n{r_emp['Ea_total_estatico_tm']:.2f} t/m", fontsize=7.0, color='navy', weight='bold')

        poly_sis = patches.Polygon([[2.8, Hm], [4.2, Hm], [2.8, 0.0]], closed=True,
                                   facecolor='#fde2e2', edgecolor='crimson', lw=1.2, linestyle='--', alpha=0.85)
        ax2.add_patch(poly_sis)
        ax2.text(3.35, Hm * 0.68, f"ΔE sismo\n+{r_emp['dE_sismo_tm']:.2f} t/m\n(0.6·H)", fontsize=6.8, color='crimson', weight='bold')

        ax2.axhline(0.0, color='black', lw=1.2)
        ax2.axis('off')
    else:
        ax2.text(0.5, 0.5, "Módulo de Empuje de Tierras\n(Deshabilitado para este proyecto)",
                 ha='center', va='center', fontsize=8.5, color='gray', style='italic')
        ax2.axis('off')


# ==========================================================
# 3. PÁGINA OFICIAL: ANEXO ESTUDIO DE CIMENTACIÓN (TdR SICT)
# ==========================================================
def dibujar_pagina_anexo_oficial_sict(fig, num_pag, tot_pags, df_tramos, resultados,
                                      pruebas_det, datos_anexo, logo_url):
    p_proy = datos_anexo.get('Proyecto', 'ESTUDIO GEOTÉCNICO Y DE CIMENTACIÓN')
    p_elem = datos_anexo.get('Tipo_Obra', resultados.get('tipo_cruce', 'ESTRUCTURA DE CRUCE'))
    p_sondeo = datos_anexo.get('Sondeo', 'SONDEO 1')
    p_fecha = datos_anexo.get('Fecha', '')

    crear_encabezado_sict(fig, "ANEXO OFICIAL SICT — RESUMEN DE ESTUDIO DE CIMENTACIÓN",
                          num_pag, tot_pags, p_proy, p_elem, p_sondeo, p_fecha,
                          logo_url=logo_url, mostrar_antefirma=False)

    ax = fig.add_axes([0.05, 0.04, 0.90, 0.81])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 98.0, "A N E X O   —   E S T U D I O   D E   C I M E N T A C I Ó N   ( S I C T )",
            ha='center', va='top', fontsize=9.5, weight='bold', color='navy')
    contrato_str = datos_anexo.get('Contrato', 'S/N')
    ax.text(50, 94.8, f"SEGÚN CONTRATO No.:  {contrato_str}", ha='center', va='top', fontsize=8.2, weight='bold')

    # I. DATOS DE LA OBRA
    ax.add_patch(patches.Rectangle((0, 81.5), 100, 11.2, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 91.0, "I.- DATOS DE LA OBRA", fontsize=8.0, weight='bold', color='navy')
    ax.text(2.0, 88.3, f"Tipo de obra:   {datos_anexo.get('Tipo_Obra', resultados.get('tipo_cruce', 'Puente / Paso Superior'))}", fontsize=7.6)
    ax.text(2.0, 85.8, f"Camino:         {datos_anexo.get('Camino', 'Proyecto Carretero / Ferroviario')}", fontsize=7.6)
    ax.text(2.0, 83.3, f"Tramo / Km:     {datos_anexo.get('Tramo', 'S/D')}     |     Localización: {datos_anexo.get('Localizacion', 'S/D')}", fontsize=7.6)

    # II. EXPLORACIÓN Y MUESTREO
    prof_max_s = float(df_tramos['Prof_fin'].max()) if not df_tramos.empty else 0.0
    naf_v = resultados.get('naf_m', None)
    naf_txt = f"{naf_v:.2f} m" if naf_v is not None else "No se detectó hasta la máxima profundidad explorada"
    tipo_muestras = datos_anexo.get('Tipo_Muestras', 'Alteradas (SPT) e Inalteradas (PCA / Shelby) / Núcleos')

    ax.add_patch(patches.Rectangle((0, 70.5), 100, 10.0, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 78.8, "II.- EXPLORACIÓN Y MUESTREO", fontsize=8.0, weight='bold', color='navy')
    ax.text(2.0, 76.0, f"Número, tipo y profundidad de sondeos:  {p_sondeo} (Profundidad máxima explorada = {prof_max_s:.2f} m)", fontsize=7.5)
    ax.text(2.0, 73.6, f"Tipo de muestras:  {tipo_muestras}", fontsize=7.5)
    ax.text(2.0, 71.3, f"Profundidad del nivel freático (NAF):  {naf_txt}", fontsize=7.5)

    # III. PRUEBAS DE LABORATORIO EFECTUADAS
    def _chk(flag):
        return "( X )" if flag else "(   )"

    ax.add_patch(patches.Rectangle((0, 52.5), 100, 17.0, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 67.8, "III.- PRUEBAS DE LABORATORIO EFECTUADAS (NORMAS ASTM / SICT)", fontsize=8.0, weight='bold', color='navy')

    col_izq_lab = [
        f"{_chk(pruebas_det.get('humedad_natural', True))}  Humedad natural",
        f"{_chk(pruebas_det.get('limites_plasticidad', True))}  Límites de plasticidad (LL, LP)",
        f"{_chk(pruebas_det.get('granulometria', True))}  Granulometría por mallas / SUCS",
        f"{_chk(pruebas_det.get('porcentaje_finos', True))}  Porcentaje de finos",
        f"{_chk(True)}  Peso específico relativo de sólidos",
        f"{_chk(pruebas_det.get('peso_volumetrico', True))}  Peso volumétrico en estado natural"
    ]
    col_der_lab = [
        f"{_chk(pruebas_det.get('compresion_simple_o_roca', False))}  Compresión simple / Roca (RQD)",
        f"{_chk(pruebas_det.get('triaxial_corte', True))}  Compresión triaxial rápida (UU) / Corte",
        f"{_chk(datos_anexo.get('Triaxial_CU', False))}  Compresión triaxial consolidada (CU)",
        f"{_chk(datos_anexo.get('Triaxial_CD', False))}  Compresión triaxial lenta (CD)",
        f"{_chk(resultados.get('terraplen_excavacion', {}).get('aplica', False))}  Consolidación unidimensional",
        f"{_chk(datos_anexo.get('Torcometro', False))}  Resistencia con torcómetro de bolsillo"
    ]
    for idx_l, txt_l in enumerate(col_izq_lab):
        ax.text(2.5, 64.8 - idx_l * 2.2, txt_l, fontsize=7.3, family='monospace')
    for idx_r, txt_r in enumerate(col_der_lab):
        ax.text(51.0, 64.8 - idx_r * 2.2, txt_r, fontsize=7.3, family='monospace')

    # IV. ESTRATIGRAFÍA Y TIPO DE FORMACIÓN
    ax.add_patch(patches.Rectangle((0, 41.0), 100, 10.5, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 49.8, "IV.- ESTRATIGRAFÍA Y TIPO DE FORMACIÓN", fontsize=8.0, weight='bold', color='navy')
    resumen_est_list = []
    for _, rt in df_tramos.head(4).iterrows():
        desc_corta = rt['Descripcion'][:38] if rt['Descripcion'] else rt['Tipo']
        resumen_est_list.append(f"De {rt['Prof_ini']:.1f} a {rt['Prof_fin']:.1f} m: [{rt['SUCS']}] {desc_corta} (γ={rt['Gamma']:.1f} kN/m³)")
    est_texto = "  |  ".join(resumen_est_list)
    lineas_est = textwrap.wrap(est_texto, width=112)[:3]
    for i_ln, ln_s in enumerate(lineas_est):
        ax.text(2.0, 47.2 - i_ln * 2.2, ln_s, fontsize=7.2)

    # V. CÁLCULOS EFECTUADOS
    cfg_m = resultados.get('config_modulos', {})
    sup_on = cfg_m.get('aplica_superficial_aashto', False)
    pil_on = cfg_m.get('aplica_pandeo_davisson', False)
    soc_on = cfg_m.get('aplica_socavacion', False)
    emp_on = cfg_m.get('aplica_empujes_muros', False)
    ter_on = cfg_m.get('aplica_terraplenes_excavacion', False)

    ax.add_patch(patches.Rectangle((0, 24.5), 100, 15.5, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 38.2, "V.- CÁLCULOS GEOTÉCNICOS Y ESTRUCTURALES REALIZADOS", fontsize=8.0, weight='bold', color='navy')

    calcs_izq = [
        f"{_chk(sup_on)}  1a. Capacidad de carga superficial (AASHTO)",
        f"{_chk(sup_on)}  1b. Estabilidad al deslizamiento y volteo",
        f"{_chk(pil_on)}  1c. Pilas / Pilotes (Pandeo Davisson-Robinson)",
        f"{_chk(pil_on or sup_on)}  2.  Módulos de reacción (kh, kv, ks)"
    ]
    calcs_der = [
        f"{_chk(sup_on or ter_on)}  3.  Asentamientos corto y largo plazo",
        f"{_chk(ter_on)}  4.  Estabilidad de taludes y excavaciones",
        f"{_chk(emp_on)}  5a. Empuje de tierras (Rankine / Mononobe)",
        f"{_chk(soc_on)}  5b. Socavación general y local ({'Activa' if soc_on else 'No aplica al cruce'})"
    ]
    for idx_c, tc_i in enumerate(calcs_izq):
        ax.text(2.5, 35.2 - idx_c * 2.4, tc_i, fontsize=7.3, family='monospace')
    for idx_c, tc_d in enumerate(calcs_der):
        ax.text(51.0, 35.2 - idx_c * 2.4, tc_d, fontsize=7.3, family='monospace')

    # VI. CONCLUSIONES Y RECOMENDACIONES SINTETIZADAS
    ax.add_patch(patches.Rectangle((0, 8.5), 100, 15.0, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 21.8, "VI.- SÍNTESIS DE CONCLUSIONES Y RECOMENDACIONES", fontsize=8.0, weight='bold', color='navy')

    bullets_conc = []
    if sup_on:
        rs = resultados['superficial_aashto']
        bullets_conc.append(
            f"• Cimentación Superficial (Df={rs['Df_m']:.2f}m, B={rs['B_m']:.2f}x{rs['L_m']:.2f}m): q_adm = {rs['q_adm_asd_kgcm2']:.2f} kg/cm² "
            f"(FS_cap={rs['FS_cap_calc']:.2f}, FS_desl={rs['FS_desl_calc']:.2f}, FS_volt={rs['FS_volt_calc']:.2f}, Se={rs['Se_cm']:.2f} cm)."
        )
    if pil_on:
        rd = resultados['davisson_pandeo']
        bullets_conc.append(
            f"• Cimentación Profunda Davisson-Robinson (D={rd['D_m']:.2f}m, L={rd['L_enterrada_m']:.1f}m): Empotramiento mín. requerido = "
            f"{rd['L_emp_min_requerida_m']:.2f} m | P_cr pandeo = {rd['P_cr_euler_ton']:.0f} t (FS_pandeo={rd['FS_pandeo']:.1f})."
        )
    if emp_on:
        re_m = resultados['empujes_muros']
        bullets_conc.append(
            f"• Empuje en Estribos/Muros (H={re_m['H_muro_m']:.1f}m): Ka={re_m['Ka']:.3f}, Kae={re_m['Kae_mononobe']:.3f} | "
            f"Empuje estático={re_m['Ea_total_estatico_tm']:.2f} t/m, sísmico={re_m['Ea_total_sismico_tm']:.2f} t/m."
        )
    if ter_on:
        rt_e = resultados['terraplen_excavacion']
        bullets_conc.append(
            f"• Terraplén (H={rt_e['H_terraplen_m']:.1f}m) y Corte: Asent. total={rt_e['asent_total_terraplen_cm']:.1f} cm "
            f"(corto={rt_e['asent_corto_plazo_cm']:.1f} cm, cons.={rt_e['asent_largo_plazo_cm']:.1f} cm) | Talud exc. {rt_e['talud_exc_H_V']} (FS={rt_e['FS_talud_exc']:.2f})."
        )
    if not soc_on:
        bullets_conc.append(f"• Socavación: {resultados['socavacion'].get('motivo_no_aplica', 'No aplica por ausencia de cauce fluvial.')}")
    else:
        rc_s = resultados['socavacion']
        bullets_conc.append(f"• Socavación Total = {rc_s['soc_total_m']:.2f} m (General={rc_s['soc_general_m']:.2f} m + Local {rc_s['metodo_local_usado']}={rc_s['soc_local_adoptada_m']:.2f} m).")

    y_b = 19.3
    for b_txt in bullets_conc[:5]:
        for sub_l in textwrap.wrap(b_txt, width=116)[:2]:
            if y_b >= 9.3:
                ax.text(2.0, y_b, sub_l, fontsize=6.9)
                y_b -= 2.0

    # FIRMA DEL RESPONSABLE TÉCNICO
    resp_nom = datos_anexo.get('Responsable_Tecnico', 'ING. ESPECIALISTA EN GEOTECNIA')
    resp_ced = datos_anexo.get('Cedula_Prof', 'S/D')
    ax.plot([28, 72], [3.8, 3.8], color='black', lw=1.0)
    ax.text(50, 2.2, f"{resp_nom}   —   CÉD. PROF. NÚM.: {resp_ced}", ha='center', fontsize=7.6, weight='bold')
    ax.text(50, 0.5, "NOMBRE Y FIRMA DEL TÉCNICO RESPONSABLE DEL ESTUDIO", ha='center', fontsize=6.8, color='dimgray')


# ==========================================================
# 4. FUNCIÓN PRINCIPAL GENERADORA DEL PDF SICT / AASHTO
# ==========================================================
def generar_memoria_sict_pdf(df_tramos, resultados, pruebas_det, datos_anexo, logo_url='logo_empresa.png'):
    """
    Compila la Memoria de Calculo Geotecnica SICT / AASHTO adaptandose
    dinamicamente a los modulos habilitados/deshabilitados e integrando al
    final el Formato Anexo Oficial de la SICT.
    """
    pdf_buffer = io.BytesIO()

    p_proy = str(datos_anexo.get('Proyecto', 'ESTUDIO GEOTÉCNICO Y DE CIMENTACIÓN'))
    p_elem = str(datos_anexo.get('Tipo_Obra', resultados.get('tipo_cruce', 'ESTRUCTURA DE CRUCE')))
    p_sondeo = str(datos_anexo.get('Sondeo', 'SONDEO 1'))
    p_fecha = str(datos_anexo.get('Fecha', ''))

    FILAS_EST_PAG = 28
    bloques_est = [df_tramos.iloc[i:i + FILAS_EST_PAG] for i in range(0, max(1, len(df_tramos)), FILAS_EST_PAG)]

    secciones_texto = []

    r_exp = resultados.get('exploracion', {})
    r_soc = resultados.get('socavacion', {})
    txt_b1 = "3. REVISIÓN DE CRITERIOS DE EXPLORACIÓN (TdR 1.5.2) Y SOCAVACIÓN (TdR 1.5.6)\n"
    txt_b1 += "====================================================================================\n\n"
    if r_exp.get('aplica', False):
        txt_b1 += (
            f"A. VERIFICACIÓN NORMATIVA DE PROFUNDIDAD Y SUSPENSIÓN DE SONDEOS (TdR 1.5.2):\n"
            f"   - Profundidad máxima explorada en el sondeo:       {r_exp['prof_max_sondeo_m']:.2f} m\n"
            f"   - Nivel de desplante evaluado (incl. corte subr.): {r_exp['desplante_evaluado_m']:.2f} m\n"
            f"   - Espesor explorado bajo el nivel de desplante:    {r_exp['espesor_bajo_desplante_m']:.2f} m\n"
            f"   - Dictamen suspensión: {r_exp['criterio_suspension_msg']}\n"
            f"   - Condición en ladera: {r_exp['ladera_msg']}\n\n"
        )
    if r_soc.get('aplica', False):
        txt_b1 += (
            f"B. CÁLCULO DE SOCAVACIÓN GENERAL Y LOCAL (TdR 1.5.6.1):\n"
            f"   - Modelo del lecho del cauce: {r_soc['modelo_cauce']}\n"
            f"   - Parámetros Lischtvan-Levediev: alpha = {r_soc['alpha']:.3f} | beta = {r_soc['beta']:.3f} | exp x = {r_soc['x_exp']:.3f}\n"
            f"   - Tirante de equilibrio Hs = {r_soc['hs_equilibrio_m']:.2f} m  =>  Socavación General = {r_soc['soc_general_m']:.2f} m\n"
            f"   - Socavación Local en apoyos (Fr0 = {r_soc['Fr0']:.3f}):\n"
            f"     * Método de Laursen:       {r_soc['soc_local_laursen_m']:.2f} m\n"
            f"     * Método de Yaroslavtziev: {r_soc['soc_local_yaroslavtziev_m']:.2f} m\n"
            f"     * Socavación Local Adoptada ({r_soc['metodo_local_usado']}): {r_soc['soc_local_adoptada_m']:.2f} m\n"
            f"   => PROFUNDIDAD DE SOCAVACIÓN TOTAL (General + Local) = {r_soc['soc_total_m']:.2f} m\n"
        )
    else:
        txt_b1 += (
            f"B. ESTUDIO DE SOCAVACIÓN HIDRÁULICA (TdR 1.5.6.1 — DESHABILITADO):\n"
            f"   - Estado: NO APLICA AL PROYECTO.\n"
            f"   - Justificación técnica: {r_soc.get('motivo_no_aplica', 'Cruce sin corriente de agua superficial.')}\n"
            f"   - Efecto en cimentaciones: Socavación total = 0.00 m (no reduce Df ni genera longitud libre adicional).\n"
        )

    r_sup = resultados.get('superficial_aashto', {})
    if r_sup.get('aplica', False):
        alerta_4m = (
            "   [!] ALERTA NORMATIVA TdR 1.5.8: Df > 4.00 m. El TdR exige analizar y proponer CIMENTACIÓN PROFUNDA.\n"
            if r_sup['excede_4m_tdr'] else
            "   - Verificación TdR 1.5.8 (Df <= 4.00 m): CUMPLE para cimentación superficial.\n"
        )
        txt_b1 += (
            f"\nC. REVISIÓN DE CIMENTACIÓN SUPERFICIAL BAJO ESTADOS LÍMITE AASHTO (TdR 1.5.8):\n"
            f"   - Geometría: B = {r_sup['B_m']:.2f} m | L = {r_sup['L_m']:.2f} m | Df = {r_sup['Df_m']:.2f} m (Df_efec = {r_sup['Df_efectivo_m']:.2f} m)\n"
            f"{alerta_4m}"
            f"   - Acciones actuantes: V = {r_sup['V_ton']:.1f} t | H_res = {r_sup['H_tot_ton']:.1f} t | Excentricidades eB = {r_sup['e_B_m']:.3f} m, eL = {r_sup['e_L_m']:.3f} m\n"
            f"   - Dimensiones efectivas Meyerhof: B' = {r_sup['B_eff_m']:.2f} m, L' = {r_sup['L_eff_m']:.2f} m (A_ef = {r_sup['Area_eff_m2']:.2f} m²)\n"
            f"   - Presión actuante q_act = {r_sup['q_act_kgcm2']:.2f} kg/cm² ({r_sup['q_act_tm2']:.1f} t/m²)\n"
            f"   - Capacidad última AASHTO q_ult = {r_sup['q_ult_kgcm2']:.2f} kg/cm² | Admisible q_adm = {r_sup['q_adm_asd_kgcm2']:.2f} kg/cm²\n"
            f"   - Revisión de Estados Límite:\n"
            f"     1) Capacidad de Carga: FS = {r_sup['FS_cap_calc']:.2f} (mín. {r_sup['FS_cap_req']:.2f}) -> {'CUMPLE' if r_sup['cumple_capacidad'] else 'NO CUMPLE'}\n"
            f"     2) Deslizamiento:      FS = {r_sup['FS_desl_calc']:.2f} (mín. {r_sup['FS_desl_req']:.2f}) -> {'CUMPLE' if r_sup['cumple_deslizamiento'] else 'NO CUMPLE'}\n"
            f"     3) Volteo:             FS = {r_sup['FS_volt_calc']:.2f} (mín. {r_sup['FS_volt_req']:.2f}) -> {'CUMPLE' if r_sup['cumple_volteo'] else 'NO CUMPLE'}\n"
            f"     4) Asentamiento Se:    Se = {r_sup['Se_cm']:.2f} cm ({r_sup['Se_mm']:.1f} mm <= 25.4 mm) -> {'CUMPLE' if r_sup['cumple_asentamiento'] else 'EXCEDE'}\n"
        )
    secciones_texto.append(("EXPLORACIÓN, SOCAVACIÓN Y ZAPATAS AASHTO", txt_b1))

    r_dr = resultados.get('davisson_pandeo', {})
    r_emp = resultados.get('empujes_muros', {})
    r_ter = resultados.get('terraplen_excavacion', {})

    if r_dr.get('aplica', False) or r_emp.get('aplica', False) or r_ter.get('aplica', False):
        txt_b2 = "4. EMPOTRAMIENTO EN PILAS (DAVISSON-ROBINSON), EMPUJES Y TERRAPLENES\n"
        txt_b2 += "====================================================================================\n\n"
        if r_dr.get('aplica', False):
            z_res_str = f"{r_dr['z_estrato_resistente_m']:.2f} m" if r_dr['z_estrato_resistente_m'] is not None else "No detectado"
            txt_b2 += (
                f"A. LONGITUD DE EMPOTRAMIENTO Y PANDEO — MÉTODO DE DAVISSON Y ROBINSON (TdR 1.5.8):\n"
                f"   - Pila circular D = {r_dr['D_m']:.2f} m | L enterrada = {r_dr['L_enterrada_m']:.2f} m | Rigidez Ep·Ip = {r_dr['EpIp_MNm2']:.1f} MN·m²\n"
                f"   - Modelo lateral suelo-pila: {r_dr['modelo_suelo_dr']}\n"
                f"   - Profundidad de fijación equivalente zf = {r_dr['zf_fijacion_m']:.2f} m | Long. libre sin soporte Lu = {r_dr['L_libre_total_Lu_m']:.2f} m\n"
                f"   - Longitud equivalente de pandeo Leq = K·(Lu + zf) = {r_dr['K_efectivo']:.2f} * {(r_dr['L_libre_total_Lu_m'] + r_dr['zf_fijacion_m']):.2f} = {r_dr['L_eq_pandeo_m']:.2f} m (kL/r = {r_dr['esbeltez_kL_r']:.1f})\n"
                f"   - Longitud mínima de empotramiento lateral requerida (4·T o 4·R): {r_dr['L_emp_min_requerida_m']:.2f} m (Estrato firme a: {z_res_str})\n"
                f"   - Carga crítica elástica de pandeo P_cr = {r_dr['P_cr_euler_ton']:.1f} t vs. P_act = {r_dr['P_act_ton']:.1f} t => FS_pandeo = {r_dr['FS_pandeo']:.2f} ({'CUMPLE' if r_dr['cumple_pandeo'] else 'REVISAR'})\n\n"
            )
        if r_emp.get('aplica', False):
            txt_b2 += (
                f"B. EMPUJE DE TIERRAS EN ESTRIBOS Y MUROS DE CONTENCIÓN (RANKINE / MONONOBE-OKABE):\n"
                f"   - Altura de muro H = {r_emp['H_muro_m']:.2f} m | Relleno: gamma = {r_emp['gamma_relleno_kNm3']:.1f} kN/m³, phi = {r_emp['phi_relleno_deg']:.1f}°\n"
                f"   - Coeficientes estáticos: Activo Ka = {r_emp['Ka']:.3f} | En reposo K0 = {r_emp['K0']:.3f} | Pasivo Kp = {r_emp['Kp']:.2f}\n"
                f"   - Coeficiente dinámico sísmico Mononobe-Okabe: Kae = {r_emp['Kae_mononobe']:.3f} (ΔKae = {r_emp['delta_Kae']:.3f}, psi = {r_emp['psi_sismico_deg']:.2f}°)\n"
                f"   - Empuje Activo Estático Total (relleno + sobrecarga viva {r_emp['q_sobrecarga_kpa']:.1f} kPa): Ea = {r_emp['Ea_total_estatico_tm']:.2f} t/m (M_volc = {r_emp['M_volc_estatico_tmm']:.2f} t·m/m)\n"
                f"   - Empuje Activo Sísmico Total (estático + ΔE sismo): Eae = {r_emp['Ea_total_sismico_tm']:.2f} t/m (M_volc = {r_emp['M_volc_sismico_tmm']:.2f} t·m/m)\n\n"
            )
        if r_ter.get('aplica', False):
            txt_b2 += (
                f"C. ESTABILIDAD Y ASENTAMIENTOS DE TERRAPLENES DE ACCESO Y EXCAVACIONES (TdR 1.5.7):\n"
                f"   - Terraplén H = {r_ter['H_terraplen_m']:.2f} m (presión basal = {r_ter['q_terraplen_kpa']:.1f} kPa): FS falla de fondo = {r_ter['FS_base_terraplen']:.2f}\n"
                f"   - Asentamiento etapa constructiva (elástico corto plazo):     {r_ter['asent_corto_plazo_cm']:.2f} cm\n"
                f"   - Asentamiento etapa de servicio (consolidación largo plazo): {r_ter['asent_largo_plazo_cm']:.2f} cm (t90 = {r_ter['t90_consolidacion_meses']:.1f} meses)\n"
                f"   - Asentamiento Total Estimado en Acceso:                      {r_ter['asent_total_terraplen_cm']:.2f} cm\n"
                f"   - Mitigación: {r_ter['mitigacion_terraplen']}\n"
                f"   - Excavación (H = {r_ter['H_excavacion_m']:.2f} m, Talud {r_ter['talud_exc_H_V']}): FS = {r_ter['FS_talud_exc']:.2f} -> {r_ter['recomendacion_excavacion']}\n"
            )
        secciones_texto.append(("PANDEO DAVISSON-ROBINSON, EMPUJES Y TERRAPLENES", txt_b2))

    tiene_esquemas = r_dr.get('aplica', False) or r_emp.get('aplica', False)
    total_paginas = 1 + len(bloques_est) + len(secciones_texto) + (1 if tiene_esquemas else 0) + 1

    with PdfPages(pdf_buffer) as pdf:
        contador = 1

        # PÁGINA 1: MARCO NORMATIVO SICT / AASHTO Y ALCANCE MODULAR
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_sict(fig, "MARCO NORMATIVO Y HIPÓTESIS DE DISEÑO",
                              contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
        cfg_m = resultados.get('config_modulos', {})
        texto_pg1 = (
            "1. MARCO NORMATIVO, HIPÓTESIS Y ALCANCE DEL ESTUDIO (TdR SICT ETAPA V Y VI)\n"
            "====================================================================================\n\n"
            f"ESTRUCTURA ANALIZADA: {resultados.get('tipo_cruce', p_elem)}\n\n"
            "A. NORMATIVA Y REFERENCIAS TÉCNICAS APLICADAS (TdR 1.5.12.2 / 1.6)\n"
            "   - Términos de Referencia SICT para Estudios Geotécnicos y de Cimentación de Puentes.\n"
            "   - Normativa para la Infraestructura del Transporte (SICT):\n"
            "     * N-PRY-CAR-6-01-003/01 (Cargas y Acciones) y N-PRY-CAR-6-01-006/16 (Combinaciones).\n"
            "     * N-PRY-CAR-6-01-005/01 (Diseño por Sismo) y Manual de Obras Civiles CFE.\n"
            "   - AASHTO Standard Specifications for Highway Bridges / AASHTO LRFD Bridge Design.\n"
            "   - Davisson, M.T. & Robinson, K.E. (1965). 'Bending and Buckling of Partially Embedded Piles'.\n"
            "   - Juárez Badillo & Rico Rodríguez / Manual de Socavación SICT (Lischtvan-Levediev, Laursen).\n\n"
            "B. CONFIGURACIÓN MODULAR DE CÁLCULOS HABILITADOS PARA ESTE SITIO DE CRUCE\n"
            f"   1. Criterios de Exploración y Suspensión de Sondeos (TdR 1.5.2):   {'[ HABILITADO ]' if cfg_m.get('aplica_exploracion', True) else '[ NO APLICA ]'}\n"
            f"   2. Socavación General y Local de Cauces (TdR 1.5.6.1):             {'[ HABILITADO ]' if cfg_m.get('aplica_socavacion', False) else '[ DESHABILITADO — SIN CAUCE ]'}\n"
            f"   3. Cimentación Superficial bajo Norma AASHTO (TdR 1.5.8):          {'[ HABILITADO ]' if cfg_m.get('aplica_superficial_aashto', True) else '[ NO APLICA ]'}\n"
            f"   4. Pilas/Pilotes: Empotramiento y Pandeo Davisson (TdR 1.5.8):     {'[ HABILITADO ]' if cfg_m.get('aplica_pandeo_davisson', True) else '[ NO APLICA ]'}\n"
            f"   5. Empuje de Tierras Estático y Sísmico en Estribos (TdR 1.4.13):  {'[ HABILITADO ]' if cfg_m.get('aplica_empujes_muros', True) else '[ NO APLICA ]'}\n"
            f"   6. Terraplenes de Acceso y Taludes de Excavación (TdR 1.5.7):      {'[ HABILITADO ]' if cfg_m.get('aplica_terraplenes_excavacion', True) else '[ NO APLICA ]'}\n\n"
            "C. ACOPLAMIENTO GEOTÉCNICO-ESTRUCTURAL\n"
            "   - Los módulos activos transfieren automáticamente sus efectos hacia las revisiones subsecuentes.\n"
            "   - Cuando el cruce corresponde a un Paso Superior/Inferior sin cauce fluvial (ej. PFFCC, PSV, PIV),\n"
            "     la socavación hidráulica se anula justificadamente sin penalizar el desplante ni el pandeo."
        )
        fig.text(0.06, 0.84, texto_pg1, va='top', ha='left', fontsize=7.9, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA(S) 2: MODELO ESTRATIGRÁFICO COMPLETO
        for idx_e, df_sub in enumerate(bloques_est):
            fig = plt.figure(figsize=(8.5, 11))
            suf_e = f" (Parte {idx_e + 1}/{len(bloques_est)})" if len(bloques_est) > 1 else ""
            crear_encabezado_sict(fig, f"ESTRATIGRAFÍA Y PARÁMETROS GEOTÉCNICOS{suf_e}",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            fig.text(0.06, 0.84, f"2. MODELO ESTRATIGRÁFICO DEL SITIO DE CRUCE{suf_e}",
                     fontsize=8.5, weight='bold', color='navy')

            headers_e = ["Prof. (m)", "SUCS", "Tipo", "SPT / RQD", "γ\n(kN/m³)", "c\n(kPa)", "φ\n(°)", "Es\n(kPa)", "Cc / e0"]
            rows_e = []
            for _, r in df_sub.iterrows():
                spt_lbl = str(r['SPT_raw']) if r['SPT_raw'] else (f"RQD {r['RQD_pct']:.0f}%" if pd.notna(r['RQD_pct']) else "Lab")
                rows_e.append([
                    f"{r['Prof_ini']:.2f}-{r['Prof_fin']:.2f}",
                    str(r['SUCS']),
                    str(r['Tipo'])[:12],
                    spt_lbl[:10],
                    f"{r['Gamma']:.2f}",
                    f"{r['c_kPa']:.1f}",
                    f"{r['phi_deg']:.1f}°",
                    f"{r['Es_kPa']:.0f}",
                    f"{r['Cc']:.2f}/{r['e0']:.2f}"
                ])

            n_fe = len(rows_e)
            h_box = min(0.73, (n_fe + 1.5) * 0.026)
            ax_te = fig.add_axes([0.05, 0.81 - h_box, 0.90, h_box])
            ax_te.axis('off')
            t_e = ax_te.table(
                cellText=[headers_e] + rows_e,
                bbox=[0.0, 0.0, 1.0, 1.0],
                cellLoc='center',
                colWidths=[0.14, 0.08, 0.13, 0.11, 0.10, 0.10, 0.09, 0.12, 0.13]
            )
            t_e.auto_set_font_size(False)
            t_e.set_fontsize(7.0 if n_fe > 22 else 7.5)
            for (ri, ci), cell in t_e.get_celld().items():
                cell.set_linewidth(0.5)
                if ri == 0:
                    cell.set_facecolor('navy')
                    cell.set_text_props(color='white', weight='bold')
                elif ri % 2 == 0:
                    cell.set_facecolor('#f4f4f4')

            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINAS DE MEMORIA DE CÁLCULO DETALLADA
        for tit_sec, cuerpo_txt in secciones_texto:
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_sict(fig, tit_sec, contador, total_paginas,
                                  p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            fig.text(0.06, 0.84, cuerpo_txt, va='top', ha='left', fontsize=7.5, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA DE ESQUEMAS Y DIAGRAMAS ESTRUCTURALES-GEOTÉCNICOS
        if tiene_esquemas:
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_sict(fig, "ESQUEMAS DE INTERACCIÓN, PANDEO Y EMPUJES",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            dibujar_esquemas_sict(fig, resultados)

            nota_proc = (
                "LINEAMIENTOS DE PROCEDIMIENTO CONSTRUCTIVO Y CONTROL GEOTÉCNICO (TdR 1.5.10):\n"
                "------------------------------------------------------------------------------------\n"
                "1. Trazo y Verificación: Previo al inicio de excavaciones o perforaciones deberá contarse con la\n"
                "   validación de ejes de apoyo trazados en campo (Minuta II y Minuta IV firmadas con LA DEPENDENCIA).\n"
                "2. Desplante y Protección: Todo fondo de excavación para zapatas o cabezales se protegerá de inmediato\n"
                "   con plantilla de concreto simple f'c = 100 kg/cm² de 5 cm de espesor mínimo.\n"
                "3. Colado de Pilas y Rellenos: En perforaciones bajo NAF o suelos inestables se empleará ademe metálico\n"
                "   recuperable o lodo estabilizador y colado continuo con tubería Tremie. Los rellenos en estribos se\n"
                "   compactarán en capas <= 20 cm al 95% de su PVSM AASHTO con material granular drenante y drenaje posterior."
            )
            fig.text(0.06, 0.36, nota_proc, va='top', ha='left', fontsize=7.9, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA FINAL: CÉDULA ANEXO OFICIAL SICT
        fig = plt.figure(figsize=(8.5, 11))
        dibujar_pagina_anexo_oficial_sict(
            fig, contador, total_paginas, df_tramos, resultados, pruebas_det, datos_anexo, logo_url
        )
        pdf.savefig(fig); plt.close(); contador += 1

    return pdf_buffer.getvalue()