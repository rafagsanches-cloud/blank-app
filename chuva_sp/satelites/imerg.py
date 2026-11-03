"""GPM IMERG v07 Late Run (0,1°, meia-hora, 1998–presente) via Icechunk/Zarr público da dynamical.org.

O repositório fica no S3 (us-west-2) sem autenticação; os blocos são de 30 dias x 10° x 10°,
então para SP lemos ~4 blocos espaciais por mês, sem baixar o globo inteiro.

Observação: o produto 'Final' (com ajuste mensal por pluviômetros GPCC) exige login no
NASA Earthdata. A versão 'Late' (~14 h de latência) é a disponível em acesso aberto aqui.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .. import config
from . import base

log = logging.getLogger("chuva_sp")
PRODUTO = "IMERG"
BUCKET = "dynamical-nasa-imerg"
PREFIXO = "nasa-imerg-analysis-late/v0.1.0.icechunk"
PASSO_S = 1800  # meia hora

_estado: dict = {}


def _abrir():
    if _estado:
        return _estado
    import icechunk
    import zarr

    st = icechunk.s3_storage(bucket=BUCKET, prefix=PREFIXO, region="us-west-2", anonymous=True)
    repo = icechunk.Repository.open(st)
    sessao = repo.readonly_session("main")
    raiz = zarr.open_group(sessao.store, mode="r")
    tempo = pd.to_datetime(raiz["time"][:], unit="s") if raiz["time"].dtype.kind in "iu" else pd.DatetimeIndex(raiz["time"][:])
    lat = raiz["latitude"][:]
    lon = raiz["longitude"][:]
    g = base.Grade(lon, lat)
    _estado.update(raiz=raiz, tempo=tempo, grade=g, var=raiz["precipitation_surface"])
    return _estado


def _tempo_icechunk() -> pd.DatetimeIndex:
    """Lê o eixo de tempo respeitando units/calendar do Zarr via xarray (uma vez)."""
    import icechunk
    import xarray as xr

    st = icechunk.s3_storage(bucket=BUCKET, prefix=PREFIXO, region="us-west-2", anonymous=True)
    s = icechunk.Repository.open(st).readonly_session("main")
    ds = xr.open_zarr(s.store, consolidated=False, chunks=None)
    return pd.DatetimeIndex(ds.time.values)


def processar_bloco(i0: int, refazer: bool = False) -> pd.DataFrame | None:
    """Processa um bloco de 1440 meias-horas (30 dias) começando no índice i0."""
    e = _abrir()
    t = e["tempo"]
    t0 = t[i0]
    arq = base.pasta_cache(PRODUTO) / f"IMERG_horario_{t0:%Y%m%d}.parquet"
    if arq.exists() and not refazer:
        return pd.read_parquet(arq)
    i1 = min(i0 + 1440, len(t))
    g: base.Grade = e["grade"]
    bruto = np.asarray(e["var"][i0:i1, g.sy, g.sx], dtype="float32") * PASSO_S  # mm por meia hora
    bruto[~np.isfinite(bruto) | (bruto < 0)] = np.nan
    tt = t[i0:i1]
    # agrega pares de meia hora em horas cheias (HH:00 + HH:30)
    horas = tt.floor("h")
    uh, inv = np.unique(horas, return_inverse=True)
    n_por_hora = np.bincount(inv)
    soma = np.zeros((len(uh),) + bruto.shape[1:], dtype="float32")
    np.add.at(soma, inv, np.nan_to_num(bruto))
    falta = np.zeros_like(soma, dtype=bool)
    np.logical_or.at(falta, inv, np.isnan(bruto))
    soma[falta] = np.nan
    soma[n_por_hora < 2] = np.nan  # hora incompleta (borda da série)
    idx = pd.DatetimeIndex(uh, name="data_hora_utc")
    df = pd.DataFrame(g.medias(soma), index=idx, columns=g.regioes).astype("float32")
    df = df[n_por_hora == 2]
    # grade diária (somente dias com 24 h completas) para mapas e extração em pontos
    dias = idx.normalize()
    ud = [d for d in dias.unique() if (dias == d).sum() == 24]
    if ud:
        cub_d = np.stack([soma[dias == d].sum(axis=0) for d in ud])
        base.salvar_cubo(PRODUTO, f"{t0:%Y%m%d}", ud, cub_d, g)
    completo = (i1 - i0) == 1440 and tt[-1] < pd.Timestamp(config.DATA_FIM)
    if completo:
        df.to_parquet(arq)
    log.info("IMERG bloco %s: %d horas", f"{t0:%Y-%m-%d}", len(df))
    return df


def baixar(inicio=config.DATA_INICIO, fim=config.DATA_FIM, workers: int = 4) -> pd.DataFrame:
    """Série horária (mm/h) por UGRHI e estado. Índice = início da hora (UTC)."""
    e = _abrir()
    t = e["tempo"]
    blocos = list(range(0, len(t), 1440))
    blocos = [i for i in blocos if t[min(i + 1439, len(t) - 1)] >= pd.Timestamp(inicio) and t[i] <= pd.Timestamp(fim) + pd.Timedelta(days=1)]
    res = base.executar_em_paralelo(processar_bloco, blocos, workers=workers)
    partes = [res[i] for i in blocos if res[i] is not None]
    return pd.concat(partes).sort_index()
