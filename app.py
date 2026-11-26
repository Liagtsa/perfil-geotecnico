import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox
import io
import os
import textwrap
from PIL import Image

# Importación limpia de los módulos especializados de cimentaciones profundas, superficiales y memorias
from cimentaciones_profundas import (
    procesar_sondeo_completo,
    generar_matrices_parametricas,
    obtener_tabla_balasto_metro_a_metro,
    calcular_asentamiento_elastico_pila_ntc
)
from generador_memoria_pdf import generar_memoria_calculo_pdf
from cimentaciones_superficiales import (
    procesar_datos_superficiales,
    generar_analisis_parametrico_zapatas,
    calcular_asentamientos_cargas_estructurales_ntc
)
from generador_memoria_zapatas import generar_memoria_zapatas_pdf, cargar_imagen_logo
from calculos_sict_puentes import procesar_sondeo_sict, extraer_config_sict_desde_proyecto, ejecutar_estudio_sict_modular
from generador_memoria_sict import generar_memoria_sict_pdf

# ==========================================
# 0. CONFIGURACIÓN DE PÁGINA E ICONO
# ==========================================
ruta_logo = "logo_empresa.png"
if os.path.exists(ruta_logo):
    try:
        icono_pestana = Image.open(ruta_logo)
    except Exception:
        icono_pestana = "🏗️"
else:
    icono_pestana = "🏗️"

st.set_page_config(
    page_title="Portal Geotécnico - Perfiles y Cimentaciones",
    page_icon=icono_pestana,
    layout="wide"
)

# ==========================================
# 1. SISTEMA DE LOGIN (Autenticación Segura)
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    with col_centro:
        if os.path.exists(ruta_logo):
            st.image(ruta_logo, width=180)
        
        st.title("Portal de Ingeniería Geotécnica")
        st.subheader("Acceso al Sistema")
        
        usuario_input = st.text_input("Usuario")
        contrasena_input = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar"):
            try:
                usuario_valido = st.secrets.get("USUARIO", "admin")
                contrasena_valida = st.secrets.get("CONTRASENA", "geotecnia2026")
            except Exception:
                usuario_valido = "admin"
                contrasena_valida = "geotecnia2026"
            
            if usuario_input == usuario_valido and contrasena_input == contrasena_valida:
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==========================================
# 2. MOTOR GEOTÉCNICO Y PERFIL ISO 710-2
# ==========================================
PROF_POR_PAGINA = 25.0

def generar_plantilla_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_proy = pd.DataFrame({
            'Parametro': ['Proyecto', 'Elemento', 'Sondeo', 'Fecha', 'LogoURL', 
                          'Coordenadas', 'Elevacion_Sup', 'Elevacion_Fondo', 'Rasante_Final', 'NAF', 'Fecha_NAF',
                          'Eficiencia_SPT', 'Diametro_Barrena_mm', 'Muestreador_Liner', 'Gamma_Default_kN_m3',
                          'Diametro_Min_m', 'Diametro_Max_m', 'Diametro_Paso_m',
                          'Longitud_Min_m', 'Longitud_Max_m', 'Longitud_Paso_m',
                          'Zap_Df_Min_m', 'Zap_Df_Max_m', 'Zap_Df_Paso_m',
                          'Zap_Corrida_B_Min_m', 'Zap_Corrida_B_Max_m', 'Zap_Corrida_B_Paso_m',
                          'Zap_Aislada_B_Min_m', 'Zap_Aislada_B_Max_m', 'Zap_Aislada_B_Paso_m',
                          'Zap_Colindante', 'Zap_Se_Max_Corrida_cm', 'Zap_Se_Max_Aislada_cm', 'Zap_Margen_Deformacion_pct',
                          'SICT_Contrato', 'SICT_Tipo_Obra', 'SICT_Camino', 'SICT_Tramo', 'SICT_Localizacion',
                          'SICT_Aplica_Socavacion', 'SICT_Responsable_Tecnico', 'SICT_Cedula_Prof',
                          'SICT_H_Muro_m', 'SICT_kh_Sismo', 'SICT_H_Terraplen_m'],
            'Valor': ['ESTUDIO DE MECÁNICA DE SUELOS', 'SISTEMA DE TRANSPORTE POR CABLE', 'PERFIL ESTRATIGRÁFICO SONDEO 1', 
                      'NOVIEMBRE 2026', 'logo_empresa.png', 
                      'N 2 106 106   E 586 885   WGS84', '2170.53', '2140.53', '2170.53', '5.8', '2026-11-25',
                      '60', '100', 'CON_LINER', '18.0',
                      '0.8', '1.6', '0.2',
                      '14.0', '26.0', '2.0',
                      '1.8', '2.8', '0.2',
                      '0.6', '1.2', '0.2',
                      '1.8', '3.0', '0.2',
                      'NO', '2.5', '5.0', '80.0',
                      'SICT-2026-S/N', 'PFFCC (Paso Superior de Ferrocarril — Sin Cauce)', 'Vía Férrea / Vialidad', 'Km 0+000.00', 'Puebla, Pue.',
                      'NO', 'ING. ESPECIALISTA EN GEOTECNIA', 'S/D',
                      '7.0', '0.12', '6.5']
        })
        df_proy.to_excel(writer, sheet_name='Proyecto', index=False)
        
        df_hum = pd.DataFrame({
            'Prof_ini': [0.0, 3.0, 8.0, 15.0, 22.0, 27.0],
            'Prof_fin': [3.0, 8.0, 15.0, 22.0, 27.0, 32.0],
            'W%': [15, 20, 18, 22, 19, 14],
            'SPT': ['15', '25', '50/10', 'TS', 'ABT', 'NQ'],
            'Recuperacion_cm': [45, 60, 50, 40, 30, 25],
            'RQD_cm': [np.nan, np.nan, np.nan, np.nan, 20, 18],
            'Gamma_kN_m3': [17.5, 18.0, 18.5, 19.0, 22.0, 24.0],
            'Angulo_deg': [np.nan, 28, np.nan, np.nan, np.nan, 35],
            'Cohesion_kPa': [np.nan, 35, np.nan, np.nan, np.nan, 50],
            'Es_kPa': [np.nan, 14500.0, np.nan, np.nan, np.nan, np.nan],
            'UC_Roca_MPa': [np.nan, np.nan, np.nan, np.nan, 85, 120],
            'PLT_MPa': [np.nan, np.nan, np.nan, np.nan, 40, 55]
        })
        df_hum.to_excel(writer, sheet_name='Humedades', index=False)
        
        df_ind = pd.DataFrame({
            'Prof_ini': [0.0, 8.0, 22.0],
            'Prof_fin': [8.0, 22.0, 32.0],
            'F%': [10, 45, 8],
            'LL': [25, 40, np.nan],
            'LP': [15, 20, np.nan],
            'SUCS': ['SC', 'CL', 'Roca'],
            'Tipo_Mecanico': ['Friccionante', 'Cohesivo', 'Roca'],
            'Descripción': ['Arena arcillosa con grava.', 'Arcilla de baja plasticidad.', 'Fragmentos de roca basáltica.']
        })
        df_ind.to_excel(writer, sheet_name='PruebasIndice', index=False)
    return output.getvalue()

def procesar_spt(valor):
    if pd.isna(valor) or str(valor).lower() == 'nan': return np.nan, ""
    val_str = str(valor).strip().upper()
    if '00:00:00' in val_str: return np.nan, val_str.split(' ')[0]
    if val_str == 'ABT': return np.nan, "ABT"
    if val_str in ['TS', 'NQ']: return np.nan, val_str
    if '/' in val_str:
        partes = val_str.split('/')
        try: return float(partes[0]), val_str
        except Exception: return np.nan, val_str
    try: return float(val_str), ""
    except Exception: return np.nan, val_str

def obtener_patron(sucs):
    s = str(sucs).strip().upper()
    if not s or s == 'NAN': return '', 'white'
    if 'ROCA' in s or (s.startswith('R') and not s.startswith('RD')): return 'xx', '#b0b0b0'
    if 'PT' in s or 'OL' in s or 'OH' in s: return '+-', '#d2b48c'
    if 'G' in s and 'C' in s: return '///oo', '#d5d0ce'
    if 'G' in s and 'M' in s: return '-.oo', '#dcd8d5'
    if 'S' in s and 'C' in s: return '///...', '#eae5d8'
    if 'S' in s and 'M' in s: return '-...', '#f0efe0'
    if 'C' in s and 'M' in s: return '///-.', '#d0ccd0'
    if 'G' in s and 'S' in s: return '...oo', '#e8e5dc'
    if 'G' in s: return 'oo', '#e0e0e0'
    if 'C' in s: return '///', '#c0c0c0'
    if 'M' in s: return '-.', '#e6e6fa'
    if 'S' in s: return '...', '#f5f5dc'
    return '', 'white'

