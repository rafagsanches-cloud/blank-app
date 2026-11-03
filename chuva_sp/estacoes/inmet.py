"""INMET – estações meteorológicas automáticas (dados horários desde 2000).

O INMET publica um .zip por ano com um CSV por estação:
https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip

Este módulo baixa (ou lê de uma pasta local) esses arquivos e extrai a coluna
"PRECIPITAÇÃO TOTAL, HORÁRIO (mm)" das estações de SP. O horário vem em UTC.
O portal do INMET está bloqueado neste ambiente de nuvem; rode localmente.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config, ugrhi
from ..satelites import base

log = logging.getLogger("chuva_sp")
URL = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"


def _num(s: str) -> float:
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return np.nan


def _ler_csv_inmet(texto: str) -> tuple[dict, pd.DataFrame] | None:
    linhas = texto.splitlines()
    meta = {}
    for l in linhas[:8]:
        k, _, v = l.partition(":")
        meta[k.strip().upper()] = v.strip(" ;")
    if meta.get("UF") != "SP":
        return None
    cab = linhas[8].split(";")
    i_prec = next(i for i, c in enumerate(cab) if "PRECIPITA" in c.upper())
    reg = [l.split(";") for l in linhas[9:] if l.strip()]
    datas = [r[0].replace("/", "-") for r in reg]
    horas = [re.sub(r"\D", "", r[1])[:4].ljust(4, "0") for r in reg]
    ts = pd.to_datetime([f"{d} {h[:2]}:{h[2:]}" for d, h in zip(datas, horas)], errors="coerce")
    v = np.array([_num(r[i_prec]) if len(r) > i_prec else np.nan for r in reg])
    v[v < 0] = np.nan  # -9999 = falta
    est = {
        "codigo": meta.get("CODIGO (WMO)", ""),
        "nome": meta.get("ESTACAO", meta.get("ESTAÇÃO", "")).title(),
        "lat": _num(meta.get("LATITUDE", "")),
        "lon": _num(meta.get("LONGITUDE", "")),
        "altitude": _num(meta.get("ALTITUDE", "")),
    }
    return est, pd.DataFrame({"data_hora_utc": ts, "chuva_mm": v}).dropna(subset=["data_hora_utc"])


def ler_zip_ano(origem: str | Path | bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    if isinstance(origem, (str, Path)):
        origem = Path(origem).read_bytes()
    estacoes, series = [], []
    with zipfile.ZipFile(io.BytesIO(origem)) as z:
        for n in z.namelist():
            if not n.upper().endswith(".CSV") or "_SP_" not in n.upper():
                continue
            r = _ler_csv_inmet(z.read(n).decode("latin-1"))
            if r is None:
                continue
            est, s = r
            s.insert(0, "estacao", est["codigo"])
            estacoes.append(est)
            series.append(s)
    return pd.DataFrame(estacoes), pd.concat(series, ignore_index=True) if series else pd.DataFrame()


def baixar(ano_ini: int = 2000, ano_fim: int = config.DATA_FIM.year, pasta_zips: Path | None = None):
    """Devolve (inventário, série horária larga data_hora_utc x estação)."""
    invs, sers = [], []
    for ano in range(ano_ini, ano_fim + 1):
        local = pasta_zips / f"{ano}.zip" if pasta_zips else None
        b = local.read_bytes() if local and local.exists() else base.baixar_bytes(URL.format(ano=ano), timeout=600)
        if b is None:
            continue
        i, s = ler_zip_ano(b)
        invs.append(i)
        sers.append(s)
        log.info("INMET %d: %d estações em SP", ano, len(i))
    inv = pd.concat(invs).drop_duplicates("codigo", keep="last")
    inv["ugrhi"] = ugrhi.ponto_em_ugrhi(inv.lon.values, inv.lat.values)
    longa = pd.concat(sers, ignore_index=True)
    larga = longa.pivot_table(index="data_hora_utc", columns="estacao", values="chuva_mm", aggfunc="first")
    return inv.reset_index(drop=True), larga
