import numpy as np
import pandas as pd
import re
import math

def convertir_spt_campo(valor_raw):
    """
    Convierte lecturas numéricas y de rechazo de campo en N de diseño.
    Aplica el criterio conservador normativo de topar a 50 golpes máximos.
    """
    if pd.isna(valor_raw): return np.nan
    if isinstance(valor_raw, (int, float)):
        return min(float(valor_raw), 50.0) if valor_raw > 0 else np.nan

    val_str = str(valor_raw).strip().upper()
    if 'ABT' in val_str or 'RECHAZO' in val_str or 'NQ' in val_str:
        return 50.0
        
    match = re.search(r'(\d+)\s*/\s*(\d+)', val_str)
    if match:
        return 50.0

    try:
        n_num = float(val_str)
        return min(n_num, 50.0) if n_num > 0 else np.nan
    except ValueError:
        return np.nan


def estimar_peso_volumetrico(tipo, sucs, n60, w_pct=None, f_pct=None, bajo_naf=False):
    """
    Estima el peso volumétrico gamma (en kN/m3) combinando relaciones gravimétricas
    de fases (w%, F%, Gs) con la compacidad/consistencia empírica de N60.
    """
    gamma_w = 9.81
    if tipo == 'Roca' or 'ROCA' in str(sucs).upper():
        gamma_roca = 21.0 + (min(n60, 50.0) / 50.0) * 3.5
        return round(gamma_roca, 2)
        
    f = float(f_pct) if (f_pct is not None and not pd.isna(f_pct)) else (10.0 if tipo == 'Friccionante' else 60.0)
    
    if f < 12.0: gs = 2.65
    elif f <= 50.0: gs = 2.68
    else: gs = 2.72 if 'CH' in str(sucs).upper() else 2.70
        
    gamma_fase = None
    if w_pct is not None and not pd.isna(w_pct) and float(w_pct) > 0:
        w = float(w_pct) / 100.0
        sr = 1.00 if bajo_naf else min(0.85, 0.45 + 0.015 * float(w_pct))
        e = (w * gs) / sr
        gamma_fase = gamma_w * (gs * (1.0 + w)) / (1.0 + e)
        
    if tipo == 'Friccionante':
        delta_f = 0.5 if f > 20.0 else 0.0
        gamma_spt = 14.5 + 0.12 * min(n60, 50.0) - delta_f
    else:
        gamma_spt = 14.0 + 0.15 * min(n60, 40.0)
        
    if gamma_fase is not None:
        gamma_final = 0.70 * gamma_fase + 0.30 * gamma_spt
    else:
        gamma_final = gamma_spt
        
    lim_inf = 13.5 if tipo == 'Cohesivo' else 14.5
    lim_sup = 22.0
    return round(max(lim_inf, min(gamma_final, lim_sup)), 2)