def generar_pdf_desde_excel(archivo_excel):
    df_proyecto = pd.read_excel(archivo_excel, sheet_name='Proyecto').set_index('Parametro')
    df_agua = pd.read_excel(archivo_excel, sheet_name='Humedades')
    df_indice = pd.read_excel(archivo_excel, sheet_name='PruebasIndice')

    def get_proy(param, default=""):
        return str(df_proyecto.loc[param, 'Valor']) if param in df_proyecto.index and pd.notna(df_proyecto.loc[param, 'Valor']) else default

    p_proy = get_proy('Proyecto', 'ESTUDIO DE MECÁNICA DE SUELOS')
    p_elem = get_proy('Elemento', 'PROYECTO')
    p_sondeo = get_proy('Sondeo', 'PERFIL ESTRATIGRÁFICO')
    p_fecha = get_proy('Fecha', 'OCTUBRE 2026')
    logo_url = get_proy('LogoURL', 'logo_empresa.png')
    p_coords = get_proy('Coordenadas', 'N/A')
    p_esup = get_proy('Elevacion_Sup', 'N/A')
    p_efon = get_proy('Elevacion_Fondo', 'N/A')
    p_ras = get_proy('Rasante_Final', 'N/A')
    p_naf = get_proy('NAF', 'N/A')
    p_fnaf = get_proy('Fecha_NAF', 'N/A')

    df_agua = df_agua.rename(columns={'W%': 'w'})
    df_indice = df_indice.rename(columns={'F%': 'F'})

    cols_resistencia = ['Angulo_deg', 'Cohesion_kPa', 'UC_Roca_MPa', 'PLT_MPa']
    for col in cols_resistencia:
        if col not in df_agua.columns: df_agua[col] = np.nan
        else: df_agua[col] = pd.to_numeric(df_agua[col], errors='coerce')

    for col in ['Prof_ini', 'Prof_fin', 'w']: df_agua[col] = pd.to_numeric(df_agua[col], errors='coerce')
    for col in ['Prof_ini', 'Prof_fin', 'LL', 'LP', 'F']: df_indice[col] = pd.to_numeric(df_indice[col], errors='coerce')

    df_agua['Prof_media'] = (df_agua['Prof_ini'] + df_agua['Prof_fin']) / 2.0
    df_indice['Prof_media'] = (df_indice['Prof_ini'] + df_indice['Prof_fin']) / 2.0
    df_agua = df_agua.sort_values(by='Prof_media').reset_index(drop=True)
    df_indice = df_indice.sort_values(by='Prof_media').reset_index(drop=True)

    df_agua['SPT'] = df_agua['SPT'].astype(str)
    df_agua[['SPT_Num', 'SPT_Etiqueta']] = df_agua['SPT'].apply(lambda x: pd.Series(procesar_spt(x)))

    prof_max = max(df_agua['Prof_fin'].max(), df_indice['Prof_fin'].max())
    total_paginas = max(1, int(np.ceil(prof_max / PROF_POR_PAGINA)))
    limites_estratos = pd.concat([df_indice['Prof_ini'], df_indice['Prof_fin']]).dropna().unique()

    pdf_buffer = io.BytesIO()
    
    with PdfPages(pdf_buffer) as pdf:
        for num_pagina in range(1, total_paginas + 1):
            y_min = (num_pagina - 1) * PROF_POR_PAGINA
            y_max = num_pagina * PROF_POR_PAGINA

            fig, (ax_desc, ax_rec, ax_prop, ax_perfil, ax_spt) = plt.subplots(
                1, 5, sharey=True, figsize=(12, 13), gridspec_kw={'width_ratios': [3.5, 1.2, 2.5, 0.8, 2]} 
            )

            ax_logo = fig.add_axes([0.08, 0.89, 0.15, 0.08])
            ax_logo.axis('off')
            img_logo_perfil = cargar_imagen_logo(logo_url)
            if img_logo_perfil is not None:
                ax_logo.imshow(img_logo_perfil, aspect='equal')
            else:
                ax_logo.text(0.5, 0.5, '[ LOGO ]', ha='center', va='center', fontsize=10, color='gray')
            
            fig.text(0.28, 0.945, f"PROYECTO: {p_proy}", fontsize=11, weight='bold')
            fig.text(0.28, 0.925, p_elem, fontsize=9)
            fig.text(0.28, 0.905, f"ELEMENTO: {p_sondeo}", fontsize=9)
            fig.text(0.95, 0.945, f"FECHA: {p_fecha}", ha='right', fontsize=9)
            fig.text(0.95, 0.925, f"PÁGINA: {num_pagina} / {total_paginas}", ha='right', fontsize=9, weight='bold')
            fig.lines.append(plt.Line2D([0.08, 0.95], [0.88, 0.88], transform=fig.transFigure, color='black', lw=1.5))
            
            ax_desc.invert_yaxis()
            ax_desc.set_ylim(y_max, y_min)
            ax_desc.set_yticks(np.arange(y_min, y_max + 1, 1))

            ax_desc.set_title("DESCRIPCIÓN Y\nCLASIFICACIÓN (SUCS)", fontsize=9, weight='bold', y=1.03, va='bottom')
            ax_desc.set_xlim(0, 1)
            ax_desc.spines['right'].set_visible(False)
            ax_desc.set_xticks([]) 
            ax_desc.set_ylabel("Profundidad (m)", fontsize=10, weight='bold')
            ax_desc.axhline(y_min, color='black', linewidth=1.2, zorder=5)
            
            if y_min < prof_max <= y_max:
                ax_desc.axhline(prof_max, color='black', linewidth=1.2)
                ax_perfil.axhline(prof_max, color='black', linewidth=1.2)
                ax_desc.text(0.5, prof_max + 0.35, f"FIN DEL SONDEO (Prof. = {prof_max:.2f} m)", 
                             ha='center', va='top', fontsize=7.5, weight='bold')
            
            for lim in limites_estratos:
                if y_min < lim < y_max: ax_desc.axhline(lim, color='black', linewidth=0.5, alpha=0.4)
            
            for _, row in df_indice.dropna(subset=['Descripción', 'Prof_ini', 'Prof_fin']).iterrows():
                p_ini_vis = max(row['Prof_ini'], y_min)
                p_fin_vis = min(row['Prof_fin'], y_max)
                if p_fin_vis > p_ini_vis:
                    desc = str(row['Descripción']).strip()
                    if desc.lower() == 'nan' or not desc: continue
                    sucs = str(row['SUCS']).strip() if pd.notna(row['SUCS']) and str(row['SUCS']).lower() != 'nan' else ""
                    texto = f"{desc} ({sucs})" if sucs else desc
                    y_pos = (p_ini_vis + p_fin_vis) / 2.0
                    ax_desc.text(0.02, y_pos, textwrap.fill(texto, width=42), fontsize=7.5, verticalalignment='center')

            ax_rec.set_title("Recuperación /\nRQD (cm)", fontsize=9, weight='bold', y=1.03, va='bottom')
            ax_rec.set_xlim(0, 1)
            ax_rec.set_xticks([])
            for lim in limites_estratos:
                if y_min < lim < y_max: ax_rec.axhline(lim, color='black', linewidth=0.5, alpha=0.4)

            for _, row in df_agua.dropna(subset=['Prof_media']).iterrows():
                prof = row['Prof_media']
                if y_min <= prof <= y_max:
                    rec, rqd = row.get('Recuperacion_cm', np.nan), row.get('RQD_cm', np.nan)
                    t_rec = f"{int(rec)}" if pd.notna(rec) else "-"
                    t_rqd = f"{int(rqd)}" if pd.notna(rqd) else "-"
                    if t_rec != "-" or t_rqd != "-": ax_rec.text(0.5, prof, f"{t_rec} / {t_rqd}", ha='center', va='center', fontsize=7.5)

            ax_prop.set_title("")
            ax_prop.set_xlim(0, 100)
            ax_prop.xaxis.set_ticks_position('bottom')
            ax_prop.tick_params(axis='x', labelsize=7, pad=2)
            ax_prop.grid(True, axis='x', color='gray', linestyle='--', alpha=0.4) 
            for lim in limites_estratos:
                if y_min < lim < y_max: ax_prop.axhline(lim, color='black', linewidth=0.5, alpha=0.4)
                
            df_aw = df_agua.dropna(subset=['w', 'Prof_media'])
            df_if = df_indice.dropna(subset=['F', 'Prof_media'])
            ax_prop.plot(df_aw['w'], df_aw['Prof_media'], 'o-', color='dodgerblue', markersize=4, lw=1)
            ax_prop.plot(df_if['F'], df_if['Prof_media'], 'o-.', color='firebrick', markersize=3, fillstyle='none', lw=0.8)
            ax_prop.plot(df_indice['LL'], df_indice['Prof_media'], marker='x', linestyle='None', color='black', markersize=5)
            ax_prop.plot(df_indice['LP'], df_indice['Prof_media'], marker='+', linestyle='None', color='black', markersize=6)

            try:
                naf = float(p_naf)
                if pd.notna(naf) and y_min <= naf <= y_max:
                    sep_naf = max(0.045, PROF_POR_PAGINA * 0.0055)
                    ax_prop.axhline(naf, color='blue', linestyle='--', linewidth=1.0, alpha=0.7, zorder=4)
                    ax_prop.plot([84, 96], [naf, naf], color='blue', lw=1.5, zorder=5)
                    ax_prop.plot(90, naf, marker='v', color='blue', markersize=6, zorder=5)
                    ax_prop.plot([86, 94], [naf + sep_naf, naf + sep_naf], color='blue', lw=1.0, zorder=5)
                    ax_prop.plot([88, 92], [naf + 2 * sep_naf, naf + 2 * sep_naf], color='blue', lw=0.8, zorder=5)
                    ax_prop.text(82, naf, f"NAF\n{naf:.1f} m", color='blue', va='center', ha='right', fontsize=7, weight='bold', zorder=5)
            except Exception: pass

            b1 = TextArea("w(", textprops=dict(color="black", fontsize=8, weight='bold'))
            b2 = TextArea("●", textprops=dict(color="dodgerblue", fontsize=8, weight='bold'))
            b3 = TextArea("),   LL(x),   LP(+),   F(", textprops=dict(color="black", fontsize=8, weight='bold'))
            b4 = TextArea("o", textprops=dict(color="firebrick", fontsize=8, weight='bold'))
            b5 = TextArea(")", textprops=dict(color="black", fontsize=8, weight='bold'))
            box_lbl = HPacker(children=[b1, b2, b3, b4, b5], align="baseline", pad=0, sep=0)
            ab_lbl = AnnotationBbox(box_lbl, (0.5, -0.033), xycoords='axes fraction', frameon=False, box_alignment=(0.5, 0.5))
            ax_prop.add_artist(ab_lbl)

            def crear_eje_superior(ax_base, posicion_y, limites, ticks, etiqueta):
                ax_nuevo = ax_base.twiny()
                ax_nuevo.set_xlim(limites); ax_nuevo.set_xticks(ticks)
                ax_nuevo.xaxis.set_ticks_position('top'); ax_nuevo.xaxis.set_label_position('top')
                ax_nuevo.spines['top'].set_position(('axes', posicion_y))
                for s in ['bottom', 'left', 'right']: ax_nuevo.spines[s].set_visible(False)
                ax_nuevo.set_xlabel(etiqueta, fontsize=7, labelpad=2, weight='bold', color='#222222')
                ax_nuevo.tick_params(axis='x', labelsize=7, colors='#222222', pad=1)
                return ax_nuevo

            ax_deg = crear_eje_superior(ax_prop, 1.000, (0, 40), [10, 20, 30, 40], "Ángulo Fricción ✦ (°)")
            ax_kpa = crear_eje_superior(ax_prop, 1.035, (0, 200), [50, 100, 150, 200], "Cohesión ✿ (kPa)")
            ax_mpa = crear_eje_superior(ax_prop, 1.070, (0, 160), [40, 80, 120, 160], "RESISTENCIA ROCA: ■ UC_rock   ◎ PLT (MPa)")

            df_deg = df_agua.dropna(subset=['Angulo_deg', 'Prof_media'])
            df_deg_p = df_deg[(df_deg['Prof_media'] >= y_min) & (df_deg['Prof_media'] <= y_max)]
            if not df_deg_p.empty:
                ax_deg.plot(df_deg_p['Angulo_deg'], df_deg_p['Prof_media'], marker='$✦$', color='black', linestyle='None', markersize=6.5, zorder=6)

            df_kpa = df_agua.dropna(subset=['Cohesion_kPa', 'Prof_media'])
            df_kpa_p = df_kpa[(df_kpa['Prof_media'] >= y_min) & (df_kpa['Prof_media'] <= y_max)]
            if not df_kpa_p.empty:
                ax_kpa.plot(df_kpa_p['Cohesion_kPa'], df_kpa_p['Prof_media'], marker='$✿$', color='black', linestyle='None', markersize=6.5, zorder=6)

            df_uc = df_agua.dropna(subset=['UC_Roca_MPa', 'Prof_media'])
            df_uc_p = df_uc[(df_uc['Prof_media'] >= y_min) & (df_uc['Prof_media'] <= y_max)]
            if not df_uc_p.empty:
                ax_mpa.plot(df_uc_p['UC_Roca_MPa'], df_uc_p['Prof_media'], marker='s', color='black', linestyle='None', markersize=5.5, zorder=6)

            df_plt = df_agua.dropna(subset=['PLT_MPa', 'Prof_media'])
            df_plt_p = df_plt[(df_plt['Prof_media'] >= y_min) & (df_plt['Prof_media'] <= y_max)]
            if not df_plt_p.empty:
                ax_mpa.plot(df_plt_p['PLT_MPa'], df_plt_p['Prof_media'], marker='$◎$', color='black', linestyle='None', markersize=6.5, zorder=6)

            ax_perfil.set_title("Perfil", fontsize=9, weight='bold', y=1.04, va='bottom')
            ax_perfil.set_xticks([])
            for _, row in df_indice.dropna(subset=['Prof_ini', 'Prof_fin']).iterrows():
                p_ini_vis, p_fin_vis = max(row['Prof_ini'], y_min), min(row['Prof_fin'], y_max)
                if p_fin_vis > p_ini_vis:
                    hatch, color = obtener_patron(row['SUCS'])
                    rect = patches.Rectangle((0, p_ini_vis), 1, p_fin_vis - p_ini_vis, linewidth=1, edgecolor='black', facecolor=color, hatch=hatch)
                    ax_perfil.add_patch(rect)

            ax_spt.set_title("N (Golpes SPT)", fontsize=9, weight='bold', y=1.04, va='bottom')
            ax_spt.set_xlim(0, 60); ax_spt.xaxis.set_ticks_position('bottom'); ax_spt.tick_params(axis='x', labelsize=7, pad=2)
            ax_spt.grid(True, axis='x', color='gray', linestyle='--', alpha=0.4)
            for lim in limites_estratos:
                if y_min < lim < y_max: ax_spt.axhline(lim, color='black', linewidth=0.5, alpha=0.4)
                
            ax_spt.step(df_agua['SPT_Num'], df_agua['Prof_media'], where='post', color='navy', linewidth=1.5)
            marcadores = {'ABT': ('v', 'firebrick'), 'TS': ('o', 'forestgreen'), 'NQ': ('s', 'purple')}
            for _, row in df_agua.dropna(subset=['Prof_media']).iterrows():
                prof = row['Prof_media']
                if y_min <= prof <= y_max:
                    etiq, val = str(row['SPT_Etiqueta']), row['SPT_Num']
                    if etiq in marcadores:
                        m, c = marcadores[etiq]
                        ax_spt.plot(5, prof, marker=m, color=c, markersize=5.5, zorder=5)
                        ax_spt.text(8.5, prof, etiq, fontsize=7.5, ha='left', va='center', color=c, weight='bold', zorder=5)
                    elif etiq != "" and etiq != "nan":
                        ax_spt.text(val - 2 if pd.notna(val) else 50, prof, etiq, fontsize=7, ha='right', va='center', color='black')

            plt.subplots_adjust(wspace=0, top=0.80, bottom=0.115, left=0.08, right=0.95)
            for ax in [ax_desc, ax_rec, ax_prop, ax_perfil, ax_spt]:
                if ax != ax_desc:
                    for s in ax.spines.values(): s.set_edgecolor('black'); s.set_linewidth(1)
                else:
                    for s in ['left', 'bottom', 'top']: ax_desc.spines[s].set_edgecolor('black'); ax_desc.spines[s].set_linewidth(1.2 if s=='top' else 1); ax_desc.spines[s].set_visible(True)

            ax_foot = fig.add_axes([0.08, 0.015, 0.87, 0.065])
            ax_foot.set_xlim(0, 1); ax_foot.set_ylim(0, 1); ax_foot.set_xticks([]); ax_foot.set_yticks([])
            for s in ax_foot.spines.values(): s.set_edgecolor('black'); s.set_linewidth(1.0); s.set_visible(True)
            ax_foot.axvline(0.55, color='black', lw=0.8)
            
            tipos_suelo = [('Grava (G)', 'oo', '#e0e0e0'), ('Arena (S)', '...', '#f5f5dc'), ('Limo (M)', '-.', '#e6e6fa'), ('Arcilla (C)', '///', '#c0c0c0'), ('Roca', 'xx', '#b0b0b0')]
            x_pos = 0.015
            for nombre, hatch, color in tipos_suelo:
                ax_foot.add_patch(patches.Rectangle((x_pos, 0.55), 0.022, 0.32, facecolor=color, hatch=hatch, edgecolor='black', lw=0.7))
                ax_foot.text(x_pos + 0.028, 0.71, nombre, va='center', fontsize=6.8)
                x_pos += 0.105
                
            ax_foot.text(0.015, 0.22, "MUESTREO:", va='center', fontsize=7, weight='bold', color='#333333')
            ax_foot.plot(0.13, 0.22, marker='v', color='firebrick', markersize=4.5); ax_foot.text(0.145, 0.22, "ABT (Tricónica)", va='center', fontsize=6.8)
            ax_foot.plot(0.265, 0.22, marker='o', color='forestgreen', markersize=4.5); ax_foot.text(0.28, 0.22, "TS (Shelby)", va='center', fontsize=6.8)
            ax_foot.plot(0.395, 0.22, marker='s', color='purple', markersize=4.5); ax_foot.text(0.41, 0.22, "NQ (Barril)", va='center', fontsize=6.8)

            ax_foot.text(0.57, 0.82, "CARACTERÍSTICAS DEL SONDEO", fontsize=7.5, weight='bold')
            ax_foot.text(0.57, 0.64, f"COORDENADAS: {p_coords}", fontsize=6.8)
            ax_foot.text(0.57, 0.46, f"ELEVACIÓN DE SUPERFICIE: {p_esup}", fontsize=6.8)
            ax_foot.text(0.57, 0.28, f"ELEVACIÓN DE FONDO: {p_efon}  |  RASANTE FINAL: {p_ras}", fontsize=6.8)
            ax_foot.text(0.57, 0.10, f"PROF. NIVEL FREÁTICO: {p_naf} m (bgs) medido el {p_fnaf}", fontsize=6.8)

            pdf.savefig(fig)
            plt.close(fig)
            
    return pdf_buffer.getvalue()

