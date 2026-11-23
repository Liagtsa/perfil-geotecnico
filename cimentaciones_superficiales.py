# ==============================================================================
# MODULO: cimentaciones_superficiales.py
# VERSION: 2.1.0-NTC2023-CDMX-COLINDANTE-SERVICIO
# REVISION NORMATIVA: NTC-CDMX 2023 (Numeral 3.5.1 y Tabla 3.6.1)
# DESCRIPCION:
#   Evaluacion de cimentaciones superficiales (Zapatas Corridas y Aisladas)
#   exclusivamente bajo NTC-CDMX 2023, considerando:
#     1. Condicion de ubicacion: Zapata Interior (FR = 0.65) vs. Zapata
#        Colindante / de Lindero (FR = 0.35, Tabla 3.6.1 NTC-CDMX 2023)
#     2. Estado Limite de Falla (r_CDMX y q_adm_corte)
#     3. Estado Limite de Servicio: Deformacion elastica (Se_corte) vs.
#        Deformacion Objetivo (80% de Se_max por defecto) -> Capacidad
#        Recomendada Gobernante (q_rec).
# ==============================================================================

import math
import re
import numpy as np
import pandas as pd


def _a_float(val, default=np.nan):
    """Convierte cualquier celda de Excel (incluyendo espacios ' ', guiones o NaN) a float seguro."""
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


def _convertir_spt_campo(valor_raw):
    """Convierte lecturas numericas y de rechazo SPT en golpes de diseno (tope 50)."""
    if valor_raw is None or pd.isna(valor_raw):
        return np.nan
    if isinstance(valor_raw, (int, float, np.number)):
        fval = float(valor_raw)
        return min(fval, 50.0) if fval > 0 else np.nan

    val_str = str(valor_raw).strip().upper()
    if val_str == '' or val_str in ('NAN', 'NONE', '-', 'PCA', 'TS'):
        return np.nan
    if any(k in val_str for k in ['ABT', 'RECHAZO', 'NQ']):
        return 50.0

    match = re.search(r'(\d+)\s*/\s*(\d+)', val_str)
    if match:
        return 50.0

    fval = _a_float(val_str, np.nan)
    return min(fval, 50.0) if (pd.notna(fval) and fval > 0) else np.nan


def _estimar_gamma_estrato(tipo, sucs, n60, w_pct=None, f_pct=None, bajo_naf=False):
    """Estima gamma (kN/m3) mediante relaciones de fases y compacidad/consistencia."""
    gamma_w = 9.81
    n_ref_roca = _a_float(n60, 50.0)
    if tipo == 'Roca' or 'ROCA' in str(sucs).upper():
        return round(21.0 + (min(n_ref_roca, 50.0) / 50.0) * 3.5, 2)

    default_f = 10.0 if tipo == 'Friccionante' else 60.0
    f = _a_float(f_pct, default_f)
    if f < 12.0:
        gs = 2.65
    elif f <= 50.0:
        gs = 2.68
    else:
        gs = 2.72 if 'CH' in str(sucs).upper() else 2.70

    gamma_fase = None
    w_val = _a_float(w_pct, np.nan)
    if pd.notna(w_val) and w_val > 0:
        w = w_val / 100.0
        sr = 1.00 if bajo_naf else min(0.85, 0.45 + 0.015 * w_val)
        e = (w * gs) / sr
        gamma_fase = gamma_w * (gs * (1.0 + w)) / (1.0 + e)

    n_ref = _a_float(n60, 15.0)
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


