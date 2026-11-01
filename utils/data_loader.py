import json
from pathlib import Path
import pandas as pd
import streamlit as st
from utils.helpers import normalize_text

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GEOJSON_URL = "https://raw.githubusercontent.com/Rodasluis/Peru-maps/main/salida/departamento_simplificado.geojson"

REQUIRED_GEO = {"nombre_cite", "latitud", "longitud", "region_cite", "provincia_cite", "distrito_cite", "direccion"}
REQUIRED_TEM = {"CITE", "TIPO DE SERVICIO", "N.°", "TEMÁTICA AGRUPADA"}

@st.cache_data(show_spinner=False)
def load_data():
    loc_file = DATA_DIR / "localizacion_cite.xlsx"
    tem_file = DATA_DIR / "tematicas_cite.xlsx"

    if not loc_file.exists():
        raise FileNotFoundError(f"No se encontró {loc_file.name} en data/.")
    if not tem_file.exists():
        raise FileNotFoundError(f"No se encontró {tem_file.name} en data/.")

    df_geo = pd.read_excel(loc_file)
    df_tem = pd.read_excel(tem_file)

    missing_geo = REQUIRED_GEO - set(df_geo.columns)
    missing_tem = REQUIRED_TEM - set(df_tem.columns)
    if missing_geo:
        raise ValueError(f"Faltan columnas en localizacion_cite.xlsx: {sorted(missing_geo)}")
    if missing_tem:
        raise ValueError(f"Faltan columnas en tematicas_cite.xlsx: {sorted(missing_tem)}")

    for col in ["nombre_cite", "region_cite", "provincia_cite", "distrito_cite", "direccion"]:
        df_geo[col] = df_geo[col].astype("string").str.strip()
    for col in ["CITE", "TIPO DE SERVICIO", "TEMÁTICA AGRUPADA"]:
        df_tem[col] = df_tem[col].astype("string").str.strip()

    df_geo["latitud"] = pd.to_numeric(df_geo["latitud"], errors="coerce")
    df_geo["longitud"] = pd.to_numeric(df_geo["longitud"], errors="coerce")
    df_tem["N.°"] = pd.to_numeric(df_tem["N.°"], errors="coerce")

    df_geo["_cite_key"] = df_geo["nombre_cite"].map(normalize_text)
    df_geo["_region_key"] = df_geo["region_cite"].map(normalize_text)
    df_tem["_cite_key"] = df_tem["CITE"].map(normalize_text)

    # La cartografía departamental se consume directamente desde GitHub RAW.
    # El resultado queda cacheado junto con el resto de los datos por @st.cache_data.
    geojson_data = None
    geojson_source = None
    try:
        import urllib.request
        request = urllib.request.Request(
            GEOJSON_URL,
            headers={"User-Agent": "Mapa-Tematicas-Red-CITE/1.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            geojson_data = json.loads(response.read().decode("utf-8"))
        geojson_source = "GitHub RAW"
    except Exception:
        # La app puede seguir mostrando los CITE/UT mediante sus coordenadas,
        # aunque la capa de polígonos regionales no esté disponible.
        geojson_data = None
        geojson_source = None

    return df_geo, df_tem, geojson_data, geojson_source


def validate_data(df_geo, df_tem):
    warnings = []
    geo_keys = set(df_geo["_cite_key"].dropna())
    tem_keys = set(df_tem["_cite_key"].dropna())
    if geo_keys - tem_keys:
        warnings.append(f"{len(geo_keys-tem_keys)} CITE/UT de localización no tienen temáticas asociadas.")
    if tem_keys - geo_keys:
        warnings.append(f"{len(tem_keys-geo_keys)} CITE/UT de temáticas no tienen coincidencia geográfica.")
    n_null = int(df_geo[["latitud", "longitud"]].isna().any(axis=1).sum())
    if n_null:
        warnings.append(f"{n_null} CITE/UT no tienen coordenadas válidas.")
    return warnings
