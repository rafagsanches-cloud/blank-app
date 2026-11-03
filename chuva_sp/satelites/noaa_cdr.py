"""Produtos NOAA CDR no S3 público (NOAA Open Data Dissemination):

* PERSIANN-CDR diário, 0,25°, 1983–presente
* CMORPH CDR horário, 0,25°, 1998–presente
* GPCP v2.3 mensal (2,5°, 1979–) e GPCP v1.3 diário (1°, 1996–)
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import numpy as np
import pandas as pd

from .. import config
from . import base

log = logging.getLogger("chuva_sp")

S3 = {
    "PERSIANN": "https://noaa-cdr-precip-persiann-pds.s3.amazonaws.com",
    "CMORPH": "https://noaa-cdr-precip-cmorph-pds.s3.amazonaws.com",
    "GPCP_D": "https://noaa-cdr-precip-gpcp-daily-pds.s3.amazonaws.com",
    "GPCP_M": "https://noaa-cdr-precip-gpcp-monthly-pds.s3.amazonaws.com",
}

_grades: dict[str, base.Grade] = {}


def _grade(chave: str, lons, lats, offset: float = 0.0) -> base.Grade:
    if chave not in _grades:
        _grades[chave] = base.Grade(lons, lats, offset)
    return _grades[chave]


def _data_da_chave(k: str, padrao: str, fmt: str):
    m = re.search(padrao, k)
    return dt.datetime.strptime(m.group(1), fmt) if m else None


# ============================================================ PERSIANN-CDR
def _persiann_ler(url: str):
    b = base.baixar_bytes(url)
    if b is None:
        return None
    if "PERSIANN" not in _grades:
        _, lat, lon = base.ler_h5(b, "precipitation", (0,), coords=("lat", "lon"))
        _grade("PERSIANN", lon, lat)
    g = _grades["PERSIANN"]
    return base.ler_h5(b, "precipitation", (0, g.sx, g.sy)).T  # (lon, lat) -> (lat, lon)


def persiann_ano(ano: int, workers: int = 16, refazer: bool = False) -> pd.DataFrame | None:
    arq = base.arquivo_ano("PERSIANN", ano)
    if arq.exists() and not refazer:
        return pd.read_parquet(arq)
    chaves = [k for k in base.listar_s3(S3["PERSIANN"], f"data/{ano}/") if k.endswith(".nc")]
    if not chaves:
        return None
    datas = {k: _data_da_chave(k, r"_(\d{8})_c", "%Y%m%d") for k in chaves}
    # garante a grade antes das threads
    _persiann_ler(f"{S3['PERSIANN']}/{chaves[0]}")
    res = base.executar_em_paralelo(lambda k: _persiann_ler(f"{S3['PERSIANN']}/{k}"), chaves, workers)
    ok = sorted([k for k in chaves if res[k] is not None], key=lambda k: datas[k])
    cubo = np.stack([res[k] for k in ok])
    g = _grades["PERSIANN"]
    idx = pd.DatetimeIndex([datas[k] for k in ok], name="data")
    df = pd.DataFrame(g.medias(cubo), index=idx, columns=g.regioes)
    base.salvar_cubo("PERSIANN", ano, idx, cubo, g)
    if ano < config.DATA_FIM.year:
        df.to_parquet(arq)
    log.info("PERSIANN %d: %d dias", ano, len(ok))
    return df


def persiann(inicio=config.DATA_INICIO, fim=config.DATA_FIM, workers: int = 16) -> pd.DataFrame:
    anos = base.anos_periodo(config.PRODUTOS["PERSIANN"]["inicio"], inicio, fim)
    partes = [persiann_ano(a, workers) for a in anos]
    return pd.concat([p for p in partes if p is not None]).sort_index()


# ============================================================ CMORPH (horário 0,25°)
def _cmorph_ler(url: str):
    b = base.baixar_bytes(url)
    if b is None:
        return None
    if "CMORPH" not in _grades:
        _, lat, lon = base.ler_h5(b, "cmorph", (0,), coords=("lat", "lon"))
        _grade("CMORPH", lon, lat)
    g = _grades["CMORPH"]
    return base.ler_h5(b, "cmorph", (0, g.sy, g.sx))  # mm acumulados na hora


def cmorph_mes(ano: int, mes: int, workers: int = 24, refazer: bool = False) -> pd.DataFrame | None:
    """Série horária (mm/h) de um mês. Índice = início da hora (UTC)."""
    arq = base.pasta_cache("CMORPH") / f"CMORPH_horario_{ano}{mes:02d}.parquet"
    if arq.exists() and not refazer:
        return pd.read_parquet(arq)
    chaves = [k for k in base.listar_s3(S3["CMORPH"], f"data/hourly/0.25deg/{ano}/{mes:02d}/") if k.endswith(".nc")]
    if not chaves:
        return None
    horas = {k: _data_da_chave(k, r"HLY_(\d{10})\.nc", "%Y%m%d%H") for k in chaves}
    _cmorph_ler(f"{S3['CMORPH']}/{chaves[0]}")
    res = base.executar_em_paralelo(lambda k: _cmorph_ler(f"{S3['CMORPH']}/{k}"), chaves, workers)
    ok = sorted([k for k in chaves if res[k] is not None], key=lambda k: horas[k])
    cubo = np.stack([res[k] for k in ok])
    g = _grades["CMORPH"]
    idx = pd.DatetimeIndex([horas[k] for k in ok], name="data_hora_utc")
    df = pd.DataFrame(g.medias(cubo), index=idx, columns=g.regioes).astype("float32")
    # grade diária (dia UTC completo = 24 h) para mapas/pontos
    dias = pd.Series(range(len(idx)), index=idx).groupby(idx.normalize())
    completos = [(d, v.values) for d, v in dias if len(v) == 24]
    if completos:
        cub_d = np.stack([np.nansum(cubo[ii], axis=0) * np.where(np.isnan(cubo[ii]).all(0), np.nan, 1) for _, ii in completos])
        base.salvar_cubo("CMORPH", f"{ano}{mes:02d}", [d for d, _ in completos], cub_d, g)
    hoje = config.DATA_FIM
    if (ano, mes) < (hoje.year, hoje.month):
        df.to_parquet(arq)
    log.info("CMORPH %d-%02d: %d horas", ano, mes, len(ok))
    return df


def cmorph(inicio=config.DATA_INICIO, fim=config.DATA_FIM, workers: int = 24) -> pd.DataFrame:
    partes = []
    for ano in base.anos_periodo(config.PRODUTOS["CMORPH"]["inicio"], inicio, fim):
        for mes in range(1, 13):
            if dt.date(ano, mes, 1) > fim:
                break
            p = cmorph_mes(ano, mes, workers)
            if p is not None:
                partes.append(p)
    return pd.concat(partes).sort_index()


# ============================================================ GPCP
def _gpcp_ler(url: str, chave_grade: str):
    b = base.baixar_bytes(url)
    if b is None:
        return None
    if chave_grade not in _grades:
        _, lat, lon = base.ler_h5(b, "precip", (0,), coords=("latitude", "longitude"))
        # o diário (1°) traz a borda inferior/esquerda da célula; o mensal (2,5°) traz o centro
        _grade(chave_grade, lon, lat, 0.5 if chave_grade == "GPCP_D" else 0.0)
    g = _grades[chave_grade]
    return base.ler_h5(b, "precip", (0, g.sy, g.sx))  # mm/dia


def gpcp_mensal(inicio=config.DATA_INICIO, fim=config.DATA_FIM, workers: int = 16) -> pd.DataFrame:
    """Total mensal (mm/mês) por UGRHI. GPCP v2.3 – 2,5°."""
    arq = base.pasta_cache("GPCP") / "GPCP_mensal.parquet"
    chaves = []
    for ano in range(max(1979, inicio.year), fim.year + 1):
        chaves += [k for k in base.listar_s3(S3["GPCP_M"], f"data/{ano}/") if k.endswith(".nc")]
    meses = {k: _data_da_chave(k, r"_d(\d{6})_c", "%Y%m") for k in chaves}
    _gpcp_ler(f"{S3['GPCP_M']}/{chaves[0]}", "GPCP_M")
    res = base.executar_em_paralelo(lambda k: _gpcp_ler(f"{S3['GPCP_M']}/{k}", "GPCP_M"), chaves, workers)
    ok = sorted([k for k in chaves if res[k] is not None], key=lambda k: meses[k])
    cubo = np.stack([res[k] for k in ok])
    g = _grades["GPCP_M"]
    idx = pd.DatetimeIndex([meses[k] for k in ok], name="mes")
    df = pd.DataFrame(g.medias(cubo), index=idx, columns=g.regioes)
    df = df.mul(idx.days_in_month, axis=0)  # mm/dia -> mm/mês
    df.to_parquet(arq)
    log.info("GPCP mensal: %d meses", len(df))
    return df


def gpcp_diario_ano(ano: int, workers: int = 16, refazer: bool = False) -> pd.DataFrame | None:
    arq = base.arquivo_ano("GPCP", ano, "_diario")
    if arq.exists() and not refazer:
        return pd.read_parquet(arq)
    chaves = [k for k in base.listar_s3(S3["GPCP_D"], f"data/{ano}/") if k.endswith(".nc")]
    if not chaves:
        return None
    datas = {k: _data_da_chave(k, r"_d(\d{8})_c", "%Y%m%d") for k in chaves}
    _gpcp_ler(f"{S3['GPCP_D']}/{chaves[0]}", "GPCP_D")
    res = base.executar_em_paralelo(lambda k: _gpcp_ler(f"{S3['GPCP_D']}/{k}", "GPCP_D"), chaves, workers)
    ok = sorted([k for k in chaves if res[k] is not None], key=lambda k: datas[k])
    cubo = np.stack([res[k] for k in ok])
    g = _grades["GPCP_D"]
    idx = pd.DatetimeIndex([datas[k] for k in ok], name="data")
    df = pd.DataFrame(g.medias(cubo), index=idx, columns=g.regioes)
    if ano < config.DATA_FIM.year:
        df.to_parquet(arq)
    log.info("GPCP diário %d: %d dias", ano, len(ok))
    return df


def gpcp_diario(inicio=config.DATA_INICIO, fim=config.DATA_FIM, workers: int = 16) -> pd.DataFrame:
    partes = [gpcp_diario_ano(a, workers) for a in range(max(1996, inicio.year), fim.year + 1)]
    return pd.concat([p for p in partes if p is not None]).sort_index()
