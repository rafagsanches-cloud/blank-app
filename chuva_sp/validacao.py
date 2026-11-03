"""Validação ponto-a-pixel: satélite x pluviômetro (métricas diárias e mensais)."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xarray as xr

from . import config

log = logging.getLogger("chuva_sp")


def series_no_ponto(produto: str, lons: np.ndarray, lats: np.ndarray, ids: list[str]) -> pd.DataFrame:
    """Lê as grades diárias em cache e devolve a série do pixel que contém cada estação."""
    arqs = sorted((config.CACHE / produto).glob(f"{produto}_grade_diaria_*.nc"))
    if not arqs:
        return pd.DataFrame()
    partes = []
    ix = iy = None
    for a in arqs:
        with xr.open_dataset(a, engine="h5netcdf") as ds:
            if ix is None:
                ix = np.abs(ds.lon.values[None, :] - lons[:, None]).argmin(axis=1)
                iy = np.abs(ds.lat.values[None, :] - lats[:, None]).argmin(axis=1)
            v = ds.precip.values[:, iy, ix]
            partes.append(pd.DataFrame(v, index=pd.DatetimeIndex(ds.time.values), columns=ids))
    df = pd.concat(partes).sort_index()
    return df[~df.index.duplicated()]


def metricas(obs: pd.Series, est: pd.Series, limiar: float = 1.0) -> dict:
    m = obs.notna() & est.notna()
    o, e = obs[m].values.astype(float), est[m].values.astype(float)
    n = len(o)
    if n < 30:
        return {"n": n}
    r = np.corrcoef(o, e)[0, 1] if o.std() > 0 and e.std() > 0 else np.nan
    beta = e.mean() / o.mean() if o.mean() > 0 else np.nan
    gama = (e.std() / e.mean()) / (o.std() / o.mean()) if o.mean() > 0 and e.mean() > 0 else np.nan
    kge = 1 - np.sqrt((r - 1) ** 2 + (beta - 1) ** 2 + (gama - 1) ** 2)
    so, se = o >= limiar, e >= limiar
    h, f, mi = (so & se).sum(), (~so & se).sum(), (so & ~se).sum()
    return {
        "n": n,
        "media_obs": o.mean(),
        "media_sat": e.mean(),
        "vies_pct": 100 * (e.sum() - o.sum()) / o.sum() if o.sum() > 0 else np.nan,
        "r_pearson": r,
        "rmse": float(np.sqrt(np.mean((e - o) ** 2))),
        "mae": float(np.mean(np.abs(e - o))),
        "kge": kge,
        "pod": h / (h + mi) if h + mi else np.nan,
        "far": f / (h + f) if h + f else np.nan,
        "csi": h / (h + f + mi) if h + f + mi else np.nan,
    }


def melhor_defasagem(postos: pd.DataFrame, sat: pd.DataFrame) -> int:
    """Testa defasagens -1, 0, +1 dia (convenção do 'dia pluviométrico') pela correlação média."""
    scores = {}
    for lag in (-1, 0, 1):
        s = sat.shift(lag)
        rs = [postos[c].corr(s[c]) for c in postos.columns if c in s.columns and postos[c].notna().sum() > 365]
        scores[lag] = np.nanmean(rs) if rs else np.nan
    log.info("correlação média por defasagem: %s", {k: round(v, 3) for k, v in scores.items()})
    return max(scores, key=lambda k: -np.inf if np.isnan(scores[k]) else scores[k])


def validar(inv: pd.DataFrame, postos: pd.DataFrame, produtos=("CHIRPS", "PERSIANN", "CMORPH", "IMERG")) -> tuple[pd.DataFrame, dict]:
    """Tabela de métricas por estação e produto (diária e mensal)."""
    linhas, lags = [], {}
    from .agregacao import diario_para_mensal

    for p in produtos:
        sat = series_no_ponto(p, inv.lon.values, inv.lat.values, inv.id.tolist())
        if sat.empty:
            continue
        comum = postos.index.intersection(sat.index)
        if len(comum) < 365:
            continue
        lag = melhor_defasagem(postos.loc[comum], sat.reindex(postos.index).loc[comum])
        lags[p] = lag
        sat_l = sat.reindex(postos.index).shift(lag)
        pm, sm = diario_para_mensal(postos), diario_para_mensal(sat_l)
        for est in inv.itertuples():
            d = metricas(postos[est.id], sat_l[est.id])
            if d.get("n", 0) < 365:
                continue
            mm = metricas(pm[est.id], sm[est.id], limiar=10.0)
            linhas.append(
                {
                    "produto": p, "estacao": est.id, "codigo_original": est.codigo_original, "rede": est.rede,
                    "nome": est.nome, "ugrhi": est.ugrhi, "defasagem_dias": lag,
                    **{f"diario_{k}": v for k, v in d.items()},
                    **{f"mensal_{k}": v for k, v in mm.items() if k in ("n", "vies_pct", "r_pearson", "rmse", "kge")},
                }
            )
        log.info("validação %s: %d estações (defasagem %+d dia)", p, sum(1 for l in linhas if l["produto"] == p), lag)
    return pd.DataFrame(linhas), lags