# ==========================================
# 3. INTERFAZ GRÁFICA PRINCIPAL (CON PESTAÑAS)
# ==========================================
st.title("🏗️ Portal de Ingeniería Geotécnica")
st.caption("Perfiles Estratigráficos (ISO 710-2), Cimentaciones NTC-CDMX 2023 y Estudios de Puentes SICT / AASHTO (TdR)")

tab_perfil, tab_cimentacion, tab_zapatas, tab_sict = st.tabs([
    "📄 Perfil Estratigráfico ISO 710-2",
    "🏗️ Cimentaciones Profundas (Pilas)",
    "📐 Zapatas Superficiales (NTC-CDMX 2023)",
    "🌉 Puentes SICT / AASHTO (TdR)"
])

with tab_perfil:
    st.subheader("Generador de Perfil Estratigráfico")
    st.markdown("Herramienta técnica para generación de perfiles estratigráficos bajo la norma ISO 710-2.")

    st.markdown("### 1. Plantilla de Datos")
    st.info("Descarga la plantilla Excel con las columnas de resistencia, colindancia y módulo secante axial actualizadas.")
    st.download_button(
        label="📥 Descargar Plantilla Excel",
        data=generar_plantilla_excel(),
        file_name="Datos_Sondeo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("### 2. Procesar Sondeo")
    archivo_subido = st.file_uploader("Sube tu archivo Excel lleno (.xlsx)", type=["xlsx"], key="uploader_perfil")

    if archivo_subido is not None:
        with st.spinner("Procesando datos y dibujando perfil..."):
            try:
                pdf_bytes = generar_pdf_desde_excel(archivo_subido)
                st.success("¡Perfil generado exitosamente!")
                st.download_button(
                    label="📄 Descargar Perfil en PDF",
                    data=pdf_bytes,
                    file_name="Perfil_Estratigrafico_Final.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Ocurrió un error al procesar el archivo: {e}")

with tab_cimentacion:
    st.header("Cálculo de Capacidad de Carga Profunda (NTC CDMX / Puebla)")
    st.caption("Revisión a Compresión y Tensión/Extracción con correlaciones SPT e ICR/RQD en roca.")
    
    archivo_calc = st.file_uploader("Carga el archivo Datos_Sondeo.xlsx para cálculo", type=["xlsx"], key="calc_spt")
    
    if archivo_calc is not None:
        try:
            df_tramos, naf_val, cfg = procesar_sondeo_completo(archivo_calc)
            st.success(f"Sondeo procesado: {len(df_tramos)} tramos analizados. Nivel Freático detectado: {naf_val} m")

            with st.expander("Ver Perfil Mecánico Unificado (N60, (N1)60, ICR/RQD, qu, Litología)"):
                cols_vis = ['Prof_ini', 'Prof_fin', 'SUCS', 'Tipo', 'N_campo', 'N60']
                if 'ICR' in df_tramos.columns: cols_vis.append('ICR')
                if 'qu_kPa' in df_tramos.columns: cols_vis.append('qu_kPa')
                if 'Cu_lab' in df_tramos.columns: cols_vis.append('Cu_lab')
                st.dataframe(df_tramos[cols_vis])

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Rango de Diámetros (m)")
                d_min = st.number_input("Diámetro Mínimo (m)", value=cfg['d_min'], min_value=0.40, step=0.10)
                d_max = st.number_input("Diámetro Máximo (m)", value=cfg['d_max'], min_value=d_min, step=0.10)
                paso_d = st.number_input("Paso de Diámetro (m)", value=cfg['d_paso'], min_value=0.05, step=0.05)

            with col2:
                st.subheader("Rango de Profundidades (m)")
                l_min = st.number_input("Profundidad Mínima (m)", value=cfg['l_min'], min_value=1.0, step=0.5)
                l_max = st.number_input("Profundidad Máxima (m)", value=cfg['l_max'], min_value=l_min, step=0.5)
                paso_l = st.number_input("Paso de Profundidad (m)", value=cfg['l_paso'], min_value=0.5, step=0.5)

            st.markdown("#### Configuración de Acampanamiento (Campana)")
            chk_campana = st.checkbox("¿Considerar base acampanada en la punta?", value=False)
            if chk_campana:
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    rel_camp = st.slider("Relación D_base / D_fuste", min_value=1.2, max_value=2.5, value=1.5, step=0.1)
                with col_c2:
                    h_camp = st.number_input("Altura de la campana (m) [Mínimo 0.50 m NTC]", min_value=0.50, value=1.0, step=0.10)
            else:
                rel_camp = 1.0
                h_camp = 0.0

            st.info("ℹ️ **Restricciones aplicadas automáticamente:** Se desprecian los primeros 1.50 m de fuste y 1.0·D antes de la punta/campana (criterio FHWA-NHI-10-016 / NTC-CDMX).")

            if cfg['diametros_lista'] and cfg['diametros_lista'] != 'nan':
                diametros = [float(x.strip()) for x in cfg['diametros_lista'].split(',') if x.strip()]
            else:
                diametros = np.arange(d_min, d_max + paso_d/2, paso_d).round(2).tolist()

            if cfg['longitudes_lista'] and cfg['longitudes_lista'] != 'nan':
                longitudes = [float(x.strip()) for x in cfg['longitudes_lista'].split(',') if x.strip()]
            else:
                longitudes = np.arange(l_min, l_max + paso_l/2, paso_l).round(2).tolist()

            if st.button("Calcular Matrices de Capacidad y Rigidez", type="primary"):
                matrices = generar_matrices_parametricas(
                    df_tramos, naf_val, diametros, longitudes,
                    con_campana=chk_campana, rel_campana=rel_camp, h_campana_m=h_camp
                )
                st.session_state['matrices_calculadas'] = matrices
                st.session_state['diametros_calc'] = diametros
                st.session_state['longitudes_calc'] = longitudes

            if 'matrices_calculadas' in st.session_state:
                matrices = st.session_state['matrices_calculadas']
                d_calc = st.session_state.get('diametros_calc', diametros)
                l_calc = st.session_state.get('longitudes_calc', longitudes)

                st.markdown("### 1. Capacidad Reducida a Compresión: $R$ (Toneladas)")
                st.caption(f"Evaluando {len(d_calc)} diámetros ({d_calc[0]} m a {d_calc[-1]} m) y {len(l_calc)} profundidades ({l_calc[0]} m a {l_calc[-1]} m). Considera estratos de suelo (CDMX/Puebla) y roca/fragmentos según ICR/RQD (NTC-CDMX 3.6.2.3.5).")
                st.dataframe(matrices['matriz_compresion'].style.format("{:.1f} t").highlight_max(axis=0, color="#d4edda"))

                st.markdown("### 2. Capacidad Reducida a Extracción / Tensión: $R_t$ (Toneladas)")
                st.caption("Punta nula (Cp = 0) + Fuste reducido por tensión (0.80/0.60) + Peso propio neto del elemento.")
                st.dataframe(matrices['matriz_extraccion'].style.format("{:.1f} t").highlight_max(axis=0, color="#fff3cd"))

                st.markdown("### 3. Acero Longitudinal Mínimo Requerido por Tensión ($A_s$ en cm²)")
                st.caption("Calculado para absorber el 100% de la carga de extracción admisible con fy = 4,200 kg/cm² y FR = 0.90.")
                st.dataframe(matrices['matriz_acero'].style.format("{:.1f} cm²"))

                col_k1, col_k2 = st.columns(2)
                with col_k1:
                    st.markdown("### 4. Módulo de Reacción Horizontal Promedio: $k_h$ (t/m³)")
                    st.caption("Coeficiente de balasto lateral para modelado elasto-plástico del fuste.")
                    st.dataframe(matrices['matriz_kh'].style.format("{:.1f} t/m³"))

                with col_k2:
                    st.markdown("### 5. Rigidez Axial en Cabeza: $K_v$ (t/cm)")
                    st.caption("Constante del resorte vertical de la pila para apoyos en ETABS / SAP2000.")
                    st.dataframe(matrices['matriz_Kv'].style.format("{:.2f} t/cm"))

                st.markdown("---")
                st.markdown("### 6. Módulos de Reacción Horizontal y Vertical Metro a Metro")
                st.caption("Valores discretizados por metro para la asignación de resortes puntuales laterales (kh, Kh) y verticales (kv, Kv) en nudos de software estructural (ETABS, SAP2000, Midas, STAAD).")

                col_sel1, col_sel2 = st.columns(2)
                with col_sel1:
                    sel_d = st.selectbox(
                        "Selecciona Diámetro (D) a consultar",
                        d_calc,
                        index=len(d_calc) - 1,
                        format_func=lambda x: f"D = {x:.2f} m"
                    )
                with col_sel2:
                    sel_l = st.selectbox(
                        "Selecciona Profundidad (L) a consultar",
                        l_calc,
                        index=len(l_calc) - 1,
                        format_func=lambda x: f"L = {x:.2f} m"
                    )

                df_balasto_view = obtener_tabla_balasto_metro_a_metro(df_tramos, naf_val, sel_d, sel_l)
                st.dataframe(df_balasto_view, width="stretch", hide_index=True)

                csv_balasto = df_balasto_view.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Descargar Tabla de Balasto (D={sel_d:.2f}m, L={sel_l:.2f}m) [.CSV]",
                    data=csv_balasto,
                    file_name=f"Balasto_Metro_a_Metro_D{sel_d:.2f}_L{sel_l:.2f}.csv",
                    mime="text/csv"
                )

                st.markdown("---")
                st.subheader("7. Cálculo de Asentamientos Elásticos bajo Cargas del Estructurista (Monopila vs. Grupo — NTC-CDMX 2023)")
                st.caption(
                    "Evalúa el asentamiento elástico de servicio bajo las cargas dadas por el estructurista para decidir entre **pila única (monopila)** o **grupo de pilas**."
                )

                ca_p1, ca_p2, ca_p3, ca_p4 = st.columns(4)
                with ca_p1:
                    p_est_carga = st.number_input("Carga actuante del estructurista (t)", value=650.0, min_value=1.0, step=25.0, key="p_est_carga_ntc")
                with ca_p2:
                    p_est_cond = st.selectbox("Condición de carga", options=["Tensión / Extracción", "Compresión"], index=0, key="p_est_cond_ntc")
                with ca_p3:
                    p_est_n_grp = st.number_input("Núm. de pilas en grupo (1 = Monopila)", value=4, min_value=1, max_value=16, step=1, key="p_est_ngrp_ntc")
                with ca_p4:
                    p_est_se_lim = st.number_input("Límite de servicio NTC (cm)", value=2.50, min_value=0.50, max_value=15.0, step=0.25, key="p_est_selim_ntc")

                if st.button("Comparar Asentamiento Elástico (Monopila vs. Grupo)", type="secondary", key="btn_calc_asent_pilas_ntc"):
                    es_t_b = ("Tensión" in p_est_cond)
                    r_mono = calcular_asentamiento_elastico_pila_ntc(
                        df_tramos, naf_val, sel_d, sel_l, p_est_carga,
                        es_tension=es_t_b, n_pilas_grupo=1, se_max_cm=p_est_se_lim
                    )
                    r_grp = calcular_asentamiento_elastico_pila_ntc(
                        df_tramos, naf_val, sel_d, sel_l, p_est_carga,
                        es_tension=es_t_b, n_pilas_grupo=int(p_est_n_grp), se_max_cm=p_est_se_lim
                    )
                    st.session_state['df_asent_pilas_ntc'] = pd.DataFrame([r_mono, r_grp])

                if 'df_asent_pilas_ntc' in st.session_state:
                    st.dataframe(st.session_state['df_asent_pilas_ntc'], width="stretch", hide_index=True)

                st.markdown("---")
                st.subheader("Generar Memoria de Cálculo en PDF")
                st.caption("Memoria geotécnica formal con desglose estrato por estrato, balasto metro a metro y matrices de diseño.")

                try:
                    archivo_calc.seek(0)
                    df_p_raw = pd.read_excel(archivo_calc, sheet_name='Proyecto')
                    df_p_raw['Parametro'] = df_p_raw['Parametro'].astype(str).str.strip()
                    df_proy_temp = df_p_raw.set_index('Parametro')['Valor'].to_dict()
                    nm_proy = str(df_proy_temp.get('Proyecto', 'ESTUDIO GEOTÉCNICO'))
                    nm_elem = str(df_proy_temp.get('Elemento', 'DISEÑO DE CIMENTACIONES'))
                    nm_sondeo = str(df_proy_temp.get('Sondeo', 'SONDEO 1'))
                    nm_fecha = str(df_proy_temp.get('Fecha', ''))
                    nm_logo = str(df_proy_temp.get('LogoURL', 'logo_empresa.png')).strip()
                except Exception:
                    nm_proy, nm_elem, nm_sondeo, nm_fecha, nm_logo = "PROYECTO", "CIMENTACIONES", "SONDEO 1", "", "logo_empresa.png"

                with st.spinner("Compilando memoria analítica en PDF..."):
                    pdf_memoria_bytes = generar_memoria_calculo_pdf(
                        df_tramos, matrices, nm_proy, nm_elem, nm_sondeo, nm_fecha, logo_url=nm_logo
                    )

                st.download_button(
                    label="📄 Descargar Memoria de Cálculo PDF",
                    data=pdf_memoria_bytes,
                    file_name="Memoria_Capacidad_Carga.pdf",
                    mime="application/pdf",
                    type="primary"
                )
        except Exception as e:
            st.error(f"Error al analizar el sondeo: {e}")

