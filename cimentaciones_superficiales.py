# ==============================================================================
# MODULO: cimentaciones_superficiales.py
# VERSION: 2.0.0-NTC-CDMX-2023-FALLA-SERVICIO-CARGAS-ESTRUCTURALES
# NORMATIVA: NTC-CDMX 2023 (Cimentaciones — Num. 3.5.1, 3.6.1, Cap. 4 Estado Limite de Servicio)
# DESCRIPCION:
#   Calcula la capacidad de carga admisible y recomendada para zapatas corridas
#   y aisladas (combinando Estado Limite de Falla y Estado Limite de Servicio) y
#   permite revisar los asentamientos elasticos reales bajo las cargas dadas por
#   el estructurista (V, H, Mx, My) comparadas contra los limites NTC-CDMX 2023.
# ==============================================================================

import math
import re
import numpy as np
import pandas as pd


def _a_float(val, default=np.nan):
    if val is None or pd.isna(val):
        return default
    if isinstance(val, (int, float, np.number)):
        fval = float(val)
        return default if math.isnan(fval) else fval
    s = str(val).strip()
    if s == '' or s.lower() in ('nan', 'none', 'null', '-', 's/d', 'n/a'):
        return default
    try:
        fval = float(s.replace(',', '.'))
        return default if math.isnan(fval) else fval
    except ValueError:
        return default


def _convertir_spt_raw(valor_raw):
    if valor_raw is None or pd.isna(valor_raw):
        return np.nan
    if isinstance(valor_raw, (int, float, np.number)):
        fval = float(valor_raw)
        return min(fval, 50.0) if fval > 0 else np.nan
    s = str(valor_raw).strip().upper()
    if s in ('', 'NAN', 'NONE', '-', 'PCA', 'TS'):
        return np.nan
    if any(k in s for k in ['ABT', 'RECHAZO', 'NQ', 'NX']):
        return 50.0
    m = re.search(r'(\d+)\s*/\s*(\d+)', s)
    if m:
        return min(float(m.group(1)), 50.0)
    return _a_float(s, np.nan)


