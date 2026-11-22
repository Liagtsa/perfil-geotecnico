# ==============================================================================
# MODULO: cimentaciones_superficiales.py
# VERSION: 1.0.0-NTC2023-NTCPUEBLA-SPT-PCA
# REVISION NORMATIVA: NTC-CDMX 2023 (Cap. 3.5) & NTC-PUEBLA (Cimentaciones)
# ==============================================================================

import math
import re
import numpy as np
import pandas as pd


def _convertir_spt_campo(valor_raw):
    """Convierte lecturas numericas y de rechazo SPT en golpes de diseno (tope 50)."""
    if pd.isna(valor_raw):
        return np.nan
    if isinstance(valor_raw, (int, float)):
        return min(float(valor_raw), 50.0) if valor_raw > 0 else np.nan

    val_str = str(valor_raw).strip().upper()
    if any(k in val_str for k in ['ABT', 'RECHAZO', 'NQ', 'PCA']):
        return 50.0 if 'PCA' not in val_str else np.nan

    match = re.search(r'(\d+)\s*/\s*(\d+)', val_str)
    if match:
        return 50.0

    try:
        n_num = float(val_str)
        return min(n_num, 50.0) if n_num > 0 else np.nan
    except ValueError:
        return np.nan


def _estimar_gamma_estrato(tipo, sucs, n60, w_pct=None, f_pct=None, bajo_naf=False):
    """Estima gamma (kN/m3) mediante relaciones de fases y compacidad/consistencia."""
    gamma_w = 9.81
    if tipo == 'Roca' or 'ROCA' in str(sucs).upper():
        return round(21.0 + (min(n60 if pd.notna(n60) else 50.0, 50.0) / 50.0) * 3.5, 2)

    f = float(f_pct) if (f_pct is not None and not pd.isna(f_pct)) else (10.0 if tipo == 'Friccionante' else 60.0)
    if f < 12.0:
        gs = 2.65
    elif f <= 50.0:
        gs = 2.68
    else:
        gs = 2.72 if 'CH' in str(sucs).upper() else 2.70

    gamma_fase = None
    if w_pct is not None and not pd.isna(w_pct) and float(w_pct) > 0:
        w = float(w_pct) / 100.0
        sr = 1.00 if bajo_naf else min(0.85, 0.45 + 0.015 * float(w_pct))
        e = (w * gs) / sr
        gamma_fase = gamma_w * (gs * (1.0 + w)) / (1.0 + e)

    n_ref = float(n60) if (n60 is not None and pd.notna(n60)) else 15.0
    if tipo == 'Friccionante':
        delta_f = 0.5 if f > 20.0 else 0.0
        gamma_spt = 14.5 + 0.12 * min(n_ref, 50.0) - delta_f
    else:
        gamma_spt = 14.0 + 0.15 * min(n_ref, 40.0)

    if gamma_fase is not None:
        gamma_final = 0.70 * gamma_fase + 0.30 * gamma_spt
    else:
        gamma_final = gamma_spt

    lim_inf = 13.5 if tipo == 'Cohesivo' else 14.5
    return round(max(lim_inf, min(gamma_final, 22.0)), 2)