def procesar_sondeo_completo(xls_path_o_bytes):
    """
    Lee las hojas del archivo Excel, interpreta rechazos de SPT, aplica correcciones,
    evalúa el peso específico de cada estrato y retorna la configuración unificada.
    """
    xls = pd.ExcelFile(xls_path_o_bytes)
    df_proy = pd.read_excel(xls, 'Proyecto').set_index('Parametro')['Valor'].to_dict()
    df_hum = pd.read_excel(xls, 'Humedades')
    df_ind = pd.read_excel(xls, 'PruebasIndice')
    
    try: naf = float(df_proy.get('NAF', np.nan))
    except (ValueError, TypeError): naf = None
        
    eficiencia = float(df_proy.get('Eficiencia_SPT', 60.0))
    diam_barr = float(df_proy.get('Diametro_Barrena_mm', 100.0))
    sin_liner = str(df_proy.get('Muestreador_Liner', 'CON_LINER')).upper() == 'SIN_LINER'
    
    config_geometria = {
        'd_min': float(df_proy.get('Diametro_Min_m', 0.8)),
        'd_max': float(df_proy.get('Diametro_Max_m', 1.6)),
        'd_paso': float(df_proy.get('Diametro_Paso_m', 0.2)),
        'l_min': float(df_proy.get('Longitud_Min_m', 20.0)),
        'l_max': float(df_proy.get('Longitud_Max_m', 25.0)),
        'l_paso': float(df_proy.get('Longitud_Paso_m', 1.0)),
        'diametros_lista': str(df_proy.get('Diametros_Lista', '')).strip(),
        'longitudes_lista': str(df_proy.get('Longitudes_Lista', '')).strip()
    }
    
    tramos = []
    sigma_v_eff = 0.0
    gamma_w = 9.81
    
    for _, row in df_hum.iterrows():
        p_ini = float(row['Prof_ini'])
        p_fin = float(row['Prof_fin'])
        espesor = p_fin - p_ini
        p_med = (p_ini + p_fin) / 2.0
        
        tipo = 'Friccionante'
        sucs = 'SM'
        f_pct = 20.0
        coincidencias = df_ind[(df_ind['Prof_ini'] <= p_med) & (df_ind['Prof_fin'] >= p_med)]
        if not coincidencias.empty:
            fila_ind = coincidencias.iloc[0]
            sucs = str(fila_ind.get('SUCS', 'SM')).strip().upper()
            f_pct = fila_ind.get('F%', 20.0)
            if 'Tipo_Mecanico' in fila_ind and pd.notna(fila_ind['Tipo_Mecanico']):
                tipo = str(fila_ind['Tipo_Mecanico']).capitalize()
            else:
                if 'ROCA' in sucs or sucs.startswith('R'): tipo = 'Roca'
                elif sucs.startswith(('C', 'M', 'O', 'CL', 'CH', 'ML', 'MH')): tipo = 'Cohesivo'
                else: tipo = 'Friccionante'
                    
        rqd_cm = row.get('RQD_cm', np.nan)
        rec_cm = row.get('Recuperacion_cm', np.nan)
        icr_pct = np.nan
        if pd.notna(rqd_cm) and float(rqd_cm) > 0:
            if pd.notna(rec_cm) and float(rec_cm) > 0:
                icr_pct = min((float(rqd_cm) / float(rec_cm)) * 100.0, 100.0)
            else:
                icr_pct = min((float(rqd_cm) / (espesor * 100.0)) * 100.0, 100.0)
                
        uc_mpa = row.get('UC_Roca_MPa', np.nan)
        plt_mpa = row.get('PLT_MPa', np.nan)
        qu_kpa = np.nan
        if pd.notna(uc_mpa) and float(uc_mpa) > 0:
            qu_kpa = float(uc_mpa) * 1000.0
        elif pd.notna(plt_mpa) and float(plt_mpa) > 0:
            qu_kpa = float(plt_mpa) * 22.0 * 1000.0
            
        if pd.notna(qu_kpa) or pd.notna(icr_pct):
            tipo = 'Roca'
            if pd.isna(icr_pct): icr_pct = 20.0

        n_campo = convertir_spt_campo(row.get('SPT', np.nan))
        if pd.isna(n_campo) or n_campo <= 0:
            n_campo = 50.0 if tipo == 'Roca' else 10.0
            
        n_corr = n_campo
        # Corrección por dilatancia bajo NAF en arenas finas sumergidas
        if (tipo == 'Friccionante') and (naf is not None and p_med > naf) and n_corr > 15:
            n_corr = 15.0 + 0.5 * (n_corr - 15.0)
            
        ce = eficiencia / 60.0
        cr = 1.00 if p_med > 10.0 else (0.95 if p_med >= 6.0 else (0.85 if p_med >= 4.0 else 0.75))
        cb = 1.00 if diam_barr <= 115.0 else (1.05 if diam_barr <= 150.0 else 1.15)
        cs = 1.20 if sin_liner else 1.00
        n60 = min(n_corr * ce * cr * cb * cs, 50.0)
        
        w_pct = row.get('W%', np.nan)
        bajo_naf = (naf is not None and p_med > naf)
        gamma_manual = row.get('Gamma_kN_m3', np.nan)
        
        if pd.notna(gamma_manual) and float(gamma_manual) > 0:
            gamma = float(gamma_manual)
        else:
            gamma = estimar_peso_volumetrico(tipo, sucs, n60, w_pct, f_pct, bajo_naf)
            
        gamma_eff = (gamma - gamma_w) if bajo_naf else gamma
        sigma_v_eff += gamma_eff * espesor
        
        cn = min(np.sqrt(100.0 / max(sigma_v_eff, 5.0)), 1.7)
        n1_60 = min(n60 * cn, 50.0)
        
        tramos.append({
            'Prof_ini': p_ini, 'Prof_fin': p_fin, 'P_med': p_med, 'Espesor': espesor,
            'Tipo': tipo, 'SUCS': sucs, 'Gamma': gamma, 'Sigma_v_eff': round(sigma_v_eff, 1),
            'N_campo': round(n_campo, 1), 'N60': round(n60, 1), 'N1_60': round(n1_60, 1),
            'Cu_lab': row.get('Cohesion_kPa', np.nan),
            'ICR': round(icr_pct, 1) if pd.notna(icr_pct) else np.nan,
            'qu_kPa': round(qu_kpa, 1) if pd.notna(qu_kpa) else np.nan
        })
        
    return pd.DataFrame(tramos), naf, config_geometria


