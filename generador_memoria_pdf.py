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
# 1. ENCABEZADO Y MEMBRETE EJECUTIVO
# ==========================================================
def crear_encabezado_memoria(fig, titulo_pagina, num_pagina, total_paginas, p_proy, p_elem, p_sondeo, p_fecha):
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
    fig.text(0.30, 0.904, f"SONDEO: {p_sondeo}", fontsize=8.5)
    fig.text(0.30, 0.884, f"MEMORIA TÉCNICA: {titulo_pagina}", fontsize=8.0, color='dimgray')
    
    if not p_fecha:
        p_fecha = datetime.datetime.now().strftime("%B %Y").upper()
    fig.text(0.95, 0.940, f"FECHA: {p_fecha}", ha='right', fontsize=8.5)
    fig.text(0.95, 0.904, f"PÁGINA: {num_pagina} / {total_paginas}", ha='right', fontsize=9, weight='bold')
    fig.lines.append(plt.Line2D([0.05, 0.95], [0.870, 0.870], transform=fig.transFigure, color='black', lw=1.5))

# ==========================================================
# 2. ESQUEMA GEOMÉTRICO PARAMÉTRICO
# ==========================================================
def dibujar_esquemas(fig, D_val, L_val, naf_m):
    ax1 = fig.add_axes([0.08, 0.44, 0.42, 0.38])
    ax2 = fig.add_axes([0.55, 0.44, 0.38, 0.38])
    
    ax1.set_title("Esquema Paramétrico Pila Profunda\n(Criterios de Castigo FHWA / NTC 2023)", fontsize=9.5, weight='bold')
    ax1.set_xlim(-5.0, 4.0)
    ax1.set_ylim(-(L_val + 2.5), 2.0)
    
    ax1.axhline(0, color='brown', lw=2)
    ax1.text(1.2, 0.4, "N.T.N. (Terreno ±0.00)", fontsize=8, color='brown', weight='bold')
    
    w_p = max(0.8, D_val)
    pila = patches.Rectangle((-w_p/2, -L_val), w_p, L_val, linewidth=1.5, edgecolor='black', facecolor='#e6e6e6', zorder=2)
    ax1.add_patch(pila)
    
    if naf_m is not None and naf_m < L_val:
        ax1.axhline(-naf_m, color='blue', lw=1.2, linestyle='-.', zorder=3)
        ax1.text(1.2, -naf_m + 0.3, f"N.A.F. (-{naf_m:.2f} m)", fontsize=7.5, color='blue', weight='bold')
        ax1.plot([1.0], [-naf_m], marker='v', color='blue', markersize=5)
        
    z_relaj = 1.50
    z_castigo_punta = L_val - D_val
    
    ax1.axhline(-z_relaj, color='red', lw=1.0, linestyle='--', zorder=3)
    ax1.text(1.2, -z_relaj, f"Fin Relajación (-{z_relaj:.2f} m)", fontsize=7.5, color='red')
    
    ax1.axhline(-z_castigo_punta, color='red', lw=1.0, linestyle='--', zorder=3)
    ax1.text(1.2, -z_castigo_punta, f"Inicio Castigo Base (-{z_castigo_punta:.2f} m)", fontsize=7.5, color='red')
    
    ax1.axhline(-L_val, color='green', lw=1.5, linestyle='-', zorder=3)
    ax1.text(1.2, -L_val - 0.4, f"Punta Z_tip (-{L_val:.2f} m)", fontsize=7.5, color='green', weight='bold')
    
    x_arrow = -w_p/2 - 0.5
    x_text = -w_p/2 - 1.2
    
    ax1.annotate('', xy=(x_arrow, 0), xytext=(x_arrow, -z_relaj), arrowprops=dict(arrowstyle='<->', color='red', lw=1.3))
    ax1.text(x_text, -z_relaj/2, "Fricción Anulada\n(1.50 m superior)", fontsize=7.5, color='red', weight='bold', ha='right', va='center')
    
    ax1.annotate('', xy=(x_arrow, -z_relaj), xytext=(x_arrow, -z_castigo_punta), arrowprops=dict(arrowstyle='<->', color='green', lw=1.5))
    ax1.text(x_text, -(z_relaj + z_castigo_punta)/2, f"Fricción Activa\n(L_efec = {z_castigo_punta - z_relaj:.1f} m)", fontsize=8, color='green', weight='bold', ha='right', va='center')
    
    ax1.annotate('', xy=(x_arrow, -z_castigo_punta), xytext=(x_arrow, -L_val), arrowprops=dict(arrowstyle='<->', color='red', lw=1.3))
    ax1.text(x_text, -(z_castigo_punta + L_val)/2, "Fricción Anulada\n(1.0·D base)", fontsize=7.5, color='red', weight='bold', ha='right', va='center')
    ax1.axis('off')

    ax2.set_title("Modelo de Interacción y Rigideces\n(Resortes para SAP2000 / ETABS)", fontsize=9.5, weight='bold')
    ax2.set_xlim(-3, 3)
    ax2.set_ylim(-11, 2)
    ax2.axhline(0, color='brown', lw=2)
    ax2.text(0, 0.5, "Nivel de Apoyo / Brocal", ha='center', fontsize=8, color='brown', weight='bold')
    cap = patches.Rectangle((-1.8, -1.8), 3.6, 1.8, facecolor='#d9d9d9', edgecolor='black', lw=1.5)
    ax2.add_patch(cap)
    ax2.text(0, -0.9, "Cabezal de Concreto", ha='center', va='center', fontsize=8.5, weight='bold')
    ax2.annotate('', xy=(0, -1.8), xytext=(0, -5.5), arrowprops=dict(arrowstyle='<->', color='navy', lw=2))
    ax2.text(0.3, -3.2, r"Resorte Vertical $K_v$", fontsize=9, color='navy', weight='bold')
    ax2.annotate('', xy=(-2.0, -7.5), xytext=(-0.5, -7.5), arrowprops=dict(arrowstyle='<->', color='darkgreen', lw=2))
    ax2.text(-1.25, -6.8, r"Resorte Lateral $K_h$", fontsize=9, color='darkgreen', weight='bold', ha='center')
    ax2.axis('off')