def _extraer_modulo_secante_fila(row):
    """
    Busca el modulo elastico secante de ensaye axial en el Excel bajo distintos
    nombres posibles de columna y lo convierte a kPa:
      - En kPa: Es_kPa, Es_sec_kPa, Modulo_Secante_kPa, E50_kPa
      - En MPa: Es_MPa, Es_sec_MPa, Modulo_Secante_MPa, E50_MPa
      - En kg/cm2: Es_kgcm2, Es_sec_kgcm2, Modulo_Secante_kgcm2, E50_kgcm2
    """
    cols_kpa = ['Es_kPa', 'Es_sec_kPa', 'Modulo_Secante_kPa', 'E50_kPa']
    cols_mpa = ['Es_MPa', 'Es_sec_MPa', 'Modulo_Secante_MPa', 'E50_MPa']
    cols_kgcm2 = ['Es_kgcm2', 'Es_sec_kgcm2', 'Modulo_Secante_kgcm2', 'E50_kgcm2']

    for c in cols_kpa:
        if c in row:
            v = _a_float(row[c], np.nan)
            if pd.notna(v) and v > 0:
                return v

    for c in cols_mpa:
        if c in row:
            v = _a_float(row[c], np.nan)
            if pd.notna(v) and v > 0:
                return v * 1000.0

    for c in cols_kgcm2:
        if c in row:
            v = _a_float(row[c], np.nan)
            if pd.notna(v) and v > 0:
                return v * 98.0665

    return np.nan


