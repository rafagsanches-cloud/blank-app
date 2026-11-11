"""Gera os dados da ANA (HidroWeb) que o app macOS "Chuva SP" leva dentro dele.

Grava só arquivos novos, com prefixo ana_, na pasta macos/ChuvaSP/Dados; os arquivos
gerados por gerar_dados.py ficam como estão. Rode na raiz do repositório:

    python -m chuva_sp.estacoes.ana        # baixa e organiza (precisa de acesso à ANA)
    python macos/gerar_dados_ana.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from chuva_sp import config, ugrhi  # noqa: E402

DESTINO = RAIZ / "macos" / "ChuvaSP" / "Dados"
P = config.PROCESSADOS
INICIO_MENSAL = pd.Timestamp("1980-01-01")
ANOS = list(range(1980, config.DATA_FIM.year + 1))


def salvar(nome: str, obj) -> None:
    (DESTINO / nome).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def limpo(v, casas=2):
    return None if v is None or not np.isfinite(v) else round(float(v), casas)


def f32(valores) -> bytes:
    return np.asarray(valores, dtype="float64").round(2).astype("<f4").tobytes()


def main() -> None:
    (DESTINO / "diario").mkdir(parents=True, exist_ok=True)
    inv = pd.read_csv(P / "ANA_inventario.csv", dtype={"id": str, "codigo_original": str})
    inv_ws = pd.read_csv(config.CACHE / "ANA" / "inventario_ws.csv", dtype=str)
    inv_ws = inv_ws[inv_ws.ugrhi.notna()]

    # média dos postos da ANA em cada UGRHI: mesmos formatos de anual.json, mensal.json e diario_indice.json
    a = pd.read_parquet(P / "ANA_MEDIA_anual.parquet")
    salvar("ana_anual.json", [{"produto": "ANA", "sigla": s, "ano": int(ano), "mm": limpo(v, 1)}
                              for s in a.columns for ano, v in a[s].dropna().items()])
    m = pd.read_parquet(P / "ANA_MEDIA_mensal.parquet")
    mensal = []
    for s in m.columns:
        x = m[s]
        ok = x.dropna()
        if ok.empty:
            continue
        x = x.loc[ok.index.min():ok.index.max()]
        mensal.append({"produto": "ANA", "sigla": s, "inicio": f"{x.index[0]:%Y-%m}", "valores": [limpo(v, 1) for v in x.values]})
    salvar("ana_mensal.json", mensal)
    d = pd.read_parquet(P / "ANA_MEDIA_diario.parquet")
    indice = []
    for s in d.columns:
        x = d[s]
        ok = x.dropna()
        if len(ok) < 365:
            continue
        x = x.loc[ok.index.min():ok.index.max()]
        nome = f"ANA_{s}.f32"
        (DESTINO / "diario" / nome).write_bytes(f32(x.values))
        indice.append({"produto": "ANA", "sigla": s, "inicio": f"{x.index[0]:%Y-%m-%d}", "dias": int(len(x)), "arquivo": nome})
    salvar("ana_diario_indice.json", indice)

    # postos: inventário + totais mensais e anuais de cada posto (matrizes Float32, uma linha por posto)
    pm = pd.read_parquet(P / "ANA_mensal.parquet")
    pa = pd.read_parquet(P / "ANA_anual.parquet")
    meses = pd.date_range(INICIO_MENSAL, pm.index.max(), freq="MS")
    pm = pm.reindex(meses)
    pa = pa.reindex(ANOS)
    inv = inv.sort_values(["ugrhi", "id"]).reset_index(drop=True)
    postos, mat_m, mat_a = [], [], []
    for k, r in enumerate(inv.itertuples()):
        postos.append({
            "id": r.id, "nome": str(r.nome), "municipio": str(r.municipio), "operadora": str(r.operadora), "sigla": r.ugrhi,
            "lat": round(float(r.lat), 4), "lon": round(float(r.lon), 4), "altitude": limpo(r.altitude, 0),
            "inicio": str(r.primeiro_dia)[:10], "fim": str(r.ultimo_dia)[:10], "dias": int(r.dias_validos_desde_1980),
            "anosCompletos": int(r.anos_completos), "mediaAnual": limpo(r.media_anual_mm, 0),
            "operando": bool(r.operando), "telemetrica": bool(r.telemetrica), "linha": k,
        })
        mat_m.append(pm[r.id].values)
        mat_a.append(pa[r.id].values)
    salvar("ana_postos.json", postos)
    (DESTINO / "ana_postos_mensal.f32").write_bytes(f32(np.vstack(mat_m)))
    (DESTINO / "ana_postos_anual.f32").write_bytes(f32(np.vstack(mat_a)))

    c = pd.read_csv(P / "ANA_n_por_ano.csv")
    c = c[c.ano <= config.DATA_FIM.year]
    salvar("ana_postos_por_ano.json", [{"ano": int(r.ano), "sigla": s, "postos": int(getattr(r, s))}
                                       for r in c.itertuples() for s in c.columns if s != "ano"])

    v = pd.read_csv(P / "validacao_sat_x_ana.csv", dtype={"estacao": str})
    salvar("ana_validacao.json", [
        {"produto": r.produto, "estacao": r.estacao, "sigla": r.ugrhi, "rede": "ANA (HidroWeb)",
         "rDiario": limpo(r.diario_r_pearson, 3), "rMensal": limpo(r.mensal_r_pearson, 3),
         "viesPct": limpo(r.diario_vies_pct, 1), "kge": limpo(r.diario_kge, 3), "csi": limpo(r.diario_csi, 3),
         "diasComuns": int(r.diario_n)}
        for r in v.itertuples()])

    contagem = inv_ws.groupby("ugrhi").size().to_dict()
    contagem["SP"] = int(len(inv_ws))
    baixado = dt.datetime.fromtimestamp((config.CACHE / "ANA" / "inventario_ws.csv").stat().st_mtime).date()
    salvar("ana_resumo.json", {
        "baixadoEm": baixado.isoformat(),
        "fonte": "ANA, HidroWeb: web service telemetriaws1.ana.gov.br (HidroInventario e HidroSerieHistorica)",
        "inicioMensal": f"{meses[0]:%Y-%m}", "meses": int(len(meses)),
        "anoInicial": ANOS[0], "anos": len(ANOS),
        "inventario": {s: int(contagem.get(s, 0)) for s in ugrhi.regioes()},
    })
    tam = sum(f.stat().st_size for f in DESTINO.glob("ana_*")) + sum(f.stat().st_size for f in (DESTINO / "diario").glob("ANA_*"))
    print(f"dados da ANA no app: {len(postos)} postos, {tam / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
