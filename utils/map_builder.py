import folium
import html
import re
from collections import Counter
from utils.helpers import normalize_text

REGION_FIELDS = ("nombre", "NOMDEP", "NOMBDEP", "NOMB_REG", "DEPARTAMEN", "NAME_1")


def _feature_region(props):
    for field in REGION_FIELDS:
        value = props.get(field)
        if value:
            return str(value)
    return ""


def entity_type(name):
    value = normalize_text(name)
    if re.match(r"^(ut\b|unidad tecnica\b)", value):
        return "UT"
    if value.startswith("cite"):
        return "CITE"
    return "Sin clasificar"


def safe(value):
    text = str(value).strip()
    return "No registrado" if text.lower() in {"", "nan", "<na>", "none"} else html.escape(text)


def create_map(df_geo, geojson_data, selected_region=None, selected_cite=None):
    center = [-9.19, -75.0152]
    zoom = 5.5
    if selected_region:
        subset = df_geo[df_geo["_region_key"] == normalize_text(selected_region)]
        valid = subset.dropna(subset=["latitud", "longitud"])
        if not valid.empty:
            center = [float(valid["latitud"].mean()), float(valid["longitud"].mean())]
            zoom = 7

    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
        zoom_control=True,
        prefer_canvas=True,
        zoom_snap=0.25,
        zoom_delta=0.25,
        min_zoom=4.5,
    )
    counts = df_geo.groupby("_region_key")["_cite_key"].nunique().to_dict()
    max_count = max(counts.values(), default=0)
    def region_color(count):
        if count == 0: return "#E2E8F0"
        ratio = count / max(max_count, 1)
        if ratio <= 0.25: return "#BFDBFE"
        if ratio <= 0.50: return "#60A5FA"
        if ratio <= 0.75: return "#2563EB"
        return "#1E3A8A"
    selected_key = normalize_text(selected_region)

    if geojson_data and geojson_data.get("features"):
        def style(feature):
            key = normalize_text(_feature_region(feature.get("properties", {})))
            if selected_key and key == selected_key:
                return {"fillColor":"#2563EB","color":"#0F2C59","weight":2.6,"fillOpacity":0.58}
            if counts.get(key, 0):
                return {"fillColor":region_color(counts[key]),"color":"#FFFFFF","weight":1.1,"fillOpacity":0.55}
            return {"fillColor":"#D1D5DB","color":"#FFFFFF","weight":1.0,"fillOpacity":0.48}

        for feature in geojson_data["features"]:
            props = feature.setdefault("properties", {})
            props["_display_region"] = _feature_region(props)
            props["_display_count"] = counts.get(normalize_text(_feature_region(props)), 0)

        folium.GeoJson(
            geojson_data,
            name="Regiones",
            style_function=style,
            highlight_function=lambda _: {"weight": 2.5, "color": "#1E3A8A", "fillOpacity": 0.62},
            tooltip=folium.GeoJsonTooltip(fields=["_display_region", "_display_count"], aliases=["Región:", "CITE/UT:"]),
        ).add_to(m)

        features_to_fit = geojson_data["features"]
        if selected_key:
            selected_features = [
                f for f in features_to_fit
                if normalize_text(_feature_region(f.get("properties", {}))) == selected_key
            ]
            if selected_features:
                features_to_fit = selected_features

        lats, lons = [], []
        def collect_coords(coords):
            if not isinstance(coords, list) or not coords:
                return
            if isinstance(coords[0], (int, float)) and len(coords) >= 2:
                lons.append(float(coords[0])); lats.append(float(coords[1]))
                return
            for part in coords:
                collect_coords(part)

        for feature in features_to_fit:
            collect_coords(feature.get("geometry", {}).get("coordinates", []))
        if lats and lons and selected_key:
            m.fit_bounds(
                [[min(lats), min(lons)], [max(lats), max(lons)]],
                padding=(8, 8),
                max_zoom=8,
            )

    selected_cite_key = normalize_text(selected_cite)
    for _, row in df_geo.dropna(subset=["latitud", "longitud"]).iterrows():
        name = str(row["nombre_cite"])
        is_selected = normalize_text(name) == selected_cite_key
        kind = entity_type(name)
        direccion = safe(row.get("direccion", ""))
        cite_key = normalize_text(name)
        popup = (
            "<div style='font-family:Arial,sans-serif;font-size:13px;min-width:190px;color:#0F2C59;line-height:1.6'>"
            f"<div style='font-size:11px;color:#64748B;font-weight:bold'>{safe(kind)}</div>"
            f"<strong style='font-size:15px'>{safe(name)}</strong><hr style='margin:6px 0;border:0;border-top:1px solid #E2E8F0'>"
            f"<b>Región:</b> {safe(row.get('region_cite'))}<br>"
            f"<b>Provincia:</b> {safe(row.get('provincia_cite'))}<br>"
            f"<b>Distrito:</b> {safe(row.get('distrito_cite'))}<br>"
            f"<b>Dirección:</b> {direccion}<br>"
            "<small>Selecciona la región o busca este establecimiento para consultar sus servicios y temáticas.</small>"
            "</div>"
        )
        fill = {"CITE": "#2563EB", "UT": "#F97316", "Sin clasificar": "#64748B"}[kind]
        folium.CircleMarker(
            [float(row["latitud"]), float(row["longitud"])],
            radius=9 if is_selected else 6,
            color="#B91C1C" if is_selected else "#FFFFFF",
            fill=True,
            fill_color="#EF4444" if is_selected else fill,
            fill_opacity=0.95,
            weight=3 if is_selected else 1.5,
            tooltip=name,
            popup=folium.Popup(popup, max_width=280),
        ).add_to(m)

    legend = """<div style="position:fixed;bottom:24px;left:12px;z-index:9999;background:white;
    padding:10px 12px;border-radius:9px;box-shadow:0 2px 10px #0002;font:12px Arial;line-height:1.7">
    <b>Establecimientos</b><br><span style="color:#2563EB">●</span> CITE &nbsp;
    <span style="color:#F97316">●</span> UT &nbsp;<span style="color:#64748B">●</span> Otros<br>
    <b>Presencia por región</b><br>
    <span style="color:#E2E8F0">■</span> 0 &nbsp;
    <span style="color:#BFDBFE">■</span> Baja &nbsp;
    <span style="color:#60A5FA">■</span> Media &nbsp;
    <span style="color:#2563EB">■</span> Alta &nbsp;
    <span style="color:#1E3A8A">■</span> Máxima<br>
    <small>Escala relativa al máximo regional</small></div>"""
    m.get_root().html.add_child(folium.Element(legend))
    return m
