import io
import os
import math
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
# 0. UTILIDAD DE CARGA DE LOGO (URL REMOTA O ARCHIVO LOCAL)
# ==========================================================
_CACHE_LOGOS = {}

def _normalizar_url_imagen(url):
    """Convierte enlaces compartidos (Google Drive, Dropbox, GitHub) en enlaces de descarga directa."""
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

def cargar_imagen_logo(logo_source):
    """
    Carga una imagen de logotipo desde:
      1. Una URL web (http:// o https://, incluyendo Google Drive, Dropbox y GitHub).
      2. Una ruta de archivo local especificada en LogoURL.
      3. Respaldo automatico a 'logo_empresa.png'.
    Cachea el resultado en memoria para evitar descargas repetidas por pagina.
    """
    key = str(logo_source).strip() if (logo_source is not None and not pd.isna(logo_source)) else ''
    if key.lower() in ('', 'nan', 'none', 'null'):
        key = 'logo_empresa.png'

    if key in _CACHE_LOGOS:
        return _CACHE_LOGOS[key]

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
                pil_img = Image.open(io.BytesIO(raw_bytes)).convert('RGBA')
                arr = np.asarray(pil_img)
                _CACHE_LOGOS[key] = arr
                return arr
            except Exception:
                continue

        if os.path.exists(src):
            try:
                pil_img = Image.open(src).convert('RGBA')
                arr = np.asarray(pil_img)
                _CACHE_LOGOS[key] = arr
                return arr
            except Exception:
                continue

    _CACHE_LOGOS[key] = None
    return None


# ==========================================================
# 1. ENCABEZADO Y MEMBRETE EJECUTIVO (CONFORME A PRODUCCIÓN)
# ==========================================================
def crear_encabezado_memoria_zapata(fig, titulo_pagina, num_pagina, total_paginas,
                                    p_proy, p_elem, p_sondeo, p_fecha, logo_url='logo_empresa.png'):
    ax_logo = fig.add_axes([0.05, 0.88, 0.22, 0.08])
    ax_logo.axis('off')

    img_arr = cargar_imagen_logo(logo_url)
    if img_arr is not None:
        ax_logo.imshow(img_arr, aspect='equal')
    else:
        ax_logo.text(0.5, 0.5, '[ LOGO EMPRESA ]', ha='center', va='center', fontsize=8, color='navy', weight='bold')

    fig.text(0.30, 0.940, f"PROYECTO: {p_proy}", fontsize=10.0, weight='bold', color='navy')
    fig.text(0.30, 0.922, f"ELEMENTO: {p_elem}", fontsize=8.5)
    fig.text(0.30, 0.904, f"EXPLORACIÓN: {p_sondeo}", fontsize=8.5)
    fig.text(0.30, 0.884, f"MEMORIA TÉCNICA: {titulo_pagina}", fontsize=8.0, color='dimgray')

    if not p_fecha or str(p_fecha).strip().lower() == 'nan':
        p_fecha = datetime.datetime.now().strftime("%B %Y").upper()
    fig.text(0.95, 0.940, f"FECHA: {p_fecha}", ha='right', fontsize=8.5)
    fig.text(0.95, 0.904, f"PÁGINA: {num_pagina} / {total_paginas}", ha='right', fontsize=9, weight='bold')
    fig.lines.append(plt.Line2D([0.05, 0.95], [0.870, 0.870], transform=fig.transFigure, color='black', lw=1.5))


