"""ANA – Agência Nacional de Águas e Saneamento Básico (HidroWeb / SNIRH).

Duas formas de obter os dados:

1. **Web service SOAP da ANA** (telemetriaws1.ana.gov.br/ServiceANA.asmx) – baixa
   inventário, séries diárias convencionais (HidroSerieHistorica) e dados das estações
   automáticas/telemétricas (DadosHidrometeorologicos, 15 min).
2. **Arquivos exportados do portal HidroWeb** (https://www.snirh.gov.br/hidroweb/serieshistoricas):
   os .zip/.csv de "chuvas" podem ser colocados em uma pasta e lidos por ``ler_hidroweb_csv``.

Atenção: este ambiente de nuvem não tem acesso aos servidores da ANA (política de rede);
rode este módulo na sua máquina. A ANA vem migrando para a API "HidroWebService"
(https://www.ana.gov.br/hidrowebservice/), que exige cadastro (identificador e senha);
se o serviço SOAP for desligado, use a opção 2 ou a nova API.
"""
from __future__ import annotations

import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

from .. import config, ugrhi
from ..satelites import base

log = logging.getLogger("chuva_sp")
WS = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx"


def _xml_tabelas(texto: str, tag: str) -> pd.DataFrame:
    raiz = ET.fromstring(texto)
    linhas = []
    for el in raiz.iter():
        if el.tag.split("}")[-1] == tag:
            linhas.append({c.tag.split("}")[-1]: (c.text or "").strip() for c in el})
    return pd.DataFrame(linhas)


def inventario_sp(telemetricas: bool = False) -> pd.DataFrame:
    """Inventário de estações pluviométricas (tpEst=2) do Estado de São Paulo."""
    params = {
        "codEstDE": "", "codEstATE": "", "tpEst": "2", "nmEst": "", "nmRio": "",
        "codSubBacia": "", "codBacia": "", "nmMunicipio": "", "nmEstado": "SÃO PAULO",
        "sgResp": "", "sgOper": "", "telemetrica": "1" if telemetricas else "",
    }
    r = base.sessao().get(f"{WS}/HidroInventario", params=params, timeout=300)
    r.raise_for_status()
    df = _xml_tabelas(r.text, "Table")
    for c in ("Latitude", "Longitude"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ugrhi"] = ugrhi.ponto_em_ugrhi(df.Longitude.values, df.Latitude.values)
    return df


def serie_diaria(codigo: str, inicio="01/01/1980", fim=None) -> pd.DataFrame:
    """Série diária convencional (mm) de uma estação. Prefere dado consistido (nível 2)."""
    fim = fim or config.DATA_FIM.strftime("%d/%m/%Y")
    params = {"codEstacao": codigo, "dataInicio": inicio, "dataFim": fim, "tipoDados": "2", "nivelConsistencia": ""}
    r = base.sessao().get(f"{WS}/HidroSerieHistorica", params=params, timeout=300)
    r.raise_for_status()
    t = _xml_tabelas(r.text, "SerieHistorica")
    return _mensal_para_diario(t, codigo)


def _mensal_para_diario(t: pd.DataFrame, codigo: str) -> pd.DataFrame:
    """Converte linhas mensais (Chuva01..Chuva31) em série diária, priorizando consistidos."""
    if t.empty:
        return pd.DataFrame(columns=["estacao", "data", "chuva_mm", "nivel"])
    col_data = "DataHora" if "DataHora" in t else "Data"
    t["mes"] = pd.to_datetime(t[col_data], dayfirst=col_data == "Data", errors="coerce").dt.to_period("M")
    t["nivel"] = pd.to_numeric(t.get("NivelConsistencia", 1), errors="coerce").fillna(1)
    t = t.sort_values("nivel").drop_duplicates("mes", keep="last")
    linhas = []
    for _, row in t.iterrows():
        for d in range(1, row["mes"].days_in_month + 1):
            v = row.get(f"Chuva{d:02d}")
            if v in (None, ""):
                continue
            linhas.append((row["mes"].to_timestamp() + pd.Timedelta(days=d - 1), float(str(v).replace(",", ".")), row["nivel"]))
    df = pd.DataFrame(linhas, columns=["data", "chuva_mm", "nivel"])
    df.insert(0, "estacao", codigo)
    return df.sort_values("data")


def serie_telemetrica(codigo: str, inicio: str, fim: str) -> pd.DataFrame:
    """Dados de estação automática/telemétrica (≈15 min) agregados para hora cheia (mm/h)."""
    params = {"codEstacao": codigo, "dataInicio": inicio, "dataFim": fim}
    r = base.sessao().get(f"{WS}/DadosHidrometeorologicos", params=params, timeout=300)
    r.raise_for_status()
    t = _xml_tabelas(r.text, "DadosHidrometereologicos")
    if t.empty:
        return pd.DataFrame(columns=["estacao", "data_hora_local", "chuva_mm"])
    t["data_hora"] = pd.to_datetime(t["DataHora"], errors="coerce")
    t["chuva"] = pd.to_numeric(t["Chuva"].str.replace(",", "."), errors="coerce")
    # O valor de cada registro é a chuva acumulada no intervalo que termina em DataHora
    h = t.set_index("data_hora")["chuva"].resample("h", closed="right", label="left").sum(min_count=1)
    return pd.DataFrame({"estacao": codigo, "data_hora_local": h.index, "chuva_mm": h.values})


def ler_hidroweb_csv(caminho: str | Path) -> pd.DataFrame:
    """Lê um arquivo 'chuvas_*.csv' (ou .zip) exportado do portal HidroWeb -> série diária."""
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".zip":
        partes = []
        with zipfile.ZipFile(caminho) as z:
            for n in z.namelist():
                if n.lower().endswith(".zip"):
                    partes.append(ler_hidroweb_csv(io.BytesIO(z.read(n))))  # type: ignore[arg-type]
                elif re.search(r"chuva", n, re.I) and n.lower().endswith((".csv", ".txt")):
                    partes.append(_ler_hidroweb_texto(z.read(n).decode("latin-1")))
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    return _ler_hidroweb_texto(caminho.read_text(encoding="latin-1"))


def _ler_hidroweb_texto(texto: str) -> pd.DataFrame:
    linhas = texto.splitlines()
    i = next(i for i, l in enumerate(linhas) if l.startswith("EstacaoCodigo"))
    t = pd.read_csv(io.StringIO("\n".join(linhas[i:])), sep=";", dtype=str, decimal=",")
    codigo = str(t["EstacaoCodigo"].iloc[0]).zfill(8)
    return _mensal_para_diario(t, codigo)


def baixar_todas_sp(pasta_saida: Path | None = None, workers: int = 8) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inventário + séries diárias de todas as estações pluviométricas da ANA em SP."""
    pasta_saida = pasta_saida or base.pasta_cache("ANA")
    inv = inventario_sp()
    inv = inv[inv.ugrhi.notna()]
    res = base.executar_em_paralelo(lambda c: serie_diaria(c), list(inv["Codigo"]), workers)
    longa = pd.concat([v for v in res.values() if v is not None and len(v)], ignore_index=True)
    larga = longa.pivot_table(index="data", columns="estacao", values="chuva_mm", aggfunc="first")
    larga.to_parquet(pasta_saida / "ana_sp_diario.parquet")
    inv.to_csv(pasta_saida / "ana_sp_inventario.csv", index=False)
    return inv, larga
