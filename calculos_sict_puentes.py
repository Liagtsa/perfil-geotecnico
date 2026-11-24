# ==============================================================================
# MODULO: calculos_sict_puentes.py
# VERSION: 1.0.0-SICT-AASHTO-PUENTES-MODULAR
# NORMATIVA: TdR SICT (Etapa V y VI), Normas SICT (N-PRY-CAR-6-01), AASHTO
# DESCRIPCION:
#   Motor analitico modular para Estudios Geotecnicos y de Cimentacion de
#   Puentes, Pasos Superiores/Inferiores (PFFCC, PSV, PIV) y Viaductos.
#   Cada calculo puede habilitarse o deshabilitarse individualmente segun las
#   condiciones reales del cruce (ej. PFFCC sin cauce fluvial -> socavacion OFF),
#   acoplando automaticamente sus efectos aguas abajo.
# ==============================================================================

import math
import re
import numpy as np
import pandas as pd


def _a_float(val, default=np.nan):
    """Conversion segura a float para celdas de Excel con espacios o texto."""
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
    """Interpreta golpes SPT y rechazos/avance triconica (tope 50 para correlacion, mas bandera de rechazo)."""
    if valor_raw is None or pd.isna(valor_raw):
        return np.nan, False
    if isinstance(valor_raw, (int, float, np.number)):
        fval = float(valor_raw)
        if fval <= 0:
            return np.nan, False
        return min(fval, 50.0), (fval >= 50.0)

    val_str = str(valor_raw).strip().upper()
    if val_str == '' or val_str in ('NAN', 'NONE', '-', 'PCA', 'TS'):
        return np.nan, False
    if any(k in val_str for k in ['ABT', 'RECHAZO', 'NQ', 'NX']):
        return 50.0, True

    match = re.search(r'(\d+)\s*/\s*(\d+)', val_str)
    if match:
        g = float(match.group(1))
        return min(g, 50.0), (g >= 50.0)

    fval = _a_float(val_str, np.nan)
    if pd.notna(fval) and fval > 0:
        return min(fval, 50.0), (fval >= 50.0)
    return np.nan, False


