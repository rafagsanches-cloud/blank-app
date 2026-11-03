"""Orquestra download, agregação, validação e exportação para Excel.

Uso:  python -m chuva_sp                 # tudo (satélites + postos + Excel)
      python -m chuva_sp --so-excel      # só refaz o Excel a partir do cache
      python -m chuva_sp --produtos CHIRPS PERSIANN
      python -m chuva_sp --ana --inmet   # inclui ANA/INMET (precisa de acesso a esses sites)
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging

import pandas as pd

from . import agregacao as ag
from . import config, excel, ugrhi, validacao
from .satelites import base

log = logging.getLogger("chuva_sp")
TODOS = ["CHIRPS", "IMERG", "PERSIANN", "CMORPH", "GPCP"]


# ---------------------------------------------------------------- satélites
def series_satelite(produto: str, workers: int = 16, inicio=config.DATA_INICIO, fim=config.DATA_FIM) -> dict[str, pd.DataFrame]:
    """Devolve {'horario'?, 'diario', 'mensal', 'anual'} recortados no período (padrão 1980–hoje)."""
    from .satelites import chirps, imerg, noaa_cdr

    out: dict[str, pd.DataFrame] = {}
    if produto == "CHIRPS":
        out["diario"] = chirps.baixar(inicio, fim, workers=workers)
    elif produto == "PERSIANN":
        out["diario"] = noaa_cdr.persiann(inicio, fim, workers=workers)
    elif produto == "CMORPH":
        out["horario"] = noaa_cdr.cmorph(inicio, fim, workers=max(workers, 24))
    elif produto == "IMERG":
        out["horario"] = imerg.baixar(inicio, fim, workers=4)
    elif produto == "GPCP":
        out["diario"] = noaa_cdr.gpcp_diario(inicio, fim, workers=workers)
        out["mensal"] = noaa_cdr.gpcp_mensal(inicio, fim, workers=workers)
        m = out["mensal"]
        anual = m.resample("YS").sum(min_count=12)
        anual.index = anual.index.year
        anual.index.name = "ano"
        out["anual"] = anual
    if "horario" in out:
        out["diario"] = ag.horario_para_diario(out["horario"])
    if "mensal" not in out:
        out["mensal"] = ag.diario_para_mensal(out["diario"])
    if "anual" not in out:
        out["anual"] = ag.diario_para_anual(out["diario"])
    return {k: ag.recortar_periodo(v, inicio, fim) for k, v in out.items()}


# ---------------------------------------------------------------- postos
def series_postos(ana: bool = False, inmet: bool = False) -> dict:
    from .estacoes import ghcn

    inv, diario = ghcn.baixar()
    if ana:  # ANA HidroWeb (precisa de acesso a telemetriaws1.ana.gov.br)
        from .estacoes import ana as m_ana

        inv_a, d_a = m_ana.baixar_todas_sp()
        inv_a = inv_a.rename(columns={"Codigo": "id", "Nome": "nome", "Latitude": "lat", "Longitude": "lon"})
        inv_a["rede"], inv_a["fonte"], inv_a["codigo_original"] = "ANA (HidroWeb)", "ANA HidroWeb", inv_a["id"]
        inv_a["id"] = "ANA_" + inv_a["id"].astype(str)
        d_a.columns = ["ANA_" + str(c) for c in d_a.columns]
        inv = pd.concat([inv, inv_a[inv.columns.intersection(inv_a.columns)]], ignore_index=True)
        diario = diario.join(d_a, how="outer")
    out = {"inventario": inv, "diario": diario}
    out["mensal"] = ag.diario_para_mensal(diario)
    out["anual"] = ag.diario_para_anual(diario)
    out["contagem"] = ag.contagem_postos(diario, inv)
    med = ag.media_postos_por_ugrhi(diario, inv)
    out["media_ugrhi"] = {"diario": med, "mensal": ag.diario_para_mensal(med), "anual": ag.diario_para_anual(med)}
    for k in ("diario", "mensal", "anual"):
        out[k] = ag.recortar_periodo(out[k])
        out["media_ugrhi"][k] = ag.recortar_periodo(out["media_ugrhi"][k])
    if inmet:  # horário das automáticas do INMET (precisa de acesso a portal.inmet.gov.br)
        from .estacoes import inmet as m_inmet

        out["inmet_inventario"], out["inmet_horario"] = m_inmet.baixar()
    return out


# ---------------------------------------------------------------- textos
def leia_me(sat: dict, postos: dict | None, lags: dict) -> list[tuple[str, str]]:
    hoje = dt.date.today().strftime("%d/%m/%Y")
    L = [
        ("#", "Chuva no Estado de São Paulo por UGRHI – satélites e postos pluviométricos (1980–hoje)"),
        ("Gerado em", hoje + " pelo programa chuva_sp (Python) – ver README do repositório."),
        ("Área", "22 UGRHIs de SP (limites DAEE/SIBH) + 'Estado de São Paulo' (soma das UGRHIs)."),
        ("Unidade", "mm (total no intervalo: hora, dia, mês ou ano)."),
        ("Método areal", "Média ponderada pela fração de cada pixel dentro da UGRHI x cos(latitude). Pixels sem dado são ignorados; exige ≥50% da área com dado."),
        ("Horário", "Produtos horários em UTC (coluna extra com horário local UTC-3). Dia = 00–24 UTC."),
        ("Faltas (padrão RClimDex/ETCCDI)", "Dia: falta se alguma hora faltar. Mês: falta se >3 dias faltarem. Ano: falta se >15 dias faltarem (por isso o ano corrente aparece vazio)."),
        ("Planilhas *_UGRHI_satelites", "Uma linha por produto e data; use o filtro da coluna 'produto'. Inclui 'POSTOS (média simples)': média aritmética dos postos de cada UGRHI (mín. 3 postos no dia)."),
        ("Planilhas Postos_*", "Uma coluna por posto (código GHCN). Inventário com rede (ANA/DAEE), código original, UGRHI e período."),
        ("Validacao_sat_x_postos", "Comparação pixel x posto: viés (%), r de Pearson, RMSE, MAE, KGE, POD/FAR/CSI (limiar 1 mm/dia). Defasagem aplicada por produto: " + (", ".join(f"{k} {v:+d} dia" for k, v in lags.items()) or "—") + "."),
        ("Dados horários", "CMORPH e IMERG em pastas separadas (Chuva_SP_horario_*.xlsx) por causa do limite de linhas do Excel."),
        ("", ""),
        ("#", "Cobertura efetiva"),
    ]
    for p, s in sat.items():
        d = s["diario"].dropna(how="all")
        L.append((p, f"{config.PRODUTOS[p]['nome']} – diário de {d.index.min():%d/%m/%Y} a {d.index.max():%d/%m/%Y}" + (" (+ horário)" if "horario" in s else "") + (" (mensal desde 1980)" if p == "GPCP" else "")))
    if postos is not None:
        inv = postos["inventario"]
        L.append(("Postos (GHCN-Daily)", f"{len(inv)} postos em SP ({(inv.rede == 'DAEE-SP').sum()} DAEE, {(inv.rede == 'ANA (HidroWeb)').sum()} ANA). A maioria das séries vai até 1997–2005."))
    L += [
        ("", ""),
        ("#", "Limitações"),
        ("ANA, DAEE/SIBH, INMET", "Os servidores destes órgãos não estavam acessíveis no ambiente em que esta pasta foi gerada. O código para baixá-los está pronto (python -m chuva_sp --ana --inmet) e deve ser rodado em uma máquina com acesso."),
        ("IMERG", "Versão 'Late Run' v07 (acesso aberto). A 'Final Run' exige login NASA Earthdata."),
        ("CMORPH", "Grade de 0,25° horária (a de 8 km/30 min existe, mas não foi usada pelo volume). Em SP, os totais do CMORPH CDR ficam ~18% abaixo dos outros produtos (média anual 2001–2020 no Estado: ~1.260 mm, contra ~1.480–1.520 mm). A soma das 24 horas confere com o arquivo diário oficial, portanto a diferença é do produto e não do processamento."),
        ("GPCP", "Grade grossa (2,5° mensal; 1° diário). Útil como referência climática de longo prazo."),
        ("TRMM", "O IMERG v07 já incorpora a era TRMM (1998–2014). O TRMM 3B42 original exige login NASA Earthdata."),
    ]
    return L


# ---------------------------------------------------------------- execução
def salvar_processados(sat: dict, postos: dict | None, valid: pd.DataFrame | None) -> None:
    config.PROCESSADOS.mkdir(parents=True, exist_ok=True)
    for p, s in sat.items():
        for esc, df in s.items():
            df.astype("float32").round(2).to_parquet(config.PROCESSADOS / f"{p}_{esc}.parquet", compression="zstd")
    if postos is not None:
        postos["inventario"].to_csv(config.PROCESSADOS / "postos_inventario.csv", index=False)
        for esc in ("diario", "mensal", "anual"):
            postos[esc].astype("float32").to_parquet(config.PROCESSADOS / f"POSTOS_{esc}.parquet", compression="zstd")
            postos["media_ugrhi"][esc].astype("float32").round(2).to_parquet(config.PROCESSADOS / f"POSTOS_MEDIA_{esc}.parquet", compression="zstd")
        postos["contagem"].to_csv(config.PROCESSADOS / "postos_n_por_ano.csv")
    if valid is not None and len(valid):
        valid.to_csv(config.PROCESSADOS / "validacao_sat_x_postos.csv", index=False)


def executar(produtos=TODOS, ana=False, inmet=False, workers=16, com_postos=True, com_validacao=True) -> dict:
    config.garantir_pastas()
    if not config.UGRHI_GPKG.exists():
        ugrhi.exportar_ugrhi()
    sat = {}
    for p in produtos:
        log.info("=== %s", p)
        sat[p] = series_satelite(p, workers)
    postos = series_postos(ana, inmet) if com_postos else None
    valid, lags = (None, {})
    if postos is not None and com_validacao:
        valid, lags = validacao.validar(postos["inventario"], postos["diario"], [p for p in produtos if p != "GPCP"])
    salvar_processados(sat, postos, valid)
    fim = config.DATA_FIM.year
    txt = leia_me(sat, postos, lags)
    arqs = [excel.escrever_principal(config.SAIDAS / f"Chuva_SP_1980-{fim}_satelites_e_postos.xlsx", sat, postos, valid, txt)]
    for p, s in sat.items():
        if "horario" in s:
            ini = s["horario"].index.min().year
            arqs.append(excel.escrever_horario(config.SAIDAS / f"Chuva_SP_horario_{p}_{ini}-{fim}.xlsx", p, s["horario"], txt))
    if postos is not None and "inmet_horario" in postos:
        h = postos["inmet_horario"]
        arqs.append(excel.escrever_horario(config.SAIDAS / f"Chuva_SP_horario_INMET_{h.index.min().year}-{fim}.xlsx", "INMET", h, txt))
    for a in arqs:
        log.info("Excel: %s (%.1f MB)", a, a.stat().st_size / 1e6)
    return {"satelites": sat, "postos": postos, "validacao": valid, "arquivos": arqs}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Chuva em SP por UGRHI: satélites + postos -> Excel")
    ap.add_argument("--produtos", nargs="+", default=TODOS, choices=TODOS)
    ap.add_argument("--sem-postos", action="store_true")
    ap.add_argument("--sem-validacao", action="store_true")
    ap.add_argument("--ana", action="store_true", help="baixa também a ANA/HidroWeb (precisa de acesso)")
    ap.add_argument("--inmet", action="store_true", help="baixa também o INMET horário (precisa de acesso)")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args(argv)
    base.configurar_log()
    executar(a.produtos, a.ana, a.inmet, a.workers, not a.sem_postos, not a.sem_validacao)


if __name__ == "__main__":
    main()
