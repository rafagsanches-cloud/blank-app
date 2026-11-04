"""Leitura dos dados embutidos (os mesmos do app do Mac: macos/ChuvaSP/Dados)."""
from __future__ import annotations

import array
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .calculos import NAN, Parametros, SerieDiaria, calcular_indices, finito, mediana, tendencia

PRODUTOS = ["CHIRPS", "IMERG", "PERSIANN", "CMORPH", "GPCP", "POSTOS"]
SATELITES = ["CHIRPS", "IMERG", "PERSIANN", "CMORPH", "GPCP"]
NOME_PRODUTO = {p: p for p in PRODUTOS} | {"POSTOS": "Postos (média)"}
PERIODO_MEDIA = (2001, 2020)
PERIODO_POSTOS = (1980, 1999)


def localizar_dados() -> Path:
    """Dentro do executável (PyInstaller), na variável CHUVASP_DADOS ou no repositório."""
    candidatas = []
    if getattr(sys, "_MEIPASS", None):
        candidatas.append(Path(sys._MEIPASS) / "Dados")
    if os.environ.get("CHUVASP_DADOS"):
        candidatas.append(Path(os.environ["CHUVASP_DADOS"]))
    aqui = Path(__file__).resolve()
    candidatas += [aqui.parent / "Dados", aqui.parents[2] / "macos" / "ChuvaSP" / "Dados", Path.cwd() / "Dados"]
    for c in candidatas:
        if (c / "regioes.json").exists():
            return c
    raise FileNotFoundError("Não encontrei a pasta Dados do aplicativo.")


@dataclass
class Regiao:
    sigla: str
    codigo: int
    nome: str
    rotulo: str
    area_km2: float
    aneis: list  # [[(lon, lat), ...], ...]


@dataclass
class SerieMensal:
    ano0: int
    mes0: int
    valores: list

    def valor(self, ano: int, mes: int) -> float:
        k = (ano - self.ano0) * 12 + (mes - self.mes0)
        return self.valores[k] if 0 <= k < len(self.valores) else NAN


class BaseDados:
    def __init__(self, pasta: Path | None = None):
        self.pasta = pasta or localizar_dados()
        ler = lambda nome: json.loads((self.pasta / nome).read_text(encoding="utf-8"))  # noqa: E731
        self.regioes = sorted(
            [Regiao(r["sigla"], r["codigo"], r["nome"], r["rotulo"], r["areaKm2"], [[tuple(c) for c in anel] for anel in r["aneis"]])
             for r in ler("regioes.json")], key=lambda r: r.codigo)
        self.por_sigla = {r.sigla: r for r in self.regioes}
        self.anual: dict[tuple, dict] = {}
        for a in ler("anual.json"):
            if a["mm"] is not None:
                self.anual.setdefault((a["produto"], a["sigla"]), {})[a["ano"]] = a["mm"]
        self.mensal: dict[tuple, SerieMensal] = {}
        for m in ler("mensal.json"):
            ano, mes = (int(x) for x in m["inicio"].split("-")[:2])
            self.mensal[(m["produto"], m["sigla"])] = SerieMensal(ano, mes, [NAN if v is None else v for v in m["valores"]])
        self.indice_diario = {(d["produto"], d["sigla"]): d for d in ler("diario_indice.json")}
        self.postos = ler("postos.json")
        self.postos_por_ano: dict[str, list] = {}
        for r in ler("postos_por_ano.json"):
            self.postos_por_ano.setdefault(r["sigla"], []).append((r["ano"], r["postos"]))
        self.validacao = ler("validacao.json")
        self.produtos = ler("produtos.json")
        self.fontes = ler("fontes.json")
        self._diario: dict[tuple, SerieDiaria] = {}
        self._indices: dict[tuple, object] = {}

    # ---- séries
    def serie_anual(self, produto: str, sigla: str) -> list:
        return sorted(self.anual.get((produto, sigla), {}).items())

    def media(self, produto: str, sigla: str, periodo=PERIODO_MEDIA) -> float:
        v = [mm for a, mm in self.serie_anual(produto, sigla) if periodo[0] <= a <= periodo[1]]
        return sum(v) / len(v) if v else NAN

    def tendencia_anual(self, produto: str, sigla: str):
        s = self.serie_anual(produto, sigla)
        return tendencia([a for a, _ in s], [v for _, v in s])

    def climatologia(self, produto: str, sigla: str) -> list:
        s = self.mensal.get((produto, sigla))
        if not s:
            return []
        a0, a1 = PERIODO_POSTOS if produto == "POSTOS" else PERIODO_MEDIA
        out = []
        for mes in range(1, 13):
            v = [s.valor(a, mes) for a in range(a0, a1 + 1)]
            v = [x for x in v if finito(x)]
            out.append(sum(v) / len(v) if v else NAN)
        return out

    def diario(self, produto: str, sigla: str) -> SerieDiaria | None:
        k = (produto, sigla)
        if k in self._diario:
            return self._diario[k]
        idx = self.indice_diario.get(k)
        if not idx:
            return None
        arr = array.array("f")
        arr.frombytes((self.pasta / "diario" / idx["arquivo"]).read_bytes())
        if sys.byteorder != "little":
            arr.byteswap()
        ini = dt.date.fromisoformat(idx["inicio"])
        s = SerieDiaria(produto, sigla, ini, [float(v) for v in arr[: idx["dias"]]])
        self._diario[k] = s
        return s

    def indices(self, produto: str, sigla: str, par: Parametros):
        k = (produto, sigla, par)
        if k not in self._indices:
            s = self.diario(produto, sigla)
            self._indices[k] = calcular_indices(s, par) if s else None
        return self._indices[k]

    # ---- postos e validação
    def postos_na_regiao(self, sigla: str) -> list:
        return self.postos if sigla == "SP" else [p for p in self.postos if p["sigla"] == sigla]

    def validacoes(self, sigla: str) -> list:
        return self.validacao if sigla == "SP" else [v for v in self.validacao if v["sigla"] == sigla]

    def mediana_validacao(self, produto: str, sigla: str, campo: str):
        v = [x[campo] for x in self.validacoes(sigla) if x["produto"] == produto and x[campo] is not None]
        return (mediana(v), len(v)) if v else (NAN, 0)