def procesar_datos_superficiales(xls_path_o_bytes, metodo_exploracion="SPT"):
    """
    Procesa el archivo Datos_Sondeo.xlsx para cimentaciones superficiales
    bajo NTC-CDMX 2023 en modo SPT o PCA, extrayendo parametros de corte,
    modulo elastico secante Es_kPa y configuracion de rangos/limites de deformacion.
    """
    xls = pd.ExcelFile(xls_path_o_bytes)
    df_proy_raw = pd.read_excel(xls, 'Proyecto')
    df_proy_raw['Parametro'] = df_proy_raw['Parametro'].astype(str).str.strip()
    df_proy = df_proy_raw.set_index('Parametro')['Valor'].to_dict()

    df_hum = pd.read_excel(xls, 'Humedades')
    df_ind = pd.read_excel(xls, 'PruebasIndice')

    naf_raw = _a_float(df_proy.get('NAF', np.nan), np.nan)
    naf = None if pd.isna(naf_raw) else naf_raw

    eficiencia = _a_float(df_proy.get('Eficiencia_SPT', 60.0), 60.0)
    diam_barr = _a_float(df_proy.get('Diametro_Barrena_mm', 100.0), 100.0)
    sin_liner = str(df_proy.get('Muestreador_Liner', 'CON_LINER')).strip().upper() == 'SIN_LINER'
    gamma_def = _a_float(df_proy.get('Gamma_Default_kN_m3', 18.0), 18.0)

    for col_n in ['Prof_ini', 'Prof_fin', 'W%', 'Gamma_kN_m3', 'Angulo_deg', 'Cohesion_kPa', 'Es_kPa', 'UC_Roca_MPa']:
        if col_n in df_hum.columns:
            df_hum[col_n] = df_hum[col_n].apply(lambda x: _a_float(x, np.nan))
    df_hum = df_hum.dropna(subset=['Prof_ini', 'Prof_fin']).reset_index(drop=True)

    for col_i in ['Prof_ini', 'Prof_fin', 'F%', 'LL', 'LP']:
        if col_i in df_ind.columns:
            df_ind[col_i] = df_ind[col_i].apply(lambda x: _a_float(x, np.nan))
    df_ind = df_ind.dropna(subset=['Prof_ini', 'Prof_fin']).reset_index(drop=True)

    tramos = []
    sigma_v_eff = 0.0
    gamma_w = 9.81

    for _, row in df_hum.iterrows():
        p_ini = _a_float(row['Prof_ini'], 0.0)
        p_fin = _a_float(row['Prof_fin'], p_ini + 0.5)
        if p_fin <= p_ini:
            continue
        espesor = p_fin - p_ini
        p_med = (p_ini + p_fin) / 2.0

        sucs = 'SC'
        tipo = 'Friccionante'
        coinc = df_ind[(df_ind['Prof_ini'] <= p_med) & (df_ind['Prof_fin'] >= p_med)]
        if not coinc.empty:
            fi = coinc.iloc[0]
            s_raw = str(fi.get('SUCS', 'SC')).strip().upper()
            if s_raw and s_raw != 'NAN':
                sucs = s_raw
            tm_raw = str(fi.get('Tipo_Mecanico', '')).strip()
            if tm_raw and tm_raw.lower() != 'nan':
                tipo = tm_raw.capitalize()
            else:
                if 'ROCA' in sucs or sucs.startswith('R'):
                    tipo = 'Roca'
                elif sucs.startswith(('C', 'M', 'O', 'PT')):
                    tipo = 'Cohesivo'
                else:
                    tipo = 'Friccionante'

        n_campo = _convertir_spt_raw(row.get('SPT', np.nan))
        bajo_naf = (naf is not None and p_med > naf)

        if pd.notna(n_campo):
            n_corr = 15.0 + 0.5 * (n_campo - 15.0) if (tipo == 'Friccionante' and bajo_naf and n_campo > 15.0) else n_campo
            ce = eficiencia / 60.0
            cr = 1.00 if p_med > 10.0 else (0.95 if p_med >= 6.0 else (0.85 if p_med >= 4.0 else 0.75))
            cb = 1.00 if diam_barr <= 115.0 else (1.05 if diam_barr <= 150.0 else 1.15)
            cs = 1.20 if sin_liner else 1.00
            n60 = min(50.0, n_corr * ce * cr * cb * cs)
        else:
            n60 = np.nan

        gamma_man = _a_float(row.get('Gamma_kN_m3', np.nan), np.nan)
        if pd.notna(gamma_man) and gamma_man > 0:
            gamma = gamma_man
        elif pd.notna(n60):
            gamma = round(15.0 + 0.10 * min(n60, 50.0), 2)
        else:
            gamma = gamma_def

        sigma_v_med_eff = sigma_v_eff + ((gamma - gamma_w) if bajo_naf else gamma) * (espesor / 2.0)
        sigma_v_eff += ((gamma - gamma_w) if bajo_naf else gamma) * espesor

        cn = min(1.70, math.sqrt(100.0 / max(sigma_v_med_eff, 5.0))) if pd.notna(n60) else np.nan
        n1_60 = min(50.0, n60 * cn) if pd.notna(n60) else np.nan

        phi_lab = _a_float(row.get('Angulo_deg', np.nan), np.nan)
        c_lab = _a_float(row.get('Cohesion_kPa', np.nan), np.nan)
        es_lab = _a_float(row.get('Es_kPa', np.nan), np.nan)

        if metodo_exploracion.upper() == "PCA" or (pd.notna(phi_lab) or pd.notna(c_lab)):
            phi_dis = phi_lab if pd.notna(phi_lab) else (30.0 if tipo != 'Cohesivo' else 0.0)
            c_dis = c_lab if pd.notna(c_lab) else (60.0 if tipo == 'Cohesivo' else 0.0)
            if pd.notna(c_lab) and pd.notna(phi_lab) and c_lab > 0 and phi_lab > 0:
                tipo = "Dual (Cohesivo vs. Friccionante)"
        else:
            n60_v = n60 if pd.notna(n60) else 15.0
            n1_v = n1_60 if pd.notna(n1_60) else 15.0
            if tipo == 'Cohesivo':
                c_dis = round(6.0 * n60_v, 1)
                phi_dis = 0.0
            else:
                c_dis = 0.0
                phi_dis = round(min(44.0, 27.0 + 0.30 * n1_v), 2)

        if pd.notna(es_lab) and es_lab > 0:
            es_dis = es_lab
            origen_es = "Lab. (Es_kPa)"
        else:
            ref_n = n60 if pd.notna(n60) else 15.0
            es_dis = max(5000.0, 350.0 * max(c_dis, 20.0)) if tipo == 'Cohesivo' else max(6000.0, 600.0 * ref_n)
            origen_es = "Correlación"

        tramos.append({
            'Prof_ini': round(p_ini, 2),
            'Prof_fin': round(p_fin, 2),
            'P_med': round(p_med, 2),
            'Espesor': round(espesor, 2),
            'SUCS': sucs,
            'Tipo': tipo,
            'N60': round(n60, 1) if pd.notna(n60) else np.nan,
            'N1_60': round(n1_60, 1) if pd.notna(n1_60) else np.nan,
            'Gamma': round(gamma, 2),
            'c_kPa': round(c_dis, 2),
            'phi_deg': round(phi_dis, 2),
            'Es_kPa': round(es_dis, 1),
            'Origen_Es': origen_es
        })

    df_tramos = pd.DataFrame(tramos)
    colind_str = str(df_proy.get('Zap_Colindante', 'NO')).strip().upper()

    cfg = {
        'df_min': _a_float(df_proy.get('Zap_Df_Min_m', 1.2), 1.2),
        'df_max': _a_float(df_proy.get('Zap_Df_Max_m', 2.4), 2.4),
        'df_paso': _a_float(df_proy.get('Zap_Df_Paso_m', 0.2), 0.2),
        'bc_min': _a_float(df_proy.get('Zap_Corrida_B_Min_m', 0.6), 0.6),
        'bc_max': _a_float(df_proy.get('Zap_Corrida_B_Max_m', 1.2), 1.2),
        'bc_paso': _a_float(df_proy.get('Zap_Corrida_B_Paso_m', 0.2), 0.2),
        'ba_min': _a_float(df_proy.get('Zap_Aislada_B_Min_m', 1.2), 1.2),
        'ba_max': _a_float(df_proy.get('Zap_Aislada_B_Max_m', 2.4), 2.4),
        'ba_paso': _a_float(df_proy.get('Zap_Aislada_B_Paso_m', 0.3), 0.3),
        'es_colindante': colind_str in ('SI', 'SÍ', 'TRUE', '1', 'YES'),
        'se_max_corrida_cm': _a_float(df_proy.get('Zap_Se_Max_Corrida_cm', 2.5), 2.5),
        'se_max_aislada_cm': _a_float(df_proy.get('Zap_Se_Max_Aislada_cm', 5.0), 5.0),
        'margen_se_pct': _a_float(df_proy.get('Zap_Margen_Deformacion_pct', 80.0), 80.0)
    }

    return df_tramos, naf, cfg