def procesar_datos_superficiales(xls_path_o_bytes, metodo_exploracion="SPT"):
    """
    Lee el archivo Excel estandar (Datos_Sondeo.xlsx) y prepara la estratigrafia
    para cimentaciones superficiales tanto en modo SPT como en modo PCA
    (Pozo a Cielo Abierto con muestras inalteradas de laboratorio).
    """
    xls = pd.ExcelFile(xls_path_o_bytes)
    df_proy = pd.read_excel(xls, 'Proyecto').set_index('Parametro')['Valor'].to_dict()
    df_hum = pd.read_excel(xls, 'Humedades')
    df_ind = pd.read_excel(xls, 'PruebasIndice')

    hojas_excel = [h.upper() for h in xls.sheet_names]
    if metodo_exploracion.upper() == "PCA" and any(h in hojas_excel for h in ['PCA', 'MUESTRAS_PCA']):
        nombre_hoja_pca = xls.sheet_names[hojas_excel.index('PCA' if 'PCA' in hojas_excel else 'MUESTRAS_PCA')]
        df_fuente = pd.read_excel(xls, nombre_hoja_pca)
    else:
        df_fuente = df_hum.copy()

    try:
        naf = float(df_proy.get('NAF', np.nan))
        if pd.isna(naf):
            naf = None
    except (ValueError, TypeError):
        naf = None

    eficiencia = float(df_proy.get('Eficiencia_SPT', 60.0))
    diam_barr = float(df_proy.get('Diametro_Barrena_mm', 100.0))
    sin_liner = str(df_proy.get('Muestreador_Liner', 'CON_LINER')).upper() == 'SIN_LINER'

    config_zap = {
        'df_min': float(df_proy.get('Zap_Df_Min_m', 1.2)),
        'df_max': float(df_proy.get('Zap_Df_Max_m', 2.0)),
        'df_paso': float(df_proy.get('Zap_Df_Paso_m', 0.2)),
        'bc_min': float(df_proy.get('Zap_Corrida_B_Min_m', 0.6)),
        'bc_max': float(df_proy.get('Zap_Corrida_B_Max_m', 1.2)),
        'bc_paso': float(df_proy.get('Zap_Corrida_B_Paso_m', 0.2)),
        'ba_min': float(df_proy.get('Zap_Aislada_B_Min_m', 1.2)),
        'ba_max': float(df_proy.get('Zap_Aislada_B_Max_m', 2.0)),
        'ba_paso': float(df_proy.get('Zap_Aislada_B_Paso_m', 0.2)),
    }

    tramos = []
    sigma_v_eff = 0.0
    gamma_w = 9.81

    for _, row in df_fuente.iterrows():
        p_ini = float(row['Prof_ini'])
        p_fin = float(row['Prof_fin'])
        espesor = max(0.01, p_fin - p_ini)
        p_med = (p_ini + p_fin) / 2.0

        tipo = 'Friccionante'
        sucs = 'SM'
        f_pct = 20.0
        desc_estrato = ''

        coincidencias = df_ind[(df_ind['Prof_ini'] <= p_med) & (df_ind['Prof_fin'] >= p_med)]
        if not coincidencias.empty:
            fila_ind = coincidencias.iloc[0]
            sucs = str(fila_ind.get('SUCS', 'SM')).strip().upper()
            f_pct = fila_ind.get('F%', 20.0)
            desc_estrato = str(fila_ind.get('Descripción', fila_ind.get('Descripcion', ''))).strip()
            if 'Tipo_Mecanico' in fila_ind and pd.notna(fila_ind['Tipo_Mecanico']):
                tipo = str(fila_ind['Tipo_Mecanico']).capitalize()
            else:
                if 'ROCA' in sucs or sucs.startswith('R'):
                    tipo = 'Roca'
                elif sucs.startswith(('C', 'M', 'O', 'CL', 'CH', 'ML', 'MH')):
                    tipo = 'Cohesivo'
                else:
                    tipo = 'Friccionante'

        if 'SUCS' in row and pd.notna(row['SUCS']):
            sucs = str(row['SUCS']).strip().upper()
        if 'Tipo_Mecanico' in row and pd.notna(row['Tipo_Mecanico']):
            tipo = str(row['Tipo_Mecanico']).capitalize()

        phi_lab = float(row['Angulo_deg']) if ('Angulo_deg' in row and pd.notna(row['Angulo_deg'])) else np.nan
        coh_lab = float(row['Cohesion_kPa']) if ('Cohesion_kPa' in row and pd.notna(row['Cohesion_kPa'])) else np.nan
        es_lab = float(row['Es_kPa']) if ('Es_kPa' in row and pd.notna(row['Es_kPa'])) else np.nan

        n_campo = _convertir_spt_campo(row.get('SPT', np.nan))
        n_corr = n_campo
        if pd.notna(n_corr):
            if (tipo == 'Friccionante') and (naf is not None and p_med > naf) and n_corr > 15:
                n_corr = 15.0 + 0.5 * (n_corr - 15.0)
            ce = eficiencia / 60.0
            cr = 1.00 if p_med > 10.0 else (0.95 if p_med >= 6.0 else (0.85 if p_med >= 4.0 else 0.75))
            cb = 1.00 if diam_barr <= 115.0 else (1.05 if diam_barr <= 150.0 else 1.15)
            cs = 1.20 if sin_liner else 1.00
            n60 = min(n_corr * ce * cr * cb * cs, 50.0)
        else:
            n60 = np.nan

        w_pct = row.get('W%', np.nan)
        bajo_naf = (naf is not None and p_med > naf)
        gamma_manual = row.get('Gamma_kN_m3', np.nan)

        if pd.notna(gamma_manual) and float(gamma_manual) > 0:
            gamma = float(gamma_manual)
        else:
            gamma = _estimar_gamma_estrato(tipo, sucs, n60, w_pct, f_pct, bajo_naf)

        gamma_eff = (gamma - gamma_w) if bajo_naf else gamma
        sigma_v_eff += gamma_eff * espesor

        if pd.notna(n60):
            cn = min(2.0, math.sqrt(100.0 / max(sigma_v_eff, 5.0)))
            n1_60 = min(n60 * cn, 50.0)
        else:
            cn = np.nan
            n1_60 = np.nan

        if metodo_exploracion.upper() == "PCA":
            if pd.notna(phi_lab) or pd.notna(coh_lab):
                phi_dis = phi_lab if pd.notna(phi_lab) else 0.0
                c_dis = coh_lab if pd.notna(coh_lab) else 0.0
                if phi_dis > 0 and c_dis > 0:
                    tipo_efec = 'Cohesivo-Friccionante'
                elif phi_dis > 0:
                    tipo_efec = 'Friccionante'
                else:
                    tipo_efec = 'Cohesivo'
            else:
                if tipo == 'Cohesivo':
                    c_dis = 50.0
                    phi_dis = 0.0
                    tipo_efec = 'Cohesivo'
                else:
                    c_dis = 0.0
                    phi_dis = 30.0
                    tipo_efec = 'Friccionante'

            if pd.notna(es_lab) and es_lab > 0:
                es_dis = es_lab
            elif tipo_efec == 'Cohesivo':
                es_dis = max(300.0 * c_dis, 3000.0)
            elif tipo_efec == 'Cohesivo-Friccionante':
                es_dis = max(300.0 * c_dis + 400.0 * phi_dis, 6000.0)
            else:
                es_dis = max(600.0 * phi_dis, 8000.0)
            origen_param = "Lab. PCA (Muestra Inalterada)"
        else:
            n_val_160 = n1_60 if pd.notna(n1_60) else 15.0
            n_val_60 = n60 if pd.notna(n60) else 15.0
            if tipo == 'Cohesivo':
                c_dis = round(6.0 * n_val_60, 1)
                phi_dis = 0.0
                es_dis = round(300.0 * c_dis, 1)
                tipo_efec = 'Cohesivo'
            else:
                phi_dis = round(min(45.0, 27.5 + 0.92 * math.sqrt(max(n_val_160, 1.0))), 2)
                c_dis = 0.0
                es_dis = round(500.0 * n_val_160, 1)
                tipo_efec = 'Friccionante'
            origen_param = "Correlacion SPT (N1)60"

        tramos.append({
            'Prof_ini': p_ini,
            'Prof_fin': p_fin,
            'P_med': round(p_med, 2),
            'Espesor': round(espesor, 2),
            'SUCS': sucs,
            'Tipo': tipo_efec,
            'Gamma': gamma,
            'W_pct': w_pct,
            'N_campo': round(n_campo, 1) if pd.notna(n_campo) else np.nan,
            'N60': round(n60, 1) if pd.notna(n60) else np.nan,
            'Cn': round(cn, 3) if pd.notna(cn) else np.nan,
            'N1_60': round(n1_60, 1) if pd.notna(n1_60) else np.nan,
            'c_kPa': round(c_dis, 2),
            'phi_deg': round(phi_dis, 2),
            'Es_kPa': round(es_dis, 1),
            'Origen': origen_param,
            'Descripcion': desc_estrato
        })

    return pd.DataFrame(tramos), naf, config_zap