# ==========================================================
# 2. ESQUEMA GEOMÉTRICO PARAMÉTRICO DE ZAPATA Y BULBO
# ==========================================================
def dibujar_esquema_zapata(fig, Df_rep, B_rep, naf_m, metodo_exp, ubicacion_lbl, margen_pct):
    ax1 = fig.add_axes([0.08, 0.44, 0.42, 0.38])
    ax2 = fig.add_axes([0.55, 0.44, 0.38, 0.38])

    ax1.set_title("Esquema Paramétrico de Zapata Superficial\n(Sobrecarga pv y Bulbo de Presiones)", fontsize=9.5, weight='bold')
    z_max_plot = max(Df_rep + 2.0 * B_rep + 0.6, 4.0)
    ax1.set_xlim(-3.2, 3.2)
    ax1.set_ylim(-z_max_plot, 1.2)

    ax1.axhline(0, color='brown', lw=2.0)
    ax1.text(2.9, 0.15, "N.T.N. (±0.00 m)", fontsize=7.5, color='brown', weight='bold', ha='right')

    w_dado = min(0.45, B_rep * 0.35)
    dado = patches.Rectangle((-w_dado / 2, -Df_rep + 0.35), w_dado, Df_rep,
                             linewidth=1.3, edgecolor='black', facecolor='#d9d9d9', zorder=3)
    zapata = patches.Rectangle((-B_rep / 2, -Df_rep), B_rep, 0.35,
                               linewidth=1.5, edgecolor='black', facecolor='#cccccc', zorder=4)
    ax1.add_patch(dado)
    ax1.add_patch(zapata)

    if naf_m is not None and naf_m < z_max_plot:
        ax1.axhline(-naf_m, color='blue', lw=1.2, linestyle='-.', zorder=5)
        ax1.text(2.9, -naf_m + 0.12, f"N.A.F. (-{naf_m:.2f} m)", fontsize=7.5, color='blue', weight='bold', ha='right')
        ax1.plot([1.8], [-naf_m], marker='v', color='blue', markersize=5)

    z_bulbo = Df_rep + 1.5 * B_rep
    bulbo_rect = patches.Rectangle((-B_rep * 0.85, -z_bulbo), B_rep * 1.70, 1.5 * B_rep,
                                   linewidth=1.0, edgecolor='navy', facecolor='#e8eef7', linestyle='--', zorder=1)
    ax1.add_patch(bulbo_rect)
    ax1.text(0, -(Df_rep + 0.75 * B_rep), f"Bulbo Activo\n(1.5·B a 2.0·B)\n[{metodo_exp}]",
             ha='center', va='center', fontsize=7.5, color='navy', weight='bold', zorder=2)

    x_cota = -B_rep / 2 - 0.55
    ax1.annotate('', xy=(x_cota, 0), xytext=(x_cota, -Df_rep), arrowprops=dict(arrowstyle='<->', color='darkgreen', lw=1.4))
    ax1.text(x_cota - 0.12, -Df_rep / 2, f"Desplante\nDf = {Df_rep:.2f} m", fontsize=7.5, color='darkgreen', weight='bold', ha='right', va='center')

    ax1.annotate('', xy=(-B_rep / 2, -Df_rep - 0.25), xytext=(B_rep / 2, -Df_rep - 0.25),
                 arrowprops=dict(arrowstyle='<->', color='black', lw=1.3))
    ax1.text(0, -Df_rep - 0.52, f"Ancho B = {B_rep:.2f} m", fontsize=7.5, weight='bold', ha='center')
    ax1.axis('off')

    ax2.set_title("Interacción Suelo-Cimentación (NTC-CDMX 2023)\n(Ecuaciones Separadas Cohesivo/Friccionante + Servicio)", fontsize=9.0, weight='bold')
    ax2.set_xlim(-3.0, 3.0)
    ax2.set_ylim(-6.4, 2.0)

    ax2.annotate('', xy=(0, 0.2), xytext=(0, 1.5), arrowprops=dict(arrowstyle='->', color='darkred', lw=2.2))
    ax2.text(0.25, 1.0, "Carga Recomendada q_rec", fontsize=8.0, color='darkred', weight='bold')

    zap2 = patches.Rectangle((-1.6, -0.5), 3.2, 0.7, facecolor='#d9d9d9', edgecolor='black', lw=1.5)
    ax2.add_patch(zap2)
    ax2.text(0, -0.15, f"Zapata {ubicacion_lbl}", ha='center', va='center', fontsize=7.8, weight='bold')

    for x_s in [-1.2, -0.6, 0.0, 0.6, 1.2]:
        ax2.annotate('', xy=(x_s, -0.5), xytext=(x_s, -2.4), arrowprops=dict(arrowstyle='<->', color='navy', lw=1.5))
    ax2.axhline(-2.4, color='brown', lw=1.8)
    ax2.text(0, -3.0, "Módulo de Balasto Vertical ks (t/m³)", ha='center', fontsize=8.5, color='navy', weight='bold')
    ax2.text(0, -3.8, "Deformación Elástica: Se = [q_neta · B · (1 - nu²) · If] / Es_sec", ha='center', fontsize=7.8, color='darkgreen')
    ax2.text(0, -5.1, f"Criterio Gobernante (NTC-CDMX 2023 Num. 3.5.1):\nq_rec = min(r_CDMX, q_adm_corte, q_adm_def)\nControl Servicio: Se <= {margen_pct:.0f}% Se_máx",
             ha='center', fontsize=7.5, bbox=dict(boxstyle='round,pad=0.35', facecolor='#fff3cd', edgecolor='orange'))
    ax2.axis('off')