def evaluar_pila(df_tramos, naf_m, diametro_m, longitud_m, tipo_elemento="Pila",
                 con_campana=False, rel_campana=1.5, h_campana_m=1.0,
                 factor_cu_spt=6.0, gamma_concreto=24.0, fc_kg_cm2=300.0,
                 qu_roca_conservador=15000.0):
    """
    Evalúa la capacidad de carga vertical a compresión y tensión según NTC-CDMX 2023:
    1. Roca: Mecánica de rocas (3.6.2.3.5) con ICR/RQD y qu conservador si no hay ensaye destructivo.
    2. Suelos Friccionantes: Fricción empírica SPT (3.6.2.3.2.3), fui <= 200 kPa, FR=0.50.
    3. Suelos Cohesivos: Método Alfa a partir de Su (cu = 6*N60 o laboratorio), fui <= 200 kPa, FR=0.70.
       Punta en cohesivos con Nc*=9.0 y factor Fre = (B+1)/(2B+1).
    4. NAF: Considera afectación por subpresión en pv_total y peso propio neto del concreto.
    """
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
    
    cf_comp_kn = 0.0
    cf_tens_kn = 0.0
    pv_total = 0.0
    
    f_red_fricc = 0.80 if l_d > 20.0 else 0.60
    f_red_cohes = 0.80
    f_red_roca = 0.70
    Ec_ton_m2 = (14000.0 * np.sqrt(fc_kg_cm2)) * 10.0
    
    desglose_estratos = []
    kh_acumulado = 0.0
    peso_estratos = 0.0

    for _, tramo in df_tramos.iterrows():
        if tramo['Prof_ini'] >= longitud_m: break
        long_real = min(tramo['Prof_fin'], longitud_m) - tramo['Prof_ini']
        if long_real <= 0: continue
            
        p_med = tramo['P_med']
        bajo_naf = (naf_m is not None and p_med > naf_m)
        gamma_eff = (tramo['Gamma'] - gamma_w) if bajo_naf else tramo['Gamma']
        pv_total += gamma_eff * long_real
        
        ini_fuste = max(tramo['Prof_ini'], z_act_ini)
        fin_fuste = min(tramo['Prof_fin'], z_act_fin)
        long_fuste_efectiva = max(0.0, fin_fuste - ini_fuste)
        
        n60 = tramo['N60']
        tipo = tramo['Tipo']
        
        if tipo == 'Roca':
            icr = tramo['ICR'] if pd.notna(tramo.get('ICR')) else 20.0
            qu_medido = pd.notna(tramo.get('qu_kPa')) and tramo['qu_kPa'] > 0
            qu = tramo['qu_kPa'] if qu_medido else qu_roca_conservador
            alpha_e = 10.0 ** (0.013 * icr - 1.34)
            fui = min(1.4 * pa * np.sqrt(alpha_e * qu / pa), 3000.0)
            fr_f = 0.65
            tramo_comp = fr_f * (pp * fui * long_fuste_efectiva)
            tramo_tens = fr_f * (pp * (fui * f_red_roca) * long_fuste_efectiva)
            Em_kPa = max(alpha_e * 300.0 * qu, 150000.0)
            kh_local = (Em_kPa / (diametro_m * (1.0 - 0.25**2))) / 9.81
            norma = "NTC CDMX 3.6.2.3.5 (Roca)"
        elif tipo == 'Friccionante':
            fui = min(2.5 * n60, 200.0)
            fr_f = 0.50
            tramo_comp = fr_f * (pp * fui * long_fuste_efectiva)
            tramo_tens = fr_f * (pp * (fui * f_red_fricc) * long_fuste_efectiva)
            nh_ton_m3 = 25.0 * n60
            kh_local = nh_ton_m3 * (tramo['P_med'] / diametro_m)
            norma = "NTC CDMX 3.6.2.3.2.3 (Arenas)"
        else: # Cohesivo / Limo con Método Alfa
            cu = tramo['Cu_lab'] if (pd.notna(tramo.get('Cu_lab')) and tramo['Cu_lab'] > 0) else (factor_cu_spt * n60)
            alpha = max(0.35, min(1.0, 0.55 * np.sqrt(100.0 / max(cu, 25.0))))
            fui = min(alpha * cu, 200.0)
            fr_f = 0.70
            tramo_comp = fr_f * (pp * fui * long_fuste_efectiva)
            tramo_tens = fr_f * (pp * (fui * f_red_cohes) * long_fuste_efectiva)
            kh_local = (67.0 * cu / diametro_m) / 9.81
            norma = "NTC CDMX 3.6.2.3.2.1 (Método Alfa)"
            
        cf_comp_kn += tramo_comp
        cf_tens_kn += tramo_tens
        kh_acumulado += kh_local * long_real
        peso_estratos += long_real

        desglose_estratos.append({
            'zt': tramo['Prof_ini'], 'zb': min(tramo['Prof_fin'], longitud_m),
            'l_efec': long_fuste_efectiva, 'tipo': tipo, 'sucs': tramo['SUCS'],
            'n60': n60, 'fui_kpa': fui, 'fr_f': fr_f,
            'f_nom_ton': (pp * fui * long_fuste_efectiva) / 9.81,
            'f_red_ton': tramo_comp / 9.81,
            'kh_local': kh_local, 'norma': norma
        })

    kh_prom_ton_m3 = (kh_acumulado / peso_estratos) if peso_estratos > 0 else 1500.0
    Kh_resorte_lineal = kh_prom_ton_m3 * diametro_m

    # Punta
    estrato_punta = df_tramos[(df_tramos['Prof_ini'] <= longitud_m) & (df_tramos['Prof_fin'] >= longitud_m)]
    estrato_p = estrato_punta.iloc[0] if not estrato_punta.empty else df_tramos.iloc[-1]
    tipo_p = estrato_p['Tipo']
    
    if tipo_p == 'Roca':
        icr_p = estrato_p['ICR'] if pd.notna(estrato_p.get('ICR')) else 20.0
        qu_medido = pd.notna(estrato_p.get('qu_kPa')) and estrato_p['qu_kPa'] > 0
        qu_p = estrato_p['qu_kPa'] if qu_medido else qu_roca_conservador
        sd = max(0.05, 0.05 + 0.95 * (icr_p / 100.0)**2)
        td = 0.002
        ksp = (3.0 + sd / d_punta) / ((10.0 / 3.0) * np.sqrt(1.0 + 300.0 * (td / sd)))
        d_fact = min(1.0 + 0.4 * (longitud_m / d_punta), 3.0)
        pu_kpa = qu_p * ksp * d_fact
        fr_p = 0.35
        cp_comp_kn = fr_p * (pu_kpa * ap)
        Em_base = max((10.0 ** (0.013 * icr_p - 1.34)) * 300.0 * qu_p, 300000.0)
        kv_base_ton_m3 = (Em_base / (d_punta * (1.0 - 0.25**2))) / 9.81
        detalles_punta = f"Roca (qu={qu_p/1000:.1f} MPa, ICR={icr_p:.1f}%)"
        norma_punta = "NTC CDMX 3.6.2.3.5 (Roca)"
    elif tipo_p == 'Friccionante':
        zona_inf = longitud_m + 2.0 * d_punta
        pts = df_tramos[(df_tramos['Prof_fin'] >= longitud_m) & (df_tramos['Prof_ini'] <= zona_inf)]
        n60_punta = min(pts['N60'].mean() if not pts.empty else estrato_p['N60'], 75.0)
        pu_kpa = 57.5 * n60_punta
        fr_p = 0.35
        cp_comp_kn = fr_p * (pu_kpa * ap)
        Es_base = 3500.0 * n60_punta
        kv_base_ton_m3 = (Es_base / (d_punta * (1.0 - 0.30**2))) / 9.81
        detalles_punta = f"Arena (N60_punta={n60_punta:.1f})"
        norma_punta = "NTC CDMX 3.6.2.3.2.4.2 (SPT)"
    else: # Cohesivo con factor Fre y Nc* = 9.0
        cu_p = estrato_p['Cu_lab'] if (pd.notna(estrato_p.get('Cu_lab')) and estrato_p['Cu_lab'] > 0) else (factor_cu_spt * estrato_p['N60'])
        fre = (d_punta + 1.0) / (2.0 * d_punta + 1.0) if d_punta > 0.5 else 1.0
        fr_p = 0.35
        nc_star = 9.0
        cp_comp_kn = (cu_p * nc_star * fr_p + pv_total) * ap * fre
        pu_kpa = cp_comp_kn / (fr_p * ap)
        Es_base = 600.0 * cu_p
        kv_base_ton_m3 = (Es_base / (d_punta * (1.0 - 0.40**2))) / 9.81
        detalles_punta = f"Limo/Arcilla (cu={cu_p:.1f} kPa, Nc*=9, Fre={fre:.3f})"
        norma_punta = "NTC Puebla / CDMX (Cohesivo)"

    vol_fuste = (np.pi * (diametro_m**2) / 4.0) * (longitud_m - (h_campana_m if con_campana else 0.0))
    vol_campana = ((np.pi * h_campana_m / 12.0) * (diametro_m**2 + diametro_m * d_punta + d_punta**2)) if con_campana else 0.0
    vol_total = vol_fuste + vol_campana
    
    # Afectación del NAF en peso propio de la pila (Tensión / Extracción)
    if naf_m is not None and naf_m < longitud_m:
        h_seco = min(naf_m, longitud_m)
        h_sum = max(0.0, longitud_m - naf_m)
        frac_sum = h_sum / longitud_m
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
    
    # Retornamos el diccionario completo con todos los campos y alias necesarios
    return {
        'Diametro_m': diametro_m,
        'Longitud_m': longitud_m,
        'D': diametro_m,
        'L': longitud_m,
        'd_punta': d_punta,
        'Area_fuste': np.pi * (diametro_m**2) / 4.0,
        'Area_punta': ap,
        'Perimetro': pp,
        'z_act_ini': z_act_ini,
        'z_act_fin': z_act_fin,
        'Long_fuste_activa_m': round(max(0.0, z_act_fin - z_act_ini), 2),
        'L_fuste_activa': max(0.0, z_act_fin - z_act_ini),
        'desglose_estratos': desglose_estratos,
        'Cf_nom_ton': sum(e['f_nom_ton'] for e in desglose_estratos),
        'Cf_comp_ton': round(cf_comp_kn / 9.81, 1),
        'pu_kpa': pu_kpa,
        'pu_ton_m2': round(pu_kpa / 9.81, 1),
        'Rup_ton': round((pu_kpa * ap) / 9.81, 1),
        'Cp_comp_ton': round(cp_comp_kn / 9.81, 1),
        'R_comp_ton': round(r_comp_ton, 1),
        'W_ton': round(peso_kn / 9.81, 1),
        'W_concreto_ton': round(peso_kn / 9.81, 1),
        'Cf_tens_ton': round(cf_tens_kn / 9.81, 1),
        'R_tens_ton': round(r_tens_ton, 1),
        'As_tensin_cm2': round(as_req_cm2, 1),
        'detalles_punta': detalles_punta,
        'norma_punta': norma_punta,
        'kh_t_m3': round(kh_prom_ton_m3, 1),
        'kh_prom_t_m3': round(kh_prom_ton_m3, 1),
        'Kh_lineal_t_m': round(Kh_resorte_lineal, 1),
        'kv_base_t_m3': round(kv_base_ton_m3, 1),
        'Kv_cabeza_t_m': round(Kv_cabeza_ton_m, 1),
        'Kv_cabeza_t_cm': round(Kv_cabeza_ton_cm, 2)
    }


