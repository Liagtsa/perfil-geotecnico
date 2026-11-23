import io
import os
import math
import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg


# ==========================================================
# 1. ENCABEZADO Y MEMBRETE EJECUTIVO (CONFORME A PRODUCCIÓN)
# ==========================================================
def crear_encabezado_memoria_zapata(fig, titulo_pagina, num_pagina, total_paginas, p_proy, p_elem, p_sondeo, p_fecha):
    ax_logo = fig.add_axes([0.05, 0.88, 0.22, 0.08])
    ax_logo.axis('off')

    ruta_logo = 'logo_empresa.png'
    if os.path.exists(ruta_logo):
        try:
            ax_logo.imshow(mpimg.imread(ruta_logo), aspect='equal')
        except Exception:
            ax_logo.text(0.5, 0.5, '[ LOGO EMPRESA ]', ha='center', va='center', fontsize=8, color='navy', weight='bold')
    else:
        ax_logo.text(0.5, 0.5, '[ LOGO EMPRESA ]', ha='center', va='center', fontsize=8, color='navy', weight='bold')

    fig.text(0.30, 0.940, f"PROYECTO: {p_proy}", fontsize=10.0, weight='bold', color='navy')
    fig.text(0.30, 0.922, f"ELEMENTO: {p_elem}", fontsize=8.5)
    fig.text(0.30, 0.904, f"EXPLORACIÓN: {p_sondeo}", fontsize=8.5)
    fig.text(0.30, 0.884, f"MEMORIA TÉCNICA: {titulo_pagina}", fontsize=8.0, color='dimgray')

    if not p_fecha:
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

    total_paginas = 1 + 1 + 1 + len(pags_corr) + len(pags_ais) + 1 + 1

    with PdfPages(pdf_buffer) as pdf:
        contador = 1

        # --------------------------------------------------------
        # PÁGINA 1: METODOLOGÍA NORMATIVA NTC-CDMX 2023 (FALLA VS SERVICIO)
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "METODOLOGÍA Y CRITERIOS NORMATIVOS (NTC-CDMX 2023)", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
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
            f"   - Se evalúa la deformación elástica que produciría la carga por corte: Se_corte = q_neta·B·(1-nu²)·If / Es_sec.\n"
            f"   - Para evitar asentamientos excesivos, se fija una deformación objetivo al {margen_pct:.0f}% del límite máximo\n"
            f"     permitido (Se_máx = {se_max_ais*10:.0f} mm en zapatas aisladas; {se_max_corr*10:.0f} mm en zapatas corridas):\n"
            "       Se_obj = (Margen %) * Se_máx   =>   q_adm_def = [Se_obj * Es_sec / (B * (1 - nu²) * If)] + pv\n"
            "   - Capacidad Recomendada Gobernante: q_rec = min(r_CDMX, q_adm_corte, q_adm_def)."
        )
        fig.text(0.08, 0.84, texto_pg1, va='top', ha='left', fontsize=7.9, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA 2: PERFIL ESTRATIGRÁFICO / PARÁMETROS DE DISEÑO
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, f"PERFIL GEOTÉCNICO Y PARÁMETROS ({metodo_exp.upper()})", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
        sub_t2 = (
            f"2. PERFIL ESTRATIGRÁFICO Y PARÁMETROS MECÁNICOS DE DISEÑO ({metodo_exp.upper()})\n"
            f"====================================================================================\n"
        )
        fig.text(0.08, 0.84, sub_t2, va='top', ha='left', fontsize=8.0, family='monospace')

        ax_t2 = fig.add_axes([0.06, 0.08, 0.88, 0.72])
        ax_t2.axis('off')

        df_sub = df_tramos.head(38)
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

        tab2 = ax_t2.table(cellText=[headers_t2] + filas_t2, loc='center', cellLoc='center',
                           colWidths=[0.14, 0.08, 0.21, 0.11, 0.12, 0.10, 0.10, 0.14])
        tab2.auto_set_font_size(False)
        tab2.set_fontsize(7.2 if len(filas_t2) > 25 else 8.0)
        tab2.scale(1, 1.15 if len(filas_t2) > 25 else 1.35)
        for j in range(len(headers_t2)):
            tab2[0, j].set_facecolor('navy')
            tab2[0, j].set_text_props(color='white', weight='bold')
        for r_i in range(1, len(filas_t2) + 1):
            if r_i % 2 == 0:
                for c_i in range(len(headers_t2)):
                    tab2[r_i, c_i].set_facecolor('#f4f4f4')

        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA 3: ESQUEMA PARAMÉTRICO Y MODELO WINKLER
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "ESQUEMA PARAMÉTRICO Y BULBO DE PRESIONES", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
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
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
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
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
            tit_a = (
                f"4. MEMORIA DE CÁLCULO DETALLADA — ZAPATAS AISLADAS (Parte {idx_p + 1} de {len(pags_ais)})\n"
                f"====================================================================================\n\n"
            )
            fig.text(0.08, 0.84, tit_a + pag_txt, va='top', ha='left', fontsize=7.5, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA DE GRÁFICAS COMPARATIVAS (CORTE VS RECOMENDADA Y DEFORMACIONES)
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "GRÁFICAS DE CAPACIDAD RECOMENDADA Y DEFORMACIONES",
                                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)

        ax_g1 = fig.add_axes([0.10, 0.50, 0.37, 0.30])
        if not df_corr.empty:
            for b_val, grp in df_corr.groupby('B'):
                ax_g1.plot(grp['Df'], grp['q_rec_kgcm2'], marker='o', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g1.set_title("Zapatas Corridas: q_rec Recomendada vs Df", fontsize=8.5, weight='bold')
        ax_g1.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g1.set_ylabel("q_rec (kg/cm²)", fontsize=8)
        ax_g1.grid(True, linestyle='--', alpha=0.6)
        ax_g1.legend(fontsize=7)

        ax_g2 = fig.add_axes([0.56, 0.50, 0.37, 0.30])
        if not df_ais.empty:
            for b_val, grp in df_ais.groupby('B'):
                ax_g2.plot(grp['Df'], grp['q_rec_kgcm2'], marker='s', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g2.set_title("Zapatas Aisladas: q_rec Recomendada vs Df", fontsize=8.5, weight='bold')
        ax_g2.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g2.set_ylabel("q_rec (kg/cm²)", fontsize=8)
        ax_g2.grid(True, linestyle='--', alpha=0.6)
        ax_g2.legend(fontsize=7)

        ax_g3 = fig.add_axes([0.10, 0.10, 0.37, 0.30])
        if not df_corr.empty:
            for b_val, grp in df_corr.groupby('B'):
                ax_g3.plot(grp['Df'], grp['Se_corte_mm'], marker='o', linestyle='--', alpha=0.65, lw=1.3, label=f"Se_corte B={b_val:.2f}m")
            ax_g3.axhline(se_max_corr * 10.0, color='red', linestyle='-', lw=1.2, label=f"Lím. {se_max_corr*10:.0f} mm")
            ax_g3.axhline(se_max_corr * 10.0 * (margen_pct / 100.0), color='green', linestyle='-.', lw=1.2, label=f"Obj. {margen_pct:.0f}%")
        ax_g3.set_title("Corridas: Deformación Corte vs. Límite (mm)", fontsize=8.3, weight='bold')
        ax_g3.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g3.set_ylabel("Deformación Se (mm)", fontsize=8)
        ax_g3.grid(True, linestyle='--', alpha=0.6)
        ax_g3.legend(fontsize=6.5)

        ax_g4 = fig.add_axes([0.56, 0.10, 0.37, 0.30])
        if not df_ais.empty:
            for b_val, grp in df_ais.groupby('B'):
                ax_g4.plot(grp['Df'], grp['Se_corte_mm'], marker='s', linestyle='--', alpha=0.65, lw=1.3, label=f"Se_corte B={b_val:.2f}m")
            ax_g4.axhline(se_max_ais * 10.0, color='red', linestyle='-', lw=1.2, label=f"Lím. {se_max_ais*10:.0f} mm")
            ax_g4.axhline(se_max_ais * 10.0 * (margen_pct / 100.0), color='green', linestyle='-.', lw=1.2, label=f"Obj. {margen_pct:.0f}%")
        ax_g4.set_title("Aisladas: Deformación Corte vs. Límite (mm)", fontsize=8.3, weight='bold')
        ax_g4.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g4.set_ylabel("Deformación Se (mm)", fontsize=8)
        ax_g4.grid(True, linestyle='--', alpha=0.6)
        ax_g4.legend(fontsize=6.5)

        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA FINAL: TABLAS RESUMEN Y DICTAMEN GEOTÉCNICO
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "RESUMEN DE DISEÑO (FALLA VS. DEFORMACIÓN) Y DICTAMEN",
                                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)

        cols_res = ["Df\n(m)", "B\n(m)", "Modelo\nSuelo", "q_corte\n(kg/cm²)", "Se_corte\n(mm)", "q_def\n(kg/cm²)", "Criterio\nGobernante", "q_rec\n(kg/cm²)", "Se_rec\n(mm)", "ks\n(t/m³)"]

        def _cortar_modelo(m_txt):
            return "Cohesivo" if "Cohesiv" in str(m_txt) else "Friccionante"

        fig.text(0.05, 0.84, f"A. RESUMEN DE DISEÑO — ZAPATAS CORRIDAS [NTC-CDMX 2023 | {ubicacion_lbl}]", fontsize=8.2, weight='bold', color='navy')
        ax_m1 = fig.add_axes([0.05, 0.53, 0.90, 0.29]); ax_m1.axis('off')
        if not df_corr.empty:
            rows_c = [[
                f"{r['Df']:.2f}", f"{r['B']:.2f}", _cortar_modelo(r.get('modelo_suelo_aplicado', '')),
                f"{r['q_adm_corte_kgcm2']:.2f}", f"{r['Se_corte_mm']:.1f}",
                f"{r['q_adm_def_kgcm2']:.2f}", r['criterio_gobernante'], f"{r['q_rec_kgcm2']:.2f}",
                f"{r['Se_final_mm']:.1f}", f"{r['ks_ton_m3']:.0f}"
            ] for _, r in df_corr.head(14).iterrows()]
            t1 = ax_m1.table(cellText=[cols_res] + rows_c, loc='center', cellLoc='center',
                             colWidths=[0.06, 0.06, 0.11, 0.09, 0.09, 0.09, 0.20, 0.09, 0.09, 0.12])
            t1.auto_set_font_size(False); t1.set_fontsize(6.8); t1.scale(1, 1.18)
            for j in range(len(cols_res)):
                t1[0, j].set_facecolor('navy'); t1[0, j].set_text_props(color='white', weight='bold')
            for ri in range(1, len(rows_c) + 1):
                if ri % 2 == 0:
                    for ci in range(len(cols_res)): t1[ri, ci].set_facecolor('#f4f4f4')

        fig.text(0.05, 0.49, f"B. RESUMEN DE DISEÑO — ZAPATAS AISLADAS [NTC-CDMX 2023 | {ubicacion_lbl}]", fontsize=8.2, weight='bold', color='#7030a0')
        ax_m2 = fig.add_axes([0.05, 0.18, 0.90, 0.29]); ax_m2.axis('off')
        if not df_ais.empty:
            rows_a = [[
                f"{r['Df']:.2f}", f"{r['B']:.2f}", _cortar_modelo(r.get('modelo_suelo_aplicado', '')),
                f"{r['q_adm_corte_kgcm2']:.2f}", f"{r['Se_corte_mm']:.1f}",
                f"{r['q_adm_def_kgcm2']:.2f}", r['criterio_gobernante'], f"{r['q_rec_kgcm2']:.2f}",
                f"{r['Se_final_mm']:.1f}", f"{r['ks_ton_m3']:.0f}"
            ] for _, r in df_ais.head(14).iterrows()]
            t2 = ax_m2.table(cellText=[cols_res] + rows_a, loc='center', cellLoc='center',
                             colWidths=[0.06, 0.06, 0.11, 0.09, 0.09, 0.09, 0.20, 0.09, 0.09, 0.12])
            t2.auto_set_font_size(False); t2.set_fontsize(6.8); t2.scale(1, 1.18)
            for j in range(len(cols_res)):
                t2[0, j].set_facecolor('#7030a0'); t2[0, j].set_text_props(color='white', weight='bold')
            for ri in range(1, len(rows_a) + 1):
                if ri % 2 == 0:
                    for ci in range(len(cols_res)): t2[ri, ci].set_facecolor('#f4f4f4')

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
        fig.text(0.05, 0.04, nota_dictamen, fontsize=7.4, style='italic', weight='bold', color='darkgreen')

        pdf.savefig(fig); plt.close()

    return pdf_buffer.getvalue()