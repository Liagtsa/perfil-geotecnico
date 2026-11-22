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
def dibujar_esquema_zapata(fig, Df_rep, B_rep, naf_m, metodo_exp):
    ax1 = fig.add_axes([0.08, 0.44, 0.42, 0.38])
    ax2 = fig.add_axes([0.55, 0.44, 0.38, 0.38])

    ax1.set_title("Esquema Paramétrico de Zapata Superficial\n(Sobrecarga pv y Bulbo de Presiones)", fontsize=9.5, weight='bold')
    z_max_plot = max(Df_rep + 2.0 * B_rep + 0.6, 4.0)
    ax1.set_xlim(-3.2, 3.2)
    ax1.set_ylim(-z_max_plot, 1.2)

    ax1.axhline(0, color='brown', lw=2.0)
    ax1.text(2.9, 0.15, "N.T.N. (±0.00 m)", fontsize=7.5, color='brown', weight='bold', ha='right')

    w_dado = min(0.45, B_rep * 0.35)
    dado = patches.Rectangle((-w_dado / 2, -Df_rep + 0.35), w_dado, Df_rep - 0.35 + 0.35,
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

    ax2.set_title("Modelo de Interacción Suelo-Cimentación\n(NTC-CDMX 2023 vs NTC-Puebla)", fontsize=9.5, weight='bold')
    ax2.set_xlim(-3.0, 3.0)
    ax2.set_ylim(-6.0, 2.0)

    ax2.annotate('', xy=(0, 0.2), xytext=(0, 1.5), arrowprops=dict(arrowstyle='->', color='darkred', lw=2.2))
    ax2.text(0.25, 1.0, "Carga Axial Servicio Q", fontsize=8.0, color='darkred', weight='bold')

    zap2 = patches.Rectangle((-1.6, -0.5), 3.2, 0.7, facecolor='#d9d9d9', edgecolor='black', lw=1.5)
    ax2.add_patch(zap2)
    ax2.text(0, -0.15, "Cimentación Superficial (Rígida)", ha='center', va='center', fontsize=8.0, weight='bold')

    for x_s in [-1.2, -0.6, 0.0, 0.6, 1.2]:
        ax2.annotate('', xy=(x_s, -0.5), xytext=(x_s, -2.5), arrowprops=dict(arrowstyle='<->', color='navy', lw=1.5))
    ax2.axhline(-2.5, color='brown', lw=1.8)
    ax2.text(0, -3.1, "Módulo de Balasto Vertical ks (t/m³)", ha='center', fontsize=8.5, color='navy', weight='bold')
    ax2.text(0, -3.9, "Asentamiento Elástico: Se = [q_neta · B · (1 - nu²) · If] / Es", ha='center', fontsize=8.0, color='darkgreen')
    ax2.text(0, -4.9, "Criterio Gobernante:\nr_diseño = min(r_CDMX, r_Puebla)", ha='center', fontsize=8.0,
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff3cd', edgecolor='orange'))
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
    FS_val = analisis_zap.get('FS', 3.0)
    nu_val = analisis_zap.get('nu', 0.30)
    naf_m = analisis_zap.get('naf_m', None)

    def _bloque_texto_caso(r):
        norma_tag = f"[GOBIERNA: {r['norma_gobernante']}]"
        if r['metodo'].upper() == 'SPT' and pd.notna(r['N1_60']):
            param_linea = (
                f"   - Parámetros SPT en bulbo (h={r['h_bulbo']:.2f}m): "
                f"N60={r['N60']:.1f}, Cn={r['Cn']:.3f}, (N1)60={r['N1_60']:.1f} | "
                f"phi_ef={r['phi_efec']:.2f}°, c={r['c_kpa']:.1f} kPa"
            )
        else:
            param_linea = (
                f"   - Parámetros Lab. PCA en bulbo (h={r['h_bulbo']:.2f}m): "
                f"c={r['c_kpa']:.2f} kPa, phi_ef={r['phi_efec']:.2f}°, "
                f"gamma_ef={r['gamma_cuna']:.2f} kN/m³, Es={r['Es_kpa']:.0f} kPa"
            )

        return (
            f" > ZAPATA {r['tipo_zapata'].upper()} | B = {r['B']:.2f} m | Df = {r['Df']:.2f} m | pv = {r['pv_kpa']:.2f} kPa\n"
            f"{param_linea}\n"
            f"   - NTC-CDMX 2023 (FR={r['fr_cdmx']:.2f}): Nc*={r['nc_star_cdmx']:.2f}, Nq*={r['nq_star_cdmx']:.2f}, Ng*={r['ng_star_cdmx']:.2f} => r_CDMX = {r['r_cdmx_kpa']:.1f} kPa ({r['r_cdmx_kgcm2']:.2f} kg/cm²)\n"
            f"   - NTC-Puebla    (FR={r['fr_puebla']:.2f}): Nc*={r['nc_star_pue']:.2f}, Nq*={r['nq_star_pue']:.2f}, Ng*={r['ng_star_pue']:.2f} => r_Puebla = {r['r_puebla_kpa']:.1f} kPa ({r['r_puebla_kgcm2']:.2f} kg/cm²)\n"
            f"   => CAPACIDAD REDUCIDA GOBERNANTE {norma_tag}: r = {r['r_gob_kpa']:.2f} kPa ({r['r_gob_kgcm2']:.2f} kg/cm² | {r['r_gob_tonm2']:.1f} t/m²)\n"
            f"   => CAPACIDAD ADMISIBLE SERVICIO (FS={r['FS']:.1f}): q_adm = {r['q_adm_kpa']:.2f} kPa ({r['q_adm_kgcm2']:.2f} kg/cm² | {r['q_adm_tonm2']:.1f} t/m²)\n"
            f"   => ASENTAMIENTO ELÁSTICO (If={r['If']:.3f}): Se = {r['Se_cm']:.3f} cm | BALASTO VERTICAL: ks = {r['ks_ton_m3']:.1f} t/m³ ({r['ks_kg_cm3']:.2f} kg/cm³)\n\n"
        )

    textos_corr = [_bloque_texto_caso(row) for _, row in df_corr.iterrows()]
    textos_ais = [_bloque_texto_caso(row) for _, row in df_ais.iterrows()]

    def _paginar(lista_txt, por_pag=5):
        return ["".join(lista_txt[i:i + por_pag]) for i in range(0, len(lista_txt), por_pag)]

    pags_corr = _paginar(textos_corr, 5)
    pags_ais = _paginar(textos_ais, 5)

    total_paginas = 1 + 1 + 1 + len(pags_corr) + len(pags_ais) + 1 + 1

    with PdfPages(pdf_buffer) as pdf:
        contador = 1

        # PÁGINA 1: METODOLOGÍA NORMATIVA DUAL (NTC-CDMX + PUEBLA)
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "METODOLOGÍA Y CRITERIOS NORMATIVOS", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
        texto_pg1 = (
            "1. METODOLOGÍA DE CÁLCULO DE CIMENTACIONES SUPERFICIALES\n"
            "   (CRITERIO COMPARATIVO DUAL: NTC-CDMX 2023 vs. NTC-PUEBLA)\n"
            "====================================================================================\n\n"
            f"A. CARACTERIZACIÓN GEOTÉCNICA MEDIANTE {metodo_exp.upper()}\n"
            "   - Modo SPT: Corrección por sobrecarga Cn = min(2.0, sqrt(100 / sigma'_v)) [Liao & Whitman],\n"
            "     energía y varillaje N60, (N1)60; ángulo de fricción phi = 27.5 + 0.92*sqrt((N1)60) [Wolff],\n"
            "     cohesión no drenada cu = 6.0 * N60 y módulo elástico Es = 500*(N1)60 (arenas) / 300*cu (arcillas).\n"
            "   - Modo PCA (Pozo a Cielo Abierto): Emplea directamente los parámetros de resistencia al esfuerzo\n"
            "     cortante (c, phi) y peso volumétrico (gamma) de muestras inalteradas ensayadas en laboratorio.\n"
            "   - Ponderación en Bulbo de Presiones: Promedio ponderado desde z = Df hasta Df + 1.5·B (aislada)\n"
            "     o Df + 2.0·B (corrida), considerando subpresión por Nivel Freático (NAF) en pv y gamma_efec.\n\n"
            "B. CAPACIDAD DE CARGA EN ESTADO LÍMITE DE FALLA — NTC-CDMX 2023 (Numeral 3.5.1)\n"
            "   - Suelos Cohesivos (phi = 0): r_CDMX = cu * Nc* * FR + pv\n"
            "     donde Nc* = 5.14 * (1 + 0.25*(Df/B) + 0.25*(B/L)), con Df/B <= 2.0 y B/L <= 1.0.\n"
            "   - Suelos Friccionantes / c-phi: r_CDMX = [c*Nc* + pv*(Nq* - 1) + 0.5*gamma*B*Ngamma*] * FR + pv\n"
            "     con Nq = exp(pi*tan(phi))*tan^2(45 + phi/2), Ngamma = 2*(Nq + 1)*tan(phi) [Vesic],\n"
            "     fq = 1 + (B/L)*tan(phi), fgamma = 1 - 0.4*(B/L), y FR = 0.65.\n\n"
            "C. CAPACIDAD DE CARGA EN ESTADO LÍMITE DE FALLA — NTC-PUEBLA\n"
            "   - Emplea Ngamma = (Nq - 1)*tan(1.4*phi) [Meyerhof], factores de forma sc = 1 + 0.2*(B/L)*Kp,\n"
            "     sq = sgamma = 1 + 0.1*(B/L)*Kp (para phi > 10°), sin factores de profundidad en cepas abiertas,\n"
            "     con factor de resistencia FR = 0.60 (muestras inalteradas PCA) o FR = 0.50 (correlación SPT).\n\n"
            "D. CRITERIO DE SELECCIÓN MÁS DESFAVORABLE Y ESTADO LÍMITE DE SERVICIO\n"
            "   - Capacidad Reducida Gobernante: r_diseño = min(r_CDMX, r_Puebla).\n"
            f"   - Capacidad Admisible de Servicio: q_adm = min(q_ult_neta / FS + pv) con FS = {FS_val:.1f}.\n"
            f"   - Asentamiento Elástico (Steinbrenner/Bowles): Se = [q_neta * B * (1 - nu^2) * If] / Es (nu = {nu_val:.2f})."
        )
        fig.text(0.08, 0.84, texto_pg1, va='top', ha='left', fontsize=8.2, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA 2: PERFIL ESTRATIGRÁFICO / PARÁMETROS DE DISEÑO
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
        headers_t2 = ["Prof. (m)", "SUCS", "Tipo", "gamma\n(kN/m³)", "N60 /\n(N1)60", "c\n(kPa)", "phi\n(°)", "Es\n(kPa)"]
        filas_t2 = []
        for _, row in df_sub.iterrows():
            spt_str = f"{row['N60']:.0f}/{row['N1_60']:.0f}" if pd.notna(row['N60']) else "PCA"
            filas_t2.append([
                f"{row['Prof_ini']:.2f}-{row['Prof_fin']:.2f}",
                str(row['SUCS']),
                str(row['Tipo'])[:14],
                f"{row['Gamma']:.2f}",
                spt_str,
                f"{row['c_kPa']:.1f}",
                f"{row['phi_deg']:.1f}°",
                f"{row['Es_kPa']:.0f}"
            ])

        tab2 = ax_t2.table(cellText=[headers_t2] + filas_t2, loc='center', cellLoc='center',
                           colWidths=[0.15, 0.09, 0.19, 0.11, 0.12, 0.10, 0.10, 0.14])
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

        # PÁGINA 3: ESQUEMA PARAMÉTRICO Y MODELO WINKLER
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "ESQUEMA PARAMÉTRICO Y BULBO DE PRESIONES", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
        df_rep = float(df_res['Df'].median()) if not df_res.empty else 1.5
        b_rep = float(df_res['B'].median()) if not df_res.empty else 1.2
        dibujar_esquema_zapata(fig, df_rep, b_rep, naf_m, metodo_exp)

        texto_esq = (
            "CRITERIOS DE MODELADO GEOTÉCNICO Y ESTRUCTURAL:\n"
            "------------------------------------------------------------------------------------\n"
            "1. Sobrecarga Efectiva de Desplante (pv):\n"
            "   Integra el peso volumétrico de los estratos superiores hasta la cota -Df. Si el Nivel de Aguas\n"
            "   Freáticas (NAF) se ubica por encima de Df, se aplica el peso volumétrico sumergido (gamma - 9.81).\n\n"
            "2. Zona de Influencia Bajo la Zapata (Bulbo de Presiones):\n"
            "   Se ponderan los parámetros de resistencia (c, phi) y deformabilidad (Es) en una profundidad de\n"
            "   1.5·B para zapatas aisladas y 2.0·B para zapatas corridas. Si el NAF intercepta la cuña de falla\n"
            "   (Df < z_NAF < Df + B), el peso volumétrico gamma se interpola linealmente hacia gamma'.\n\n"
            "3. Resortes Verticales (Módulo de Balasto ks) para SAP2000 / ETABS / SAFE:\n"
            "   Se reporta ks = q_neta / Se en t/m³ y kg/cm³ para modelado de losas y zapatas sobre suelo elástico."
        )
        fig.text(0.08, 0.36, texto_esq, va='top', ha='left', fontsize=8.3, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINAS DE DESGLOSE ANALÍTICO: ZAPATAS CORRIDAS
        for idx_p, pag_txt in enumerate(pags_corr):
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria_zapata(fig, f"DESGLOSE ANALÍTICO — ZAPATAS CORRIDAS (Parte {idx_p + 1})",
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
            tit_c = (
                f"3. MEMORIA DE CÁLCULO DETALLADA — ZAPATAS CORRIDAS (Parte {idx_p + 1} de {len(pags_corr)})\n"
                f"====================================================================================\n\n"
            )
            fig.text(0.08, 0.84, tit_c + pag_txt, va='top', ha='left', fontsize=7.8, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINAS DE DESGLOSE ANALÍTICO: ZAPATAS AISLADAS
        for idx_p, pag_txt in enumerate(pags_ais):
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria_zapata(fig, f"DESGLOSE ANALÍTICO — ZAPATAS AISLADAS (Parte {idx_p + 1})",
                                            contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
            tit_a = (
                f"4. MEMORIA DE CÁLCULO DETALLADA — ZAPATAS AISLADAS (Parte {idx_p + 1} de {len(pags_ais)})\n"
                f"====================================================================================\n\n"
            )
            fig.text(0.08, 0.84, tit_a + pag_txt, va='top', ha='left', fontsize=7.8, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA DE GRÁFICAS COMPARATIVAS
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "GRÁFICAS DE CAPACIDAD DE CARGA Y ASENTAMIENTOS",
                                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)

        ax_g1 = fig.add_axes([0.10, 0.50, 0.37, 0.30])
        if not df_corr.empty:
            for b_val, grp in df_corr.groupby('B'):
                ax_g1.plot(grp['Df'], grp['q_adm_kgcm2'], marker='o', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g1.set_title("Zapatas Corridas: q_adm Gobernante vs Df", fontsize=8.5, weight='bold')
        ax_g1.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g1.set_ylabel("q_adm (kg/cm²)", fontsize=8)
        ax_g1.grid(True, linestyle='--', alpha=0.6)
        ax_g1.legend(fontsize=7)

        ax_g2 = fig.add_axes([0.56, 0.50, 0.37, 0.30])
        if not df_ais.empty:
            for b_val, grp in df_ais.groupby('B'):
                ax_g2.plot(grp['Df'], grp['q_adm_kgcm2'], marker='s', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g2.set_title("Zapatas Aisladas: q_adm Gobernante vs Df", fontsize=8.5, weight='bold')
        ax_g2.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g2.set_ylabel("q_adm (kg/cm²)", fontsize=8)
        ax_g2.grid(True, linestyle='--', alpha=0.6)
        ax_g2.legend(fontsize=7)

        ax_g3 = fig.add_axes([0.10, 0.10, 0.37, 0.30])
        if not df_corr.empty:
            for b_val, grp in df_corr.groupby('B'):
                ax_g3.plot(grp['Df'], grp['Se_cm'], marker='o', linestyle='-.', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g3.axhline(2.5, color='red', linestyle='--', lw=1.1, label="Lím. 2.5 cm")
        ax_g3.set_title("Zapatas Corridas: Asentamiento Se vs Df", fontsize=8.5, weight='bold')
        ax_g3.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g3.set_ylabel("Asentamiento Se (cm)", fontsize=8)
        ax_g3.grid(True, linestyle='--', alpha=0.6)
        ax_g3.legend(fontsize=7)

        ax_g4 = fig.add_axes([0.56, 0.10, 0.37, 0.30])
        if not df_ais.empty:
            for b_val, grp in df_ais.groupby('B'):
                ax_g4.plot(grp['Df'], grp['Se_cm'], marker='s', linestyle='-.', lw=1.7, label=f"B = {b_val:.2f} m")
        ax_g4.axhline(5.0, color='red', linestyle='--', lw=1.1, label="Lím. 5.0 cm")
        ax_g4.set_title("Zapatas Aisladas: Asentamiento Se vs Df", fontsize=8.5, weight='bold')
        ax_g4.set_xlabel("Profundidad Df (m)", fontsize=8)
        ax_g4.set_ylabel("Asentamiento Se (cm)", fontsize=8)
        ax_g4.grid(True, linestyle='--', alpha=0.6)
        ax_g4.legend(fontsize=7)

        pdf.savefig(fig); plt.close(); contador += 1

        # PÁGINA FINAL: TABLAS RESUMEN COMPARATIVAS Y DICTAMEN
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria_zapata(fig, "RESUMEN COMPARATIVO (NTC-CDMX vs NTC-PUEBLA) Y DICTAMEN",
                                        contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)

        cols_res = ["Df\n(m)", "B\n(m)", "r CDMX\n(kg/cm²)", "r Puebla\n(kg/cm²)", "Norma\nGobernante", "r Gob.\n(kg/cm²)", "q_adm\n(kg/cm²)", "Se\n(cm)", "ks\n(t/m³)"]

        fig.text(0.06, 0.84, "A. RESUMEN DE DISEÑO — ZAPATAS CORRIDAS (SELECCIÓN MÁS DESFAVORABLE)", fontsize=8.5, weight='bold', color='navy')
        ax_m1 = fig.add_axes([0.06, 0.53, 0.88, 0.29]); ax_m1.axis('off')
        if not df_corr.empty:
            rows_c = [[
                f"{r['Df']:.2f}", f"{r['B']:.2f}", f"{r['r_cdmx_kgcm2']:.2f}", f"{r['r_puebla_kgcm2']:.2f}",
                r['norma_gobernante'], f"{r['r_gob_kgcm2']:.2f}", f"{r['q_adm_kgcm2']:.2f}",
                f"{r['Se_cm']:.2f}", f"{r['ks_ton_m3']:.0f}"
            ] for _, r in df_corr.head(14).iterrows()]
            t1 = ax_m1.table(cellText=[cols_res] + rows_c, loc='center', cellLoc='center',
                             colWidths=[0.08, 0.08, 0.11, 0.11, 0.17, 0.11, 0.11, 0.09, 0.14])
            t1.auto_set_font_size(False); t1.set_fontsize(7.2); t1.scale(1, 1.18)
            for j in range(len(cols_res)):
                t1[0, j].set_facecolor('navy'); t1[0, j].set_text_props(color='white', weight='bold')
            for ri in range(1, len(rows_c) + 1):
                if ri % 2 == 0:
                    for ci in range(len(cols_res)): t1[ri, ci].set_facecolor('#f4f4f4')

        fig.text(0.06, 0.49, "B. RESUMEN DE DISEÑO — ZAPATAS AISLADAS (SELECCIÓN MÁS DESFAVORABLE)", fontsize=8.5, weight='bold', color='#7030a0')
        ax_m2 = fig.add_axes([0.06, 0.18, 0.88, 0.29]); ax_m2.axis('off')
        if not df_ais.empty:
            rows_a = [[
                f"{r['Df']:.2f}", f"{r['B']:.2f}", f"{r['r_cdmx_kgcm2']:.2f}", f"{r['r_puebla_kgcm2']:.2f}",
                r['norma_gobernante'], f"{r['r_gob_kgcm2']:.2f}", f"{r['q_adm_kgcm2']:.2f}",
                f"{r['Se_cm']:.2f}", f"{r['ks_ton_m3']:.0f}"
            ] for _, r in df_ais.head(14).iterrows()]
            t2 = ax_m2.table(cellText=[cols_res] + rows_a, loc='center', cellLoc='center',
                             colWidths=[0.08, 0.08, 0.11, 0.11, 0.17, 0.11, 0.11, 0.09, 0.14])
            t2.auto_set_font_size(False); t2.set_fontsize(7.2); t2.scale(1, 1.18)
            for j in range(len(cols_res)):
                t2[0, j].set_facecolor('#7030a0'); t2[0, j].set_text_props(color='white', weight='bold')
            for ri in range(1, len(rows_a) + 1):
                if ri % 2 == 0:
                    for ci in range(len(cols_res)): t2[ri, ci].set_facecolor('#f4f4f4')

        q_min_g = df_res['q_adm_kgcm2'].min() if not df_res.empty else 0.0
        q_max_g = df_res['q_adm_kgcm2'].max() if not df_res.empty else 0.0
        se_max_g = df_res['Se_cm'].max() if not df_res.empty else 0.0

        nota_dictamen = (
            f"DICTAMEN GEOTÉCNICO Y RECOMENDACIONES DE DISEÑO (EXPLORACIÓN {metodo_exp.upper()}):\n"
            f"1. Se evaluaron las cimentaciones superficiales bajo NTC-CDMX 2023 y NTC-Puebla, adoptando la condición más desfavorable.\n"
            f"2. Las capacidades admisibles gobernantes (FS={FS_val:.1f}) oscilan entre {q_min_g:.2f} y {q_max_g:.2f} kg/cm², con asentamiento máximo Se = {se_max_g:.2f} cm.\n"
            f"3. Se recomienda desplante sobre terreno natural firme libre de rellenos o suelo orgánico, con plantilla de concreto pobre f'c = 100 kg/cm²."
        )
        fig.text(0.06, 0.04, nota_dictamen, fontsize=7.6, style='italic', weight='bold', color='darkgreen')

        pdf.savefig(fig); plt.close()

    return pdf_buffer.getvalue()