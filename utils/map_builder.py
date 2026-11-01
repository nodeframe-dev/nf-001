import folium
from utils.helpers import normalize_text

REGION_FIELDS = ("nombre", "NOMDEP", "NOMBDEP", "NOMB_REG", "DEPARTAMEN", "NAME_1")


def _feature_region(props):
    for field in REGION_FIELDS:
        value = props.get(field)
        if value:
            return str(value)
    return ""


def create_map(df_geo, geojson_data, selected_region=None, selected_cite=None):
    center = [-9.19, -75.0152]
    # Vista nacional ajustada para que el Perú aproveche mejor el alto del mapa.
    # Leaflet admite zoom fraccionario mediante zoomSnap.
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
    regions_with_cite = set(df_geo["_region_key"].dropna())
    selected_key = normalize_text(selected_region)

    if geojson_data and geojson_data.get("features"):
        def style(feature):
            key = normalize_text(_feature_region(feature.get("properties", {})))
            if selected_key and key == selected_key:
                return {"fillColor":"#2563EB","color":"#0F2C59","weight":2.6,"fillOpacity":0.58}
            if key in regions_with_cite:
                return {"fillColor":"#60A5FA","color":"#FFFFFF","weight":1.1,"fillOpacity":0.50}
            return {"fillColor":"#D1D5DB","color":"#FFFFFF","weight":1.0,"fillOpacity":0.48}

        # El tooltip se construye sin depender de un nombre de campo específico.
        for feature in geojson_data["features"]:
            feature.setdefault("properties", {})["_display_region"] = _feature_region(feature.get("properties", {}))

        folium.GeoJson(
            geojson_data,
            name="Regiones",
            style_function=style,
            highlight_function=lambda _: {"weight": 2.5, "color": "#1E3A8A", "fillOpacity": 0.62},
            tooltip=folium.GeoJsonTooltip(fields=["_display_region"], aliases=["Región:"]),
        ).add_to(m)

        # Ajusta el encuadre a la geometría real del Perú (o a la región seleccionada),
        # evitando mostrar grandes extensiones de países vecinos.
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
            # Para una región sí usamos sus límites reales. En la vista nacional
            # conservamos el zoom 5.75 para que el Perú llene mejor el alto del
            # visor y no quede rodeado por demasiado territorio vecino.
            m.fit_bounds(
                [[min(lats), min(lons)], [max(lats), max(lons)]],
                padding=(8, 8),
                max_zoom=8,
            )

    selected_cite_key = normalize_text(selected_cite)
    for _, row in df_geo.dropna(subset=["latitud", "longitud"]).iterrows():
        name = str(row["nombre_cite"])
        is_selected = normalize_text(name) == selected_cite_key
        direccion = row.get("direccion", "")
        direccion = "" if direccion is None else str(direccion).strip()
        direccion_html = "" if direccion.lower() in {"", "nan", "<na>"} else f"<br><b>Dirección:</b> {direccion}"
        popup = (
            f"<div style='font-family:Arial;font-size:13px;color:#0F2C59'>"
            f"<b>{name}</b><br><b>Región:</b> {row['region_cite']}<br>"
            f"<b>Provincia:</b> {row['provincia_cite']}<br><b>Distrito:</b> {row['distrito_cite']}"
            f"{direccion_html}</div>"
        )
        folium.CircleMarker(
            [float(row["latitud"]), float(row["longitud"])],
            radius=9 if is_selected else 6,
            color="#B91C1C" if is_selected else "#FFFFFF",
            fill=True,
            fill_color="#EF4444" if is_selected else "#EF3340",
            fill_opacity=0.95,
            weight=3 if is_selected else 1.5,
            tooltip=name,
            popup=folium.Popup(popup, max_width=280),
        ).add_to(m)

    return m
