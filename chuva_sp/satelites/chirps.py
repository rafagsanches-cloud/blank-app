"""CHIRPS v3.0 RNL diário (0,05°, 1981–presente) a partir de COGs públicos no S3 (Source Cooperative).

Lê apenas os blocos do GeoTIFF que cobrem SP (leitura parcial via HTTP), sem baixar o arquivo global.
"""
from __future__ import annotations

import datetime as dt
import logging
import os

import numpy as np
import pandas as pd

from .. import config
from . import base

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "6")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")

import rasterio  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

log = logging.getLogger("chuva_sp")
PRODUTO = "CHIRPS"
URL = (
    "https://s3.eu-central-1.amazonaws.com/eu-central-1.opendata.source.coop/"
    "wfp/chirps-rnl-daily/v3.0/{d:%Y}/{d:%m}/{d:%d}/chirps-v3.0.rnl.{d:%Y}.{d:%m}.{d:%d}.tif"
)

_grade: base.Grade | None = None
_janela = None


def _preparar_grade():
    global _grade, _janela
    if _grade is not None:
        return
    with rasterio.open(URL.format(d=dt.date(2000, 1, 1))) as r:
        tr = r.transform
        w = from_bounds(*config.BBOX_SP, transform=tr).round_offsets().round_lengths()
        col0, row0 = int(w.col_off), int(w.row_off)
        lons = tr.c + tr.a * (np.arange(r.width) + 0.5)
        lats = tr.f + tr.e * (np.arange(r.height) + 0.5)
    g = base.Grade.__new__(base.Grade)
    g.sx = slice(col0, col0 + int(w.width))
    g.sy = slice(row0, row0 + int(w.height))
    g.lons, g.lats = lons[g.sx], lats[g.sy]
    from .. import ugrhi

    g.W = ugrhi.pesos_grade(g.lons, g.lats)
    g.regioes = ugrhi.regioes()
    _grade, _janela = g, w


def _ler_dia(d: dt.date):
    url = URL.format(d=d)
    for tentativa in range(4):
        try:
            with rasterio.Env(GDAL_HTTP_TIMEOUT=60):
                with rasterio.open(url) as r:
                    a = r.read(1, window=_janela).astype("float32")
            a[a < 0] = np.nan
            return a
        except rasterio.errors.RasterioIOError as e:
            msg = str(e)
            if "404" in msg or "does not exist" in msg or "No such file" in msg:
                return None
            log.warning("CHIRPS %s: %s (tentativa %d)", d, msg[:120], tentativa + 1)
    return None


def processar_ano(ano: int, workers: int = 16, refazer: bool = False) -> pd.DataFrame | None:
    arq = base.arquivo_ano(PRODUTO, ano)
    if arq.exists() and not refazer:
        return pd.read_parquet(arq)
    _preparar_grade()
    fim = min(dt.date(ano, 12, 31), config.DATA_FIM)
    dias = list(pd.date_range(dt.date(ano, 1, 1), fim, freq="D").date)
    res = base.executar_em_paralelo(_ler_dia, dias, workers=workers)
    ok = [d for d in dias if res.get(d) is not None]
    if not ok:
        return None
    cubo = np.stack([res[d] for d in ok])
    df = pd.DataFrame(_grade.medias(cubo), index=pd.DatetimeIndex(ok, name="data"), columns=_grade.regioes)
    df = df.reindex(pd.date_range(dt.date(ano, 1, 1), ok[-1], freq="D", name="data"))
    base.salvar_cubo(PRODUTO, ano, ok, cubo, _grade)
    # o ano corrente fica incompleto: não grava no cache definitivo
    if ano < config.DATA_FIM.year:
        df.to_parquet(arq)
    log.info("CHIRPS %d: %d dias", ano, len(ok))
    return df


def baixar(inicio=config.DATA_INICIO, fim=config.DATA_FIM, workers: int = 16) -> pd.DataFrame:
    """Série diária (mm/dia) por UGRHI e estado. Índice = data (dia UTC)."""
    partes = [processar_ano(a, workers) for a in base.anos_periodo(config.PRODUTOS[PRODUTO]["inicio"], inicio, fim)]
    return pd.concat([p for p in partes if p is not None]).sort_index()
