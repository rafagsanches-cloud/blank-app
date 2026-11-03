"""Aplicativo: Chuva em São Paulo por UGRHI – satélites e postos pluviométricos (1980–hoje).

Rodar:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import datetime as dt
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chuva_sp import config, fontes, indices

st.set_page_config(page_title="Chuva SP – satélites e postos", page_icon="🌧️", layout="wide")

# Paleta categórica de referência (ordem fixa; a cor acompanha o produto, nunca a posição)
CORES = {
    "CHIRPS": "#2a78d6",
    "IMERG": "#eb6834",
    "PERSIANN": "#1baf7a",
    "CMORPH": "#eda100",
    "GPCP": "#e87ba4",
    "POSTOS": "#008300",
}
SEQ_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGENTE = [[0, "#d03b3b"], [0.5, "#f0efec"], [1, "#2a78d6"]]  # vermelho = mais seco, azul = mais úmido
P = config.PROCESSADOS


# ------------------------------------------------------------------ dados
@st.cache_data
def ugrhis() -> pd.DataFrame:
    return pd.read_csv(config.UGRHI_DIR / "ugrhi_sp.csv")


@st.cache_data
def geojson() -> dict:
    return json.loads((config.UGRHI_DIR / "UGRHI_SP_simplificado.geojson").read_text(encoding="utf-8"))


def nomes() -> dict:
    d = {r.sigla: f"{r.codigo:02d} – {r.nome}" for r in ugrhis().itertuples()}
    d["SP"] = "Estado de São Paulo"
    return d


def produtos_disponiveis() -> list[str]:
    return [p for p in list(config.PRODUTOS) + ["POSTOS"] if (P / f"{'POSTOS_MEDIA' if p == 'POSTOS' else p}_diario.parquet").exists()]


@st.cache_data
def serie(produto: str, escala: str) -> pd.DataFrame | None:
    arq = P / f"{'POSTOS_MEDIA' if produto == 'POSTOS' else produto}_{escala}.parquet"
    return pd.read_parquet(arq) if arq.exists() else None


@st.cache_data
def postos_inv() -> pd.DataFrame | None:
    a = P / "postos_inventario.csv"
    return pd.read_csv(a, parse_dates=["primeiro_dia", "ultimo_dia"]) if a.exists() else None


@st.cache_data
def postos_diario() -> pd.DataFrame | None:
    a = P / "POSTOS_diario.parquet"
    return pd.read_parquet(a) if a.exists() else None


@st.cache_data
def validacao() -> pd.DataFrame | None:
    a = P / "validacao_sat_x_postos.csv"
    return pd.read_csv(a) if a.exists() else None


@st.cache_data
def contornos() -> dict:
    """Anéis externos de cada UGRHI (lon, lat) com None separando partes – para desenhar sem basemap."""
    out = {}
    for f in geojson()["features"]:
        g = f["geometry"]
        polis = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        xs, ys = [], []
        for pol in polis:
            anel = pol[0]
            xs += [c[0] for c in anel] + [None]
            ys += [c[1] for c in anel] + [None]
        out[f["properties"]["sigla"]] = (xs, ys)
    return out


def figura_mapa(valores: pd.Series | None = None, escala=None, faixa=None, titulo="", unidade="mm",
                altura: int = 520) -> go.Figure:
    """Mapa das UGRHIs com polígonos preenchidos (sem depender de mapa-base externo)."""
    from plotly.colors import sample_colorscale

    fig = go.Figure()
    nm = nomes()
    if valores is not None and np.isfinite(valores.values).any():
        vmin, vmax = faixa if faixa else (np.nanmin(valores.values), np.nanmax(valores.values))
    for sig, (xs, ys) in contornos().items():
        v = None if valores is None else valores.get(sig, np.nan)
        if v is not None and np.isfinite(v):
            t = 0.5 if vmax == vmin else (v - vmin) / (vmax - vmin)
            cor = sample_colorscale(escala, [min(max(t, 0), 1)])[0]
            txt = f"{nm[sig]}<br>{v:,.0f} {unidade}".replace(",", ".")
        else:
            cor, txt = "rgba(0,0,0,0)", nm[sig]
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=cor, mode="lines",
                                 line=dict(color="#fcfcfb" if valores is not None else "#898781", width=1),
                                 hoveron="fills", text=txt, hoverinfo="text", showlegend=False))
    if valores is not None and np.isfinite(valores.values).any():
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", showlegend=False, hoverinfo="skip",
                                 marker=dict(colorscale=escala, cmin=vmin, cmax=vmax, color=[vmin],
                                             colorbar=dict(title=unidade, thickness=14))))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1 / np.cos(np.deg2rad(22.5)))
    fig.update_layout(title=titulo, height=altura, margin=dict(l=0, r=0, t=40, b=0),
                      plot_bgcolor="rgba(0,0,0,0)", hovermode="closest")
    return fig


def rotulo_produto(p: str) -> str:
    return "Postos (média simples)" if p == "POSTOS" else p


def estilo(fig: go.Figure, altura: int = 420) -> go.Figure:
    fig.update_layout(
        height=altura, margin=dict(l=10, r=10, t=90, b=10), hovermode="x unified",
        title=dict(y=0.98, yanchor="top", x=0, xanchor="left"),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(137,135,129,0.25)", zeroline=False)
    fig.update_traces(selector=dict(type="scatter"), line=dict(width=2))
    return fig


# ------------------------------------------------------------------ cabeçalho
st.title("🌧️ Chuva em São Paulo por UGRHI")
st.caption(
    "Estimativas de satélite (CHIRPS, IMERG, PERSIANN, CMORPH, GPCP) e postos pluviométricos (ANA/DAEE) "
    "nas 22 Unidades de Gerenciamento de Recursos Hídricos, de 1980 até hoje. Médias areais ponderadas por área."
)

disp = produtos_disponiveis()
if not disp:
    st.warning("Ainda não há dados processados. Rode `python -m chuva_sp` (ou use a aba **Buscar dados**).")

N = nomes()
regioes = list(N)

with st.sidebar:
    st.header("Filtros")
    regiao = st.selectbox("UGRHI / Estado", regioes, index=len(regioes) - 1, format_func=lambda s: N[s])
    escolhidos = st.multiselect("Produtos", disp, default=[p for p in ("CHIRPS", "IMERG", "PERSIANN", "CMORPH", "POSTOS") if p in disp],
                                format_func=rotulo_produto)
    escala = st.radio("Escala", ["anual", "mensal", "diario", "horario"],
                      format_func=lambda e: {"anual": "Anual", "mensal": "Mensal", "diario": "Diária", "horario": "Horária"}[e],
                      horizontal=True)
    anos = st.slider("Período", 1980, dt.date.today().year, (1981, dt.date.today().year))
    st.divider()
    st.caption("Código: pacote `chuva_sp` (Python) e `R/ClimdexSP.R` (índices tipo RClimDex).")

abas = st.tabs(["📈 Séries", "🗺️ Mapa", "⚡ Extremos (ETCCDI)", "📍 Postos", "✅ Validação", "🛰️ Produtos e fontes", "⬇️ Excel e busca"])

# ------------------------------------------------------------------ 1. séries
with abas[0]:
    fig = go.Figure()
    tabela = {}
    for p in escolhidos:
        df = serie(p, escala)
        if df is None or regiao not in df:
            continue
        s = df[regiao]
        idx = s.index if escala != "anual" else pd.to_datetime(s.index.astype(str) + "-07-01")
        s = pd.Series(s.values, index=pd.DatetimeIndex(idx))
        s = s[(s.index.year >= anos[0]) & (s.index.year <= anos[1])]
        if escala == "horario" and len(s) > 200_000:
            st.info(f"{p}: série horária longa – mostrando os últimos 365 dias do período (o Excel tem tudo).")
            s = s[s.index >= s.index.max() - pd.Timedelta(days=365)]
        tabela[rotulo_produto(p)] = s
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=rotulo_produto(p), mode="lines",
                                 line=dict(color=CORES[p], width=3 if p == "POSTOS" else 2)))
    if tabela:
        unid = {"anual": "mm/ano", "mensal": "mm/mês", "diario": "mm/dia", "horario": "mm/h"}[escala]
        fig.update_layout(title=f"{N[regiao]} – chuva {escala.replace('diario', 'diária').replace('horario', 'horária')}", yaxis_title=unid)
        st.plotly_chart(estilo(fig), width="stretch")
        t = pd.DataFrame(tabela)
        c1, c2 = st.columns([3, 1])
        with c1:
            with st.expander("Tabela"):
                st.dataframe(t.round(2), width="stretch")
        with c2:
            st.download_button("Baixar seleção (CSV)", t.to_csv().encode("utf-8"), f"chuva_{regiao}_{escala}.csv", "text/csv")
        if escala in ("anual", "mensal"):
            r = t.describe().T[["count", "mean", "std", "min", "max"]].round(1)
            r.columns = ["n", "média", "desvio", "mín", "máx"]
            st.dataframe(r, width="stretch")
    elif escolhidos:
        st.info("Sem dados para esta combinação (os produtos horários são só CMORPH e IMERG).")

# ------------------------------------------------------------------ 2. mapa
with abas[1]:
    c1, c2 = st.columns([1, 3])
    with c1:
        p_mapa = st.selectbox("Produto", [p for p in disp], format_func=rotulo_produto, key="pmapa")
        modo = st.radio("Mostrar", ["Média anual no período", "Tendência (Sen, mm/década)"])
    an = serie(p_mapa, "anual")
    if an is not None:
        an = an[(an.index >= anos[0]) & (an.index <= anos[1])]
        u = ugrhis()
        if modo.startswith("Média"):
            val = an[u.sigla].mean()
            escala_cor, titulo, faixa = SEQ_AZUL, f"{rotulo_produto(p_mapa)}: média anual {anos[0]}–{anos[1]} (mm)", None
        else:
            val = pd.Series({s: indices.tendencia(an.index, an[s]).get("sen_por_decada", np.nan) for s in u.sigla})
            m = np.nanmax(np.abs(val.values)) if np.isfinite(val.values).any() else 1
            escala_cor, titulo, faixa = DIVERGENTE, f"{rotulo_produto(p_mapa)}: tendência de Sen {anos[0]}–{anos[1]} (mm/década)", (-m, m)
        d = pd.DataFrame({"sigla": u.sigla, "UGRHI": [N[s] for s in u.sigla], "valor": val.reindex(u.sigla).values})
        unid = "mm" if modo.startswith("Média") else "mm/década"
        fig = figura_mapa(val.reindex(u.sigla), escala_cor, faixa, titulo, unid)
        with c2:
            st.plotly_chart(fig, width="stretch")
        with st.expander("Tabela por UGRHI"):
            st.dataframe(d[["UGRHI", "valor"]].round(1), width="stretch", hide_index=True)

# ------------------------------------------------------------------ 3. extremos
with abas[2]:
    st.markdown("Índices do ETCCDI calculados como no **RClimDex** (mesmas definições do `R/ClimdexSP.R`, "
                "conferidas com o pacote `climdex.pcic`). Base dos percentis: 1981–2010 (ou a série toda se não houver dados).")
    c1, c2 = st.columns([1, 3])
    with c1:
        ind = st.selectbox("Índice", list(indices.DESCRICAO), format_func=lambda k: f"{k} – {indices.DESCRICAO[k][0]}")
    fig = go.Figure()
    linhas = []
    for p in escolhidos:
        d = serie(p, "diario")
        if d is None or regiao not in d:
            continue
        a = indices.indices_anuais(d[regiao])
        a = a[(a.index >= anos[0]) & (a.index <= anos[1])]
        fig.add_trace(go.Scatter(x=a.index, y=a[ind], name=rotulo_produto(p), mode="lines+markers",
                                 line=dict(color=CORES[p]), marker=dict(size=6)))
        linhas.append({"produto": rotulo_produto(p), **indices.tendencia(a.index, a[ind])})
    if linhas:
        fig.update_layout(title=f"{ind} – {N[regiao]}", yaxis_title=indices.DESCRICAO[ind][1])
        with c2:
            st.plotly_chart(estilo(fig, 400), width="stretch")
        t = pd.DataFrame(linhas).set_index("produto").round(4)
        t["significativa (p<0,05)"] = np.where(t["mk_p"] < 0.05, "sim", "não")
        st.dataframe(t, width="stretch")
        st.caption("Sen e linear por década; MK = teste de Mann-Kendall. Para QC, gráficos por índice e lote completo use o ClimdexSP em R.")

# ------------------------------------------------------------------ 4. postos
with abas[3]:
    inv = postos_inv()
    if inv is None:
        st.info("Inventário de postos ainda não gerado.")
    else:
        c1, c2 = st.columns([2, 3])
        with c1:
            st.metric("Postos em SP com dados desde 1980", f"{len(inv):,}".replace(",", "."))
            st.dataframe(inv.groupby("rede").size().rename("postos"), width="stretch")
            cont = pd.read_csv(P / "postos_n_por_ano.csv", index_col=0)
            figc = go.Figure(go.Bar(x=cont.index, y=cont["SP"], marker_color=CORES["CHIRPS"], name="postos"))
            figc.update_layout(title="Postos com dado por ano (Estado)", yaxis_title="postos")
            st.plotly_chart(estilo(figc, 300), width="stretch")
        with c2:
            fig = figura_mapa(titulo="Postos pluviométricos (GHCN-Daily)")
            for i, (rede, g) in enumerate(inv.groupby("rede")):
                fig.add_trace(go.Scatter(x=g.lon, y=g.lat, mode="markers", name=rede,
                                         marker=dict(size=8, color=["#2a78d6", "#eb6834", "#1baf7a"][i % 3],
                                                     line=dict(width=1, color="#fcfcfb")),
                                         text=g.id + " – " + g.nome + " (" + g.ugrhi + ")", hoverinfo="text"))
            fig.update_layout(legend=dict(orientation="h", y=-0.02), showlegend=True)
            st.plotly_chart(fig, width="stretch")
        dd = postos_diario()
        sel_ugrhi = st.selectbox("Filtrar postos pela UGRHI", ["(todas)"] + list(ugrhis().sigla), format_func=lambda s: N.get(s, s))
        lista = inv if sel_ugrhi == "(todas)" else inv[inv.ugrhi == sel_ugrhi]
        posto = st.selectbox("Posto", lista.id, format_func=lambda i: f"{i} – {inv.set_index('id').loc[i, 'nome']}")
        if dd is not None and posto in dd:
            s = dd[posto].dropna()
            m = s.resample("MS").sum(min_count=28)
            figp = go.Figure(go.Bar(x=m.index, y=m.values, marker_color=CORES["POSTOS"], name="mm/mês"))
            figp.update_layout(title=f"{posto} – total mensal (mm)", yaxis_title="mm/mês")
            st.plotly_chart(estilo(figp, 320), width="stretch")
        st.dataframe(lista, width="stretch", height=300)

# ------------------------------------------------------------------ 5. validação
with abas[4]:
    v = validacao()
    if v is None:
        st.info("Validação ainda não gerada.")
    else:
        st.markdown("Comparação **pixel do satélite × pluviômetro** (dias com os dois dados). "
                    "Métricas: r de Pearson, viés (%), RMSE, KGE e POD/FAR/CSI (limiar 1 mm/dia).")
        met = st.selectbox("Métrica", ["diario_r_pearson", "diario_vies_pct", "diario_kge", "diario_rmse", "diario_csi", "mensal_r_pearson", "mensal_vies_pct"])
        fig = go.Figure()
        for p in [x for x in CORES if x in v.produto.unique()]:
            fig.add_trace(go.Box(y=v.loc[v.produto == p, met], name=p, marker_color=CORES[p], boxmean=True))
        fig.update_layout(title=f"{met} por produto (um ponto por posto)", showlegend=False, hovermode="closest")
        st.plotly_chart(estilo(fig, 380), width="stretch")
        res = v.groupby("produto")[[c for c in v.columns if c.startswith(("diario_", "mensal_"))]].median().round(3)
        st.markdown("**Mediana entre postos**")
        st.dataframe(res.T, width="stretch")
        with st.expander("Tabela completa por posto"):
            st.dataframe(v, width="stretch")

# ------------------------------------------------------------------ 6. produtos e fontes
with abas[5]:
    from chuva_sp.excel import tabela_produtos

    st.subheader("Produtos de precipitação por satélite")
    st.dataframe(tabela_produtos().set_index("Produto"), width="stretch")
    st.subheader("Bases de dados")
    st.dataframe(fontes.tabela(), width="stretch", hide_index=True)

# ------------------------------------------------------------------ 7. excel e busca
with abas[6]:
    st.subheader("Pastas de trabalho prontas")
    arqs = sorted(config.SAIDAS.glob("*.xlsx"))
    if not arqs:
        st.info("Nenhum Excel em `saidas/` – rode `python -m chuva_sp`.")
    for a in arqs:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{a.name}** – {a.stat().st_size / 1e6:.1f} MB")
        c2.download_button("Baixar", a.read_bytes(), a.name, key=a.name)

    st.subheader("Buscar dados de satélite agora")
    st.caption("Baixa os produtos escolhidos direto das fontes abertas (AWS S3), calcula as médias por UGRHI e monta um Excel. "
               "Períodos longos de produtos horários levam vários minutos.")
    with st.form("buscar"):
        ps = st.multiselect("Produtos", list(config.PRODUTOS), default=["CHIRPS"])
        c1, c2 = st.columns(2)
        ini = c1.date_input("Início", dt.date(2024, 1, 1), min_value=dt.date(1980, 1, 1))
        fim = c2.date_input("Fim", dt.date.today())
        ok = st.form_submit_button("Buscar e gerar Excel")
    if ok and ps:
        from chuva_sp import excel, pipeline

        sat = {}
        barra = st.progress(0.0)
        for i, p in enumerate(ps):
            with st.spinner(f"Baixando {p}…"):
                sat[p] = pipeline.series_satelite(p, inicio=ini, fim=fim)
            barra.progress((i + 1) / len(ps))
        destino = config.CACHE / f"busca_{dt.datetime.now():%Y%m%d_%H%M%S}.xlsx"
        excel.escrever_principal(destino, sat, None, None, pipeline.leia_me(sat, None, {}))
        st.success("Pronto!")
        st.download_button("Baixar Excel", destino.read_bytes(), f"Chuva_SP_{ini:%Y%m%d}-{fim:%Y%m%d}.xlsx")
