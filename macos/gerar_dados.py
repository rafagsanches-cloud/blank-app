"""Gera os dados que o app macOS "Chuva SP" leva dentro dele (macos/ChuvaSP/Dados).

Rode na raiz do repositório depois de `python -m chuva_sp`:
    python macos/gerar_dados.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import shapely

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from chuva_sp import config, fontes, ugrhi  # noqa: E402
from chuva_sp.excel import tabela_produtos  # noqa: E402

DESTINO = RAIZ / "macos" / "ChuvaSP" / "Dados"
P = config.PROCESSADOS
PRODUTOS = {"CHIRPS": "CHIRPS", "IMERG": "IMERG", "PERSIANN": "PERSIANN", "CMORPH": "CMORPH", "GPCP": "GPCP", "POSTOS": "POSTOS_MEDIA"}


def salvar(nome: str, obj) -> None:
    (DESTINO / nome).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def limpo(v, casas=2):
    return None if v is None or not np.isfinite(v) else round(float(v), casas)


def main() -> None:
    (DESTINO / "diario").mkdir(parents=True, exist_ok=True)
    g = ugrhi.carregar_ugrhi()
    nomes = ugrhi.nomes_regioes()

    # regiões: anéis (externos e furos) simplificados, lon/lat com 3 casas
    regioes = []
    for r in g.itertuples():
        geo = r.geometry.simplify(0.003, preserve_topology=True)
        polis = [geo] if geo.geom_type == "Polygon" else list(geo.geoms)
        aneis = []
        for p in polis:
            for anel in [p.exterior, *p.interiors]:
                aneis.append([[round(x, 3), round(y, 3)] for x, y in anel.coords])
        regioes.append({"sigla": r.sigla, "codigo": int(r.codigo), "nome": r.nome, "rotulo": nomes[r.sigla],
                        "areaKm2": round(float(r.area_km2), 1), "aneis": aneis})
    regioes.append({"sigla": "SP", "codigo": 0, "nome": "Estado de São Paulo", "rotulo": "Estado de São Paulo",
                    "areaKm2": round(float(g.area_km2.sum()), 1), "aneis": []})
    salvar("regioes.json", regioes)

    # totais anuais oficiais de cada produto
    anual = []
    for prod, arq in PRODUTOS.items():
        a = pd.read_parquet(P / f"{arq}_anual.parquet")
        for s in a.columns:
            for ano, v in a[s].dropna().items():
                anual.append({"produto": prod, "sigla": s, "ano": int(ano), "mm": limpo(v, 1)})
    salvar("anual.json", anual)

    # séries mensais compactas: início + lista de valores (null = falta)
    mensal = []
    for prod, arq in PRODUTOS.items():
        m = pd.read_parquet(P / f"{arq}_mensal.parquet")
        for s in m.columns:
            x = m[s]
            ok = x.dropna()
            if ok.empty:
                continue
            x = x.loc[ok.index.min():ok.index.max()]
            mensal.append({"produto": prod, "sigla": s, "inicio": f"{x.index[0]:%Y-%m}", "valores": [limpo(v, 1) for v in x.values]})
    salvar("mensal.json", mensal)

    # séries diárias em Float32 (little-endian, NaN = falta) + índice
    indice = []
    for prod, arq in PRODUTOS.items():
        d = pd.read_parquet(P / f"{arq}_diario.parquet")
        for s in d.columns:
            x = d[s]
            ok = x.dropna()
            if len(ok) < 365:
                continue
            x = x.loc[ok.index.min():ok.index.max()].astype("float64").round(2).astype("<f4")
            nome = f"{prod}_{s}.f32"
            (DESTINO / "diario" / nome).write_bytes(x.to_numpy().tobytes())
            indice.append({"produto": prod, "sigla": s, "inicio": f"{x.index[0]:%Y-%m-%d}", "dias": int(len(x)), "arquivo": nome})
    salvar("diario_indice.json", indice)

    # postos, contagem por ano e validação
    inv = pd.read_csv(P / "postos_inventario.csv")
    salvar("postos.json", [
        {"id": r.id, "nome": r.nome, "rede": r.rede, "codigoOriginal": str(r.codigo_original), "sigla": r.ugrhi,
         "lat": round(r.lat, 4), "lon": round(r.lon, 4), "altitude": limpo(r.altitude, 0),
         "inicio": str(r.primeiro_dia)[:10], "fim": str(r.ultimo_dia)[:10], "dias": int(r.dias_validos_desde_1980)}
        for r in inv.itertuples()])
    c = pd.read_csv(P / "postos_n_por_ano.csv")
    salvar("postos_por_ano.json", [{"ano": int(r.ano), "sigla": s, "postos": int(getattr(r, s))}
                                   for r in c.itertuples() for s in c.columns if s != "ano"])
    v = pd.read_csv(P / "validacao_sat_x_postos.csv")
    salvar("validacao.json", [
        {"produto": r.produto, "estacao": r.estacao, "sigla": r.ugrhi, "rede": r.rede,
         "rDiario": limpo(r.diario_r_pearson, 3), "rMensal": limpo(r.mensal_r_pearson, 3),
         "viesPct": limpo(r.diario_vies_pct, 1), "kge": limpo(r.diario_kge, 3), "csi": limpo(r.diario_csi, 3),
         "diasComuns": int(r.diario_n)}
        for r in v.itertuples()])

    # tabelas de texto
    pr = tabela_produtos()
    cob = {"CHIRPS": "1981-01-01 a 2026-09-30", "IMERG": "1998-01-01 a 2026-11-03", "PERSIANN": "1983-01-01 a 2026-07-31",
           "CMORPH": "1998-01-01 a 2026-05-31", "GPCP": "1980-01 (mensal) e 1996-10-01 (diário) a 2026"}
    salvar("produtos.json", [{"produto": r["Produto"], "sensor": r["Tipo de Sensor Principal"], "serie": r["Série Histórica"],
                               "resolucao": r["Resolução Espacial"], "foco": r["Foco Principal"], "versao": r["Versão usada"],
                               "periodo": cob.get(r["Produto"], ""), "url": r["URL"]} for _, r in pr.iterrows()])
    salvar("fontes.json", [{"grupo": r.Grupo, "base": r.Base, "endereco": r["Endereço"], "descricao": r["Descrição"]}
                           for _, r in fontes.tabela().iterrows()])
    tam = sum(f.stat().st_size for f in DESTINO.rglob("*") if f.is_file())
    print(f"dados do app: {tam / 1e6:.1f} MB em {DESTINO}")


if __name__ == "__main__":
    main()