def _evaluar_geometria_zapata_ntc(df_tramos, naf_m, Df_m, B_m, L_m, es_corrida=False,
                                   FS=3.0, nu=0.30, fr_cdmx=0.65, es_colindante=False,
                                   criterio_suelo_ntc="Automatico", se_max_cm=5.0, factor_margen_se=0.80):
    gamma_w = 9.81
    q_sobrecarga_kpa = 0.0
    for _, t in df_tramos.iterrows():
        dz = min(float(t['Prof_fin']), Df_m) - float(t['Prof_ini'])
        if dz <= 0:
            continue
        p_med_s = float(t['Prof_ini']) + dz / 2.0
        g_ef = (float(t['Gamma']) - gamma_w) if (naf_m is not None and p_med_s > naf_m) else float(t['Gamma'])
        q_sobrecarga_kpa += max(g_ef, 4.0) * dz

    z_b_ini = Df_m
    z_b_fin = Df_m + 1.5 * B_m
    peso_z, c_ac, tanp_ac, gam_ac, es_inv_ac = 0.0, 0.0, 0.0, 0.0, 0.0
    for _, t in df_tramos.iterrows():
        ov_i = max(float(t['Prof_ini']), z_b_ini)
        ov_f = min(float(t['Prof_fin']), z_b_fin)
        dz = ov_f - ov_i
        if dz <= 0:
            continue
        c_ac += float(t['c_kPa']) * dz
        tanp_ac += math.tan(math.radians(float(t['phi_deg']))) * dz
        gam_ac += float(t['Gamma']) * dz
        es_inv_ac += dz / max(float(t['Es_kPa']), 500.0)
        peso_z += dz

    if peso_z > 0:
        c_bulbo = c_ac / peso_z
        phi_bulbo = math.degrees(math.atan(tanp_ac / peso_z))
        gam_nat = gam_ac / peso_z
        es_bulbo = peso_z / es_inv_ac
    elif not df_tramos.empty:
        ult = df_tramos.iloc[-1]
        c_bulbo, phi_bulbo, gam_nat, es_bulbo = float(ult['c_kPa']), float(ult['phi_deg']), float(ult['Gamma']), float(ult['Es_kPa'])
    else:
        c_bulbo, phi_bulbo, gam_nat, es_bulbo = 30.0, 30.0, 18.0, 15000.0

    gam_sum = max(4.5, gam_nat - gamma_w)
    if naf_m is None or naf_m >= (Df_m + B_m):
        gam_cuna = gam_nat
    elif naf_m <= Df_m:
        gam_cuna = gam_sum
    else:
        gam_cuna = gam_sum + ((naf_m - Df_m) / max(B_m, 0.1)) * (gam_nat - gam_sum)

    B_p, L_p = (L_m, B_m) if B_m > L_m else (B_m, L_m)
    m_asp = max(1.0, L_p / max(B_p, 0.15)) if not es_corrida else 6.0
    If_flex = (2.0 / math.pi) * (math.log(m_asp + math.sqrt(m_asp**2 + 1.0)) + m_asp * math.log((1.0 + math.sqrt(m_asp**2 + 1.0)) / m_asp))
    If_rig = 0.80 * If_flex
    rel_df_b = min(2.0, Df_m / max(B_p, 0.15))
    Id = max(0.50, 1.0 - 0.30 * rel_df_b)
    factor_col = 0.85 if es_colindante else 1.00

    # Ecuacion puramente cohesiva (NTC-CDMX 2023 Num. 3.5.1)
    Nc_ntc = 5.14 * (1.0 + 0.25 * (B_p / max(L_p, 0.15))) * (1.0 + 0.20 * min(Df_m / max(B_p, 0.15), 2.0))
    qu_coh_kpa = c_bulbo * Nc_ntc + q_sobrecarga_kpa

    # Ecuacion puramente friccionante (NTC-CDMX 2023 Num. 3.5.1)
    pr = math.radians(max(phi_bulbo, 1.0))
    nq_f = math.exp(math.pi * math.tan(pr)) * (math.tan(math.radians(45.0 + max(phi_bulbo, 1.0) / 2.0)) ** 2)
    ng_f = 2.0 * (nq_f + 1.0) * math.tan(pr)
    qu_fric_kpa = q_sobrecarga_kpa * (nq_f - 1.0) * (1.0 + 0.15 * min(Df_m / max(B_p, 0.15), 1.5)) + 0.5 * gam_cuna * B_p * ng_f * (1.0 - 0.30 * min(B_p / max(L_p, 0.15), 1.0)) + q_sobrecarga_kpa

    if criterio_suelo_ntc == "Puramente Cohesivo":
        qu_kpa, modelo_lbl = qu_coh_kpa, "Cohesivo (NTC 3.5.1)"
    elif criterio_suelo_ntc == "Puramente Friccionante":
        qu_kpa, modelo_lbl = qu_fric_kpa, "Friccionante (NTC 3.5.1)"
    else:
        if c_bulbo > 0 and phi_bulbo > 0:
            if qu_coh_kpa <= qu_fric_kpa:
                qu_kpa, modelo_lbl = qu_coh_kpa, "Dual -> Cohesivo (Gob.)"
            else:
                qu_kpa, modelo_lbl = qu_fric_kpa, "Dual -> Friccionante (Gob.)"
        elif c_bulbo > 0:
            qu_kpa, modelo_lbl = qu_coh_kpa, "Cohesivo (NTC 3.5.1)"
        else:
            qu_kpa, modelo_lbl = qu_fric_kpa, "Friccionante (NTC 3.5.1)"

    kpa_to_kgcm2 = 0.01019716
    r_cdmx_kpa = qu_kpa * float(fr_cdmx)
    q_adm_corte_kpa = r_cdmx_kpa / max(float(FS), 1.0)

    # Asentamiento elastico bajo q_adm_corte
    q_neta_corte = max(0.0, q_adm_corte_kpa - q_sobrecarga_kpa)
    se_corte_m = (q_neta_corte * B_p * (1.0 - nu**2) * If_rig * Id * factor_col) / max(es_bulbo, 500.0)
    se_corte_cm = se_corte_m * 100.0

    # Presion admisible limitada por deformacion objetivo (factor_margen_se * se_max_cm)
    se_obj_m = (float(factor_margen_se) * float(se_max_cm)) / 100.0
    denom_rig = max(B_p * (1.0 - nu**2) * If_rig * Id * factor_col, 1e-4)
    q_neta_def_kpa = (se_obj_m * max(es_bulbo, 500.0)) / denom_rig
    q_adm_def_kpa = q_neta_def_kpa + q_sobrecarga_kpa

    if q_adm_def_kpa < q_adm_corte_kpa:
        q_rec_kpa = q_adm_def_kpa
        gob_lbl = "Servicio / Deformación"
    else:
        q_rec_kpa = q_adm_corte_kpa
        gob_lbl = "Falla / Cortante"

    q_neta_rec = max(0.0, q_rec_kpa - q_sobrecarga_kpa)
    se_final_m = (q_neta_rec * denom_rig) / max(es_bulbo, 500.0)
    se_final_cm = se_final_m * 100.0
    ks_tm3 = ((max(es_bulbo, 500.0) / denom_rig) / 9.81)

    r_coh_kpa = qu_coh_kpa * float(fr_cdmx)
    q_corte_coh_kpa = r_coh_kpa / max(float(FS), 1.0)
    r_fricc_kpa = qu_fric_kpa * float(fr_cdmx)
    q_corte_fricc_kpa = r_fricc_kpa / max(float(FS), 1.0)
    se_obj_mm = float(factor_margen_se) * float(se_max_cm) * 10.0
    pct_se_max = (se_final_cm / max(float(se_max_cm), 0.01)) * 100.0

    return {
        'Df': round(Df_m, 2),
        'B': round(B_m, 2),
        'L': round(L_m, 2),
        'tipo_zapata': 'Corrida' if es_corrida else 'Aislada',
        'modelo_suelo_aplicado': modelo_lbl,
        'r_cdmx_kgcm2': round(r_cdmx_kpa * kpa_to_kgcm2, 2),
        'r_coh_kgcm2': round(r_coh_kpa * kpa_to_kgcm2, 2),
        'q_corte_coh_kgcm2': round(q_corte_coh_kpa * kpa_to_kgcm2, 2),
        'r_fricc_kgcm2': round(r_fricc_kpa * kpa_to_kgcm2, 2),
        'q_corte_fricc_kgcm2': round(q_corte_fricc_kpa * kpa_to_kgcm2, 2),
        'q_adm_corte_kgcm2': round(q_adm_corte_kpa * kpa_to_kgcm2, 2),
        'Se_corte_mm': round(se_corte_cm * 10.0, 1),
        'q_adm_def_kgcm2': round(q_adm_def_kpa * kpa_to_kgcm2, 2),
        'criterio_gobernante': gob_lbl,
        'q_rec_kgcm2': round(q_rec_kpa * kpa_to_kgcm2, 2),
        'q_rec_tonm2': round(q_rec_kpa / 9.81, 1),
        'Se_final_mm': round(se_final_cm * 10.0, 1),
        'Se_final_cm': round(se_final_cm, 2),
        'Se_obj_mm': round(se_obj_mm, 1),
        'pct_se_max': round(pct_se_max, 0),
        'margen_se_pct': round(float(factor_margen_se) * 100.0, 0),
        'ks_ton_m3': round(ks_tm3, 0),
        'ks_kg_cm3': round(ks_tm3 * 0.001, 2),
        'Es_kpa': round(es_bulbo, 0),
        'Es_bulbo_kpa': round(es_bulbo, 0),
        'pv_kpa': round(q_sobrecarga_kpa, 2),
        'q_sobrecarga_kpa': round(q_sobrecarga_kpa, 1),
        'gamma_cuna': round(gam_cuna, 2),
        'c_kpa': round(c_bulbo, 2),
        'phi_efec': round(phi_bulbo, 2),
        'FS': round(float(FS), 1),
        'fr_cdmx': round(float(fr_cdmx), 2),
        'metodo': 'PCA',
        'N1_60': np.nan,
        'h_bulbo': round(1.5 * B_m, 2)
    }

