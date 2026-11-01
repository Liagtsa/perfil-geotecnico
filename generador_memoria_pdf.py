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
def crear_encabezado_memoria(fig, titulo_pagina, num_pagina, total_paginas, p_proy, p_elem, p_fecha):
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
    
    fig.text(0.30, 0.935, f"PROYECTO: {p_proy}", fontsize=10.5, weight='bold', color='navy')
    fig.text(0.30, 0.915, f"ELEMENTO: {p_elem}", fontsize=9)
    fig.text(0.30, 0.895, f"MEMORIA TÉCNICA: {titulo_pagina}", fontsize=8.5, color='dimgray')
    
    if not p_fecha:
        p_fecha = datetime.datetime.now().strftime("%B %Y").upper()
    fig.text(0.95, 0.935, f"FECHA: {p_fecha}", ha='right', fontsize=8.5)
    fig.text(0.95, 0.900, f"PÁGINA: {num_pagina} / {total_paginas}", ha='right', fontsize=9, weight='bold')
    fig.lines.append(plt.Line2D([0.05, 0.95], [0.875, 0.875], transform=fig.transFigure, color='black', lw=1.5))


# ==========================================================
# 2. MOTOR DE DESGLOSE ANALÍTICO DETALLADO
# ==========================================================
def desglosar_calculo_pila(df_tramos, naf_m, diametro_m, longitud_m,
                            con_campana=False, rel_campana=1.5, h_campana_m=1.0,
                            factor_cu_spt=6.0, gamma_concreto=24.0, fc_kg_cm2=300.0):
    pp = np.pi * diametro_m
    z_act_ini = 1.50
    
    if con_campana:
        d_punta = diametro_m * rel_campana
        ap = (np.pi * (d_punta ** 2)) / 4.0
        z_act_fin = max(z_act_ini, longitud_m - h_campana_m - diametro_m)
    else:
        d_punta = diametro_m
        ap = (np.pi * (d_punta ** 2)) / 4.0
        z_act_fin = max(z_act_ini, longitud_m - diametro_m)
        
    l_d = longitud_m / diametro_m
    gamma_w = 9.81
    pa = 100.0
    f_red_fricc = 0.80 if l_d > 20.0 else 0.60
    f_red_cohes = 0.80
    f_red_roca = 0.70
    Ec_ton_m2 = (14000.0 * np.sqrt(fc_kg_cm2)) * 10.0
    
    desglose_estratos = []
    cf_comp_kn = 0.0
    cf_tens_kn = 0.0
    pv_total = 0.0
    kh_acumulado = 0.0
    peso_estratos = 0.0
    
    for _, tramo in df_tramos.iterrows():
        if tramo['Prof_ini'] >= longitud_m:
            break
        long_real = min(tramo['Prof_fin'], longitud_m) - tramo['Prof_ini']
        if long_real <= 0:
            continue
            
        pv_total += tramo['Gamma'] * long_real
        
        ini_f = max(tramo['Prof_ini'], z_act_ini)
        fin_f = min(tramo['Prof_fin'], z_act_fin)
        l_efec = max(0.0, fin_f - ini_f)
        
        n60 = tramo['N60']
        tipo = tramo['Tipo']
        
        if tipo == 'Roca':
            icr = tramo['ICR'] if pd.notna(tramo.get('ICR')) else 20.0
            qu = tramo['qu_kPa'] if pd.notna(tramo.get('qu_kPa')) else 25000.0
            alpha_e = 10.0 ** (0.013 * icr - 1.34)
            fui = min(1.4 * pa * np.sqrt(alpha_e * qu / pa), 3000.0)
            fr_f = 0.65
            tramo_comp = fr_f * (pp * fui * l_efec)
            tramo_tens = fr_f * (pp * (fui * f_red_roca) * l_efec)
            Em_kPa = max(alpha_e * 300.0 * qu, 200000.0)
            kh_local = (Em_kPa / (diametro_m * (1.0 - 0.25**2))) / 9.81
            norma = "NTC CDMX Roca"
        elif tipo == 'Friccionante':
            fui = min(3.0 * n60, 150.0)
            fr_f = 0.50
            tramo_comp = fr_f * (pp * fui * l_efec)
            tramo_tens = fr_f * (pp * (fui * f_red_fricc) * l_efec)
            nh_ton_m3 = 25.0 * n60
            kh_local = nh_ton_m3 * (tramo['P_med'] / diametro_m)
            norma = "NTC CDMX Arenas"
        else:
            cu = tramo['Cu_lab'] if (pd.notna(tramo.get('Cu_lab')) and tramo['Cu_lab'] > 0) else (factor_cu_spt * n60)
            fui = cu
            fr_f = 0.70
            tramo_comp = fr_f * (pp * fui * l_efec)
            tramo_tens = fr_f * (pp * (fui * f_red_cohes) * l_efec)
            kh_local = (67.0 * cu / diametro_m) / 9.81
            norma = "NTC Puebla Arcillas"
            
        cf_comp_kn += tramo_comp
        cf_tens_kn += tramo_tens
        kh_acumulado += kh_local * long_real
        peso_estratos += long_real
        
        desglose_estratos.append({
            'zt': tramo['Prof_ini'],
            'zb': min(tramo['Prof_fin'], longitud_m),
            'l_efec': l_efec,
            'tipo': tipo,
            'sucs': tramo['SUCS'],
            'n60': n60,
            'fui_kpa': fui,
            'fr_f': fr_f,
            'f_nom_ton': (pp * fui * l_efec) / 9.81,
            'f_red_ton': tramo_comp / 9.81,
            'kh_local': kh_local,
            'norma': norma
        })
        
    kh_prom_ton_m3 = (kh_acumulado / peso_estratos) if peso_estratos > 0 else 1500.0
    Kh_resorte_lineal = kh_prom_ton_m3 * diametro_m
    
    # Punta
    estrato_punta = df_tramos[(df_tramos['Prof_ini'] <= longitud_m) & (df_tramos['Prof_fin'] >= longitud_m)]
    estrato_p = estrato_punta.iloc[0] if not estrato_punta.empty else df_tramos.iloc[-1]
    tipo_p = estrato_p['Tipo']
    
    if tipo_p == 'Roca':
        icr_p = estrato_p['ICR'] if pd.notna(estrato_p.get('ICR')) else 20.0
        qu_p = estrato_p['qu_kPa'] if pd.notna(estrato_p.get('qu_kPa')) else 30000.0
        sd = max(0.05, 0.05 + 0.95 * (icr_p / 100.0)**2)
        td = 0.002
        ksp = (3.0 + sd / d_punta) / ((10.0 / 3.0) * np.sqrt(1.0 + 300.0 * (td / sd)))
        d_fact = min(1.0 + 0.4 * (longitud_m / d_punta), 3.0)
        pu_kpa = qu_p * ksp * d_fact
        fr_p = 0.35
        cp_comp_kn = fr_p * (pu_kpa * ap)
        Em_base = max((10.0 ** (0.013 * icr_p - 1.34)) * 300.0 * qu_p, 500000.0)
        kv_base_ton_m3 = (Em_base / (d_punta * (1.0 - 0.25**2))) / 9.81
        detalles_punta = f"Roca (qu={qu_p/1000:.1f} MPa, ICR={icr_p:.1f}%, Ksp={ksp:.3f}, d={d_fact:.2f})"
        norma_punta = "NTC CDMX Roca"
    elif tipo_p == 'Friccionante':
        zona_inf = longitud_m + 2.0 * d_punta
        pts = df_tramos[(df_tramos['Prof_fin'] >= longitud_m) & (df_tramos['Prof_ini'] <= zona_inf)]
        n60_punta = min(pts['N60'].mean() if not pts.empty else estrato_p['N60'], 50.0)
        pu_kpa = 60.0 * n60_punta
        fr_p = 0.35
        cp_comp_kn = fr_p * (pu_kpa * ap)
        Es_base = 3500.0 * n60_punta
        kv_base_ton_m3 = (Es_base / (d_punta * (1.0 - 0.30**2))) / 9.81
        detalles_punta = f"Arena (N60_punta={n60_punta:.1f} en 2D)"
        norma_punta = "NTC CDMX Arenas"
    else:
        cu_p = estrato_p['Cu_lab'] if (pd.notna(estrato_p.get('Cu_lab')) and estrato_p['Cu_lab'] > 0) else (factor_cu_spt * estrato_p['N60'])
        fre = (d_punta + 1.0) / (2.0 * d_punta + 1.0) if d_punta > 0.5 else 1.0
        fr_p = 0.35
        pu_kpa = (cu_p * 9.0 * fr_p + pv_total) * fre / fr_p
        cp_comp_kn = ((cu_p * 9.0 * fr_p) + pv_total) * ap * fre
        Es_base = 600.0 * cu_p
        kv_base_ton_m3 = (Es_base / (d_punta * (1.0 - 0.40**2))) / 9.81
        detalles_punta = f"Arcilla (cu={cu_p:.1f} kPa, Nc*=9.0, Fre={fre:.3f})"
        norma_punta = "NTC Puebla Arcillas"
        
    vol_fuste = (np.pi * (diametro_m**2) / 4.0) * (longitud_m - (h_campana_m if con_campana else 0.0))
    vol_campana = ((np.pi * h_campana_m / 12.0) * (diametro_m**2 + diametro_m * d_punta + d_punta**2)) if con_campana else 0.0
    vol_total = vol_fuste + vol_campana
    
    if naf_m is not None and naf_m < longitud_m:
        frac_sum = max(0.0, (longitud_m - naf_m) / longitud_m)
        vol_sum = vol_total * frac_sum
        vol_sec = vol_total - vol_sum
        peso_kn = (vol_sec * gamma_concreto) + (vol_sum * (gamma_concreto - gamma_w))
    else:
        peso_kn = vol_total * gamma_concreto
        
    r_comp_ton = (cf_comp_kn + cp_comp_kn) / 9.81
    r_tens_ton = (cf_tens_kn + peso_kn) / 9.81
    as_req_cm2 = (r_tens_ton * 1000.0) / (0.90 * 4200.0)
    
    xi = (cp_comp_kn + 0.5 * cf_comp_kn) / max(cf_comp_kn + cp_comp_kn, 1.0)
    flex_fuste = (xi * longitud_m) / (ap * Ec_ton_m2)
    flex_base = 1.0 / max(kv_base_ton_m3 * ap, 1.0)
    Kv_cabeza_ton_m = 1.0 / (flex_fuste + flex_base)
    Kv_cabeza_ton_cm = Kv_cabeza_ton_m / 100.0
    
    return {
        'D': diametro_m,
        'L': longitud_m,
        'd_punta': d_punta,
        'Area_fuste': np.pi * (diametro_m**2) / 4.0,
        'Area_punta': ap,
        'Perimetro': pp,
        'z_act_ini': z_act_ini,
        'z_act_fin': z_act_fin,
        'L_fuste_activa': max(0.0, z_act_fin - z_act_ini),
        'desglose_estratos': desglose_estratos,
        'Cf_nom_ton': sum(e['f_nom_ton'] for e in desglose_estratos),
        'Cf_comp_ton': cf_comp_kn / 9.81,
        'pu_kpa': pu_kpa,
        'pu_ton_m2': pu_kpa / 9.81,
        'Rup_ton': (pu_kpa * ap) / 9.81,
        'Cp_comp_ton': cp_comp_kn / 9.81,
        'R_comp_ton': r_comp_ton,
        'W_concreto_ton': peso_kn / 9.81,
        'Cf_tens_ton': cf_tens_kn / 9.81,
        'R_tens_ton': r_tens_ton,
        'As_tensin_cm2': as_req_cm2,
        'detalles_punta': detalles_punta,
        'norma_punta': norma_punta,
        'kh_prom_t_m3': kh_prom_ton_m3,
        'Kh_lineal_t_m': Kh_resorte_lineal,
        'kv_base_t_m3': kv_base_ton_m3,
        'Kv_cabeza_t_cm': Kv_cabeza_ton_cm
    }