def _obtener_parametros_bulbo(df_tramos, naf_m, Df, B, es_corrida=False):
    """Ponderacion de parametros en bulbo de presiones (Df a Df + 1.5B / 2.0B)."""
    gamma_w = 9.81

    pv = 0.0
    for _, t in df_tramos.iterrows():
        if t['Prof_ini'] >= Df:
            break
        dz = min(t['Prof_fin'], Df) - t['Prof_ini']
        if dz <= 0:
            continue
        p_med_sub = t['Prof_ini'] + dz / 2.0
        g_eff = (t['Gamma'] - gamma_w) if (naf_m is not None and p_med_sub > naf_m) else t['Gamma']
        pv += g_eff * dz

    prof_max_sondeo = df_tramos['Prof_fin'].max()
    if Df > prof_max_sondeo:
        ult = df_tramos.iloc[-1]
        dz_ext = Df - prof_max_sondeo
        g_eff = (ult['Gamma'] - gamma_w) if (naf_m is not None and (prof_max_sondeo + dz_ext / 2.0) > naf_m) else ult['Gamma']
        pv += g_eff * dz_ext

    h_bulbo = 2.0 * B if es_corrida else 1.5 * B
    z_ini_b = Df
    z_fin_b = Df + h_bulbo

    peso_total = 0.0
    c_acum = 0.0
    tan_phi_acum = 0.0
    gamma_nat_acum = 0.0
    es_inv_acum = 0.0
    n60_acum = 0.0
    n1_60_acum = 0.0
    cn_acum = 0.0
    conteo_spt = 0.0

    for _, t in df_tramos.iterrows():
        overlap_ini = max(t['Prof_ini'], z_ini_b)
        overlap_fin = min(t['Prof_fin'], z_fin_b)
        dz = overlap_fin - overlap_ini
        if dz <= 0:
            continue

        c_acum += t['c_kPa'] * dz
        tan_phi_acum += math.tan(math.radians(t['phi_deg'])) * dz
        gamma_nat_acum += t['Gamma'] * dz
        es_inv_acum += (dz / max(t['Es_kPa'], 1000.0))
        if pd.notna(t['N60']):
            n60_acum += t['N60'] * dz
            n1_60_acum += t['N1_60'] * dz
            cn_acum += t['Cn'] * dz
            conteo_spt += dz
        peso_total += dz

    if peso_total <= 0:
        ult = df_tramos.iloc[-1]
        c_prom = float(ult['c_kPa'])
        phi_prom = float(ult['phi_deg'])
        gamma_nat = float(ult['Gamma'])
        es_prom = float(ult['Es_kPa'])
        n60_prom = float(ult['N60']) if pd.notna(ult['N60']) else np.nan
        n1_60_prom = float(ult['N1_60']) if pd.notna(ult['N1_60']) else np.nan
        cn_prom = float(ult['Cn']) if pd.notna(ult['Cn']) else np.nan
    else:
        c_prom = c_acum / peso_total
        phi_prom = math.degrees(math.atan(tan_phi_acum / peso_total))
        gamma_nat = gamma_nat_acum / peso_total
        es_prom = peso_total / es_inv_acum
        n60_prom = (n60_acum / conteo_spt) if conteo_spt > 0 else np.nan
        n1_60_prom = (n1_60_acum / conteo_spt) if conteo_spt > 0 else np.nan
        cn_prom = (cn_acum / conteo_spt) if conteo_spt > 0 else np.nan

    gamma_sum = max(gamma_nat - gamma_w, 5.0)
    if naf_m is None or naf_m >= (Df + B):
        gamma_cuna = gamma_nat
    elif naf_m <= Df:
        gamma_cuna = gamma_sum
    else:
        gamma_cuna = gamma_sum + ((naf_m - Df) / B) * (gamma_nat - gamma_sum)

    return {
        'pv': round(pv, 2),
        'c_kPa': round(c_prom, 2),
        'phi_deg': round(phi_prom, 2),
        'gamma_nat': round(gamma_nat, 2),
        'gamma_cuna': round(gamma_cuna, 2),
        'Es_kPa': round(es_prom, 1),
        'N60': round(n60_prom, 1) if pd.notna(n60_prom) else np.nan,
        'N1_60': round(n1_60_prom, 1) if pd.notna(n1_60_prom) else np.nan,
        'Cn': round(cn_prom, 3) if pd.notna(cn_prom) else np.nan,
        'h_bulbo': round(h_bulbo, 2)
    }