# ==========================================================
# 3. FUNCIÓN PRINCIPAL GENERADORA DE LA MEMORIA
# ==========================================================
def generar_memoria_calculo_pdf(df_tramos, matrices, p_proy, p_elem, *args, **kwargs):
    import cimentaciones_profundas
    
    if len(args) >= 2:
        p_sondeo = str(args[0])
        p_fecha = str(args[1])
    elif len(args) == 1:
        p_sondeo = str(kwargs.get('p_sondeo', 'SONDEO 1'))
        p_fecha = str(args[0])
    else:
        p_sondeo = str(kwargs.get('p_sondeo', 'SONDEO 1'))
        p_fecha = str(kwargs.get('p_fecha', ''))
        
    pdf_buffer = io.BytesIO()
    
    matriz_comp = matrices['matriz_compresion']
    matriz_tens = matrices['matriz_extraccion']
    matriz_acero = matrices['matriz_acero']
    matriz_kh = matrices['matriz_kh']
    matriz_Kv = matrices['matriz_Kv']
    df_comp = matrices['df_completo']
    
    diametros = matriz_comp.columns.tolist()
    longitudes = matriz_comp.index.tolist()
    
    # Paginación inteligente del registro estratigráfico:
    # Hasta 42 filas caben holgadamente por página sin tocar el encabezado.
    n_total_estratos = len(df_tramos)
    num_pags_estratos = max(1, int(math.ceil(n_total_estratos / 42.0)))
    filas_por_pag = int(math.ceil(n_total_estratos / float(num_pags_estratos)))
    
    bloques_estratos = []
    for i in range(num_pags_estratos):
        sub = df_tramos.iloc[i * filas_por_pag : (i + 1) * filas_por_pag]
        if not sub.empty: bloques_estratos.append(sub)
    num_pags_estratos = len(bloques_estratos)
    
    con_campana = matrices.get('con_campana', False)
    rel_campana = matrices.get('rel_campana', 1.5)
    h_campana_m = matrices.get('h_campana_m', 1.0)
    naf_m = matrices.get('naf_m', None)
    
    # Desglose representativo de pilas (8 casos estándar)
    casos_analisis = []
    for d in diametros:
        casos_analisis.append((d, longitudes[-1]))
        if len(longitudes) > 1 and (d, longitudes[0]) not in casos_analisis:
            casos_analisis.append((d, longitudes[0]))
            
    desgloses = []
    for d, l in casos_analisis:
        desglose = cimentaciones_profundas.evaluar_pila(
            df_tramos, naf_m=naf_m, diametro_m=d, longitud_m=l,
            con_campana=con_campana, rel_campana=rel_campana, h_campana_m=h_campana_m
        )
        desgloses.append(desglose)
    
    # Estructura ejecutiva de 22 páginas exactas
    total_paginas = 1 + num_pags_estratos + 1 + (len(desgloses) * 2) + 2
    
    with PdfPages(pdf_buffer) as pdf:
        contador = 1
        
        # --------------------------------------------------------
        # PÁGINA 1: METODOLOGÍA
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria(fig, "METODOLOGÍA Y CRITERIOS NORMATIVOS", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
        texto_pg1 = (
            "1. METODOLOGÍA DE CÁLCULO GEOTÉCNICO (NTC CDMX 2023 / NTC PUEBLA)\n"
            "====================================================================================\n\n"
            "A. CORRECCIONES A LA PRUEBA DE PENETRACIÓN ESTÁNDAR (SPT)\n"
            "   - Corrección por Nivel Freático (dilatancia en arenas finas sumergidas con N > 15):\n"
            "     N' = 15 + 0.5 * (N_campo - 15)\n"
            "   - Corrección por Energía y Equipo: N60 = N' * C_E * C_B * C_S * C_R (con tope conservador N60 <= 50)\n"
            "   - Confinamiento efectivo: (N1)60 = N60 * min(sqrt(100 / sigma'_v), 1.7).\n\n"
            "B. CAPACIDAD EN CIMENTACIONES PROFUNDAS (Pilas Perforadas)\n"
            "   - Suelos Friccionantes (NTC CDMX 3.6.2.3.2.3): fui = min(2.5 * N60, 200 kPa); FR_fuste = 0.50.\n"
            "     Punta: pu = 57.5 * N60_punta (<= 75 golpes); FR_punta = 0.35.\n"
            "   - Suelos Cohesivos (Método Alfa NTC 3.6.2.3.2.1): fui = min(alpha * cu, 200 kPa); FR_fuste = 0.70.\n"
            "     Punta: Cp = (cu * Nc* * FR + pv) * Ap * Fre; Nc* = 9.0; FR = 0.35; Fre = (B+1)/(2B+1).\n"
            "   - Formaciones Rocosas (NTC CDMX 3.6.2.3.5): fui = min(1.4*Pa*sqrt(alpha_E*qu/Pa), 3000 kPa); FR_f = 0.65.\n"
            "     Punta: pu = qu * Ksp * d; FR_p = 0.35; alpha_E = 10^(0.013*ICR - 1.34).\n\n"
            "C. RESTRICCIONES GEOTÉCNICAS OBLIGATORIAS (FHWA-NHI-10-016 / NTC 2023)\n"
            "   - Se desprecian los primeros 1,500 mm (1.50 m) de fuste por remoldeo y relajación superficial.\n"
            "   - Se desprecia 1.0·D de fuste antes de la punta por interacción destructiva de esfuerzos.\n"
            "   - Extracción / Tensión: Fricción penalizada al 80% (60% para L/D <= 20) + Peso del concreto neto.\n\n"
            "D. ESTIMACIÓN DEL PESO VOLUMÉTRICO ESTRATIFICADO\n"
            "   - En estratos granulares/cohesivos se estima gamma según F%, W% y compacidad/consistencia (N60)."
        )
        fig.text(0.08, 0.84, texto_pg1, va='top', ha='left', fontsize=8.5, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINAS DE ESTRATIGRAFÍA
        # --------------------------------------------------------
        for sub_df in bloques_estratos:
            fig = plt.figure(figsize=(8.5, 11))
            z_ini_b, z_fin_b = sub_df['Prof_ini'].min(), sub_df['Prof_fin'].max()
            crear_encabezado_memoria(fig, f"REGISTRO ESTRATIGRÁFICO ({z_ini_b:.1f} m a {z_fin_b:.1f} m)", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
            
            sub_title = (
                f"2. PERFIL ESTRATIGRÁFICO Y RESULTADOS SPT (Tramo {z_ini_b:.1f} m a {z_fin_b:.1f} m)\n"
                f"====================================================================================\n"
            )
            fig.text(0.08, 0.840, sub_title, va='top', ha='left', fontsize=8.0, family='monospace')
            
            ax_tab_est = fig.add_axes([0.08, 0.06, 0.84, 0.74])
            ax_tab_est.axis('off')
            
            headers_e = ["Profundidad (m)", "Espesor (m)", "SUCS", "Comportamiento", "N campo (golpes)", "N60 corregido"]
            filas_e = []
            for _, row in sub_df.iterrows():
                filas_e.append([
                    f"{row['Prof_ini']:.2f} - {row['Prof_fin']:.2f}",
                    f"{row['Espesor']:.2f} m",
                    str(row['SUCS']),
                    str(row['Tipo']),
                    f"{row['N_campo']:.0f}",
                    f"{row['N60']:.1f}"
                ])
                
            t_est = ax_tab_est.table(cellText=[headers_e] + filas_e, loc='center', cellLoc='center',
                                     colWidths=[0.20, 0.14, 0.14, 0.22, 0.15, 0.15])
            t_est.auto_set_font_size(False)
            n_e = len(filas_e)
            f_sz = 7.0 if n_e > 35 else (7.5 if n_e > 25 else 8.0)
            sc_y = 1.05 if n_e > 35 else (1.2 if n_e > 25 else 1.35)
            t_est.set_fontsize(f_sz)
            t_est.scale(1, sc_y)
            
            for j in range(6):
                t_est[0, j].set_facecolor('navy'); t_est[0, j].set_text_props(color='white', weight='bold')
            for r_idx in range(1, len(filas_e) + 1):
                if r_idx % 2 == 0:
                    for c_idx in range(6): t_est[r_idx, c_idx].set_facecolor('#f4f4f4')
                    
            pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA: ESQUEMAS VISUALES Y CRITERIOS
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria(fig, "ESQUEMA PARAMÉTRICO Y ZONAS DE EXCLUSIÓN", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
        d_rep, l_rep = diametros[-1], longitudes[-1]
        dibujar_esquemas(fig, d_rep, l_rep, naf_m=naf_m)
        texto_esq = (
            "JUSTIFICACIÓN TÉCNICA DE LOS CRITERIOS DE CASTIGO Y MODELADO:\n"
            "------------------------------------------------------------------------------------\n"
            "1. Anulación de Fricción Superior (Primeros 1.50 m):\n"
            "   Las normas NTC-CDMX (Cap. 7) y FHWA-NHI-10-016 exigen despreciar la adherencia lateral\n"
            "   en los 1,500 mm superiores debido al remoldeo mecánico por hincado de brocal temporal,\n"
            "   la desecación estacional y la posible separación fuste-terreno ante flexión y cortante sísmico.\n\n"
            "2. Anulación de Fricción en la Base (Último 1.0·D antes de la punta):\n"
            "   En pilotes y pilas perforadas, el bulbo de esfuerzos de la punta interactúa con el fuste adyacente\n"
            "   generando desconfinamiento radial. Asimismo, se protege el diseño ante eventuales acumulaciones\n"
            "   de azolves o caídos de perforación antes del colado del concreto sumergido.\n\n"
            "3. Parámetros de Interacción para Software Estructural (ETABS / SAP2000):\n"
            "   - Coeficiente de Balasto Lateral (kh): Extraído metro a metro en las siguientes hojas para la asignación\n"
            "     de resortes laterales tipo Winkler en el análisis no lineal de interacción suelo-estructura.\n"
            "     * Asignación: K_resorte_nodal = kh * D * L_tributaria (ton/m)\n"
            "   - Rigidez Axial Vertical (Kv): Representa la constante elástica del resorte en cabeza (t/cm)."
        )
        fig.text(0.08, 0.36, texto_esq, va='top', ha='left', fontsize=8.5, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINAS DE DESGLOSE: 2 PÁGINAS POR CASO
        # --------------------------------------------------------
        for idx_caso, r in enumerate(desgloses):
            
            # --- HOJA 1: MEMORIA DE CÁLCULO ---
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria(fig, f"DESGLOSE CAPACIDAD AXIAL (Caso {idx_caso+1} de {len(desgloses)})", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
            
            texto_caso = (
                f"2. MEMORIA DE CÁLCULO DETALLADA — CAPACIDAD AXIAL (Caso {idx_caso+1})\n"
                f"====================================================================================\n"
                f" > PILA PROFUNDA: Diámetro D = {r['D']:.2f} m | Longitud L = {r['L']:.2f} m\n"
                f"   Perímetro Fuste: {r['Perimetro']:.2f} m | Área Punta (Ap): {r['Area_punta']:.3f} m²\n"
                f"   Volumen Concreto: {(r['Area_fuste']*r['L']):.2f} m³ | Peso Concreto Neto (W): {r['W_ton']:.1f} t\n"
                f"   Criterio de Fuste: 1.50 m superior y 1.0·D en la base anulados (FHWA-NHI-10-016)\n"
                f"   Zona Activa de Fuste: {r['z_act_ini']:.2f} m a {r['z_act_fin']:.2f} m (Longitud Efectiva = {r['Long_fuste_activa_m']:.2f} m)\n\n"
                f"A. INTEGRACIÓN DE RESISTENCIA POR FRICCIÓN LATERAL:\n"
                f"   - Sumatoria de Fricción Nominal Acumulada (Ruf) = {r['Cf_nom_ton']:.1f} toneladas\n"
                f"   - Fricción unitaria máxima acotada por norma: fui <= 200 kPa (Ec. 3.6.2.3.2.4.3)\n"
                f"   => CAPACIDAD REDUCIDA POR FRICCIÓN (Cf = sum FR · F_nom) = {r['Cf_comp_ton']:.1f} toneladas\n\n"
                f"B. CAPACIDAD DE CARGA EN LA BASE / PUNTA (Cota de Desplante -{r['L']:.2f} m):\n"
                f"   - Estrato de apoyo: {r['detalles_punta']} [{r['norma_punta']}]\n"
                f"   - Resistencia unitaria última de punta: pu = {r['pu_kpa']:.1f} kPa ({r['pu_ton_m2']:.1f} t/m²)\n"
                f"   - Capacidad Nominal de Punta: Rup = pu * Ap = {r['Rup_ton']:.1f} toneladas\n"
                f"   - Factor de Resistencia de Punta: FR_p = 0.35 (NTC CDMX / Puebla)\n"
                f"   => CAPACIDAD REDUCIDA POR PUNTA (Cp = 0.35 * Rup) = {r['Cp_comp_ton']:.1f} toneladas\n\n"
                f"C. REVISIÓN DE ESTADO LÍMITE DE FALLA A COMPRESIÓN:\n"
                f"   - Ecuación: R = Cf + Cp = {r['Cf_comp_ton']:.1f} t + {r['Cp_comp_ton']:.1f} t\n"
                f"   => CAPACIDAD RESISTENTE REDUCIDA TOTAL (R) = {r['R_comp_ton']:.1f} TONELADAS\n\n"
                f"D. REVISIÓN A TENSIÓN / EXTRACCIÓN (NTC CDMX 3.6.3.2):\n"
                f"   - Fricción reducida a tensión (castigo 0.80/0.60): Cf_tens = {r['Cf_tens_ton']:.1f} t (Punta Cp = 0.0 t)\n"
                f"   - Peso propio neto del concreto (descontando subpresión bajo NAF): W = {r['W_ton']:.1f} t\n"
                f"   - Ecuación: Rt = Cf_tens + W = {r['Cf_tens_ton']:.1f} t + {r['W_ton']:.1f} t\n"
                f"   => CAPACIDAD RESISTENTE A TENSIÓN (Rt) = {r['R_tens_ton']:.1f} TONELADAS\n"
                f"   => Acero Longitudinal Mínimo Requerido (As = Rt / (0.90 * fy)) = {r['As_tensin_cm2']:.1f} cm²\n"
                f"      (Considerando acero de refuerzo con fy = 4,200 kg/cm² y FR = 0.90)\n\n"
                f"E. RIGIDEZ GLOBAL E INTERACCIÓN SUELO-ESTRUCTURA:\n"
                f"   - Módulo de balasto lateral promedio ponderado en fuste: kh_prom = {r['kh_t_m3']:.1f} t/m³\n"
                f"   - Rigidez lateral distribuida promedio: Kh_lineal = {r['Kh_lineal_t_m']:.1f} t/m\n"
                f"   - Rigidez Axial Vertical en Cabeza (Resorte Point Spring para software):\n"
                f"     Kv = {r['Kv_cabeza_t_cm']:.2f} t/cm ({r['Kv_cabeza_t_cm']*100:.0f} t/m)\n\n"
                f"   * Nota: En la siguiente página se presenta la tabla de balasto (kh, kv) metro a metro."
            )
            fig.text(0.08, 0.84, texto_caso, va='top', ha='left', fontsize=8.2, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

            # --- HOJA 2: TABLA DE BALASTO ---
            fig = plt.figure(figsize=(8.5, 11))
            n_m = int(math.ceil(r['L']))
            crear_encabezado_memoria(fig, f"BALASTO Y RESORTES METRO A METRO (1 a {n_m} m)", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
            
            info_balasto = (
                f" > ANÁLISIS DE RESORTES LATERALES Y VERTICALES (D = {r['D']:.2f} m | L = {r['L']:.2f} m)\n"
                f"   Rigidez lateral: Kh = kh * D (t/m) | Rigidez vertical: Kv_lin = kv * D (t/m) | Resorte en Cabeza: Kv = {r['Kv_cabeza_t_cm']:.2f} t/cm\n"
                f"   TABLA DE COEFICIENTES DE BALASTO (kh, kv) Y RIGIDECES (Kh, Kv) - TRAMO 1.00 m A {n_m}.00 m:"
            )
            fig.text(0.08, 0.840, info_balasto, va='top', ha='left', fontsize=8.0, family='monospace')
            
            ax_tab_kh = fig.add_axes([0.08, 0.14, 0.84, 0.67])
            ax_tab_kh.axis('off')
            
            df_balasto = cimentaciones_profundas.obtener_tabla_balasto_metro_a_metro(df_tramos, naf_m, r['D'], r['L'])
            h_kh = df_balasto.columns.tolist()
            d_kh = df_balasto.values.tolist()
                
            t_kh = ax_tab_kh.table(cellText=[h_kh] + d_kh, loc='center', cellLoc='center',
                                   colWidths=[0.16, 0.08, 0.16, 0.08, 0.13, 0.13, 0.13, 0.13])
            t_kh.auto_set_font_size(False)
            t_kh.set_fontsize(7.2 if len(d_kh) > 25 else 7.5)
            t_kh.scale(1, 1.15 if len(d_kh) > 25 else 1.3)
            
            for j in range(len(h_kh)):
                t_kh[0, j].set_facecolor('navy'); t_kh[0, j].set_text_props(color='white', weight='bold')
            for r_idx in range(1, len(d_kh) + 1):
                if r_idx % 2 == 0:
                    for c_idx in range(len(h_kh)): t_kh[r_idx, c_idx].set_facecolor('#f4f4f4')
                    
            nota_b = (
                f"NOTA PARA EL MODELO ESTRUCTURAL:\n"
                f"Módulo de Balasto Promedio en Fuste: kh_prom = {r['kh_t_m3']:.1f} t/m³ (Kh_prom = {r['Kh_lineal_t_m']:.1f} t/m).\n"
                f"Se recomienda asignar resortes puntuales en los nudos del fuste cada metro empleando las columnas 'Kh lineal' y 'Kv lineal'."
            )
            fig.text(0.08, 0.08, nota_b, va='top', ha='left', fontsize=7.5, family='monospace')
            
            pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA: GRÁFICAS DE COMPORTAMIENTO GEOTÉCNICO
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria(fig, "GRÁFICAS DE COMPORTAMIENTO GEOTÉCNICO", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
        
        ax_g1 = fig.add_axes([0.10, 0.48, 0.38, 0.32])
        for d in diametros:
            sub = df_comp[df_comp['Diametro_m'] == d]
            ax_g1.plot(sub['Longitud_m'], sub['R_comp_ton'], marker='o', lw=1.8, label=f"D = {d:.2f} m")
        ax_g1.set_title("Capacidad Reducida R (Compresión) vs L", fontsize=8.5, weight='bold')
        ax_g1.set_xlabel("Profundidad de Desplante L (m)", fontsize=8)
        ax_g1.set_ylabel("Capacidad R (toneladas)", fontsize=8)
        ax_g1.grid(True, linestyle='--', alpha=0.6)
        ax_g1.legend(fontsize=7.5)

        ax_g2 = fig.add_axes([0.56, 0.48, 0.38, 0.32])
        for l in longitudes:
            sub = df_comp[df_comp['Longitud_m'] == l]
            ax_g2.plot(sub['Diametro_m'], sub['R_tens_ton'], marker='s', lw=1.8, linestyle='--', label=f"L = {l:.1f} m")
        ax_g2.set_title("Capacidad Reducida Rt (Tensión) vs D", fontsize=8.5, weight='bold')
        ax_g2.set_xlabel("Diámetro de Pila D (m)", fontsize=8)
        ax_g2.set_ylabel("Capacidad Rt (toneladas)", fontsize=8)
        ax_g2.grid(True, linestyle='--', alpha=0.6)
        ax_g2.legend(fontsize=7.5)

        ax_g3 = fig.add_axes([0.25, 0.08, 0.50, 0.30])
        for l in longitudes:
            sub = df_comp[df_comp['Longitud_m'] == l]
            ax_g3.plot(sub['Diametro_m'], sub['Kv_cabeza_t_cm'], marker='^', lw=1.8, label=f"L = {l:.1f} m")
        ax_g3.set_title("Rigidez Axial en Cabeza Kv (Resorte) vs D", fontsize=8.5, weight='bold')
        ax_g3.set_xlabel("Diámetro de Pila D (m)", fontsize=8)
        ax_g3.set_ylabel("Rigidez Kv (t/cm)", fontsize=8)
        ax_g3.grid(True, linestyle='--', alpha=0.6)
        ax_g3.legend(fontsize=7.5)
        
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA: TABLAS RESUMEN Y MATRICES DE DISEÑO
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria(fig, "RESUMEN TABULAR Y MATRICES DE DISEÑO ESTRUCTURAL", contador, total_paginas, p_proy, p_elem, p_sondeo, p_fecha)
        
        head_cols = ["Prof. (m)"] + [f"D = {d:.2f} m" for d in diametros]
        
        fig.text(0.08, 0.84, "A. MATRIZ DE CAPACIDAD REDUCIDA A COMPRESIÓN: R (Toneladas)", fontsize=8.5, weight='bold')
        ax_m1 = fig.add_axes([0.08, 0.63, 0.84, 0.18]); ax_m1.axis('off')
        data_m1 = [head_cols] + [[f"{idx:.1f}"] + [f"{val:.1f} t" for val in matriz_comp.loc[idx].values] for idx in matriz_comp.index]
        t_m1 = ax_m1.table(cellText=data_m1, loc='center', cellLoc='center')
        t_m1.auto_set_font_size(False); t_m1.set_fontsize(8.0); t_m1.scale(1, 1.3)
        for j in range(len(head_cols)):
            t_m1[0, j].set_facecolor('navy'); t_m1[0, j].set_text_props(color='white', weight='bold')
        for i_row in range(1, len(data_m1)):
            for j in range(len(head_cols)):
                if i_row % 2 == 0: t_m1[i_row, j].set_facecolor('#f4f4f4')

        fig.text(0.08, 0.58, "B. MATRIZ DE CAPACIDAD REDUCIDA A TENSIÓN / EXTRACCIÓN: Rt (Toneladas)", fontsize=8.5, weight='bold')
        ax_m2 = fig.add_axes([0.08, 0.37, 0.84, 0.18]); ax_m2.axis('off')
        data_m2 = [head_cols] + [[f"{idx:.1f}"] + [f"{val:.1f} t" for val in matriz_tens.loc[idx].values] for idx in matriz_tens.index]
        t_m2 = ax_m2.table(cellText=data_m2, loc='center', cellLoc='center')
        t_m2.auto_set_font_size(False); t_m2.set_fontsize(8.0); t_m2.scale(1, 1.3)
        for j in range(len(head_cols)):
            t_m2[0, j].set_facecolor('#7030a0'); t_m2[0, j].set_text_props(color='white', weight='bold')
        for i_row in range(1, len(data_m2)):
            for j in range(len(head_cols)):
                if i_row % 2 == 0: t_m2[i_row, j].set_facecolor('#f4f4f4')

        fig.text(0.08, 0.32, "C. MATRIZ DE RIGIDEZ AXIAL EN CABEZA DE PILA: Kv (t/cm)", fontsize=8.5, weight='bold')
        ax_m3 = fig.add_axes([0.08, 0.15, 0.84, 0.15]); ax_m3.axis('off')
        data_m3 = [head_cols] + [[f"{idx:.1f}"] + [f"{val:.2f} t/cm" for val in matriz_Kv.loc[idx].values] for idx in matriz_Kv.index]
        t_m3 = ax_m3.table(cellText=data_m3, loc='center', cellLoc='center')
        t_m3.auto_set_font_size(False); t_m3.set_fontsize(8.0); t_m3.scale(1, 1.3)
        for j in range(len(head_cols)):
            t_m3[0, j].set_facecolor('#203764'); t_m3[0, j].set_text_props(color='white', weight='bold')
        for i_row in range(1, len(data_m3)):
            for j in range(len(head_cols)):
                if i_row % 2 == 0: t_m3[i_row, j].set_facecolor('#f4f4f4')

        nota_dictamen = (
            "DICTAMEN GEOTÉCNICO Y RECOMENDACIONES DE DISEÑO:\n"
            "El diseño por compresión y tensión axial corrobora la estabilidad geotécnica de los elementos (NTC-CDMX 3.6.3.2 / NTC-Puebla).\n"
            "Las capacidades portantes asimilan el castigo por relajación superficial (primeros 1.50 m) y la\n"
            "interacción destructiva en la base (1.0·D). Se avalan los módulos de rigidez Kv y kh para el modelo estructural en SAP/ETABS."
        )
        fig.text(0.08, 0.05, nota_dictamen, wrap=True, fontsize=8.0, style='italic', weight='bold', color='darkgreen')

        pdf.savefig(fig); plt.close()

    return pdf_buffer.getvalue()