# ==========================================================
# 3. ESQUEMA GEOMÉTRICO PARAMÉTRICO SIN EMPALMES
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
    
    ax1.annotate('', xy=(x_arrow, 0), xytext=(x_arrow, -z_relaj),
                arrowprops=dict(arrowstyle='<->', color='red', lw=1.3))
    ax1.text(x_text, -z_relaj/2, "Fricción Anulada\n(1.50 m superior)", fontsize=7.5, color='red', weight='bold', ha='right', va='center')
    
    ax1.annotate('', xy=(x_arrow, -z_relaj), xytext=(x_arrow, -z_castigo_punta),
                arrowprops=dict(arrowstyle='<->', color='green', lw=1.5))
    ax1.text(x_text, -(z_relaj + z_castigo_punta)/2, f"Fricción Activa\n(L_efec = {z_castigo_punta - z_relaj:.1f} m)", fontsize=8, color='green', weight='bold', ha='right', va='center')
    
    ax1.annotate('', xy=(x_arrow, -z_castigo_punta), xytext=(x_arrow, -L_val),
                arrowprops=dict(arrowstyle='<->', color='red', lw=1.3))
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
    
    ax2.annotate('', xy=(0, -1.8), xytext=(0, -5.5),
                 arrowprops=dict(arrowstyle='<->', color='navy', lw=2))
    ax2.text(0.3, -3.2, r"Resorte Vertical $K_v$", fontsize=9, color='navy', weight='bold')
    ax2.text(0.3, -4.2, r"$K_v = \frac{P}{\delta_{\mathrm{total}}}$ (t/cm)", fontsize=8, color='navy')
    
    ax2.annotate('', xy=(-2.0, -7.5), xytext=(-0.5, -7.5),
                 arrowprops=dict(arrowstyle='<->', color='darkgreen', lw=2))
    ax2.text(-1.25, -6.8, r"Resorte Lateral $K_h$", fontsize=9, color='darkgreen', weight='bold', ha='center')
    ax2.text(-1.25, -8.3, r"$k_h(z) = n_h \cdot \frac{z}{D}$ (t/m³)", fontsize=8, color='darkgreen', ha='center')
    
    ax2.text(0, -10.2, "Rigidez metro a metro para\nresortes Point Springs en nodos", fontsize=8, ha='center', style='italic',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#f0f4f8', edgecolor='#b0c4de'))
    ax2.axis('off')


# ==========================================================
# 4. FUNCIÓN PRINCIPAL GENERADORA DE LA MEMORIA
# ==========================================================
def generar_memoria_calculo_pdf(df_tramos, matrices, p_proy, p_elem, p_fecha):
    pdf_buffer = io.BytesIO()
    
    matriz_comp = matrices['matriz_compresion']
    matriz_tens = matrices['matriz_extraccion']
    matriz_acero = matrices['matriz_acero']
    matriz_kh = matrices['matriz_kh']
    matriz_Kv = matrices['matriz_Kv']
    df_comp = matrices['df_completo']
    
    diametros = matriz_comp.columns.tolist()
    longitudes = matriz_comp.index.tolist()
    
    # 1. Paginación de la estratigrafía general en bloques de 25 m
    prof_max_sondeo = df_tramos['Prof_fin'].max()
    bloques_estratos = []
    z_cursor = 0.0
    while z_cursor < prof_max_sondeo:
        z_sig = z_cursor + 25.0
        sub_est = df_tramos[(df_tramos['Prof_ini'] >= z_cursor) & (df_tramos['Prof_ini'] < z_sig)]
        if not sub_est.empty:
            bloques_estratos.append((z_cursor, z_sig, sub_est))
        z_cursor = z_sig
    if not bloques_estratos:
        bloques_estratos.append((0.0, 25.0, df_tramos))
        
    num_pags_estratos = len(bloques_estratos)
    
    # Extracción de metadatos de configuración sincronizados
    con_campana = matrices.get('con_campana', False)
    rel_campana = matrices.get('rel_campana', 1.5)
    h_campana_m = matrices.get('h_campana_m', 1.0)
    naf_m = matrices.get('naf_m', None)
    
    # 2. Desglose representativo de pilas
    casos_analisis = []
    for d in diametros:
        casos_analisis.append((d, longitudes[-1]))
        if len(longitudes) > 1 and (d, longitudes[0]) not in casos_analisis:
            casos_analisis.append((d, longitudes[0]))
            
    desgloses = [
        desglosar_calculo_pila(
            df_tramos, naf_m=naf_m, diametro_m=d, longitud_m=l,
            con_campana=con_campana, rel_campana=rel_campana, h_campana_m=h_campana_m
        ) 
        for d, l in casos_analisis
    ]
    
    pags_por_desglose = []
    for r in desgloses:
        n_pags_balasto = int(math.ceil(r['L'] / 25.0))
        pags_por_desglose.append(1 + n_pags_balasto)
        
    total_paginas = 1 + num_pags_estratos + 1 + sum(pags_por_desglose) + 2
    
    with PdfPages(pdf_buffer) as pdf:
        contador = 1
        
        # --------------------------------------------------------
        # PÁGINA 1: METODOLOGÍA Y CRITERIOS NORMATIVOS (TEXTO PURO)
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria(fig, "METODOLOGÍA Y CRITERIOS NORMATIVOS", contador, total_paginas, p_proy, p_elem, p_fecha)
        
        texto_pg1 = (
            "1. METODOLOGÍA DE CÁLCULO GEOTÉCNICO (NTC CDMX 2023 / NTC PUEBLA)\n"
            "====================================================================================\n\n"
            "A. CORRECCIONES A LA PRUEBA DE PENETRACIÓN ESTÁNDAR (SPT)\n"
            "   - Corrección por Nivel Freático (dilatancia en arenas finas sumergidas con N > 15):\n"
            "     N' = 15 + 0.5 * (N_campo - 15)\n"
            "   - Corrección por Energía y Equipo: N60 = N' * C_E * C_B * C_S * C_R (con tope conservador N60 <= 50)\n"
            "     Donde: C_E = Eficiencia/60; C_R = Longitud varilla (0.75 a 1.00); C_B = Diámetro; C_S = Muestreador.\n"
            "   - Confinamiento efectivo: (N1)60 = N60 * min(sqrt(100 / sigma'_v), 1.7).\n\n"
            "B. CAPACIDAD EN CIMENTACIONES PROFUNDAS (Pilas Perforadas)\n"
            "   - Suelos Friccionantes (NTC CDMX 3.6.2.3.2.3): fui = min(3*N60, 150 kPa); FR_fuste = 0.50.\n"
            "     Punta: pu = 60 * N60_punta (<= 50 en 2D); FR_punta = 0.35.\n"
            "   - Suelos Cohesivos (NTC Puebla 3.5.1 / 3.6.1): f = cu; FR_fuste = 0.70.\n"
            "     Punta: Cp = (cu * Nc* * FR + pv) * Ap * Fre; Nc* = 9.0; FR = 0.35; Fre = (B+1)/(2B+1).\n"
            "   - Formaciones Rocosas (NTC CDMX 3.6.2.3.5): fui = 1.4*Pa*sqrt(alpha_E*qu/Pa); FR_f = 0.65.\n"
            "     Punta: pu = qu * Ksp * d; FR_p = 0.35; alpha_E = 10^(0.013*ICR - 1.34).\n\n"
            "C. RESTRICCIONES GEOTÉCNICAS OBLIGATORIAS (FHWA-NHI-10-016 / NTC 2023)\n"
            "   - Se desprecian los primeros 1,500 mm (1.50 m) de fuste por remoldeo y relajación superficial.\n"
            "   - Se desprecia 1.0·D de fuste antes de la punta por interacción destructiva de esfuerzos.\n"
            "   - Extracción / Tensión: Fricción penalizada al 80% (60% para L/D <= 20) + Peso del concreto.\n\n"
            "D. ESTIMACIÓN DEL PESO VOLUMÉTRICO ESTRATIFICADO\n"
            "   - Para evitar sobreestimaciones con un peso volumétrico fijo artificialmente alto,\n"
            "     gamma se deduce a partir de relaciones gravimétricas de fase (w%, F%, Gs) y compacidad N60.\n"
            "   - En roca y formaciones consolidadas se asignan densidades reales de 21.0 a 24.5 kN/m³."
        )
        fig.text(0.08, 0.84, texto_pg1, va='top', ha='left', fontsize=8.5, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINAS DE ESTRATIGRAFÍA (DEDICADAS CADA 25 METROS)
        # --------------------------------------------------------
        for idx_b, (z_ini_b, z_fin_b, sub_df) in enumerate(bloques_estratos):
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria(fig, f"REGISTRO ESTRATIGRÁFICO ({z_ini_b:.1f} m a {z_fin_b:.1f} m)", contador, total_paginas, p_proy, p_elem, p_fecha)
            
            sub_title = (
                f"2. PERFIL ESTRATIGRÁFICO Y RESULTADOS SPT (Tramo {z_ini_b:.1f} m a {z_fin_b:.1f} m)\n"
                f"====================================================================================\n"
                f"Se omiten columnas redundantes para garantizar el formato tabular dentro de la página.\n"
            )
            fig.text(0.08, 0.84, sub_title, va='top', ha='left', fontsize=8.5, family='monospace')
            
            ax_tab_est = fig.add_axes([0.08, 0.10, 0.84, 0.68])
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
            t_est.set_fontsize(8.0 if len(filas_e) > 15 else 8.5)
            t_est.scale(1, 1.4)
            for j in range(6):
                t_est[0, j].set_facecolor('navy'); t_est[0, j].set_text_props(color='white', weight='bold')
            for r_idx in range(1, len(filas_e) + 1):
                if r_idx % 2 == 0:
                    for c_idx in range(6): t_est[r_idx, c_idx].set_facecolor('#f4f4f4')
                    
            pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINA: ESQUEMAS VISUALES Y CRITERIOS DE CASTIGO
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria(fig, "ESQUEMA PARAMÉTRICO Y ZONAS DE EXCLUSIÓN", contador, total_paginas, p_proy, p_elem, p_fecha)
        
        d_rep = diametros[-1]
        l_rep = longitudes[-1]
        dibujar_esquemas(fig, d_rep, l_rep, naf_m=naf_m)
        
        texto_esq = (
            "JUSTIFICACIÓN TÉCNICA DE LOS CRITERIOS DE CASTIGO Y MODELADO:\n"
            "------------------------------------------------------------------------------------\n"
            "1. Anulación de Fricción Superior (Primeros 1.50 m):\n"
            "   Las normas NTC-CDMX (Cap. 7) y FHWA-NHI-10-016 exigen despreciar la adherencia lateral\n"
            "   en los 1 500 mm superiores debido al remoldeo mecánico por los trabajos superficiales de la perforación,\n"
            "   la desecación estacional y la posible separación fuste-terreno ante flexión y cortante sísmico.\n\n"
            "2. Anulación de Fricción en la Base (Último 1.0·D antes de la punta):\n"
            "   En pilotes y pilas perforadas, el bulbo de esfuerzos de la punta interactúa con el fuste adyacente\n"
            "   generando desconfinamiento radial. Asimismo, se protege el diseño ante eventuales acumulaciones\n"
            "   de azolves o caídos de perforación antes del colado del concreto sumergido.\n\n"
            "3. Parámetros de Interacción para Software Estructural:\n"
            "   - Coeficiente de Balasto Lateral (kh): Extraído metro a metro en las siguientes hojas para la asignación\n"
            "     de resortes laterales tipo Winkler en el análisis no lineal de interacción suelo-estructura.\n"
            "   - Rigidez Axial Vertical (Kv): Representa la constante elástica del resorte en cabeza (t/cm),\n"
            "     integrando la elasticidad del fuste de concreto y el asentamiento en la base de apoyo."
        )
        fig.text(0.08, 0.36, texto_esq, va='top', ha='left', fontsize=8.5, family='monospace')
        pdf.savefig(fig); plt.close(); contador += 1

        # --------------------------------------------------------
        # PÁGINAS DE DESGLOSE: CÁLCULO POR CÁLCULO
        # --------------------------------------------------------
        for idx_caso, r in enumerate(desgloses):
            # --- HOJA 1 DEL CASO: MEMORIA DE CAPACIDAD AXIAL (TEXTO FORMAL) ---
            fig = plt.figure(figsize=(8.5, 11))
            crear_encabezado_memoria(fig, f"DESGLOSE CAPACIDAD AXIAL (Caso {idx_caso+1} de {len(desgloses)})", contador, total_paginas, p_proy, p_elem, p_fecha)
            
            texto_pila = (
                f"2. MEMORIA DE CÁLCULO DETALLADA - CAPACIDAD AXIAL (Caso {idx_caso+1})\n"
                f"====================================================================================\n\n"
                f" > PILA PROFUNDA: Diámetro D = {r['D']:.2f} m | Longitud L = {r['L']:.2f} m\n"
                f"   - Perímetro Fuste: {r['Perimetro']:.2f} m | Área Punta (Ap): {r['Area_punta']:.3f} m²\n"
                f"   - Volumen Concreto: {r['Area_fuste'] * r['L']:.2f} m³ | Peso Concreto Neto (W): {r['W_concreto_ton']:.1f} t\n"
                f"   - Criterio de Fuste: 1.50 m superior y 1.0·D en la base anulados (FHWA-NHI-10-016)\n"
                f"   - Zona Activa de Fuste: {r['z_act_ini']:.2f} m a {r['z_act_fin']:.2f} m (Longitud Efectiva = {r['L_fuste_activa']:.2f} m)\n\n"
                f"   A. INTEGRACIÓN DE RESISTENCIA POR FRICCIÓN LATERAL:\n"
                f"      - Sumatoria de Fricción Nominal Acumulada (Ruf) = {r['Cf_nom_ton']:.1f} toneladas\n"
                f"      - Factor de Resistencia de Fuste aplicado: FR = 0.50 (Arenas) / 0.70 (Arcillas)\n"
                f"      => CAPACIDAD REDUCIDA POR FRICCIÓN (Cf = sum FR * F_nom) = {r['Cf_comp_ton']:.1f} toneladas\n\n"
                f"   B. CAPACIDAD DE CARGA EN LA BASE / PUNTA (Cota de Desplante -{r['L']:.2f} m):\n"
                f"      - Estrato de apoyo: {r['detalles_punta']} [{r['norma_punta']}]\n"
                f"      - Resistencia unitaria última de punta: pu = {r['pu_kpa']:.1f} kPa ({r['pu_ton_m2']:.1f} t/m²)\n"
                f"      - Capacidad Nominal de Punta: Rup = pu * Ap = {r['Rup_ton']:.1f} toneladas\n"
                f"      - Factor de Resistencia de Punta: FR_p = 0.35 (NTC CDMX / Puebla)\n"
                f"      => CAPACIDAD REDUCIDA POR PUNTA (Cp = 0.35 * Rup) = {r['Cp_comp_ton']:.1f} toneladas\n\n"
                f"   C. REVISIÓN DE ESTADO LÍMITE DE FALLA A COMPRESIÓN:\n"
                f"      - Ecuación: R = Cf + Cp = {r['Cf_comp_ton']:.1f} t + {r['Cp_comp_ton']:.1f} t\n"
                f"      => CAPACIDAD RESISTENTE REDUCIDA TOTAL (R) = {r['R_comp_ton']:.1f} TONELADAS\n\n"
                f"   D. REVISIÓN A TENSIÓN / EXTRACCIÓN (NTC CDMX 3.6.3.2):\n"
                f"      - Fricción reducida a tensión (castigo 0.80/0.60): Cf_tens = {r['Cf_tens_ton']:.1f} t  (Punta Cp = 0.0 t)\n"
                f"      - Peso propio neto del concreto (descontando subpresión bajo NAF): W = {r['W_concreto_ton']:.1f} t\n"
                f"      - Ecuación: Rt = Cf_tens + W = {r['Cf_tens_ton']:.1f} t + {r['W_concreto_ton']:.1f} t\n"
                f"      => CAPACIDAD RESISTENTE A TENSIÓN (Rt) = {r['R_tens_ton']:.1f} TONELADAS\n"
                f"      => Acero Longitudinal Mínimo Requerido (As = Rt / (0.90 * fy)) = {r['As_tensin_cm2']:.1f} cm²\n"
                f"         (Considerando acero de refuerzo con fy = 4,200 kg/cm² y FR = 0.90)\n\n"
                f"   E. RIGIDEZ GLOBAL E INTERACCIÓN SUELO-ESTRUCTURA:\n"
                f"      - Módulo de balasto lateral promedio ponderado en fuste: kh_prom = {r['kh_prom_t_m3']:.1f} t/m³\n"
                f"      - Rigidez lateral distribuida promedio: Kh_lineal = {r['Kh_lineal_t_m']:.1f} t/m\n"
                f"      - Rigidez Axial Vertical en Cabeza (Resorte Point Spring para software):\n"
                f"        Kv = {r['Kv_cabeza_t_cm']:.2f} t/cm  ({r['Kv_cabeza_t_cm']*100:.0f} t/m)\n"
                f"   ------------------------------------------------------------------------------------\n"
                f"   * Nota: En la siguiente página se presenta la tabla de balasto (kh, kv) metro a metro."
            )
            fig.text(0.08, 0.84, texto_pila, va='top', ha='left', fontsize=8.2, family='monospace')
            pdf.savefig(fig); plt.close(); contador += 1

            # --- HOJA 2 DEL CASO: TABLA DE BALASTO METRO A METRO (DEDICADA CADA 25 METROS) ---
            n_metros_totales = int(math.ceil(r['L']))
            z_cursor_kh = 1
            
            while z_cursor_kh <= n_metros_totales:
                z_fin_kh_bloque = min(z_cursor_kh + 24, n_metros_totales)
                
                fig = plt.figure(figsize=(8.5, 11))
                crear_encabezado_memoria(fig, f"BALASTO Y RESORTES METRO A METRO ({z_cursor_kh} a {z_fin_kh_bloque} m)", contador, total_paginas, p_proy, p_elem, p_fecha)
                
                info_balasto = (
                    f" > ANÁLISIS DE RESORTES LATERALES Y VERTICALES (D = {r['D']:.2f} m | L = {r['L']:.2f} m)\n"
                    f"   - Rigidez lateral por metro lineal: Kh = kh * D (t/m). Rigidez vertical en fuste: Kv_lin = kv * D (t/m).\n"
                    f"   - Rigidez Axial Vertical en Cabeza (Resorte Point Spring): Kv = {r['Kv_cabeza_t_cm']:.2f} t/cm ({r['Kv_cabeza_t_cm']*100:.0f} t/m)\n"
                    f"   TABLA DE COEFICIENTES DE BALASTO (kh, kv) Y RIGIDECES (Kh, Kv) - TRAMO {z_cursor_kh}.00 m A {z_fin_kh_bloque}.00 m:"
                )
                fig.text(0.08, 0.84, info_balasto, va='top', ha='left', fontsize=8.0, family='monospace')
                
                ax_tab_kh = fig.add_axes([0.08, 0.12, 0.84, 0.65])
                ax_tab_kh.axis('off')
                
                h_kh = ["Prof. z (m)", "SUCS", "Comportamiento", "kh (t/m³)", "Kh lineal (t/m)", "kv (t/m³)", "Kv lineal (t/m)"]
                d_kh = []
                
                for z_i in range(z_cursor_kh, z_fin_kh_bloque + 1):
                    z_flt = min(float(z_i), r['L'])
                    e_match = None
                    for e_item in r['desglose_estratos']:
                        if e_item['zt'] < z_flt <= e_item['zb'] or (e_item['zt'] == 0 and z_flt == 0):
                            e_match = e_item
                            break
                    if e_match is None:
                        e_match = r['desglose_estratos'][-1]
                        
                    kh_v = e_match['kh_local']
                    kh_lin = kh_v * r['D']
                    
                    if e_match['tipo'] == 'Roca': kv_v = kh_v * 1.0
                    elif e_match['tipo'] == 'Friccionante': kv_v = kh_v * 0.85
                    else: kv_v = kh_v * 1.2
                    kv_lin = kv_v * r['D']
                    
                    d_kh.append([
                        f"-{z_flt:.2f} m",
                        str(e_match['sucs']),
                        str(e_match['tipo']),
                        f"{kh_v:.1f}",
                        f"{kh_lin:.1f}",
                        f"{kv_v:.1f}",
                        f"{kv_lin:.1f}"
                    ])
                    
                t_kh = ax_tab_kh.table(cellText=[h_kh] + d_kh, loc='center', cellLoc='center',
                                       colWidths=[0.16, 0.10, 0.18, 0.14, 0.14, 0.14, 0.14])
                t_kh.auto_set_font_size(False)
                t_kh.set_fontsize(7.2 if len(d_kh) > 18 else 8.0)
                t_kh.scale(1, 1.25)
                for j in range(7):
                    t_kh[0, j].set_facecolor('navy'); t_kh[0, j].set_text_props(color='white', weight='bold')
                for r_idx in range(1, len(d_kh) + 1):
                    if r_idx % 2 == 0:
                        for c_idx in range(7): t_kh[r_idx, c_idx].set_facecolor('#f4f4f4')
                        
                nota_kh = (
                    f"NOTA PARA EL MODELO ESTRUCTURAL:\n"
                    f"- Módulo de Balasto Promedio en Fuste: kh_prom = {r['kh_prom_t_m3']:.1f} t/m³ (Kh_prom = {r['Kh_lineal_t_m']:.1f} t/m).\n"
                    f"- Se recomienda asignar resortes puntuales en los nudos del fuste cada metro empleando las columnas 'Kh lineal' y 'Kv lineal'."
                )
                fig.text(0.08, 0.05, nota_kh, va='top', ha='left', fontsize=8.0, family='monospace', style='italic')
                pdf.savefig(fig); plt.close(); contador += 1
                
                z_cursor_kh = z_fin_kh_bloque + 1

        # --------------------------------------------------------
        # PÁGINA: GRÁFICAS DE COMPORTAMIENTO GEOTÉCNICO
        # --------------------------------------------------------
        fig = plt.figure(figsize=(8.5, 11))
        crear_encabezado_memoria(fig, "GRÁFICAS DE COMPORTAMIENTO GEOTÉCNICO", contador, total_paginas, p_proy, p_elem, p_fecha)
        
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
        crear_encabezado_memoria(fig, "RESUMEN TABULAR Y MATRICES DE DISEÑO ESTRUCTURAL", contador, total_paginas, p_proy, p_elem, p_fecha)
        
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
            "El análisis paramétrico corrobora la estabilidad geotécnica ante solicitaciones axiales de compresión y tensión.\n"
            "Las capacidades portantes asimilan la depresiación por relajación superficial (primeros 1.50 m) y la\n"
            "interacción destructiva en la base (1.0·D). Se avalan los módulos de rigidez Kv y kh para el modelo estructural."
        )
        fig.text(0.08, 0.05, nota_dictamen, wrap=True, fontsize=8.0, style='italic', weight='bold', color='darkgreen')

        pdf.savefig(fig); plt.close()

    return pdf_buffer.getvalue()