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
import time
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


def _pedir(endpoint: str, params: dict, tentativas: int = 4, timeout: int = 180) -> str | None:
    """GET no web service da ANA com novas tentativas. None quando a estação não tem dados."""
    espera = 3.0
    for i in range(tentativas):
        try:
            r = base.sessao().get(f"{WS}/{endpoint}", params=params, timeout=timeout)
        except Exception as erro:  # rede instável: tenta de novo
            log.debug("ANA %s %s: %s", endpoint, params.get("codEstacao"), erro)
        else:
            if "ErrorTable" in r.text[:3000] or "Sem dados" in r.text[:5000]:
                return None  # a ANA responde 500 + ErrorTable quando não há série
            if r.ok:
                return r.text
            if r.status_code < 500:
                return None
        time.sleep(espera)
        espera *= 2
    raise RuntimeError(f"ANA {endpoint} {params.get('codEstacao')}: sem resposta após {tentativas} tentativas")


def serie_diaria(codigo: str, inicio="01/01/1980", fim=None, cache: bool = True) -> pd.DataFrame:
    """Série diária convencional (mm) de uma estação (HidroSerieHistorica, tipoDados=2).

    Prefere o dado consistido (nível 2) ao bruto (nível 1) em cada mês. Dias com status
    4 (acumulado: chuva de vários dias lançada num dia só) ficam como falta, como no RClimDex.
    """
    arq = base.pasta_cache("ANA") / f"serie_{codigo}.parquet"
    if cache and arq.exists():
        return pd.read_parquet(arq)
    fim = fim or config.DATA_FIM.strftime("%d/%m/%Y")
    params = {"codEstacao": codigo, "dataInicio": inicio, "dataFim": fim, "tipoDados": "2", "nivelConsistencia": ""}
    texto = _pedir("HidroSerieHistorica", params)
    t = _xml_tabelas(texto, "SerieHistorica") if texto else pd.DataFrame()
    df = _mensal_para_diario(t, codigo)
    if cache:
        df.to_parquet(arq, index=False)
    return df


COLUNAS_DIARIO = ["estacao", "data", "chuva_mm", "nivel", "status"]


def _mensal_para_diario(t: pd.DataFrame, codigo: str) -> pd.DataFrame:
    """Converte linhas mensais (Chuva01..Chuva31) em série diária, priorizando consistidos."""
    if t.empty:
        return pd.DataFrame({c: pd.Series(dtype=tp) for c, tp in
                             zip(COLUNAS_DIARIO, ["object", "datetime64[ns]", "float64", "int8", "int8"])})
    col_data = "DataHora" if "DataHora" in t else "Data"
    t = t.copy()
    t["mes"] = pd.to_datetime(t[col_data], dayfirst=col_data == "Data", errors="coerce").dt.to_period("M")
    t = t[t["mes"].notna()]
    t["nivel"] = pd.to_numeric(t.get("NivelConsistencia", 1), errors="coerce").fillna(1)
    # pluviômetro (1) antes de pluviógrafo (2) quando há as duas medições no mesmo mês
    t["tipo"] = -pd.to_numeric(t.get("TipoMedicaoChuvas", 1), errors="coerce").fillna(1)
    t = t.sort_values(["nivel", "tipo"]).drop_duplicates("mes", keep="last")
    linhas = []
    for _, row in t.iterrows():
        inicio_mes = row["mes"].to_timestamp()
        for d in range(1, row["mes"].days_in_month + 1):
            v = row.get(f"Chuva{d:02d}")
            if v is None or str(v).strip() == "":
                continue
            st = str(row.get(f"Chuva{d:02d}Status") or "1").strip() or "1"
            if st in ("0", "4"):  # 0 = em branco; 4 = acumulado
                continue
            try:
                valor = float(str(v).replace(",", "."))
            except ValueError:
                continue
            if valor < 0:
                continue
            linhas.append((inicio_mes + pd.Timedelta(days=d - 1), valor, int(row["nivel"]), int(st) if st.isdigit() else 1))
    df = pd.DataFrame(linhas, columns=COLUNAS_DIARIO[1:])
    df.insert(0, "estacao", codigo)
    df["nivel"] = df["nivel"].astype("int8")
    df["status"] = df["status"].astype("int8")
    return df.sort_values("data").reset_index(drop=True)


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


# ---------------------------------------------------------------- controle de qualidade
LIMITE_FISICO_MM = 700.0     # maior chuva em 24 h já medida no Brasil: cerca de 683 mm (Bertioga, fev/2023)
REPETICAO_MIN_MM = 5.0       # valor repetido em 3 ou mais dias seguidos (sensor travado, código de falta como 99,9)
REPETICAO_DIAS = 3
ESPACIAL_MIN_MM = 100.0      # valores altos comparados com os vizinhos
ESPACIAL_RAIO_KM = 50.0
ESPACIAL_RAZAO = 0.10        # removido se todos os vizinhos (dia anterior a seguinte) ficaram abaixo de 10% do valor
ESPACIAL_ALTO_MM = 200.0     # para valores muito altos a exigência é maior:
ESPACIAL_RAZAO_ALTO = 0.30   # removido se nenhum vizinho chegou a 30% do valor
ESPACIAL_MIN_VIZINHOS = 3


