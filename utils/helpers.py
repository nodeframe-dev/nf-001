import re
import unicodedata


def remove_accents(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def normalize_text(value) -> str:
    if value is None:
        return ""
    text = remove_accents(str(value)).lower().strip()
    return re.sub(r"\s+", " ", text)


def search_entities(query, df_geo):
    """Devuelve todas las coincidencias de CITE/UT y regiones para una búsqueda parcial."""
    q = normalize_text(query)
    if not q or df_geo.empty:
        return []

    results = []
    seen = set()

    # CITE/UT: coincidencias exactas primero y luego parciales.
    for _, row in df_geo.iterrows():
        name = str(row.get("nombre_cite", ""))
        key = normalize_text(name)
        if q in key:
            item_key = ("cite", key)
            if item_key not in seen:
                results.append({
                    "type": "cite",
                    "label": name,
                    "value": name,
                    "region": row.get("region_cite"),
                    "exact": key == q,
                })
                seen.add(item_key)

    # Regiones.
    for region in df_geo["region_cite"].dropna().astype(str).unique():
        key = normalize_text(region)
        if q in key:
            item_key = ("region", key)
            if item_key not in seen:
                results.append({
                    "type": "region",
                    "label": region,
                    "value": region,
                    "region": region,
                    "exact": key == q,
                })
                seen.add(item_key)

    return sorted(results, key=lambda x: (not x["exact"], x["type"] != "region", normalize_text(x["label"])))


def region_from_point(lat, lng, geojson_data):
    """Devuelve el nombre de la región cuyo polígono contiene el punto clicado."""
    if not geojson_data or lat is None or lng is None:
        return None
    try:
        from shapely.geometry import Point, shape
        point = Point(float(lng), float(lat))
        fields = ("nombre", "NOMDEP", "NOMBDEP", "NOMB_REG", "DEPARTAMEN", "NAME_1")
        for feature in geojson_data.get("features", []):
            geometry = feature.get("geometry")
            if not geometry:
                continue
            polygon = shape(geometry)
            if polygon.contains(point) or polygon.touches(point):
                props = feature.get("properties", {})
                for field in fields:
                    value = props.get(field)
                    if value:
                        return str(value)
    except Exception:
        return None
    return None
