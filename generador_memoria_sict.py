# ==============================================================================
# MODULO: generador_memoria_sict.py
# VERSION: 3.0.0-SICT-AASHTO-ESTILO-MEMORIA-DETALLADA
# DESCRIPCION:
#   Generador ejecutivo en PDF de la Memoria Geotecnica para Puentes y Pasos
#   con formato y desglose inspirados en generador_memoria_pdf.py (2 hojas por
#   caso representativo: desglose axial detallado + tabla de balasto/resortes
#   metro a metro), Consideraciones Geotecnicas, y opciones configurables para
#   incluir u omitir la Minuta IV (TdR 1.5.9) y el Anexo Oficial SICT.
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
# 1. ENCABEZADO, PIE Y TABLAS AL ESTILO MEMORIA DETALLADA
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
        fig.text(0.05, 0.024, "NORMATIVA: TdR SICT (Etapa V y VI) | N-PRY-CAR-8-01-004/19 | AASHTO LRFD Bridge Design",
                 fontsize=6.8, color='dimgray')
        fig.text(0.95, 0.024, "ANTEFIRMA RESP. TÉCNICO: ______________________",
                 ha='right', fontsize=6.8, color='black')


def _dibujar_tabla_ajustada(fig, headers, rows_data, x_left, y_top, width, max_height,
                            col_widths=None, color_header='navy', font_sz=7.2):
    n_f = len(rows_data)
    h_ideal = (n_f + 1.45) * 0.0235
    h_box = min(max_height, max(0.06, h_ideal))
    ax_t = fig.add_axes([x_left, y_top - h_box, width, h_box])
    ax_t.axis('off')

    tab = ax_t.table(
        cellText=[headers] + rows_data,
        bbox=[0.0, 0.0, 1.0, 1.0],
        cellLoc='center',
        colWidths=col_widths
    )
    tab.auto_set_font_size(False)
    tab.set_fontsize(font_sz)

    tot_u = n_f + 1.45
    h_hdr = 1.45 / tot_u
    h_row = 1.0 / tot_u

    for (ri, ci), cell in tab.get_celld().items():
        cell.set_linewidth(0.5)
        if ri == 0:
            cell.set_height(h_hdr)
            cell.set_facecolor(color_header)
            cell.set_text_props(color='white', weight='bold')
        else:
            cell.set_height(h_row)
            if ri % 2 == 0:
                cell.set_facecolor('#f4f4f4')
    return y_top - h_box


def _construir_desglose_caso_sict(df_tramos, naf_m, D_m, L_m, socavacion_total_m=0.0, fc_kgcm2=280.0):
    """Calcula el desglose detallado de un caso (D, L) y su perfil metro a metro (kh, Kh, kv, Kv_lin)."""
    from calculos_sict_puentes import evaluar_pila_individual_aashto_lrfd

    D = float(D_m)
    L = float(L_m)
    z_soc = max(0.0, float(socavacion_total_m))
    res = evaluar_pila_individual_aashto_lrfd(df_tramos, naf_m, D, L, socavacion_total_m=z_soc, fc_kgcm2=fc_kgcm2)

    perim = math.pi * D
    ap = math.pi * (D ** 2) / 4.0
    vol = ap * L
    z_ini = z_soc + 1.50
    z_fin = max(z_ini, L - 1.0 * D)

    # Discretizacion metro a metro (1.0 m hasta int(round(L)))
    n_metros = max(1, int(round(L)))
    filas_m = []
    for m_i in range(1, n_metros + 1):
        z_m = float(m_i)
        tr_m = df_tramos[(df_tramos['Prof_ini'] < z_m) & (df_tramos['Prof_fin'] >= z_m)]
        if tr_m.empty and not df_tramos.empty:
            tr_m = df_tramos.iloc[[-1]]
        if not tr_m.empty:
            fila_t = tr_m.iloc[0]
            sucs_m = str(fila_t['SUCS'])
            tipo_m = str(fila_t['Tipo'])
            n60_m = float(fila_t['N60']) if pd.notna(fila_t['N60']) else 20.0
            cu_m = max(float(fila_t['c_kPa']), 6.0 * n60_m, 25.0)
        else:
            sucs_m, tipo_m, n60_m, cu_m = 'SM', 'Friccionante', 25.0, 50.0

        z_rel = max(0.5, z_m - z_soc)
        if z_m <= z_soc:
            kh_val = 0.0
        elif tipo_m == 'Cohesivo':
            kh_val = (67.0 * cu_m) / (D * 9.81)
        elif tipo_m == 'Roca':
            kh_val = 25000.0 / D
        else:
            kh_val = (25.0 * n60_m) * (z_rel / D)

        kv_val = 0.85 * kh_val if tipo_m != 'Cohesivo' else 1.20 * kh_val
        filas_m.append({
            'z_m': -z_m,
            'sucs': sucs_m,
            'tipo': tipo_m,
            'n60': n60_m,
            'kh': round(kh_val, 1),
            'Kh_lin': round(kh_val * D, 1),
            'kv': round(kv_val, 1),
            'Kv_lin': round(kv_val * D, 1)
        })

    return {
        'D': D, 'L': L, 'Perimetro': perim, 'Area_punta': ap,
        'Volumen': vol, 'W_ton': res['W_neto_ton'],
        'z_act_ini': z_ini, 'z_act_fin': z_fin,
        'L_efec': res['L_efectiva_m'],
        'Cf_comp_ton': res['Cf_comp_ton'], 'Cp_comp_ton': res['Cp_comp_ton'],
        'R_comp_ton': res['R_comp_ton'],
        'Cf_tens_ton': res['Cf_tens_ton'], 'R_tens_ton': res['R_tens_ton'],
        'kh_prom': res['kh_prom_tm3'], 'Kv_t_cm': res['Kv_cabeza_t_cm'],
        'filas_metro': filas_m
    }


