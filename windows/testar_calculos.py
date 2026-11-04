"""Confere os cálculos do app Windows contra o ClimdexSP em R.

Uso (na raiz do repositório):  python windows/testar_calculos.py
"""
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "windows"))

from chuva_sp_win.calculos import INDICES, Parametros, calcular_indices, nome_indice, tendencia  # noqa: E402
from chuva_sp_win.dados import BaseDados  # noqa: E402

base = BaseDados(RAIZ / "macos" / "ChuvaSP" / "Dados")
casos = json.loads((RAIZ / "macos" / "ChuvaSP" / "Testes" / "referencia_climdexsp.json").read_text())
p = Parametros()
falhas = comparacoes = 0


def confere(rotulo, obtido, esperado, tol=1e-6):
    global falhas, comparacoes
    comparacoes += 1
    if esperado is None:
        if math.isfinite(obtido):
            falhas += 1
            print(f"FALHA {rotulo}: esperado falta, obtido {obtido}")
        return
    if not abs(obtido - esperado) <= tol * max(1, abs(esperado)):
        falhas += 1
        print(f"FALHA {rotulo}: esperado {esperado}, obtido {obtido}")


for caso in casos:
    nome = f"{caso['produto']} {caso['sigla']}"
    s = base.diario(caso["produto"], caso["sigla"])
    r = calcular_indices(s, p)
    confere(f"{nome} p95", r.p95, caso["p95"])
    confere(f"{nome} p99", r.p99, caso["p99"])
    if r.anos != caso["anos"]:
        falhas += 1
        print(f"FALHA {nome}: anos diferentes")
    for ind in INDICES:
        chave = nome_indice(ind, p.nn)
        ref = caso["indices"][chave]
        for k, ano in enumerate(caso["anos"]):
            confere(f"{nome} {chave} {ano}", r.valores[ind][k], ref[k])
        tr = next((t for t in caso["tendencias"] if t["indice"] == chave), None)
        if tr:
            t = tendencia(r.anos, r.valores[ind])
            if t:
                confere(f"{nome} {chave} Sen", t.sen_por_decada, tr["sen"])
                confere(f"{nome} {chave} OLS", t.ols_por_decada, tr["ols"])
                confere(f"{nome} {chave} p OLS", t.p_ols, tr["p_ols"], 1e-5)
                confere(f"{nome} {chave} p MK", t.mk_p, tr["mk_p"], 1e-5)
            elif tr["sen"] is not None:
                falhas += 1
                print(f"FALHA {nome} {chave}: tendência não calculada")
    print(f"ok: {nome} – {len(r.anos)} anos, p95 = {r.p95:.3f} mm")

print(f"{comparacoes} comparações, {falhas} falhas")
sys.exit(1 if falhas else 0)
