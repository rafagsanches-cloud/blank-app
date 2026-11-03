"""Limites das 22 UGRHIs de São Paulo e pesos de área para médias areais em grades."""
from __future__ import annotations

import csv
import sys
import zipfile
from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import wkt as swkt

from . import config


def _corrigir_texto(s: str) -> str:
    """O CSV do SIBH vem com UTF-8 codificado duas vezes ('TietÃª' -> 'Tietê')."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def ler_ugrhi_csv(caminho=config.UGRHI_CSV) -> gpd.GeoDataFrame:
    """Lê o CSV exportado do GeoServer do SIBH (geometria WKT com eixos lat/lon trocados)."""
    csv.field_size_limit(sys.maxsize)
    linhas = []
    with open(caminho, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            geom = swkt.loads(r["the_geom"])
            # O WKT está como (lat lon); o padrão é (lon lat)
            geom = shapely.transform(geom, lambda c: c[:, ::-1])
            geom = shapely.make_valid(geom)
            linhas.append(
                {
                    "codigo": int(r["codigo"]),
                    "sigla": f"UGRHI{int(r['codigo']):02d}",
                    "nome": _corrigir_texto(r["nome"]).replace("/ ", "/").replace("Jundaí", "Jundiaí"),
                    "fonte": r["fonte"],
                    "geometry": geom,
                }
            )
    gdf = gpd.GeoDataFrame(linhas, geometry="geometry", crs="EPSG:4326").sort_values("codigo")
    gdf["area_km2"] = gdf.to_crs("EPSG:5880").area / 1e6  # SIRGAS 2000 / Brazil Polyconic
    return gdf.reset_index(drop=True)


def exportar_ugrhi(gdf: gpd.GeoDataFrame | None = None) -> dict:
    """Grava GeoPackage, GeoJSON e shapefile (zipado) em dados/ugrhi."""
    config.garantir_pastas()
    gdf = ler_ugrhi_csv() if gdf is None else gdf
    out = {}
    out["csv"] = config.UGRHI_DIR / "ugrhi_sp.csv"
    gdf.drop(columns="geometry").to_csv(out["csv"], index=False)
    out["gpkg"] = config.UGRHI_GPKG
    gdf.to_file(out["gpkg"], layer="ugrhi_sp", driver="GPKG")
    # GeoJSON simplificada (~100 m) para mapas leves no aplicativo
    out["geojson"] = config.UGRHI_DIR / "UGRHI_SP_simplificado.geojson"
    simp = gdf.copy()
    simp["geometry"] = simp.geometry.simplify(0.001, preserve_topology=True)
    # anel externo no sentido horário: exigência do d3-geo/Plotly para preencher o polígono certo
    simp["geometry"] = shapely.orient_polygons(simp.geometry.values, exterior_cw=True)
    simp.to_file(out["geojson"], driver="GeoJSON", COORDINATE_PRECISION=4)
    shp_dir = config.CACHE / "shp_ugrhi"
    shp_dir.mkdir(parents=True, exist_ok=True)
    gdf.to_file(shp_dir / "UGRHI_SP.shp", encoding="utf-8")
    out["shp_zip"] = config.UGRHI_DIR / "UGRHI_SP_shapefile.zip"
    with zipfile.ZipFile(out["shp_zip"], "w", zipfile.ZIP_DEFLATED) as z:
        for ext in ("shp", "shx", "dbf", "prj", "cpg"):
            p = shp_dir / f"UGRHI_SP.{ext}"
            if p.exists():
                z.write(p, p.name)
    return out


@lru_cache(maxsize=1)
def carregar_ugrhi() -> gpd.GeoDataFrame:
    if config.UGRHI_GPKG.exists():
        return gpd.read_file(config.UGRHI_GPKG)
    gdf = ler_ugrhi_csv()
    exportar_ugrhi(gdf)
    return gdf


def regioes() -> list[str]:
    """Rótulos das colunas de saída: UGRHI01..UGRHI22 e SP (estado inteiro)."""
    return list(carregar_ugrhi()["sigla"]) + ["SP"]


def nomes_regioes() -> dict[str, str]:
    g = carregar_ugrhi()
    d = {r.sigla: f"{r.codigo:02d} - {r.nome}" for r in g.itertuples()}
    d["SP"] = "Estado de São Paulo"
    return d


def pesos_grade(lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Matriz de pesos (n_regioes x n_celulas) para uma grade regular lat/lon.

    Peso = fração da célula dentro do polígono x cos(lat) (área real da célula).
    A ordem das células é a de ``np.meshgrid(lons, lats)`` achatada (linhas = lat).
    """
    g = carregar_ugrhi()
    lons = np.asarray(lons, dtype=float)
    lats = np.asarray(lats, dtype=float)
    dx = float(np.median(np.abs(np.diff(lons)))) if lons.size > 1 else 1.0
    dy = float(np.median(np.abs(np.diff(lats)))) if lats.size > 1 else 1.0
    LON, LAT = np.meshgrid(lons, lats)
    cx, cy = LON.ravel(), LAT.ravel()
    celulas = shapely.box(cx - dx / 2, cy - dy / 2, cx + dx / 2, cy + dy / 2)
    area_cel = dx * dy
    W = np.zeros((len(g) + 1, cx.size), dtype=float)
    arvore = shapely.STRtree(celulas)
    for i, geom in enumerate(g.geometry):
        shapely.prepare(geom)
        idx = arvore.query(geom, predicate="intersects")
        if idx.size == 0:
            continue
        frac = shapely.area(shapely.intersection(celulas[idx], geom)) / area_cel
        W[i, idx] = frac * np.cos(np.deg2rad(cy[idx]))
    W[-1] = W[:-1].sum(axis=0)  # estado = soma das UGRHIs
    # Para grades muito grossas (ex.: GPCP 2,5°) nenhuma célula fica vazia; ok.
    return W


def media_areal(X: np.ndarray, W: np.ndarray, cobertura_min: float = 0.5) -> np.ndarray:
    """Média ponderada por região.

    X: (n_tempos, n_celulas) com NaN para falhas. Retorna (n_tempos, n_regioes).
    Se a fração de área válida < cobertura_min, devolve NaN.
    """
    X = np.asarray(X, dtype=np.float64)
    valido = np.isfinite(X)
    Xf = np.where(valido, X, 0.0)
    soma = Xf @ W.T
    peso_valido = valido.astype(np.float64) @ W.T
    peso_total = W.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = soma / peso_valido
    m[peso_valido < cobertura_min * peso_total[None, :]] = np.nan
    return m


def ponto_em_ugrhi(lon: np.ndarray, lat: np.ndarray) -> list[str | None]:
    """Sigla da UGRHI que contém cada ponto (None se fora de SP)."""
    g = carregar_ugrhi()
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")
    j = gpd.sjoin(pts, g[["sigla", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return [None if pd.isna(s) else s for s in j["sigla"]]


if __name__ == "__main__":
    gdf = ler_ugrhi_csv()
    print(gdf.drop(columns="geometry").to_string())
    print("Área total (km²):", round(gdf.area_km2.sum()))
    print(exportar_ugrhi(gdf))