# ==========================================================
# 2. ESQUEMAS GRÁFICOS DE INGENIERÍA (DAVISSON Y MONONOBE)
# ==========================================================
def dibujar_esquemas_sict(fig, resultados):
    r_soc = resultados.get('socavacion', {})
    r_dr = resultados.get('davisson_pandeo', {})
    r_emp = resultados.get('empujes_muros', {})

    ax1 = fig.add_axes([0.07, 0.44, 0.41, 0.37])
    ax1.set_title("Esquema Paramétrico y Fijación de Pila\n(Criterios FHWA / AASHTO / Davisson)", fontsize=8.6, weight='bold')

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
        ax1.text(3.9, 0.3, "Terreno / Desplante (±0.00 m)", ha='right', fontsize=7.0, color='saddlebrown', weight='bold')

        if r_soc.get('aplica', False) and z_soc > 0.01:
            ax1.axhline(-z_soc, color='dodgerblue', lw=1.3, linestyle='--')
            ax1.text(3.9, -z_soc - 0.5, f"Nivel Socavado (-{z_soc:.2f} m)", ha='right', fontsize=6.8, color='dodgerblue', weight='bold')

        w_vis = max(0.65, min(1.3, D_v))
        rect_pila = patches.Rectangle((-w_vis / 2, y_bot_pila), w_vis, L_ent + L_col,
                                      facecolor='#d9d9d9', edgecolor='black', lw=1.4, zorder=3)
        ax1.add_patch(rect_pila)

        y_fij = -(min(L_ent * 0.85, zf))
        ax1.axhline(y_fij, color='crimson', lw=1.3, linestyle='-.')
        ax1.plot([0], [y_fij], marker='s', color='crimson', markersize=6, zorder=5)
        ax1.text(3.9, y_fij + 0.3, f"Fijación zf ({zf:.2f} m)", ha='right', fontsize=7.0, color='crimson', weight='bold')

        ax1.annotate('', xy=(0, y_top_col), xytext=(0, y_top_col + 1.6),
                     arrowprops=dict(arrowstyle='->', color='darkred', lw=2.0))
        ax1.text(0.2, y_top_col + 0.9, f"P_act = {r_dr['P_act_ton']:.0f} t\nP_cr = {r_dr['P_cr_euler_ton']:.0f} t",
                 fontsize=7.1, color='darkred', weight='bold')
        ax1.axis('off')
    else:
        # Esquema de zonas de exclusion de fuste (1.50 m superior y 1.0*D en base)
        ax1.set_xlim(-3.5, 4.5)
        ax1.set_ylim(-24.0, 2.5)
        ax1.axhline(0.0, color='saddlebrown', lw=1.8)
        ax1.text(4.2, 0.4, "N.T.N. (±0.00 m)", ha='right', fontsize=7.0, color='saddlebrown', weight='bold')
        rect_p = patches.Rectangle((-0.6, -20.0), 1.2, 20.0, facecolor='#d9d9d9', edgecolor='black', lw=1.4)
        ax1.add_patch(rect_p)
        ax1.add_patch(patches.Rectangle((-0.6, -1.5), 1.2, 1.5, facecolor='#f8d7da', edgecolor='crimson', hatch='xx'))
        ax1.text(0.85, -0.75, "Fricción anulada\n(1.50 m superior)", va='center', fontsize=6.8, color='crimson', weight='bold')
        ax1.add_patch(patches.Rectangle((-0.6, -20.0), 1.2, 1.2, facecolor='#f8d7da', edgecolor='crimson', hatch='xx'))
        ax1.text(0.85, -19.4, "Fricción anulada\n(1.0·D en punta)", va='center', fontsize=6.8, color='crimson', weight='bold')
        ax1.text(0.85, -10.0, "Fricción Activa\n(L_efec)", va='center', fontsize=7.2, color='navy', weight='bold')
        ax1.axis('off')

    ax2 = fig.add_axes([0.55, 0.44, 0.39, 0.37])
    ax2.set_title("Diagrama de Empujes en Estribos / Muros\n(Rankine + Sismo Mononobe-Okabe, SICT)", fontsize=8.6, weight='bold')

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
        ax2.text(1.30, Hm * 0.22, f"Ea estático\n{r_emp['Ea_total_estatico_tm']:.2f} t/m", fontsize=7.0, color='navy', weight='bold')

        poly_sis = patches.Polygon([[2.8, Hm], [4.2, Hm], [2.8, 0.0]], closed=True,
                                   facecolor='#fde2e2', edgecolor='crimson', lw=1.2, linestyle='--', alpha=0.85)
        ax2.add_patch(poly_sis)
        ax2.text(3.35, Hm * 0.68, f"ΔE sismo\n+{r_emp['dE_sismo_tm']:.2f} t/m\n(0.6·H)", fontsize=6.8, color='crimson', weight='bold')

        ax2.axhline(0.0, color='black', lw=1.2)
        ax2.axis('off')
    else:
        ax2.text(0.5, 0.5, "Módulo de Empuje de Tierras\n(Deshabilitado para este proyecto)",
                 ha='center', va='center', fontsize=8.2, color='gray', style='italic')
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

    ax.add_patch(patches.Rectangle((0, 81.5), 100, 11.2, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 91.0, "I.- DATOS DE LA OBRA", fontsize=8.0, weight='bold', color='navy')
    ax.text(2.0, 88.3, f"Tipo de obra:   {datos_anexo.get('Tipo_Obra', resultados.get('tipo_cruce', 'Puente / Paso Superior'))}", fontsize=7.6)
    ax.text(2.0, 85.8, f"Camino:         {datos_anexo.get('Camino', 'Proyecto Carretero / Ferroviario')}", fontsize=7.6)
    ax.text(2.0, 83.3, f"Tramo / Km:     {datos_anexo.get('Tramo', 'S/D')}     |     Localización: {datos_anexo.get('Localizacion', 'S/D')}", fontsize=7.6)

    prof_max_s = float(df_tramos['Prof_fin'].max()) if not df_tramos.empty else 0.0
    naf_v = resultados.get('naf_m', None)
    naf_txt = f"{naf_v:.2f} m" if naf_v is not None else "No se detectó hasta la máxima profundidad explorada"
    tipo_muestras = datos_anexo.get('Tipo_Muestras', 'Alteradas (SPT) e Inalteradas (PCA / Shelby) / Núcleos')

    ax.add_patch(patches.Rectangle((0, 70.5), 100, 10.0, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 78.8, "II.- EXPLORACIÓN Y MUESTREO", fontsize=8.0, weight='bold', color='navy')
    ax.text(2.0, 76.0, f"Número, tipo y profundidad de sondeos:  {p_sondeo} (Profundidad máxima explorada = {prof_max_s:.2f} m)", fontsize=7.5)
    ax.text(2.0, 73.6, f"Tipo de muestras:  {tipo_muestras}", fontsize=7.5)
    ax.text(2.0, 71.3, f"Profundidad del nivel freático (NAF):  {naf_txt}", fontsize=7.5)

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

    ax.add_patch(patches.Rectangle((0, 41.0), 100, 10.5, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 49.8, "IV.- ESTRATIGRAFÍA Y TIPO DE FORMACIÓN", fontsize=8.0, weight='bold', color='navy')
    resumen_est_list = []
    for _, rt in df_tramos.head(4).iterrows():
        desc_corta = rt['Descripcion'][:36] if rt['Descripcion'] else rt['Tipo']
        resumen_est_list.append(f"De {rt['Prof_ini']:.1f} a {rt['Prof_fin']:.1f} m: [{rt['SUCS']}] {desc_corta} (γ={rt['Gamma']:.1f} kN/m³)")
    est_texto = "  |  ".join(resumen_est_list)
    for i_ln, ln_s in enumerate(textwrap.wrap(est_texto, width=112)[:3]):
        ax.text(2.0, 47.2 - i_ln * 2.2, ln_s, fontsize=7.2)

    cfg_m = resultados.get('config_modulos', {})
    prop_on = cfg_m.get('aplica_propuesta_inicial', True)
    rev_on = cfg_m.get('aplica_revision_definitiva', False) and resultados.get('revision_definitiva', {}).get('aplica', False)
    soc_on = cfg_m.get('aplica_socavacion', False)
    emp_on = cfg_m.get('aplica_empujes_muros', False)
    ter_on = cfg_m.get('aplica_terraplenes_excavacion', False)

    ax.add_patch(patches.Rectangle((0, 24.5), 100, 15.5, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 38.2, "V.- CÁLCULOS GEOTÉCNICOS Y ESTRUCTURALES REALIZADOS", fontsize=8.0, weight='bold', color='navy')

    calcs_izq = [
        f"{_chk(prop_on or rev_on)}  1a. Propuesta inicial pilas y zapatas (AASHTO)",
        f"{_chk(rev_on)}  1b. Revisión definitiva grupos de pilas / zapatas",
        f"{_chk(rev_on)}  1c. Pandeo Davisson-Robinson y lateral Broms",
        f"{_chk(prop_on or rev_on)}  2.  Módulos de reacción (kh, Kv, ks)"
    ]
    calcs_der = [
        f"{_chk(rev_on or ter_on)}  3.  Asentamientos Poulos (grupo) y consolidación",
        f"{_chk(ter_on)}  4.  Estabilidad de taludes y excavaciones",
        f"{_chk(emp_on)}  5a. Empuje de tierras metro a metro (Mononobe)",
        f"{_chk(soc_on)}  5b. Socavación general y local ({'Activa' if soc_on else 'No aplica al cruce'})"
    ]
    for idx_c, tc_i in enumerate(calcs_izq):
        ax.text(2.5, 35.2 - idx_c * 2.4, tc_i, fontsize=7.3, family='monospace')
    for idx_c, tc_d in enumerate(calcs_der):
        ax.text(51.0, 35.2 - idx_c * 2.4, tc_d, fontsize=7.3, family='monospace')

    ax.add_patch(patches.Rectangle((0, 8.5), 100, 15.0, fill=False, edgecolor='black', lw=0.8))
    ax.text(1.5, 21.8, "VI.- SÍNTESIS DE CONCLUSIONES Y RECOMENDACIONES", fontsize=8.0, weight='bold', color='navy')

    bullets_conc = []
    if prop_on and resultados.get('propuesta_inicial', {}).get('aplica', False):
        pi = resultados['propuesta_inicial']
        if not pi['df_pilas'].empty:
            rmin, rmax = pi['df_pilas']['R_comp_ton'].min(), pi['df_pilas']['R_comp_ton'].max()
            tmin, tmax = pi['df_pilas']['R_tens_ton'].min(), pi['df_pilas']['R_tens_ton'].max()
            bullets_conc.append(
                f"• Etapa 1 (Propuesta Inicial Pilas AASHTO LRFD): Capacidad individual a compresión de {rmin:.1f} a {rmax:.1f} t "
                f"y a extracción/tensión de {tmin:.1f} a {tmax:.1f} t."
            )
    if rev_on:
        df_ra = resultados['revision_definitiva']['df_resumen_apoyos']
        n_ok = int((df_ra['Estado'] == 'CUMPLE').sum())
        s_max_mm = float(df_ra['Asentamiento_mm'].max())
        bullets_conc.append(
            f"• Etapa 2 (Revisión Definitiva Multi-Apoyo): Evaluados {len(df_ra)} apoyos estructurales ({n_ok}/{len(df_ra)} en cumplimiento integral); "
            f"asentamiento máximo = {s_max_mm:.1f} mm (<= 25.0 mm N-PRY-CAR-8-01-004/19)."
        )
    if emp_on:
        re_m = resultados['empujes_muros']
        bullets_conc.append(
            f"• Empuje de Diseño en Estribos (H={re_m['H_muro_m']:.1f}m): Ka={re_m['Ka']:.3f}, Kp={re_m['Kp']:.2f}, Kae={re_m['Kae_mononobe']:.3f} | "
            f"Ea estático = {re_m['Ea_total_estatico_tm']:.2f} t/m, Ea sísmico = {re_m['Ea_total_sismico_tm']:.2f} t/m."
        )
    if ter_on:
        rt_e = resultados['terraplen_excavacion']
        bullets_conc.append(
            f"• Excavaciones y Terraplenes: Prof. máx. sin ademe = {rt_e['H_max_sin_estab_m']:.2f} m (talud {rt_e['angulo_talud_deg']:.0f}°) | "
            f"Asentamiento total en acceso = {rt_e['asent_total_terraplen_cm']:.1f} cm."
        )
    if not soc_on:
        bullets_conc.append(f"• Socavación: {resultados['socavacion'].get('motivo_no_aplica', 'No aplica por ausencia de cauce fluvial.')}")
    else:
        rc_s = resultados['socavacion']
        bullets_conc.append(f"• Socavación Total = {rc_s['soc_total_m']:.2f} m (General = {rc_s['soc_general_m']:.2f} m + Local = {rc_s['soc_local_adoptada_m']:.2f} m).")

    y_b = 19.3
    for b_txt in bullets_conc[:5]:
        for sub_l in textwrap.wrap(b_txt, width=116)[:2]:
            if y_b >= 9.3:
                ax.text(2.0, y_b, sub_l, fontsize=6.9)
                y_b -= 2.0

    resp_nom = datos_anexo.get('Responsable_Tecnico', 'ING. ESPECIALISTA EN GEOTECNIA')
    resp_ced = datos_anexo.get('Cedula_Prof', 'S/D')
    ax.plot([28, 72], [3.8, 3.8], color='black', lw=1.0)
    ax.text(50, 2.2, f"{resp_nom}   —   CÉD. PROF. NÚM.: {resp_ced}", ha='center', fontsize=7.6, weight='bold')
    ax.text(50, 0.5, "NOMBRE Y FIRMA DEL TÉCNICO RESPONSABLE DEL ESTUDIO", ha='center', fontsize=6.8, color='dimgray')


# ==========================================================
# 4. FUNCIÓN PRINCIPAL GENERADORA DEL PDF SICT / AASHTO
#    (ESTILO DETALLADO + OPCIONES PARA OMITIR MINUTA IV Y ANEXO)
# ==========================================================
def generar_memoria_sict_pdf(df_tramos, resultados, pruebas_det, datos_anexo,
                             logo_url='logo_empresa.png',
                             incluir_minuta4=True, incluir_anexo_sict=True):
    """
    Compila la Memoria Geotecnica SICT / AASHTO con desglose detallado de
    casos y balasto metro a metro (estilo generador_memoria_pdf.py), permitiendo
    incluir u omitir de forma independiente la Minuta IV y el Anexo Oficial SICT.
    """
    pdf_buffer = io.BytesIO()

    p_proy = str(datos_anexo.get('Proyecto', 'ESTUDIO GEOTÉCNICO Y DE CIMENTACIÓN'))
    p_elem = str(datos_anexo.get('Tipo_Obra', resultados.get('tipo_cruce', 'ESTRUCTURA DE CRUCE')))
    p_sondeo = str(datos_anexo.get('Sondeo', 'SONDEO 1'))
    p_fecha = str(datos_anexo.get('Fecha', ''))

    FILAS_EST_PAG = 28
    bloques_est = [df_tramos.iloc[i:i + FILAS_EST_PAG] for i in range(0, max(1, len(df_tramos)), FILAS_EST_PAG)]

    prop_ini = resultados.get('propuesta_inicial', {})
    tiene_etapa1 = prop_ini.get('aplica', False) and (not prop_ini.get('df_pilas', pd.DataFrame()).empty)
    pags_etapa1 = 2 if tiene_etapa1 else 0

    # Desgloses detallados estilo generador_memoria_pdf.py (2 paginas por caso: desglose + balasto m a m)
    desgloses_det = []
    if tiene_etapa1:
        df_p_all = prop_ini['df_pilas']
        l_min_v = float(df_p_all['L_m'].min())
        l_max_v = float(df_p_all['L_m'].max())
        d_vals = sorted(df_p_all['D_m'].unique().tolist())
        soc_v = resultados.get('socavacion', {}).get('soc_total_m', 0.0)
        pares_dl = []
        for d_i in d_vals:
            pares_dl.append((d_i, l_max_v))
            if l_min_v != l_max_v and (d_i, l_min_v) not in pares_dl:
                pares_dl.append((d_i, l_min_v))
        for d_i, l_i in pares_dl[:8]:
            desgloses_det.append(_construir_desglose_caso_sict(df_tramos, resultados.get('naf_m'), d_i, l_i, socavacion_total_m=soc_v))

    pags_desglose_det = len(desgloses_det) * 2

    rev_def = resultados.get('revision_definitiva', {})
    tiene_etapa2 = rev_def.get('aplica', False) and (not rev_def.get('df_resumen_apoyos', pd.DataFrame()).empty)
    if tiene_etapa2:
        df_ap_all = rev_def['df_resumen_apoyos']
        bloques_apoyos = [df_ap_all.iloc[i:i + 10] for i in range(0, len(df_ap_all), 10)]
        pags_etapa2 = len(bloques_apoyos)
    else:
        bloques_apoyos = []
        pags_etapa2 = 0

    r_emp = resultados.get('empujes_muros', {})
    r_ter = resultados.get('terraplen_excavacion', {})
    tiene_etapa3 = r_emp.get('aplica', False) or r_ter.get('aplica', False)
    pags_etapa3 = 1 if tiene_etapa3 else 0

    pags_consid_geo = 1
    pags_minuta4 = 1 if incluir_minuta4 else 0
    pags_esquemas_rec = 1
    pags_anexo = 1 if incluir_anexo_sict else 0

    total_paginas = (
        1 + len(bloques_est) + pags_consid_geo + pags_etapa1 + pags_desglose_det +
        pags_etapa2 + pags_etapa3 + pags_minuta4 + pags_esquemas_rec + pags_anexo
    )

    with PdfPages(pdf_buffer) as pdf:
        contador = 1

        # PÁGINA 1: MARCO NORMATIVO, EXPLORACIÓN Y SOCAVACIÓN
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_sict(fig, "MARCO NORMATIVO, EXPLORACIÓN Y SOCAVACIÓN",
                              contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

        cfg_m = resultados.get('config_modulos', {})
        r_exp = resultados.get('exploracion', {})
        r_soc = resultados.get('socavacion', {})

        txt_exp = ""
        if r_exp.get('aplica', False):
            txt_exp = (
                f"C. REVISIÓN DE CRITERIOS DE EXPLORACIÓN Y SUSPENSIÓN DE SONDEOS (TdR 1.5.2)\n"
                f"   - Profundidad máxima explorada: {r_exp['prof_max_sondeo_m']:.2f} m | Desplante ref.: {r_exp['desplante_evaluado_m']:.2f} m\n"
                f"   - Dictamen suspensión: {r_exp['criterio_suspension_msg']}\n"
                f"   - Condición en ladera: {r_exp['ladera_msg']}\n\n"
            )

        if r_soc.get('aplica', False):
            txt_soc = (
                f"D. ESTUDIO DE SOCAVACIÓN GENERAL Y LOCAL (TdR 1.5.6.1 — ACTIVO)\n"
                f"   - Modelo del lecho: {r_soc['modelo_cauce']} | alpha = {r_soc['alpha']:.3f}, beta = {r_soc['beta']:.3f}, Fr0 = {r_soc['Fr0']:.3f}\n"
                f"   - Tirante equilibrio Hs = {r_soc['hs_equilibrio_m']:.2f} m => Socavación General (Lischtvan-Levediev) = {r_soc['soc_general_m']:.2f} m\n"
                f"   - Socavación Local: Laursen = {r_soc['soc_local_laursen_m']:.2f} m | Yaroslavtziev = {r_soc['soc_local_yaroslavtziev_m']:.2f} m\n"
                f"   => SOCAVACIÓN TOTAL ACUMULADA = {r_soc['soc_total_m']:.2f} m (descontada automáticamente en Etapa 1 y Etapa 2)."
            )
        else:
            txt_soc = (
                f"D. ESTUDIO DE SOCAVACIÓN HIDRÁULICA (TdR 1.5.6.1 — DESHABILITADO)\n"
                f"   - Estado: NO APLICA AL PROYECTO (Socavación total = 0.00 m).\n"
                f"   - Sustento: {r_soc.get('motivo_no_aplica', 'Cruce sin corriente de agua superficial.')}"
            )

        texto_pg1 = (
            "1. METODOLOGÍA DE CÁLCULO Y MARCO NORMATIVO (SICT / AASHTO LRFD)\n"
            "====================================================================================\n\n"
            f"ESTRUCTURA: {resultados.get('tipo_cruce', p_elem)}\n"
            f"ALCANCE:    {resultados.get('alcance_etapa', 'Estudio Geotécnico y de Cimentación')}\n\n"
            "A. SECUENCIA DE DISEÑO GEOTÉCNICO-ESTRUCTURAL\n"
            "   - ETAPA 1 (Propuesta Inicial): Catálogos de capacidad a compresión y tensión para pilas\n"
            "     individuales (AASHTO LRFD, O'Neill & Reese 1999: métodos alfa y beta, anulando 1.50 m\n"
            "     superiores y 1.0·D en punta), zapatas preliminares (Df <= 4.00 m), desglose por caso y\n"
            "     tablas de balasto/resortes metro a metro.\n"
            "   - ETAPA 2 (Revisión Definitiva Multi-Apoyo): Verifica cada apoyo con descargas estructurales\n"
            "     (eficiencia y bloque AASHTO 10.7.3.9 / 10.8.3.6, par biaxial, Poulos <= 25 mm, Broms,\n"
            "     Davisson-Robinson y cotas topográficas).\n\n"
            "B. MÓDULOS HABILITADOS EN ESTA CORRIDA\n"
            f"   [ {'X' if cfg_m.get('aplica_exploracion', True) else ' '} ] Exploración TdR 1.5.2      "
            f"[ {'X' if cfg_m.get('aplica_socavacion', False) else ' '} ] Socavación TdR 1.5.6       "
            f"[ {'X' if tiene_etapa1 else ' '} ] Etapa 1: Propuesta Inicial\n"
            f"   [ {'X' if tiene_etapa2 else ' '} ] Etapa 2: Revisión Apoyos   "
            f"[ {'X' if r_emp.get('aplica', False) else ' '} ] Empujes Muros (Mononobe)   "
            f"[ {'X' if r_ter.get('aplica', False) else ' '} ] Terraplenes y Excavaciones\n\n"
            + txt_exp + txt_soc
        )
        fig.text(0.06, 0.84, texto_pg1, va='top', ha='left', fontsize=7.6, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA(S) 2: MODELO ESTRATIGRÁFICO
        for idx_e, df_sub in enumerate(bloques_est):
            fig = plt.figure(figsize=(8.5, 11))
            suf_e = f" (Parte {idx_e + 1}/{len(bloques_est)})" if len(bloques_est) > 1 else ""
            crear_encabezado_sict(fig, f"ESTRATIGRAFÍA Y PROPIEDADES MECÁNICAS{suf_e}",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            fig.text(0.05, 0.84, f"2. MODELO ESTRATIGRÁFICO DEL SITIO DE CRUCE{suf_e}",
                     fontsize=8.5, weight='bold', color='navy')

            headers_e = ["Prof. (m)", "SUCS", "Tipo", "SPT / RQD", "γ\n(kN/m³)", "c / Su\n(kPa)", "φ\n(°)", "Es\n(kPa)", "Cc / e0"]
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

            _dibujar_tabla_ajustada(
                fig, headers_e, rows_e, x_left=0.05, y_top=0.81, width=0.90, max_height=0.73,
                col_widths=[0.14, 0.08, 0.13, 0.11, 0.10, 0.10, 0.09, 0.12, 0.13],
                color_header='navy', font_sz=7.1 if len(rows_e) > 20 else 7.5
            )
            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA: DESGLOSE DE CONSIDERACIONES GEOTÉCNICAS
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_sict(fig, "CONSIDERACIONES GEOTÉCNICAS Y DEDUCCIÓN DE PARÁMETROS",
                              contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

        fig.text(0.05, 0.84, "2B. DESGLOSE DE CORRECCIONES SPT (CE, CR, CB, CS, CN), CONSISTENCIA Y ORIGEN DE PARÁMETROS",
                 fontsize=8.2, weight='bold', color='navy')

        hdr_cg = ["Prof. (m)", "SUCS", "N_camp", "CE/CR/CB/CS", "N60", "CN", "(N1)60", "σ'v\n(kPa)", "Estado /\nCompacidad", "Origen\nParámetros"]
        rows_cg = []
        for _, r in df_tramos.head(18).iterrows():
            nc_s = f"{r['N_campo']:.0f}" if pd.notna(r.get('N_campo', np.nan)) else "-"
            n60_s = f"{r['N60']:.1f}" if pd.notna(r.get('N60', np.nan)) else "-"
            cn_s = f"{r['CN']:.2f}" if pd.notna(r.get('CN', np.nan)) else "-"
            n1_s = f"{r['N1_60']:.1f}" if pd.notna(r.get('N1_60', np.nan)) else "-"
            if pd.notna(r.get('CE', np.nan)):
                fac_s = f"{r['CE']:.2f}/{r['CR']:.2f}/{r['CB']:.2f}/{r['CS']:.2f}"
            else:
                fac_s = "Lab. PCA"
            rows_cg.append([
                f"{r['Prof_ini']:.1f}-{r['Prof_fin']:.1f}",
                str(r['SUCS']),
                nc_s,
                fac_s,
                n60_s,
                cn_s,
                n1_s,
                f"{r['Sigma_v0_eff']:.1f}",
                str(r.get('Estado_Comp', 'S/D'))[:14],
                str(r.get('Origen_Param', 'SPT/Lab'))[:16]
            ])

        y_bot_cg = _dibujar_tabla_ajustada(
            fig, hdr_cg, rows_cg, x_left=0.05, y_top=0.82, width=0.90, max_height=0.38,
            col_widths=[0.10, 0.07, 0.07, 0.14, 0.07, 0.06, 0.07, 0.08, 0.16, 0.18],
            color_header='#1f4e78', font_sz=6.6
        )

        txt_consideraciones = (
            "CONSIDERACIONES GEOTÉCNICAS Y CRITERIOS DE MODELADO (TdR SICT / AASHTO LRFD):\n"
            "====================================================================================\n"
            "1. Corrección de Golpes SPT: N60 = min(N' · CE · CR · CB · CS, 50) y (N1)60 = min(N60 · CN, 50),\n"
            "   con CN = min(sqrt(100 / sigma'_v), 1.70). En muestras inalteradas (PCA) se emplean directamente\n"
            "   los parámetros de resistencia al corte (c, phi) y módulo secante (Es) obtenidos en laboratorio.\n"
            "2. Correlaciones de Resistencia y Deformabilidad (cuando no existe prueba triaxial directa):\n"
            "   - Suelos Friccionantes: phi = min(44°, 27° + 0.30·(N1)60) [Peck]; Es derivado de N60 [Skempton].\n"
            "   - Suelos Cohesivos: Su = 6.0 · N60 (kPa); Es = 300 · Su; Cc = 0.009·(LL - 10) [Terzaghi].\n"
            "3. Factores de Resistencia AASHTO LRFD (Tabla 10.5.5.2.4-1 — O'Neill & Reese, 1999):\n"
            "   - Cohesivos (Método alfa):  phi_qs = 0.45 (fuste comp.) | phi_up = 0.35 (tensión) | phi_qp = 0.40 (punta).\n"
            "   - Granulares (Método beta): phi_qs = 0.55 (fuste comp.) | phi_up = 0.45 (tensión) | phi_qp = 0.50 (punta).\n"
            "   - Roca (Horvath & Kenney):  phi_qs = 0.55 (fuste comp.) | phi_up = 0.40 (tensión) | phi_qp = 0.50 (punta).\n"
            "4. Zonas de Exclusión Obligatorias en Pilas Perforadas (FHWA-NHI-10-016 / AASHTO):\n"
            "   - Se anulan los primeros 1.50 m de fuste bajo el terreno (o nivel socavado) y 1.0·D arriba de la punta.\n"
            "5. Regla Normativa de Profundidad de Desplante (TdR 1.5.8): Si Df > 4.00 m en zapata superficial,\n"
            "   es obligatorio analizar y proponer cimentación profunda para autorización en Minuta IV."
        )
        fig.text(0.05, min(y_bot_cg - 0.03, 0.41), txt_consideraciones, va='top', ha='left', fontsize=7.2, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # ETAPA 1: PROPUESTA INICIAL (MATRICES + GRÁFICAS)
        if tiene_etapa1:
            mat_c = prop_ini['mat_pila_comp_ton']
            mat_t = prop_ini['mat_pila_tens_ton']
            mat_z = prop_ini['mat_zap_qadm_tm2']
            df_p_prop = prop_ini['df_pilas']
            df_z_prop = prop_ini['df_zapatas']

            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_sict(fig, "ETAPA 1: PROPUESTA INICIAL DE CAPACIDAD DE CARGA (AASHTO LRFD)",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

            y_cur = 0.84
            d_cols = mat_c.columns.tolist()
            hdr_pilas = ["Longitud L (m)", "L efec. aprox (m)"] + [f"D = {d:.2f} m" for d in d_cols]

            fig.text(0.05, y_cur, "3A. PROPUESTA INICIAL — CAPACIDAD A COMPRESIÓN DE PILAS INDIVIDUALES R_R (Toneladas, AASHTO LRFD)",
                     fontsize=8.1, weight='bold', color='navy')
            rows_mc = []
            for l_idx in mat_c.index:
                l_ef_aprox = max(0.0, l_idx - 1.50 - float(np.median(d_cols)))
                rows_mc.append([f"{l_idx:.1f} m", f"{l_ef_aprox:.1f} m"] + [f"{v:.1f} t" for v in mat_c.loc[l_idx].values])
            y_cur = _dibujar_tabla_ajustada(fig, hdr_pilas, rows_mc, 0.05, y_cur - 0.015, 0.90, 0.23, color_header='navy', font_sz=7.3) - 0.035

            fig.text(0.05, y_cur, "3B. PROPUESTA INICIAL — CAPACIDAD A TENSIÓN / EXTRACCIÓN DE PILAS INDIVIDUALES R_T (Toneladas, AASHTO LRFD)",
                     fontsize=8.1, weight='bold', color='#7030a0')
            rows_mt = []
            for l_idx in mat_t.index:
                l_ef_aprox = max(0.0, l_idx - 1.50 - float(np.median(d_cols)))
                rows_mt.append([f"{l_idx:.1f} m", f"{l_ef_aprox:.1f} m"] + [f"{v:.1f} t" for v in mat_t.loc[l_idx].values])
            y_cur = _dibujar_tabla_ajustada(fig, hdr_pilas, rows_mt, 0.05, y_cur - 0.015, 0.90, 0.23, color_header='#7030a0', font_sz=7.3) - 0.035

            if not mat_z.empty:
                fig.text(0.05, y_cur, "3C. ALTERNATIVA PRELIMINAR SUPERFICIAL — CAPACIDAD ADMISIBLE q_adm EN ZAPATAS (t/m² y [kg/cm²], Df <= 4.0 m)",
                         fontsize=8.0, weight='bold', color='#1f4e78')
                b_cols = mat_z.columns.tolist()
                hdr_zap = ["Desplante Df (m)"] + [f"Ancho B = {b:.2f} m" for b in b_cols]
                mat_z_kg = prop_ini['mat_zap_qadm_kgcm2']
                rows_mz = []
                for df_i in mat_z.index:
                    fila_z = [f"{df_i:.2f} m"]
                    for b_c in b_cols:
                        fila_z.append(f"{mat_z.loc[df_i, b_c]:.1f} [{mat_z_kg.loc[df_i, b_c]:.2f}]")
                    rows_mz.append(fila_z)
                _dibujar_tabla_ajustada(fig, hdr_zap, rows_mz, 0.05, y_cur - 0.015, 0.90, 0.20, color_header='#1f4e78', font_sz=7.2)

            pdf.savefig(fig); plt.close(); contador += 1

            # Curvas Etapa 1
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_sict(fig, "ETAPA 1: GRÁFICAS DE CAPACIDAD POR LONGITUD Y DIÁMETRO",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

            ax_p1 = fig.add_axes([0.10, 0.50, 0.37, 0.31])
            for d_v, grp in df_p_prop.groupby('D_m'):
                ax_p1.plot(grp['L_m'], grp['R_comp_ton'], marker='o', lw=1.7, label=f"D = {d_v:.2f} m")
            ax_p1.set_title("Pilas Individuales: Compresión R_R vs L", fontsize=8.5, weight='bold')
            ax_p1.set_xlabel("Longitud de Pila L (m)", fontsize=8)
            ax_p1.set_ylabel("Capacidad Compresión (t)", fontsize=8)
            ax_p1.grid(True, linestyle='--', alpha=0.6)
            ax_p1.legend(fontsize=6.8)

            ax_p2 = fig.add_axes([0.56, 0.50, 0.37, 0.31])
            for d_v, grp in df_p_prop.groupby('D_m'):
                ax_p2.plot(grp['L_m'], grp['R_tens_ton'], marker='s', linestyle='--', lw=1.7, label=f"D = {d_v:.2f} m")
            ax_p2.set_title("Pilas Individuales: Tensión R_T vs L", fontsize=8.5, weight='bold')
            ax_p2.set_xlabel("Longitud de Pila L (m)", fontsize=8)
            ax_p2.set_ylabel("Capacidad Extracción (t)", fontsize=8)
            ax_p2.grid(True, linestyle='--', alpha=0.6)
            ax_p2.legend(fontsize=6.8)

            ax_p3 = fig.add_axes([0.10, 0.10, 0.37, 0.31])
            for l_v, grp in df_p_prop.groupby('L_m'):
                ax_p3.plot(grp['D_m'], grp['Kv_cabeza_t_cm'], marker='^', lw=1.6, label=f"L = {l_v:.1f} m")
            ax_p3.set_title("Rigidez Axial en Cabeza Kv vs Diámetro", fontsize=8.5, weight='bold')
            ax_p3.set_xlabel("Diámetro D (m)", fontsize=8)
            ax_p3.set_ylabel("Rigidez Kv (t/cm)", fontsize=8)
            ax_p3.grid(True, linestyle='--', alpha=0.6)
            ax_p3.legend(fontsize=6.8)

            ax_p4 = fig.add_axes([0.56, 0.10, 0.37, 0.31])
            if not df_z_prop.empty:
                for df_v, grp in df_z_prop.groupby('Df_m'):
                    ax_p4.plot(grp['B_m'], grp['q_adm_tm2'], marker='d', lw=1.6, label=f"Df = {df_v:.2f} m")
            ax_p4.set_title("Zapatas Preliminares: q_adm (t/m²) vs Ancho B", fontsize=8.5, weight='bold')
            ax_p4.set_xlabel("Ancho de Zapata B (m)", fontsize=8)
            ax_p4.set_ylabel("Capacidad q_adm (t/m²)", fontsize=8)
            ax_p4.grid(True, linestyle='--', alpha=0.6)
            ax_p4.legend(fontsize=6.8)

            pdf.savefig(fig); plt.close(); contador += 1

        # DESGLOSE DETALLADO POR CASO + BALASTO METRO A METRO (ESTILO MEMORIA DE PILAS)
        for idx_c, dc in enumerate(desgloses_det):
            # Hoja 1 de cada caso: Desglose Axial
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_sict(fig, f"DESGLOSE CAPACIDAD AXIAL (Caso {idx_c + 1} de {len(desgloses_det)})",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

            txt_dc = (
                f"3D. MEMORIA DE CÁLCULO DETALLADA — CAPACIDAD AXIAL (Caso {idx_c + 1})\n"
                f"====================================================================================\n"
                f" > PILA PERFORADA: Diámetro D = {dc['D']:.2f} m | Longitud L = {dc['L']:.2f} m\n"
                f"   Perímetro Fuste: {dc['Perimetro']:.2f} m | Área Punta (Ap): {dc['Area_punta']:.3f} m²\n"
                f"   Volumen Concreto: {dc['Volumen']:.2f} m³ | Peso Neto (W): {dc['W_ton']:.1f} t\n"
                f"   Zona Activa de Fuste: {dc['z_act_ini']:.2f} m a {dc['z_act_fin']:.2f} m (Longitud Efectiva = {dc['L_efec']:.2f} m)\n\n"
                f"A. CAPACIDAD REDUCIDA POR FRICCIÓN LATERAL (AASHTO LRFD — O'Neill & Reese):\n"
                f"   => Capacidad Reducida por Fricción a Compresión (Cf) = {dc['Cf_comp_ton']:.1f} toneladas\n\n"
                f"B. CAPACIDAD REDUCIDA EN PUNTA (Cota de Desplante -{dc['L']:.2f} m):\n"
                f"   => Capacidad Reducida por Punta a Compresión (Cp) = {dc['Cp_comp_ton']:.1f} toneladas\n\n"
                f"C. ESTADO LÍMITE DE FALLA A COMPRESIÓN (R_R = Cf + Cp):\n"
                f"   => CAPACIDAD RESISTENTE REDUCIDA TOTAL (R_R) = {dc['R_comp_ton']:.1f} TONELADAS\n\n"
                f"D. REVISIÓN A TENSIÓN / EXTRACCIÓN (R_T = Cf_tens + 0.90·W):\n"
                f"   - Fricción reducida a tensión: Cf_tens = {dc['Cf_tens_ton']:.1f} t (Punta Cp = 0.0 t)\n"
                f"   => CAPACIDAD RESISTENTE A TENSIÓN (R_T) = {dc['R_tens_ton']:.1f} TONELADAS\n\n"
                f"E. RIGIDEZ GLOBAL E INTERACCIÓN SUELO-ESTRUCTURA:\n"
                f"   - Módulo de balasto lateral promedio en fuste: kh_prom = {dc['kh_prom']:.1f} t/m³\n"
                f"   - Rigidez axial vertical en cabeza (resorte): Kv = {dc['Kv_t_cm']:.2f} t/cm"
            )
            fig.text(0.06, 0.84, txt_dc, va='top', ha='left', fontsize=8.0, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

            # Hoja 2 de cada caso: Balasto y Resortes Metro a Metro
            fig = plt.figure(figsize=(8.5, 11))
            n_m_tot = len(dc['filas_metro'])
            crear_encabezado_sict(fig, f"BALASTO Y RESORTES METRO A METRO (1 a {n_m_tot} m — Caso {idx_c + 1})",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

            fig.text(0.05, 0.84,
                     f"3E. COEFICIENTES DE BALASTO (kh, kv) Y RIGIDECES (Kh_lin, Kv_lin) — D = {dc['D']:.2f} m | L = {dc['L']:.1f} m",
                     fontsize=8.0, weight='bold', color='navy')

            hdr_m = ["Prof. (m)", "SUCS", "Tipo", "N60", "kh (t/m³)", "Kh lin (t/m)", "kv (t/m³)", "Kv lin (t/m)"]
            rows_m = [
                [
                    f"{fm['z_m']:.2f} m", fm['sucs'], fm['tipo'][:11], f"{fm['n60']:.1f}",
                    f"{fm['kh']:.1f}", f"{fm['Kh_lin']:.1f}", f"{fm['kv']:.1f}", f"{fm['Kv_lin']:.1f}"
                ]
                for fm in dc['filas_metro'][:28]
            ]
            _dibujar_tabla_ajustada(
                fig, hdr_m, rows_m, x_left=0.05, y_top=0.815, width=0.90, max_height=0.73,
                col_widths=[0.12, 0.10, 0.14, 0.09, 0.13, 0.14, 0.13, 0.15],
                color_header='#203764', font_sz=6.9 if len(rows_m) > 20 else 7.4
            )
            pdf.savefig(fig); plt.close(); contador += 1

        # ETAPA 2: REVISIÓN DEFINITIVA MULTI-APOYO
        if tiene_etapa2:
            for idx_b, df_chunk_ap in enumerate(bloques_apoyos):
                fig = plt.figure(figsize=(8.5, 11))
                suf_ap = f" (Parte {idx_b + 1}/{len(bloques_apoyos)})" if len(bloques_apoyos) > 1 else ""
                crear_encabezado_sict(fig, f"ETAPA 2: REVISIÓN DEFINITIVA DE APOYOS ESTRUCTURALES{suf_ap}",
                                      contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

                fig.text(0.05, 0.84, f"4A. REVISIÓN DEFINITIVA DE CAPACIDAD AXIAL (GRUPO AASHTO 10.7.3.9) Y ASENTAMIENTOS POULOS{suf_ap}",
                         fontsize=8.0, weight='bold', color='navy')
                hdr_ap1 = [
                    "Apoyo", "Arreglo\nElegido", "L tot /\nL ef (m)", "V_comp\nAct (t)", "Cap. Grupo\nComp (t)",
                    "T_tens\nAct (t)", "T_máx Pila\nCrít. (t)", "Cap. Pila\nTens. Ef (t)", "Asent.\n(mm)", "Dictamen"
                ]
                rows_ap1 = []
                for _, ra in df_chunk_ap.iterrows():
                    t_crit_str = f"{ra['T_Max_Pila_Crit_ton']:.1f}" if pd.notna(ra['T_Max_Pila_Crit_ton']) else "-"
                    c_tens_str = f"{ra['Cap_Tens_Pila_Ef_ton']:.1f}" if pd.notna(ra['Cap_Tens_Pila_Ef_ton']) else "-"
                    rows_ap1.append([
                        str(ra['Apoyo'])[:14], str(ra['Arreglo'])[:18], f"{ra['L_Total_m']:.1f}/{ra['L_Efectiva_m']:.1f}",
                        f"{ra['V_Comp_Act_ton']:.1f}", f"{ra['Cap_Comp_Grupo_ton']:.1f}", f"{ra['T_Tens_Act_ton']:.1f}",
                        t_crit_str, c_tens_str, f"{ra['Asentamiento_mm']:.1f}", str(ra['Estado'])
                    ])
                y_mid = _dibujar_tabla_ajustada(
                    fig, hdr_ap1, rows_ap1, 0.05, 0.82, 0.90, 0.34,
                    col_widths=[0.11, 0.16, 0.09, 0.09, 0.10, 0.09, 0.10, 0.10, 0.07, 0.09],
                    color_header='navy', font_sz=6.8
                ) - 0.045

                fig.text(0.05, y_mid, f"4B. CONTROL TOPOGRÁFICO DE DESPLANTE (m.s.n.m.), CARGA LATERAL (BROMS) Y PANDEO (DAVISSON){suf_ap}",
                         fontsize=8.0, weight='bold', color='#203764')
                hdr_ap2 = [
                    "Apoyo", "Elev. NTN\n(m.s.n.m.)", "Desplante\nCabezal/Zap", "Desplante\nPilas (msnm)",
                    "H_act\n(t)", "H_adm\nFS=2.0 (t)", "M_máx\n(t·m)", "M_adm\nFS=1.5 (t·m)", "L_mín\nDavisson", "FS\nPandeo"
                ]
                rows_ap2 = []
                for _, ra in df_chunk_ap.iterrows():
                    el_p = f"{ra['Elev_Desplante_Pilas_msnm']:.2f}" if pd.notna(ra['Elev_Desplante_Pilas_msnm']) else "N/A (Zap)"
                    lm_d = f"{ra['L_Min_Davisson_m']:.2f} m" if pd.notna(ra['L_Min_Davisson_m']) else "-"
                    fs_p = f"{ra['FS_Pandeo']:.1f}" if pd.notna(ra['FS_Pandeo']) else "-"
                    rows_ap2.append([
                        str(ra['Apoyo'])[:14], f"{ra['Elev_NTN_msnm']:.2f}", f"{ra['Elev_Desplante_Zap_msnm']:.2f}",
                        el_p, f"{ra['H_Act_ton']:.1f}", f"{ra['H_Adm_Grupo_ton']:.1f}", f"{ra['M_Max_Act_tonm']:.1f}",
                        f"{ra['M_Adm_Grupo_tonm']:.1f}", lm_d, fs_p
                    ])
                _dibujar_tabla_ajustada(
                    fig, hdr_ap2, rows_ap2, 0.05, y_mid - 0.015, 0.90, 0.34,
                    col_widths=[0.11, 0.10, 0.11, 0.11, 0.08, 0.10, 0.09, 0.11, 0.10, 0.09],
                    color_header='#203764', font_sz=6.8
                )
                pdf.savefig(fig); plt.close(); contador += 1

        # ETAPA 3: EMPUJES METRO A METRO, EXCAVACIONES Y TERRAPLENES
        if tiene_etapa3:
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_sict(fig, "EMPUJE DE DISEÑO EN MUROS, TALUDES Y TERRAPLENES",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

            y_c3 = 0.84
            if r_emp.get('aplica', False):
                fig.text(0.05, y_c3,
                         f"5A. EMPUJES SOBRE MUROS / ESTRIBOS DE CONTENCIÓN METRO A METRO (H = {r_emp['H_muro_m']:.2f} m, Ka = {r_emp['Ka']:.3f}, Kae = {r_emp['Kae_mononobe']:.3f})",
                         fontsize=8.0, weight='bold', color='navy')
                df_ez = r_emp['df_empujes_z']
                hdr_ez = df_ez.columns.tolist()
                rows_ez = [[f"{v:.3f}" if i == 1 else f"{v:.2f}" for i, v in enumerate(row_v)] for row_v in df_ez.values]
                y_c3 = _dibujar_tabla_ajustada(
                    fig, hdr_ez, rows_ez, 0.05, y_c3 - 0.015, 0.90, 0.36,
                    col_widths=[0.08, 0.08, 0.11, 0.12, 0.14, 0.12, 0.14, 0.12, 0.09],
                    color_header='navy', font_sz=6.9
                ) - 0.035

            if r_ter.get('aplica', False):
                txt_t3 = (
                    "5B. REVISIÓN DE ESTABILIDAD DE EXCAVACIONES Y TERRAPLENES DE ACCESO (TdR 1.5.7 y 1.4.13)\n"
                    "====================================================================================\n"
                    f"1. Estabilidad de Taludes de Excavación (Método Número de Estabilidad / Culmann):\n"
                    f"   - Profundidad de excavación evaluada: H = {r_ter['H_excavacion_m']:.2f} m | Inclinación propuesta: {r_ter['angulo_talud_deg']:.1f}° ({r_ter['talud_exc_H_V']})\n"
                    f"   - Profundidad máxima sin estabilización especial: H_máx = {r_ter['H_max_sin_estab_m']:.2f} m | FS talud = {r_ter['FS_talud_exc']:.2f}\n"
                    f"   - Dictamen excavación: {r_ter['recomendacion_excavacion']}\n\n"
                    f"2. Comportamiento de Terraplenes de Acceso (H = {r_ter['H_terraplen_m']:.2f} m, q_basal = {r_ter['q_terraplen_kpa']:.1f} kPa):\n"
                    f"   - Estabilidad contra falla de fondo: FS_base = {r_ter['FS_base_terraplen']:.2f} ({'CUMPLE >= 1.50' if r_ter['cumple_base_terraplen'] else 'REQUIERE MEJORAMIENTO'})\n"
                    f"   - Asentamiento etapa constructiva (elástico corto plazo):     {r_ter['asent_corto_plazo_cm']:.2f} cm\n"
                    f"   - Asentamiento durante servicio (consolidación largo plazo):  {r_ter['asent_largo_plazo_cm']:.2f} cm (t90 = {r_ter['t90_consolidacion_meses']:.1f} meses)\n"
                    f"   - Asentamiento Total Estimado en Terraplén de Acceso:         {r_ter['asent_total_terraplen_cm']:.2f} cm\n"
                    f"   - Solución de mitigación: {r_ter['mitigacion_terraplen']}"
                )
                fig.text(0.05, y_c3, txt_t3, va='top', ha='left', fontsize=7.5, family='monospace')

            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA OPCIONAL: MINUTA IV (TdR 1.5.9)
        if incluir_minuta4:
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_sict(fig, "PROPUESTA DE CIMENTACIÓN PARA AUTORIZACIÓN — MINUTA IV (TdR 1.5.9)",
                                  contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url,
                                  mostrar_antefirma=False)

            ax_m4 = fig.add_axes([0.05, 0.04, 0.90, 0.81])
            ax_m4.set_xlim(0, 100)
            ax_m4.set_ylim(0, 100)
            ax_m4.axis('off')

            ax_m4.text(50, 98.0, "MINUTA IV — PROPUESTA Y AUTORIZACIÓN DEL TIPO DE CIMENTACIÓN (TdR 1.5.9)",
                       ha='center', va='top', fontsize=9.2, weight='bold', color='navy')
            ax_m4.text(50, 94.8, f"CONTRATO No.: {datos_anexo.get('Contrato', 'S/N')}   |   OBRA: {p_elem[:55]}",
                       ha='center', va='top', fontsize=7.8, weight='bold')

            pi_m4 = resultados.get('propuesta_inicial', {})
            if pi_m4.get('aplica', False) and not pi_m4.get('df_pilas', pd.DataFrame()).empty:
                r_p_min, r_p_max = pi_m4['df_pilas']['R_comp_ton'].min(), pi_m4['df_pilas']['R_comp_ton'].max()
                t_p_min, t_p_max = pi_m4['df_pilas']['R_tens_ton'].min(), pi_m4['df_pilas']['R_tens_ton'].max()
                res_pilas_txt = f"Compresión: {r_p_min:.0f} a {r_p_max:.0f} t/pila | Tensión: {t_p_min:.0f} a {t_p_max:.0f} t/pila"
            else:
                res_pilas_txt = "Evaluada en Etapa 2 según arreglo definitivo"

            if pi_m4.get('aplica', False) and not pi_m4.get('df_zapatas', pd.DataFrame()).empty:
                q_z_min, q_z_max = pi_m4['df_zapatas']['q_adm_kgcm2'].min(), pi_m4['df_zapatas']['q_adm_kgcm2'].max()
                res_zap_txt = f"q_adm = {q_z_min:.2f} a {q_z_max:.2f} kg/cm² (para Df <= 4.00 m)"
            else:
                res_zap_txt = "Sujeta a revisión de Df <= 4.00 m"

            soc_m4_txt = f"Socavación Total = {r_soc['soc_total_m']:.2f} m" if r_soc.get('aplica', False) else "No aplica (Cruce sin cauce fluvial, 0.00 m)"

            hdr_m4 = ["Alternativa de Cimentación", "Rango de Capacidad (AASHTO)", "Condición de Aplicación (TdR 1.5.8 / 1.5.9)", "Viabilidad"]
            rows_m4 = [
                ["1. Cimentación Superficial\n(Zapatas Aisladas / Estribos)", res_zap_txt,
                 "Desplante en terreno natural firme a Df <= 4.00 m,\nlibre de rellenos y verificando volteo/deslizamiento.", "APLICABLE\n(Cargas moderadas)"],
                ["2. Cimentación Profunda\n(Pilas Perforadas / Grupos)", res_pilas_txt,
                 "Recomendada ante cargas elevadas, tensiones altas,\nvolteo sísmico o desplante firme > 4.00 m.", "RECOMENDADA\n(Apoyos críticos)"],
            ]
            _dibujar_tabla_ajustada(
                fig, hdr_m4, rows_m4, x_left=0.05, y_top=0.78, width=0.90, max_height=0.22,
                col_widths=[0.24, 0.24, 0.36, 0.16], color_header='navy', font_sz=7.2
            )

            ax_m4.add_patch(patches.Rectangle((0, 26.0), 100, 38.0, fill=False, edgecolor='black', lw=0.8))
            ax_m4.text(1.5, 62.0, "RESUMEN TÉCNICO Y ACUERDO DE SELECCIÓN DE CIMENTACIÓN (TdR 1.5.9):", fontsize=8.0, weight='bold', color='navy')
            texto_m4 = (
                f"1. Condiciones del sitio: Exploración {p_sondeo} (prof. máx. {float(df_tramos['Prof_fin'].max()):.2f} m) | {soc_m4_txt}.\n"
                f"2. Propuesta Geotécnica Pre-Estructural: Con base en el perfil estratigráfico y los análisis AASHTO LRFD\n"
                f"   de la Etapa 1, se someten a consideración de LA DEPENDENCIA y del área de Estructuras las alternativas\n"
                f"   de cimentación superficial (Df <= 4.00 m) y profunda (pilas perforadas / grupos de pilas) contenidas\n"
                f"   en la presente memoria, junto con sus módulos de reacción (ks, kh, Kv) y empujes en estribos.\n"
                f"3. Resolución / Tipo de Cimentación Autorizado por Apoyo:\n"
                f"   ____________________________________________________________________________________________________\n"
                f"   ____________________________________________________________________________________________________\n"
                f"   ____________________________________________________________________________________________________\n\n"
                f"4. Observaciones y compromisos para Proyecto Constructivo (Etapa VI): Una vez validada la presente Minuta IV\n"
                f"   por todas las partes, se procederá a la revisión definitiva de descargas estructurales por apoyo."
            )
            ax_m4.text(2.0, 59.0, texto_m4, va='top', ha='left', fontsize=7.1, family='monospace')

            resp_nom = datos_anexo.get('Responsable_Tecnico', 'ING. ESPECIALISTA EN GEOTECNIA')
            resp_ced = datos_anexo.get('Cedula_Prof', 'S/D')

            ax_m4.text(25, 19.5, "POR 'LA DEPENDENCIA' (SICT)", ha='center', fontsize=8.0, weight='bold', color='navy')
            ax_m4.plot([6, 44], [9.5, 9.5], color='black', lw=1.0)
            ax_m4.text(25, 7.2, "NOMBRE, CARGO Y FIRMA DE AUTORIZACIÓN", ha='center', fontsize=7.0)

            ax_m4.text(75, 19.5, "POR 'LA CONTRATISTA' (RESPONSABLE TÉCNICO)", ha='center', fontsize=8.0, weight='bold', color='navy')
            ax_m4.plot([56, 94], [9.5, 9.5], color='black', lw=1.0)
            ax_m4.text(75, 7.2, f"{resp_nom}", ha='center', fontsize=7.2, weight='bold')
            ax_m4.text(75, 4.8, f"CÉD. PROF. NÚM.: {resp_ced}", ha='center', fontsize=6.9, color='dimgray')

            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA DE ESQUEMAS Y RECOMENDACIONES CONSTRUCTIVAS
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_sict(fig, "ESQUEMAS Y RECOMENDACIONES DE CONSTRUCCIÓN (TdR 1.5.10)",
                              contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
        dibujar_esquemas_sict(fig, resultados)

        nota_proc = (
            "RECOMENDACIONES CONSTRUCTIVAS PARA PILAS, CABEZALES Y ZAPATAS (TdR 1.5.10):\n"
            "------------------------------------------------------------------------------------\n"
            "1. Control Topográfico y Equipo: Referenciar ejes y niveles antes y después del colado (tolerancia\n"
            "   +-5 cm en longitud y +-1 cm en sección/acero). Emplear perforadora rotatoria con herramienta tipo\n"
            "   bote; evitar hélice continua (auger) bajo el NAF para no descomprimir las paredes.\n"
            "2. Estabilización de Paredes: En estratos granulares sueltos, boleos o bajo NAF emplear ademe metálico\n"
            "   recuperable o lodo bentonítico/polimérico (densidad > 1.04 g/cm³, contenido de arena < 6.0%).\n"
            "3. Acero y Colado con Tubo Tremie: Colocar separadores ('pollos') garantizando recubrimiento libre y\n"
            "   dejar puntas de varilla >= 30 cm arriba del fondo limpio de azolves. Colado continuo mediante tubo\n"
            "   Tremie con tapón deslizante ('diablo'), revenimiento 18 a 20 cm, manteniendo la descarga sumergida\n"
            "   al menos 1.0 m en concreto fresco y sobrecolando 40 cm para descabece de concreto contaminado.\n"
            "4. Pruebas de Integridad y Plantilla: Ejecutar pruebas de integridad física en los primeros elementos.\n"
            "   En zapatas y cabezales, colar de inmediato plantilla de concreto pobre f'c = 100 kg/cm² de 5 cm."
        )
        fig.text(0.05, 0.38, nota_proc, va='top', ha='left', fontsize=7.4, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA OPCIONAL: CÉDULA ANEXO OFICIAL SICT
        if incluir_anexo_sict:
            fig = plt.figure(figsize=(8.5, 11))
            dibujar_pagina_anexo_oficial_sict(
                fig, contador, total_paginas, df_tramos, resultados, pruebas_det, datos_anexo, logo_url
            )
            pdf.savefig(fig); plt.close(); contador += 1

    return pdf_buffer.getvalue()
