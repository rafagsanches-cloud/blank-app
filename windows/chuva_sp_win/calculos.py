"""Cálculos do Chuva SP para Windows: índices ETCCDI, tendências e formatação.

Tradução direta do núcleo do app do Mac (macos/ChuvaSP/Fontes/Nucleo/Calculos.swift),
em Python puro (sem numpy), conferida contra o ClimdexSP em R por testar_calculos.py.
"""
from __future__ import annotations

import datetime as dt
import math
import sys
from dataclasses import dataclass, field

NAN = float("nan")


def finito(v: float | None) -> bool:
    return v is not None and math.isfinite(v)


# ---------------------------------------------------------------- índices

INDICES = ["PRCPTOT", "SDII", "R10mm", "R20mm", "Rnnmm", "CDD", "CWD", "R95p", "R99p",
           "R95pTOT", "R99pTOT", "Rx1day", "Rx5day"]

UNIDADE = {"PRCPTOT": "mm", "R95p": "mm", "R99p": "mm", "Rx1day": "mm", "Rx5day": "mm", "SDII": "mm/dia",
           "R95pTOT": "%", "R99pTOT": "%"}


def unidade(indice: str) -> str:
    return UNIDADE.get(indice, "dias")


def nome_indice(indice: str, nn: float) -> str:
    return f"R{round(nn)}mm" if indice == "Rnnmm" else indice


def descricao_indice(indice: str, nn: float, limiar: float) -> str:
    l = num(limiar, 0 if limiar == round(limiar) else 1)
    return {
        "PRCPTOT": f"Chuva total do ano nos dias com pelo menos {l} mm.",
        "SDII": "Chuva dos dias úmidos dividida pelo número de dias úmidos.",
        "R10mm": "Dias no ano com chuva de 10 mm ou mais.",
        "R20mm": "Dias no ano com chuva de 20 mm ou mais.",
        "Rnnmm": f"Dias no ano com chuva de {num(nn, 0)} mm ou mais.",
        "CDD": f"Maior sequência de dias com menos de {l} mm.",
        "CWD": f"Maior sequência de dias com pelo menos {l} mm.",
        "R95p": "Chuva do ano nos dias acima do percentil 95 dos dias úmidos do período-base.",
        "R99p": "Chuva do ano nos dias acima do percentil 99 dos dias úmidos do período-base.",
        "R95pTOT": "Parcela da chuva anual que caiu em dias acima do percentil 95.",
        "R99pTOT": "Parcela da chuva anual que caiu em dias acima do percentil 99.",
        "Rx1day": "Maior chuva em um único dia do ano.",
        "Rx5day": "Maior soma de chuva em 5 dias seguidos.",
    }[indice]


@dataclass(frozen=True)
class Parametros:
    base_inicio: int = 1981
    base_fim: int = 2010
    limiar_umido: float = 1.0
    nn: float = 50.0
    sequencias_cruzam_anos: bool = True
    max_faltas_ano: int = 15


@dataclass
class SerieDiaria:
    produto: str
    sigla: str
    inicio: dt.date
    valores: list  # mm/dia; NaN = falta

    @property
    def fim(self) -> dt.date:
        return self.inicio + dt.timedelta(days=len(self.valores) - 1)

    def valor(self, d: dt.date) -> float:
        k = (d - self.inicio).days
        return self.valores[k] if 0 <= k < len(self.valores) else NAN


@dataclass
class ResultadoIndices:
    anos: list
    valores: dict
    p95: float
    p99: float
    base_usada: tuple
    faltas_por_ano: list = field(default_factory=list)

    def serie(self, indice: str):
        return list(zip(self.anos, self.valores[indice]))


def quantil_tipo8(ordenados: list, p: float) -> float:
    """Quantil tipo 8, reproduzindo stats::quantile(type = 8) do R (mesma folga e ordem das contas)."""
    n = len(ordenados)
    if n == 0:
        return NAN
    a = b = 1.0 / 3.0
    folga = 4 * sys.float_info.epsilon
    nppm = a + p * (n + 1 - a - b)
    j = math.floor(nppm + folga)
    h = nppm - j
    if abs(h) < folga:
        h = 0.0

    def estendido(k: int) -> float:  # vetor do R: x1, x1, x..., xn, xn (base 1)
        i = k - 2
        return ordenados[min(max(i, 1), n) - 1]

    xlo, xhi = estendido(j + 2), estendido(j + 3)
    if h == 1:
        return xhi
    if 0 < h < 1 and xlo != xhi:
        return (1 - h) * xlo + h * xhi
    return xlo


