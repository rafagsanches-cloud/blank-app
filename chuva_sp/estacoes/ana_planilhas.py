"""Planilhas (Excel e CSV) com a chuva das estações da ANA em todo o Estado de São Paulo.

Lê as séries já baixadas em dados/cache/ANA (python -m chuva_sp.estacoes.ana) e grava em
saidas/ana:

* Chuva_ANA_SP_1980-2026_mensal_anual.xlsx: inventário, totais anuais e mensais de cada
  posto, dias com dado em cada mês, médias por UGRHI (diária, mensal e anual) e postos por ano;
* diario/Chuva_ANA_SP_diario_<UGRHI>.xlsx: chuva diária de cada posto, um arquivo por UGRHI;
* Chuva_ANA_SP_1980-2026_csv.zip: as mesmas tabelas em CSV (diário de todo o Estado num só arquivo).

Uso: python -m chuva_sp.estacoes.ana_planilhas
"""
from __future__ import annotations

import datetime as dt
import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .. import agregacao as ag
from .. import config, ugrhi
from ..excel import Pasta
from ..satelites import base
from .ana import controle_qualidade

log = logging.getLogger("chuva_sp")
DESTINO = config.SAIDAS / "ana"
FORA = "fora das UGRHIs"


def montar() -> dict:
    pasta = base.pasta_cache("ANA")
    ws = pd.read_csv(pasta / "inventario_ws.csv", dtype=str)
    ws["codigo"] = ws.Codigo.str.zfill(8)
    ws = ws.drop_duplicates("codigo").set_index("codigo")
    fim = pd.Timestamp(config.DATA_FIM)
    series, nivel2 = {}, {}
    for c in ws.index:
        arq = pasta / f"serie_{c}.parquet"
        if not arq.exists():
            continue
        d = pd.read_parquet(arq)
        d = d[(d.data >= pd.Timestamp(config.DATA_INICIO)) & (d.data <= fim)]
        if len(d):
            series[c] = d.set_index("data")["chuva_mm"]
            nivel2[c] = float((d.nivel == 2).mean())
    diario = pd.DataFrame(series).sort_index()
    diario = diario.reindex(pd.date_range(config.DATA_INICIO, diario.index.max(), freq="D", name="data"))
    diario = diario[sorted(diario.columns, key=lambda c: (str(ws.at[c, "ugrhi"]) if pd.notna(ws.at[c, "ugrhi"]) else "ZZ", c))]
    diario, removidos = controle_qualidade(diario, pd.to_numeric(ws.Latitude, errors="coerce"), pd.to_numeric(ws.Longitude, errors="coerce"))
    diario = diario.loc[:, diario.notna().any()]
    mensal = ag.diario_para_mensal(diario)
    anual = ag.diario_para_anual(diario)
    anual = anual[anual.index <= fim.year]
    completo = diario.reindex(pd.date_range(diario.index.min(), f"{diario.index.max().year}-12-31", freq="D", name="data"))
    dias_mes = completo.notna().resample("MS").sum().astype("int16")
    dias_mes.index.name = "mes"

    nomes = ugrhi.nomes_regioes()
    num = lambda col: pd.to_numeric(ws[col], errors="coerce")  # noqa: E731
    data = lambda col: pd.to_datetime(ws[col], errors="coerce").map(lambda x: None if pd.isna(x) else x.date())  # noqa: E731
    inv = pd.DataFrame({
        "codigo": ws.index, "nome": ws.Nome.str.strip(), "municipio": ws.nmMunicipio.str.strip(),
        "ugrhi": ws.ugrhi.fillna(""), "ugrhi_nome": ws.ugrhi.map(nomes).fillna(FORA),
        "latitude": num("Latitude"), "longitude": num("Longitude"), "altitude_m": num("Altitude"),
        "responsavel": ws.ResponsavelSigla.str.strip(), "operadora": ws.OperadoraSigla.str.strip(),
        "operando": np.where(ws.Operando.eq("1"), "sim", "não"),
        "telemetrica": np.where(ws.TipoEstacaoTelemetrica.eq("1"), "sim", "não"),
        "inventario_inicio": data("PeriodoPluviometroInicio"), "inventario_fim": data("PeriodoPluviometroFim"),
    }).reset_index(drop=True)
    tem = inv.codigo.isin(diario.columns)
    validos = diario.notna()
    prim = {c: diario.index[validos[c].values.argmax()].date() for c in diario.columns}
    ult = {c: diario.index[len(diario) - 1 - validos[c].values[::-1].argmax()].date() for c in diario.columns}
    inv["serie_desde_1980"] = np.where(tem, "sim", "não")
    inv["primeiro_dia"] = inv.codigo.map(prim).astype(object).where(tem, None)
    inv["ultimo_dia"] = inv.codigo.map(ult).astype(object).where(tem, None)
    inv["dias_com_dado"] = inv.codigo.map(validos.sum()).astype("float64")
    inv["anos_completos"] = inv.codigo.map(anual.notna().sum()).astype("float64")
    inv["media_anual_mm"] = inv.codigo.map(anual.mean().astype("float64").round(1))
    inv["pct_dias_consistidos"] = inv.codigo.map(pd.Series(nivel2).mul(100).round(1))
    inv = inv.sort_values(["serie_desde_1980", "ugrhi", "codigo"], ascending=[False, True, True]).reset_index(drop=True)

    inv_u = inv.set_index("codigo").reindex(diario.columns).rename_axis("id").reset_index()
    contagem = ag.contagem_postos(diario, inv_u[inv_u.ugrhi != ""])  # a coluna SP conta todos os postos do Estado
    contagem = contagem[contagem.index <= fim.year]
    P = config.PROCESSADOS
    media = {k: pd.read_parquet(P / f"ANA_MEDIA_{k}.parquet") for k in ("diario", "mensal", "anual")}
    media["anual"] = media["anual"][media["anual"].index <= fim.year]
    nomes_est = ws.Nome.str.strip()
    removidos.insert(1, "nome", removidos.estacao.map(nomes_est))
    removidos = removidos.rename(columns={"estacao": "codigo", "chuva_mm": "valor_removido_mm"})
    return {"inventario": inv, "diario": diario, "mensal": mensal, "anual": anual, "dias_mes": dias_mes,
            "contagem": contagem, "media": media, "removidos": removidos}