def controle_qualidade(diario: pd.DataFrame, lat: pd.Series, lon: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove erros grosseiros da chuva diária e devolve (série limpa, tabela dos valores removidos).

    1. Limite físico: valor acima de 700 mm.
    2. Repetição: 3 ou mais dias seguidos com o mesmo valor de 5 mm ou mais.
    3. Teste espacial: valor de 100 mm ou mais quando pelo menos 3 postos num raio de 50 km, do dia
       anterior ao seguinte, registraram todos menos de 10% dele (menos de 30% para valores de 200 mm ou mais).
    """
    import numpy as np

    cols = list(diario.columns)
    datas = diario.index
    a = diario.to_numpy(dtype="float64", copy=True)
    removidos = []

    def tirar(mascara: np.ndarray, motivo: str) -> None:
        ii, jj = np.nonzero(mascara)
        removidos.extend((cols[j], datas[i], float(a[i, j]), motivo) for i, j in zip(ii, jj))
        a[mascara] = np.nan

    with np.errstate(invalid="ignore"):
        tirar(a > LIMITE_FISICO_MM, f"acima de {LIMITE_FISICO_MM:.0f} mm")

        # repetição: comprimento de cada sequência de valores iguais (NaN quebra a sequência)
        igual = np.zeros(a.shape, bool)
        igual[1:] = a[1:] == a[:-1]
        rep = np.zeros(a.shape, bool)
        for j in range(a.shape[1]):
            grupo = np.cumsum(~igual[:, j])
            tam = np.bincount(grupo)[grupo]
            rep[:, j] = (tam >= REPETICAO_DIAS) & (a[:, j] >= REPETICAO_MIN_MM)
        tirar(rep, f"mesmo valor em {REPETICAO_DIAS} ou mais dias seguidos")

        # teste espacial
        la = np.radians(lat.reindex(cols).to_numpy(float))
        lo = np.radians(lon.reindex(cols).to_numpy(float))
        dist = 6371.0 * 2 * np.arcsin(np.sqrt(np.sin((la[:, None] - la[None, :]) / 2) ** 2
                                              + np.cos(la[:, None]) * np.cos(la[None, :]) * np.sin((lo[:, None] - lo[None, :]) / 2) ** 2))
        vizinhos = [np.where((dist[j] <= ESPACIAL_RAIO_KM) & (dist[j] > 0))[0] for j in range(len(cols))]
        tem = np.isfinite(a)
        z = np.where(tem, a, -np.inf)
        jan = z.copy()
        jan[1:] = np.maximum(jan[1:], z[:-1])
        jan[:-1] = np.maximum(jan[:-1], z[1:])
        jan_n = tem.copy()
        jan_n[1:] |= tem[:-1]
        jan_n[:-1] |= tem[1:]
        esp = np.zeros(a.shape, bool)
        for i, j in zip(*np.nonzero(a >= ESPACIAL_MIN_MM)):
            viz = vizinhos[j]
            if len(viz) < ESPACIAL_MIN_VIZINHOS or int(jan_n[i, viz].sum()) < ESPACIAL_MIN_VIZINHOS:
                continue
            razao = ESPACIAL_RAZAO_ALTO if a[i, j] >= ESPACIAL_ALTO_MM else ESPACIAL_RAZAO
            if jan[i, viz].max() < razao * a[i, j]:
                esp[i, j] = True
        tirar(esp, f"vizinhos num raio de {ESPACIAL_RAIO_KM:.0f} km bem abaixo do valor "
                   f"(menos de {ESPACIAL_RAZAO:.0%}; {ESPACIAL_RAZAO_ALTO:.0%} se o valor passa de {ESPACIAL_ALTO_MM:.0f} mm)")

    tab = pd.DataFrame(removidos, columns=["estacao", "data", "chuva_mm", "motivo"]).sort_values(["estacao", "data"])
    log.info("controle de qualidade: %d valores removidos (%s)", len(tab), tab.motivo.value_counts().to_dict())
    limpo = pd.DataFrame(a.astype("float32"), index=datas, columns=diario.columns)
    return limpo, tab.reset_index(drop=True)


# ---------------------------------------------------------------- organização para o app e o Excel
def processar_sp(min_dias: int = 365) -> dict:
    """Junta as séries baixadas (cache) em tabelas prontas: inventário, diário, mensal, anual,
    média por UGRHI, contagem de postos por ano e validação satélite × posto.

    Usa as mesmas regras do resto do projeto (mês com mais de 3 dias sem dado = falta;
    ano com mais de 15 = falta; média da UGRHI só com 3 postos ou mais no dia).
    """
    from .. import agregacao as ag
    from .. import validacao

    pasta = base.pasta_cache("ANA")
    inv = pd.read_csv(pasta / "inventario_ws.csv", dtype=str)
    inv = inv[inv.ugrhi.notna()].copy()
    inv["id"] = inv["Codigo"].str.zfill(8)
    series = {}
    for c in inv["id"]:
        arq = pasta / f"serie_{c}.parquet"
        if not arq.exists():
            continue
        d = pd.read_parquet(arq)
        d = d[(d.data >= pd.Timestamp(config.DATA_INICIO)) & (d.data <= pd.Timestamp(config.DATA_FIM))]
        if len(d) >= min_dias:
            series[c] = d.set_index("data")["chuva_mm"]
    diario = pd.DataFrame(series).sort_index()
    diario = diario.reindex(pd.date_range(config.DATA_INICIO, diario.index.max(), freq="D", name="data"))
    diario = diario.astype("float32")
    inv = inv[inv.id.isin(diario.columns)].copy()
    num = lambda col: pd.to_numeric(inv[col], errors="coerce")  # noqa: E731
    tab = pd.DataFrame({
        "id": inv.id, "nome": inv.Nome.str.strip(), "municipio": inv.nmMunicipio.str.strip(),
        "operadora": inv.OperadoraSigla.str.strip(), "responsavel": inv.ResponsavelSigla.str.strip(),
        "ugrhi": inv.ugrhi, "lat": num("Latitude"), "lon": num("Longitude"), "altitude": num("Altitude"),
        "operando": inv.Operando.eq("1"), "telemetrica": inv.TipoEstacaoTelemetrica.eq("1"),
    }).set_index("id").reindex(diario.columns).rename_axis("id").reset_index()
    diario, removidos = controle_qualidade(diario, tab.set_index("id").lat, tab.set_index("id").lon)
    validos = diario.notna()
    tab["primeiro_dia"] = [diario.index[validos[c].values.argmax()].date() for c in tab.id]
    tab["ultimo_dia"] = [diario.index[len(diario) - 1 - validos[c].values[::-1].argmax()].date() for c in tab.id]
    tab["dias_validos_desde_1980"] = validos.sum().loc[tab.id].values
    mensal = ag.diario_para_mensal(diario)
    anual = ag.diario_para_anual(diario)
    anual = anual[anual.index <= config.DATA_FIM.year]
    tab["anos_completos"] = anual.notna().sum().loc[tab.id].values
    tab["media_anual_mm"] = anual.mean().astype("float64").loc[tab.id].round(1).values
    tab["rede"], tab["codigo_original"] = "ANA (HidroWeb)", tab["id"]

    med = ag.media_postos_por_ugrhi(diario, tab)
    out = {
        "inventario": tab, "diario": diario, "mensal": mensal, "anual": anual, "removidos": removidos,
        "contagem": ag.contagem_postos(diario, tab),
        "media_ugrhi": {"diario": med, "mensal": ag.diario_para_mensal(med), "anual": ag.diario_para_anual(med)},
    }
    out["media_ugrhi"]["anual"] = out["media_ugrhi"]["anual"][out["media_ugrhi"]["anual"].index <= config.DATA_FIM.year]
    valid, lags = validacao.validar(tab, diario.astype("float64"))
    out["validacao"], out["defasagens"] = valid, lags
    return out


def salvar_processados_sp(res: dict) -> None:
    """Grava as tabelas da ANA em dados/processados (Parquet/CSV), sem tocar nos demais arquivos."""
    P = config.PROCESSADOS
    res["inventario"].to_csv(P / "ANA_inventario.csv", index=False)
    for k in ("diario", "mensal", "anual"):
        res[k].to_parquet(P / f"ANA_{k}.parquet")
        res["media_ugrhi"][k].to_parquet(P / f"ANA_MEDIA_{k}.parquet")
    res["contagem"].to_csv(P / "ANA_n_por_ano.csv")
    res["validacao"].to_csv(P / "validacao_sat_x_ana.csv", index=False)
    res["removidos"].to_csv(P / "ANA_controle_qualidade.csv", index=False)


def baixar_series_sp(workers: int = 6) -> pd.DataFrame:
    """Baixa (ou lê do cache) o inventário e as séries diárias de todas as estações de SP."""
    pasta = base.pasta_cache("ANA")
    inv = inventario_sp()
    inv.to_csv(pasta / "inventario_ws.csv", index=False)
    codigos = [str(c).zfill(8) for c in inv.loc[inv.ugrhi.notna(), "Codigo"]]
    base.executar_em_paralelo(serie_diaria, codigos, workers)
    log.info("ANA: %d estações de SP verificadas", len(codigos))
    return inv


if __name__ == "__main__":  # python -m chuva_sp.estacoes.ana
    base.configurar_log()
    baixar_series_sp()
    res = processar_sp()
    salvar_processados_sp(res)
    log.info("ANA: %d postos com série desde 1980; validação com %d linhas", len(res["inventario"]), len(res["validacao"]))