def _factor_influencia_rigida(B, L, es_corrida=False):
    """Calcula relacion m = L/B y factor de influencia de Steinbrenner para zapata rigida."""
    L_eff = B * 10.0 if es_corrida else max(L, B)
    m = L_eff / B
    If_flex = (2.0 / math.pi) * (
        math.log(m + math.sqrt(m**2 + 1.0)) +
        m * math.log((1.0 + math.sqrt(m**2 + 1.0)) / m)
    )
    If_rigida = If_flex * 0.80
    return round(m, 2), round(If_rigida, 4)


def evaluar_zapata_dual(df_tramos, naf_m, B, L, Df, es_corrida=False,
                        metodo_exploracion="SPT", FS=3.0, nu=0.30,
                        fr_cdmx_override=None, fr_puebla_override=None):
    """
    Evalua simultaneamente la capacidad de carga superficial bajo NTC-CDMX 2023
    y NTC-Puebla, seleccionando automaticamente la condicion MAS DESFAVORABLE.
    """
    L_calc = B * 10.0 if es_corrida else max(L, B)
    rel_BL = 0.0 if es_corrida else (B / L_calc)
    rel_DfB = min(Df / B, 2.0)

    bulbo = _obtener_parametros_bulbo(df_tramos, naf_m, Df, B, es_corrida=es_corrida)
    pv = bulbo['pv']
    c = bulbo['c_kPa']
    phi = bulbo['phi_deg']
    gamma_b = bulbo['gamma_cuna']
    Es = bulbo['Es_kPa']

    # Reduccion por falla local en arenas sueltas a medias (NTC-CDMX 3.5.1.2)
    phi_efec = phi
    if phi > 0 and pd.notna(bulbo['N1_60']):
        Dr = min(1.0, math.sqrt(max(bulbo['N1_60'], 1.0) / 60.0))
        if Dr < 0.67:
            f_loc = 0.67 + Dr - 0.75 * (Dr ** 2)
            phi_efec = math.degrees(math.atan(f_loc * math.tan(math.radians(phi))))

    phi_rad = math.radians(phi_efec)

    # 1. NTC-CDMX 2023 (Numeral 3.5.1)
    fr_cdmx = fr_cdmx_override if fr_cdmx_override is not None else 0.65

    if phi_efec <= 0.01:
        nc_cdmx = 5.14
        fc_cdmx = 1.0 + 0.25 * rel_DfB + 0.25 * rel_BL
        nc_star_cdmx = nc_cdmx * fc_cdmx
        nq_star_cdmx = 1.0
        ng_star_cdmx = 0.0
        term_c_cdmx = c * nc_star_cdmx
        term_q_cdmx = 0.0
        term_g_cdmx = 0.0
    else:
        nq_cdmx = math.exp(math.pi * math.tan(phi_rad)) * (math.tan(math.radians(45.0 + phi_efec / 2.0)) ** 2)
        nc_cdmx = (nq_cdmx - 1.0) / math.tan(phi_rad)
        ng_cdmx = 2.0 * (nq_cdmx + 1.0) * math.tan(phi_rad)

        fq_cdmx = 1.0 if es_corrida else (1.0 + rel_BL * math.tan(phi_rad))
        fc_cdmx = 1.0 if es_corrida else (1.0 + 0.25 * rel_BL)
        fg_cdmx = 1.0 if es_corrida else (1.0 - 0.40 * rel_BL)

        nc_star_cdmx = nc_cdmx * fc_cdmx
        nq_star_cdmx = nq_cdmx * fq_cdmx
        ng_star_cdmx = ng_cdmx * fg_cdmx

        term_c_cdmx = c * nc_star_cdmx
        term_q_cdmx = pv * (nq_star_cdmx - 1.0)
        term_g_cdmx = 0.5 * gamma_b * B * ng_star_cdmx

    q_ult_neta_cdmx = term_c_cdmx + term_q_cdmx + term_g_cdmx
    r_cdmx_kpa = q_ult_neta_cdmx * fr_cdmx + pv
    q_adm_cdmx_kpa = q_ult_neta_cdmx / FS + pv

    # 2. NTC-Puebla (Cimentaciones Superficiales)
    if fr_puebla_override is not None:
        fr_puebla = fr_puebla_override
    else:
        fr_puebla = 0.60 if metodo_exploracion.upper() == "PCA" else 0.50

    if phi_efec <= 0.01:
        nc_pue = 5.14
        sc_pue = 1.0 + 0.20 * rel_BL
        nc_star_pue = nc_pue * sc_pue
        nq_star_pue = 1.0
        ng_star_pue = 0.0
        term_c_pue = c * nc_star_pue
        term_q_pue = 0.0
        term_g_pue = 0.0
    else:
        kp_pue = math.tan(math.radians(45.0 + phi_efec / 2.0)) ** 2
        nq_pue = math.exp(math.pi * math.tan(phi_rad)) * kp_pue
        nc_pue = (nq_pue - 1.0) / math.tan(phi_rad)
        ng_pue = (nq_pue - 1.0) * math.tan(math.radians(1.4 * phi_efec))

        if es_corrida:
            sc_pue, sq_pue, sg_pue = 1.0, 1.0, 1.0
        else:
            sc_pue = 1.0 + 0.20 * rel_BL * kp_pue
            if phi_efec > 10.0:
                sq_pue = 1.0 + 0.10 * rel_BL * kp_pue
                sg_pue = 1.0 + 0.10 * rel_BL * kp_pue
            else:
                sq_pue, sg_pue = 1.0, 1.0

        nc_star_pue = nc_pue * sc_pue
        nq_star_pue = nq_pue * sq_pue
        ng_star_pue = ng_pue * sg_pue

        term_c_pue = c * nc_star_pue
        term_q_pue = pv * (nq_star_pue - 1.0)
        term_g_pue = 0.5 * gamma_b * B * ng_star_pue

    q_ult_neta_pue = term_c_pue + term_q_pue + term_g_pue
    r_puebla_kpa = q_ult_neta_pue * fr_puebla + pv
    q_adm_puebla_kpa = q_ult_neta_pue / FS + pv

    # 3. Seleccion de condicion mas desfavorable (gobernante)
    if r_puebla_kpa <= r_cdmx_kpa:
        norma_gob = "NTC-Puebla"
        r_gob_kpa = r_puebla_kpa
        fr_gob = fr_puebla
    else:
        norma_gob = "NTC-CDMX 2023"
        r_gob_kpa = r_cdmx_kpa
        fr_gob = fr_cdmx

    q_adm_fs_kpa = min(q_adm_cdmx_kpa, q_adm_puebla_kpa)
    q_diseno_kpa = min(r_gob_kpa, q_adm_fs_kpa)

    # 4. Asentamiento elastico y balasto vertical
    m_val, If_rig = _factor_influencia_rigida(B, L_calc, es_corrida=es_corrida)
    q_neta_serv = max(q_adm_fs_kpa - pv, 5.0)
    se_m = (q_neta_serv * B * (1.0 - nu**2) * If_rig) / max(Es, 1000.0)
    se_cm = se_m * 100.0

    ks_kpa_m = q_neta_serv / max(se_m, 1e-5)
    ks_ton_m3 = ks_kpa_m / 9.81
    ks_kg_cm3 = ks_ton_m3 / 1000.0

    kpa_a_kgcm2 = 0.01019716
    kpa_a_tonm2 = 1.0 / 9.81

    return {
        'Df': round(Df, 2),
        'B': round(B, 2),
        'L': round(L_calc, 2),
        'es_corrida': es_corrida,
        'tipo_zapata': "Corrida (L >> B)" if es_corrida else f"Aislada ({B:.2f} x {L_calc:.2f} m)",
        'metodo': metodo_exploracion,
        'pv_kpa': pv,
        'c_kpa': c,
        'phi_orig': phi,
        'phi_efec': round(phi_efec, 2),
        'gamma_cuna': gamma_b,
        'Es_kpa': Es,
        'N60': bulbo['N60'],
        'N1_60': bulbo['N1_60'],
        'Cn': bulbo['Cn'],
        'h_bulbo': bulbo['h_bulbo'],
        'fr_cdmx': fr_cdmx,
        'nc_star_cdmx': round(nc_star_cdmx, 2),
        'nq_star_cdmx': round(nq_star_cdmx, 2),
        'ng_star_cdmx': round(ng_star_cdmx, 2),
        'term_c_cdmx': round(term_c_cdmx, 2),
        'term_q_cdmx': round(term_q_cdmx, 2),
        'term_g_cdmx': round(term_g_cdmx, 2),
        'r_cdmx_kpa': round(r_cdmx_kpa, 2),
        'r_cdmx_kgcm2': round(r_cdmx_kpa * kpa_a_kgcm2, 2),
        'r_cdmx_tonm2': round(r_cdmx_kpa * kpa_a_tonm2, 2),
        'q_adm_cdmx_kpa': round(q_adm_cdmx_kpa, 2),
        'fr_puebla': fr_puebla,
        'nc_star_pue': round(nc_star_pue, 2),
        'nq_star_pue': round(nq_star_pue, 2),
        'ng_star_pue': round(ng_star_pue, 2),
        'term_c_pue': round(term_c_pue, 2),
        'term_q_pue': round(term_q_pue, 2),
        'term_g_pue': round(term_g_pue, 2),
        'r_puebla_kpa': round(r_puebla_kpa, 2),
        'r_puebla_kgcm2': round(r_puebla_kpa * kpa_a_kgcm2, 2),
        'r_puebla_tonm2': round(r_puebla_kpa * kpa_a_tonm2, 2),
        'q_adm_puebla_kpa': round(q_adm_puebla_kpa, 2),
        'norma_gobernante': norma_gob,
        'fr_gob': fr_gob,
        'r_gob_kpa': round(r_gob_kpa, 2),
        'r_gob_kgcm2': round(r_gob_kpa * kpa_a_kgcm2, 2),
        'r_gob_tonm2': round(r_gob_kpa * kpa_a_tonm2, 2),
        'q_adm_kpa': round(q_adm_fs_kpa, 2),
        'q_adm_kgcm2': round(q_adm_fs_kpa * kpa_a_kgcm2, 2),
        'q_adm_tonm2': round(q_adm_fs_kpa * kpa_a_tonm2, 2),
        'q_diseno_kgcm2': round(q_diseno_kpa * kpa_a_kgcm2, 2),
        'FS': FS,
        'nu': nu,
        'm': m_val,
        'If': If_rig,
        'Se_cm': round(se_cm, 3),
        'ks_ton_m3': round(ks_ton_m3, 1),
        'ks_kg_cm3': round(ks_kg_cm3, 2)
    }