def leia_me(r: dict) -> list[tuple[str, str]]:
    inv, d = r["inventario"], r["diario"]
    n = int((inv.serie_desde_1980 == "sim").sum())
    return [
        ("#", "Chuva das estações pluviométricas da ANA no Estado de São Paulo, 1980–2026"),
        ("Fonte", "ANA, HidroWeb: web service público telemetriaws1.ana.gov.br (HidroInventario e HidroSerieHistorica, tipoDados=2), "
                  "o mesmo usado pelo pyHidroWeb e pelo hydrobr. Baixado em " + dt.date.today().strftime("%d/%m/%Y") + "."),
        ("Estações", f"{len(inv)} estações pluviométricas da ANA em SP no inventário; {n} têm série diária com dado entre "
                     f"01/01/1980 e {d.index.max():%d/%m/%Y}. As demais são automáticas (CEMADEN e outras) sem série convencional "
                     "no HidroWeb, ou só têm dados antes de 1980."),
        ("Unidade", "mm (total do dia, do mês ou do ano)."),
        ("Dia", "Leitura convencional das 7 h: o valor de um dia é a chuva das 24 horas anteriores à leitura."),
        ("Consistência", "Em cada mês vale o dado consistido (nível 2) quando existe; senão, o bruto (nível 1). "
                         "A coluna pct_dias_consistidos do inventário mostra a parcela de dias consistidos de cada posto."),
        ("Faltas", "Dias em branco e dias marcados como acumulados (chuva de vários dias lançada num dia só) ficam vazios. "
                   "Mês: vazio se mais de 3 dias faltarem. Ano: vazio se mais de 15 dias faltarem (padrão RClimDex/ETCCDI). "
                   "A planilha Mensal_dias_com_dado traz o número de dias com dado em cada mês."),
        ("Controle de qualidade", "Valores removidos (lista completa na planilha Controle_qualidade): (1) acima de 700 mm em um dia, "
                                  "acima do maior valor já medido no Brasil (cerca de 683 mm em 24 h, Bertioga, 2023); (2) o mesmo valor de "
                                  "5 mm ou mais em 3 ou mais dias seguidos (sensor travado ou código de falta, como 99,9); (3) valor de 100 mm "
                                  "ou mais quando pelo menos 3 postos num raio de 50 km, do dia anterior ao seguinte, registraram todos menos "
                                  "de 10% dele (menos de 30% se o valor passa de 200 mm). Eventos fortes da Serra do Mar, com vizinhos "
                                  f"também altos, são mantidos. Foram removidos {len(r['removidos'])} valores diários."),
        ("Médias por UGRHI", "Média aritmética diária dos postos da UGRHI, só nos dias com pelo menos 3 postos (9 no Estado); "
                             "mês e ano seguem as mesmas regras de falta."),
        ("UGRHI", f"Pelo ponto da estação nos limites das 22 UGRHIs. Postos com coordenada arredondada no inventário ou na divisa "
                  f"do Estado ficam como '{FORA}'."),
        ("Chuva horária", "As estações convencionais da ANA medem uma vez por dia. Dados horários ou de 15 minutos só existem nas "
                          "estações automáticas (telemétricas), e a ANA hoje os entrega apenas pela API nova, com cadastro "
                          "(identificador e senha): https://www.snirh.gov.br/dadoshidrometereologicos/manual. O web service "
                          "antigo não devolveu chuva para nenhuma estação automática de SP testada."),
        ("Arquivos", "Esta pasta: inventário, mensal e anual por posto, médias por UGRHI. Pasta diario/: chuva diária por posto, "
                     "um arquivo por UGRHI. Chuva_ANA_SP_1980-2026_csv.zip: tudo em CSV (separador ponto e vírgula, vírgula "
                     "decimal, UTF-8), com o diário do Estado inteiro num só arquivo."),
        ("No R", 'read.csv2("diario.csv", fileEncoding = "UTF-8-BOM", check.names = FALSE, colClasses = c(data = "Date"))'),
        ("No Python", 'pd.read_csv("diario.csv", sep=";", decimal=",", parse_dates=["data"], encoding="utf-8-sig")'),
    ]


