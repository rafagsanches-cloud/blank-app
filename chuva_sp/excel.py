"""Gravação das pastas de trabalho do Excel (xlsxwriter, linha a linha, pouca memória)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import xlsxwriter

from . import config, fontes, ugrhi


class Pasta:
    def __init__(self, caminho: Path):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.wb = xlsxwriter.Workbook(str(caminho), {"constant_memory": True, "nan_inf_to_errors": False})
        self.f = {
            "cab": self.wb.add_format({"bold": True, "bg_color": "#1F4E78", "font_color": "white", "text_wrap": True, "valign": "top", "border": 1}),
            "num": self.wb.add_format({"num_format": "0.0"}),
            "num2": self.wb.add_format({"num_format": "0.00"}),
            "int": self.wb.add_format({"num_format": "0"}),
            "data": self.wb.add_format({"num_format": "dd/mm/yyyy"}),
            "mes": self.wb.add_format({"num_format": "mm/yyyy"}),
            "hora": self.wb.add_format({"num_format": "dd/mm/yyyy hh:mm"}),
            "titulo": self.wb.add_format({"bold": True, "font_size": 14, "font_color": "#1F4E78"}),
            "neg": self.wb.add_format({"bold": True}),
            "texto": self.wb.add_format({"text_wrap": True, "valign": "top"}),
        }

    def tabela(self, nome: str, df: pd.DataFrame, formatos: dict[str, str] | None = None, larguras: dict[str, int] | None = None,
               fmt_padrao: str = "num", congelar: tuple[int, int] = (1, 1), filtro: bool = True) -> None:
        """Escreve o DataFrame (índice vira coluna) linha a linha."""
        ws = self.wb.add_worksheet(nome[:31])
        df = df.reset_index() if df.index.name is not None or not isinstance(df.index, pd.RangeIndex) else df
        formatos = formatos or {}
        larguras = larguras or {}
        cols = list(df.columns)
        ws.write_row(0, 0, [str(c) for c in cols], self.f["cab"])
        fmts = []
        for j, c in enumerate(cols):
            s = df[c]
            if c in formatos:
                k = formatos[c]
            elif pd.api.types.is_datetime64_any_dtype(s):
                k = "data"
            elif pd.api.types.is_integer_dtype(s):
                k = "int"
            elif pd.api.types.is_float_dtype(s):
                k = fmt_padrao
            else:
                k = None
            fmts.append(self.f[k] if k else None)
            ws.set_column(j, j, larguras.get(c, 18 if k in ("hora",) else 12 if k else max(12, min(40, int(s.astype(str).str.len().max() or 10) + 2))))
        # converte para listas python (rápido) tratando NaN/NaT como célula vazia
        colunas_py = []
        for c in cols:
            s = df[c]
            if pd.api.types.is_datetime64_any_dtype(s):
                v = [None if pd.isna(x) else x.to_pydatetime() for x in s]
            elif pd.api.types.is_float_dtype(s):
                a = s.to_numpy(dtype=float)
                v = [None if not np.isfinite(x) else float(x) for x in a]
            else:
                v = [None if (x is None or (isinstance(x, float) and np.isnan(x))) else x for x in s.tolist()]
            colunas_py.append(v)
        for i in range(len(df)):
            r = i + 1
            for j in range(len(cols)):
                x = colunas_py[j][i]
                if x is None:
                    continue
                if isinstance(x, (dt.datetime, dt.date)):
                    ws.write_datetime(r, j, x, fmts[j])
                elif isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool):
                    ws.write_number(r, j, float(x), fmts[j])
                else:
                    ws.write_string(r, j, str(x), fmts[j])
        ws.freeze_panes(*congelar)
        if filtro and len(df):
            ws.autofilter(0, 0, len(df), len(cols) - 1)

    def texto(self, nome: str, linhas: list[tuple[str, str]]) -> None:
        ws = self.wb.add_worksheet(nome[:31])
        ws.set_column(0, 0, 32)
        ws.set_column(1, 1, 120)
        for i, (a, b) in enumerate(linhas):
            if a == "#":
                ws.write(i, 0, b, self.f["titulo"])
            else:
                ws.write(i, 0, a, self.f["neg"])
                ws.write(i, 1, b, self.f["texto"])

    def fechar(self) -> None:
        self.wb.close()


def _colunas_com_nomes(df: pd.DataFrame) -> pd.DataFrame:
    n = ugrhi.nomes_regioes()
    return df.rename(columns=lambda c: n.get(c, c))


def tabela_produtos() -> pd.DataFrame:
    linhas = []
    for k, p in config.PRODUTOS.items():
        linhas.append(
            {
                "Produto": k,
                "Tipo de Sensor Principal": p["sensor"],
                "Série Histórica": f"Desde {p['inicio'][:4]}",
                "Resolução Espacial": p["resolucao"],
                "Foco Principal": p["foco"],
                "Versão usada": p["nome"],
                "Escala nativa": p["escala_nativa"],
                "Fonte / acesso": p["fonte"],
                "URL": p["url"],
                "Citação": p["citacao"],
            }
        )
    return pd.DataFrame(linhas)


def tabela_ugrhi() -> pd.DataFrame:
    g = ugrhi.carregar_ugrhi()
    return pd.DataFrame({"sigla": g.sigla, "codigo": g.codigo, "nome": g.nome, "area_km2": g.area_km2.round(1), "fonte_limite": "DAEE/SIBH"})


def empilhar(series: dict[str, pd.DataFrame], rotulo_tempo: str) -> pd.DataFrame:
    """{produto: df(tempo x regiao)} -> tabela longa por produto com regiões nas colunas."""
    partes = []
    for p, df in series.items():
        d = df.astype("float64").round(2)
        d.index.name = rotulo_tempo
        d = d.reset_index()
        d.insert(0, "produto", p)
        partes.append(d)
    return pd.concat(partes, ignore_index=True)


def escrever_principal(caminho: Path, sat: dict, postos: dict | None, validacao: pd.DataFrame | None, leia_me: list) -> Path:
    """Pasta principal: anual, mensal e diário de satélites (por UGRHI) e postos."""
    px = Pasta(caminho)
    px.texto("LEIA-ME", leia_me)
    px.tabela("Produtos", tabela_produtos(), congelar=(1, 1), filtro=False)
    px.tabela("Fontes", fontes.tabela(), congelar=(1, 1), filtro=False)
    px.tabela("UGRHIs", tabela_ugrhi(), formatos={"area_km2": "num"}, filtro=False)

    for escala, rot, fmt in (("anual", "ano", "int"), ("mensal", "mes", "mes"), ("diario", "data", "data")):
        tab = empilhar({p: s[escala] for p, s in sat.items() if escala in s}, rot)
        if postos is not None and escala in postos.get("media_ugrhi", {}):
            m = postos["media_ugrhi"][escala].astype("float64").round(2)
            m.index.name = rot
            m = m.reset_index()
            m.insert(0, "produto", "POSTOS (média simples)")
            tab = pd.concat([tab, m], ignore_index=True)
        tab = _colunas_com_nomes(tab)
        px.tabela(f"{escala.capitalize()}_UGRHI_satelites".replace("Diario", "Diário"), tab, formatos={rot: fmt}, congelar=(1, 2))

    if postos is not None:
        inv = postos["inventario"].copy()
        px.tabela("Postos_inventario", inv, formatos={"lat": "num2", "lon": "num2", "altitude": "int"}, congelar=(1, 1))
        px.tabela("Postos_n_por_ano", postos["contagem"], fmt_padrao="int")
        for escala, rot, fmt in (("anual", "ano", "int"), ("mensal", "mes", "mes"), ("diario", "data", "data")):
            df = postos[escala].copy()
            df.index.name = rot
            px.tabela(f"Postos_{escala}".replace("diario", "diário"), df, formatos={rot: fmt}, congelar=(1, 1))
    if validacao is not None and len(validacao):
        px.tabela("Validacao_sat_x_postos", validacao, fmt_padrao="num2", congelar=(1, 3))
    px.fechar()
    return caminho


def escrever_horario(caminho: Path, produto: str, h: pd.DataFrame, leia_me: list) -> Path:
    px = Pasta(caminho)
    px.texto("LEIA-ME", leia_me)
    d = h.copy()
    d.index = pd.DatetimeIndex(d.index)
    d.index.name = "data_hora_UTC"
    d = d.round(2).reset_index()
    d.insert(1, "data_hora_local_UTC-3", d["data_hora_UTC"] + pd.Timedelta(hours=config.FUSO_LOCAL_H))
    d = _colunas_com_nomes(d)
    # Excel aceita até 1.048.575 linhas de dados por planilha
    lim = 1_048_000
    for k in range(0, len(d), lim):
        px.tabela(f"Horario_{produto}" + (f"_{k // lim + 1}" if len(d) > lim else ""), d.iloc[k:k + lim],
                  formatos={"data_hora_UTC": "hora", "data_hora_local_UTC-3": "hora"}, fmt_padrao="num2", congelar=(1, 2))
    px.fechar()
    return caminho
