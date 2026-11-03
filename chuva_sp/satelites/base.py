"""Funções comuns aos produtos de satélite: HTTP, cache por ano, pesos e recortes."""
from __future__ import annotations

import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import warnings

import xarray as xr

from .. import config, ugrhi

warnings.filterwarnings("ignore", category=xr.SerializationWarning)

log = logging.getLogger("chuva_sp")

_sessao: requests.Session | None = None


def sessao() -> requests.Session:
    global _sessao
    if _sessao is None:
        s = requests.Session()
        ad = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64)
        s.mount("https://", ad)
        s.headers["User-Agent"] = "chuva-sp/1.0 (pesquisa climatologica)"
        _sessao = s
    return _sessao


def baixar_bytes(url: str, tentativas: int = 5, timeout: int = 120) -> bytes | None:
    """GET com novas tentativas. Devolve None se o arquivo não existe (404/403)."""
    espera = 2.0
    for i in range(tentativas):
        try:
            r = sessao().get(url, timeout=timeout)
            if r.status_code == 200:
                return r.content
            if r.status_code in (403, 404):
                return None
            log.warning("HTTP %s em %s", r.status_code, url)
        except requests.RequestException as e:  # rede instável: tenta de novo
            log.warning("erro de rede (%s) em %s", e.__class__.__name__, url)
        time.sleep(espera)
        espera *= 2
    raise RuntimeError(f"falha ao baixar {url}")


def abrir_nc(b: bytes) -> xr.Dataset:
    return xr.open_dataset(io.BytesIO(b), engine="h5netcdf", decode_timedelta=False)


def ler_h5(b: bytes, var: str, recorte: tuple | None = None, coords: tuple[str, str] | None = None):
    """Lê uma variável NetCDF4/HDF5 direto com h5py (bem mais rápido que xarray).

    Aplica scale_factor/add_offset e troca missing_value/_FillValue/negativos por NaN.
    Se ``coords`` for dado, devolve também (lat, lon).
    """
    import h5py

    with h5py.File(io.BytesIO(b), "r") as f:
        v = f[var]
        bruto = v[recorte] if recorte is not None else v[...]
        falta = np.zeros(bruto.shape, dtype=bool)
        for att in ("missing_value", "_FillValue"):
            if att in v.attrs:
                for mv in np.atleast_1d(v.attrs[att]):
                    falta |= bruto == mv
        a = bruto.astype("float32")
        if "scale_factor" in v.attrs:
            a *= float(np.atleast_1d(v.attrs["scale_factor"])[0])
        if "add_offset" in v.attrs:
            a += float(np.atleast_1d(v.attrs["add_offset"])[0])
        a[falta | ~np.isfinite(a) | (a < 0)] = np.nan
        if coords:
            return a, f[coords[0]][:], f[coords[1]][:]
        return a


def listar_s3(bucket_url: str, prefixo: str) -> list[str]:
    """Lista chaves de um bucket S3 público (ListObjectsV2, paginado)."""
    import re

    chaves, token = [], None
    while True:
        params = {"list-type": "2", "prefix": prefixo, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        r = sessao().get(bucket_url, params=params, timeout=120)
        r.raise_for_status()
        chaves += re.findall(r"<Key>([^<]+)</Key>", r.text)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", r.text)
        if not m:
            return chaves
        token = m.group(1)


# ---------------------------------------------------------------- recortes
def indices_recorte(coord: np.ndarray, vmin: float, vmax: float) -> slice:
    """Fatia de índices de uma coordenada 1-D (crescente ou decrescente) dentro de [vmin, vmax]."""
    idx = np.where((coord >= vmin) & (coord <= vmax))[0]
    return slice(int(idx.min()), int(idx.max()) + 1)


def lon_180(lon: np.ndarray) -> np.ndarray:
    lon = np.asarray(lon, dtype=float)
    return np.where(lon > 180, lon - 360, lon)


class Grade:
    """Recorte de uma grade regular sobre SP + pesos das UGRHIs (calculados uma vez)."""

    def __init__(self, lons_global: np.ndarray, lats_global: np.ndarray, centros_offset: float = 0.0):
        lons = lon_180(np.asarray(lons_global, dtype=float) + centros_offset)
        lats = np.asarray(lats_global, dtype=float) + centros_offset
        x0, y0, x1, y1 = config.BBOX_SP
        self.sx = indices_recorte(lons, x0, x1)
        self.sy = indices_recorte(lats, y0, y1)
        self.lons = lons[self.sx]
        self.lats = lats[self.sy]
        self.W = ugrhi.pesos_grade(self.lons, self.lats)
        self.regioes = ugrhi.regioes()

    @property
    def forma(self) -> tuple[int, int]:
        return (self.lats.size, self.lons.size)

    def medias(self, cubo: np.ndarray) -> np.ndarray:
        """cubo: (n_tempos, n_lat, n_lon) -> (n_tempos, n_regioes)."""
        n = cubo.shape[0]
        return ugrhi.media_areal(cubo.reshape(n, -1), self.W)


# ---------------------------------------------------------------- cache por ano
def pasta_cache(produto: str) -> Path:
    p = config.CACHE / produto
    p.mkdir(parents=True, exist_ok=True)
    return p


def arquivo_ano(produto: str, ano: int, sufixo: str = "") -> Path:
    return pasta_cache(produto) / f"{produto}{sufixo}_{ano}.parquet"


def salvar_cubo(produto: str, ano: int, tempos, cubo: np.ndarray, grade: Grade) -> None:
    """Guarda o recorte diário (tempo x lat x lon) em NetCDF comprimido, para mapas e pontos."""
    da = xr.DataArray(
        np.round(cubo, 1).astype("float32"),
        dims=("time", "lat", "lon"),
        coords={"time": pd.DatetimeIndex(tempos).values, "lat": grade.lats, "lon": grade.lons},
        name="precip",
        attrs={"units": "mm/dia"},
    )
    enc = {"precip": {"zlib": True, "complevel": 4, "shuffle": True}}
    da.to_dataset().to_netcdf(pasta_cache(produto) / f"{produto}_grade_diaria_{ano}.nc", encoding=enc, engine="h5netcdf")


def anos_periodo(inicio_produto: str, inicio=config.DATA_INICIO, fim=config.DATA_FIM) -> list[int]:
    a0 = max(pd.Timestamp(inicio_produto).year, inicio.year)
    return list(range(a0, fim.year + 1))


def executar_em_paralelo(func, itens, workers: int = 16, desc: str = ""):
    """Executa func(item) em threads e devolve dict item->resultado (None se faltou)."""
    res = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {ex.submit(func, it): it for it in itens}
        for f in as_completed(fut):
            res[fut[f]] = f.result()
    return res


def configurar_log(nivel=logging.INFO) -> None:
    logging.basicConfig(level=nivel, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for ruidoso in ("rasterio", "rasterio.session", "botocore", "urllib3", "h5py", "icechunk"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