def procesar_datos_superficiales(xls_path_o_bytes, metodo_exploracion="SPT"):
    """
    Lee el archivo Excel estandar (Datos_Sondeo.xlsx) y prepara la estratigrafia
    para cimentaciones superficiales tanto en modo SPT como en modo PCA
    (Pozo a Cielo Abierto con muestras inalteradas de laboratorio).
    """
    xls = pd.ExcelFile(xls_path_o_bytes)
    df_proy_raw = pd.read_excel(xls, 'Proyecto')
    df_proy_raw['Parametro'] = df_proy_raw['Parametro'].astype(str).str.strip()
    df_proy = df_proy_raw.set_index('Parametro')['Valor'].to_dict()

    df_hum = pd.read_excel(xls, 'Humedades')
    df_ind = pd.read_excel(xls, 'PruebasIndice')

    hojas_excel = [h.strip().upper() for h in xls.sheet_names]
    if metodo_exploracion.upper() == "PCA" and any(h in hojas_excel for h in ['PCA', 'MUESTRAS_PCA']):
        nombre_hoja_pca = xls.sheet_names[hojas_excel.index('PCA' if 'PCA' in hojas_excel else 'MUESTRAS_PCA')]
        df_fuente = pd.read_excel(xls, nombre_hoja_pca)
    else:
        df_fuente = df_hum.copy()

    cols_limpiar = [
        'Prof_ini', 'Prof_fin', 'W%', 'Gamma_kN_m3', 'Angulo_deg', 'Cohesion_kPa',
        'Es_kPa', 'Es_sec_kPa', 'Modulo_Secante_kPa', 'E50_kPa',
        'Es_MPa', 'Es_sec_MPa', 'Modulo_Secante_MPa', 'E50_MPa',
        'Es_kgcm2', 'Es_sec_kgcm2', 'Modulo_Secante_kgcm2', 'E50_kgcm2'
    ]
    for col_num in cols_limpiar:
        if col_num in df_fuente.columns:
            df_fuente[col_num] = df_fuente[col_num].apply(lambda x: _a_float(x, np.nan))
    df_fuente = df_fuente.dropna(subset=['Prof_ini', 'Prof_fin']).reset_index(drop=True)

    for col_ind in ['Prof_ini', 'Prof_fin', 'F%', 'LL', 'LP']:
        if col_ind in df_ind.columns:
            df_ind[col_ind] = df_ind[col_ind].apply(lambda x: _a_float(x, np.nan))
    df_ind = df_ind.dropna(subset=['Prof_ini', 'Prof_fin']).reset_index(drop=True)

    naf_raw = _a_float(df_proy.get('NAF', np.nan), np.nan)
    naf = None if pd.isna(naf_raw) else naf_raw

    eficiencia = _a_float(df_proy.get('Eficiencia_SPT', 60.0), 60.0)
    diam_barr = _a_float(df_proy.get('Diametro_Barrena_mm', 100.0), 100.0)
    sin_liner = str(df_proy.get('Muestreador_Liner', 'CON_LINER')).strip().upper() == 'SIN_LINER'

    config_zap = {
        'df_min': _a_float(df_proy.get('Zap_Df_Min_m', 1.0), 1.0),
        'df_max': _a_float(df_proy.get('Zap_Df_Max_m', 2.2), 2.2),
        'df_paso': _a_float(df_proy.get('Zap_Df_Paso_m', 0.2), 0.2),
        'bc_min': _a_float(df_proy.get('Zap_Corrida_B_Min_m', 0.6), 0.6),
        'bc_max': _a_float(df_proy.get('Zap_Corrida_B_Max_m', 1.2), 1.2),
        'bc_paso': _a_float(df_proy.get('Zap_Corrida_B_Paso_m', 0.2), 0.2),
        'ba_min': _a_float(df_proy.get('Zap_Aislada_B_Min_m', 1.2), 1.2),
        'ba_max': _a_float(df_proy.get('Zap_Aislada_B_Max_m', 2.4), 2.4),
        'ba_paso': _a_float(df_proy.get('Zap_Aislada_B_Paso_m', 0.3), 0.3),
        'se_max_aislada_cm': _a_float(df_proy.get('Zap_Se_Max_Aislada_cm', 5.0), 5.0),
        'se_max_corrida_cm': _a_float(df_proy.get('Zap_Se_Max_Corrida_cm', 2.5), 2.5),
        'margen_se_pct': _a_float(df_proy.get('Zap_Margen_Deformacion_pct', 80.0), 80.0),
        'es_colindante': str(df_proy.get('Zap_Colindante', 'NO')).strip().upper() in ('SI', 'SÍ', 'TRUE', '1', 'COLINDANTE'),
    }

    tramos = []
    sigma_v_eff = 0.0
    gamma_w = 9.81

    for _, row in df_fuente.iterrows():
        p_ini = _a_float(row['Prof_ini'], 0.0)
        p_fin = _a_float(row['Prof_fin'], p_ini + 0.5)
        espesor = max(0.01, p_fin - p_ini)
        p_med = (p_ini + p_fin) / 2.0

        tipo = 'Friccionante'
        sucs = 'SM'
        f_pct = 20.0
        desc_estrato = ''

        coincidencias = df_ind[(df_ind['Prof_ini'] <= p_med) & (df_ind['Prof_fin'] >= p_med)]
        if not coincidencias.empty:
            fila_ind = coincidencias.iloc[0]
            sucs_raw = str(fila_ind.get('SUCS', 'SM')).strip().upper()
            if sucs_raw and sucs_raw != 'NAN':
                sucs = sucs_raw
            f_pct = _a_float(fila_ind.get('F%', 20.0), 20.0)
            desc_estrato = str(fila_ind.get('Descripción', fila_ind.get('Descripcion', ''))).strip()
            tm_raw = str(fila_ind.get('Tipo_Mecanico', '')).strip()
            if tm_raw and tm_raw.lower() != 'nan':
                tipo = tm_raw.capitalize()
            else:
                if 'ROCA' in sucs or sucs.startswith('R'):
                    tipo = 'Roca'
                elif sucs.startswith(('C', 'M', 'O', 'CL', 'CH', 'ML', 'MH')):
                    tipo = 'Cohesivo'
                else:
                    tipo = 'Friccionante'

        if 'SUCS' in row and pd.notna(row['SUCS']) and str(row['SUCS']).strip() != '':
            sucs = str(row['SUCS']).strip().upper()
        if 'Tipo_Mecanico' in row and pd.notna(row['Tipo_Mecanico']) and str(row['Tipo_Mecanico']).strip() != '':
            tipo = str(row['Tipo_Mecanico']).strip().capitalize()

        phi_lab = _a_float(row.get('Angulo_deg', np.nan), np.nan)
        coh_lab = _a_float(row.get('Cohesion_kPa', np.nan), np.nan)
        es_lab = _extraer_modulo_secante_fila(row)

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

        w_pct = _a_float(row.get('W%', np.nan), np.nan)
        bajo_naf = (naf is not None and p_med > naf)
        gamma_manual = _a_float(row.get('Gamma_kN_m3', np.nan), np.nan)

        if pd.notna(gamma_manual) and gamma_manual > 0:
            gamma = gamma_manual
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
                origen_es = "Ensaye Axial Lab. (Secante)"
            elif tipo_efec == 'Cohesivo':
                es_dis = max(300.0 * c_dis, 3000.0)
                origen_es = "Correlación Empírica (300·cu)"
            elif tipo_efec == 'Cohesivo-Friccionante':
                es_dis = max(300.0 * c_dis + 400.0 * phi_dis, 6000.0)
                origen_es = "Correlación Empírica (c-phi)"
            else:
                es_dis = max(600.0 * phi_dis, 8000.0)
                origen_es = "Correlación Empírica (phi)"
            origen_param = "Lab. PCA (Muestra Inalterada)"
        else:
            n_val_160 = n1_60 if pd.notna(n1_60) else 15.0
            n_val_60 = n60 if pd.notna(n60) else 15.0
            if tipo == 'Cohesivo':
                c_dis = round(6.0 * n_val_60, 1)
                phi_dis = 0.0
                tipo_efec = 'Cohesivo'
                if pd.notna(es_lab) and es_lab > 0:
                    es_dis = es_lab
                    origen_es = "Ensaye Axial Lab. (Secante)"
                else:
                    es_dis = round(300.0 * c_dis, 1)
                    origen_es = "Correlación Empírica (300·cu)"
            else:
                phi_dis = round(min(45.0, 27.5 + 0.92 * math.sqrt(max(n_val_160, 1.0))), 2)
                c_dis = 0.0
                tipo_efec = 'Friccionante'
                if pd.notna(es_lab) and es_lab > 0:
                    es_dis = es_lab
                    origen_es = "Ensaye Axial Lab. (Secante)"
                else:
                    es_dis = round(500.0 * n_val_160, 1)
                    origen_es = "Correlación SPT (500·N1_60)"
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
            'Origen_Es': origen_es,
            'Origen': origen_param,
            'Descripcion': desc_estrato
        })

    return pd.DataFrame(tramos), naf, config_zap


