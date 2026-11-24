# ==============================================================================
# MODULO: calculos_sict_puentes.py
# VERSION: 2.0.0-SICT-AASHTO-2ETAPAS-MODULAR
# NORMATIVA:
#   - Terminos de Referencia SICT (Etapas V y VI) y N-PRY-CAR-8-01-004/19
#   - AASHTO LRFD Bridge Design Specifications (O'Neill & Reese 1999, Sec. 10)
#   - Poulos (1994) para asentamiento de grupo de pilotes (pilote equivalente)
#   - Broms (1964) para capacidad lateral y momento maximo
#   - Davisson & Robinson (1965) para longitud de empotramiento y pandeo
#   - Rankine + Mononobe-Okabe para empujes metro a metro en estribos/muros
# DESCRIPCION:
#   Flujo geotecnico-estructural en 2 Etapas secuenciales con interruptores
#   modulares independientes:
#     * ETAPA 1 (Pre-Estructural): Propuesta inicial de capacidad de carga para
#       pilas individuales (compresion y tension) y zapatas preliminares.
#     * ETAPA 2 (Post-Estructural): Revision definitiva multi-apoyo (grupos de
#       pilotes a compresion, tension y cortante, asentamientos Poulos, Broms,
#       Davisson-Robinson, o zapatas definitivas AASHTO).
#     * ETAPA 3 (Complementarios): Socavacion opcional, estabilidad de taludes
#       de excavacion, empujes metro a metro en muros y terraplenes de acceso.
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
    """Interpreta golpes SPT y rechazos/avance triconica (tope 50, mas bandera de rechazo)."""
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
# 0. PROCESAMIENTO UNIFICADO DEL SONDEO (CON DEPURACIÓN DE TRAMOS INVERTIDOS)
# ==============================================================================
def procesar_sondeo_sict(xls_path_o_bytes):
    """
    Lee Datos_Sondeo.xlsx, depura posibles cotas invertidas y extrae el perfil
    estratigrafico enriquecido para las Etapas 1, 2 y 3 del estudio SICT/AASHTO.
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

    for col_n in ['Prof_ini', 'Prof_fin', 'W%', 'Recuperacion_cm', 'RQD_cm', 'Gamma_kN_m3',
                  'Angulo_deg', 'Cohesion_kPa', 'Es_kPa', 'UC_Roca_MPa']:
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
        if p_fin <= p_ini:
            continue
        espesor = p_fin - p_ini
        p_med = (p_ini + p_fin) / 2.0

        sucs = 'SM'
        tipo = 'Friccionante'
        f_pct, ll_val, lp_val = np.nan, np.nan, np.nan
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

        cn = min(1.70, math.sqrt(100.0 / max(sigma_v_med_eff, 5.0))) if pd.notna(n60) else np.nan
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
                phi_dis = round(min(44.0, 27.0 + 0.30 * n1_v), 2)

        if pd.notna(es_lab) and es_lab > 0:
            es_dis = es_lab
        elif tipo == 'Roca':
            es_dis = 250000.0
        elif tipo == 'Cohesivo':
            es_dis = max(3500.0, 300.0 * max(c_dis, 20.0))
        else:
            n60_v = n60 if pd.notna(n60) else 20.0
            es_dis = max(6000.0, (4.8 + 1.25 * n60_v) * 1000.0 * 0.35)

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
        ll_est = ll_val if (pd.notna(ll_val) and ll_val > 15.0) else (40.0 if tipo == 'Cohesivo' else 24.0)
        cc_est = round(max(0.05, 0.009 * (ll_est - 10.0)), 3) if tipo == 'Cohesivo' else 0.02

        tramos.append({
            'Prof_ini': round(p_ini, 2),
            'Prof_fin': round(p_fin, 2),
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
# 1. CUMPLIMIENTO DE EXPLORACIÓN Y SOCAVACIÓN OPCIONAL (TdR 1.5.2 y 1.5.6)
# ==============================================================================
def revisar_criterios_exploracion_sict(df_tramos, prof_desplante_m, ancho_zapata_m=0.0,
                                       en_ladera=False, distancia_horiz_talud_m=0.0,
                                       corte_subrasante_m=0.0):
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
        criterio_susp_txt = f"CUMPLE: {espesor_roca_fondo:.2f} m continuos en roca (>= 4.00 m TdR 1.5.2)."
    elif espesor_rechazo_fondo >= 6.0:
        cumple_suspension = True
        criterio_susp_txt = f"CUMPLE: {espesor_rechazo_fondo:.2f} m continuos con N >= 50 (>= 6.00 m TdR 1.5.2)."
    else:
        criterio_susp_txt = (
            f"A JUICIO DEL ESPECIALISTA (TdR 1.5.2): Prof. explorada = {prof_max:.2f} m "
            f"(N>=50 al fondo: {espesor_rechazo_fondo:.2f} m | roca: {espesor_roca_fondo:.2f} m)."
        )

    espesor_bajo_desplante = prof_max - desplante_real
    min_bajo_desplante = (1.5 * ancho_zapata_m) if (ancho_zapata_m > 0) else 2.0
    cumple_prof_desplante = espesor_bajo_desplante >= min_bajo_desplante

    cumple_ladera = True
    msg_ladera = "No aplica (estructura fuera de borde de barranca/ladera)."
    if en_ladera and ancho_zapata_m > 0:
        req_dist = 2.0 * ancho_zapata_m
        req_esp = 1.5 * ancho_zapata_m
        cumple_ladera = (distancia_horiz_talud_m >= req_dist) and (espesor_bajo_desplante >= req_esp)
        msg_ladera = (
            f"{'CUMPLE' if cumple_ladera else 'NO CUMPLE'}: Retiro horiz. talud = {distancia_horiz_talud_m:.2f} m "
            f"(mín. 2B = {req_dist:.2f} m) | Bajo desplante = {espesor_bajo_desplante:.2f} m (mín. 1.5B = {req_esp:.2f} m)."
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


def calcular_socavacion_sict(df_tramos, aplica_socavacion=True,
                             motivo_no_aplica="Cruce sin corriente de agua (ej. PFFCC / PSV / PIV)",
                             gasto_diseno_m3s=120.0, ancho_efectivo_m=25.0, tirante_medio_m=2.50,
                             tirante_local_m=2.80, velocidad_aprox_ms=2.40, periodo_retorno_anios=100,
                             ancho_pila_m=1.20, largo_pila_m=3.60, angulo_esviaje_deg=0.0,
                             forma_pila="Circular / Redondeada", metodo_local="Envolvente (Mayor)",
                             dm_manual_mm=None, gamma_d_manual_tm3=None, tipo_cauce_manual="Auto"):
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
        Hs, x_exp, modelo_cauce = Ho, 0.0, "Roca sana (no erosionable)"
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
        k1_laur, kf_yar = 1.10, 12.4
    elif "AGUD" in forma_pila.upper() or "LENTIC" in forma_pila.upper():
        k1_laur, kf_yar = 0.90, 10.0
    else:
        k1_laur, kf_yar = 1.00, 8.5

    k2_esv = (math.cos(theta_rad) + (lp / bp) * math.sin(theta_rad)) ** 0.65
    soc_laursen = 0.0 if es_roca else max(0.0, 2.0 * Ho * k1_laur * k2_esv * ((bp / Ho) ** 0.65) * (Fr0 ** 0.43))

    e_yar = 0.60
    fr_pila = V0 / math.sqrt(g * bp)
    kv_yar = max(0.50, min(1.0, 0.85 * (fr_pila ** 0.25)))
    kh_yar = 0.15 * math.log10(max(Ho / bp, 1.05))
    dm_m = dm_mm / 1000.0
    soc_yar = 0.0 if es_roca else max(0.0, (kf_yar * k2_esv) * kv_yar * (e_yar + kh_yar) * ((V0 ** 2) / g) - 30.0 * dm_m)

    met_up = str(metodo_local).upper()
    if "LAURSEN" in met_up:
        soc_loc, met_lbl = soc_laursen, "Laursen"
    elif "YAROS" in met_up:
        soc_loc, met_lbl = soc_yar, "Yaroslavtziev"
    else:
        soc_loc = max(soc_laursen, soc_yar)
        met_lbl = "Laursen (Envolvente)" if soc_laursen >= soc_yar else "Yaroslavtziev (Envolvente)"

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
        'soc_total_m': round(soc_gen + soc_loc, 2),
        'metodo_local_usado': met_lbl
    }


# ==============================================================================
# 2. ETAPA 1: PROPUESTA INICIAL — PILAS INDIVIDUALES AASHTO LRFD (O'NEILL & REESE)
#    Y ZAPATAS PRELIMINARES (PARA SELECCIÓN ESTRUCTURAL / MINUTA IV)
# ==============================================================================
def evaluar_pila_individual_aashto_lrfd(df_tramos, naf_m, D_m, L_m, socavacion_total_m=0.0, fc_kgcm2=280.0):
    """
    Calcula la capacidad de carga reducida a compresion (R_R) y a tension/extraccion (R_T)
    de una pila individual perforada conforme a AASHTO LRFD Bridge Design Specifications
    (O'Neill & Reese, 1999, Tabla 10.5.5.2.4-1):
      - Suelos Cohesivos (Metodo alfa): phi_qs = 0.45 (comp), phi_up = 0.35 (tens), phi_qp = 0.40
      - Suelos Granulares (Metodo beta): phi_qs = 0.55 (comp), phi_up = 0.45 (tens), phi_qp = 0.50
      - Roca (Horvath & Kenney / CGS):  phi_qs = 0.55 (comp), phi_up = 0.40 (tens), phi_qp = 0.50
      - Exclusiones de fuste: primeros 1.50 m bajo lecho firme (o socavado) y 1.0*D arriba de la punta.
    """
    D = max(0.40, float(D_m))
    L = max(3.0, float(L_m))
    z_soc = max(0.0, float(socavacion_total_m))
    Pa = 100.0

    z_act_ini = z_soc + 1.50
    z_act_fin = max(z_act_ini, L - 1.0 * D)
    L_efectiva = max(0.0, z_act_fin - z_act_ini)

    perim = math.pi * D
    Ap = (math.pi * (D ** 2)) / 4.0

    prof_max_s = float(df_tramos['Prof_fin'].max()) if not df_tramos.empty else L
    df_ext = df_tramos.copy()
    if L + 2.0 * D > prof_max_s and not df_ext.empty:
        ult_fila = df_ext.iloc[-1].copy()
        ult_fila['Prof_ini'] = prof_max_s
        ult_fila['Prof_fin'] = L + 2.5 * D
        ult_fila['Espesor'] = ult_fila['Prof_fin'] - ult_fila['Prof_ini']
        ult_fila['P_med'] = 0.5 * (ult_fila['Prof_ini'] + ult_fila['Prof_fin'])
        ult_fila['Sigma_v0_eff'] = ult_fila['Sigma_v0_eff'] + 10.0 * (ult_fila['P_med'] - prof_max_s)
        df_ext = pd.concat([df_ext, pd.DataFrame([ult_fila])], ignore_index=True)

    Rs_nom_kN = 0.0
    Rs_comp_red_kN = 0.0
    Rs_tens_red_kN = 0.0
    kh_acum = 0.0
    dz_kh = 0.0

    for _, t in df_ext.iterrows():
        zi = max(float(t['Prof_ini']), z_act_ini)
        zf = min(float(t['Prof_fin']), z_act_fin)
        dz = zf - zi
        if dz > 0:
            z_med_tramo = 0.5 * (zi + zf)
            tipo = str(t['Tipo'])
            n60_t = float(t['N60']) if pd.notna(t['N60']) else 20.0
            su_t = max(float(t['c_kPa']), 6.0 * n60_t if tipo == 'Cohesivo' else 0.0)
            sig_eff = max(15.0, float(t['Sigma_v0_eff']))

            if tipo == 'Roca':
                qu_kpa = (float(t['UC_MPa']) * 1000.0) if pd.notna(t['UC_MPa']) else 5000.0
                qs_kpa = min(2500.0, 0.65 * Pa * math.sqrt(qu_kpa / Pa))
                phi_qs, phi_up = 0.55, 0.40
            elif tipo == 'Cohesivo':
                rel_su = su_t / Pa
                if rel_su <= 1.5:
                    alpha = 0.55
                elif rel_su <= 2.5:
                    alpha = 0.55 - 0.10 * (rel_su - 1.5)
                else:
                    alpha = max(0.35, 0.45 - 0.05 * (rel_su - 2.5))
                qs_kpa = min(200.0, alpha * su_t)
                phi_qs, phi_up = 0.45, 0.35
            else:
                beta_base = max(0.25, min(1.20, 1.50 - 0.245 * math.sqrt(max(z_med_tramo, 1.0))))
                factor_n = min(1.0, n60_t / 15.0)
                beta = max(0.25, beta_base * factor_n)
                qs_kpa = min(190.0, beta * sig_eff)
                phi_qs, phi_up = 0.55, 0.45

            dRs = perim * qs_kpa * dz
            Rs_nom_kN += dRs
            Rs_comp_red_kN += phi_qs * dRs
            Rs_tens_red_kN += phi_up * dRs

        zi_k = max(float(t['Prof_ini']), z_soc)
        zf_k = min(float(t['Prof_fin']), L)
        dz_k = zf_k - zi_k
        if dz_k > 0:
            zm_k = 0.5 * (zi_k + zf_k) - z_soc
            n60_k = float(t['N60']) if pd.notna(t['N60']) else 20.0
            if str(t['Tipo']) == 'Cohesivo':
                cu_k = max(float(t['c_kPa']), 6.0 * n60_k, 25.0)
                kh_tm3 = (67.0 * cu_k) / (D * 9.81)
            elif str(t['Tipo']) == 'Roca':
                kh_tm3 = 25000.0 / D
            else:
                kh_tm3 = (25.0 * n60_k) * (max(zm_k, 0.5) / D)
            kh_acum += kh_tm3 * dz_k
            dz_kh += dz_k

    zp_i, zp_f = L, L + 2.0 * D
    dz_p, n60_p_ac, su_p_ac, dz_coh_p, dz_roca_p, uc_p_ac = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    for _, t in df_ext.iterrows():
        zi = max(float(t['Prof_ini']), zp_i)
        zf = min(float(t['Prof_fin']), zp_f)
        dz = zf - zi
        if dz <= 0:
            continue
        tp = str(t['Tipo'])
        n60_v = float(t['N60']) if pd.notna(t['N60']) else 25.0
        if tp == 'Roca':
            dz_roca_p += dz
            uc_p_ac += (float(t['UC_MPa']) if pd.notna(t['UC_MPa']) else 10.0) * dz
        elif tp == 'Cohesivo':
            dz_coh_p += dz
            su_p_ac += max(float(t['c_kPa']), 6.0 * n60_v, 30.0) * dz
        else:
            n60_p_ac += n60_v * dz
        dz_p += dz

    if dz_roca_p >= 0.5 * max(dz_p, 0.01):
        uc_med = uc_p_ac / max(dz_roca_p, 0.01)
        qp_kpa = min(10000.0, 2.5 * uc_med * 1000.0 * 0.35)
        phi_qp = 0.50
        Es_base_kpa = 300000.0
    elif dz_coh_p >= 0.5 * max(dz_p, 0.01):
        su_med = su_p_ac / max(dz_coh_p, 0.01)
        Nc_tip = min(9.0, 6.0 * (1.0 + 0.20 * (max(L - z_soc, D) / D)))
        qp_kpa = min(4000.0, Nc_tip * su_med)
        phi_qp = 0.40
        Es_base_kpa = 600.0 * su_med
    else:
        dz_fr = max(dz_p - dz_coh_p - dz_roca_p, 0.01)
        n60_med = n60_p_ac / dz_fr if dz_p > 0 else 35.0
        qp_kpa = min(2900.0, 57.5 * min(n60_med, 50.0))
        phi_qp = 0.50
        Es_base_kpa = 3500.0 * min(n60_med, 50.0)

    Rp_nom_kN = qp_kpa * Ap
    Rp_comp_red_kN = phi_qp * Rp_nom_kN

    L_enterrada_real = max(0.5, L - z_soc)
    if naf_m is None or naf_m >= L:
        L_seca, L_sum = L_enterrada_real, 0.0
    elif naf_m <= z_soc:
        L_seca, L_sum = 0.0, L_enterrada_real
    else:
        L_seca = naf_m - z_soc
        L_sum = L - naf_m
    W_neto_kN = Ap * (L_seca * 24.0 + L_sum * (24.0 - 9.81))

    RR_comp_ton = (Rs_comp_red_kN + Rp_comp_red_kN) / 9.81
    RT_tens_ton = (Rs_tens_red_kN + 0.90 * W_neto_kN) / 9.81

    Ec_tm2 = 14000.0 * math.sqrt(max(fc_kgcm2, 200.0)) * 10.0
    xi_fuste = (Rp_comp_red_kN + 0.50 * Rs_comp_red_kN) / max(Rs_comp_red_kN + Rp_comp_red_kN, 1.0)
    delta_fuste = (xi_fuste * L) / max(Ap * Ec_tm2, 1.0)
    kv_base_tm3 = Es_base_kpa / (D * (1.0 - 0.30**2) * 9.81)
    delta_base = 1.0 / max(kv_base_tm3 * Ap, 1.0)
    Kv_t_cm = (1.0 / (delta_fuste + delta_base)) / 100.0
    kh_prom_tm3 = kh_acum / max(dz_kh, 0.1)

    return {
        'D_m': round(D, 2),
        'L_m': round(L, 2),
        'L_efectiva_m': round(L_efectiva, 2),
        'Cf_comp_ton': round(Rs_comp_red_kN / 9.81, 1),
        'Cp_comp_ton': round(Rp_comp_red_kN / 9.81, 1),
        'R_comp_ton': round(RR_comp_ton, 1),
        'Cf_tens_ton': round(Rs_tens_red_kN / 9.81, 1),
        'W_neto_ton': round(W_neto_kN / 9.81, 1),
        'R_tens_ton': round(RT_tens_ton, 1),
        'kh_prom_tm3': round(kh_prom_tm3, 1),
        'Kv_cabeza_t_cm': round(Kv_t_cm, 2)
    }


def generar_propuesta_inicial_sict(df_tramos, naf_m, diametros_pilas, longitudes_pilas,
                                   anchos_zapatas, desplantes_zapatas, socavacion_total_m=0.0):
    filas_pilas = []
    for l_val in longitudes_pilas:
        for d_val in diametros_pilas:
            filas_pilas.append(
                evaluar_pila_individual_aashto_lrfd(df_tramos, naf_m, d_val, l_val, socavacion_total_m=socavacion_total_m)
            )
    df_pilas_prop = pd.DataFrame(filas_pilas)

    mat_pila_comp = df_pilas_prop.pivot(index='L_m', columns='D_m', values='R_comp_ton') if not df_pilas_prop.empty else pd.DataFrame()
    mat_pila_tens = df_pilas_prop.pivot(index='L_m', columns='D_m', values='R_tens_ton') if not df_pilas_prop.empty else pd.DataFrame()
    mat_pila_kv = df_pilas_prop.pivot(index='L_m', columns='D_m', values='Kv_cabeza_t_cm') if not df_pilas_prop.empty else pd.DataFrame()

    filas_zap = []
    for df_v in desplantes_zapatas:
        for b_v in anchos_zapatas:
            rz = revisar_zapata_aashto_sict(
                df_tramos, naf_m, B_m=b_v, L_m=b_v * 2.0, Df_m=df_v,
                V_ton=100.0, H_B_ton=0.0, H_L_ton=0.0, M_B_tonm=0.0, M_L_tonm=0.0,
                socavacion_total_m=socavacion_total_m
            )
            filas_zap.append({
                'Df_m': rz['Df_m'],
                'B_m': rz['B_m'],
                'q_adm_kgcm2': rz['q_adm_asd_kgcm2'],
                'q_adm_tm2': rz['q_adm_asd_tm2'],
                'ks_tm3': rz['ks_tm3'],
                'excede_4m_tdr': rz['excede_4m_tdr']
            })
    df_zap_prop = pd.DataFrame(filas_zap)
    mat_zap_qadm = df_zap_prop.pivot(index='Df_m', columns='B_m', values='q_adm_tm2') if not df_zap_prop.empty else pd.DataFrame()
    mat_zap_kgcm2 = df_zap_prop.pivot(index='Df_m', columns='B_m', values='q_adm_kgcm2') if not df_zap_prop.empty else pd.DataFrame()

    return {
        'df_pilas': df_pilas_prop,
        'mat_pila_comp_ton': mat_pila_comp,
        'mat_pila_tens_ton': mat_pila_tens,
        'mat_pila_kv_tcm': mat_pila_kv,
        'df_zapatas': df_zap_prop,
        'mat_zap_qadm_tm2': mat_zap_qadm,
        'mat_zap_qadm_kgcm2': mat_zap_kgcm2
    }


# ==============================================================================
# 3. CIMENTACIÓN SUPERFICIAL DEFINITIVA AASHTO (TdR 1.5.8)
# ==============================================================================
def revisar_zapata_aashto_sict(df_tramos, naf_m, B_m, L_m, Df_m,
                               V_ton, H_B_ton=0.0, H_L_ton=0.0, M_B_tonm=0.0, M_L_tonm=0.0,
                               socavacion_total_m=0.0, es_sismo=False,
                               FS_capacidad=3.0, FS_deslizamiento_min=1.50, FS_volteo_min=2.00,
                               phi_b_lrfd=0.45, nu=0.30):
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
    peso_z, c_ac, tanp_ac, gam_ac, es_inv_ac = 0.0, 0.0, 0.0, 0.0, 0.0

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
    B_p, L_p = (L_eff, B_eff) if B_eff > L_eff else (B_eff, L_eff)
    Area_eff = B_eff * L_eff

    q_act_tm2 = V_safe / Area_eff
    q_act_kpa = q_act_tm2 * 9.81
    q_act_kgcm2 = q_act_kpa * 0.01019716

    phi_r = math.radians(phi_bulbo)
    if phi_bulbo <= 0.05:
        nq, nc, ng = 1.0, 5.14, 0.0
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
    denom_ks = max(B_p * (1.0 - nu**2) * If_rig, 1e-4)
    ks_tm3 = (max(es_bulbo, 500.0) / denom_ks) / 9.81

    q_neta_act_kpa = max(0.0, q_act_kpa - q_sobrecarga)
    se_m = (q_neta_act_kpa * denom_ks) / max(es_bulbo, 500.0)
    se_cm = se_m * 100.0
    cumple_asentamiento = (se_cm <= 2.50)

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
        'ks_tm3': round(ks_tm3, 0),
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
# 4. MÉTODO DE DAVISSON Y ROBINSON (1965) Y MÉTODO LATERAL DE BROMS (1964)
# ==============================================================================
def analizar_davisson_robinson_sict(df_tramos, naf_m, D_m, L_enterrada_m,
                                    P_axial_act_ton=150.0, altura_libre_col_m=0.0,
                                    socavacion_total_m=0.0, fc_kgcm2=250.0,
                                    condicion_cabeza="Articulada - Traslación Impedida (K = 0.80)"):
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

    z_sup, z_inf = z_soc, z_soc + 8.0 * D
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
        zf_m, L_emp_min_m = 1.40 * R_m, 4.0 * R_m
        modelo_dr = f"Módulo Constante Cohesivo (Kh = {Kh_kpa:.0f} kPa, R = {R_m:.2f} m)"
        param_rigidez_m = R_m
    else:
        dz_fricc = max(dz_tot - dz_coh, 0.01)
        n60_med = (n60_ac / dz_fricc) if dz_tot > 0 else 20.0
        nh_seco = 250.0 * max(n60_med, 4.0)
        nh_kNm3 = (0.60 * nh_seco) if sumergido else nh_seco
        T_m = (EpIp_kNm2 / max(nh_kNm3, 200.0)) ** 0.20
        zf_m, L_emp_min_m = 1.80 * T_m, 4.0 * T_m
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

    P_cr_ton = ((math.pi ** 2) * EpIp_kNm2 / max(L_eq_pandeo ** 2, 0.25)) / 9.81
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


def analizar_capacidad_lateral_broms(df_tramos, naf_m, D_m, L_efec_lat_m,
                                     H_pila_act_ton=25.0, e_brazo_m=0.0):
    """
    Calcula la capacidad lateral ultima y admisible del suelo (FS=2.0) y el
    momento resistente / maximo por pilote mediante el metodo de Broms (1964).
    """
    b = max(0.40, float(D_m))
    # En pilotes largos (L > 6.5*D), la reaccion pasiva lateral efectiva de Broms se moviliza en el tramo superior (6.5*D)
    L = min(max(2.0, float(L_efec_lat_m)), 6.5 * b)
    e = max(0.0, float(e_brazo_m))
    P_act = max(0.10, float(H_pila_act_ton))

    z_lim = 6.0 * b
    dz_t, dz_c, cu_ac, phi_ac, gam_ac = 0.0, 0.0, 0.0, 0.0, 0.0
    for _, t in df_tramos.iterrows():
        ov_f = min(float(t['Prof_fin']), z_lim)
        dz = ov_f - float(t['Prof_ini'])
        if dz <= 0:
            continue
        gam_ef = (float(t['Gamma']) - 9.81) if (naf_m is not None and float(t['P_med']) > naf_m) else float(t['Gamma'])
        gam_ac += max(5.0, gam_ef) * dz
        if t['Tipo'] == 'Cohesivo':
            dz_c += dz
            cu_ac += max(float(t['c_kPa']), 25.0) * dz
        else:
            phi_ac += max(float(t['phi_deg']), 28.0) * dz
        dz_t += dz

    gam_tm3 = ((gam_ac / max(dz_t, 0.01)) if dz_t > 0 else 17.5) / 9.81
    es_cohesivo = (dz_c >= 0.5 * dz_t) if dz_t > 0 else False

    if not es_cohesivo:
        phi_med = (phi_ac / max(dz_t - dz_c, 0.01)) if (dz_t - dz_c) > 0 else 32.0
        Kp = math.tan(math.radians(45.0 + phi_med / 2.0)) ** 2
        Pt_ult_ton = (0.5 * gam_tm3 * b * (L ** 3) * Kp) / max(e + L, 0.5)
        Mt_ult_tonm = 0.5 * gam_tm3 * b * (L ** 3) * Kp
        f_m = min(L, 0.816 * math.sqrt(P_act / max(gam_tm3 * b * Kp, 0.01)))
        M_max_act_tonm = P_act * (e + 0.67 * f_m)
    else:
        cu_tm2 = ((cu_ac / max(dz_c, 0.01)) if dz_c > 0 else 50.0) / 9.81
        L_util = max(0.5, L - 1.5 * b)
        Pt_ult_ton = (2.25 * cu_tm2 * b * (L_util ** 2)) / max(1.0 + (e / max(L_util, 0.5)), 1.0)
        Mt_ult_tonm = 2.25 * cu_tm2 * b * (L_util ** 2)
        f_m = min(L_util, P_act / max(9.0 * cu_tm2 * b, 0.1))
        M_max_act_tonm = P_act * (e + 1.5 * b + 0.5 * f_m)

    Pt_adm_ton = Pt_ult_ton / 2.0
    Mt_adm_tonm = Mt_ult_tonm / 1.5

    return {
        'Pt_ult_pila_ton': round(Pt_ult_ton, 1),
        'Pt_adm_pila_ton': round(Pt_adm_ton, 1),
        'Mt_ult_pila_tonm': round(Mt_ult_tonm, 1),
        'Mt_adm_pila_tonm': round(Mt_adm_tonm, 1),
        'f_prof_mmax_m': round(f_m, 2),
        'M_max_act_pila_tonm': round(M_max_act_tonm, 1),
        'cumple_lateral_broms': (P_act <= Pt_adm_ton)
    }


# ==============================================================================
# 5. ETAPA 2: REVISIÓN DEFINITIVA DE GRUPO DE PILOTES POR APOYO
#    (Capacidad Grupo AASHTO 10.7.3.9 + Tensión + Poulos 1994 + Broms + Davisson)
# ==============================================================================
def _calcular_asentamiento_grupo_poulos(df_tramos, D_m, L_m, nx, ny, sep_m, Q_grupo_ton, pred_punta=False, fc_kgcm2=280.0):
    n_tot = max(1, int(nx) * int(ny))
    if n_tot == 1:
        A_grupo = (math.pi * (D_m ** 2)) / 4.0
        d_e = D_m
    else:
        Bg = (max(1, int(nx)) - 1) * sep_m + D_m
        Lg = (max(1, int(ny)) - 1) * sep_m + D_m
        A_grupo = Bg * Lg
        d_e = (1.13 if pred_punta else 1.27) * math.sqrt(A_grupo)

    es_fuste_ac, dz_f = 0.0, 0.0
    for _, t in df_tramos.iterrows():
        zf = min(float(t['Prof_fin']), L_m)
        dz = zf - float(t['Prof_ini'])
        if dz <= 0:
            continue
        es_fuste_ac += max(float(t['Es_kPa']), 4000.0) * dz
        dz_f += dz
    Es_fuste_kpa = (es_fuste_ac / max(dz_f, 0.1)) if dz_f > 0 else 15000.0

    eb_ac, dz_b = 0.0, 0.0
    for _, t in df_tramos.iterrows():
        zi = max(float(t['Prof_ini']), L_m)
        zf = min(float(t['Prof_fin']), L_m + 3.0 * d_e)
        dz = zf - zi
        if dz <= 0:
            continue
        eb_ac += max(float(t['Es_kPa']), 8000.0) * dz
        dz_b += dz
    if dz_b > 0:
        Eb_kpa = eb_ac / dz_b
    elif not df_tramos.empty:
        Eb_kpa = max(float(df_tramos.iloc[-1]['Es_kPa']) * 1.5, 20000.0)
    else:
        Eb_kpa = 25000.0

    rel_L_de = max(0.2, min(10.0, L_m / max(d_e, 0.4)))
    rel_Eb_Es = max(1.0, min(100.0, Eb_kpa / max(Es_fuste_kpa, 1000.0)))

    x_lde = [0.0, 1.0, 2.0, 3.0, 5.0, 10.0]
    curva_eb1 = [0.46, 0.37, 0.30, 0.25, 0.21, 0.17]
    curva_eb2 = [0.34, 0.25, 0.21, 0.19, 0.17, 0.15]
    curva_eb5 = [0.18, 0.13, 0.12, 0.12, 0.125, 0.12]
    curva_eb10 = [0.09, 0.08, 0.08, 0.085, 0.10, 0.10]
    curva_eb100 = [0.01, 0.025, 0.04, 0.05, 0.07, 0.08]

    i1 = float(np.interp(rel_L_de, x_lde, curva_eb1))
    i2 = float(np.interp(rel_L_de, x_lde, curva_eb2))
    i5 = float(np.interp(rel_L_de, x_lde, curva_eb5))
    i10 = float(np.interp(rel_L_de, x_lde, curva_eb10))
    i100 = float(np.interp(rel_L_de, x_lde, curva_eb100))

    Is = float(np.interp(math.log10(rel_Eb_Es), [0.0, math.log10(2), math.log10(5), 1.0, 2.0], [i1, i2, i5, i10, i100]))

    Q_kN = max(0.0, float(Q_grupo_ton)) * 9.81
    S_grupo_mm = ((Q_kN * Is) / max(d_e * Es_fuste_kpa, 100.0)) * 1000.0

    return {
        'd_e_m': round(d_e, 2),
        'Is_poulos': round(Is, 3),
        'asentamiento_mm': round(S_grupo_mm, 1),
        'cumple_servicio_25mm': (S_grupo_mm <= 25.0)
    }


def revisar_apoyo_definitivo_sict(df_tramos, naf_m, fila_apoyo, socavacion_total_m=0.0):
    nombre_ap = str(fila_apoyo.get('Apoyo', 'Apoyo 1'))
    tipo_cim = str(fila_apoyo.get('Tipo_Cimentacion', 'Grupo de Pilas'))
    elev_ntn = _a_float(fila_apoyo.get('Elev_NTN_msnm', 100.0), 100.0)
    df_zap_cabezal = max(0.5, _a_float(fila_apoyo.get('Df_Cabezal_Zapata_m', 2.0), 2.0))
    elev_desp_zap = elev_ntn - df_zap_cabezal

    V_comp = max(0.0, _a_float(fila_apoyo.get('V_Comp_ton', 400.0), 400.0))
    T_tens = max(0.0, _a_float(fila_apoyo.get('T_Tens_ton', 0.0), 0.0))
    Hx = _a_float(fila_apoyo.get('Hx_ton', 25.0), 25.0)
    Hy = _a_float(fila_apoyo.get('Hy_ton', 10.0), 10.0)
    Mx = _a_float(fila_apoyo.get('Mx_tonm', 40.0), 40.0)
    My = _a_float(fila_apoyo.get('My_tonm', 80.0), 80.0)
    H_res = math.hypot(Hx, Hy)

    if "ZAPATA" in tipo_cim.upper():
        B_z = max(0.8, _a_float(fila_apoyo.get('B_Zapata_m', 3.5), 3.5))
        L_z = max(B_z, _a_float(fila_apoyo.get('L_Zapata_m', 8.0), 8.0))
        rz = revisar_zapata_aashto_sict(
            df_tramos, naf_m, B_m=B_z, L_m=L_z, Df_m=df_zap_cabezal,
            V_ton=max(V_comp, 1.0), H_B_ton=Hx, H_L_ton=Hy, M_B_tonm=My, M_L_tonm=Mx,
            socavacion_total_m=socavacion_total_m
        )
        return {
            'Apoyo': nombre_ap,
            'Tipo_Cimentacion': 'Zapata Aislada',
            'Arreglo': f"B={B_z:.2f}x{L_z:.2f} m",
            'N_Pilas': 0,
            'D_m': np.nan,
            'Elev_NTN_msnm': round(elev_ntn, 3),
            'Elev_Desplante_Zap_msnm': round(elev_desp_zap, 3),
            'Elev_Desplante_Pilas_msnm': np.nan,
            'L_Total_m': round(df_zap_cabezal, 2),
            'L_Efectiva_m': round(rz['Df_efectivo_m'], 2),
            'V_Comp_Act_ton': round(V_comp, 1),
            'Cap_Comp_Indiv_ton': np.nan,
            'Cap_Comp_Grupo_ton': round(rz['q_adm_asd_tm2'] * rz['Area_eff_m2'], 1),
            'T_Tens_Act_ton': round(T_tens, 1),
            'T_Max_Pila_Crit_ton': np.nan,
            'Cap_Tens_Pila_Ef_ton': np.nan,
            'Cap_Tens_Grupo_ton': 0.0,
            'Asentamiento_mm': rz['Se_mm'],
            'H_Act_ton': round(H_res, 1),
            'H_Adm_Grupo_ton': rz['R_desl_ton'],
            'M_Max_Act_tonm': round(max(abs(Mx), abs(My)), 1),
            'M_Adm_Grupo_tonm': round(V_comp * (B_z / 2.0) / rz['FS_volt_req'], 1),
            'L_Min_Davisson_m': np.nan,
            'FS_Pandeo': np.nan,
            'Estado': 'CUMPLE' if (rz['cumple_global'] and T_tens <= 0.1) else 'REVISAR',
            'detalle_zapata': rz
        }

    nx = max(1, int(_a_float(fila_apoyo.get('Pilas_nx', 2), 2)))
    ny = max(1, int(_a_float(fila_apoyo.get('Pilas_ny', 2), 2)))
    n_pilas = nx * ny
    D = max(0.50, _a_float(fila_apoyo.get('D_Pila_m', 1.20), 1.20))
    L_pila = max(4.0, _a_float(fila_apoyo.get('L_Pila_m', 18.0), 18.0))
    rel_s_d = max(2.5, _a_float(fila_apoyo.get('Sep_entre_D', 3.0), 3.0))
    S_m = rel_s_d * D

    elev_desp_pilas = elev_desp_zap - L_pila
    prof_punta_desde_ntn = df_zap_cabezal + L_pila

    z_ini_pila = max(df_zap_cabezal, socavacion_total_m)
    res_1p = evaluar_pila_individual_aashto_lrfd(
        df_tramos, naf_m, D_m=D, L_m=prof_punta_desde_ntn, socavacion_total_m=z_ini_pila
    )
    Rc_1 = res_1p['R_comp_ton']
    Rt_1 = res_1p['R_tens_ton']
    L_efec_pila = max(0.5, L_pila - 1.50 - 1.0 * D)

    est_sup = df_tramos.iloc[0] if not df_tramos.empty else None
    es_arcilla_blanda = (est_sup is not None and est_sup['Tipo'] == 'Cohesivo' and est_sup['c_kPa'] < 50.0)
    if n_pilas == 1:
        eta_comp, eta_tens = 1.00, 1.00
    else:
        eta_comp = float(np.interp(rel_s_d, [2.5, 6.0], [0.65, 1.00])) if es_arcilla_blanda else 1.00
        eta_tens = float(np.interp(rel_s_d, [2.5, 4.0], [0.67, 1.00]))

    Bg = (nx - 1) * S_m + D
    Lg = (ny - 1) * S_m + D
    if n_pilas > 1:
        perim_blq = 2.0 * (Bg + Lg)
        area_blq = Bg * Lg
        c_med_blq = float(df_tramos['c_kPa'].mean()) if not df_tramos.empty else 40.0
        su_eq = max(c_med_blq, 50.0)
        R_blq_comp_ton = (0.55 * (perim_blq * L_pila * su_eq + 9.0 * su_eq * area_blq)) / 9.81
        W_blq_ton = (area_blq * L_pila * 18.0) / 9.81
        R_blq_tens_ton = (0.45 * (perim_blq * L_pila * su_eq)) / 9.81 + 0.90 * W_blq_ton
        Rc_grupo = min(n_pilas * Rc_1 * eta_comp, R_blq_comp_ton) if es_arcilla_blanda else (n_pilas * Rc_1 * eta_comp)
        Rt_grupo = min(n_pilas * Rt_1 * eta_tens, R_blq_tens_ton)
    else:
        Rc_grupo, Rt_grupo = Rc_1, Rt_1

    B_cab = Bg + 0.70 if n_pilas > 1 else (D + 0.60)
    L_cab = Lg + 0.70 if n_pilas > 1 else (D + 0.60)
    h_cab = max(1.20, 1.20 * D)
    W_cab_ton = (B_cab * L_cab * h_cab * 24.0) / 9.81

    xs = np.linspace(-(nx - 1) * S_m / 2.0, (nx - 1) * S_m / 2.0, nx) if nx > 1 else np.array([0.0])
    ys = np.linspace(-(ny - 1) * S_m / 2.0, (ny - 1) * S_m / 2.0, ny) if ny > 1 else np.array([0.0])
    sum_x2 = ny * float(np.sum(xs ** 2))
    sum_y2 = nx * float(np.sum(ys ** 2))
    x_max = float(np.max(np.abs(xs)))
    y_max = float(np.max(np.abs(ys)))

    My_tot = abs(My) + abs(Hx) * h_cab
    Mx_tot = abs(Mx) + abs(Hy) * h_cab

    dP_My = (My_tot * x_max / sum_x2) if sum_x2 > 1e-4 else 0.0
    dP_Mx = (Mx_tot * y_max / sum_y2) if sum_y2 > 1e-4 else 0.0

    P_comp_max_pila = ((V_comp + W_cab_ton) / n_pilas) + dP_My + dP_Mx
    if T_tens > 0.01:
        T_max_pila = max(0.0, ((T_tens - 0.90 * W_cab_ton) / n_pilas) + dP_My + dP_Mx)
    else:
        T_max_pila = max(0.0, dP_My + dP_Mx - ((0.90 * V_comp + 0.90 * W_cab_ton) / n_pilas))

    Rt_pila_ef = Rt_1 * eta_tens
    Rc_pila_ef = Rc_1 * eta_comp

    ok_comp = (V_comp <= Rc_grupo) and (P_comp_max_pila <= Rc_pila_ef * 1.05)
    ok_tens = (T_tens <= Rt_grupo) and (T_max_pila <= Rt_pila_ef)

    pred_punta = (res_1p['Cp_comp_ton'] > res_1p['Cf_comp_ton'])
    res_poulos = _calcular_asentamiento_grupo_poulos(
        df_tramos, D_m=D, L_m=L_pila, nx=nx, ny=ny, sep_m=S_m, Q_grupo_ton=V_comp, pred_punta=pred_punta
    )

    p_mult_lat = 0.75 if n_pilas > 1 else 1.00
    H_por_pila = H_res / n_pilas
    res_broms = analizar_capacidad_lateral_broms(
        df_tramos, naf_m, D_m=D, L_efec_lat_m=max(3.0, L_pila), H_pila_act_ton=H_por_pila / p_mult_lat, e_brazo_m=0.0
    )
    H_adm_grupo = res_broms['Pt_adm_pila_ton'] * n_pilas * p_mult_lat
    M_adm_grupo = res_broms['Mt_adm_pila_tonm'] * n_pilas * p_mult_lat

    h_libre_soc = max(0.0, socavacion_total_m - df_zap_cabezal)
    res_dr = analizar_davisson_robinson_sict(
        df_tramos, naf_m, D_m=D, L_enterrada_m=L_pila,
        P_axial_act_ton=max(P_comp_max_pila, 10.0), altura_libre_col_m=h_libre_soc,
        socavacion_total_m=z_ini_pila
    )

    cumple_todo = ok_comp and ok_tens and res_poulos['cumple_servicio_25mm'] and (H_res <= H_adm_grupo) and res_dr['cumple_pandeo']

    return {
        'Apoyo': nombre_ap,
        'Tipo_Cimentacion': 'Grupo de Pilas' if n_pilas > 1 else 'Pila Individual',
        'Arreglo': f"{n_pilas} pilas ({nx}x{ny}) @ {S_m:.2f}m",
        'N_Pilas': n_pilas,
        'D_m': round(D, 2),
        'Elev_NTN_msnm': round(elev_ntn, 3),
        'Elev_Desplante_Zap_msnm': round(elev_desp_zap, 3),
        'Elev_Desplante_Pilas_msnm': round(elev_desp_pilas, 3),
        'L_Total_m': round(L_pila, 2),
        'L_Efectiva_m': round(L_efec_pila, 2),
        'V_Comp_Act_ton': round(V_comp, 1),
        'P_Max_Pila_Comp_ton': round(P_comp_max_pila, 1),
        'Cap_Comp_Indiv_ton': round(Rc_1, 1),
        'Cap_Comp_Grupo_ton': round(Rc_grupo, 1),
        'T_Tens_Act_ton': round(T_tens, 1),
        'T_Max_Pila_Crit_ton': round(T_max_pila, 1),
        'Cap_Tens_Pila_Ef_ton': round(Rt_pila_ef, 1),
        'Cap_Tens_Grupo_ton': round(Rt_grupo, 1),
        'Asentamiento_mm': res_poulos['asentamiento_mm'],
        'H_Act_ton': round(H_res, 1),
        'H_Adm_Grupo_ton': round(H_adm_grupo, 1),
        'M_Max_Act_tonm': round(res_broms['M_max_act_pila_tonm'] * n_pilas, 1),
        'M_Adm_Grupo_tonm': round(M_adm_grupo, 1),
        'L_Min_Davisson_m': res_dr['L_emp_min_requerida_m'],
        'FS_Pandeo': res_dr['FS_pandeo'],
        'Estado': 'CUMPLE' if cumple_todo else 'REVISAR',
        'detalle_poulos': res_poulos,
        'detalle_broms': res_broms,
        'detalle_davisson': res_dr
    }


# ==============================================================================
# 6. ETAPA 3: EMPUJES METRO A METRO EN MUROS, EXCAVACIONES Y TERRAPLENES
# ==============================================================================
def calcular_empujes_muros_sict(altura_muro_m=6.0, gamma_relleno_kNm3=19.0,
                                phi_relleno_deg=32.0, c_relleno_kpa=0.0,
                                beta_talud_relleno_deg=0.0, h_eq_sobrecarga_m=0.60,
                                kh_sismico=0.12, kv_sismico=0.0):
    H = max(1.0, float(altura_muro_m))
    gam = max(14.0, float(gamma_relleno_kNm3))
    gam_tm3 = gam / 9.81
    phi = max(15.0, min(45.0, float(phi_relleno_deg)))
    c = max(0.0, float(c_relleno_kpa))
    beta = max(0.0, min(phi - 1.0, float(beta_talud_relleno_deg)))

    phi_r, beta_r = math.radians(phi), math.radians(beta)
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
        raiz_mo = math.sqrt((math.sin(phi_r) * math.sin(phi_r - psi_r - beta_r)) / max(math.cos(psi_r) * math.cos(beta_r), 1e-5))
        den_mo = math.cos(psi_r) * ((1.0 + raiz_mo) ** 2)
        Kae = (1.0 - kv) * (num_mo / max(den_mo, 1e-5))

    delta_Kae = max(0.0, Kae - Ka)
    q_sc_kpa = gam * max(0.0, float(h_eq_sobrecarga_m))
    q_sc_tm2 = q_sc_kpa / 9.81

    cotas_z = sorted(list(set([float(z) for z in range(0, int(math.floor(H)) + 1)] + [round(H, 2)])))
    filas_z = []
    for z in cotas_z:
        pa_suelo_tm2 = Ka * gam_tm3 * z
        ea_suelo_tm = 0.5 * pa_suelo_tm2 * z
        ea_sc_tm = (Ka * q_sc_tm2) * z
        ea_est_tm = ea_suelo_tm + ea_sc_tm
        de_sis_tm = 0.5 * gam_tm3 * (z ** 2) * delta_Kae
        z_ap = (z / 3.0) if z > 0 else 0.0
        filas_z.append({
            'H (m)': round(z, 2),
            'Ka': round(Ka, 3),
            'Pa (t/m²)': round(pa_suelo_tm2, 2),
            'Ea Relleno (t/m)': round(ea_suelo_tm, 2),
            'Ea + Sobrecarga (t/m)': round(ea_est_tm, 2),
            'ΔE Sismo (t/m)': round(de_sis_tm, 2),
            'Ea Sísmico Total (t/m)': round(ea_est_tm + de_sis_tm, 2),
            'Punto Aplicación (m)': round(z_ap, 2),
            'Kp': round(Kp, 2)
        })
    df_empujes_z = pd.DataFrame(filas_z)

    Ea_relleno_kNm = max(0.0, 0.5 * gam * (H ** 2) * Ka - 2.0 * c * H * math.sqrt(Ka))
    Ea_sc_kNm = q_sc_kpa * H * Ka
    E0_reposo_kNm = 0.5 * gam * (H ** 2) * K0 + q_sc_kpa * H * K0
    dE_sismo_kNm = 0.5 * gam * (H ** 2) * delta_Kae

    Ea_estatico_tot_tm = (Ea_relleno_kNm + Ea_sc_kNm) / 9.81
    Ea_sismico_tot_tm = (Ea_relleno_kNm + Ea_sc_kNm + dE_sismo_kNm) / 9.81

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
        'E0_reposo_tm': round(E0_reposo_kNm / 9.81, 2),
        'M_volc_estatico_tmm': round(M_volc_estatico_tmm, 2),
        'M_volc_sismico_tmm': round(M_volc_sismico_tmm, 2),
        'df_empujes_z': df_empujes_z
    }


def analizar_terraplen_y_excavacion_sict(df_tramos, naf_m,
                                         altura_terraplen_m=5.0, corona_terraplen_m=12.0,
                                         talud_terraplen_H_V=1.5, gamma_terraplen_kNm3=19.5,
                                         cv_consolidacion_m2_anio=2.5,
                                         prof_excavacion_m=2.5, talud_exc_propuesto_H_V=0.58):
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

    asent_elastico_m, asent_consolid_m, espesor_cohesivo_acum = 0.0, 0.0, 0.0
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
            dh_c = (float(t['Cc']) / (1.0 + float(t['e0']))) * dz * math.log10((sigma_v0 + delta_sigma_kpa) / sigma_v0)
            asent_consolid_m += max(0.0, dh_c)
            espesor_cohesivo_acum += dz

    se_corto_cm = asent_elastico_m * 100.0
    sc_largo_cm = asent_consolid_m * 100.0
    s_total_terr_cm = se_corto_cm + sc_largo_cm

    t90_meses = ((0.848 * ((espesor_cohesivo_acum / 2.0) ** 2)) / max(float(cv_consolidacion_m2_anio), 0.1)) * 12.0 if espesor_cohesivo_acum > 0.1 else 0.0

    if s_total_terr_cm > 10.0:
        mitigacion = "Instalar drenes verticales prefabricados + precarga temporal, pedraplén basal y losa de transición reforzada."
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
        ov_f = min(t['Prof_fin'], max(H_exc, 3.0))
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
        c_exc, phi_exc_rad, gam_exc = 25.0, math.radians(28.0), 18.0

    c_eq_kpa = max(c_exc, 15.0 + 12.0 * math.tan(phi_exc_rad))
    No_est = float(np.interp(beta_exc_deg, [45.0, 60.0, 75.0, 90.0], [6.20, 5.25, 4.45, 3.85]))
    H_crit_sin_ademe_m = max(1.50, min((No_est * c_eq_kpa * 0.70) / max(gam_exc, 14.0), 6.00))

    theta_crit = 0.5 * (beta_exc_rad + phi_exc_rad)
    peso_cuna = 0.5 * gam_exc * (H_exc ** 2) * max(0.08, (1.0 / math.tan(theta_crit)) - (1.0 / math.tan(beta_exc_rad)))
    long_falla = H_exc / max(math.sin(theta_crit), 0.1)
    f_res_talud = c_eq_kpa * long_falla + max(0.0, peso_cuna * math.cos(theta_crit)) * math.tan(phi_exc_rad)
    FS_talud_exc = min(9.99, f_res_talud / max(0.1, peso_cuna * math.sin(theta_crit)))

    requiere_diseno_especial_4m = (H_exc > 4.00) or (H_exc > H_crit_sin_ademe_m)
    if H_exc > 4.00:
        rec_exc = f"Excavación profunda H = {H_exc:.2f} m (> 4.00 m TdR 1.5.7): Ejecutar bermas cada 3.5 m o ademe/tablaestaca temporal."
    elif H_exc > H_crit_sin_ademe_m:
        rec_exc = f"H = {H_exc:.2f} m supera H_máx sin estabilización ({H_crit_sin_ademe_m:.2f} m): Abatir talud o colocar ademe ligero."
    else:
        rec_exc = f"CUMPLE sin estabilización especial (H = {H_exc:.2f} m <= H_máx = {H_crit_sin_ademe_m:.2f} m para talud {beta_exc_deg:.0f}°)."

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
        'H_max_sin_estab_m': round(H_crit_sin_ademe_m, 2),
        'FS_talud_exc': round(FS_talud_exc, 2),
        'cumple_talud_exc': (FS_talud_exc >= 1.30) and (H_exc <= H_crit_sin_ademe_m),
        'requiere_diseno_especial_4m': requiere_diseno_especial_4m,
        'recomendacion_excavacion': rec_exc
    }


# ==============================================================================
# 7. ORQUESTADOR INTEGRAL DE 2 ETAPAS + MÓDULOS COMPLEMENTARIOS SICT / AASHTO
# ==============================================================================
def ejecutar_estudio_sict_modular(df_tramos, naf_m, config_modulos, params):
    resultados = {
        'tipo_cruce': params.get('tipo_cruce', 'PFFCC (Paso Superior de Ferrocarril)'),
        'alcance_etapa': params.get('alcance_etapa', 'Completo (Etapa 1: Propuesta Inicial + Etapa 2: Revisión Estructural)'),
        'config_modulos': config_modulos,
        'naf_m': naf_m
    }

    if config_modulos.get('aplica_socavacion', False):
        res_soc = calcular_socavacion_sict(
            df_tramos, aplica_socavacion=True,
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
            metodo_local=params.get('metodo_soc_local', 'Envolvente (Mayor)')
        )
    else:
        res_soc = calcular_socavacion_sict(
            df_tramos, aplica_socavacion=False,
            motivo_no_aplica=f"No aplica socavación hidráulica por tratarse de: {params.get('tipo_cruce', 'Paso sin cauce fluvial')}."
        )
    resultados['socavacion'] = res_soc
    soc_tot_m = res_soc['soc_total_m']

    if config_modulos.get('aplica_exploracion', True):
        resultados['exploracion'] = revisar_criterios_exploracion_sict(
            df_tramos,
            prof_desplante_m=params.get('Df_ref_exp_m', 2.5),
            ancho_zapata_m=params.get('B_ref_exp_m', 3.0),
            en_ladera=params.get('en_ladera', False),
            distancia_horiz_talud_m=params.get('dist_talud_m', 8.0),
            corte_subrasante_m=params.get('corte_subrasante_m', 0.0)
        )
    else:
        resultados['exploracion'] = {'aplica': False}

    if config_modulos.get('aplica_propuesta_inicial', True):
        d_pilas_prop = params.get('diametros_prop', [0.80, 1.00, 1.20, 1.50])
        l_pilas_prop = params.get('longitudes_prop', [12.0, 15.0, 18.0, 21.0, 24.0])
        b_zap_prop = params.get('anchos_zap_prop', [2.0, 2.5, 3.0, 3.5])
        df_zap_prop = params.get('df_zap_prop', [1.5, 2.0, 2.5, 3.0])
        prop_ini = generar_propuesta_inicial_sict(
            df_tramos, naf_m, d_pilas_prop, l_pilas_prop, b_zap_prop, df_zap_prop, socavacion_total_m=soc_tot_m
        )
        prop_ini['aplica'] = True
        resultados['propuesta_inicial'] = prop_ini
    else:
        resultados['propuesta_inicial'] = {'aplica': False}

    df_apoyos_in = params.get('df_apoyos_estructurales', None)
    if config_modulos.get('aplica_revision_definitiva', True) and df_apoyos_in is not None and not df_apoyos_in.empty:
        lista_res_ap = []
        for _, fila_ap in df_apoyos_in.iterrows():
            lista_res_ap.append(revisar_apoyo_definitivo_sict(df_tramos, naf_m, fila_ap, socavacion_total_m=soc_tot_m))
        df_res_apoyos = pd.DataFrame([{k: v for k, v in d.items() if not k.startswith('detalle_')} for d in lista_res_ap])
        resultados['revision_definitiva'] = {
            'aplica': True,
            'lista_apoyos': lista_res_ap,
            'df_resumen_apoyos': df_res_apoyos
        }
        ap_pilas = [a for a in lista_res_ap if 'detalle_davisson' in a]
        ap_zaps = [a for a in lista_res_ap if 'detalle_zapata' in a]
        resultados['davisson_pandeo'] = ap_pilas[0]['detalle_davisson'] if ap_pilas else {'aplica': False}
        resultados['superficial_aashto'] = ap_zaps[0]['detalle_zapata'] if ap_zaps else {'aplica': False}
    else:
        resultados['revision_definitiva'] = {'aplica': False}
        resultados['davisson_pandeo'] = {'aplica': False}
        resultados['superficial_aashto'] = {'aplica': False}

    if config_modulos.get('aplica_empujes_muros', True):
        resultados['empujes_muros'] = calcular_empujes_muros_sict(
            altura_muro_m=params.get('H_muro_m', 6.5),
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
            prof_excavacion_m=params.get('H_exc_m', 2.5),
            talud_exc_propuesto_H_V=params.get('talud_exc_HV', 0.58)
        )
    else:
        resultados['terraplen_excavacion'] = {'aplica': False}

    return resultados