def calcular_indices(serie: SerieDiaria, p: Parametros) -> ResultadoIndices:
    ini = dt.date(serie.inicio.year, 1, 1)
    fim = dt.date(serie.fim.year, 12, 31)
    n = (fim - ini).days + 1
    x = [NAN] * n
    desl = (serie.inicio - ini).days
    x[desl:desl + len(serie.valores)] = serie.valores
    ano = []
    d = ini
    um_dia = dt.timedelta(days=1)
    for _ in range(n):
        ano.append(d.year)
        d += um_dia
    anos = sorted(set(ano))
    pos = {a: i for i, a in enumerate(anos)}
    na = len(anos)

    b_ini, b_fim = min(p.base_inicio, p.base_fim), max(p.base_inicio, p.base_fim)
    lim = p.limiar_umido
    umidos = [v for v, a in zip(x, ano) if v == v and v >= lim and b_ini <= a <= b_fim]
    base_usada = (b_ini, b_fim)
    if len(umidos) < 100:
        umidos = [v for v in x if v == v and v >= lim]
        com_dado = [a for v, a in zip(x, ano) if v == v]
        if com_dado:
            base_usada = (min(com_dado), max(com_dado))
    umidos.sort()
    p95 = quantil_tipo8(umidos, 0.95)
    p99 = quantil_tipo8(umidos, 0.99)

    faltas = [0] * na
    com = [0] * na
    prcptot = [0.0] * na
    n_umidos = [0] * na
    r10 = [0.0] * na
    r20 = [0.0] * na
    rnn = [0.0] * na
    r95 = [0.0] * na
    r99 = [0.0] * na
    rx1 = [-math.inf] * na
    rx5 = [-math.inf] * na
    for i in range(n):
        k = pos[ano[i]]
        v = x[i]
        if v != v:
            faltas[k] += 1
        else:
            com[k] += 1
            if v >= lim:
                prcptot[k] += v
                n_umidos[k] += 1
                if v > p95:
                    r95[k] += v
                if v > p99:
                    r99[k] += v
            if v >= 10:
                r10[k] += 1
            if v >= 20:
                r20[k] += 1
            if v >= p.nn:
                rnn[k] += 1
            if v > rx1[k]:
                rx1[k] = v
        if i >= 4:
            s = 0.0
            ok = True
            for j in range(i - 4, i + 1):
                if x[j] == x[j]:
                    s += x[j]
                else:
                    ok = False
                    break
            if ok and s > rx5[k]:
                rx5[k] = s

    def maior_sequencia(cond) -> list:
        res = [0.0] * na
        corrida = 0
        for i in range(n):
            v = x[i]
            ok = v == v and cond(v)
            if p.sequencias_cruzam_anos:
                corrida = corrida + 1 if ok else 0
                if ok and (i == n - 1 or not (x[i + 1] == x[i + 1] and cond(x[i + 1]))):
                    k = pos[ano[i]]
                    res[k] = max(res[k], float(corrida))
            else:
                if i > 0 and ano[i] != ano[i - 1]:
                    corrida = 0
                corrida = corrida + 1 if ok else 0
                k = pos[ano[i]]
                res[k] = max(res[k], float(corrida))
        return res

    cdd = maior_sequencia(lambda v: v < lim)
    cwd = maior_sequencia(lambda v: v >= lim)

    val = {i: [NAN] * na for i in INDICES}
    for k in range(na):
        if faltas[k] > p.max_faltas_ano or com[k] == 0:
            continue
        val["PRCPTOT"][k] = prcptot[k]
        val["SDII"][k] = prcptot[k] / n_umidos[k] if n_umidos[k] else 0.0
        val["R10mm"][k] = r10[k]
        val["R20mm"][k] = r20[k]
        val["Rnnmm"][k] = rnn[k]
        val["CDD"][k] = cdd[k]
        val["CWD"][k] = cwd[k]
        val["R95p"][k] = r95[k]
        val["R99p"][k] = r99[k]
        val["R95pTOT"][k] = 100 * r95[k] / prcptot[k] if prcptot[k] > 0 else NAN
        val["R99pTOT"][k] = 100 * r99[k] / prcptot[k] if prcptot[k] > 0 else NAN
        val["Rx1day"][k] = rx1[k] if math.isfinite(rx1[k]) else NAN
        val["Rx5day"][k] = rx5[k] if math.isfinite(rx5[k]) else NAN
    return ResultadoIndices(anos, val, p95, p99, base_usada, faltas)