# ==========================================
# 4. PESTAÑA 3: CIMENTACIONES SUPERFICIALES (ZAPATAS)
# ==========================================
with tab_zapatas:
    st.header("Cálculo de Cimentaciones Superficiales — NTC-CDMX 2023")
    st.caption("Revisión combinada de Estado Límite de Falla (esfuerzo cortante) vs. Estado Límite de Servicio (deformación elástica acotada al margen normativo).")

    col_met, col_info = st.columns([1, 2])
    with col_met:
        metodo_exp_zap = st.radio(
            "Método de Exploración Geotécnica:",
            options=["SPT", "PCA"],
            format_func=lambda x: "SPT (Ensayo de Penetración Estándar)" if x == "SPT" else "PCA (Pozo a Cielo Abierto — Muestras Inalteradas)",
            key="metodo_zap_radio"
        )
    with col_info:
        if metodo_exp_zap == "SPT":
            st.info(r"**Modo SPT (NTC-CDMX 2023):** Deduce $\phi$, $c_u$ mediante correlaciones corregidas ($C_N$, $N_{60}$, $(N_1)_{60}$). Si capturas el **Módulo Elástico Secante ($E_{s,\text{sec}}$)** del ensaye axial, se usará directamente para el control de deformaciones.")
        else:
            st.info(r"**Modo PCA (Muestras Inalteradas):** Emplea los parámetros de laboratorio ($c$, $\phi$, $\gamma$) y el **Módulo Elástico Secante ($E_{s,\text{sec}}$)** del ensaye axial. En suelos con ambos parámetros ($c$ y $\phi$), evalúa las ecuaciones cohesiva y friccionante por separado conforme a NTC-CDMX 3.5.1.")

    archivo_zap = st.file_uploader("Carga el archivo Datos_Sondeo.xlsx", type=["xlsx"], key="uploader_zapatas")

    if archivo_zap is not None:
        try:
            df_tramos_z, naf_z, cfg_z = procesar_datos_superficiales(archivo_zap, metodo_exploracion=metodo_exp_zap)
            st.success(f"Archivo procesado ({metodo_exp_zap}): {len(df_tramos_z)} estratos detectados. NAF: {naf_z} m")

            col_tb_tit, col_tb_unit = st.columns([2, 1])
            with col_tb_tit:
                st.markdown(r"#### Parámetros Geotécnicos por Estrato (Introduce aquí el Módulo Elástico Secante Axial $E_{s,\text{sec}}$)")
            with col_tb_unit:
                unidad_es_sec = st.selectbox(
                    "Unidad de captura para Es Secante:",
                    options=["kPa", "kg/cm²", "MPa"],
                    index=0,
                    help="Selecciona la unidad en la que tu laboratorio reporta el módulo elástico secante (E50) del ensaye axial. Internamente se convierte a kPa.",
                    key="unidad_es_sec_zap"
                )

            factor_es_unidad = 1.0 if unidad_es_sec == "kPa" else (98.0665 if unidad_es_sec == "kg/cm²" else 1000.0)
            col_es_display = f"Es_sec ({unidad_es_sec})"

            df_vista_editor = df_tramos_z.copy()
            df_vista_editor[col_es_display] = (df_vista_editor['Es_kPa'] / factor_es_unidad).round(2)

            cols_edit_z = ['Prof_ini', 'Prof_fin', 'SUCS', 'Tipo', 'Gamma', 'c_kPa', 'phi_deg', col_es_display, 'Origen_Es']
            if metodo_exp_zap == "SPT":
                cols_edit_z.insert(5, 'N60')
                cols_edit_z.insert(6, 'N1_60')

            df_tramos_z_edit_raw = st.data_editor(
                df_vista_editor[cols_edit_z],
                column_config={
                    "Prof_ini": st.column_config.NumberColumn("Prof. Ini (m)", format="%.2f", disabled=True),
                    "Prof_fin": st.column_config.NumberColumn("Prof. Fin (m)", format="%.2f", disabled=True),
                    "SUCS": st.column_config.TextColumn("SUCS"),
                    "Tipo": st.column_config.SelectboxColumn(
                        "Comportamiento NTC-CDMX",
                        options=["Cohesivo", "Friccionante", "Dual (Cohesivo vs. Friccionante)", "Roca"],
                        help="NTC-CDMX 2023 Num. 3.5.1: En suelos con c y phi ('Dual'), evalúa ambas ecuaciones por separado y toma la más desfavorable."
                    ),
                    "Gamma": st.column_config.NumberColumn("γ (kN/m³)", min_value=10.0, max_value=28.0, step=0.1, format="%.2f"),
                    "c_kPa": st.column_config.NumberColumn("Cohesión c (kPa)", min_value=0.0, step=1.0, format="%.2f"),
                    "phi_deg": st.column_config.NumberColumn("Fricción φ (°)", min_value=0.0, max_value=50.0, step=0.5, format="%.2f"),
                    col_es_display: st.column_config.NumberColumn(
                        f"Es Secante Axial ({unidad_es_sec})",
                        min_value=0.1,
                        step=10.0 if unidad_es_sec != "MPa" else 1.0,
                        format="%.2f",
                        help=f"Módulo elástico secante (E50) obtenido del ensaye axial de laboratorio en {unidad_es_sec}."
                    ),
                    "Origen_Es": st.column_config.TextColumn("Origen Es", disabled=True)
                },
                width="stretch",
                hide_index=True,
                key="editor_estratos_zapatas"
            )

            # Convertir el módulo secante editado de vuelta a kPa para el motor de cálculo
            df_tramos_z_calc = df_tramos_z_edit_raw.copy()
            df_tramos_z_calc['Es_kPa'] = pd.to_numeric(df_tramos_z_calc[col_es_display], errors='coerce').fillna(100.0) * factor_es_unidad

            st.markdown("#### Geometrías a Evaluar")
            col_z1, col_z2, col_z3 = st.columns(3)
            with col_z1:
                st.subheader("Desplante Df (m)")
                z_df_min = st.number_input("Df Mínimo (m)", value=cfg_z['df_min'], min_value=0.50, step=0.20, key="z_df_min")
                z_df_max = st.number_input("Df Máximo (m)", value=cfg_z['df_max'], min_value=z_df_min, step=0.20, key="z_df_max")
                z_df_paso = st.number_input("Paso Df (m)", value=cfg_z['df_paso'], min_value=0.10, step=0.10, key="z_df_paso")

            with col_z2:
                st.subheader("Zapatas Corridas B (m)")
                z_bc_min = st.number_input("Ancho Corrida Mín. (m)", value=cfg_z['bc_min'], min_value=0.30, step=0.10, key="z_bc_min")
                z_bc_max = st.number_input("Ancho Corrida Máx. (m)", value=cfg_z['bc_max'], min_value=z_bc_min, step=0.10, key="z_bc_max")
                z_bc_paso = st.number_input("Paso Corrida (m)", value=cfg_z['bc_paso'], min_value=0.10, step=0.10, key="z_bc_paso")

            with col_z3:
                st.subheader("Zapatas Aisladas B (m)")
                z_ba_min = st.number_input("Ancho Aislada Mín. (m)", value=cfg_z['ba_min'], min_value=0.60, step=0.20, key="z_ba_min")
                z_ba_max = st.number_input("Ancho Aislada Máx. (m)", value=cfg_z['ba_max'], min_value=z_ba_min, step=0.20, key="z_ba_max")
                z_ba_paso = st.number_input("Paso Aislada (m)", value=cfg_z['ba_paso'], min_value=0.10, step=0.10, key="z_ba_paso")

            st.markdown("#### Parámetros Normativos (NTC-CDMX 2023 Num. 3.5.1) y Control de Deformaciones")
            col_criterio_s, col_ubic_s = st.columns(2)
            with col_criterio_s:
                criterio_suelo_ui = st.selectbox(
                    "Ecuación de Capacidad de Carga (NTC-CDMX 3.5.1):",
                    options=[
                        "Automático (Evalúa Cohesivo vs. Friccionante por separado y elige el menor)",
                        "Puramente Cohesivo (φ = 0, esfuerzos totales)",
                        "Puramente Friccionante (c = 0, esfuerzos efectivos)"
                    ],
                    index=0,
                    help="Las NTC-CDMX 2023 separan estrictamente el cálculo en dos ecuaciones independientes sin sumar c y φ en la misma fórmula.",
                    key="z_criterio_suelo_ntc"
                )
                if "Puramente Cohesivo" in criterio_suelo_ui:
                    criterio_suelo_val = "Puramente Cohesivo"
                elif "Puramente Friccionante" in criterio_suelo_ui:
                    criterio_suelo_val = "Puramente Friccionante"
                else:
                    criterio_suelo_val = "Automatico"

            with col_ubic_s:
                ubicacion_zap = st.selectbox(
                    "Ubicación / Factor de Resistencia FR (Tabla 3.6.1):",
                    options=["Interior / Central (FR = 0.65)", "Colindante / Lindero (FR = 0.35)"],
                    index=1 if cfg_z.get('es_colindante', False) else 0,
                    help="NTC-CDMX 2023 Tabla 3.6.1: FR = 0.65 para zapatas interiores; FR = 0.35 para zapatas colindantes.",
                    key="z_ubicacion_fr"
                )
                es_colindante_zap = "0.35" in ubicacion_zap
                fr_cdmx_zap = 0.35 if es_colindante_zap else 0.65

            col_p2, col_p3, col_p4 = st.columns(3)
            with col_p2:
                rel_lb = st.number_input("Relación L / B (Aislada)", value=1.0, min_value=1.0, max_value=5.0, step=0.25, key="z_rel_lb")
            with col_p3:
                fs_zap = st.number_input("Factor Seguridad Corte (FS)", value=3.0, min_value=1.5, max_value=5.0, step=0.5, key="z_fs")
            with col_p4:
                nu_zap = st.number_input("Relación de Poisson (ν)", value=0.30, min_value=0.15, max_value=0.49, step=0.05, key="z_nu")

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                se_max_corr_mm = st.number_input(
                    "Deformación Máx. Permitida Corrida (mm)",
                    value=float(cfg_z.get('se_max_corrida_cm', 2.5) * 10.0),
                    min_value=5.0, max_value=100.0, step=5.0,
                    help="Límite normativo de asentamiento para zapatas corridas (por defecto 25 mm = 2.5 cm).",
                    key="z_se_max_corr_mm"
                )
            with col_s2:
                se_max_ais_mm = st.number_input(
                    "Deformación Máx. Permitida Aislada (mm)",
                    value=float(cfg_z.get('se_max_aislada_cm', 5.0) * 10.0),
                    min_value=10.0, max_value=150.0, step=5.0,
                    help="Límite normativo de asentamiento para zapatas aisladas (por defecto 50 mm = 5.0 cm).",
                    key="z_se_max_ais_mm"
                )
            with col_s3:
                margen_def_pct = st.slider(
                    "Margen de Deformación Objetivo (% de Se_máx)",
                    min_value=50, max_value=100,
                    value=int(cfg_z.get('margen_se_pct', 80.0)),
                    step=5,
                    help="Porcentaje máximo de la deformación permitida que se usará para acotar la capacidad recomendada (ej. 80% de 50 mm = 40 mm).",
                    key="z_margen_def_pct"
                )

            df_list_z = np.arange(z_df_min, z_df_max + z_df_paso / 2, z_df_paso).round(2).tolist()
            bc_list_z = np.arange(z_bc_min, z_bc_max + z_bc_paso / 2, z_bc_paso).round(2).tolist()
            ba_list_z = np.arange(z_ba_min, z_ba_max + z_ba_paso / 2, z_ba_paso).round(2).tolist()

            if st.button("Calcular Zapatas (NTC-CDMX 2023: Falla vs. Deformación)", type="primary", key="btn_calc_zapatas"):
                analisis_z = generar_analisis_parametrico_zapatas(
                    df_tramos_z_calc,
                    naf_z,
                    df_list=df_list_z,
                    b_corridas=bc_list_z,
                    b_aisladas=ba_list_z,
                    rel_LB_aislada=rel_lb,
                    metodo_exploracion=metodo_exp_zap,
                    FS=fs_zap,
                    nu=nu_zap,
                    fr_cdmx=fr_cdmx_zap,
                    es_colindante=es_colindante_zap,
                    criterio_suelo_ntc=criterio_suelo_val,
                    se_max_corrida_cm=se_max_corr_mm / 10.0,
                    se_max_aislada_cm=se_max_ais_mm / 10.0,
                    factor_margen_se=margen_def_pct / 100.0
                )
                st.session_state['analisis_zapatas_calc'] = analisis_z
                st.session_state['df_tramos_z_pdf'] = df_tramos_z_calc

            if 'analisis_zapatas_calc' in st.session_state:
                az = st.session_state['analisis_zapatas_calc']
                df_z_pdf = st.session_state.get('df_tramos_z_pdf', df_tramos_z_calc)
                df_corr_v = az['df_corridas']
                df_ais_v = az['df_aisladas']

                st.markdown("---")
                st.subheader("1. Revisión Combinada: Capacidad por Corte vs. Capacidad Limitada por Deformación")
                st.caption(
                    f"Condición activa: **{ubicacion_zap}** | Control de deformación objetivo: **{margen_def_pct}% de Se_máx** "
                    f"({se_max_corr_mm * margen_def_pct / 100.0:.1f} mm en corridas | {se_max_ais_mm * margen_def_pct / 100.0:.1f} mm en aisladas)."
                )

                cols_vista_z = [
                    'Df', 'B', 'modelo_suelo_aplicado', 'r_cdmx_kgcm2', 'q_adm_corte_kgcm2', 'Se_corte_mm',
                    'q_adm_def_kgcm2', 'criterio_gobernante', 'q_rec_kgcm2', 'q_rec_tonm2',
                    'Se_final_mm', 'ks_ton_m3'
                ]

                formato_tabla_z = {
                    'Df': '{:.2f} m',
                    'B': '{:.2f} m',
                    'r_cdmx_kgcm2': '{:.2f}',
                    'q_adm_corte_kgcm2': '{:.2f}',
                    'Se_corte_mm': '{:.1f} mm',
                    'q_adm_def_kgcm2': '{:.2f}',
                    'q_rec_kgcm2': '{:.2f} kg/cm²',
                    'q_rec_tonm2': '{:.1f} t/m²',
                    'Se_final_mm': '{:.1f} mm',
                    'ks_ton_m3': '{:.0f} t/m³'
                }

                st.markdown(r"#### A. Zapatas Corridas ($L \gg B$)")
                st.dataframe(
                    df_corr_v[cols_vista_z].style.format(formato_tabla_z),
                    width="stretch",
                    hide_index=True
                )

                st.markdown(r"#### B. Zapatas Aisladas ($B \times L$)")
                st.dataframe(
                    df_ais_v[cols_vista_z].style.format(formato_tabla_z),
                    width="stretch",
                    hide_index=True
                )

                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.markdown(r"#### Matriz $q_{\text{rec}}$ Recomendada — Corridas (kg/cm²)")
                    st.dataframe(az['mat_corr_qrec_kgcm2'].style.format("{:.2f} kg/cm²").highlight_max(axis=0, color="#d4edda"))
                with col_m2:
                    st.markdown(r"#### Matriz $q_{\text{rec}}$ Recomendada — Aisladas (kg/cm²)")
                    st.dataframe(az['mat_ais_qrec_kgcm2'].style.format("{:.2f} kg/cm²").highlight_max(axis=0, color="#d4edda"))

                col_s_m1, col_s_m2 = st.columns(2)
                with col_s_m1:
                    st.markdown("#### Matriz Deformación Esperada $S_e$ — Corridas (cm)")
                    st.dataframe(az['mat_corr_se_final_cm'].style.format("{:.2f} cm"))
                with col_s_m2:
                    st.markdown("#### Matriz Deformación Esperada $S_e$ — Aisladas (cm)")
                    st.dataframe(az['mat_ais_se_final_cm'].style.format("{:.2f} cm"))

                st.markdown("---")
                st.subheader("2. Cálculo de Asentamientos Elásticos bajo Cargas del Estructurista (NTC-CDMX 2023)")
                st.caption(
                    "Captura las reacciones de servicio/diseño entregadas por el estructurista ($V$, $H$, $M_x$, $M_y$) y la geometría de cada zapata "
                    "para calcular su asentamiento elástico real ($S_e$) y contrastarlo contra el límite de Estado Límite de Servicio de las NTC-CDMX 2023."
                )

                if 'df_cargas_zap_default' not in st.session_state:
                    st.session_state['df_cargas_zap_default'] = pd.DataFrame([
                        {
                            'Elemento': 'Zapata Aislada ZA-1',
                            'Tipo_Zapata': 'Aislada',
                            'Df_m': 2.00,
                            'B_m': 2.20,
                            'L_m': 2.20,
                            'V_ton': 185.0,
                            'H_ton': 18.0,
                            'Mx_tonm': 10.0,
                            'My_tonm': 25.0
                        },
                        {
                            'Elemento': 'Zapata Corrida ZC-1',
                            'Tipo_Zapata': 'Corrida',
                            'Df_m': 1.80,
                            'B_m': 1.00,
                            'L_m': 6.00,
                            'V_ton': 95.0,
                            'H_ton': 8.0,
                            'Mx_tonm': 5.0,
                            'My_tonm': 12.0
                        }
                    ])

                df_cargas_edit_z = st.data_editor(
                    st.session_state['df_cargas_zap_default'],
                    num_rows="dynamic",
                    column_config={
                        "Elemento": st.column_config.TextColumn("Elemento / Eje"),
                        "Tipo_Zapata": st.column_config.SelectboxColumn("Tipo", options=["Aislada", "Corrida"]),
                        "Df_m": st.column_config.NumberColumn("Df (m)", min_value=0.3, step=0.2, format="%.2f"),
                        "B_m": st.column_config.NumberColumn("B (m)", min_value=0.4, step=0.2, format="%.2f"),
                        "L_m": st.column_config.NumberColumn("L (m)", min_value=0.4, step=0.5, format="%.2f"),
                        "V_ton": st.column_config.NumberColumn("V Vertical (t)", min_value=0.1, step=10.0, format="%.1f"),
                        "H_ton": st.column_config.NumberColumn("H Cortante (t)", min_value=0.0, step=2.0, format="%.1f"),
                        "Mx_tonm": st.column_config.NumberColumn("Mx (t·m)", step=5.0, format="%.1f"),
                        "My_tonm": st.column_config.NumberColumn("My (t·m)", step=5.0, format="%.1f"),
                    },
                    width="stretch",
                    key="editor_cargas_est_zapatas"
                )

                if st.button("Calcular Asentamientos con Cargas Estructurales (NTC-CDMX 2023)", type="secondary", key="btn_calc_asent_est_zap"):
                    df_res_asent_est = calcular_asentamientos_cargas_estructurales_ntc(
                        df_z_pdf,
                        naf_z,
                        df_cargas_edit_z,
                        nu=nu_zap,
                        es_colindante=es_colindante_zap,
                        se_max_corrida_cm=se_max_corr_mm / 10.0,
                        se_max_aislada_cm=se_max_ais_mm / 10.0
                    )
                    st.session_state['df_res_asent_est_zap'] = df_res_asent_est

                if 'df_res_asent_est_zap' in st.session_state:
                    df_ae_v = st.session_state['df_res_asent_est_zap']
                    st.dataframe(
                        df_ae_v.style.format({
                            'V_ton': '{:.1f} t',
                            'H_ton': '{:.1f} t',
                            'e_B_m': '{:.3f} m',
                            'q_act_kgcm2': '{:.2f} kg/cm²',
                            'Es_bulbo_kgcm2': '{:.1f} kg/cm²',
                            'Se_mm': '{:.1f} mm',
                            'Se_cm': '{:.2f} cm',
                            'Limite_NTC_mm': '{:.1f} mm',
                            'Uso_Limite_pct': '{:.1f}%',
                            'ks_act_tm3': '{:.0f} t/m³'
                        }),
                        width="stretch",
                        hide_index=True
                    )

                st.markdown("---")
                st.subheader("Generar Memoria de Cálculo de Zapatas en PDF")
                try:
                    archivo_zap.seek(0)
                    df_pz_raw = pd.read_excel(archivo_zap, sheet_name='Proyecto')
                    df_pz_raw['Parametro'] = df_pz_raw['Parametro'].astype(str).str.strip()
                    df_proy_z = df_pz_raw.set_index('Parametro')['Valor'].to_dict()
                    nm_proy_z = str(df_proy_z.get('Proyecto', 'ESTUDIO DE MECÁNICA DE SUELOS'))
                    nm_elem_z = str(df_proy_z.get('Elemento', 'CIMENTACIONES SUPERFICIALES'))
                    nm_sondeo_z = f"{df_proy_z.get('Sondeo', 'EXPLORACIÓN')} ({metodo_exp_zap})"
                    nm_fecha_z = str(df_proy_z.get('Fecha', ''))
                    nm_logo_z = str(df_proy_z.get('LogoURL', 'logo_empresa.png')).strip()
                except Exception:
                    nm_proy_z, nm_elem_z, nm_sondeo_z, nm_fecha_z, nm_logo_z = "PROYECTO", "CIMENTACIONES SUPERFICIALES", f"EXPLORACIÓN ({metodo_exp_zap})", "", "logo_empresa.png"

                with st.spinner("Compilando memoria ejecutiva de zapatas en PDF..."):
                    pdf_zap_bytes = generar_memoria_zapatas_pdf(
                        df_z_pdf, az, nm_proy_z, nm_elem_z, nm_sondeo_z, nm_fecha_z,
                        logo_url=nm_logo_z, df_asent_est=st.session_state.get('df_res_asent_est_zap', None)
                    )

                st.download_button(
                    label="📄 Descargar Memoria de Cálculo Zapatas PDF",
                    data=pdf_zap_bytes,
                    file_name=f"Memoria_Zapatas_NTC_CDMX_2023_{metodo_exp_zap}.pdf",
                    mime="application/pdf",
                    type="primary",
                    key="btn_descarga_pdf_zapatas"
                )
        except Exception as e:
            st.error(f"Error al procesar zapatas superficiales: {e}")