def generar_matrices_parametricas(df_tramos, naf_m, diametros, profundidades, tipo_elemento="Pila",
                                   con_campana=False, rel_campana=1.5, h_campana_m=1.0):
    res = []
    for l in profundidades:
        for d in diametros:
            val = evaluar_pila(df_tramos, naf_m, d, l, tipo_elemento=tipo_elemento,
                               con_campana=con_campana, rel_campana=rel_campana, h_campana_m=h_campana_m)
            res.append(val)
            
    df_res = pd.DataFrame(res)
    return {
        'df_completo': df_res,
        'matriz_compresion': df_res.pivot(index='Longitud_m', columns='Diametro_m', values='R_comp_ton'),
        'matriz_extraccion': df_res.pivot(index='Longitud_m', columns='Diametro_m', values='R_tens_ton'),
        'matriz_acero': df_res.pivot(index='Longitud_m', columns='Diametro_m', values='As_tensin_cm2'),
        'matriz_kh': df_res.pivot(index='Longitud_m', columns='Diametro_m', values='kh_t_m3'),
        'matriz_Kv': df_res.pivot(index='Longitud_m', columns='Diametro_m', values='Kv_cabeza_t_cm'),
        'con_campana': con_campana,
        'rel_campana': rel_campana,
        'h_campana_m': h_campana_m,
        'naf_m': naf_m
    }