def _cabecalho_postos(df: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    nomes = inv.set_index("codigo").nome
    return df.rename(columns=lambda c: f"{c} {nomes.get(c, '')}".strip())


FMT_INV = {"latitude": "num2", "longitude": "num2", "altitude_m": "int", "media_anual_mm": "num", "pct_dias_consistidos": "num",
           "dias_com_dado": "int", "anos_completos": "int", "inventario_inicio": "data", "inventario_fim": "data",
           "primeiro_dia": "data", "ultimo_dia": "data"}


def escrever_excel(r: dict) -> list[Path]:
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / "diario").mkdir(exist_ok=True)
    inv, nomes = r["inventario"], ugrhi.nomes_regioes()
    texto = leia_me(r)
    saidas = []

    arq = DESTINO / "Chuva_ANA_SP_1980-2026_mensal_anual.xlsx"
    p = Pasta(arq)
    p.texto("LEIA-ME", texto)
    p.tabela("Inventario", inv, formatos=FMT_INV, congelar=(1, 2))
    p.tabela("Anual", _cabecalho_postos(r["anual"], inv), formatos={"ano": "int"}, altura_cabecalho=60)
    p.tabela("Mensal", _cabecalho_postos(r["mensal"], inv), formatos={"mes": "mes"}, altura_cabecalho=60)
    p.tabela("Mensal_dias_com_dado", _cabecalho_postos(r["dias_mes"], inv), formatos={"mes": "mes"}, fmt_padrao="int",
             altura_cabecalho=60)
    for k, rot, fmt in (("anual", "ano", "int"), ("mensal", "mes", "mes"), ("diario", "data", "data")):
        df = r["media"][k].rename(columns=lambda c: nomes.get(c, c))
        df.index.name = rot
        p.tabela(f"Media_UGRHI_{k.replace('diario', 'diaria')}", df, formatos={rot: fmt}, altura_cabecalho=45)
    p.tabela("Postos_por_ano", r["contagem"].rename(columns=lambda c: nomes.get(c, c)), formatos={"ano": "int"}, fmt_padrao="int")
    p.tabela("Controle_qualidade", r["removidos"], formatos={"data": "data", "valor_removido_mm": "num"}, congelar=(1, 1))
    p.fechar()
    saidas.append(arq)

    grupos = [(s, nomes.get(s, s)) for s in ugrhi.regioes() if s != "SP"] + [("", FORA)]
    for sig, rotulo in grupos:
        cods = inv[(inv.ugrhi == sig) & (inv.serie_desde_1980 == "sim")].codigo.tolist()
        if not cods:
            continue
        d = r["diario"][cods].dropna(how="all")
        nome_arq = f"Chuva_ANA_SP_diario_{sig or 'fora_das_UGRHIs'}.xlsx"
        p = Pasta(DESTINO / "diario" / nome_arq)
        p.texto("LEIA-ME", [("#", f"Chuva diária dos postos da ANA: {rotulo}")] + texto[1:])
        p.tabela("Postos", inv[inv.codigo.isin(cods)], formatos=FMT_INV, congelar=(1, 2))
        p.tabela("Diario", _cabecalho_postos(d, inv), formatos={"data": "data"}, altura_cabecalho=60)
        p.fechar()
        saidas.append(DESTINO / "diario" / nome_arq)
        log.info("diário %s: %d postos", rotulo, len(cods))
    return saidas