def generar_analisis_parametrico_zapatas(df_tramos, naf_m, df_list, b_corridas, b_aisladas,
                                         rel_LB_aislada=1.0, metodo_exploracion="SPT",
                                         FS=3.0, nu=0.30, fr_cdmx=0.65, es_colindante=False,
                                         criterio_suelo_ntc="Automatico",
                                         se_max_corrida_cm=2.5, se_max_aislada_cm=5.0,
                                         factor_margen_se=0.80):
    filas_c = []
    for df_v in df_list:
        for bc_v in b_corridas:
            filas_c.append(_evaluar_geometria_zapata_ntc(
                df_tramos, naf_m, Df_m=df_v, B_m=bc_v, L_m=bc_v * 6.0, es_corrida=True,
                FS=FS, nu=nu, fr_cdmx=fr_cdmx, es_colindante=es_colindante,
                criterio_suelo_ntc=criterio_suelo_ntc, se_max_cm=se_max_corrida_cm, factor_margen_se=factor_margen_se
            ))
    df_corr = pd.DataFrame(filas_c)

    filas_a = []
    for df_v in df_list:
        for ba_v in b_aisladas:
            filas_a.append(_evaluar_geometria_zapata_ntc(
                df_tramos, naf_m, Df_m=df_v, B_m=ba_v, L_m=ba_v * float(rel_LB_aislada), es_corrida=False,
                FS=FS, nu=nu, fr_cdmx=fr_cdmx, es_colindante=es_colindante,
                criterio_suelo_ntc=criterio_suelo_ntc, se_max_cm=se_max_aislada_cm, factor_margen_se=factor_margen_se
            ))
    df_ais = pd.DataFrame(filas_a)

    df_comp_comb = pd.concat([
        df_corr.assign(Tipo_Zapata='Corrida'),
        df_ais.assign(Tipo_Zapata='Aislada')
    ], ignore_index=True)

    return {
        'df_completo': df_comp_comb,
        'df_corridas': df_corr,
        'df_aisladas': df_ais,
        'mat_corr_qrec_kgcm2': df_corr.pivot(index='Df', columns='B', values='q_rec_kgcm2') if not df_corr.empty else pd.DataFrame(),
        'mat_ais_qrec_kgcm2': df_ais.pivot(index='Df', columns='B', values='q_rec_kgcm2') if not df_ais.empty else pd.DataFrame(),
        'mat_corr_se_final_cm': df_corr.pivot(index='Df', columns='B', values='Se_final_cm') if not df_corr.empty else pd.DataFrame(),
        'mat_ais_se_final_cm': df_ais.pivot(index='Df', columns='B', values='Se_final_cm') if not df_ais.empty else pd.DataFrame(),
        'se_max_corrida_cm': se_max_corrida_cm,
        'se_max_aislada_cm': se_max_aislada_cm,
        'factor_margen_se': factor_margen_se,
        'es_colindante': es_colindante,
        'fr_cdmx': fr_cdmx
    }