def _obtener_parametros_bulbo(df_tramos, naf_m, Df, B, es_corrida=False):
    """Ponderacion de parametros en bulbo de presiones (Df a Df + 1.5B / 2.0B)."""
    gamma_w = 9.81

    pv = 0.0
    for _, t in df_tramos.iterrows():
        p_i = _a_float(t['Prof_ini'], 0.0)
        p_f = _a_float(t['Prof_fin'], p_i)
        gam = _a_float(t.get('Gamma', t.get('Gamma_kN_m3', 18.0)), 18.0)
        if p_i >= Df:
            break
        dz = min(p_f, Df) - p_i
        if dz <= 0:
            continue
        p_med_sub = p_i + dz / 2.0
        g_eff = (gam - gamma_w) if (naf_m is not None and p_med_sub > naf_m) else gam
        pv += g_eff * dz

    prof_max_sondeo = df_tramos['Prof_fin'].apply(lambda x: _a_float(x, 0.0)).max()
    if Df > prof_max_sondeo:
        ult = df_tramos.iloc[-1]
        gam_ult = _a_float(ult.get('Gamma', ult.get('Gamma_kN_m3', 18.0)), 18.0)
        dz_ext = Df - prof_max_sondeo
        g_eff = (gam_ult - gamma_w) if (naf_m is not None and (prof_max_sondeo + dz_ext / 2.0) > naf_m) else gam_ult
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
        p_i = _a_float(t['Prof_ini'], 0.0)
        p_f = _a_float(t['Prof_fin'], p_i)
        overlap_ini = max(p_i, z_ini_b)
        overlap_fin = min(p_f, z_fin_b)
        dz = overlap_fin - overlap_ini
        if dz <= 0:
            continue

        c_val = _a_float(t.get('c_kPa', 0.0), 0.0)
        phi_val = _a_float(t.get('phi_deg', 0.0), 0.0)
        gam_val = _a_float(t.get('Gamma', t.get('Gamma_kN_m3', 18.0)), 18.0)
        es_val = _a_float(t.get('Es_kPa', 10000.0), 10000.0)

        c_acum += c_val * dz
        tan_phi_acum += math.tan(math.radians(phi_val)) * dz
        gamma_nat_acum += gam_val * dz
        es_inv_acum += (dz / max(es_val, 100.0))

        n60_val = _a_float(t.get('N60', np.nan), np.nan)
        if pd.notna(n60_val):
            n1_val = _a_float(t.get('N1_60', n60_val), n60_val)
            cn_val = _a_float(t.get('Cn', 1.0), 1.0)
            n60_acum += n60_val * dz
            n1_60_acum += n1_val * dz
            cn_acum += cn_val * dz
            conteo_spt += dz
        peso_total += dz

    if peso_total <= 0:
        ult = df_tramos.iloc[-1]
        c_prom = _a_float(ult.get('c_kPa', 0.0), 0.0)
        phi_prom = _a_float(ult.get('phi_deg', 30.0), 30.0)
        gamma_nat = _a_float(ult.get('Gamma', ult.get('Gamma_kN_m3', 18.0)), 18.0)
        es_prom = _a_float(ult.get('Es_kPa', 10000.0), 10000.0)
        n60_prom = _a_float(ult.get('N60', np.nan), np.nan)
        n1_60_prom = _a_float(ult.get('N1_60', np.nan), np.nan)
        cn_prom = _a_float(ult.get('Cn', np.nan), np.nan)
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