def generar_analisis_parametrico_zapatas(df_tramos, naf_m, df_list, b_corridas, b_aisladas,
                                         rel_LB_aislada=1.0, metodo_exploracion="SPT",
                                         FS=3.0, nu=0.30, fr_cdmx_override=None, fr_puebla_override=None):
    """Evalua todas las combinaciones parametricas de Df y B para zapatas corridas y aisladas."""
    resultados = []

    for df in df_list:
        for b in b_corridas:
            res_c = evaluar_zapata_dual(
                df_tramos, naf_m, B=b, L=b * 10.0, Df=df, es_corrida=True,
                metodo_exploracion=metodo_exploracion, FS=FS, nu=nu,
                fr_cdmx_override=fr_cdmx_override, fr_puebla_override=fr_puebla_override
            )
            resultados.append(res_c)

        for b in b_aisladas:
            l_ais = round(b * rel_LB_aislada, 2)
            res_a = evaluar_zapata_dual(
                df_tramos, naf_m, B=b, L=l_ais, Df=df, es_corrida=False,
                metodo_exploracion=metodo_exploracion, FS=FS, nu=nu,
                fr_cdmx_override=fr_cdmx_override, fr_puebla_override=fr_puebla_override
            )
            resultados.append(res_a)

    df_res = pd.DataFrame(resultados)
    df_corr = df_res[df_res['es_corrida']].copy()
    df_ais = df_res[~df_res['es_corrida']].copy()

    return {
        'df_completo': df_res,
        'df_corridas': df_corr,
        'df_aisladas': df_ais,
        'mat_corr_r_gob_kgcm2': df_corr.pivot(index='Df', columns='B', values='r_gob_kgcm2') if not df_corr.empty else pd.DataFrame(),
        'mat_corr_qadm_kgcm2': df_corr.pivot(index='Df', columns='B', values='q_adm_kgcm2') if not df_corr.empty else pd.DataFrame(),
        'mat_corr_se_cm': df_corr.pivot(index='Df', columns='B', values='Se_cm') if not df_corr.empty else pd.DataFrame(),
        'mat_corr_ks_tm3': df_corr.pivot(index='Df', columns='B', values='ks_ton_m3') if not df_corr.empty else pd.DataFrame(),
        'mat_ais_r_gob_kgcm2': df_ais.pivot(index='Df', columns='B', values='r_gob_kgcm2') if not df_ais.empty else pd.DataFrame(),
        'mat_ais_qadm_kgcm2': df_ais.pivot(index='Df', columns='B', values='q_adm_kgcm2') if not df_ais.empty else pd.DataFrame(),
        'mat_ais_se_cm': df_ais.pivot(index='Df', columns='B', values='Se_cm') if not df_ais.empty else pd.DataFrame(),
        'mat_ais_ks_tm3': df_ais.pivot(index='Df', columns='B', values='ks_ton_m3') if not df_ais.empty else pd.DataFrame(),
        'metodo_exploracion': metodo_exploracion,
        'rel_LB_aislada': rel_LB_aislada,
        'FS': FS,
        'nu': nu,
        'naf_m': naf_m
    }