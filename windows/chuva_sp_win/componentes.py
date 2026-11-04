"""Componentes visuais: cartões, gráficos (Qt Charts), mapa, ranking e tabelas simples."""
from __future__ import annotations

import math
import re
import textwrap

from PySide6.QtCharts import QCategoryAxis, QChart, QChartView, QLineSeries, QScatterSeries, QValueAxis
from PySide6.QtCore import QLocale, QMargins, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QBoxLayout, QFrame, QGraphicsLineItem, QGridLayout, QHBoxLayout, QLabel, QLayout, QScrollArea,
                               QSizePolicy, QToolTip, QVBoxLayout, QWidget)

from .calculos import finito, num
from .dados import NOME_PRODUTO
from .tema import T, cor_produto, escuro, fonte_titulo


def limpar_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            limpar_layout(item.layout())


_TAG = re.compile(r"<(span|a|b|br|div|table|tr|td)\b|&nbsp;", re.I)


def passo_bonito(intervalo: float, alvo: int = 5) -> float:
    """Passo 1, 2, 2,5 ou 5 × 10^k que divide o intervalo em cerca de `alvo` partes."""
    if intervalo <= 0:
        return 1.0
    bruto = intervalo / alvo
    base = 10 ** math.floor(math.log10(bruto))
    for m in (1, 2, 2.5, 5, 10):
        if bruto <= m * base:
            return m * base
    return 10 * base


def rotulo(texto: str = "", secundario: bool = False, tamanho: int | None = None, negrito: bool = False,
           quebra: bool = True) -> QLabel:
    rico = bool(_TAG.search(texto))
    l = QLabel(texto.replace("< ", "&lt; ") if rico else texto)
    l.setWordWrap(quebra)
    l.setTextFormat(Qt.RichText if rico else Qt.PlainText)
    if secundario:
        l.setObjectName("secundario")
    if tamanho or negrito:
        f = l.font()
        if tamanho:
            f.setPointSizeF(tamanho)
        f.setBold(negrito)
        l.setFont(f)
    return l


def bolinha(produto: str) -> str:
    return f"<span style='color:{cor_produto(produto).name()}'>●</span>"


class Cartao(QFrame):
    """Cartão com título, nota opcional e conteúdo em coluna."""

    def __init__(self, titulo: str, nota: str | None = None):
        super().__init__()
        self.setObjectName("cartao")
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(16, 14, 16, 16)
        self.corpo.setSpacing(8)
        self.titulo = rotulo(titulo, negrito=True, tamanho=11)
        self.corpo.addWidget(self.titulo)
        if nota:
            self.corpo.addWidget(rotulo(nota, secundario=True))

    def add(self, w) -> None:
        if isinstance(w, QWidget):
            self.corpo.addWidget(w)
        else:
            self.corpo.addLayout(w)


class CartaoNumero(QFrame):
    def __init__(self, titulo: str, valor: str, unidade: str, nota: str):
        super().__init__()
        self.setObjectName("cartao")
        self.setMinimumHeight(124)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(4)
        v.addWidget(rotulo(titulo, secundario=True))
        linha = QHBoxLayout()
        val = QLabel(valor)
        val.setFont(fonte_titulo(24))
        linha.addWidget(val)
        un = rotulo(unidade, secundario=True, quebra=False)
        linha.addWidget(un, 0, Qt.AlignBottom)
        linha.addStretch(1)
        v.addLayout(linha)
        v.addWidget(rotulo(nota, secundario=True, tamanho=8.5))
        v.addStretch(1)


class Cabecalho(QWidget):
    def __init__(self, titulo: str, subtitulo: str):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 4)
        v.setSpacing(2)
        t = QLabel(titulo)
        t.setFont(fonte_titulo(22))
        v.addWidget(t)
        v.addWidget(rotulo(subtitulo, secundario=True))


class Legenda(QLabel):
    """Legenda dos produtos (bolinha colorida + nome), que quebra linha quando falta espaço."""

    def __init__(self, produtos: list):
        itens = [f"{bolinha(p)}&nbsp;{NOME_PRODUTO[p].replace(' ', '&nbsp;')}" for p in produtos]
        super().__init__("&nbsp;&nbsp;&nbsp; ".join(itens))
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(True)
        self.setObjectName("secundario")