# ==============================================================================
# 0. PROCESAMIENTO UNIFICADO DEL ARCHIVO EXCEL PARA PUENTES SICT
# ==============================================================================
def procesar_sondeo_sict(xls_path_o_bytes):
    """
    Lee Datos_Sondeo.xlsx y extrae el perfil estratigrafico enriquecido con
    propiedades de resistencia, deformabilidad, granulometria estimada y
    consolidacion para alimentar todos los modulos SICT / AASHTO.
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

    for col_n in ['Prof_ini', 'Prof_fin', 'W%', 'Recuperacion_cm', 'RQD_cm', 'Gamma_kN_m3', 'Angulo_deg', 'Cohesion_kPa', 'Es_kPa', 'UC_Roca_MPa']:
        if col_n in df_hum.columns:
            df_hum[col_n] = df_hum[col_n].apply(lambda x: _a_float(x, np.nan))
    df_hum = df_hum.dropna(subset=['Prof_ini', 'Prof_fin']).reset_index(drop=True)

    for col_i in ['Prof_ini', 'Prof_fin', 'F%', 'LL', 'LP']:
        if col_i in df_ind.columns:
            df_ind[col_i] = df_ind[col_i].apply(lambda x: _a_float(x, np.nan))
    df_ind = df_ind.dropna(subset=['Prof_ini', 'Prof_fin']).reset_index(drop=True)

    tramos = []
    sigma_v_tot = 0.0
    sigma_v_eff = 0.0
    gamma_w = 9.81

    for _, row in df_hum.iterrows():
        p_ini = _a_float(row['Prof_ini'], 0.0)
        p_fin = _a_float(row['Prof_fin'], p_ini + 0.5)
        espesor = max(0.01, p_fin - p_ini)
        p_med = (p_ini + p_fin) / 2.0

        sucs = 'SM'
        tipo = 'Friccionante'
        f_pct = np.nan
        ll_val = np.nan
        lp_val = np.nan
        desc = ''

        coinc = df_ind[(df_ind['Prof_ini'] <= p_med) & (df_ind['Prof_fin'] >= p_med)]
        if not coinc.empty:
            fi = coinc.iloc[0]
            s_raw = str(fi.get('SUCS', 'SM')).strip().upper()
            if s_raw and s_raw != 'NAN':
                sucs = s_raw
            f_pct = _a_float(fi.get('F%', np.nan), np.nan)
            ll_val = _a_float(fi.get('LL', np.nan), np.nan)
            lp_val = _a_float(fi.get('LP', np.nan), np.nan)
            desc = str(fi.get('Descripción', fi.get('Descripcion', ''))).strip()
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

        rqd_cm = _a_float(row.get('RQD_cm', np.nan), np.nan)
        rec_cm = _a_float(row.get('Recuperacion_cm', np.nan), np.nan)
        uc_mpa = _a_float(row.get('UC_Roca_MPa', np.nan), np.nan)
        rqd_pct = np.nan
        if pd.notna(rqd_cm) and rqd_cm > 0:
            base_cm = rec_cm if (pd.notna(rec_cm) and rec_cm > 0) else (espesor * 100.0)
            rqd_pct = min(100.0, (rqd_cm / base_cm) * 100.0)
        if pd.notna(uc_mpa) or pd.notna(rqd_pct):
            tipo = 'Roca'

        spt_raw = row.get('SPT', np.nan)
        spt_str = str(spt_raw).strip().upper() if pd.notna(spt_raw) else ''
        n_campo, es_rechazo = _convertir_spt_raw(spt_raw)

        bajo_naf = (naf is not None and p_med > naf)
        if pd.notna(n_campo):
            n_corr = 15.0 + 0.5 * (n_campo - 15.0) if (tipo == 'Friccionante' and bajo_naf and n_campo > 15.0) else n_campo
            ce = eficiencia / 60.0
            cr = 1.00 if p_med > 10.0 else (0.95 if p_med >= 6.0 else (0.85 if p_med >= 4.0 else 0.75))
            cb = 1.00 if diam_barr <= 115.0 else (1.05 if diam_barr <= 150.0 else 1.15)
            cs = 1.20 if sin_liner else 1.00
            n60 = min(50.0, n_corr * ce * cr * cb * cs)
        else:
            n60 = 50.0 if tipo == 'Roca' else np.nan

        w_pct = _a_float(row.get('W%', np.nan), np.nan)
        gamma_man = _a_float(row.get('Gamma_kN_m3', np.nan), np.nan)
        if pd.notna(gamma_man) and gamma_man > 0:
            gamma = gamma_man
        else:
            n_ref = n60 if pd.notna(n60) else 15.0
            if tipo == 'Roca':
                gamma = 22.5
            elif tipo == 'Cohesivo':
                gamma = round(14.5 + 0.12 * min(n_ref, 40.0), 2)
            else:
                gamma = round(15.0 + 0.11 * min(n_ref, 50.0), 2)

        sigma_v_med_eff = sigma_v_eff + ((gamma - gamma_w) if bajo_naf else gamma) * (espesor / 2.0)
        sigma_v_tot += gamma * espesor
        sigma_v_eff += ((gamma - gamma_w) if bajo_naf else gamma) * espesor

        cn = min(2.0, math.sqrt(100.0 / max(sigma_v_med_eff, 5.0))) if pd.notna(n60) else np.nan
        n1_60 = min(50.0, n60 * cn) if pd.notna(n60) else np.nan

        phi_lab = _a_float(row.get('Angulo_deg', np.nan), np.nan)
        c_lab = _a_float(row.get('Cohesion_kPa', np.nan), np.nan)
        es_lab = _a_float(row.get('Es_kPa', np.nan), np.nan)

        if pd.notna(phi_lab) or pd.notna(c_lab):
            phi_dis = phi_lab if pd.notna(phi_lab) else 0.0
            c_dis = c_lab if pd.notna(c_lab) else 0.0
        else:
            n60_v = n60 if pd.notna(n60) else 15.0
            n1_v = n1_60 if pd.notna(n1_60) else 15.0
            if tipo == 'Roca':
                c_dis = (uc_mpa * 1000.0 * 0.15) if pd.notna(uc_mpa) else 300.0
                phi_dis = 35.0
            elif tipo == 'Cohesivo':
                c_dis = round(6.0 * n60_v, 1)
                phi_dis = 0.0
            else:
                c_dis = 0.0
                phi_dis = round(min(45.0, 27.5 + 0.92 * math.sqrt(max(n1_v, 1.0))), 2)

        if pd.notna(es_lab) and es_lab > 0:
            es_dis = es_lab
        elif tipo == 'Roca':
            es_dis = 250000.0
        elif tipo == 'Cohesivo':
            es_dis = max(3000.0, 300.0 * max(c_dis, 20.0))
        else:
            n1_v = n1_60 if pd.notna(n1_60) else 20.0
            es_dis = max(6000.0, 500.0 * n1_v)

        w_dec = (w_pct / 100.0) if (pd.notna(w_pct) and w_pct > 0) else (0.28 if tipo == 'Cohesivo' else 0.15)
        gamma_d_tm3 = round((gamma / 9.81) / (1.0 + w_dec), 2)
        if sucs.startswith('G'):
            dm_mm = 12.0
        elif sucs in ('SW', 'SP'):
            dm_mm = 1.2
        elif sucs in ('SM', 'SC', 'SP-SM', 'SP-SC'):
            dm_mm = 0.35
        else:
            dm_mm = 0.05

        gs_est = 2.70 if tipo == 'Cohesivo' else 2.66
        e0_est = round(max(0.45, w_dec * gs_est), 3)
        ll_est = ll_val if (pd.notna(ll_val) and ll_val > 15.0) else (42.0 if tipo == 'Cohesivo' else 25.0)
        cc_est = round(max(0.05, 0.009 * (ll_est - 10.0)), 3) if tipo == 'Cohesivo' else 0.02

        tramos.append({
            'Prof_ini': p_ini,
            'Prof_fin': p_fin,
            'P_med': round(p_med, 2),
            'Espesor': round(espesor, 2),
            'SUCS': sucs,
            'Tipo': tipo,
            'SPT_raw': spt_str,
            'Es_Rechazo': es_rechazo,
            'N_campo': n_campo,
            'N60': round(n60, 1) if pd.notna(n60) else np.nan,
            'N1_60': round(n1_60, 1) if pd.notna(n1_60) else np.nan,
            'W_pct': w_pct,
            'F_pct': f_pct,
            'LL': ll_val,
            'LP': lp_val,
            'RQD_pct': round(rqd_pct, 1) if pd.notna(rqd_pct) else np.nan,
            'UC_MPa': uc_mpa,
            'Gamma': round(gamma, 2),
            'Gamma_d_tm3': gamma_d_tm3,
            'Sigma_v0_eff': round(max(sigma_v_med_eff, 5.0), 2),
            'c_kPa': round(c_dis, 2),
            'phi_deg': round(phi_dis, 2),
            'Es_kPa': round(es_dis, 1),
            'dm_mm': dm_mm,
            'e0': e0_est,
            'Cc': cc_est,
            'Descripcion': desc
        })

    df_tramos = pd.DataFrame(tramos)

    pruebas_detectadas = {
        'humedad_natural': df_tramos['W_pct'].notna().any(),
        'limites_plasticidad': df_tramos['LL'].notna().any() or df_tramos['LP'].notna().any(),
        'granulometria': df_tramos['SUCS'].notna().any(),
        'porcentaje_finos': df_tramos['F_pct'].notna().any(),
        'peso_volumetrico': df_hum['Gamma_kN_m3'].notna().any() if 'Gamma_kN_m3' in df_hum.columns else False,
        'compresion_simple_o_roca': df_tramos['UC_MPa'].notna().any(),
        'triaxial_corte': (df_hum['Cohesion_kPa'].notna().any() if 'Cohesion_kPa' in df_hum.columns else False) or
                          (df_hum['Angulo_deg'].notna().any() if 'Angulo_deg' in df_hum.columns else False),
    }

    return df_tramos, naf, df_proy, pruebas_detectadas


# ==============================================================================
# 1. CUMPLIMIENTO DE EXPLORACIÓN Y SUSPENSIÓN DE SONDEO (TdR 1.5.2)
# ==============================================================================
def revisar_criterios_exploracion_sict(df_tramos, prof_desplante_m, ancho_zapata_m=0.0,
                                       en_ladera=False, distancia_horiz_talud_m=0.0,
                                       corte_subrasante_m=0.0):
    """
    Verifica automaticamente los criterios obligatorios del numeral 1.5.2 del TdR SICT:
      1. Penetracion continua >= 6.00 m en arenas/arcillas con N >= 50 golpes, o
         >= 4.00 m en masa rocosa.
      2. Que la profundidad maxima del sondeo quede por debajo del nivel de desplante
         (considerando posibles cortes de subrasante en PIV / PFFCC).
      3. En laderas/barrancas: espesor explorado >= 1.5*B debajo del desplante y
         retiro horizontal arista exterior de zapata a talud >= 2.0*B.
    """
    prof_max = float(df_tramos['Prof_fin'].max()) if not df_tramos.empty else 0.0
    desplante_real = prof_desplante_m + max(0.0, corte_subrasante_m)

    espesor_rechazo_fondo = 0.0
    espesor_roca_fondo = 0.0
    for _, r in df_tramos.iloc[::-1].iterrows():
        if r['Tipo'] == 'Roca':
            espesor_roca_fondo += r['Espesor']
        elif r['Es_Rechazo'] or (pd.notna(r['N_campo']) and r['N_campo'] >= 50.0):
            espesor_rechazo_fondo += r['Espesor']
        else:
            break

    cumple_suspension = False
    if espesor_roca_fondo >= 4.0:
        cumple_suspension = True
        criterio_susp_txt = f"CUMPLE: Se verificaron {espesor_roca_fondo:.2f} m continuos en roca (>= 4.00 m TdR 1.5.2)."
    elif espesor_rechazo_fondo >= 6.0:
        cumple_suspension = True
        criterio_susp_txt = f"CUMPLE: Se penetraron {espesor_rechazo_fondo:.2f} m continuos con N >= 50 golpes (>= 6.00 m TdR 1.5.2)."
    else:
        criterio_susp_txt = (
            f"REVISAR (Juicio del Especialista TdR 1.5.2): Prof. explorada = {prof_max:.2f} m "
            f"(tramo final N>=50: {espesor_rechazo_fondo:.2f} m | roca: {espesor_roca_fondo:.2f} m)."
        )

    espesor_bajo_desplante = prof_max - desplante_real
    min_bajo_desplante = (1.5 * ancho_zapata_m) if (ancho_zapata_m > 0) else 2.0
    cumple_prof_desplante = espesor_bajo_desplante >= min_bajo_desplante

    cumple_ladera = True
    msg_ladera = "No aplica (estructura fuera de borde de barranca/ladera)."
    if en_ladera and ancho_zapata_m > 0:
        req_dist = 2.0 * ancho_zapata_m
        req_esp = 1.5 * ancho_zapata_m
        ok_d = distancia_horiz_talud_m >= req_dist
        ok_e = espesor_bajo_desplante >= req_esp
        cumple_ladera = ok_d and ok_e
        msg_ladera = (
            f"{'CUMPLE' if cumple_ladera else 'NO CUMPLE'}: Retiro horiz. al talud = {distancia_horiz_talud_m:.2f} m "
            f"(mín. 2B = {req_dist:.2f} m) | Exploración bajo desplante = {espesor_bajo_desplante:.2f} m (mín. 1.5B = {req_esp:.2f} m)."
        )

    return {
        'aplica': True,
        'prof_max_sondeo_m': round(prof_max, 2),
        'desplante_evaluado_m': round(desplante_real, 2),
        'corte_subrasante_m': round(corte_subrasante_m, 2),
        'espesor_bajo_desplante_m': round(espesor_bajo_desplante, 2),
        'espesor_rechazo_fondo_m': round(espesor_rechazo_fondo, 2),
        'espesor_roca_fondo_m': round(espesor_roca_fondo, 2),
        'cumple_suspension': cumple_suspension,
        'criterio_suspension_msg': criterio_susp_txt,
        'cumple_prof_desplante': cumple_prof_desplante,
        'en_ladera': en_ladera,
        'cumple_ladera': cumple_ladera,
        'ladera_msg': msg_ladera
    }


# ==============================================================================
# 2. ESTUDIO DE SOCAVACIÓN GENERAL Y LOCAL (TdR 1.5.6.1) — DESHABILITABLE
# ==============================================================================
def calcular_socavacion_sict(df_tramos, aplica_socavacion=True, motivo_no_aplica="Cruce sin corriente de agua (ej. PFFCC / PSV / PIV)",
                             gasto_diseno_m3s=120.0, ancho_efectivo_m=25.0, tirante_medio_m=2.50,
                             tirante_local_m=2.80, velocidad_aprox_ms=2.40, periodo_retorno_anios=100,
                             ancho_pila_m=1.20, largo_pila_m=3.60, angulo_esviaje_deg=0.0,
                             forma_pila="Circular / Redondeada", metodo_local="Envolvente (Mayor)",
                             dm_manual_mm=None, gamma_d_manual_tm3=None, tipo_cauce_manual="Auto"):
    """
    Calcula la socavacion general (Lischtvan-Levediev) y la socavacion local en
    pilas/apoyos (Yaroslavtziev y Laursen), devolviendo el perfil de socavacion total.
    Si aplica_socavacion=False, retorna 0.00 m con sustento documental.
    """
    if not aplica_socavacion:
        return {
            'aplica': False,
            'motivo_no_aplica': motivo_no_aplica,
            'hs_equilibrio_m': 0.0,
            'soc_general_m': 0.0,
            'soc_local_laursen_m': 0.0,
            'soc_local_yaroslavtziev_m': 0.0,
            'soc_local_adoptada_m': 0.0,
            'soc_total_m': 0.0,
            'metodo_local_usado': 'No aplica'
        }

    g = 9.81
    tr_tabla = [10, 20, 50, 100, 200, 500, 1000]
    beta_tabla = [0.84, 0.88, 0.94, 0.97, 1.00, 1.03, 1.05]
    beta = float(np.interp(periodo_retorno_anios, tr_tabla, beta_tabla))

    Be = max(1.0, float(ancho_efectivo_m))
    Hm = max(0.20, float(tirante_medio_m))
    Ho = max(0.20, float(tirante_local_m))
    Qd = max(0.10, float(gasto_diseno_m3s))

    alpha = Qd / (Be * (Hm ** (5.0 / 3.0)))

    est0 = df_tramos.iloc[0] if not df_tramos.empty else None
    if tipo_cauce_manual == "Auto" and est0 is not None:
        es_cohesivo = (est0['Tipo'] == 'Cohesivo')
        es_roca = (est0['Tipo'] == 'Roca')
    else:
        es_cohesivo = ("COHES" in str(tipo_cauce_manual).upper())
        es_roca = ("ROCA" in str(tipo_cauce_manual).upper())

    dm_mm = float(dm_manual_mm) if (dm_manual_mm is not None and dm_manual_mm > 0) else (float(est0['dm_mm']) if est0 is not None else 1.0)
    gd_tm3 = float(gamma_d_manual_tm3) if (gamma_d_manual_tm3 is not None and gamma_d_manual_tm3 > 0) else (float(est0['Gamma_d_tm3']) if est0 is not None else 1.45)

    if es_roca:
        Hs = Ho
        x_exp = 0.0
        modelo_cauce = "Roca sana (no erosionable)"
    elif not es_cohesivo:
        x_exp = max(0.22, min(0.43, 0.38 - 0.055 * math.log10(max(dm_mm, 0.05))))
        denom = max(0.01, 0.68 * (dm_mm ** 0.28) * beta)
        Hs = ((alpha * (Ho ** (5.0 / 3.0))) / denom) ** (1.0 / (1.0 + x_exp))
        modelo_cauce = f"Granular (dm = {dm_mm:.2f} mm)"
    else:
        x_exp = max(0.25, min(0.55, 0.395 - 0.55 * math.log10(max(gd_tm3, 0.70))))
        denom = max(0.01, 0.60 * (gd_tm3 ** 1.18) * beta)
        Hs = ((alpha * (Ho ** (5.0 / 3.0))) / denom) ** (1.0 / (1.0 + x_exp))
        modelo_cauce = f"Cohesivo (gamma_d = {gd_tm3:.2f} t/m³)"

    soc_gen = max(0.0, Hs - Ho)

    bp = max(0.20, float(ancho_pila_m))
    lp = max(bp, float(largo_pila_m))
    theta_rad = math.radians(max(0.0, min(85.0, float(angulo_esviaje_deg))))
    V0 = max(0.10, float(velocidad_aprox_ms))
    Fr0 = V0 / math.sqrt(g * Ho)

    if "RECT" in forma_pila.upper():
        k1_laur = 1.10
        kf_yar = 12.4
    elif "AGUD" in forma_pila.upper() or "LENTIC" in forma_pila.upper():
        k1_laur = 0.90
        kf_yar = 10.0
    else:
        k1_laur = 1.00
        kf_yar = 8.5

    k2_esv = (math.cos(theta_rad) + (lp / bp) * math.sin(theta_rad)) ** 0.65

    soc_laursen = max(0.0, 2.0 * Ho * k1_laur * k2_esv * ((bp / Ho) ** 0.65) * (Fr0 ** 0.43))

    e_yar = 0.60
    fr_pila = V0 / math.sqrt(g * bp)
    kv_yar = max(0.50, min(1.0, 0.85 * (fr_pila ** 0.25)))
    kh_yar = 0.15 * math.log10(max(Ho / bp, 1.05))
    dm_m = dm_mm / 1000.0
    kf_ef = kf_yar * k2_esv
    soc_yar = max(0.0, kf_ef * kv_yar * (e_yar + kh_yar) * ((V0 ** 2) / g) - 30.0 * dm_m)

    if es_roca:
        soc_laursen = 0.0
        soc_yar = 0.0

    met_up = str(metodo_local).upper()
    if "LAURSEN" in met_up:
        soc_loc = soc_laursen
        met_lbl = "Laursen"
    elif "YAROS" in met_up:
        soc_loc = soc_yar
        met_lbl = "Yaroslavtziev"
    else:
        if soc_laursen >= soc_yar:
            soc_loc = soc_laursen
            met_lbl = "Laursen (Envolvente)"
        else:
            soc_loc = soc_yar
            met_lbl = "Yaroslavtziev (Envolvente)"

    soc_total = soc_gen + soc_loc

    return {
        'aplica': True,
        'modelo_cauce': modelo_cauce,
        'alpha': round(alpha, 3),
        'beta': round(beta, 3),
        'x_exp': round(x_exp, 3),
        'Fr0': round(Fr0, 3),
        'hs_equilibrio_m': round(Hs, 2),
        'soc_general_m': round(soc_gen, 2),
        'soc_local_laursen_m': round(soc_laursen, 2),
        'soc_local_yaroslavtziev_m': round(soc_yar, 2),
        'soc_local_adoptada_m': round(soc_loc, 2),
        'soc_total_m': round(soc_total, 2),
        'metodo_local_usado': met_lbl
    }


# ==============================================================================
# 3. CIMENTACIÓN SUPERFICIAL AASHTO — CAPACIDAD, DESLIZAMIENTO, VOLTEO (TdR 1.5.8)
# ==============================================================================
def revisar_zapata_aashto_sict(df_tramos, naf_m, B_m, L_m, Df_m,
                               V_ton, H_B_ton=0.0, H_L_ton=0.0, M_B_tonm=0.0, M_L_tonm=0.0,
                               socavacion_total_m=0.0, es_sismo=False,
                               FS_capacidad=3.0, FS_deslizamiento_min=1.50, FS_volteo_min=2.00,
                               phi_b_lrfd=0.45, nu=0.30):
    """
    Revisa los Estados Limite de Falla y Servicio de una zapata/estribo de puente
    conforme a AASHTO y el numeral 1.5.8 del TdR SICT:
      - Capacidad de carga con excentricidades (B', L') e inclinacion de carga
      - Estabilidad por deslizamiento
      - Estabilidad por volteo y ubicacion de la resultante
      - Asentamientos elasticos
      - Regla obligatoria TdR 1.5.8: si Df > 4.00 m -> proponer cimentacion profunda.
    """
    gamma_w = 9.81
    Df_ef = max(0.0, Df_m - max(0.0, socavacion_total_m))
    excede_4m_tdr = (Df_m > 4.00)

    q_sobrecarga = 0.0
    z_inicio_suelo = max(0.0, socavacion_total_m)
    for _, t in df_tramos.iterrows():
        ov_i = max(t['Prof_ini'], z_inicio_suelo)
        ov_f = min(t['Prof_fin'], Df_m)
        dz = ov_f - ov_i
        if dz <= 0:
            continue
        p_med_s = ov_i + dz / 2.0
        g_ef = (t['Gamma'] - gamma_w) if (naf_m is not None and p_med_s > naf_m) else t['Gamma']
        q_sobrecarga += max(g_ef, 4.0) * dz

    z_b_ini = Df_m
    z_b_fin = Df_m + 1.5 * B_m
    peso_z = 0.0
    c_ac, tanp_ac, gam_ac, es_inv_ac = 0.0, 0.0, 0.0, 0.0

    for _, t in df_tramos.iterrows():
        ov_i = max(t['Prof_ini'], z_b_ini)
        ov_f = min(t['Prof_fin'], z_b_fin)
        dz = ov_f - ov_i
        if dz <= 0:
            continue
        c_ac += t['c_kPa'] * dz
        tanp_ac += math.tan(math.radians(t['phi_deg'])) * dz
        gam_ac += t['Gamma'] * dz
        es_inv_ac += dz / max(t['Es_kPa'], 500.0)
        peso_z += dz

    if peso_z <= 0 and not df_tramos.empty:
        ult = df_tramos.iloc[-1]
        c_bulbo, phi_bulbo, gam_nat, es_bulbo = ult['c_kPa'], ult['phi_deg'], ult['Gamma'], ult['Es_kPa']
    elif peso_z > 0:
        c_bulbo = c_ac / peso_z
        phi_bulbo = math.degrees(math.atan(tanp_ac / peso_z))
        gam_nat = gam_ac / peso_z
        es_bulbo = peso_z / es_inv_ac
    else:
        c_bulbo, phi_bulbo, gam_nat, es_bulbo = 0.0, 30.0, 18.0, 15000.0

    gam_sum = max(4.5, gam_nat - gamma_w)
    if naf_m is None or naf_m >= (Df_m + B_m):
        gam_cuna = gam_nat
    elif naf_m <= Df_m:
        gam_cuna = gam_sum
    else:
        gam_cuna = gam_sum + ((naf_m - Df_m) / B_m) * (gam_nat - gam_sum)

    V_safe = max(float(V_ton), 0.10)
    e_B = abs(float(M_B_tonm)) / V_safe
    e_L = abs(float(M_L_tonm)) / V_safe
    e_lim_B = (B_m / 4.0) if es_sismo else (B_m / 6.0)
    e_lim_L = (L_m / 4.0) if es_sismo else (L_m / 6.0)
    cumple_excentricidad = (e_B <= e_lim_B) and (e_L <= e_lim_L)

    B_eff = max(0.15, B_m - 2.0 * e_B)
    L_eff = max(0.15, L_m - 2.0 * e_L)
    if B_eff > L_eff:
        B_p, L_p = L_eff, B_eff
    else:
        B_p, L_p = B_eff, L_eff
    Area_eff = B_eff * L_eff

    q_act_tm2 = V_safe / Area_eff
    q_act_kpa = q_act_tm2 * 9.81
    q_act_kgcm2 = q_act_kpa * 0.01019716

    phi_r = math.radians(phi_bulbo)
    if phi_bulbo <= 0.05:
        nq = 1.0
        nc = 5.14
        ng = 0.0
    else:
        nq = math.exp(math.pi * math.tan(phi_r)) * (math.tan(math.radians(45.0 + phi_bulbo / 2.0)) ** 2)
        nc = (nq - 1.0) / math.tan(phi_r)
        ng = 2.0 * (nq + 1.0) * math.tan(phi_r)

    rel_bp_lp = B_p / max(L_p, 0.15)
    sc = 1.0 + rel_bp_lp * (nq / nc) if nc > 0 else 1.0
    sq = 1.0 + rel_bp_lp * math.tan(phi_r)
    sg = max(0.60, 1.0 - 0.40 * rel_bp_lp)

    rel_df_b = min(2.0, Df_ef / max(B_p, 0.15))
    dc = 1.0 + 0.40 * rel_df_b if phi_bulbo <= 0.05 else 1.0 + 0.20 * rel_df_b * math.sqrt(nq)
    dq = 1.0 if phi_bulbo <= 0.05 else 1.0 + 0.10 * rel_df_b * math.sqrt(nq)
    dg = 1.0

    H_tot_ton = math.hypot(float(H_B_ton), float(H_L_ton))
    alpha_inc_deg = math.degrees(math.atan2(H_tot_ton, V_safe))
    if phi_bulbo > 0.5:
        ic = max(0.10, (1.0 - alpha_inc_deg / 90.0) ** 2)
        iq = ic
        ig = max(0.0, (1.0 - alpha_inc_deg / max(phi_bulbo, 1.0)) ** 2)
    else:
        ic = max(0.20, 1.0 - (2.0 * H_tot_ton * 9.81) / max(Area_eff * max(c_bulbo, 5.0) * nc, 1.0))
        iq, ig = 1.0, 0.0

    q_ult_kpa = (c_bulbo * nc * sc * dc * ic) + (q_sobrecarga * nq * sq * dq * iq) + (0.5 * gam_cuna * B_p * ng * sg * dg * ig)
    fs_cap_req = 2.0 if es_sismo else float(FS_capacidad)
    q_adm_asd_kpa = q_ult_kpa / fs_cap_req
    q_res_lrfd_kpa = q_ult_kpa * (1.0 if es_sismo else float(phi_b_lrfd))

    fs_cap_calc = q_ult_kpa / max(q_act_kpa, 0.1)
    cumple_capacidad = (fs_cap_calc >= fs_cap_req)

    delta_rad = math.radians(phi_bulbo)
    ca_kpa = 0.80 * c_bulbo
    R_desl_ton = V_safe * math.tan(delta_rad) + (ca_kpa * Area_eff) / 9.81
    fs_desl_req = 1.10 if es_sismo else float(FS_deslizamiento_min)
    fs_desl_calc = (R_desl_ton / H_tot_ton) if H_tot_ton > 0.01 else 99.9
    cumple_deslizamiento = (fs_desl_calc >= fs_desl_req)

    M_res_B = V_safe * (B_m / 2.0)
    M_res_L = V_safe * (L_m / 2.0)
    fs_volt_req = 1.50 if es_sismo else float(FS_volteo_min)
    fs_volt_B = (M_res_B / abs(float(M_B_tonm))) if abs(float(M_B_tonm)) > 0.01 else 99.9
    fs_volt_L = (M_res_L / abs(float(M_L_tonm))) if abs(float(M_L_tonm)) > 0.01 else 99.9
    fs_volt_min_calc = min(fs_volt_B, fs_volt_L)
    cumple_volteo = (fs_volt_min_calc >= fs_volt_req)

    m_asp = max(1.0, L_p / max(B_p, 0.15))
    If_flex = (2.0 / math.pi) * (math.log(m_asp + math.sqrt(m_asp**2 + 1.0)) + m_asp * math.log((1.0 + math.sqrt(m_asp**2 + 1.0)) / m_asp))
    If_rig = 0.80 * If_flex
    q_neta_act_kpa = max(0.0, q_act_kpa - q_sobrecarga)
    se_m = (q_neta_act_kpa * B_p * (1.0 - nu**2) * If_rig) / max(es_bulbo, 500.0)
    se_cm = se_m * 100.0
    cumple_asentamiento = (se_cm <= 2.54)

    kpa_kgcm2 = 0.01019716
    cumple_global = cumple_capacidad and cumple_deslizamiento and cumple_volteo and cumple_excentricidad and cumple_asentamiento and (not excede_4m_tdr)

    return {
        'aplica': True,
        'B_m': round(B_m, 2),
        'L_m': round(L_m, 2),
        'Df_m': round(Df_m, 2),
        'Df_efectivo_m': round(Df_ef, 2),
        'excede_4m_tdr': excede_4m_tdr,
        'V_ton': round(V_safe, 2),
        'H_tot_ton': round(H_tot_ton, 2),
        'e_B_m': round(e_B, 3),
        'e_L_m': round(e_L, 3),
        'e_lim_B_m': round(e_lim_B, 3),
        'cumple_excentricidad': cumple_excentricidad,
        'B_eff_m': round(B_eff, 2),
        'L_eff_m': round(L_eff, 2),
        'Area_eff_m2': round(Area_eff, 2),
        'c_bulbo_kpa': round(c_bulbo, 1),
        'phi_bulbo_deg': round(phi_bulbo, 2),
        'Es_bulbo_kpa': round(es_bulbo, 0),
        'q_act_tm2': round(q_act_tm2, 2),
        'q_act_kgcm2': round(q_act_kgcm2, 2),
        'q_ult_tm2': round(q_ult_kpa / 9.81, 2),
        'q_ult_kgcm2': round(q_ult_kpa * kpa_kgcm2, 2),
        'q_adm_asd_tm2': round(q_adm_asd_kpa / 9.81, 2),
        'q_adm_asd_kgcm2': round(q_adm_asd_kpa * kpa_kgcm2, 2),
        'q_res_lrfd_kgcm2': round(q_res_lrfd_kpa * kpa_kgcm2, 2),
        'FS_cap_calc': round(fs_cap_calc, 2),
        'FS_cap_req': round(fs_cap_req, 2),
        'cumple_capacidad': cumple_capacidad,
        'R_desl_ton': round(R_desl_ton, 2),
        'FS_desl_calc': round(min(fs_desl_calc, 99.9), 2),
        'FS_desl_req': round(fs_desl_req, 2),
        'cumple_deslizamiento': cumple_deslizamiento,
        'FS_volt_calc': round(min(fs_volt_min_calc, 99.9), 2),
        'FS_volt_req': round(fs_volt_req, 2),
        'cumple_volteo': cumple_volteo,
        'Se_cm': round(se_cm, 2),
        'Se_mm': round(se_cm * 10.0, 1),
        'cumple_asentamiento': cumple_asentamiento,
        'cumple_global': cumple_global
    }


# ==============================================================================
# 4. PILAS / PILOTES: MÉTODO DE DAVISSON Y ROBINSON (1965) — PANDEO Y EMPOTRAMIENTO (TdR 1.5.8)
# ==============================================================================
def analizar_davisson_robinson_sict(df_tramos, naf_m, D_m, L_enterrada_m,
                                    P_axial_act_ton=150.0, altura_libre_col_m=0.0,
                                    socavacion_total_m=0.0, fc_kgcm2=250.0,
                                    condicion_cabeza="Articulada - Traslación Impedida (K = 0.80)"):
    """
    Determina la longitud minima de empotramiento lateral, el punto de fijacion
    equivalente (zf) y la carga critica de pandeo elastico (Pcr) mediante el
    metodo de Davisson y Robinson (1965), exigido en el numeral 1.5.8 del TdR SICT.
    """
    D = max(0.40, float(D_m))
    L_tot = max(2.0, float(L_enterrada_m))
    z_soc = max(0.0, float(socavacion_total_m))
    L_col = max(0.0, float(altura_libre_col_m))

    L_u = L_col + z_soc
    L_emp_efectiva = max(0.50, L_tot - z_soc)

    Ec_kgcm2 = 14000.0 * math.sqrt(max(fc_kgcm2, 150.0))
    Ep_kpa = Ec_kgcm2 * 98.0665
    Ip_m4 = (math.pi * (D ** 4)) / 64.0
    EpIp_kNm2 = Ep_kpa * Ip_m4
    rg_m = D / 4.0

    z_sup = z_soc
    z_inf = z_soc + 8.0 * D
    dz_tot, dz_coh, cu_ac, n60_ac = 0.0, 0.0, 0.0, 0.0

    for _, t in df_tramos.iterrows():
        ov_i = max(t['Prof_ini'], z_sup)
        ov_f = min(t['Prof_fin'], z_inf)
        dz = ov_f - ov_i
        if dz <= 0:
            continue
        if t['Tipo'] in ('Cohesivo', 'Roca'):
            dz_coh += dz
            cu_ac += max(t['c_kPa'], 25.0) * dz
        else:
            if pd.notna(t['N60']):
                n_est = float(t['N60'])
            else:
                phi_t = float(t.get('phi_deg', 30.0))
                n_est = max(6.0, min(50.0, ((max(phi_t, 28.0) - 27.5) / 0.92) ** 2))
            n60_ac += n_est * dz
        dz_tot += dz

    es_modelo_constante = (dz_coh >= 0.5 * dz_tot) if dz_tot > 0 else False
    sumergido = (naf_m is not None and naf_m <= (z_sup + 2.0 * D))

    if es_modelo_constante:
        cu_med = (cu_ac / max(dz_coh, 0.01)) if dz_coh > 0 else 50.0
        Kh_kpa = 67.0 * cu_med
        R_m = (EpIp_kNm2 / max(Kh_kpa, 100.0)) ** 0.25
        zf_m = 1.40 * R_m
        L_emp_min_m = 4.0 * R_m
        modelo_dr = f"Módulo Constante Cohesivo (Kh = {Kh_kpa:.0f} kPa, R = {R_m:.2f} m)"
        param_rigidez_m = R_m
    else:
        dz_fricc = max(dz_tot - dz_coh, 0.01)
        n60_med = (n60_ac / dz_fricc) if dz_tot > 0 else 20.0
        nh_seco = 250.0 * max(n60_med, 4.0)
        nh_kNm3 = (0.60 * nh_seco) if sumergido else nh_seco
        T_m = (EpIp_kNm2 / max(nh_kNm3, 200.0)) ** 0.20
        zf_m = 1.80 * T_m
        L_emp_min_m = 4.0 * T_m
        modelo_dr = f"Módulo Lineal Friccionante (nh = {nh_kNm3:.0f} kN/m³, T = {T_m:.2f} m)"
        param_rigidez_m = T_m

    if "2.0" in condicion_cabeza or "LIBRE" in condicion_cabeza.upper():
        K_eff = 2.00
    elif "1.2" in condicion_cabeza or "DESPLAZABLE" in condicion_cabeza.upper():
        K_eff = 1.20
    elif "0.7" in condicion_cabeza or "EMPOTRADA" in condicion_cabeza.upper():
        K_eff = 0.70
    elif "0.8" in condicion_cabeza:
        K_eff = 0.80
    else:
        K_eff = 1.00

    L_cantilever_eq = L_u + zf_m
    L_eq_pandeo = K_eff * L_cantilever_eq
    esbeltez_kl_r = L_eq_pandeo / rg_m

    P_cr_kN = (math.pi ** 2) * EpIp_kNm2 / max(L_eq_pandeo ** 2, 0.25)
    P_cr_ton = P_cr_kN / 9.81

    Area_pila_cm2 = (math.pi * ((D * 100.0) ** 2)) / 4.0
    P_plast_concreto_ton = (0.85 * fc_kgcm2 * Area_pila_cm2) / 1000.0

    P_act = max(float(P_axial_act_ton), 1.0)
    FS_pandeo = P_cr_ton / P_act
    cumple_empotramiento = (L_emp_efectiva >= L_emp_min_m)
    cumple_pandeo = (FS_pandeo >= 3.0) and cumple_empotramiento

    z_estrato_res = None
    for _, t in df_tramos.iterrows():
        if t['Prof_fin'] <= z_soc:
            continue
        if t['Tipo'] == 'Roca' or (pd.notna(t['N60']) and t['N60'] >= 30.0) or (t['c_kPa'] >= 100.0):
            z_estrato_res = float(t['Prof_ini'])
            break

    return {
        'aplica': True,
        'D_m': round(D, 2),
        'L_enterrada_m': round(L_tot, 2),
        'L_libre_total_Lu_m': round(L_u, 2),
        'L_emp_efectiva_m': round(L_emp_efectiva, 2),
        'EpIp_MNm2': round(EpIp_kNm2 / 1000.0, 2),
        'modelo_suelo_dr': modelo_dr,
        'param_rigidez_ToR_m': round(param_rigidez_m, 2),
        'zf_fijacion_m': round(zf_m, 2),
        'L_emp_min_requerida_m': round(L_emp_min_m, 2),
        'z_estrato_resistente_m': round(z_estrato_res, 2) if z_estrato_res is not None else None,
        'K_efectivo': K_eff,
        'L_eq_pandeo_m': round(L_eq_pandeo, 2),
        'esbeltez_kL_r': round(esbeltez_kl_r, 1),
        'P_cr_euler_ton': round(P_cr_ton, 1),
        'P_plast_concreto_ton': round(P_plast_concreto_ton, 1),
        'P_act_ton': round(P_act, 1),
        'FS_pandeo': round(FS_pandeo, 2),
        'cumple_empotramiento': cumple_empotramiento,
        'cumple_pandeo': cumple_pandeo
    }


# ==============================================================================
# 5. EMPUJE DE TIERRAS EN ESTRIBOS Y MUROS (Rankine + Mononobe-Okabe, SICT)
# ==============================================================================
def calcular_empujes_muros_sict(altura_muro_m=6.0, gamma_relleno_kNm3=19.0,
                                phi_relleno_deg=32.0, c_relleno_kpa=0.0,
                                beta_talud_relleno_deg=0.0, h_eq_sobrecarga_m=0.60,
                                kh_sismico=0.12, kv_sismico=0.0):
    """
    Calcula coeficientes y diagramas de empuje de tierras estatico (activo Ka,
    en reposo K0, pasivo Kp) y dinamico sismico (Mononobe-Okabe Kae) para el
    diseno de estribos, aleros y muros de contencion (Normas SICT N-PRY-CAR-6-01).
    """
    H = max(1.0, float(altura_muro_m))
    gam = max(14.0, float(gamma_relleno_kNm3))
    phi = max(15.0, min(45.0, float(phi_relleno_deg)))
    c = max(0.0, float(c_relleno_kpa))
    beta = max(0.0, min(phi - 1.0, float(beta_talud_relleno_deg)))

    phi_r = math.radians(phi)
    beta_r = math.radians(beta)

    K0 = 1.0 - math.sin(phi_r)
    cos_b = math.cos(beta_r)
    raiz_r = math.sqrt(max(0.0, (cos_b ** 2) - (math.cos(phi_r) ** 2)))
    Ka = cos_b * ((cos_b - raiz_r) / max(cos_b + raiz_r, 1e-5))
    Kp = (1.0 + math.sin(phi_r)) / max(1.0 - math.sin(phi_r), 1e-5)

    kh = max(0.0, float(kh_sismico))
    kv = float(kv_sismico)
    psi_r = math.atan2(kh, max(1.0 - kv, 0.1))
    psi_deg = math.degrees(psi_r)

    if (phi_r - psi_r - beta_r) <= 0.01:
        Kae = Ka * 1.50
    else:
        num_mo = math.cos(phi_r - psi_r) ** 2
        raiz_mo = math.sqrt(
            (math.sin(phi_r) * math.sin(phi_r - psi_r - beta_r)) /
            max(math.cos(psi_r) * math.cos(beta_r), 1e-5)
        )
        den_mo = math.cos(psi_r) * ((1.0 + raiz_mo) ** 2)
        Kae = (1.0 - kv) * (num_mo / max(den_mo, 1e-5))

    delta_Kae = max(0.0, Kae - Ka)

    q_sc_kpa = gam * max(0.0, float(h_eq_sobrecarga_m))
    Ea_relleno_kNm = max(0.0, 0.5 * gam * (H ** 2) * Ka - 2.0 * c * H * math.sqrt(Ka))
    Ea_sc_kNm = q_sc_kpa * H * Ka
    E0_reposo_kNm = 0.5 * gam * (H ** 2) * K0 + q_sc_kpa * H * K0
    dE_sismo_kNm = 0.5 * gam * (H ** 2) * delta_Kae

    Ea_estatico_tot_tm = (Ea_relleno_kNm + Ea_sc_kNm) / 9.81
    Ea_sismico_tot_tm = (Ea_relleno_kNm + Ea_sc_kNm + dE_sismo_kNm) / 9.81
    E0_reposo_tm = E0_reposo_kNm / 9.81

    M_volc_estatico_tmm = ((Ea_relleno_kNm * (H / 3.0)) + (Ea_sc_kNm * (H / 2.0))) / 9.81
    M_volc_sismico_tmm = M_volc_estatico_tmm + ((dE_sismo_kNm * (0.60 * H)) / 9.81)

    return {
        'aplica': True,
        'H_muro_m': round(H, 2),
        'gamma_relleno_kNm3': round(gam, 2),
        'phi_relleno_deg': round(phi, 1),
        'Ka': round(Ka, 3),
        'K0': round(K0, 3),
        'Kp': round(Kp, 2),
        'psi_sismico_deg': round(psi_deg, 2),
        'Kae_mononobe': round(Kae, 3),
        'delta_Kae': round(delta_Kae, 3),
        'q_sobrecarga_kpa': round(q_sc_kpa, 2),
        'Ea_relleno_tm': round(Ea_relleno_kNm / 9.81, 2),
        'Ea_sobrecarga_tm': round(Ea_sc_kNm / 9.81, 2),
        'dE_sismo_tm': round(dE_sismo_kNm / 9.81, 2),
        'Ea_total_estatico_tm': round(Ea_estatico_tot_tm, 2),
        'Ea_total_sismico_tm': round(Ea_sismico_tot_tm, 2),
        'E0_reposo_tm': round(E0_reposo_tm, 2),
        'M_volc_estatico_tmm': round(M_volc_estatico_tmm, 2),
        'M_volc_sismico_tmm': round(M_volc_sismico_tmm, 2)
    }


# ==============================================================================
# 6. TERRAPLENES DE ACCESO Y TALUDES DE EXCAVACIÓN (TdR 1.5.7 y 1.4.13)
# ==============================================================================
def analizar_terraplen_y_excavacion_sict(df_tramos, naf_m,
                                         altura_terraplen_m=5.0, corona_terraplen_m=12.0,
                                         talud_terraplen_H_V=1.5, gamma_terraplen_kNm3=19.5,
                                         cv_consolidacion_m2_anio=2.5,
                                         prof_excavacion_m=2.5, talud_exc_propuesto_H_V=1.0):
    """
    Revisa:
      A. Terraplen de acceso: estabilidad por capacidad en la base, asentamientos
         elasticos a corto plazo (etapa constructiva) y asentamientos por
         consolidacion primaria a largo plazo (servicio), mas propuestas de mitigacion.
      B. Excavaciones y taludes de corte: talud recomendable (H:V), factor de
         seguridad de talud y diseno especial si H_exc > 4.00 m (TdR 1.5.7).
    """
    H_t = max(0.5, float(altura_terraplen_m))
    B_cor = max(4.0, float(corona_terraplen_m))
    m_t = max(0.5, float(talud_terraplen_H_V))
    gam_t = max(15.0, float(gamma_terraplen_kNm3))

    q_terr_kpa = gam_t * H_t
    B_base_terr = B_cor + 2.0 * m_t * H_t
    B_med_terr = 0.5 * (B_cor + B_base_terr)

    if not df_tramos.empty:
        e_sup = df_tramos.iloc[0]
        if e_sup['Tipo'] == 'Cohesivo' or e_sup['phi_deg'] <= 1.0:
            q_ult_base = max(e_sup['c_kPa'], 25.0) * 5.14
        else:
            pr = math.radians(e_sup['phi_deg'])
            nq_b = math.exp(math.pi * math.tan(pr)) * (math.tan(math.radians(45.0 + e_sup['phi_deg'] / 2.0)) ** 2)
            ng_b = 2.0 * (nq_b + 1.0) * math.tan(pr)
            q_ult_base = 0.5 * e_sup['Gamma'] * min(B_base_terr, 10.0) * ng_b + e_sup['c_kPa'] * ((nq_b - 1.0) / math.tan(pr))
    else:
        q_ult_base = 250.0

    FS_base_terr = q_ult_base / max(q_terr_kpa, 1.0)

    asent_elastico_m = 0.0
    asent_consolid_m = 0.0
    espesor_cohesivo_acum = 0.0

    for _, t in df_tramos.iterrows():
        if t['Tipo'] == 'Roca':
            continue
        z_med = max(0.2, float(t['P_med']))
        dz = float(t['Espesor'])
        alpha_ost = 2.0 * math.atan((B_med_terr / 2.0) / z_med)
        Iz = (alpha_ost + math.sin(alpha_ost)) / math.pi
        delta_sigma_kpa = q_terr_kpa * Iz

        asent_elastico_m += (delta_sigma_kpa * dz) / max(t['Es_kPa'], 1000.0)

        if t['Tipo'] == 'Cohesivo':
            sigma_v0 = max(float(t['Sigma_v0_eff']), 10.0)
            cc = float(t['Cc'])
            e0 = float(t['e0'])
            dh_c = (cc / (1.0 + e0)) * dz * math.log10((sigma_v0 + delta_sigma_kpa) / sigma_v0)
            asent_consolid_m += max(0.0, dh_c)
            espesor_cohesivo_acum += dz

    se_corto_cm = asent_elastico_m * 100.0
    sc_largo_cm = asent_consolid_m * 100.0
    s_total_terr_cm = se_corto_cm + sc_largo_cm

    if espesor_cohesivo_acum > 0.1:
        h_dr = espesor_cohesivo_acum / 2.0
        t90_anios = (0.848 * (h_dr ** 2)) / max(float(cv_consolidacion_m2_anio), 0.1)
        t90_meses = t90_anios * 12.0
    else:
        t90_meses = 0.0

    if s_total_terr_cm > 10.0:
        mitigacion = "Instalar drenes verticales prefabricados + precarga temporal, mejoramiento basal con pedraplén y losa de transición reforzada."
    elif s_total_terr_cm > 5.0:
        mitigacion = "Colocar capa de desplante de pedraplén / geotextil de refuerzo, construcción por etapas y losa de acceso articulada."
    else:
        mitigacion = "Asentamientos admisibles; colocar plantilla de desplante compactada al 95% AASHTO y losa de acceso estándar."

    H_exc = max(0.5, float(prof_excavacion_m))
    m_exc = max(0.1, float(talud_exc_propuesto_H_V))
    beta_exc_rad = math.atan(1.0 / m_exc)
    beta_exc_deg = math.degrees(beta_exc_rad)

    dz_e, c_e_ac, tp_e_ac, g_e_ac = 0.0, 0.0, 0.0, 0.0
    for _, t in df_tramos.iterrows():
        ov_f = min(t['Prof_fin'], H_exc)
        dz = ov_f - t['Prof_ini']
        if dz <= 0:
            continue
        c_e_ac += t['c_kPa'] * dz
        tp_e_ac += math.tan(math.radians(t['phi_deg'])) * dz
        g_e_ac += t['Gamma'] * dz
        dz_e += dz

    if dz_e > 0:
        c_exc = c_e_ac / dz_e
        phi_exc_rad = math.atan(tp_e_ac / dz_e)
        gam_exc = g_e_ac / dz_e
    else:
        c_exc, phi_exc_rad, gam_exc = 20.0, math.radians(28.0), 18.0

    theta_crit = 0.5 * (beta_exc_rad + phi_exc_rad)
    peso_cuna = 0.5 * gam_exc * (H_exc ** 2) * (max(0.05, (1.0 / math.tan(theta_crit)) - (1.0 / math.tan(beta_exc_rad))))
    long_falla = H_exc / max(math.sin(theta_crit), 0.1)
    f_res_talud = c_exc * long_falla + max(0.0, peso_cuna * math.cos(theta_crit)) * math.tan(phi_exc_rad)
    f_act_talud = max(0.1, peso_cuna * math.sin(theta_crit))
    FS_talud_exc = min(9.99, f_res_talud / f_act_talud)

    requiere_diseno_especial_4m = (H_exc > 4.00)
    if requiere_diseno_especial_4m:
        rec_exc = (
            f"Excavación profunda H = {H_exc:.2f} m (> 4.00 m TdR 1.5.7): Ejecutar corte escalonado con bermas intermedias "
            f"cada 3.50 m o sistema de retención temporal (tablaestaca / concreto lanzado con anclas pasivas) y bombeo de achique."
        )
    else:
        rec_exc = f"Excavación somera H = {H_exc:.2f} m: Talud temporal recomendado {max(m_exc, 0.75):.2f}:1 (H:V) libre de sobrecargas en el hombro."

    return {
        'aplica': True,
        'H_terraplen_m': round(H_t, 2),
        'q_terraplen_kpa': round(q_terr_kpa, 1),
        'FS_base_terraplen': round(FS_base_terr, 2),
        'cumple_base_terraplen': (FS_base_terr >= 1.50),
        'asent_corto_plazo_cm': round(se_corto_cm, 2),
        'asent_largo_plazo_cm': round(sc_largo_cm, 2),
        'asent_total_terraplen_cm': round(s_total_terr_cm, 2),
        't90_consolidacion_meses': round(t90_meses, 1),
        'mitigacion_terraplen': mitigacion,
        'H_excavacion_m': round(H_exc, 2),
        'talud_exc_H_V': f"{m_exc:.2f} : 1",
        'angulo_talud_deg': round(beta_exc_deg, 1),
        'FS_talud_exc': round(FS_talud_exc, 2),
        'cumple_talud_exc': (FS_talud_exc >= 1.30),
        'requiere_diseno_especial_4m': requiere_diseno_especial_4m,
        'recomendacion_excavacion': rec_exc
    }


# ==============================================================================
# 7. ORQUESTADOR MODULAR INTEGRAL DE CUMPLIMIENTO TdR SICT
# ==============================================================================
def ejecutar_estudio_sict_modular(df_tramos, naf_m, config_modulos, params):
    """
    Ejecuta selectivamente los calculos habilitados en `config_modulos` y
    encadena automaticamente los resultados entre si (por ejemplo, si
    aplica_socavacion=False en un PFFCC, soc_total_m = 0.0 se propaga a
    zapatas AASHTO y a Davisson-Robinson).
    """
    resultados = {
        'tipo_cruce': params.get('tipo_cruce', 'PFFCC (Paso Superior de Ferrocarril)'),
        'config_modulos': config_modulos,
        'naf_m': naf_m
    }

    if config_modulos.get('aplica_socavacion', False):
        res_soc = calcular_socavacion_sict(
            df_tramos,
            aplica_socavacion=True,
            gasto_diseno_m3s=params.get('Qd_m3s', 120.0),
            ancho_efectivo_m=params.get('Be_m', 25.0),
            tirante_medio_m=params.get('Hm_m', 2.5),
            tirante_local_m=params.get('Ho_m', 2.8),
            velocidad_aprox_ms=params.get('V0_ms', 2.4),
            periodo_retorno_anios=params.get('Tr_anios', 100),
            ancho_pila_m=params.get('bp_soc_m', 1.2),
            largo_pila_m=params.get('lp_soc_m', 3.6),
            angulo_esviaje_deg=params.get('esviaje_deg', 0.0),
            forma_pila=params.get('forma_pila', 'Circular / Redondeada'),
            metodo_local=params.get('metodo_soc_local', 'Envolvente (Mayor)'),
            dm_manual_mm=params.get('dm_manual_mm', None),
            gamma_d_manual_tm3=params.get('gd_manual_tm3', None),
            tipo_cauce_manual=params.get('tipo_cauce_manual', 'Auto')
        )
    else:
        res_soc = calcular_socavacion_sict(
            df_tramos,
            aplica_socavacion=False,
            motivo_no_aplica=f"No aplica socavación hidráulica por tratarse de: {params.get('tipo_cruce', 'Paso sin cauce fluvial')}."
        )
    resultados['socavacion'] = res_soc
    soc_tot_m = res_soc['soc_total_m']

    if config_modulos.get('aplica_exploracion', True):
        resultados['exploracion'] = revisar_criterios_exploracion_sict(
            df_tramos,
            prof_desplante_m=params.get('Df_zap_m', 2.0),
            ancho_zapata_m=params.get('B_zap_m', 3.0),
            en_ladera=params.get('en_ladera', False),
            distancia_horiz_talud_m=params.get('dist_talud_m', 8.0),
            corte_subrasante_m=params.get('corte_subrasante_m', 0.0)
        )
    else:
        resultados['exploracion'] = {'aplica': False}

    if config_modulos.get('aplica_superficial_aashto', True):
        resultados['superficial_aashto'] = revisar_zapata_aashto_sict(
            df_tramos, naf_m,
            B_m=params.get('B_zap_m', 3.0),
            L_m=params.get('L_zap_m', 8.0),
            Df_m=params.get('Df_zap_m', 2.0),
            V_ton=params.get('V_zap_ton', 180.0),
            H_B_ton=params.get('HB_zap_ton', 18.0),
            H_L_ton=params.get('HL_zap_ton', 5.0),
            M_B_tonm=params.get('MB_zap_tonm', 45.0),
            M_L_tonm=params.get('ML_zap_tonm', 15.0),
            socavacion_total_m=soc_tot_m,
            es_sismo=params.get('es_sismo_zap', False),
            FS_capacidad=params.get('FS_cap_zap', 3.0)
        )
    else:
        resultados['superficial_aashto'] = {'aplica': False}

    if config_modulos.get('aplica_pandeo_davisson', True):
        resultados['davisson_pandeo'] = analizar_davisson_robinson_sict(
            df_tramos, naf_m,
            D_m=params.get('D_pila_m', 1.20),
            L_enterrada_m=params.get('L_pila_m', 18.0),
            P_axial_act_ton=params.get('P_act_pila_ton', 220.0),
            altura_libre_col_m=params.get('H_libre_col_m', 0.0),
            socavacion_total_m=soc_tot_m,
            fc_kgcm2=params.get('fc_pila_kgcm2', 250.0),
            condicion_cabeza=params.get('condicion_cabeza_pila', 'Articulada - Traslación Impedida (K = 0.80)')
        )
    else:
        resultados['davisson_pandeo'] = {'aplica': False}

    if config_modulos.get('aplica_empujes_muros', True):
        resultados['empujes_muros'] = calcular_empujes_muros_sict(
            altura_muro_m=params.get('H_muro_m', 6.0),
            gamma_relleno_kNm3=params.get('gamma_relleno_kNm3', 19.0),
            phi_relleno_deg=params.get('phi_relleno_deg', 32.0),
            c_relleno_kpa=params.get('c_relleno_kpa', 0.0),
            beta_talud_relleno_deg=params.get('beta_relleno_deg', 0.0),
            h_eq_sobrecarga_m=params.get('heq_sc_m', 0.60),
            kh_sismico=params.get('kh_sismo_muro', 0.12),
            kv_sismico=params.get('kv_sismo_muro', 0.0)
        )
    else:
        resultados['empujes_muros'] = {'aplica': False}

    if config_modulos.get('aplica_terraplenes_excavacion', True):
        resultados['terraplen_excavacion'] = analizar_terraplen_y_excavacion_sict(
            df_tramos, naf_m,
            altura_terraplen_m=params.get('H_terr_m', 6.5),
            corona_terraplen_m=params.get('B_corona_m', 12.0),
            talud_terraplen_H_V=params.get('talud_terr_HV', 1.5),
            gamma_terraplen_kNm3=params.get('gamma_terr_kNm3', 19.5),
            cv_consolidacion_m2_anio=params.get('cv_m2_anio', 2.5),
            prof_excavacion_m=params.get('H_exc_m', params.get('Df_zap_m', 2.0)),
            talud_exc_propuesto_H_V=params.get('talud_exc_HV', 0.75)
        )
    else:
        resultados['terraplen_excavacion'] = {'aplica': False}

    return resultados