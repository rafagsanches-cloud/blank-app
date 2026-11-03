"""Postos pluviométricos de SP no GHCN-Daily (NOAA), via S3 público.

O GHCN-Daily reúne, para o Brasil, séries diárias de postos da rede hidrometeorológica
nacional (códigos ANA, ex. BR002549075 -> 02549075) e de postos do DAEE-SP
(prefixos DAEE, ex. BR00E3-0520 -> E3-052), além de estações sinóticas (BRM...).
A maior parte das séries brasileiras no GHCN vai até ~2005; para os anos recentes use
o HidroWeb/ANA e o SIBH/DAEE (módulos ana.py e daee.py, quando a rede permitir).
"""
from __future__ import annotations

import gzip
import io
import logging

import numpy as np
import pandas as pd

from .. import config, ugrhi
from ..satelites import base

log = logging.getLogger("chuva_sp")
S3 = "https://noaa-ghcn-pds.s3.amazonaws.com"


def _texto(nome: str) -> str:
    arq = base.pasta_cache("GHCN") / nome
    if not arq.exists():
        arq.write_bytes(base.baixar_bytes(f"{S3}/{nome}"))
    return arq.read_text(encoding="latin-1")


def _rede(id_: str) -> tuple[str, str]:
    """Interpreta o identificador GHCN -> (rede provável, código original)."""
    cod = id_[3:]
    if id_.startswith("BRM"):
        return "OMM/INMET (sinótica)", cod[-5:]
    cod = cod.lstrip("0") if cod.isdigit() else cod
    if cod.isdigit():
        return "ANA (HidroWeb)", cod.zfill(8)
    # Prefixos DAEE: letra + dígito + '-' + 3 dígitos (+ 1 dígito de controle no GHCN)
    if "-" in cod:
        pref, num = cod.split("-", 1)
        return "DAEE-SP", f"{pref.lstrip('0')}-{num[:3]}"
    return "outra", cod


def inventario(ano_min: int = config.DATA_INICIO.year) -> pd.DataFrame:
    """Estações GHCN-D com PRCP dentro das UGRHIs de SP e dados a partir de ano_min."""
    est = pd.read_fwf(
        io.StringIO(_texto("ghcnd-stations.txt")),
        colspecs=[(0, 11), (12, 20), (21, 30), (31, 37), (38, 40), (41, 71), (80, 85)],
        names=["id", "lat", "lon", "altitude", "uf", "nome", "omm"],
        dtype={"omm": str},
    )
    inv = pd.read_fwf(
        io.StringIO(_texto("ghcnd-inventory.txt")),
        colspecs=[(0, 11), (31, 35), (36, 40), (41, 45)],
        names=["id", "elemento", "ano_ini", "ano_fim"],
    )
    inv = inv[inv.elemento == "PRCP"].drop(columns="elemento")
    df = est.merge(inv, on="id")
    x0, y0, x1, y1 = config.BBOX_SP
    df = df[df.lon.between(x0, x1) & df.lat.between(y0, y1) & (df.ano_fim >= ano_min)].copy()
    df["ugrhi"] = ugrhi.ponto_em_ugrhi(df.lon.values, df.lat.values)
    df = df[df.ugrhi.notna()].copy()
    rede = df.id.map(_rede)
    df["rede"] = [r[0] for r in rede]
    df["codigo_original"] = [r[1] for r in rede]
    df["fonte"] = "GHCN-Daily (NOAA)"
    df["nome"] = df.nome.str.strip().str.title()
    return df.drop(columns="uf").reset_index(drop=True)


def _serie(id_: str) -> pd.DataFrame | None:
    b = base.baixar_bytes(f"{S3}/csv.gz/by_station/{id_}.csv.gz")
    if b is None:
        return None
    d = pd.read_csv(
        io.BytesIO(gzip.decompress(b)),
        header=None,
        names=["id", "data", "elemento", "valor", "m", "q", "s", "hora"],
        dtype={"data": str, "m": str, "q": str, "s": str, "hora": str},
    )
    d = d[(d.elemento == "PRCP") & (d.data >= config.DATA_INICIO.strftime("%Y%m%d"))]
    d = d[d.q.isna()]  # descarta valores reprovados no controle de qualidade do GHCN
    return pd.DataFrame(
        {"estacao": id_, "data": pd.to_datetime(d.data, format="%Y%m%d"), "chuva_mm": d.valor.astype(float) / 10.0}
    )


def baixar(workers: int = 16) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (inventário, série diária em formato largo: data x estação, mm/dia)."""
    inv = inventario()
    arq = base.pasta_cache("GHCN") / "ghcn_sp_diario.parquet"
    if arq.exists():
        larga = pd.read_parquet(arq)
    else:
        res = base.executar_em_paralelo(_serie, list(inv.id), workers)
        longa = pd.concat([v for v in res.values() if v is not None and len(v)], ignore_index=True)
        larga = longa.pivot_table(index="data", columns="estacao", values="chuva_mm", aggfunc="first")
        larga = larga.reindex(pd.date_range(config.DATA_INICIO, larga.index.max(), freq="D", name="data"))
        larga.to_parquet(arq)
    inv = inv[inv.id.isin(larga.columns)].copy()
    validos = larga.notna()
    inv["dias_validos_desde_1980"] = inv.id.map(validos.sum())
    inv["primeiro_dia"] = inv.id.map(lambda c: larga.index[validos[c].values].min())
    inv["ultimo_dia"] = inv.id.map(lambda c: larga.index[validos[c].values].max())
    inv = inv[inv.dias_validos_desde_1980 > 0].sort_values(["ugrhi", "id"]).reset_index(drop=True)
    larga = larga[inv.id]
    log.info("GHCN-D: %d estações em SP, %d valores", len(inv), int(validos.values.sum()))
    return inv, larga