def evaluar_zapata_cdmx(df_tramos, naf_m, B, L, Df, es_corrida=False,
                        metodo_exploracion="SPT", FS=3.0, nu=0.30,
                        fr_cdmx=None, es_colindante=False,
                        se_max_cm=None, factor_margen_se=0.80):
    """
    Evalua cimentaciones superficiales exclusivamente bajo NTC-CDMX 2023 (Numeral 3.5.1),
    considerando la ubicacion (zapata interior FR=0.65 vs. colindante FR=0.35)
    y la revision combinada de Falla vs. Servicio (deformacion elastica).
    """
    # Determinacion normativa de FR (NTC-CDMX 2023 Tabla 3.6.1):
    # FR = 0.35 para zapatas colindantes / de lindero; FR = 0.65 para zapatas interiores
    if fr_cdmx is None:
        fr_cdmx = 0.35 if es_colindante else 0.65
    else:
        fr_cdmx = float(fr_cdmx)
        if abs(fr_cdmx - 0.35) < 1e-4:
            es_colindante = True

    ubicacion_lbl = "Colindante (FR=0.35)" if es_colindante else "Interior / Central (FR=0.65)"

    L_calc = B * 10.0 if es_corrida else max(L, B)
    rel_BL = 0.0 if es_corrida else (B / L_calc)
    rel_DfB = min(Df / B, 2.0)

    bulbo = _obtener_parametros_bulbo(df_tramos, naf_m, Df, B, es_corrida=es_corrida)
    pv = bulbo['pv']
    c = bulbo['c_kPa']
    phi = bulbo['phi_deg']
    gamma_b = bulbo['gamma_cuna']
    Es = bulbo['Es_kPa']

    # Reduccion de friccion por falla local en arenas sueltas a medias (NTC-CDMX 3.5.1.2)
    phi_efec = phi
    if phi > 0 and pd.notna(bulbo['N1_60']):
        Dr = min(1.0, math.sqrt(max(bulbo['N1_60'], 1.0) / 60.0))
        if Dr < 0.67:
            f_loc = 0.67 + Dr - 0.75 * (Dr ** 2)
            phi_efec = math.degrees(math.atan(f_loc * math.tan(math.radians(phi))))

    phi_rad = math.radians(phi_efec)

    # ==========================================================================
    # 1. ESTADO LIMITE DE FALLA — NTC-CDMX 2023 (Numeral 3.5.1)
    # ==========================================================================
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
    q_adm_corte_kpa = q_ult_neta_cdmx / FS + pv

    # ==========================================================================
    # 2. ESTADO LIMITE DE SERVICIO — REVISION POR DEFORMACION (80% DE Se_max)
    # ==========================================================================
    m_val, If_rig = _factor_influencia_rigida(B, L_calc, es_corrida=es_corrida)

    denom_elast = max(B * (1.0 - nu**2) * If_rig, 1e-6)
    ks_kpa_m = max(Es, 100.0) / denom_elast

    q_neta_corte = max(q_adm_corte_kpa - pv, 0.0)
    se_corte_m = q_neta_corte / ks_kpa_m
    se_corte_cm = se_corte_m * 100.0

    se_lim_cm = float(se_max_cm) if (se_max_cm is not None and se_max_cm > 0) else (2.5 if es_corrida else 5.0)
    margen_frac = max(0.10, min(float(factor_margen_se), 1.0))
    se_obj_cm = se_lim_cm * margen_frac
    se_obj_m = se_obj_cm / 100.0

    q_neta_def_kpa = ks_kpa_m * se_obj_m
    q_adm_def_kpa = q_neta_def_kpa + pv

    # ==========================================================================
    # 3. CAPACIDAD DE CARGA RECOMENDADA GOBERNANTE (FALLA vs. DEFORMACION)
    # ==========================================================================
    cap_falla_kpa = min(r_cdmx_kpa, q_adm_corte_kpa)

    if q_adm_def_kpa < cap_falla_kpa:
        q_rec_kpa = q_adm_def_kpa
        criterio_gob = f"Deformación ({margen_frac * 100:.0f}% Se_máx)"
    elif r_cdmx_kpa < q_adm_corte_kpa:
        q_rec_kpa = r_cdmx_kpa
        criterio_gob = f"Estado Límite Falla (FR={fr_cdmx:.2f})"
    else:
        q_rec_kpa = q_adm_corte_kpa
        criterio_gob = f"Esfuerzo Cortante (FS={FS:.1f})"

    q_neta_rec = max(q_rec_kpa - pv, 0.0)
    se_final_m = q_neta_rec / ks_kpa_m
    se_final_cm = se_final_m * 100.0
    pct_se_max = (se_final_cm / se_lim_cm) * 100.0

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
        'es_colindante': es_colindante,
        'ubicacion_zapata': ubicacion_lbl,
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
        'q_adm_corte_kpa': round(q_adm_corte_kpa, 2),
        'q_adm_corte_kgcm2': round(q_adm_corte_kpa * kpa_a_kgcm2, 2),
        'q_adm_corte_tonm2': round(q_adm_corte_kpa * kpa_a_tonm2, 2),
        'Se_corte_cm': round(se_corte_cm, 2),
        'Se_corte_mm': round(se_corte_cm * 10.0, 1),
        'Se_max_cm': round(se_lim_cm, 2),
        'Se_max_mm': round(se_lim_cm * 10.0, 1),
        'margen_se_pct': round(margen_frac * 100.0, 0),
        'Se_obj_cm': round(se_obj_cm, 2),
        'Se_obj_mm': round(se_obj_cm * 10.0, 1),
        'q_adm_def_kpa': round(q_adm_def_kpa, 2),
        'q_adm_def_kgcm2': round(q_adm_def_kpa * kpa_a_kgcm2, 2),
        'q_adm_def_tonm2': round(q_adm_def_kpa * kpa_a_tonm2, 2),
        'criterio_gobernante': criterio_gob,
        'q_rec_kpa': round(q_rec_kpa, 2),
        'q_rec_kgcm2': round(q_rec_kpa * kpa_a_kgcm2, 2),
        'q_rec_tonm2': round(q_rec_kpa * kpa_a_tonm2, 2),
        'Se_final_cm': round(se_final_cm, 2),
        'Se_final_mm': round(se_final_cm * 10.0, 1),
        'pct_se_max': round(pct_se_max, 1),
        'FS': FS,
        'nu': nu,
        'm': m_val,
        'If': If_rig,
        'ks_ton_m3': round(ks_ton_m3, 1),
        'ks_kg_cm3': round(ks_kg_cm3, 2)
    }