# ---------------------------------------------------------------- tendências

@dataclass
class Tendencia:
    n: int
    ano_inicio: int
    ano_fim: int
    sen_por_decada: float
    ols_por_decada: float
    erro_padrao_por_decada: float
    p_ols: float
    mk_tau: float
    mk_p: float

    @property
    def significativa(self) -> bool:
        return self.mk_p < 0.05


def mediana(v) -> float:
    s = sorted(x for x in v if finito(x))
    if not s:
        return NAN
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def normal_acumulada(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2))


def _fracao_continua_beta(a: float, b: float, x: float) -> float:
    minimo = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1 - qab * x / qap
    if abs(d) < minimo:
        d = minimo
    d = 1 / d
    h = d
    for m in range(1, 501):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = minimo if abs(d) < minimo else d
        c = 1 + aa / c
        c = minimo if abs(c) < minimo else c
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = minimo if abs(d) < minimo else d
        c = 1 + aa / c
        c = minimo if abs(c) < minimo else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return h


def beta_incompleta(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    frente = math.exp(math.log(x) * a + math.log(1 - x) * b + lbeta)
    if x < (a + 1) / (a + b + 2):
        return frente * _fracao_continua_beta(a, b, x) / a
    return 1 - frente * _fracao_continua_beta(b, a, 1 - x) / b


def p_valor_t(t: float, gl: float) -> float:
    if not math.isfinite(t):
        return 0.0
    return beta_incompleta(gl / 2, 0.5, gl / (gl + t * t))


def mann_kendall(v) -> tuple:
    v = [x for x in v if finito(x)]
    n = len(v)
    if n < 8:
        return NAN, NAN, NAN
    s = 0
    for k in range(n - 1):
        vk = v[k]
        for j in range(k + 1, n):
            dlt = v[j] - vk
            s += (dlt > 0) - (dlt < 0)
    contagem = {}
    for a in v:
        contagem[a] = contagem.get(a, 0) + 1
    var_s = n * (n - 1) * (2 * n + 5)
    for t in contagem.values():
        if t > 1:
            var_s -= t * (t - 1) * (2 * t + 5)
    var_s /= 18
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    return float(s), s / (n * (n - 1) / 2), 2 * normal_acumulada(-abs(z))


def tendencia(anos, valores) -> Tendencia | None:
    pares = [(a, v) for a, v in zip(anos, valores) if finito(v)]
    n = len(pares)
    if n < 8:
        return None
    t = [float(a) for a, _ in pares]
    y = [v for _, v in pares]
    incl = [(y[j] - y[i]) / (t[j] - t[i]) for i in range(n - 1) for j in range(i + 1, n) if t[j] != t[i]]
    sen = mediana(incl)
    mt, my = sum(t) / n, sum(y) / n
    sxx = sum((ti - mt) ** 2 for ti in t)
    sxy = sum((ti - mt) * (yi - my) for ti, yi in zip(t, y))
    b = sxy / sxx
    a = my - b * mt
    sse = sum((yi - (a + b * ti)) ** 2 for ti, yi in zip(t, y))
    gl = n - 2
    se = math.sqrt(sse / gl / sxx)
    p_ols = p_valor_t(b / se, gl) if se > 0 else (NAN if b == 0 else 0.0)
    _, tau, p_mk = mann_kendall(y)
    return Tendencia(n, int(t[0]), int(t[-1]), 10 * sen, 10 * b, 10 * se, p_ols, tau, p_mk)


# ---------------------------------------------------------------- formatação (padrão brasileiro)

def num(v, casas: int = 0) -> str:
    if not finito(v):
        return "—"
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def sinal(v, casas: int = 1) -> str:
    if not finito(v):
        return "—"
    s = num(abs(v), casas)
    return ("+" + s) if v > 0 else ("−" + s if v < 0 else s)


def p_texto(v) -> str:
    if not finito(v):
        return "—"
    return "< 0,001" if v < 0.001 else num(v, 3)


def csv_num(v, casas: int = 2) -> str:
    if not finito(v):
        return ""
    return f"{v:.{casas}f}".replace(".", ",")
