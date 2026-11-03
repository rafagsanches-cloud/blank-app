"""Agregação temporal com regras de dados faltantes no padrão ETCCDI/RClimDex.

* dia   : soma de 24 h (UTC); falta se qualquer hora faltar
* mês   : soma dos dias; falta se mais de 3 dias faltarem
* ano   : soma dos dias; falta se mais de 15 dias faltarem (ano incompleto = falta)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

MAX_FALTAS_MES = 3
MAX_FALTAS_ANO = 15


def horario_para_diario(h: pd.DataFrame) -> pd.DataFrame:
    """Soma horária -> diária (dia UTC). Exige as 24 horas."""
    h = h.copy()
    h.index = pd.DatetimeIndex(h.index)
    full = pd.date_range(h.index.min().normalize(), h.index.max().normalize() + pd.Timedelta(hours=23), freq="h")
    h = h.reindex(full)
    d = h.resample("D").sum(min_count=24)
    d.index.name = "data"
    return d


def _completar_anos(d: pd.DataFrame) -> pd.DataFrame:
    idx = pd.date_range(f"{d.index.min().year}-01-01", f"{d.index.max().year}-12-31", freq="D", name="data")
    return d.reindex(idx)


def diario_para_mensal(d: pd.DataFrame) -> pd.DataFrame:
    d = _completar_anos(d)
    soma = d.resample("MS").sum(min_count=1)
    faltas = d.isna().resample("MS").sum()
    soma[faltas > MAX_FALTAS_MES] = np.nan
    soma.index.name = "mes"
    return soma


def diario_para_anual(d: pd.DataFrame) -> pd.DataFrame:
    d = _completar_anos(d)
    soma = d.resample("YS").sum(min_count=1)
    faltas = d.isna().resample("YS").sum()
    soma[faltas > MAX_FALTAS_ANO] = np.nan
    soma.index = soma.index.year
    soma.index.name = "ano"
    return soma


def recortar_periodo(df: pd.DataFrame, inicio=config.DATA_INICIO, fim=config.DATA_FIM) -> pd.DataFrame:
    if isinstance(df.index, pd.DatetimeIndex):
        return df[(df.index >= pd.Timestamp(inicio)) & (df.index <= pd.Timestamp(fim) + pd.Timedelta(days=1))]
    return df[(df.index >= inicio.year) & (df.index <= fim.year)]


def media_postos_por_ugrhi(diario: pd.DataFrame, inv: pd.DataFrame, min_postos: int = 3) -> pd.DataFrame:
    """Média aritmética diária dos postos de cada UGRHI (NaN se < min_postos com dado)."""
    out = {}
    for sig, grupo in inv.groupby("ugrhi"):
        sub = diario[grupo.id.tolist()]
        n = sub.notna().sum(axis=1)
        out[sig] = sub.mean(axis=1).where(n >= min_postos)
    n_sp = diario.notna().sum(axis=1)
    out["SP"] = diario.mean(axis=1).where(n_sp >= 3 * min_postos)
    from . import ugrhi

    cols = ugrhi.regioes()
    return pd.DataFrame(out).reindex(columns=cols)


def contagem_postos(diario: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    """Número de postos com dado por ano e UGRHI."""
    anual = diario.notna().groupby(diario.index.year).any()
    out = {sig: anual[g.id.tolist()].sum(axis=1) for sig, g in inv.groupby("ugrhi")}
    out["SP"] = anual.sum(axis=1)
    from . import ugrhi

    df = pd.DataFrame(out).reindex(columns=ugrhi.regioes()).fillna(0).astype(int)
    df.index.name = "ano"
    return df