evaluar_zapata_dual = evaluar_zapata_cdmx


def generar_analisis_parametrico_zapatas(df_tramos, naf_m, df_list, b_corridas, b_aisladas,
                                         rel_LB_aislada=1.0, metodo_exploracion="SPT",
                                         FS=3.0, nu=0.30, fr_cdmx=None, es_colindante=False,
                                         se_max_corrida_cm=2.5, se_max_aislada_cm=5.0,
                                         factor_margen_se=0.80,
                                         fr_cdmx_override=None, fr_puebla_override=None):
    """
    Evalua todas las combinaciones parametricas de Df y B para zapatas corridas
    y aisladas bajo NTC-CDMX 2023, integrando la condicion de colindancia (FR=0.35)
    y la revision por deformacion admisible.
    """
    if fr_cdmx_override is not None:
        fr_usar = float(fr_cdmx_override)
    elif fr_cdmx is not None:
        fr_usar = float(fr_cdmx)
    else:
        fr_usar = 0.35 if es_colindante else 0.65

    colindante_flag = es_colindante or (abs(fr_usar - 0.35) < 1e-4)
    resultados = []

    for df in df_list:
        for b in b_corridas:
            res_c = evaluar_zapata_cdmx(
                df_tramos, naf_m, B=b, L=b * 10.0, Df=df, es_corrida=True,
                metodo_exploracion=metodo_exploracion, FS=FS, nu=nu,
                fr_cdmx=fr_usar, es_colindante=colindante_flag,
                se_max_cm=se_max_corrida_cm, factor_margen_se=factor_margen_se
            )
            resultados.append(res_c)

        for b in b_aisladas:
            l_ais = round(b * rel_LB_aislada, 2)
            res_a = evaluar_zapata_cdmx(
                df_tramos, naf_m, B=b, L=l_ais, Df=df, es_corrida=False,
                metodo_exploracion=metodo_exploracion, FS=FS, nu=nu,
                fr_cdmx=fr_usar, es_colindante=colindante_flag,
                se_max_cm=se_max_aislada_cm, factor_margen_se=factor_margen_se
            )
            resultados.append(res_a)

    df_res = pd.DataFrame(resultados)
    df_corr = df_res[df_res['es_corrida']].copy()
    df_ais = df_res[~df_res['es_corrida']].copy()

    return {
        'df_completo': df_res,
        'df_corridas': df_corr,
        'df_aisladas': df_ais,
        'mat_corr_qrec_kgcm2': df_corr.pivot(index='Df', columns='B', values='q_rec_kgcm2') if not df_corr.empty else pd.DataFrame(),
        'mat_corr_qcorte_kgcm2': df_corr.pivot(index='Df', columns='B', values='q_adm_corte_kgcm2') if not df_corr.empty else pd.DataFrame(),
        'mat_corr_se_final_cm': df_corr.pivot(index='Df', columns='B', values='Se_final_cm') if not df_corr.empty else pd.DataFrame(),
        'mat_corr_ks_tm3': df_corr.pivot(index='Df', columns='B', values='ks_ton_m3') if not df_corr.empty else pd.DataFrame(),
        'mat_ais_qrec_kgcm2': df_ais.pivot(index='Df', columns='B', values='q_rec_kgcm2') if not df_ais.empty else pd.DataFrame(),
        'mat_ais_qcorte_kgcm2': df_ais.pivot(index='Df', columns='B', values='q_adm_corte_kgcm2') if not df_ais.empty else pd.DataFrame(),
        'mat_ais_se_final_cm': df_ais.pivot(index='Df', columns='B', values='Se_final_cm') if not df_ais.empty else pd.DataFrame(),
        'mat_ais_ks_tm3': df_ais.pivot(index='Df', columns='B', values='ks_ton_m3') if not df_ais.empty else pd.DataFrame(),
        'metodo_exploracion': metodo_exploracion,
        'rel_LB_aislada': rel_LB_aislada,
        'FS': FS,
        'nu': nu,
        'fr_cdmx': fr_usar,
        'es_colindante': colindante_flag,
        'se_max_corrida_cm': se_max_corrida_cm,
        'se_max_aislada_cm': se_max_aislada_cm,
        'factor_margen_se': factor_margen_se,
        'naf_m': naf_m
    }