import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox
import io
import os
import textwrap
from PIL import Image

# Importación de los módulos especializados de cimentaciones profundas y memoria
from cimentaciones_profundas import (
    procesar_sondeo_completo,
    generar_matrices_parametricas,
    obtener_tabla_balasto_metro_a_metro
)
from generador_memoria_pdf import generar_memoria_calculo_pdf

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
                          'Longitud_Min_m', 'Longitud_Max_m', 'Longitud_Paso_m'],
            'Valor': ['ESTUDIO DE MECÁNICA DE SUELOS', 'SISTEMA DE TRANSPORTE POR CABLE', 'PERFIL ESTRATIGRÁFICO TORRE 11', 
                      'OCTUBRE 2026', 'logo_empresa.png', 
                      'N 3,539,426   E 514,589   WGS84', '48.7 m (rel. MSL)', '16.7 m (rel. MSL)', '48.7 m (rel. MSL)', '5.8', '2026-10-08',
                      '60', '100', 'CON_LINER', '18.0',
                      '1.0', '2.0', '0.2',
                      '15.0', '25.0', '1.0']
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
            if os.path.exists(logo_url):
                try: ax_logo.imshow(plt.imread(logo_url))
                except Exception: ax_logo.text(0.5, 0.5, '[ LOGO ]', ha='center', va='center', fontsize=10, color='gray')
            elif os.path.exists('logo_empresa.png'):
                try: ax_logo.imshow(plt.imread('logo_empresa.png'))
                except Exception: ax_logo.text(0.5, 0.5, '[ LOGO ]', ha='center', va='center', fontsize=10, color='gray')
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
st.caption("Generación de Perfiles Estratigráficos (ISO 710-2) y Diseño de Cimentaciones Profundas (NTC CDMX / Puebla)")

tab_perfil, tab_cimentacion = st.tabs([
    "📄 Perfil Estratigráfico ISO 710-2",
    "🏗️ Capacidad de Pilas (Compresión / Tensión)"
])

with tab_perfil:
    st.subheader("Generador de Perfil Estratigráfico")
    st.markdown("Herramienta técnica para generación de perfiles estratigráficos bajo la norma ISO 710-2.")

    st.markdown("### 1. Plantilla de Datos")
    st.info("Descarga la plantilla Excel con las columnas de resistencia y clasificación actualizadas.")
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

            # Opciones de Geometría y Restricciones de Pilas Preperforadas
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

            # Generación de listas de evaluación
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

                # ----- SECCIÓN 6: MÓDULOS DE REACCIÓN METRO A METRO -----
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
                st.dataframe(df_balasto_view, use_container_width=True, hide_index=True)

                csv_balasto = df_balasto_view.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Descargar Tabla de Balasto (D={sel_d:.2f}m, L={sel_l:.2f}m) [.CSV]",
                    data=csv_balasto,
                    file_name=f"Balasto_Metro_a_Metro_D{sel_d:.2f}_L{sel_l:.2f}.csv",
                    mime="text/csv"
                )

                # ----- GENERACIÓN Y DESCARGA DEL REPORTE PDF COMPLETO -----
                st.markdown("---")
                st.subheader("Generar Memoria de Cálculo en PDF")
                st.caption("Memoria geotécnica formal con desglose estrato por estrato, balasto metro a metro y matrices de diseño.")

                try:
                    archivo_calc.seek(0)
                    df_proy_temp = pd.read_excel(archivo_calc, sheet_name='Proyecto').set_index('Parametro')['Valor'].to_dict()
                    nm_proy = str(df_proy_temp.get('Proyecto', 'ESTUDIO GEOTÉCNICO'))
                    nm_elem = str(df_proy_temp.get('Elemento', 'DISEÑO DE CIMENTACIONES'))
                    nm_fecha = str(df_proy_temp.get('Fecha', ''))
                except Exception:
                    nm_proy, nm_elem, nm_fecha = "PROYECTO", "CIMENTACIONES", ""

                with st.spinner("Compilando memoria analítica en PDF..."):
                    pdf_memoria_bytes = generar_memoria_calculo_pdf(df_tramos, matrices, nm_proy, nm_elem, nm_fecha)

                st.download_button(
                    label="📄 Descargar Memoria de Cálculo PDF",
                    data=pdf_memoria_bytes,
                    file_name="Memoria_Capacidad_Carga.pdf",
                    mime="application/pdf",
                    type="primary"
                )
        except Exception as e:
            st.error(f"Error al analizar el sondeo: {e}")