def calcular_asentamientos_cargas_estructurales_ntc(df_tramos, naf_m, df_cargas_est,
                                                    nu=0.30, es_colindante=False,
                                                    se_max_corrida_cm=2.5, se_max_aislada_cm=5.0):
    """
    Calcula los asentamientos elasticos reales bajo las cargas dadas por el
    estructurista (V_ton, H_ton, Mx_tonm, My_tonm) en cada zapata/apoyo y los
    contrasta contra los limites normativos de Estado Limite de Servicio NTC-CDMX 2023.
    """
    gamma_w = 9.81
    kpa_to_kgcm2 = 0.01019716
    resultados_filas = []

    for _, fila in df_cargas_est.iterrows():
        elem_lbl = str(fila.get('Elemento', 'Zapata'))
        tipo_z = str(fila.get('Tipo_Zapata', 'Aislada'))
        es_corr = ("CORR" in tipo_z.upper())

        Df_m = max(0.30, _a_float(fila.get('Df_m', 1.8), 1.8))
        B_m = max(0.40, _a_float(fila.get('B_m', 2.0), 2.0))
        L_m = max(B_m, _a_float(fila.get('L_m', B_m * (6.0 if es_corr else 1.0)), B_m))

        V_ton = max(0.10, _a_float(fila.get('V_ton', 120.0), 120.0))
        H_ton = _a_float(fila.get('H_ton', 0.0), 0.0)
        Mx_tonm = _a_float(fila.get('Mx_tonm', 0.0), 0.0)
        My_tonm = _a_float(fila.get('My_tonm', 0.0), 0.0)

        # Excentricidades y area efectiva (Meyerhof / NTC-CDMX)
        e_B = abs(My_tonm) / V_ton
        e_L = abs(Mx_tonm) / V_ton
        B_eff = max(0.15, B_m - 2.0 * e_B)
        L_eff = max(0.15, L_m - 2.0 * e_L)
        Area_eff = B_eff * L_eff

        q_act_tm2 = V_ton / Area_eff
        q_act_kpa = q_act_tm2 * 9.81
        q_act_kgcm2 = q_act_kpa * kpa_to_kgcm2

        # Sobrecarga efectiva hasta Df_m
        q_sc_kpa = 0.0
        for _, t in df_tramos.iterrows():
            dz = min(float(t['Prof_fin']), Df_m) - float(t['Prof_ini'])
            if dz <= 0:
                continue
            p_med_s = float(t['Prof_ini']) + dz / 2.0
            g_ef = (float(t['Gamma']) - gamma_w) if (naf_m is not None and p_med_s > naf_m) else float(t['Gamma'])
            q_sc_kpa += max(g_ef, 4.0) * dz

        # Modulo elastico secante Es promedio ponderado en bulbo (Df a Df + 1.5*B)
        z_b1, z_b2 = Df_m, Df_m + 1.5 * B_m
        es_inv_ac, peso_z = 0.0, 0.0
        for _, t in df_tramos.iterrows():
            ov_i, ov_f = max(float(t['Prof_ini']), z_b1), min(float(t['Prof_fin']), z_b2)
            dz = ov_f - ov_i
            if dz > 0:
                es_inv_ac += dz / max(float(t['Es_kPa']), 500.0)
                peso_z += dz
        if peso_z > 0:
            es_bulbo_kpa = peso_z / es_inv_ac
        elif not df_tramos.empty:
            es_bulbo_kpa = max(float(df_tramos.iloc[-1]['Es_kPa']), 500.0)
        else:
            es_bulbo_kpa = 15000.0

        B_p, L_p = (L_eff, B_eff) if B_eff > L_eff else (B_eff, L_eff)
        m_asp = max(1.0, L_p / max(B_p, 0.15)) if not es_corr else 6.0
        If_flex = (2.0 / math.pi) * (math.log(m_asp + math.sqrt(m_asp**2 + 1.0)) + m_asp * math.log((1.0 + math.sqrt(m_asp**2 + 1.0)) / m_asp))
        If_rig = 0.80 * If_flex
        rel_df_b = min(2.0, Df_m / max(B_p, 0.15))
        Id = max(0.50, 1.0 - 0.30 * rel_df_b)
        factor_col = 0.85 if es_colindante else 1.00

        q_neta_act_kpa = max(0.0, q_act_kpa - q_sc_kpa)
        denom_rig = max(B_p * (1.0 - nu**2) * If_rig * Id * factor_col, 1e-4)
        se_m = (q_neta_act_kpa * denom_rig) / max(es_bulbo_kpa, 500.0)
        se_cm = se_m * 100.0
        se_mm = se_cm * 10.0

        se_lim_cm = float(se_max_corrida_cm if es_corr else se_max_aislada_cm)
        se_lim_mm = se_lim_cm * 10.0
        pct_lim = (se_cm / max(se_lim_cm, 0.01)) * 100.0
        ks_act_tm3 = q_act_tm2 / max(se_m, 1e-5)

        resultados_filas.append({
            'Elemento': elem_lbl,
            'Tipo_Zapata': 'Corrida' if es_corr else 'Aislada',
            'Geometria_m': f"{B_m:.2f}x{L_m:.2f} (Df={Df_m:.2f})",
            'V_ton': round(V_ton, 1),
            'H_ton': round(H_ton, 1),
            'e_B_m': round(e_B, 3),
            'q_act_kgcm2': round(q_act_kgcm2, 2),
            'Es_bulbo_kgcm2': round(es_bulbo_kpa * kpa_to_kgcm2, 1),
            'Se_mm': round(se_mm, 1),
            'Se_cm': round(se_cm, 2),
            'Limite_NTC_mm': round(se_lim_mm, 1),
            'Uso_Limite_pct': round(pct_lim, 1),
            'ks_act_tm3': round(ks_act_tm3, 0),
            'Dictamen_Servicio_NTC': 'CUMPLE' if se_cm <= se_lim_cm else 'EXCEDE LÍMITE'
        })

    return pd.DataFrame(resultados_filas)
