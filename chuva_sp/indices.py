"""Índices ETCCDI de precipitação (mesmas definições do R/ClimdexSP.R) e tendência de Sen/Mann-Kendall."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

DESCRICAO = {
    "PRCPTOT": ("Precipitação total anual em dias úmidos", "mm"),
    "SDII": ("Intensidade diária média (dias úmidos)", "mm/dia"),
    "R10mm": ("Dias com chuva ≥ 10 mm", "dias"),
    "R20mm": ("Dias com chuva ≥ 20 mm", "dias"),
    "R50mm": ("Dias com chuva ≥ 50 mm", "dias"),
    "CDD": ("Máximo de dias secos consecutivos", "dias"),
    "CWD": ("Máximo de dias úmidos consecutivos", "dias"),
    "R95p": ("Chuva em dias > P95 (base)", "mm"),
    "R99p": ("Chuva em dias > P99 (base)", "mm"),
    "Rx1day": ("Máxima chuva em 1 dia", "mm"),
    "Rx5day": ("Máxima chuva em 5 dias", "mm"),
}


def _maior_sequencia_por_ano(cond: np.ndarray, anos: np.ndarray) -> pd.Series:
    """Sequências atribuídas ao ano em que terminam (atravessam anos, como no climdex.pcic)."""
    res = {a: 0 for a in np.unique(anos)}
    n = 0
    for i, c in enumerate(cond):
        n = n + 1 if c else 0
        fim = c and (i == len(cond) - 1 or not cond[i + 1])
        if fim:
            res[anos[i]] = max(res[anos[i]], n)
    return pd.Series(res)


def indices_anuais(serie: pd.Series, base=(1981, 2010), limiar=1.0, max_faltas_ano=15) -> pd.DataFrame:
    s = serie.copy()
    s.index = pd.DatetimeIndex(s.index)
    s = s.reindex(pd.date_range(f"{s.index.min().year}-01-01", f"{s.index.max().year}-12-31", freq="D"))
    x = s.to_numpy(dtype=float)
    anos = s.index.year.to_numpy()
    umido = np.where(np.isnan(x), False, x >= limiar)
    na_base = (anos >= base[0]) & (anos <= base[1])
    ub = x[na_base & umido]
    if ub.size < 100:
        ub = x[umido]
    # quantil tipo 8 (Hyndman & Fan), como no climdex.pcic
    p95, p99 = (np.quantile(ub, q, method="median_unbiased") for q in (0.95, 0.99))
    df = pd.DataFrame({"x": x, "ano": anos, "umido": umido})
    g = df.groupby("ano")
    out = pd.DataFrame(index=g.size().index)
    out["PRCPTOT"] = g.apply(lambda d: d.x[d.umido].sum(), include_groups=False)
    nu = g.umido.sum()
    out["SDII"] = (out.PRCPTOT / nu.replace(0, np.nan)).fillna(0)
    for k in (10, 20, 50):
        out[f"R{k}mm"] = g.x.apply(lambda v, k=k: (v >= k).sum())
    out["CDD"] = _maior_sequencia_por_ano(~np.isnan(x) & (x < limiar), anos)
    out["CWD"] = _maior_sequencia_por_ano(umido, anos)
    out["R95p"] = g.apply(lambda d: d.x[d.umido & (d.x > p95)].sum(), include_groups=False)
    out["R99p"] = g.apply(lambda d: d.x[d.umido & (d.x > p99)].sum(), include_groups=False)
    out["Rx1day"] = g.x.max()
    out["Rx5day"] = pd.Series(pd.Series(x).rolling(5).sum().to_numpy()).groupby(anos).max().values
    faltas = g.x.apply(lambda v: v.isna().sum())
    out.loc[faltas > max_faltas_ano, :] = np.nan
    out.index.name = "ano"
    return out


def tendencia(anos, valores) -> dict:
    """Sen (por década) + Mann-Kendall (p) + regressão linear (por década, p)."""
    a = np.asarray(anos, dtype=float)
    v = np.asarray(valores, dtype=float)
    ok = np.isfinite(v)
    a, v = a[ok], v[ok]
    if v.size < 8:
        return {"n": int(v.size)}
    sen = stats.theilslopes(v, a)[0]
    tau, p_mk = stats.kendalltau(a, v)
    lr = stats.linregress(a, v)
    return {"n": int(v.size), "sen_por_decada": 10 * sen, "mk_tau": tau, "mk_p": p_mk,
            "ols_por_decada": 10 * lr.slope, "p_ols": lr.pvalue}