# ==========================================================
# 3. FUNCIÓN PRINCIPAL GENERADORA DE MEMORIA PDF ZAPATAS
# ==========================================================
def generar_memoria_zapatas_pdf(df_tramos, analisis_zap, p_proy, p_elem, *args, **kwargs):
    if len(args) >= 2:
        p_sondeo = str(args[0])
        p_fecha = str(args[1])
    elif len(args) == 1:
        p_sondeo = str(kwargs.get('p_sondeo', 'SONDEO / PCA'))
        p_fecha = str(args[0])
    else:
        p_sondeo = str(kwargs.get('p_sondeo', 'SONDEO / PCA'))
        p_fecha = str(kwargs.get('p_fecha', ''))

    logo_url = kwargs.get('logo_url', 'logo_empresa.png')

    pdf_buffer = io.BytesIO()

    df_res = analisis_zap['df_completo']
    df_corr = analisis_zap['df_corridas']
    df_ais = analisis_zap['df_aisladas']
    metodo_exp = analisis_zap.get('metodo_exploracion', 'SPT')
    criterio_suelo = analisis_zap.get('criterio_suelo_ntc', 'Automatico')
    FS_val = analisis_zap.get('FS', 3.0)
    nu_val = analisis_zap.get('nu', 0.30)
    fr_val = analisis_zap.get('fr_cdmx', 0.65)
    es_colindante = analisis_zap.get('es_colindante', False)
    se_max_corr = analisis_zap.get('se_max_corrida_cm', 2.5)
    se_max_ais = analisis_zap.get('se_max_aislada_cm', 5.0)
    margen_pct = analisis_zap.get('factor_margen_se', 0.80) * 100.0
    naf_m = analisis_zap.get('naf_m', None)

    ubicacion_lbl = "Colindante (FR=0.35)" if es_colindante else "Interior (FR=0.65)"

    def _bloque_texto_caso(r):
        if r['metodo'].upper() == 'SPT' and pd.notna(r.get('N1_60')):
            param_linea = (
                f"   - Parámetros SPT en bulbo (h={r['h_bulbo']:.2f}m): "
                f"N60={r['N60']:.1f}, Cn={r['Cn']:.3f}, (N1)60={r['N1_60']:.1f} | "
                f"phi_ef={r['phi_efec']:.2f}°, c={r['c_kpa']:.1f} kPa, Es_sec={r['Es_kpa']:.0f} kPa"
            )
        else:
            param_linea = (
                f"   - Parámetros Lab. PCA en bulbo (h={r['h_bulbo']:.2f}m): "
                f"c={r['c_kpa']:.2f} kPa, phi_ef={r['phi_efec']:.2f}°, "
                f"gamma_ef={r['gamma_cuna']:.2f} kN/m³, Es_sec={r['Es_kpa']:.0f} kPa"
            )

        has_coh_val = 'q_corte_coh_kgcm2' in r and pd.notna(r['q_corte_coh_kgcm2'])
        has_fricc_val = 'q_corte_fricc_kgcm2' in r and pd.notna(r['q_corte_fricc_kgcm2'])
        if has_coh_val and has_fricc_val:
            comp_ecuaciones = (
                f"   - Revisión NTC-CDMX 3.5.1 (Ecuaciones Separadas — Criterio: {criterio_suelo}):\n"
                f"     * Hipótesis Puramente Cohesiva (phi=0):     r_coh={r['r_coh_kgcm2']:.2f} | q_corte={r['q_corte_coh_kgcm2']:.2f} kg/cm²\n"
                f"     * Hipótesis Puramente Friccionante (c=0):   r_fricc={r['r_fricc_kgcm2']:.2f} | q_corte={r['q_corte_fricc_kgcm2']:.2f} kg/cm²\n"
                f"     => Modelo Adoptado: {r['modelo_suelo_aplicado']} | q_corte = {r['q_adm_corte_kgcm2']:.2f} kg/cm² (Se_corte = {r['Se_corte_mm']:.1f} mm)\n"
            )
        else:
            mod_lbl = r.get('modelo_suelo_aplicado', 'NTC-CDMX 3.5.1')
            comp_ecuaciones = (
                f"   - Modelo Normativo NTC-CDMX 3.5.1 ({mod_lbl}, FR={r['fr_cdmx']:.2f}): "
                f"r_CDMX = {r['r_cdmx_kgcm2']:.2f} kg/cm² | q_corte (FS={r['FS']:.1f}) = {r['q_adm_corte_kgcm2']:.2f} kg/cm² (Se_corte = {r['Se_corte_mm']:.1f} mm)\n"
            )

        return (
            f" > ZAPATA {r['tipo_zapata'].upper()} | B = {r['B']:.2f} m | Df = {r['Df']:.2f} m | pv = {r['pv_kpa']:.2f} kPa\n"
            f"{param_linea}\n"
            f"{comp_ecuaciones}"
            f"   - Control Servicio ({r['margen_se_pct']:.0f}% de Se_máx = {r['Se_obj_mm']:.1f} mm): q_def = {r['q_adm_def_kgcm2']:.2f} kg/cm²\n"
            f"   => CAPACIDAD RECOMENDADA [{r['criterio_gobernante']}]: q_rec = {r['q_rec_kgcm2']:.2f} kg/cm² ({r['q_rec_tonm2']:.1f} t/m²)\n"
            f"   => DEFORMACIÓN ESPERADA REAL: Se = {r['Se_final_mm']:.1f} mm ({r['pct_se_max']:.0f}% de Se_máx) | BALASTO: ks = {r['ks_ton_m3']:.0f} t/m³ ({r['ks_kg_cm3']:.2f} kg/cm³)\n\n"
        )

    textos_corr = [_bloque_texto_caso(row) for _, row in df_corr.iterrows()]
    textos_ais = [_bloque_texto_caso(row) for _, row in df_ais.iterrows()]

    def _paginar(lista_txt, por_pag=4):
        return ["".join(lista_txt[i:i + por_pag]) for i in range(0, len(lista_txt), por_pag)]

    pags_corr = _paginar(textos_corr, 4)
    pags_ais = _paginar(textos_ais, 4)

    # Paginacion dinamica de estratos
    FILAS_ESTRATOS_PAG = 32
    bloques_estratos = [df_tramos.iloc[i:i + FILAS_ESTRATOS_PAG] for i in range(0, max(1, len(df_tramos)), FILAS_ESTRATOS_PAG)]

    # Paginacion dinamica de TODAS las zapatas analizadas en las tablas resumen (sin recortar filas)
    MAX_FILAS_TABLA_PAG = 24
    MAX_FILAS_CON_DICTAMEN = 20

    modo_compacto_una_hoja = (not df_corr.empty or not df_ais.empty) and (len(df_corr) <= 9 and len(df_ais) <= 9)

    if modo_compacto_una_hoja:
        num_pags_resumen = 1
        dictamen_en_hoja_aparte = False
    else:
        bloques_tabla_corr = [df_corr.iloc[i:i + MAX_FILAS_TABLA_PAG] for i in range(0, len(df_corr), MAX_FILAS_TABLA_PAG)] if not df_corr.empty else []
        bloques_tabla_ais = [df_ais.iloc[i:i + MAX_FILAS_TABLA_PAG] for i in range(0, len(df_ais), MAX_FILAS_TABLA_PAG)] if not df_ais.empty else []
        todos_bloques = bloques_tabla_corr + bloques_tabla_ais
        if not todos_bloques:
            num_pags_resumen = 1
            dictamen_en_hoja_aparte = False
        else:
            ult_len = len(todos_bloques[-1])
            dictamen_en_hoja_aparte = (ult_len > MAX_FILAS_CON_DICTAMEN)
            num_pags_resumen = len(todos_bloques) + (1 if dictamen_en_hoja_aparte else 0)

    total_paginas = 1 + len(bloques_estratos) + 1 + len(pags_corr) + len(pags_ais) + 1 + num_pags_resumen

    cols_res = [
        "Df\n(m)", "B\n(m)", "Modelo\nSuelo", "q_corte\n(kg/cm²)", "Se_corte\n(mm)",
        "q_def\n(kg/cm²)", "Criterio\nGobernante", "q_rec\n(kg/cm²)", "Se_rec\n(mm)", "ks\n(t/m³)"
    ]
    anchos_cols_res = [0.06, 0.06, 0.11, 0.09, 0.09, 0.09, 0.20, 0.09, 0.09, 0.12]

    def _cortar_modelo(m_txt):
        return "Cohesivo" if "Cohesiv" in str(m_txt) else "Friccionante"

    def _armar_filas_resumen(df_chunk):
        return [[
            f"{r['Df']:.2f}", f"{r['B']:.2f}", _cortar_modelo(r.get('modelo_suelo_aplicado', '')),
            f"{r['q_adm_corte_kgcm2']:.2f}", f"{r['Se_corte_mm']:.1f}",
            f"{r['q_adm_def_kgcm2']:.2f}", r['criterio_gobernante'], f"{r['q_rec_kgcm2']:.2f}",
            f"{r['Se_final_mm']:.1f}", f"{r['ks_ton_m3']:.0f}"
        ] for _, r in df_chunk.iterrows()]

    def _dibujar_tabla_en_caja(fig, df_chunk, y_top, max_h_disp, color_header):
        n_f = len(df_chunk)
        h_ideal = (n_f + 1.45) * 0.0255
        h_caja = min(max_h_disp, h_ideal)
        ax_t = fig.add_axes([0.05, y_top - h_caja, 0.90, h_caja])
        ax_t.axis('off')

        filas_txt = _armar_filas_resumen(df_chunk)
        tabla = ax_t.table(
            cellText=[cols_res] + filas_txt,
            bbox=[0.0, 0.0, 1.0, 1.0],
            cellLoc='center',
            colWidths=anchos_cols_res
        )
        tabla.auto_set_font_size(False)
        tabla.set_fontsize(6.8 if n_f > 20 else 7.2)

        total_unidades = n_f + 1.45
        h_header_rel = 1.45 / total_unidades
        h_fila_rel = 1.0 / total_unidades

        for (r_idx, c_idx), cell in tabla.get_celld().items():
            cell.set_linewidth(0.5)
            if r_idx == 0:
                cell.set_height(h_header_rel)
                cell.set_facecolor(color_header)
                cell.set_text_props(color='white', weight='bold')
            else:
                cell.set_height(h_fila_rel)
                if r_idx % 2 == 0:
                    cell.set_facecolor('#f4f4f4')
        return y_top - h_caja

    q_min_g = df_res['q_rec_kgcm2'].min() if not df_res.empty else 0.0
    q_max_g = df_res['q_rec_kgcm2'].max() if not df_res.empty else 0.0
    se_max_g = df_res['Se_final_mm'].max() if not df_res.empty else 0.0

    nota_dictamen = (
        f"DICTAMEN GEOTÉCNICO Y RECOMENDACIONES DE DISEÑO (NTC-CDMX 2023 | {ubicacion_lbl}):\n"
        f"1. Se evaluaron las ecuaciones separadas de las NTC-CDMX 2023 (Num. 3.5.1) y el control de servicio ({margen_pct:.0f}% de Se_máx).\n"
        f"2. Las capacidades recomendadas gobernantes (q_rec) oscilan entre {q_min_g:.2f} y {q_max_g:.2f} kg/cm², acotando\n"
        f"   la deformación elástica esperada a un máximo de {se_max_g:.1f} mm dentro del margen normativo.\n"
        f"3. Se recomienda desplante sobre terreno natural firme libre de rellenos, con plantilla de concreto f'c = 100 kg/cm²."
    )

    with PdfPages(pdf_buffer) as pdf:
        contador = 1

        # --------------------------------------------------------
        # PÁGINA 1: METODOLOGÍA NORMATIVA NTC-CDMX 2023
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "METODOLOGÍA Y CRITERIOS NORMATIVOS (NTC-CDMX 2023)",
                                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
        texto_pg1 = (
            "1. METODOLOGÍA DE CÁLCULO DE CIMENTACIONES SUPERFICIALES\n"
            "   (NORMA TÉCNICA COMPLEMENTARIA NTC-CDMX 2023 — NUMERAL 3.5.1)\n"
            "====================================================================================\n\n"
            f"A. CARACTERIZACIÓN GEOTÉCNICA MEDIANTE {metodo_exp.upper()}\n"
            "   - Modo SPT: Corrección por sobrecarga Cn = min(2.0, sqrt(100 / sigma'_v)) [Liao & Whitman],\n"
            "     energía y varillaje N60, (N1)60; ángulo de fricción phi = 27.5 + 0.92*sqrt((N1)60) [Wolff],\n"
            "     cohesión no drenada cu = 6.0 * N60.\n"
            "   - Modo PCA (Pozo a Cielo Abierto): Emplea directamente los parámetros de resistencia al esfuerzo\n"
            "     cortante (c, phi) y peso volumétrico (gamma) de muestras inalteradas ensayadas en laboratorio.\n"
            "   - Módulo Elástico Secante (Es_sec): Se emplea directamente el módulo secante obtenido del\n"
            "     ensaye axial/triaxial de laboratorio cuando está disponible, o se estima empíricamente.\n\n"
            "B. SEPARACIÓN NORMATIVA ESTRICTA DE ECUACIONES — NTC-CDMX 2023 (Numeral 3.5.1)\n"
            "   La norma separa el análisis en dos ecuaciones independientes (sin sumar c y phi):\n"
            "   - Ecuación (a) Suelos Cohesivos (phi = 0, esfuerzos totales): r = cu * Nc* * FR + pv_total\n"
            "     donde Nc* = 5.14 * (1 + 0.25*(Df/B) + 0.25*(B/L)), con Df/B <= 2.0 y B/L <= 1.0.\n"
            "   - Ecuación (b) Suelos Friccionantes (c = 0, esfuerzos efectivos): r = [pv_ef*(Nq* - 1) + 0.5*gamma*B*Ng*] * FR + pv_ef\n"
            "     con Nq = exp(pi*tan(phi))*tan^2(45 + phi/2), Ng = 2*(Nq + 1)*tan(phi) [Vesic],\n"
            "     fq = 1 + (B/L)*tan(phi), fg = 1 - 0.4*(B/L).\n"
            f"   - Criterio Aplicado: {criterio_suelo} | FR = {fr_val:.2f} [{ubicacion_lbl}] | FS Corte = {FS_val:.1f}.\n\n"
            "C. ESTADO LÍMITE DE SERVICIO Y CAPACIDAD DE CARGA RECOMENDADA (q_rec)\n"
            "   - Se evalúa la deformación elástica que produciría la carga por corte: Se_corte = q_neta·B·(1-nu²)·If / Es_sec.\n"
            f"   - Para evitar asentamientos excesivos, se fija una deformación objetivo al {margen_pct:.0f}% del límite máximo\n"
            f"     permitido (Se_máx = {se_max_ais*10:.0f} mm en zapatas aisladas; {se_max_corr*10:.0f} mm en zapatas corridas):\n"
            "       Se_obj = (Margen %) * Se_máx   =>   q_adm_def = [Se_obj * Es_sec / (B * (1 - nu²) * If)] + pv\n"
            "   - Capacidad Recomendada Gobernante: q_rec = min(r_CDMX, q_adm_corte, q_adm_def)."
        )
        fig.text(0.08, 0.84, texto_pg1, va='top', ha='left', fontsize=7.9, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA(S) 2: PERFIL ESTRATIGRÁFICO / PARÁMETROS DE DISEÑO
        # --------------------------------------------------------
        for idx_est, df_sub in enumerate(bloques_estratos):
            fig = plt.figure(figsize=(8.5, 11))
            suf_est = f" (Parte {idx_est + 1}/{len(bloques_estratos)})" if len(bloques_estratos) > 1 else ""
            crear_encabezado_memoria_zapata(fig, f"PERFIL GEOTÉCNICO Y PARÁMETROS ({metodo_exp.upper()}){suf_est}",
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            sub_t2 = (
                f"2. PERFIL ESTRATIGRÁFICO Y PARÁMETROS MECÁNICOS DE DISEÑO ({metodo_exp.upper()}){suf_est}\n"
                f"====================================================================================\n"
            )
            fig.text(0.08, 0.84, sub_t2, va='top', ha='left', fontsize=8.0, family='monospace')

            headers_t2 = ["Prof. (m)", "SUCS", "Modelo Estrato", "gamma\n(kN/m³)", "N60 /\n(N1)60", "c\n(kPa)", "phi\n(°)", "Es sec.\n(kPa)"]
            filas_t2 = []
            for _, row in df_sub.iterrows():
                has_n60 = ('N60' in row) and pd.notna(row['N60'])
                if has_n60:
                    n1_v = row['N1_60'] if ('N1_60' in row and pd.notna(row['N1_60'])) else row['N60']
                    spt_str = f"{row['N60']:.0f}/{n1_v:.0f}"
                else:
                    spt_str = "PCA"
                tipo_lbl = str(row['Tipo'])
                if tipo_lbl.startswith('Dual'):
                    tipo_lbl = "Dual (c vs phi)"
                filas_t2.append([
                    f"{row['Prof_ini']:.2f}-{row['Prof_fin']:.2f}",
                    str(row['SUCS']),
                    tipo_lbl[:16],
                    f"{row['Gamma']:.2f}",
                    spt_str,
                    f"{row['c_kPa']:.1f}",
                    f"{row['phi_deg']:.1f}°",
                    f"{row['Es_kPa']:.0f}"
                ])

            n_e = len(filas_t2)
            h_est_box = min(0.72, (n_e + 1.5) * 0.026)
            ax_t2 = fig.add_axes([0.06, 0.80 - h_est_box, 0.88, h_est_box])
            ax_t2.axis('off')

            tab2 = ax_t2.table(
                cellText=[headers_t2] + filas_t2,
                bbox=[0.0, 0.0, 1.0, 1.0],
                cellLoc='center',
                colWidths=[0.14, 0.08, 0.21, 0.11, 0.12, 0.10, 0.10, 0.14]
            )
            tab2.auto_set_font_size(False)
            tab2.set_fontsize(7.2 if n_e > 24 else 7.8)
            for (r_i, c_i), cell in tab2.get_celld().items():
                cell.set_linewidth(0.5)
                if r_i == 0:
                    cell.set_facecolor('navy')
                    cell.set_text_props(color='white', weight='bold')
                elif r_i % 2 == 0:
                    cell.set_facecolor('#f4f4f4')

            pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA 3: ESQUEMA PARAMÉTRICO Y MODELO WINKLER
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "ESQUEMA PARAMÉTRICO Y BULBO DE PRESIONES",
                                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
        df_rep = float(df_res['Df'].median()) if not df_res.empty else 1.5
        b_rep = float(df_res['B'].median()) if not df_res.empty else 1.2
        dibujar_esquema_zapata(fig, df_rep, b_rep, naf_m, metodo_exp, ubicacion_lbl, margen_pct)

        texto_esq = (
            "CRITERIOS DE MODELADO GEOTÉCNICO Y ESTRUCTURAL (NTC-CDMX 2023):\n"
            "------------------------------------------------------------------------------------\n"
            "1. Congruencia de Drenaje (Cohesivo vs. Friccionante):\n"
            "   En cumplimiento con las NTC-CDMX 2023, no se superponen términos de cohesión no drenada y\n"
            "   fricción efectiva. En suelos mixtos de laboratorio (c y phi), se evalúan ambas hipótesis\n"
            "   independientes y se rige el diseño con la condición más desfavorable.\n\n"
            "2. Control de Deformaciones en Estado Límite de Servicio:\n"
            "   La capacidad admisible por corte (q_corte) se contrasta contra la deformación elástica;\n"
            f"   la presión recomendada q_rec se acota para no exceder el {margen_pct:.0f}% de Se_máx.\n\n"
            "3. Resortes Verticales (Módulo de Balasto ks) para SAP2000 / ETABS / SAFE:\n"
            "   Se reporta ks = q_neta / Se en t/m³ y kg/cm³ para modelado de losas y zapatas sobre suelo elástico."
        )
        fig.text(0.08, 0.36, texto_esq, va='top', ha='left', fontsize=8.2, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINAS DE DESGLOSE ANALÍTICO: ZAPATAS CORRIDAS
        # --------------------------------------------------------
        for idx_p, pag_txt in enumerate(pags_corr):
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria_zapata(fig, f"DESGLOSE ANALÍTICO — ZAPATAS CORRIDAS (Parte {idx_p + 1})",
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            tit_c = (
                f"3. MEMORIA DE CÁLCULO DETALLADA — ZAPATAS CORRIDAS (Parte {idx_p + 1} de {len(pags_corr)})\n"
                f"====================================================================================\n\n"
            )
            fig.text(0.08, 0.84, tit_c + pag_txt, va='top', ha='left', fontsize=7.5, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINAS DE DESGLOSE ANALÍTICO: ZAPATAS AISLADAS
        # --------------------------------------------------------
        for idx_p, pag_txt in enumerate(pags_ais):
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria_zapata(fig, f"DESGLOSE ANALÍTICO — ZAPATAS AISLADAS (Parte {idx_p + 1})",
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            tit_a = (
                f"4. MEMORIA DE CÁLCULO DETALLADA — ZAPATAS AISLADAS (Parte {idx_p + 1} de {len(pags_ais)})\n"
                f"====================================================================================\n\n"
            )
            fig.text(0.08, 0.84, tit_a + pag_txt, va='top', ha='left', fontsize=7.5, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA DE GRÁFICAS COMPARATIVAS
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "GRÁFICAS DE CAPACIDAD RECOMENDADA Y DEFORMACIONES",
                                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)

        ax_g1 = fig.add_axes([0.10, 0.50, 0.37, 0.30])
        if not df_corr.empty:
            for b_val, grp in df_corr.groupby('B'):
                ax_g1.plot(grp['Df'], grp['q_rec_kgcm2'], marker='o', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g1.set_title("Zapatas Corridas: q_rec Recomendada vs Df", fontsize=8.5, weight='bold')
        ax_g1.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g1.set_ylabel("q_rec (kg/cm²)", fontsize=8)
        ax_g1.grid(True, linestyle='--', alpha=0.6)
        ax_g1.legend(fontsize=6.8)

        ax_g2 = fig.add_axes([0.56, 0.50, 0.37, 0.30])
        if not df_ais.empty:
            for b_val, grp in df_ais.groupby('B'):
                ax_g2.plot(grp['Df'], grp['q_rec_kgcm2'], marker='s', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g2.set_title("Zapatas Aisladas: q_rec Recomendada vs Df", fontsize=8.5, weight='bold')
        ax_g2.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g2.set_ylabel("q_rec (kg/cm²)", fontsize=8)
        ax_g2.grid(True, linestyle='--', alpha=0.6)
        ax_g2.legend(fontsize=6.8, ncol=2 if df_ais['B'].nunique() > 5 else 1)

        ax_g3 = fig.add_axes([0.10, 0.10, 0.37, 0.30])
        if not df_corr.empty:
            for b_val, grp in df_corr.groupby('B'):
                ax_g3.plot(grp['Df'], grp['Se_corte_mm'], marker='o', linestyle='--', alpha=0.65, lw=1.3, label=f"B={b_val:.2f}m")
            ax_g3.axhline(se_max_corr * 10.0, color='red', linestyle='-', lw=1.2, label=f"Lím. {se_max_corr*10:.0f} mm")
            ax_g3.axhline(se_max_corr * 10.0 * (margen_pct / 100.0), color='green', linestyle='-.', lw=1.2, label=f"Obj. {margen_pct:.0f}%")
        ax_g3.set_title("Corridas: Deformación Corte vs. Límite (mm)", fontsize=8.3, weight='bold')
        ax_g3.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g3.set_ylabel("Deformación Se (mm)", fontsize=8)
        ax_g3.grid(True, linestyle='--', alpha=0.6)
        ax_g3.legend(fontsize=6.2)

        ax_g4 = fig.add_axes([0.56, 0.10, 0.37, 0.30])
        if not df_ais.empty:
            for b_val, grp in df_ais.groupby('B'):
                ax_g4.plot(grp['Df'], grp['Se_corte_mm'], marker='s', linestyle='--', alpha=0.65, lw=1.3, label=f"B={b_val:.2f}m")
            ax_g4.axhline(se_max_ais * 10.0, color='red', linestyle='-', lw=1.2, label=f"Lím. {se_max_ais*10:.0f} mm")
            ax_g4.axhline(se_max_ais * 10.0 * (margen_pct / 100.0), color='green', linestyle='-.', lw=1.2, label=f"Obj. {margen_pct:.0f}%")
        ax_g4.set_title("Aisladas: Deformación Corte vs. Límite (mm)", fontsize=8.3, weight='bold')
        ax_g4.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g4.set_ylabel("Deformación Se (mm)", fontsize=8)
        ax_g4.grid(True, linestyle='--', alpha=0.6)
        ax_g4.legend(fontsize=6.0, ncol=2 if df_ais['B'].nunique() > 5 else 1)

        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA(S) FINAL(ES): TABLAS RESUMEN COMPLETAS + DICTAMEN
        # --------------------------------------------------------
        if modo_compacto_una_hoja:
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria_zapata(fig, "RESUMEN DE DISEÑO (FALLA VS. DEFORMACIÓN) Y DICTAMEN",
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
            y_cursor = 0.84
            if not df_corr.empty:
                fig.text(0.05, y_cursor, f"A. RESUMEN DE DISEÑO — ZAPATAS CORRIDAS [{ubicacion_lbl}] ({len(df_corr)} casos)",
                         fontsize=8.2, weight='bold', color='navy')
                y_cursor = _dibujar_tabla_en_caja(fig, df_corr, y_cursor - 0.015, 0.30, 'navy') - 0.035

            if not df_ais.empty:
                fig.text(0.05, y_cursor, f"B. RESUMEN DE DISEÑO — ZAPATAS AISLADAS [{ubicacion_lbl}] ({len(df_ais)} casos)",
                         fontsize=8.2, weight='bold', color='#7030a0')
                _dibujar_tabla_en_caja(fig, df_ais, y_cursor - 0.015, 0.30, '#7030a0')

            fig.text(0.05, 0.04, nota_dictamen, fontsize=7.4, style='italic', weight='bold', color='darkgreen')
            pdf.savefig(fig); plt.close(); contador += 1
        else:
            secuencia_tablas = []
            for idx_c, b_c in enumerate(bloques_tabla_corr):
                suf_c = f" (Parte {idx_c + 1} de {len(bloques_tabla_corr)})" if len(bloques_tabla_corr) > 1 else ""
                secuencia_tablas.append((
                    b_c,
                    f"A. RESUMEN DE DISEÑO — ZAPATAS CORRIDAS [NTC-CDMX 2023 | {ubicacion_lbl}]{suf_c} — Total: {len(df_corr)} casos",
                    'navy'
                ))
            for idx_a, b_a in enumerate(bloques_tabla_ais):
                suf_a = f" (Parte {idx_a + 1} de {len(bloques_tabla_ais)})" if len(bloques_tabla_ais) > 1 else ""
                secuencia_tablas.append((
                    b_a,
                    f"B. RESUMEN DE DISEÑO — ZAPATAS AISLADAS [NTC-CDMX 2023 | {ubicacion_lbl}]{suf_a} — Total: {len(df_ais)} casos",
                    '#7030a0'
                ))

            if not secuencia_tablas:
                fig = plt.figure(figsize=(8.5, 11))
                crear_encabezado_memoria_zapata(fig, "DICTAMEN GEOTÉCNICO",
                                                contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url)
                fig.text(0.05, 0.78, nota_dictamen, fontsize=8.2, style='italic', weight='bold', color='darkgreen')
                pdf.savefig(fig); plt.close(); contador += 1
            else:
                for idx_seq, (df_chunk, tit_sec, col_hdr) in enumerate(secuencia_tablas):
                    es_ult_tabla = (idx_seq == len(secuencia_tablas) - 1)
                    incluye_dictamen_aqui = es_ult_tabla and (not dictamen_en_hoja_aparte)

                    fig = plt.figure(figsize=(8.5, 11))
                    crear_encabezado_memoria_zapata(
                        fig, "RESUMEN DE DISEÑO (FALLA VS. DEFORMACIÓN)",
                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url
                    )
                    fig.text(0.05, 0.84, tit_sec, fontsize=8.2, weight='bold', color=col_hdr)

                    max_h = 0.66 if incluye_dictamen_aqui else 0.76
                    _dibujar_tabla_en_caja(fig, df_chunk, 0.82, max_h, col_hdr)

                    if incluye_dictamen_aqui:
                        fig.text(0.05, 0.04, nota_dictamen, fontsize=7.4, style='italic', weight='bold', color='darkgreen')

                    pdf.savefig(fig); plt.close(); contador += 1

                if dictamen_en_hoja_aparte:
                    fig = plt.figure(figsize=(8.5, 11))
                    crear_encabezado_memoria_zapata(
                        fig, "DICTAMEN GEOTÉCNICO Y RECOMENDACIONES DE DISEÑO",
                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha, logo_url=logo_url
                    )
                    fig.text(0.06, 0.82, nota_dictamen, va='top', ha='left', fontsize=8.8, style='italic', weight='bold', color='darkgreen')
                    pdf.savefig(fig); plt.close(); contador += 1

    return pdf_buffer.getvalue()