def _csv(df: pd.DataFrame, rotulo: str | None = None, casas: int = 2) -> bytes:
    df = df.copy()
    if rotulo:
        df.index.name = rotulo
    floats = df.select_dtypes("number").columns
    df[floats] = df[floats].astype("float64").round(casas)
    texto = df.to_csv(sep=";", decimal=",", date_format="%Y-%m-%d")
    return ("﻿" + texto).encode("utf-8")


def escrever_csv(r: dict) -> Path:
    arq = DESTINO / "Chuva_ANA_SP_1980-2026_csv.zip"
    nomes = ugrhi.nomes_regioes()
    leia = "\n".join(f"{a}: {b}" if a != "#" else b for a, b in leia_me(r)) + "\n"
    with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("LEIA-ME.txt", leia.encode("utf-8"))
        z.writestr("inventario.csv", _csv(r["inventario"].set_index("codigo"), casas=4).replace(b",0;", b";"))
        z.writestr("diario.csv", _csv(r["diario"], "data"))
        mensal = r["mensal"].copy()
        mensal.index = mensal.index.strftime("%Y-%m")
        z.writestr("mensal.csv", _csv(mensal, "mes"))
        dias = r["dias_mes"].copy()
        dias.index = dias.index.strftime("%Y-%m")
        z.writestr("mensal_dias_com_dado.csv", _csv(dias, "mes"))
        z.writestr("anual.csv", _csv(r["anual"], "ano"))
        for k, rot in (("diario", "data"), ("mensal", "mes"), ("anual", "ano")):
            df = r["media"][k].rename(columns=lambda c: nomes.get(c, c)).copy()
            if k == "mensal":
                df.index = df.index.strftime("%Y-%m")
            z.writestr(f"media_ugrhi_{k.replace('diario', 'diaria')}.csv", _csv(df, rot))
        z.writestr("postos_por_ano.csv", _csv(r["contagem"].rename(columns=lambda c: nomes.get(c, c)), "ano"))
        z.writestr("controle_qualidade.csv", _csv(r["removidos"].set_index("codigo")))
    return arq


def main() -> None:
    base.configurar_log()
    r = montar()
    log.info("ANA SP: %d estações no inventário, %d com série desde 1980, %d dias", len(r["inventario"]),
             r["diario"].shape[1], len(r["diario"]))
    for a in escrever_excel(r) + [escrever_csv(r)]:
        log.info("%s: %.1f MB", a.relative_to(config.RAIZ), a.stat().st_size / 1e6)


if __name__ == "__main__":
    main()