class LinhaResponsiva(QWidget):
    """Blocos lado a lado que viram uma coluna quando a largura fica abaixo do limite."""

    def __init__(self, limite: int = 1000, espaco: int = 12):
        super().__init__()
        self.limite = limite
        self.caixa = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.caixa.setContentsMargins(0, 0, 0, 0)
        self.caixa.setSpacing(espaco)
        self.fixos = []

    def add(self, w, esticar: int = 1, largura_fixa: int | None = None) -> None:
        self.caixa.addWidget(w, esticar)
        self.fixos.append((w, largura_fixa))
        self._ajustar(self.width() or 2000)

    def _ajustar(self, largura: int) -> None:
        estreito = largura < self.limite
        self.caixa.setDirection(QBoxLayout.TopToBottom if estreito else QBoxLayout.LeftToRight)
        for w, fixa in self.fixos:
            if fixa:
                if estreito:
                    w.setMinimumWidth(0)
                    w.setMaximumWidth(16777215)
                else:
                    w.setFixedWidth(fixa)

    def resizeEvent(self, ev):
        self._ajustar(ev.size().width())
        super().resizeEvent(ev)


class Fluxo(QLayout):
    """Controles em fila que passam para a linha de baixo quando falta largura (como texto)."""

    def __init__(self, pai=None, espaco_h: int = 18, espaco_v: int = 8):
        super().__init__(pai)
        self._itens = []
        self._eh, self._ev = espaco_h, espaco_v
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._itens.append(item)

    def count(self):
        return len(self._itens)

    def itemAt(self, i):
        return self._itens[i] if 0 <= i < len(self._itens) else None

    def takeAt(self, i):
        return self._itens.pop(i) if 0 <= i < len(self._itens) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, largura):
        return self._arrumar(QRect(0, 0, largura, 0), aplicar=False)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._arrumar(r, aplicar=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._itens:
            s = s.expandedTo(it.minimumSize())
        return s

    def _arrumar(self, r, aplicar: bool) -> int:
        linhas, atual, x = [], [], 0
        for it in self._itens:
            w = it.sizeHint().width()
            if atual and x + w > r.width():
                linhas.append(atual)
                atual, x = [], 0
            atual.append(it)
            x += w + self._eh
        if atual:
            linhas.append(atual)
        y = r.y()
        for k, linha in enumerate(linhas):
            alt = max(it.sizeHint().height() for it in linha)
            if aplicar:
                x = r.x()
                for it in linha:
                    sh = it.sizeHint()
                    it.setGeometry(QRect(QPoint(x, y + (alt - sh.height()) // 2), sh))
                    x += sh.width() + self._eh
            y += alt + (self._ev if k < len(linhas) - 1 else 0)
        return y - r.y()


def grupo(*widgets, espaco: int = 6) -> QWidget:
    """Junta rótulo e campo num bloco só, para que quebrem de linha juntos."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(espaco)
    for x in widgets:
        h.addWidget(x)
    return w


class RolagemLateral(QScrollArea):
    """Deixa um bloco largo (uma tabela) rolar para o lado dentro do cartão, sem alargar a página."""

    def __init__(self, conteudo: QWidget):
        super().__init__()
        self.setObjectName("rolagemLateral")
        self.setWidget(conteudo)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(120)
        self.setStyleSheet("QScrollArea#rolagemLateral, QScrollArea#rolagemLateral > QWidget > QWidget { background: transparent; }")
        self.viewport().setAutoFillBackground(False)
        self._altura(2000)

    def _altura(self, largura: int) -> None:
        conteudo = self.widget()
        h = conteudo.sizeHint().height()
        if conteudo.minimumSizeHint().width() > largura:
            h += self.horizontalScrollBar().sizeHint().height() + 2
        self.setFixedHeight(h)

    def resizeEvent(self, ev):
        self._altura(ev.size().width())
        super().resizeEvent(ev)


def segmentos(serie: list, passo: int = 1) -> list:
    """Divide [(x, y)] em trechos sem falta (NaN) nem saltos maiores que `passo`."""
    grupos, atual, ultimo = [], [], None
    for x, y in sorted(serie):
        if not finito(y):
            if atual:
                grupos.append(atual)
            atual, ultimo = [], None
            continue
        if ultimo is not None and x - ultimo > passo and atual:
            grupos.append(atual)
            atual = []
        atual.append((x, y))
        ultimo = x
    if atual:
        grupos.append(atual)
    return grupos


def _configurar_chart(chart: QChart) -> None:
    chart.legend().hide()
    chart.setBackgroundVisible(False)
    chart.setPlotAreaBackgroundVisible(False)
    chart.setMargins(QMargins(0, 4, 4, 0))
    chart.layout().setContentsMargins(0, 0, 0, 0)
    chart.setLocalizeNumbers(True)
    chart.setLocale(QLocale(QLocale.Portuguese, QLocale.Brazil))
    chart.setAnimationOptions(QChart.NoAnimation)


def _estilo_eixo(eixo) -> None:
    eixo.setLabelsColor(QColor(T.secundario))
    eixo.setGridLineColor(QColor(T.grade))
    eixo.setLinePenColor(QColor(T.eixo))
    f = QFont()
    f.setPointSizeF(8.5)
    eixo.setLabelsFont(f)


class GraficoLinhas(QChartView):
    """Linhas por produto com eixo x inteiro (ano, mês ou dia) e dica ao passar o mouse."""

    def __init__(self, altura: int = 300):
        chart = QChart()
        _configurar_chart(chart)
        super().__init__(chart)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(altura)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent")
        self._regua = None
        self._dados = {}
        self._rotulo_dica = str
        self._fmt = lambda v: num(v, 0)
        self._primeira = None

    def definir(self, series: dict, ticks: list, rotulo_x=str, rotulo_dica=None, unidade: str = "mm",
                casas: int = 0, incluir_zero: bool = False, passo: int = 1) -> None:
        chart = self.chart()
        chart.removeAllSeries()
        for e in list(chart.axes()):
            chart.removeAxis(e)
        self._regua = None
        self._dados = {p: dict(s) for p, s in series.items()}
        self._rotulo_dica = rotulo_dica or rotulo_x
        self._fmt = lambda v: f"{num(v, casas)} {unidade}"
        xs = [x for s in series.values() for x, y in s if finito(y)]
        ys = [y for s in series.values() for x, y in s if finito(y)]
        if not xs:
            return
        x0, x1 = min(min(xs), ticks[0] if ticks else min(xs)), max(max(xs), ticks[-1] if ticks else max(xs))
        ax = QCategoryAxis()
        ax.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        for t in ticks:
            ax.append(rotulo_x(t), t)
        ax.setRange(x0, x1 + (x1 - x0) * 0.01)
        ay = QValueAxis()
        y0, y1 = min(ys), max(ys)
        if incluir_zero:
            y0 = min(0.0, y0)
        if y1 == y0:
            y1 = y0 + 1
        passo = passo_bonito(y1 - y0)
        y0 = math.floor(y0 / passo) * passo
        y1 = math.ceil(y1 / passo) * passo
        ay.setRange(y0, y1)
        ay.setTickType(QValueAxis.TicksDynamic)
        ay.setTickAnchor(y0)
        ay.setTickInterval(passo)
        ay.setLabelFormat("%.0f" if passo >= 1 else "%.1f")
        for e in (ax, ay):
            _estilo_eixo(e)
        chart.addAxis(ax, Qt.AlignBottom)
        chart.addAxis(ay, Qt.AlignLeft)
        self._primeira = None
        for produto, serie in series.items():
            cor = cor_produto(produto)
            for trecho in segmentos(serie, passo):
                if len(trecho) == 1:
                    s = QScatterSeries()
                    s.setMarkerSize(6)
                    s.setColor(cor)
                    s.setBorderColor(cor)
                else:
                    s = QLineSeries()
                    pen = QPen(cor, 2.6 if produto == "POSTOS" else 1.8)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    s.setPen(pen)
                for x, y in trecho:
                    s.append(float(x), float(y))
                chart.addSeries(s)
                s.attachAxis(ax)
                s.attachAxis(ay)
                self._primeira = self._primeira or s
        self._xs = sorted(set(xs))

    def mouseMoveEvent(self, ev):
        super().mouseMoveEvent(ev)
        if not self._primeira or not self._xs:
            return
        chart = self.chart()
        pos = self.mapToScene(ev.position().toPoint())
        if not chart.plotArea().contains(chart.mapFromScene(pos)):
            self._esconder()
            return
        valor = chart.mapToValue(chart.mapFromScene(pos), self._primeira)
        x = min(self._xs, key=lambda v: abs(v - valor.x()))
        topo = chart.plotArea().top()
        base = chart.plotArea().bottom()
        px = chart.mapToPosition(QPointF(x, 0), self._primeira).x()
        if self._regua is None:
            self._regua = QGraphicsLineItem()
            self._regua.setPen(QPen(QColor(T.eixo), 1))
            chart.scene().addItem(self._regua)
        self._regua.setLine(px, topo, px, base)
        self._regua.show()
        linhas = sorted(((p, d[x]) for p, d in self._dados.items() if x in d and finito(d[x])), key=lambda t: -t[1])
        html = f"<div style='color:{T.secundario}'>{self._rotulo_dica(x)}</div><table cellspacing=2>"
        for p, v in linhas:
            html += f"<tr><td>{bolinha(p)} {NOME_PRODUTO[p]}</td><td align=right>&nbsp;&nbsp;{self._fmt(v)}</td></tr>"
        QToolTip.showText(ev.globalPosition().toPoint(), html + "</table>", self)

    def leaveEvent(self, ev):
        self._esconder()
        super().leaveEvent(ev)

    def _esconder(self):
        if self._regua:
            self._regua.hide()
        QToolTip.hideText()


class Dispersao(QChartView):
    """Pontos por produto (um por posto) com a mediana marcada por um traço."""

    def __init__(self, altura: int = 320):
        chart = QChart()
        _configurar_chart(chart)
        super().__init__(chart)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(altura)
        self.setStyleSheet("background: transparent")

    def definir(self, grupos: list, dominio: tuple, fmt) -> None:
        """grupos: [(produto, [(x, y, rótulo)], mediana)]"""
        chart = self.chart()
        chart.removeAllSeries()
        for e in list(chart.axes()):
            chart.removeAxis(e)
        ax = QCategoryAxis()
        ax.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        for i, (p, _, _) in enumerate(grupos):
            ax.append(NOME_PRODUTO[p], i)
        ax.setRange(-0.6, len(grupos) - 0.4)
        ay = QValueAxis()
        ay.setRange(*dominio)
        passo = passo_bonito(dominio[1] - dominio[0])
        ay.setTickType(QValueAxis.TicksDynamic)
        ay.setTickAnchor(math.ceil(dominio[0] / passo) * passo)
        ay.setTickInterval(passo)
        casas = max(0, -math.floor(math.log10(passo)))
        if abs(passo * 10 ** casas - round(passo * 10 ** casas)) > 1e-9:
            casas += 1
        ay.setLabelFormat(f"%.{casas}f")
        for e in (ax, ay):
            _estilo_eixo(e)
        ax.setGridLineVisible(False)
        chart.addAxis(ax, Qt.AlignBottom)
        chart.addAxis(ay, Qt.AlignLeft)
        for i, (p, pontos, med) in enumerate(grupos):
            s = QScatterSeries()
            s.setMarkerSize(5)
            c = QColor(cor_produto(p))
            c.setAlphaF(0.35 if len(pontos) > 300 else 0.6)
            s.setColor(c)
            s.setBorderColor(Qt.transparent)
            rotulos = {}
            for x, y, r in pontos:
                yy = min(max(y, dominio[0]), dominio[1])
                s.append(x, yy)
                rotulos[(round(x, 4), round(yy, 4))] = (r, y)
            s.hovered.connect(lambda pt, estado, rot=rotulos, prod=p: self._dica(pt, estado, rot, prod, fmt))
            chart.addSeries(s)
            s.attachAxis(ax)
            s.attachAxis(ay)
            if finito(med):
                m = QLineSeries()
                caneta = QPen(QColor(T.texto), 3)
                caneta.setCapStyle(Qt.RoundCap)
                m.setPen(caneta)
                m.append(i - 0.38, med)
                m.append(i + 0.38, med)
                chart.addSeries(m)
                m.attachAxis(ax)
                m.attachAxis(ay)

    def _dica(self, pt, estado, rotulos, produto, fmt):
        if not estado:
            QToolTip.hideText()
            return
        r = rotulos.get((round(pt.x(), 4), round(pt.y(), 4)))
        if r:
            from PySide6.QtGui import QCursor

            QToolTip.showText(QCursor.pos(), f"{r[0]}<br>{bolinha(produto)} {NOME_PRODUTO[produto]}: {fmt(r[1])}", self)


class BarrasAnos(QWidget):
    """Barras de número de postos por ano (desenho próprio, com dica)."""

    def __init__(self, altura: int = 220):
        super().__init__()
        self.setMinimumHeight(altura)
        self.setMouseTracking(True)
        self.dados = []

    def definir(self, dados: list) -> None:
        self.dados = sorted(dados)
        self.update()

    def _geometria(self):
        r = QRectF(self.rect()).adjusted(4, 8, -36, -22)
        n = max(len(self.dados), 1)
        larg = r.width() / n
        vmax = max([v for _, v in self.dados] + [1])
        passo = 10 ** math.floor(math.log10(vmax)) if vmax >= 10 else 1
        topo = math.ceil(vmax / passo) * passo
        if topo / passo > 6:
            passo *= 2
            topo = math.ceil(vmax / passo) * passo
        return r, larg, topo, passo

    def paintEvent(self, ev):
        if not self.dados:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r, larg, topo, passo = self._geometria()
        f = p.font()
        f.setPointSizeF(8.5)
        p.setFont(f)
        y = 0
        while y <= topo:
            yy = r.bottom() - r.height() * y / topo
            p.setPen(QPen(QColor(T.grade), 1))
            p.drawLine(QPointF(r.left(), yy), QPointF(r.right(), yy))
            p.setPen(QColor(T.secundario))
            p.drawText(QRectF(r.right() + 4, yy - 8, 32, 16), Qt.AlignLeft | Qt.AlignVCenter, num(y, 0))
            y += passo
        primeiro, ultimo = self.dados[0][0], self.dados[-1][0]
        for i, (ano, v) in enumerate(self.dados):
            x = r.left() + i * larg
            h = r.height() * v / topo
            p.setPen(Qt.NoPen)
            p.setBrush(cor_produto("CHIRPS"))
            p.drawRoundedRect(QRectF(x + larg * 0.15, r.bottom() - h, larg * 0.7, h), 2, 2)
            if ano % 5 == 0 and primeiro + 1 < ano < ultimo - 1:
                p.setPen(QColor(T.secundario))
                p.drawText(QRectF(x - 20, r.bottom() + 3, larg + 40, 16), Qt.AlignHCenter | Qt.AlignTop, str(ano))
        p.end()

    def mouseMoveEvent(self, ev):
        if not self.dados:
            return
        r, larg, _, _ = self._geometria()
        i = int((ev.position().x() - r.left()) // larg)
        if 0 <= i < len(self.dados):
            ano, v = self.dados[i]
            QToolTip.showText(ev.globalPosition().toPoint(), f"{ano}<br>Postos com dado: {num(v, 0)}", self)


class EscalaCor:
    def __init__(self, minimo: float, maximo: float, divergente: bool):
        self.minimo, self.maximo, self.divergente = minimo, maximo, divergente

    @staticmethod
    def _mistura(a: str, b: str, t: float) -> QColor:
        t = min(max(t, 0.0), 1.0)
        ca, cb = QColor(a), QColor(b)
        return QColor.fromRgbF(ca.redF() + (cb.redF() - ca.redF()) * t, ca.greenF() + (cb.greenF() - ca.greenF()) * t,
                               ca.blueF() + (cb.blueF() - ca.blueF()) * t)

    def cor(self, v: float) -> QColor:
        if not finito(v):
            return QColor(T.borda)
        if self.divergente:
            m = max(abs(self.minimo), abs(self.maximo), 1e-9)
            meio = "#383835" if escuro() else "#f0efec"
            return self._mistura(meio, "#e66767" if escuro() else "#d03b3b", -v / m) if v < 0 else \
                self._mistura(meio, "#5598e7" if escuro() else "#2a78d6", v / m)
        t = (v - self.minimo) / (self.maximo - self.minimo) if self.maximo > self.minimo else 0.5
        return self._mistura("#1c3550" if escuro() else "#cde2fb", "#86b6ef" if escuro() else "#104281", t)

    def extremos(self) -> tuple:
        if self.divergente:
            m = max(abs(self.minimo), abs(self.maximo))
            return -m, m
        return self.minimo, self.maximo


class MapaUGRHI(QWidget):
    """Mapa das UGRHIs desenhado a partir dos polígonos; clique escolhe a UGRHI."""

    clicado = Signal(str)

    def __init__(self, regioes: list):
        super().__init__()
        self.regioes = [r for r in regioes if r.aneis]
        pts = [c for r in self.regioes for anel in r.aneis for c in anel]
        self.lon0, self.lon1 = min(c[0] for c in pts), max(c[0] for c in pts)
        self.lat0, self.lat1 = min(c[1] for c in pts), max(c[1] for c in pts)
        self.k = math.cos(math.radians(22.5))
        self.proporcao = (self.lon1 - self.lon0) * self.k / (self.lat1 - self.lat0)
        self.valores, self.escala, self.selecionada, self.postos = {}, None, "SP", []
        self.formatar = str
        self.setMouseTracking(True)
        self.setMinimumHeight(330)
        self._caminhos = {}

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return int(w / self.proporcao)

    def definir(self, valores, escala, selecionada, postos, formatar) -> None:
        self.valores, self.escala, self.selecionada, self.postos, self.formatar = valores, escala, selecionada, postos, formatar
        self.update()

    def _projetar(self):
        w, h = self.width(), self.height()
        esc = min(w / ((self.lon1 - self.lon0) * self.k), h / (self.lat1 - self.lat0))
        dx = (w - (self.lon1 - self.lon0) * self.k * esc) / 2
        dy = (h - (self.lat1 - self.lat0) * esc) / 2
        return lambda lon, lat: QPointF(dx + (lon - self.lon0) * self.k * esc, dy + (self.lat1 - lat) * esc)

    def paintEvent(self, ev):
        proj = self._projetar()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._caminhos = {}
        for r in self.regioes:
            caminho = QPainterPath()
            caminho.setFillRule(Qt.OddEvenFill)
            for anel in r.aneis:
                if len(anel) < 3:
                    continue
                caminho.moveTo(proj(*anel[0]))
                for c in anel[1:]:
                    caminho.lineTo(proj(*c))
                caminho.closeSubpath()
            self._caminhos[r.sigla] = caminho
            cor = self.escala.cor(self.valores.get(r.sigla, float("nan"))) if self.escala else QColor(T.borda)
            p.setBrush(cor)
            p.setPen(QPen(QColor(T.cartao), 0.8))
            p.drawPath(caminho)
        if self.selecionada in self._caminhos:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(T.texto), 2.5))
            p.drawPath(self._caminhos[self.selecionada])
        if self.postos:
            c = QColor(T.texto)
            c.setAlphaF(0.55)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            for po in self.postos:
                pt = proj(po["lon"], po["lat"])
                p.drawEllipse(pt, 1.6, 1.6)
        p.end()

    def _regiao_em(self, pos):
        for sigla, cam in self._caminhos.items():
            if cam.contains(pos):
                return sigla
        return None

    def mouseMoveEvent(self, ev):
        s = self._regiao_em(ev.position())
        if s:
            r = next(x for x in self.regioes if x.sigla == s)
            QToolTip.showText(ev.globalPosition().toPoint(), f"{r.rotulo}<br>{self.formatar(self.valores.get(s))}", self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, ev):
        s = self._regiao_em(ev.position())
        if s:
            self.clicado.emit(s)


class LegendaEscala(QWidget):
    def __init__(self, escala: EscalaCor, formatar):
        super().__init__()
        self.escala, self.formatar = escala, formatar
        self.setFixedHeight(34)
        self.setMinimumWidth(270)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        a, b = self.escala.extremos()
        g = QLinearGradient(0, 0, 260, 0)
        for k in range(11):
            g.setColorAt(k / 10, self.escala.cor(a + (b - a) * k / 10))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(0, 2, 260, 10), 3, 3)
        f = p.font()
        f.setPointSizeF(8.5)
        p.setFont(f)
        p.setPen(QColor(T.secundario))
        p.drawText(QRectF(0, 15, 130, 16), Qt.AlignLeft, self.formatar(a, False))
        p.drawText(QRectF(130, 15, 130, 16), Qt.AlignRight, self.formatar(b, True))
        p.end()


class Ranking(QWidget):
    """UGRHIs ordenadas por valor, em barras horizontais; clique escolhe a UGRHI."""

    clicado = Signal(str)
    LINHA = 27

    def __init__(self):
        super().__init__()
        self.itens, self.escala, self.selecionada, self.formatar = [], None, "SP", str
        self.setMouseTracking(True)

    def definir(self, itens, escala, selecionada, formatar) -> None:
        self.itens, self.escala, self.selecionada, self.formatar = itens, escala, selecionada, formatar
        self.setMinimumHeight(len(itens) * self.LINHA + 4)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        maximo = max([abs(v) for _, _, v in self.itens] + [1e-9])
        f = p.font()
        f.setPointSizeF(8.5)
        for i, (sigla, nome, v) in enumerate(self.itens):
            y = i * self.LINHA
            sel = sigla == self.selecionada
            alfa = 1.0 if self.selecionada == "SP" or sel else 0.55
            f.setBold(sel)
            p.setFont(f)
            c = QColor(T.texto)
            c.setAlphaF(alfa)
            p.setPen(c)
            p.drawText(QRectF(0, y, w - 60, 14), Qt.AlignLeft | Qt.AlignVCenter, nome)
            p.drawText(QRectF(w - 70, y, 70, 14), Qt.AlignRight | Qt.AlignVCenter, self.formatar(v))
            cb = QColor(self.escala.cor(v))
            cb.setAlphaF(alfa)
            p.setPen(Qt.NoPen)
            p.setBrush(cb)
            p.drawRoundedRect(QRectF(0, y + 16, max(2.0, w * abs(v) / maximo), 7), 2, 2)
        p.end()

    def mousePressEvent(self, ev):
        i = int(ev.position().y() // self.LINHA)
        if 0 <= i < len(self.itens):
            self.clicado.emit(self.itens[i][0])


class Grade(QWidget):
    """Tabela simples (cabeçalho + linhas) feita de rótulos, como as grades do app do Mac."""

    def __init__(self, cabecalho: list, linhas: list, direita: set | None = None):
        super().__init__()
        direita = direita or set()
        g = QGridLayout(self)
        g.setContentsMargins(0, 4, 0, 0)
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(6)
        for j, c in enumerate(cabecalho):
            l = rotulo(c, secundario=True, tamanho=8.5, negrito=True, quebra=False)
            g.addWidget(l, 0, j, Qt.AlignRight if j in direita else Qt.AlignLeft)
        linha = QFrame()
        linha.setFrameShape(QFrame.HLine)
        linha.setStyleSheet(f"color: {T.borda}")
        g.addWidget(linha, 1, 0, 1, len(cabecalho))
        for i, valores in enumerate(linhas):
            for j, v in enumerate(valores):
                if len(v) > 22 and not _TAG.search(v):
                    v = textwrap.fill(v, 21)  # quebras explícitas: o QGridLayout não mede bem texto com quebra automática
                l = rotulo(v, quebra=False)
                l.setTextInteractionFlags(Qt.TextSelectableByMouse)
                g.addWidget(l, i + 2, j, Qt.AlignRight | Qt.AlignTop if j in direita else Qt.AlignLeft | Qt.AlignTop)
        g.setColumnStretch(len(cabecalho), 1)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