def obtener_tabla_balasto_metro_a_metro(df_tramos, naf_m, diametro_m, longitud_m):
    n_metros = int(math.ceil(longitud_m))
    filas = []
    
    for z in range(1, n_metros + 1):
        z_flt = min(float(z), longitud_m)
        e_match = None
        for _, tramo in df_tramos.iterrows():
            if tramo['Prof_ini'] < z_flt <= tramo['Prof_fin'] or (tramo['Prof_ini'] == 0 and z_flt == 0):
                e_match = tramo
                break
        if e_match is None: e_match = df_tramos.iloc[-1]
            
        tipo = e_match['Tipo']
        sucs = e_match['SUCS']
        n60 = e_match['N60']
        
        if tipo == 'Roca':
            icr = e_match['ICR'] if pd.notna(e_match.get('ICR')) else 20.0
            qu_medido = pd.notna(e_match.get('qu_kPa')) and e_match['qu_kPa'] > 0
            qu = e_match['qu_kPa'] if qu_medido else 15000.0
            alpha_e = 10.0 ** (0.013 * icr - 1.34)
            Em_kPa = max(alpha_e * 300.0 * qu, 150000.0)
            kh_local = (Em_kPa / (diametro_m * (1.0 - 0.25**2))) / 9.81
            kv_local = kh_local * 1.0
        elif tipo == 'Friccionante':
            nh_ton_m3 = 25.0 * n60
            kh_local = nh_ton_m3 * (z_flt / diametro_m)
            kv_local = kh_local * 0.85
        else:
            cu = e_match['Cu_lab'] if (pd.notna(e_match.get('Cu_lab')) and e_match['Cu_lab'] > 0) else (6.0 * n60)
            kh_local = (67.0 * cu / diametro_m) / 9.81
            kv_local = kh_local * 1.2
            
        kh_lin = kh_local * diametro_m
        kv_lin = kv_local * diametro_m
        
        filas.append({
            'Profundidad (m)': f"-{z_flt:.2f} m",
            'SUCS': str(sucs),
            'Comportamiento': str(tipo),
            'N60': round(n60, 1),
            'kh (t/m³)': round(kh_local, 1),
            'Kh lineal (t/m)': round(kh_lin, 1),
            'kv (t/m³)': round(kv_local, 1),
            'Kv lineal (t/m)': round(kv_lin, 1)
        })
        
    return pd.DataFrame(filas)