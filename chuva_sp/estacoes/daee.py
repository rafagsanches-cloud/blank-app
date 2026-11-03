"""DAEE / SP Águas – rede pluviométrica do Estado de São Paulo (SIBH).

Os dados do DAEE (atual SP Águas) ficam no Sistema de Informações sobre Bacias
Hidrográficas: https://sibh.sp.gov.br/ (séries históricas e telemetria).

Neste projeto, as séries históricas do DAEE chegam por dois caminhos:

* **GHCN-Daily** (módulo ``ghcn.py``), que redistribui ~950 postos DAEE de SP
  (prefixos como E3-052, D4-044...) com dados diários de 1980 até ~2005;
* **arquivos exportados do SIBH**, lidos aqui por ``ler_exportacao`` – a função aceita
  CSV/XLSX com uma coluna de data (ou data e hora) e uma coluna de chuva.

O portal do SIBH está bloqueado neste ambiente de nuvem; exporte os arquivos pelo site
e coloque-os em ``dados/brutos/daee/``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .. import config


def _achar(colunas, padroes):
    for p in padroes:
        for c in colunas:
            if re.search(p, str(c), re.I):
                return c
    return None


def ler_exportacao(caminho: str | Path, codigo: str | None = None) -> pd.DataFrame:
    """Lê um arquivo do SIBH/DAEE (CSV ';' ou ',' ou XLSX) -> colunas estacao, data_hora, chuva_mm."""
    caminho = Path(caminho)
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        t = pd.read_excel(caminho)
    else:
        txt = caminho.read_text(encoding="utf-8", errors="replace")
        sep = ";" if txt.count(";") > txt.count(",") else ","
        t = pd.read_csv(caminho, sep=sep, decimal="," if sep == ";" else ".", encoding_errors="replace")
    c_data = _achar(t.columns, [r"data.?hora", r"^data", r"date", r"dia"])
    c_hora = _achar(t.columns, [r"^hora", r"time"])
    c_chuva = _achar(t.columns, [r"chuva", r"precip", r"valor", r"mm"])
    if c_data is None or c_chuva is None:
        raise ValueError(f"não encontrei colunas de data/chuva em {caminho.name}: {list(t.columns)}")
    dh = t[c_data].astype(str) + ((" " + t[c_hora].astype(str)) if c_hora and c_hora != c_data else "")
    out = pd.DataFrame(
        {
            "estacao": codigo or caminho.stem,
            "data_hora": pd.to_datetime(dh, dayfirst=True, errors="coerce"),
            "chuva_mm": pd.to_numeric(t[c_chuva].astype(str).str.replace(",", "."), errors="coerce"),
        }
    )
    return out.dropna(subset=["data_hora"])


def ler_pasta(pasta: str | Path = config.BRUTOS / "daee") -> pd.DataFrame:
    pasta = Path(pasta)
    arqs = sorted([*pasta.glob("*.csv"), *pasta.glob("*.xlsx")]) if pasta.exists() else []
    return pd.concat([ler_exportacao(a) for a in arqs], ignore_index=True) if arqs else pd.DataFrame()
