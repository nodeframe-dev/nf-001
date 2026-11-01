import html
import streamlit as st
from streamlit_folium import st_folium
from utils.data_loader import load_data, validate_data
from utils.helpers import normalize_text, search_entities, region_from_point
from utils.map_builder import create_map


SERVICE_ORDER = [
    "Asistencia técnica",
    "Diseño y desarrollo de productos",
    "Soporte productivo",
    "Ensayos de laboratorio",
    "Capacitación",
    "Certificación de competencias laborales",
    "Información tecnológica especializada",
    "Promoción de investigación, desarrollo y gestión de la innovación (I+D+i)",
]
SERVICE_ORDER_KEY = {normalize_text(name): i for i, name in enumerate(SERVICE_ORDER)}

st.set_page_config(page_title="Red CITE | Mapa de servicios y temáticas", page_icon="📍", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container{padding-top:2.6rem;padding-bottom:2rem;max-width:1500px}
[data-testid="stSidebar"]{display:none}
.rc-title{color:#0F2C59;font-size:2.15rem;font-weight:800;line-height:1.05;margin:0}
.rc-sub{color:#64748B;font-size:1rem;margin:.25rem 0 1rem}
.rc-card{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:14px 16px;margin-bottom:12px}
.rc-label{font-size:.76rem;color:#64748B;text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.rc-value{font-size:1.55rem;color:#0F2C59;font-weight:800;margin-top:2px}
.rc-loc{color:#64748B;font-size:.88rem;margin:-4px 0 8px}
.rc-topic{padding:7px 10px;border-left:3px solid #93C5FD;background:#F8FAFC;margin:5px 0;border-radius:0 6px 6px 0;color:#334155;font-size:.91rem}
div[data-testid="stExpander"]{border:1px solid #E2E8F0;border-radius:10px;background:white}
div[data-testid="stExpander"] details summary p{color:#0F2C59;font-weight:650}
.stButton>button{border-radius:8px}
@media(max-width:800px){.block-container{padding-left:1rem;padding-right:1rem}.rc-title{font-size:1.8rem}}
</style>
""", unsafe_allow_html=True)

for key, default in {"selected_region":None,"selected_cite":None,"search_query":"","search_selector":None,"search_version":0,"last_map_click":None}.items():
    st.session_state.setdefault(key, default)

try:
    df_geo, df_tem, geojson_data, geojson_source = load_data()
except Exception as exc:
    st.error(f"No se pudieron cargar los datos: {exc}")
    st.stop()

warnings = validate_data(df_geo, df_tem)

def reset_peru_view():
    st.session_state.selected_region = None
    st.session_state.selected_cite = None
    st.session_state.search_query = ""
    st.session_state.search_selector = None
    st.session_state.search_version += 1

search_options = []

for reg in sorted(df_geo["region_cite"].dropna().astype(str).unique(), key=normalize_text):
    search_options.append({
        "label": f"Región: {reg}",
        "type": "region",
        "value": reg,
        "region": reg,
    })

for _, row in df_geo.sort_values("nombre_cite").iterrows():
    cite_name = str(row["nombre_cite"])
    search_options.append({
        "label": f"CITE / UT: {cite_name}",
        "type": "cite",
        "value": cite_name,
        "region": row["region_cite"],
    })

search_by_label = {item["label"]: item for item in search_options}

def apply_search_selection():
    search_key = f"search_selector_{st.session_state.search_version}"
    selected_label = st.session_state.get(search_key)
    if not selected_label:
        return

    result = search_by_label.get(selected_label)
    if not result:
        return

    if result["type"] == "cite":
        st.session_state.selected_cite = result["value"]
        st.session_state.selected_region = result["region"]
    else:
        st.session_state.selected_region = result["value"]
        st.session_state.selected_cite = None

    st.session_state.search_query = ""
    st.session_state.search_selector = None

head, search = st.columns([0.64,0.36], vertical_alignment="top")
with head:
    st.markdown(
        '<div class="rc-title">Red CITE</div>'
        '<div class="rc-sub">Ubicación, servicios y principales áreas temáticas</div>',
        unsafe_allow_html=True,
    )

with search:
    st.selectbox(
        "Buscar CITE o región",
        options=[item["label"] for item in search_options],
        index=None,
        placeholder="Buscar CITE, UT o región...",
        label_visibility="collapsed",
        key=f"search_selector_{st.session_state.search_version}",
        on_change=apply_search_selection,
    )

if warnings:
    with st.expander("Observaciones de consistencia de datos", expanded=False):
        for item in warnings: st.caption(f"• {item}")

map_col, panel_col = st.columns([0.58,0.42], gap="large")

with map_col:
    selected_region = st.session_state.selected_region
    if selected_region:
        st.button("← Ver todo el Perú", on_click=reset_peru_view)

    fmap = create_map(df_geo, geojson_data, selected_region, st.session_state.selected_cite)
    map_state = st_folium(
        fmap,
        height=650,
        use_container_width=True,
        key=f"map_{normalize_text(selected_region) or 'peru'}",
        returned_objects=["last_object_clicked"],
    )

    clicked = (map_state or {}).get("last_object_clicked")
    if clicked and geojson_data:
        click_signature = (clicked.get("lat"), clicked.get("lng"))
        is_new_click = click_signature != st.session_state.get("last_map_click")
        clicked_region = region_from_point(clicked.get("lat"), clicked.get("lng"), geojson_data)

        if clicked_region and is_new_click:
            st.session_state.last_map_click = click_signature
            region_changed = (
                normalize_text(clicked_region)
                != normalize_text(st.session_state.selected_region)
            )

            st.session_state.search_selector = None
            st.session_state.search_version += 1

            if region_changed:
                st.session_state.selected_region = clicked_region
                st.session_state.selected_cite = None

            st.rerun()

    if geojson_data is None:
        st.caption("El mapa muestra los CITE/UT por coordenadas. Agrega data/peru_departamentos.geojson para visualizar los límites regionales sin depender de Internet.")

with panel_col:
    selected_region = st.session_state.selected_region
    if not selected_region:
        total_cites = df_geo["_cite_key"].nunique()
        total_regions = df_geo["_region_key"].nunique()
        st.markdown(f'<div class="rc-card"><div class="rc-label">Resumen nacional</div><div class="rc-value">{total_cites} CITE / UT</div><div class="rc-loc">Presencia registrada en {total_regions} regiones</div></div>', unsafe_allow_html=True)
        st.info("Selecciona una región para explorar sus CITE/UT, tipos de servicio y principales temáticas.")
        st.markdown("#### Regiones con CITE / UT")
        cols = st.columns(2)
        counts = df_geo.groupby("region_cite")["_cite_key"].nunique().sort_index()
        for i, (reg, count) in enumerate(counts.items()):
            if cols[i%2].button(f"{reg.title()} · {count}", key=f"reg_{i}", use_container_width=True):
                st.session_state.selected_region = reg
                st.session_state.selected_cite = None
                st.rerun()
    else:
        reg_key = normalize_text(selected_region)
        df_reg = df_geo[df_geo["_region_key"] == reg_key].copy()
        st.markdown(f'<div class="rc-card"><div class="rc-label">Región seleccionada</div><div class="rc-value">{html.escape(str(selected_region).title())}</div><div class="rc-loc">{df_reg["_cite_key"].nunique()} CITE / UT en esta región</div></div>', unsafe_allow_html=True)

        for _, cite_row in df_reg.sort_values("nombre_cite").iterrows():
            cite_name = str(cite_row["nombre_cite"])
            cite_key = normalize_text(cite_name)
            expanded = cite_key == normalize_text(st.session_state.selected_cite)
            with st.expander(cite_name, expanded=expanded):
                loc = " · ".join([str(cite_row["distrito_cite"]), str(cite_row["provincia_cite"]), str(cite_row["region_cite"])])
                st.markdown(f'<div class="rc-loc">{html.escape(loc.title())}</div>', unsafe_allow_html=True)
                direccion = str(cite_row.get("direccion", "")).strip()
                if direccion and direccion.lower() not in {"nan", "<na>"}:
                    st.caption(f"Dirección: {direccion}")
                if st.button("Enfocar en el mapa", key=f"focus_{cite_key}"):
                    st.session_state.selected_cite = cite_name
                    st.rerun()

                cite_services = df_tem[df_tem["_cite_key"] == cite_key].copy()
                if cite_services.empty:
                    st.caption("Sin servicios o áreas temáticas registradas.")
                    continue

                service_order = cite_services["TIPO DE SERVICIO"].dropna().drop_duplicates().tolist()
                service_order = sorted(
                    service_order,
                    key=lambda name: (SERVICE_ORDER_KEY.get(normalize_text(name), 999), normalize_text(name)),
                )
                for service in service_order:
                    topics = cite_services[cite_services["TIPO DE SERVICIO"] == service].sort_values("N.°", na_position="last")
                    # Sin iconos por tipo de servicio: se reservan para una etapa gráfica posterior.
                    with st.expander(str(service), expanded=False):
                        for _, topic in topics.iterrows():
                            n = topic.get("N.°")
                            prefix = f"{int(n)}. " if n == n else ""
                            text = html.escape(str(topic["TEMÁTICA AGRUPADA"]))
                            st.markdown(f'<div class="rc-topic"><b>{prefix}</b>{text}</div>', unsafe_allow_html=True)

st.caption("Fuente temática: consolidado 2025–setiembre 2026. Ubicación: maestro de localización CITE/UT.")