# ==========================================
# 5. PESTAÑA 4: PUENTES Y PASOS SICT / AASHTO (PRE-ESTRUCTURAL + MINUTA IV + ETAPA 2)
# ==========================================
with tab_sict:
    st.header("Estudio Geotécnico y de Cimentación para Puentes y Pasos — TdR SICT / AASHTO")
    st.caption(
        "Lee automáticamente tu plantilla unificada `Datos_Sondeo.xlsx` (la misma del Perfil Estratigráfico). "
        "Conserva la **Etapa 1 Pre-Estructural + Minuta IV (TdR 1.5.9)** con desglose de **Consideraciones Geotécnicas** y permite habilitar la **Etapa 2 (Revisión Multi-Apoyo)** cuando ya existan cargas estructurales."
    )

    archivo_sict = st.file_uploader("Carga tu archivo Datos_Sondeo.xlsx (unificado SPT / PCA)", type=["xlsx"], key="uploader_sict")

    if archivo_sict is not None:
        try:
            df_tramos_s, naf_s, proy_dict_s, pruebas_det_s = procesar_sondeo_sict(archivo_sict)
            cfg_s = extraer_config_sict_desde_proyecto(proy_dict_s)
            st.success(
                f"Plantilla procesada: **{cfg_s['Sondeo']}** ({len(df_tramos_s)} estratos válidos | "
                f"Elev. Sup.: {cfg_s['Elevacion_Sup']:.2f} m | NAF: {naf_s if naf_s is not None else 'No detectado'} m)"
            )

            opciones_cruce = [
                "PFFCC (Paso Superior de Ferrocarril — Sin Cauce)",
                "PSV / PIV (Paso Vehicular — Sin Cauce)",
                "Puente sobre Cauce Fluvial / Río",
                "Viaducto / Puente sobre Barranca Seca"
            ]
            idx_cruce_def = 2 if cfg_s['SICT_Aplica_Socavacion'] else 0
            for idx_op, op_txt in enumerate(opciones_cruce):
                if cfg_s['SICT_Tipo_Obra'][:12].upper() in op_txt.upper():
                    idx_cruce_def = idx_op
                    break

            col_tipo_cr, col_alcance_cr = st.columns([1.15, 1.35])
            with col_tipo_cr:
                tipo_cruce_sict = st.selectbox(
                    "Tipo de Estructura / Sitio de Cruce (leído de Excel):",
                    options=opciones_cruce,
                    index=idx_cruce_def,
                    key="sict_tipo_cruce"
                )
            with col_alcance_cr:
                alcance_etapa_ui = st.radio(
                    "Alcance de Entrega:",
                    options=[
                        "Etapa 1: Pre-Estructural + Propuesta Minuta IV (TdR 1.5.9)",
                        "Estudio Completo: Etapa 1 + Minuta IV + Etapa 2 (Revisión Multi-Apoyo)"
                    ],
                    index=0,
                    key="sict_alcance_radio"
                )

            es_fluvial_default = ("Fluvial" in tipo_cruce_sict) or cfg_s['SICT_Aplica_Socavacion']
            incluir_etapa2_default = ("Estudio Completo" in alcance_etapa_ui)

            # --- DESGLOSE DE CONSIDERACIONES GEOTÉCNICAS EN PANTALLA ---
            with st.expander("📋 Desglose de Consideraciones Geotécnicas y Deducción de Parámetros (Editable)", expanded=True):
                st.caption("Factores de corrección SPT (CE, CR, CB, CS, CN), estado de compacidad/consistencia, origen de parámetros (SPT vs. Laboratorio PCA) y propiedades mecánicas.")
                cols_edit_s = ['Prof_ini', 'Prof_fin', 'SUCS', 'Tipo', 'N_campo', 'N60', 'CN', 'N1_60', 'Estado_Comp', 'Gamma', 'c_kPa', 'phi_deg', 'Es_kPa', 'Origen_Param']
                df_tramos_s_edit = st.data_editor(
                    df_tramos_s[cols_edit_s],
                    column_config={
                        "Prof_ini": st.column_config.NumberColumn("Ini (m)", format="%.2f", disabled=True),
                        "Prof_fin": st.column_config.NumberColumn("Fin (m)", format="%.2f", disabled=True),
                        "N_campo": st.column_config.NumberColumn("N_camp", format="%.0f", disabled=True),
                        "N60": st.column_config.NumberColumn("N60", format="%.1f", disabled=True),
                        "CN": st.column_config.NumberColumn("CN", format="%.2f", disabled=True),
                        "N1_60": st.column_config.NumberColumn("(N1)60", format="%.1f", disabled=True),
                        "Estado_Comp": st.column_config.TextColumn("Estado / Compacidad", disabled=True),
                        "Origen_Param": st.column_config.TextColumn("Origen", disabled=True),
                    },
                    width="stretch",
                    hide_index=True,
                    key="editor_tramos_sict"
                )
                df_sict_calc = df_tramos_s.copy()
                for c_ed in ['SUCS', 'Tipo', 'Gamma', 'c_kPa', 'phi_deg', 'Es_kPa']:
                    df_sict_calc[c_ed] = df_tramos_s_edit[c_ed]

            st.markdown("#### 1. Interruptores Modulares de Cálculo")
            cm_a, cm_b, cm_c = st.columns(3)
            with cm_a:
                chk_s_exp = st.checkbox("1. Exploración y Suspensión (TdR 1.5.2)", value=True, key="chk_s_exp")
                chk_s_soc = st.checkbox("2. Socavación General y Local (TdR 1.5.6)", value=es_fluvial_default, key="chk_s_soc")
            with cm_b:
                chk_s_prop = st.checkbox("3. Etapa 1: Propuesta Pre-Estructural + Minuta IV", value=True, key="chk_s_prop")
                chk_s_rev = st.checkbox("4. Etapa 2: Revisión Definitiva Multi-Apoyo", value=incluir_etapa2_default, key="chk_s_rev")
            with cm_c:
                chk_s_emp = st.checkbox("5. Empujes Metro a Metro en Muros (SICT)", value=True, key="chk_s_emp")
                chk_s_ter = st.checkbox("6. Terraplenes y Excavaciones (TdR 1.5.7)", value=True, key="chk_s_ter")

            params_sict = {
                'tipo_cruce': tipo_cruce_sict,
                'alcance_etapa': alcance_etapa_ui
            }

            st.markdown("#### 2. Parámetros Prellenados desde tu Plantilla Excel")

            if chk_s_exp:
                with st.expander("🔍 Criterios de Exploración, Cortes y Retiro en Laderas (TdR 1.5.2)", expanded=False):
                    ce1, ce2, ce3, ce4 = st.columns(4)
                    with ce1:
                        params_sict['Df_ref_exp_m'] = st.number_input("Desplante ref. (m)", value=float(cfg_s['df_ref_m']), min_value=0.50, step=0.20, key="s_df_ref")
                    with ce2:
                        params_sict['B_ref_exp_m'] = st.number_input("Ancho B ref. (m)", value=float(cfg_s['b_ref_m']), min_value=0.60, step=0.20, key="s_b_ref")
                    with ce3:
                        params_sict['corte_subrasante_m'] = st.number_input("Corte subrasante (m)", value=0.0, min_value=0.0, step=0.50, key="s_corte_sub")
                    with ce4:
                        params_sict['en_ladera'] = st.checkbox("¿Próximo a talud / barranca?", value=False, key="s_en_lad")
                        params_sict['dist_talud_m'] = st.number_input("Retiro horiz. al talud (m)", value=8.0, min_value=0.0, step=0.50, disabled=not params_sict['en_ladera'], key="s_dist_tal")

            if chk_s_soc:
                with st.expander("🌊 Parámetros Hidráulicos de Socavación General y Local (TdR 1.5.6.1)", expanded=True):
                    cs1, cs2, cs3, cs4 = st.columns(4)
                    with cs1:
                        params_sict['Qd_m3s'] = st.number_input("Gasto diseño Qd (m³/s)", value=120.0, min_value=1.0, step=10.0, key="s_qd")
                        params_sict['Be_m'] = st.number_input("Ancho efectivo Be (m)", value=25.0, min_value=1.0, step=1.0, key="s_be")
                    with cs2:
                        params_sict['Hm_m'] = st.number_input("Tirante medio Hm (m)", value=2.50, min_value=0.20, step=0.20, key="s_hm")
                        params_sict['Ho_m'] = st.number_input("Tirante local Ho (m)", value=2.80, min_value=0.20, step=0.20, key="s_ho")
                    with cs3:
                        params_sict['V0_ms'] = st.number_input("Velocidad V0 (m/s)", value=2.40, min_value=0.10, step=0.20, key="s_v0")
                        params_sict['Tr_anios'] = st.selectbox("Periodo retorno Tr (años)", options=[50, 100, 200, 500, 1000], index=1, key="s_tr")
                    with cs4:
                        params_sict['bp_soc_m'] = st.number_input("Ancho pila b (m)", value=1.20, min_value=0.30, step=0.10, key="s_bp")
                        params_sict['lp_soc_m'] = st.number_input("Largo pila l (m)", value=3.60, min_value=0.30, step=0.20, key="s_lp")
                    cs5, cs6, cs7 = st.columns(3)
                    with cs5:
                        params_sict['esviaje_deg'] = st.number_input("Ángulo esviaje (°)", value=0.0, min_value=0.0, max_value=80.0, step=5.0, key="s_esv")
                    with cs6:
                        params_sict['forma_pila'] = st.selectbox("Nariz de pila", options=["Circular / Redondeada", "Rectangular", "Lenticular / Aguda"], key="s_fpila")
                    with cs7:
                        params_sict['metodo_soc_local'] = st.selectbox("Método Local", options=["Envolvente (Mayor)", "Laursen", "Yaroslavtziev"], key="s_msoc")

            if chk_s_prop:
                with st.expander("📊 ETAPA 1: Propuesta Inicial Pre-Estructural (Prellenada desde Hoja 'Proyecto')", expanded=True):
                    cp1, cp2 = st.columns(2)
                    with cp1:
                        st.markdown("**Pilas Individuales (AASHTO LRFD: O'Neill & Reese)**")
                        d_prop_str = st.text_input("Diámetros D (m, separados por coma)", value=cfg_s['diametros_prop_str'], key="s_dprop")
                        l_prop_str = st.text_input("Longitudes L (m, separadas por coma)", value=cfg_s['longitudes_prop_str'], key="s_lprop")
                    with cp2:
                        st.markdown("**Zapatas Preliminares (Df <= 4.0 m)**")
                        b_zap_str = st.text_input("Anchos B (m, separados por coma)", value=cfg_s['anchos_zap_prop_str'], key="s_bzprop")
                        df_zap_str = st.text_input("Desplantes Df (m, separados por coma)", value=cfg_s['df_zap_prop_str'], key="s_dfzprop")

                    try:
                        params_sict['diametros_prop'] = [round(float(x.strip()), 2) for x in d_prop_str.split(',') if x.strip()]
                        params_sict['longitudes_prop'] = [round(float(x.strip()), 2) for x in l_prop_str.split(',') if x.strip()]
                        params_sict['anchos_zap_prop'] = [round(float(x.strip()), 2) for x in b_zap_str.split(',') if x.strip()]
                        params_sict['df_zap_prop'] = [round(float(x.strip()), 2) for x in df_zap_str.split(',') if x.strip()]
                    except Exception:
                        params_sict['diametros_prop'] = [0.80, 1.00, 1.20, 1.50]
                        params_sict['longitudes_prop'] = [14.0, 18.0, 22.0, 25.0]
                        params_sict['anchos_zap_prop'] = [1.80, 2.20, 2.60, 3.00]
                        params_sict['df_zap_prop'] = [1.80, 2.00, 2.20, 2.40]

            if chk_s_rev:
                with st.expander("🏗️ ETAPA 2: Revisión Definitiva Multi-Apoyo con Descargas Estructurales", expanded=True):
                    elev_base_def = float(cfg_s['Elevacion_Sup'])
                    if 'df_apoyos_sict_default' not in st.session_state:
                        st.session_state['df_apoyos_sict_default'] = pd.DataFrame([
                            {
                                'Apoyo': 'Caballete 1', 'Tipo_Cimentacion': 'Grupo de Pilas',
                                'Elev_NTN_msnm': elev_base_def, 'Df_Cabezal_Zapata_m': 2.00,
                                'Pilas_nx': 3, 'Pilas_ny': 1, 'D_Pila_m': 1.20, 'L_Pila_m': 16.0, 'Sep_entre_D': 3.0,
                                'B_Zapata_m': 3.0, 'L_Zapata_m': 9.0,
                                'V_Comp_ton': 630.0, 'T_Tens_ton': 0.0, 'Hx_ton': 45.0, 'Hy_ton': 15.0, 'Mx_tonm': 30.0, 'My_tonm': 120.0
                            },
                            {
                                'Apoyo': 'Eje 9 Crítico', 'Tipo_Cimentacion': 'Grupo de Pilas',
                                'Elev_NTN_msnm': elev_base_def, 'Df_Cabezal_Zapata_m': 1.50,
                                'Pilas_nx': 2, 'Pilas_ny': 2, 'D_Pila_m': 1.10, 'L_Pila_m': 23.0, 'Sep_entre_D': 3.0,
                                'B_Zapata_m': 5.1, 'L_Zapata_m': 5.1,
                                'V_Comp_ton': 420.0, 'T_Tens_ton': 575.0, 'Hx_ton': 267.5, 'Hy_ton': 136.3, 'Mx_tonm': 0.0, 'My_tonm': 0.0
                            }
                        ])
                    df_apoyos_edit = st.data_editor(
                        st.session_state['df_apoyos_sict_default'],
                        num_rows="dynamic",
                        column_config={
                            "Tipo_Cimentacion": st.column_config.SelectboxColumn("Sistema Elegido", options=["Grupo de Pilas", "Zapata Aislada"]),
                        },
                        width="stretch",
                        key="editor_apoyos_sict"
                    )
                    params_sict['df_apoyos_estructurales'] = df_apoyos_edit

            if chk_s_emp:
                with st.expander("🧱 Empuje de Diseño Metro a Metro en Estribos y Muros (Rankine + Mononobe-Okabe)", expanded=False):
                    cm1, cm2, cm3 = st.columns(3)
                    with cm1:
                        params_sict['H_muro_m'] = st.number_input("Altura máxima muro H (m)", value=float(cfg_s['SICT_H_Muro_m']), min_value=1.50, step=0.50, key="s_hmuro")
                        params_sict['gamma_relleno_kNm3'] = st.number_input("γ relleno compactado (kN/m³)", value=19.0, min_value=15.0, step=0.5, key="s_gamrel")
                    with cm2:
                        params_sict['phi_relleno_deg'] = st.number_input("Ángulo fricción relleno φ (°)", value=32.0, min_value=20.0, max_value=45.0, step=1.0, key="s_phirel")
                        params_sict['beta_relleno_deg'] = st.number_input("Inclinación talud relleno β (°)", value=0.0, min_value=0.0, max_value=25.0, step=1.0, key="s_betarel")
                    with cm3:
                        params_sict['heq_sc_m'] = st.number_input("Altura equiv. sobrecarga h_eq (m)", value=0.60, min_value=0.0, step=0.10, key="s_heq")
                        params_sict['kh_sismo_muro'] = st.number_input("Coeficiente sísmico horizontal kh", value=float(cfg_s['SICT_kh_Sismo']), min_value=0.0, max_value=0.50, step=0.02, key="s_khmuro")
                    params_sict['c_relleno_kpa'] = 0.0
                    params_sict['kv_sismo_muro'] = 0.0

            if chk_s_ter:
                with st.expander("⛰️ Estabilidad de Taludes de Excavación y Terraplenes de Acceso (TdR 1.5.7)", expanded=False):
                    ct1, ct2, ct3 = st.columns(3)
                    with ct1:
                        params_sict['H_terr_m'] = st.number_input("Altura terraplén de acceso (m)", value=float(cfg_s['SICT_H_Terraplen_m']), min_value=0.50, step=0.50, key="s_hterr")
                        params_sict['B_corona_m'] = st.number_input("Ancho corona terraplén (m)", value=12.0, min_value=4.0, step=1.0, key="s_bcor")
                    with ct2:
                        params_sict['talud_terr_HV'] = st.number_input("Talud terraplén (H : 1V)", value=1.50, min_value=1.0, step=0.25, key="s_talterr")
                        params_sict['cv_m2_anio'] = st.number_input("Coef. consolidación Cv (m²/año)", value=2.50, min_value=0.20, step=0.50, key="s_cv")
                    with ct3:
                        params_sict['H_exc_m'] = st.number_input("Profundidad excavación H_exc (m)", value=float(cfg_s['df_ref_m']), min_value=0.50, step=0.20, key="s_hexc")
                        params_sict['talud_exc_HV'] = st.number_input("Talud temporal corte (H : 1V)", value=0.58, min_value=0.15, step=0.10, key="s_talexc")
                    params_sict['gamma_terr_kNm3'] = 19.5

            st.markdown("#### 3. Hojas Opcionales del Documento PDF (Minuta IV y Anexo Oficial SICT)")
            copt_main1, copt_main2 = st.columns(2)
            with copt_main1:
                chk_inc_minuta4 = st.checkbox("Incluir hoja de Minuta IV (TdR 1.5.9)", value=False, key="s_inc_minuta4")
            with copt_main2:
                chk_inc_anexo = st.checkbox("Incluir Cédula Anexo Oficial SICT", value=False, key="s_inc_anexo")

            with st.expander("📋 Datos Oficiales para Minuta IV y Cédula Anexo SICT (Prellenados de Excel)", expanded=False):
                ca1, ca2, ca3 = st.columns(3)
                with ca1:
                    s_contrato = st.text_input("Contrato No.", value=cfg_s['SICT_Contrato'], key="s_cont")
                    s_camino = st.text_input("Camino / Línea Ferroviaria", value=cfg_s['SICT_Camino'], key="s_cam")
                with ca2:
                    s_tramo = st.text_input("Tramo / Kilometraje", value=cfg_s['SICT_Tramo'], key="s_tram")
                    s_loc = st.text_input("Localización", value=cfg_s['SICT_Localizacion'], key="s_loc")
                with ca3:
                    s_resp = st.text_input("Responsable Técnico", value=cfg_s['SICT_Responsable_Tecnico'], key="s_resp")
                    s_ced = st.text_input("Cédula Profesional Núm.", value=cfg_s['SICT_Cedula_Prof'], key="s_ced")

                clab1, clab2, clab3 = st.columns(3)
                with clab1:
                    chk_cu = st.checkbox("Marcar Triaxial Consolidada (CU)", value=False, key="s_chk_cu")
                with clab2:
                    chk_cd = st.checkbox("Marcar Triaxial Lenta (CD)", value=False, key="s_chk_cd")
                with clab3:
                    chk_torc = st.checkbox("Marcar Torcómetro de Bolsillo", value=False, key="s_chk_torc")

            config_modulos_sict = {
                'aplica_exploracion': chk_s_exp,
                'aplica_socavacion': chk_s_soc,
                'aplica_propuesta_inicial': chk_s_prop,
                'aplica_revision_definitiva': chk_s_rev,
                'aplica_empujes_muros': chk_s_emp,
                'aplica_terraplenes_excavacion': chk_s_ter
            }

            if st.button("Ejecutar Estudio SICT / AASHTO (Pre-Estructural + Minuta IV)", type="primary", key="btn_calc_sict"):
                res_sict = ejecutar_estudio_sict_modular(df_sict_calc, naf_s, config_modulos_sict, params_sict)
                st.session_state['res_sict_actual'] = res_sict
                st.session_state['df_sict_pdf'] = df_sict_calc

            if 'res_sict_actual' in st.session_state:
                rs_all = st.session_state['res_sict_actual']
                df_s_pdf = st.session_state.get('df_sict_pdf', df_s_calc)

                st.markdown("---")
                st.subheader("Resultados del Estudio Geotécnico y de Cimentación (SICT / AASHTO)")

                if rs_all['exploracion'].get('aplica', False):
                    rexp = rs_all['exploracion']
                    st.markdown(f"**Criterios de Exploración (TdR 1.5.2):** {rexp['criterio_suspension_msg']} | {rexp['ladera_msg']}")

                rsoc = rs_all['socavacion']
                if rsoc.get('aplica', False):
                    ms1, ms2, ms3 = st.columns(3)
                    ms1.metric("Socavación General (Lischtvan)", f"{rsoc['soc_general_m']:.2f} m")
                    ms2.metric(f"Socavación Local ({rsoc['metodo_local_usado']})", f"{rsoc['soc_local_adoptada_m']:.2f} m")
                    ms3.metric("Socavación Total Acumulada", f"{rsoc['soc_total_m']:.2f} m")
                else:
                    st.success(f"**Socavación Hidráulica Deshabilitada (`0.00 m`):** {rsoc.get('motivo_no_aplica', '')}")

                if rs_all.get('propuesta_inicial', {}).get('aplica', False):
                    pi = rs_all['propuesta_inicial']
                    st.markdown("### Etapa 1 — Propuesta Inicial Pre-Estructural (AASHTO LRFD / Minuta IV)")
                    cp_v1, cp_v2 = st.columns(2)
                    with cp_v1:
                        st.markdown("**A. Pilas Individuales a Compresión $R_R$ (Toneladas)**")
                        st.dataframe(pi['mat_pila_comp_ton'].style.format("{:.1f} t").highlight_max(axis=0, color="#d4edda"))
                    with cp_v2:
                        st.markdown("**B. Pilas Individuales a Tensión / Extracción $R_T$ (Toneladas)**")
                        st.dataframe(pi['mat_pila_tens_ton'].style.format("{:.1f} t").highlight_max(axis=0, color="#fff3cd"))

                    cp_v3, cp_v4 = st.columns(2)
                    with cp_v3:
                        st.markdown("**C. Rigidez Axial en Cabeza de Pila $K_v$ (t/cm)**")
                        st.dataframe(pi['mat_pila_kv_tcm'].style.format("{:.2f} t/cm"))
                    with cp_v4:
                        st.markdown(r"**D. Zapatas Preliminares $q_{\text{adm}}$ (t/m², con $D_f \le 4.0$ m)**")
                        st.dataframe(pi['mat_zap_qadm_tm2'].style.format("{:.1f} t/m²"))

                if rs_all.get('revision_definitiva', {}).get('aplica', False):
                    df_rev_ap = rs_all['revision_definitiva']['df_resumen_apoyos']
                    st.markdown("### Etapa 2 — Revisión Definitiva Multi-Apoyo con Descargas Estructurales")
                    st.dataframe(df_rev_ap, width="stretch", hide_index=True)

                if rs_all['empujes_muros'].get('aplica', False):
                    rem = rs_all['empujes_muros']
                    st.markdown(f"### Etapa 3A — Empujes de Diseño en Estribos / Muros ($K_a = {rem['Ka']:.3f}$, $K_{{ae}} = {rem['Kae_mononobe']:.3f}$, $K_p = {rem['Kp']:.2f}$)")
                    st.dataframe(rem['df_empujes_z'], width="stretch", hide_index=True)

                if rs_all['terraplen_excavacion'].get('aplica', False):
                    rtr = rs_all['terraplen_excavacion']
                    st.markdown("### Etapa 3B — Estabilidad de Excavaciones y Terraplenes de Acceso")
                    mt1, mt2, mt3, mt4 = st.columns(4)
                    mt1.metric("Prof. Máx. Sin Ademe", f"{rtr['H_max_sin_estab_m']:.2f} m", f"Talud {rtr['angulo_talud_deg']:.0f}°")
                    mt2.metric("FS Talud Excavación", f"{rtr['FS_talud_exc']:.2f}", "Cumple" if rtr['cumple_talud_exc'] else "Requiere ademe")
                    mt3.metric("FS Base Terraplén", f"{rtr['FS_base_terraplen']:.2f}", "Estable" if rtr['cumple_base_terraplen'] else "Mejorar")
                    mt4.metric("Asentamiento Acceso", f"{rtr['asent_total_terraplen_cm']:.1f} cm", f"t90 = {rtr['t90_consolidacion_meses']:.1f} m")
                    st.info(f"**Excavación:** {rtr['recomendacion_excavacion']}  \n**Terraplén:** {rtr['mitigacion_terraplen']}")

                st.markdown("---")
                st.subheader("Emitir Memoria Geotécnica SICT + Minuta IV + Cédula Anexo Oficial (.PDF)")
                datos_anexo_pdf = {
                    'Proyecto': cfg_s['Proyecto'],
                    'Contrato': s_contrato,
                    'Tipo_Obra': tipo_cruce_sict,
                    'Camino': s_camino,
                    'Tramo': s_tramo,
                    'Localizacion': s_loc,
                    'Sondeo': cfg_s['Sondeo'],
                    'Fecha': cfg_s['Fecha'],
                    'Responsable_Tecnico': s_resp,
                    'Cedula_Prof': s_ced,
                    'Triaxial_CU': chk_cu,
                    'Triaxial_CD': chk_cd,
                    'Torcometro': chk_torc
                }

                with st.spinner("Compilando Memoria Geotécnica SICT estilo detallado..."):
                    pdf_sict_bytes = generar_memoria_sict_pdf(
                        df_s_pdf, rs_all, pruebas_det_s, datos_anexo_pdf,
                        logo_url=cfg_s['LogoURL'],
                        incluir_minuta4=chk_inc_minuta4,
                        incluir_anexo_sict=chk_inc_anexo
                    )

                suf_archivo = "PreEstructural_MinutaIV" if not chk_s_rev else "Completo_2Etapas_MinutaIV"
                st.download_button(
                    label=f"📄 Descargar Memoria SICT ({suf_archivo}) + Anexo Oficial (.PDF)",
                    data=pdf_sict_bytes,
                    file_name=f"Memoria_Geotecnica_SICT_{suf_archivo}.pdf",
                    mime="application/pdf",
                    type="primary",
                    key="btn_descarga_pdf_sict"
                )
        except Exception as e:
            st.error(f"Error al procesar el estudio SICT / AASHTO: {e}")