"""As sete telas do Chuva SP (as mesmas do app do Mac)."""
from __future__ import annotations

import datetime as dt
import hashlib

from PySide6.QtCore import QLocale, QObject, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QPushButton,
                               QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
                               QWidget)

from .calculos import (INDICES, NAN, Parametros, descricao_indice, finito, mediana, nome_indice, num, p_texto,
                       sinal, tendencia, unidade)
from .componentes import (BarrasAnos, Cabecalho, Cartao, CartaoNumero, Dispersao, EscalaCor, Grade, GraficoLinhas,
                          Legenda, LegendaEscala, MapaUGRHI, Ranking, bolinha, limpar_layout, rotulo)
from .dados import NOME_PRODUTO, PERIODO_MEDIA, PRODUTOS, SATELITES, BaseDados

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
ABAS = [
    ("visaoGeral", "Visão geral"),
    ("mapa", "Mapa das UGRHIs"),
    ("series", "Séries mensais e diárias"),
    ("extremos", "Extremos (RClimDex)"),
    ("validacao", "Satélite × postos"),
    ("postos", "Postos pluviométricos"),
    ("produtos", "Produtos e fontes"),
]
METRICAS = [("rDiario", "r diário"), ("rMensal", "r mensal"), ("viesPct", "Viés (%)"), ("kge", "KGE"), ("csi", "CSI")]
LOCAL_BR = QLocale(QLocale.Portuguese, QLocale.Brazil)


class Estado(QObject):
    mudou = Signal()

    def __init__(self, base: BaseDados):
        super().__init__()
        self.base = base
        self.aba = "visaoGeral"
        self.regiao = "SP"
        self.visiveis = set(PRODUTOS)
        self.mapa_produto, self.mapa_modo, self.mapa_postos = "CHIRPS", "media", False
        self.indice, self.parametros = "PRCPTOT", Parametros()
        self.ano_inicial, self.ano_final, self.ano_diario = 1981, 2026, 2024
        self.metrica, self.busca = "rDiario", ""

    def alterar(self, **kw) -> None:
        mudou = False
        for k, v in kw.items():
            if getattr(self, k) != v:
                setattr(self, k, v)
                mudou = True
        if mudou:
            self.mudou.emit()

    @property
    def regiao_atual(self):
        return self.base.por_sigla.get(self.regiao)

    @property
    def rotulo_regiao(self) -> str:
        r = self.regiao_atual
        return r.rotulo if r else self.regiao

    @property
    def produtos_visiveis(self) -> list:
        return [p for p in PRODUTOS if p in self.visiveis]

    def subtitulo(self, texto: str) -> str:
        r = self.regiao_atual
        return f"{num(r.area_km2, 0)} km²  ·  {texto}" if r and r.area_km2 > 0 else texto

    def valores_mapa(self) -> dict:
        out = {}
        for r in self.base.regioes:
            if r.sigla == "SP":
                continue
            if self.mapa_modo == "media":
                out[r.sigla] = self.base.media(self.mapa_produto, r.sigla)
            else:
                t = self.base.tendencia_anual(self.mapa_produto, r.sigla)
                out[r.sigla] = t.sen_por_decada if t else NAN
        return out


def ticks_anos(a0: int, a1: int) -> list:
    span = a1 - a0
    passo = 5 if span > 30 else (2 if span > 12 else 1)
    ini = -(-a0 // passo) * passo
    return list(range(ini, a1 + 1, passo))


class Pagina(QScrollArea):
    def __init__(self, estado: Estado):
        super().__init__()
        self.estado = estado
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.interno = QWidget()
        self.interno.setObjectName("pagina")
        self.v = QVBoxLayout(self.interno)
        self.v.setContentsMargins(24, 18, 24, 24)
        self.v.setSpacing(16)
        self.setWidget(self.interno)
        self.cab = Cabecalho("", "")
        self.v.addWidget(self.cab)

    def definir_cabecalho(self, titulo: str, subtitulo: str) -> None:
        lay = self.cab.layout()
        lay.itemAt(0).widget().setText(titulo)
        lay.itemAt(1).widget().setText(subtitulo)

    def atualizar(self) -> None:  # redefinida nas telas
        pass

    @staticmethod
    def caixa() -> tuple:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        return w, lay


def segmentado(opcoes: list, atual: str, ao_escolher) -> tuple:
    """Botões lado a lado com um só marcado (como o controle segmentado do Mac)."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    grupo = QButtonGroup(w)
    grupo.setExclusive(True)
    botoes = {}
    for chave, texto in opcoes:
        b = QPushButton(texto)
        b.setObjectName("segmento")
        b.setCheckable(True)
        b.setChecked(chave == atual)
        b.clicked.connect(lambda _=False, c=chave: ao_escolher(c))
        grupo.addButton(b)
        h.addWidget(b)
        botoes[chave] = b
    h.addStretch(1)
    w.botoes = botoes
    return w, botoes


# ======================================================================= 1. Visão geral

class VisaoGeral(Pagina):
    def __init__(self, estado):
        super().__init__(estado)
        self.kpis = QGridLayout()
        self.kpis.setSpacing(12)
        self.v.addLayout(self.kpis)
        self.c_anual = Cartao("Chuva anual por produto",
                              "Total do ano civil (mm). Ano com mais de 15 dias sem dado fica em branco. "
                              "Passe o mouse para ver os valores; use o botão Produtos para esconder séries.")
        self.g_anual = GraficoLinhas(320)
        self.c_anual.add(self.g_anual)
        self.leg_anual, self.leg_anual_lay = self.caixa()
        self.c_anual.add(self.leg_anual)
        self.v.addWidget(self.c_anual)
        linha = QHBoxLayout()
        linha.setSpacing(12)
        self.c_clima = Cartao("Chuva média por mês", "Satélites: 2001–2020. Postos: 1980–1999, quando a rede do GHCN tinha mais postos ativos.")
        self.g_clima = GraficoLinhas(260)
        self.c_clima.add(self.g_clima)
        self.leg_clima, self.leg_clima_lay = self.caixa()
        self.c_clima.add(self.leg_clima)
        self.c_tend = Cartao("Tendência do total anual", "Estimador de Sen por década; p do teste de Mann-Kendall. ● marca p < 0,05.")
        self.c_tend.setFixedWidth(430)
        self.tend_box, self.tend_lay = self.caixa()
        self.c_tend.add(self.tend_box)
        self.c_tend.corpo.addStretch(1)
        linha.addWidget(self.c_clima, 1)
        linha.addWidget(self.c_tend, 0, Qt.AlignTop)
        self.v.addLayout(linha)
        self.v.addStretch(1)

    def atualizar(self):
        e, b = self.estado, self.estado.base
        reg = e.regiao
        self.definir_cabecalho(e.rotulo_regiao, e.subtitulo("Chuva por satélite e postos pluviométricos"))
        t = b.tendencia_anual("CHIRPS", reg)
        r_d, n_d = b.mediana_validacao("CHIRPS", reg, "rDiario")
        r_m, _ = b.mediana_validacao("CHIRPS", reg, "rMensal")
        limpar_layout(self.kpis)
        cartoes = [
            CartaoNumero("Chuva média anual, CHIRPS, 2001–2020", num(b.media("CHIRPS", reg), 0), "mm", "Média dos totais anuais"),
            CartaoNumero("Tendência do total anual, CHIRPS", sinal(t.sen_por_decada if t else NAN, 1), "mm por década",
                         f"Sen; Mann-Kendall p = {p_texto(t.mk_p)}, {t.ano_inicio}–{t.ano_fim}" if t else "—"),
            CartaoNumero("Postos pluviométricos com dados desde 1980", num(len(b.postos_na_regiao(reg)), 0), "postos",
                         "Rede da ANA e do DAEE, via GHCN-Daily"),
            CartaoNumero("Correlação diária CHIRPS × postos (mediana)", num(r_d, 2), "", f"Mensal: {num(r_m, 2)} · {n_d} postos"),
        ]
        for i, c in enumerate(cartoes):
            self.kpis.addWidget(c, 0, i)
        prods = e.produtos_visiveis
        series = {p: b.serie_anual(p, reg) for p in prods}
        series = {p: s for p, s in series.items() if s}
        anos = [a for s in series.values() for a, _ in s] or [1980, 2026]
        self.g_anual.definir(series, ticks_anos(min(anos), max(anos)), unidade="mm")
        limpar_layout(self.leg_anual_lay)
        self.leg_anual_lay.addWidget(Legenda(list(series)))
        clima = {p: [(m + 1, v) for m, v in enumerate(b.climatologia(p, reg))] for p in prods}
        clima = {p: s for p, s in clima.items() if s}
        self.g_clima.definir(clima, list(range(1, 13)), rotulo_x=lambda m: MESES[m - 1], unidade="mm", incluir_zero=True)
        limpar_layout(self.leg_clima_lay)
        self.leg_clima_lay.addWidget(Legenda(list(clima)))
        limpar_layout(self.tend_lay)
        linhas = []
        for p in PRODUTOS:
            t = b.tendencia_anual(p, reg)
            linhas.append([f"{bolinha(p)} {NOME_PRODUTO[p]}", f"{t.ano_inicio}–{t.ano_fim}" if t else "—",
                           sinal(t.sen_por_decada if t else NAN, 1),
                           ("● " if t and t.significativa else "") + p_texto(t.mk_p if t else NAN)])
        self.tend_lay.addWidget(Grade(["Produto", "Período", "Sen", "p"], linhas, direita={2, 3}))


# ======================================================================= 2. Mapa

class Mapa(Pagina):
    def __init__(self, estado):
        super().__init__(estado)
        ctl = QHBoxLayout()
        ctl.setSpacing(12)
        ctl.addWidget(rotulo("Produto", quebra=False))
        self.c_prod = QComboBox()
        for p in SATELITES:
            self.c_prod.addItem(p, p)
        self.c_prod.currentIndexChanged.connect(lambda i: estado.alterar(mapa_produto=self.c_prod.itemData(i)))
        ctl.addWidget(self.c_prod)
        ctl.addSpacing(12)
        ctl.addWidget(rotulo("Mostrar", quebra=False))
        self.seg, self.seg_botoes = segmentado([("media", "Média 2001–2020"), ("tendencia", "Tendência (Sen)")], "media",
                                               lambda m: estado.alterar(mapa_modo=m))
        ctl.addWidget(self.seg)
        ctl.addSpacing(12)
        self.chk_postos = QCheckBox("Mostrar postos")
        self.chk_postos.toggled.connect(lambda v: estado.alterar(mapa_postos=v))
        ctl.addWidget(self.chk_postos)
        ctl.addStretch(1)
        self.v.addLayout(ctl)
        linha = QHBoxLayout()
        linha.setSpacing(12)
        self.c_mapa = Cartao("Chuva média anual, 2001–2020", "Média dos totais anuais em cada UGRHI. Clique numa UGRHI para escolhê-la; clique de novo para voltar ao Estado.")
        self.mapa = MapaUGRHI(estado.base.regioes)
        self.mapa.clicado.connect(lambda s: estado.alterar(regiao="SP" if estado.regiao == s else s))
        self.c_mapa.add(self.mapa)
        self.leg_box, self.leg_lay = self.caixa()
        self.c_mapa.add(self.leg_box)
        self.c_rank = Cartao("Ranking das UGRHIs")
        self.c_rank.setFixedWidth(380)
        self.rank = Ranking()
        self.rank.clicado.connect(lambda s: estado.alterar(regiao="SP" if estado.regiao == s else s))
        self.c_rank.add(self.rank)
        self.c_rank.corpo.addStretch(1)
        linha.addWidget(self.c_mapa, 1, Qt.AlignTop)
        linha.addWidget(self.c_rank, 0, Qt.AlignTop)
        self.v.addLayout(linha)
        self.v.addStretch(1)

    def atualizar(self):
        e = self.estado
        self.definir_cabecalho(e.rotulo_regiao, e.subtitulo("Clique numa UGRHI para escolhê-la; clique de novo para voltar ao Estado"))
        for w, v in ((self.c_prod, None), (self.chk_postos, None)):
            w.blockSignals(True)
        self.c_prod.setCurrentIndex(SATELITES.index(e.mapa_produto))
        self.chk_postos.setChecked(e.mapa_postos)
        for w in (self.c_prod, self.chk_postos):
            w.blockSignals(False)
        for chave, botao in self.seg_botoes.items():
            botao.setChecked(chave == e.mapa_modo)
        media = e.mapa_modo == "media"
        self.c_mapa.titulo.setText("Chuva média anual, 2001–2020" if media else "Tendência do total anual (Sen)")
        valores = e.valores_mapa()
        vs = [v for v in valores.values() if finito(v)]
        escala = EscalaCor(min(vs or [0]), max(vs or [1]), not media)
        unid = "mm" if media else "mm/década"
        fmt = (lambda v: f"{num(v, 0)} mm") if media else (lambda v: f"{sinal(v, 1)} mm/década")
        self.mapa.definir(valores, escala, e.regiao, e.base.postos if e.mapa_postos else [], fmt)
        limpar_layout(self.leg_lay)
        self.leg_lay.addWidget(LegendaEscala(escala, lambda v, fim: (num(v, 0) if media else sinal(v, 0)) + (f" {unid}" if fim else "")))
        itens = sorted(((r.sigla, r.rotulo, valores[r.sigla]) for r in e.base.regioes
                        if r.sigla in valores and finito(valores[r.sigla])), key=lambda t: -t[2])
        self.c_rank.titulo.setText(f"Ranking das UGRHIs · {e.mapa_produto}")
        self.rank.definir(itens, escala, e.regiao, (lambda v: num(v, 0)) if media else (lambda v: sinal(v, 1)))


# ======================================================================= 3. Séries

class Series(Pagina):
    def __init__(self, estado):
        super().__init__(estado)
        self.c_mes = Cartao("Chuva mensal", "Total de cada mês (mm). Mês com mais de 3 dias sem dado fica em branco.")
        ctl = QHBoxLayout()
        self.s_ini, self.s_fim = QSpinBox(), QSpinBox()
        for s, rot in ((self.s_ini, "De"), (self.s_fim, "até")):
            s.setRange(1980, 2026)
            s.setLocale(LOCAL_BR)
            s.setGroupSeparatorShown(False)
            ctl.addWidget(rotulo(rot, quebra=False))
            ctl.addWidget(s)
        self.s_ini.valueChanged.connect(lambda v: estado.alterar(ano_inicial=v))
        self.s_fim.valueChanged.connect(lambda v: estado.alterar(ano_final=v))
        ctl.addStretch(1)
        self.c_mes.add(ctl)
        self.g_mes = GraficoLinhas(300)
        self.c_mes.add(self.g_mes)
        self.leg_mes, self.leg_mes_lay = self.caixa()
        self.c_mes.add(self.leg_mes)
        self.v.addWidget(self.c_mes)
        self.c_dia = Cartao("Chuva diária", "Dia de 0 h a 24 h UTC. Útil para conferir eventos extremos e a defasagem entre produtos.")
        ctl2 = QHBoxLayout()
        self.s_ano = QSpinBox()
        self.s_ano.setRange(1980, 2026)
        self.s_ano.setGroupSeparatorShown(False)
        self.s_ano.valueChanged.connect(lambda v: estado.alterar(ano_diario=v))
        ctl2.addWidget(rotulo("Ano", quebra=False))
        ctl2.addWidget(self.s_ano)
        ctl2.addSpacing(20)
        self.totais = rotulo("", secundario=True, quebra=False)
        ctl2.addWidget(self.totais)
        ctl2.addStretch(1)
        self.c_dia.add(ctl2)
        self.g_dia = GraficoLinhas(300)
        self.c_dia.add(self.g_dia)
        self.leg_dia, self.leg_dia_lay = self.caixa()
        self.c_dia.add(self.leg_dia)
        self.v.addWidget(self.c_dia)
        self.v.addStretch(1)

    def atualizar(self):
        e, b = self.estado, self.estado.base
        reg = e.regiao
        self.definir_cabecalho(e.rotulo_regiao, e.subtitulo("Chuva mensal e diária por produto"))
        for s, v in ((self.s_ini, e.ano_inicial), (self.s_fim, e.ano_final), (self.s_ano, e.ano_diario)):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)
        a0, a1 = min(e.ano_inicial, e.ano_final), max(e.ano_inicial, e.ano_final)
        series = {}
        for p in e.produtos_visiveis:
            s = b.mensal.get((p, reg))
            if s:
                serie = [(a * 12 + m - 1, s.valor(a, m)) for a in range(a0, a1 + 1) for m in range(1, 13)]
                if any(finito(y) for _, y in serie):
                    series[p] = serie
        ticks = [t * 12 for t in ticks_anos(a0, a1 + 1)]
        self.g_mes.definir(series, ticks, rotulo_x=lambda x: str(x // 12),
                           rotulo_dica=lambda x: f"{MESES[x % 12]}/{x // 12}", unidade="mm", incluir_zero=True)
        limpar_layout(self.leg_mes_lay)
        self.leg_mes_lay.addWidget(Legenda(list(series)))
        ano = e.ano_diario
        self.c_dia.titulo.setText(f"Chuva diária em {ano}")
        ini = dt.date(ano, 1, 1)
        n = (dt.date(ano + 1, 1, 1) - ini).days
        series_d, totais = {}, []
        for p in e.produtos_visiveis:
            s = b.diario(p, reg)
            if not s:
                continue
            serie = [(d + 1, s.valor(ini + dt.timedelta(days=d))) for d in range(n)]
            vals = [y for _, y in serie if finito(y)]
            if vals:
                series_d[p] = serie
                totais.append(f"{bolinha(p)} {NOME_PRODUTO[p]}: {num(sum(vals), 0)} mm")
        self.totais.setText("&nbsp;&nbsp;&nbsp;".join(totais))
        self.totais.setTextFormat(Qt.RichText)
        ticks_d = [(dt.date(ano, m, 1) - ini).days + 1 for m in range(1, 13)]
        self.g_dia.definir(series_d, ticks_d, rotulo_x=lambda d: MESES[(ini + dt.timedelta(days=d - 1)).month - 1],
                           rotulo_dica=lambda d: (ini + dt.timedelta(days=d - 1)).strftime("%d/%m/%Y"),
                           unidade="mm", casas=1, incluir_zero=True)
        limpar_layout(self.leg_dia_lay)
        self.leg_dia_lay.addWidget(Legenda(list(series_d)))


# ======================================================================= 4. Extremos

class Extremos(Pagina):
    exportar_indices = Signal()
    exportar_rclimdex = Signal(str)

    def __init__(self, estado):
        super().__init__(estado)
        c = Cartao("Parâmetros", "Os padrões são os do RClimDex: período-base 1981–2010, dia úmido com 1 mm ou mais e ano com "
                                 "no máximo 15 dias sem dado. Produtos que começam depois de 2010 usam como base toda a série disponível.")
        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        self.b_ini, self.b_fim, self.nn = QSpinBox(), QSpinBox(), QSpinBox()
        self.b_ini.setRange(1980, 2020)
        self.b_fim.setRange(1985, 2026)
        for s in (self.b_ini, self.b_fim):
            s.setGroupSeparatorShown(False)
        self.limiar = QDoubleSpinBox()
        self.limiar.setLocale(LOCAL_BR)
        self.limiar.setRange(0.1, 10)
        self.limiar.setSingleStep(0.1)
        self.limiar.setDecimals(1)
        self.limiar.setSuffix(" mm")
        self.nn.setRange(5, 300)
        self.nn.setSingleStep(5)
        self.nn.setSuffix(" mm")
        self.cruza = QCheckBox("CDD e CWD atravessam o ano")
        ctl.addWidget(rotulo("Período-base", quebra=False))
        ctl.addWidget(self.b_ini)
        ctl.addWidget(rotulo("a", quebra=False))
        ctl.addWidget(self.b_fim)
        ctl.addSpacing(14)
        ctl.addWidget(rotulo("Dia úmido", quebra=False))
        ctl.addWidget(self.limiar)
        ctl.addSpacing(14)
        ctl.addWidget(rotulo("Limiar do Rnnmm", quebra=False))
        ctl.addWidget(self.nn)
        ctl.addSpacing(14)
        ctl.addWidget(self.cruza)
        ctl.addStretch(1)
        self.padrao = QPushButton("Padrão do RClimDex")
        self.padrao.clicked.connect(lambda: estado.alterar(parametros=Parametros()))
        ctl.addWidget(self.padrao)
        c.add(ctl)
        self.v.addWidget(c)

        def novo_parametro(**kw):
            p = estado.parametros
            campos = dict(base_inicio=p.base_inicio, base_fim=p.base_fim, limiar_umido=p.limiar_umido, nn=p.nn,
                          sequencias_cruzam_anos=p.sequencias_cruzam_anos, max_faltas_ano=p.max_faltas_ano)
            campos.update(kw)
            estado.alterar(parametros=Parametros(**campos))

        self.b_ini.valueChanged.connect(lambda v: novo_parametro(base_inicio=v))
        self.b_fim.valueChanged.connect(lambda v: novo_parametro(base_fim=v))
        self.limiar.valueChanged.connect(lambda v: novo_parametro(limiar_umido=round(v, 1)))
        self.nn.valueChanged.connect(lambda v: novo_parametro(nn=float(v)))
        self.cruza.toggled.connect(lambda v: novo_parametro(sequencias_cruzam_anos=v))

        self.c_ind = Cartao("PRCPTOT")
        linha = QHBoxLayout()
        linha.addWidget(rotulo("Índice", quebra=False))
        self.c_combo = QComboBox()
        for i in INDICES:
            self.c_combo.addItem(i, i)
        self.c_combo.currentIndexChanged.connect(lambda k: estado.alterar(indice=self.c_combo.itemData(k)))
        linha.addWidget(self.c_combo)
        linha.addStretch(1)
        self.c_ind.add(linha)
        self.desc = rotulo("", secundario=True)
        self.c_ind.add(self.desc)
        self.g_ind = GraficoLinhas(300)
        self.c_ind.add(self.g_ind)
        self.leg_box, self.leg_lay = self.caixa()
        self.c_ind.add(self.leg_box)
        self.v.addWidget(self.c_ind)
        self.c_tend = Cartao("Tendências", "Sen e regressão linear por década; p do teste de Mann-Kendall e da regressão. ● marca p < 0,05 "
                                           "no Mann-Kendall. P95 e P99 são os limiares dos dias muito e extremamente úmidos no período-base usado.")
        self.tend_box, self.tend_lay = self.caixa()
        self.c_tend.add(self.tend_box)
        self.v.addWidget(self.c_tend)
        c_exp = Cartao("Exportar", "Os índices anuais de todos os produtos desta região vão para um CSV. A série diária de um produto "
                                   "pode ser gravada no formato de entrada do RClimDex original.")
        h = QHBoxLayout()
        b1 = QPushButton("Índices em CSV…")
        b1.clicked.connect(self.exportar_indices.emit)
        b2 = QToolButton()
        b2.setText("Série no formato RClimDex…")
        b2.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(b2)
        for p in PRODUTOS:
            menu.addAction(NOME_PRODUTO[p], lambda _=False, pp=p: self.exportar_rclimdex.emit(pp))
        b2.setMenu(menu)
        h.addWidget(b1)
        h.addWidget(b2)
        h.addStretch(1)
        c_exp.add(h)
        self.v.addWidget(c_exp)
        self.v.addStretch(1)

    def atualizar(self):
        e, b = self.estado, self.estado.base
        par, ind, reg = e.parametros, e.indice, e.regiao
        self.definir_cabecalho(e.rotulo_regiao, e.subtitulo("Índices de extremos de chuva do ETCCDI, calculados como no RClimDex"))
        for w in (self.b_ini, self.b_fim, self.limiar, self.nn, self.cruza, self.c_combo):
            w.blockSignals(True)
        self.b_ini.setValue(par.base_inicio)
        self.b_fim.setValue(par.base_fim)
        self.limiar.setValue(par.limiar_umido)
        self.nn.setValue(int(par.nn))
        self.cruza.setChecked(par.sequencias_cruzam_anos)
        for k, i in enumerate(INDICES):
            self.c_combo.setItemText(k, nome_indice(i, par.nn))
        self.c_combo.setCurrentIndex(INDICES.index(ind))
        for w in (self.b_ini, self.b_fim, self.limiar, self.nn, self.cruza, self.c_combo):
            w.blockSignals(False)
        self.padrao.setEnabled(par != Parametros())
        un = unidade(ind)
        self.c_ind.titulo.setText(f"{nome_indice(ind, par.nn)} ({un})")
        self.desc.setText(descricao_indice(ind, par.nn, par.limiar_umido))
        resultados = [(p, b.indices(p, reg, par)) for p in e.produtos_visiveis]
        resultados = [(p, r) for p, r in resultados if r]
        series = {p: r.serie(ind) for p, r in resultados}
        anos = [a for p, r in resultados for a in r.anos] or [1980, 2026]
        self.g_ind.definir(series, ticks_anos(min(anos), max(anos)), unidade=un, casas=0 if un == "dias" else 1)
        limpar_layout(self.leg_lay)
        self.leg_lay.addWidget(Legenda([p for p, _ in resultados]))
        self.c_tend.titulo.setText(f"Tendências de {nome_indice(ind, par.nn)}")
        linhas = []
        for p, r in resultados:
            t = tendencia(r.anos, r.valores[ind])
            linhas.append([f"{bolinha(p)} {NOME_PRODUTO[p]}", f"{t.ano_inicio}–{t.ano_fim}" if t else "—", str(t.n) if t else "—",
                           sinal(t.sen_por_decada if t else NAN, 2), ("● " if t and t.significativa else "") + p_texto(t.mk_p if t else NAN),
                           sinal(t.ols_por_decada if t else NAN, 2), p_texto(t.p_ols if t else NAN),
                           f"{num(r.p95, 1)} mm", f"{num(r.p99, 1)} mm", f"{r.base_usada[0]}–{r.base_usada[1]}"])
        limpar_layout(self.tend_lay)
        self.tend_lay.addWidget(Grade(["Produto", "Período", "Anos", "Sen/década", "p (MK)", "Linear/década", "p (linear)", "P95", "P99", "Base"],
                                      linhas, direita={2, 3, 4, 5, 6, 7, 8}))


# ======================================================================= 5. Validação

def _espalhamento(texto: str) -> float:
    h = int(hashlib.md5(texto.encode()).hexdigest()[:8], 16)
    return (h % 1000) / 1000 - 0.5


class Validacao(Pagina):
    def __init__(self, estado):
        super().__init__(estado)
        self.c_disp = Cartao("Distribuição entre os postos", "Um ponto por posto; o traço marca a mediana. IMERG e CMORPH começam em 1998, "
                                                             "depois da maior parte das séries de postos, e por isso têm poucos postos em comum.")
        self.seg, self.seg_botoes = segmentado(METRICAS, "rDiario", lambda m: estado.alterar(metrica=m))
        self.c_disp.add(self.seg)
        self.disp = Dispersao(320)
        self.c_disp.add(self.disp)
        self.v.addWidget(self.c_disp)
        self.c_med = Cartao("Mediana entre os postos", "Viés: diferença percentual do total do satélite em relação ao posto. "
                                                       "KGE: eficiência de Kling-Gupta. CSI: acerto dos dias com chuva (limiar de 1 mm).")
        self.med_box, self.med_lay = self.caixa()
        self.c_med.add(self.med_box)
        self.v.addWidget(self.c_med)
        self.v.addStretch(1)

    def atualizar(self):
        e, b = self.estado, self.estado.base
        reg, met = e.regiao, e.metrica
        self.definir_cabecalho(e.rotulo_regiao, e.subtitulo("Cada posto comparado com o pixel do satélite que o contém"))
        for chave, botao in self.seg_botoes.items():
            botao.setChecked(chave == met)
        lista = b.validacoes(reg)
        prods = [p for p in SATELITES if any(v["produto"] == p for v in lista)]
        grupos, ys = [], []
        for i, p in enumerate(prods):
            vs = [v for v in lista if v["produto"] == p and v[met] is not None]
            pontos = [(i + 0.62 * _espalhamento(v["estacao"]), v[met], f"{v['estacao']} · {v['sigla']}") for v in vs]
            ys += [y for _, y, _ in pontos]
            grupos.append((p, pontos, mediana([y for _, y, _ in pontos])))
        if ys:
            ys.sort()
            baixo = ys[int((len(ys) - 1) * 0.01)]
            alto = ys[int((len(ys) - 1) * 0.995)]
            lo = min(baixo, 0) if met == "viesPct" else baixo
            folga = max((alto - lo) * 0.05, 0.01)
            fmt = (lambda v: f"{sinal(v, 1)}%") if met == "viesPct" else (lambda v: num(v, 2))
            self.disp.definir(grupos, (lo - folga, alto + folga), fmt)
        linhas = []
        for p in prods:
            linhas.append([f"{bolinha(p)} {NOME_PRODUTO[p]}", str(b.mediana_validacao(p, reg, "rDiario")[1]),
                           num(b.mediana_validacao(p, reg, "rDiario")[0], 2), num(b.mediana_validacao(p, reg, "rMensal")[0], 2),
                           sinal(b.mediana_validacao(p, reg, "viesPct")[0], 1), num(b.mediana_validacao(p, reg, "kge")[0], 2),
                           num(b.mediana_validacao(p, reg, "csi")[0], 2)])
        limpar_layout(self.med_lay)
        self.med_lay.addWidget(Grade(["Produto", "Postos", "r diário", "r mensal", "Viés (%)", "KGE", "CSI"], linhas, direita={1, 2, 3, 4, 5, 6}))


# ======================================================================= 6. Postos

class ItemNumero(QTableWidgetItem):
    """Célula que ordena pelo número e mostra o texto formatado."""

    def __init__(self, valor: float, texto: str):
        super().__init__(texto)
        self.valor = valor
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, outro):
        return self.valor < getattr(outro, "valor", 0)


class Postos(Pagina):
    COLUNAS = ["Código GHCN", "Nome", "Rede", "Código original", "UGRHI", "Início", "Fim", "Dias com dado"]

    def __init__(self, estado):
        super().__init__(estado)
        c1 = Cartao("Postos com dado em cada ano", "O gráfico mostra quando a rede do GHCN-Daily encolhe em SP. "
                                                   "Os anos recentes dependem do HidroWeb (ANA) e do SIBH (DAEE).")
        self.barras = BarrasAnos(220)
        c1.add(self.barras)
        self.v.addWidget(c1)
        c2 = Cartao("Lista de postos", "Clique no título de uma coluna para ordenar. O botão Exportar CSV salva a lista filtrada.")
        h = QHBoxLayout()
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por nome, código ou rede (ex.: Bauru, E3-052, ANA)")
        self.busca.setClearButtonEnabled(True)
        self.busca.setMinimumWidth(380)
        self.busca.setMaximumWidth(460)
        self.busca.textChanged.connect(lambda t: estado.alterar(busca=t))
        h.addWidget(self.busca)
        self.contagem = rotulo("", secundario=True, quebra=False)
        h.addWidget(self.contagem)
        h.addStretch(1)
        c2.add(h)
        self.tabela = QTableWidget(0, len(self.COLUNAS))
        self.tabela.setHorizontalHeaderLabels(self.COLUNAS)
        self.tabela.verticalHeader().hide()
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setShowGrid(False)
        self.tabela.setMinimumHeight(440)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.Interactive)
        cab.setStretchLastSection(True)
        for i, w in enumerate([130, 260, 120, 130, 90, 100, 100]):
            self.tabela.setColumnWidth(i, w)
        cab.setSortIndicator(0, Qt.AscendingOrder)
        c2.add(self.tabela)
        self.v.addWidget(c2)
        self.v.addStretch(1)

    def lista(self) -> list:
        e = self.estado
        q = e.busca.strip().lower()
        base = e.base.postos_na_regiao(e.regiao)
        if not q:
            return base
        return [p for p in base if q in f"{p['id']} {p['nome']} {p['rede']} {p['codigoOriginal']}".lower()]

    def atualizar(self):
        e, b = self.estado, self.estado.base
        n = len(b.postos_na_regiao(e.regiao))
        self.definir_cabecalho(e.rotulo_regiao, e.subtitulo(f"{num(n, 0)} postos com dados desde 1980 (GHCN-Daily: ANA e DAEE)"))
        self.barras.definir(b.postos_por_ano.get(e.regiao, []))
        if self.busca.text() != e.busca:
            self.busca.blockSignals(True)
            self.busca.setText(e.busca)
            self.busca.blockSignals(False)
        lista = self.lista()
        self.contagem.setText(f"{num(len(lista), 0)} postos")
        t = self.tabela
        t.setSortingEnabled(False)
        t.setRowCount(len(lista))
        for i, p in enumerate(lista):
            for j, v in enumerate([p["id"], p["nome"], p["rede"], p["codigoOriginal"], p["sigla"], p["inicio"], p["fim"]]):
                t.setItem(i, j, QTableWidgetItem(v))
            t.setItem(i, 7, ItemNumero(p["dias"], num(p["dias"], 0)))
        t.setSortingEnabled(True)


# ======================================================================= 7. Produtos e fontes

REPOSITORIO = "https://github.com/rafagsanches-cloud/blank-app/blob/claude/happy-brahmagupta-udhdxu/"
ARQUIVOS = [
    ("Excel principal: anual, mensal, diário, postos e validação", "saidas/Chuva_SP_1980-2026_satelites_e_postos.xlsx"),
    ("Excel horário do CMORPH", "saidas/Chuva_SP_horario_CMORPH_1998-2026.xlsx"),
    ("Excel horário do IMERG", "saidas/Chuva_SP_horario_IMERG_1998-2026.xlsx"),
    ("Shapefile das UGRHIs", "dados/ugrhi/UGRHI_SP_shapefile.zip"),
    ("UGRHIs como objeto sf do R (.rds)", "dados/ugrhi/ugrhi_sp.rds"),
]


class Produtos(Pagina):
    def __init__(self, estado):
        super().__init__(estado)
        b = estado.base
        self.definir_cabecalho("Produtos e fontes", "A tabela de produtos de satélite, as bases de dados e os arquivos do projeto")
        c = Cartao("Produtos de satélite", "A tabela pedida, com a versão de cada produto usada aqui e o período baixado.")
        linhas = [[f"{bolinha(p['produto'])} <b>{p['produto']}</b>", p["sensor"], p["serie"], p["resolucao"], p["foco"], p["versao"], p["periodo"]]
                  for p in b.produtos]
        c.add(Grade(["Produto", "Tipo de sensor principal", "Série histórica", "Resolução espacial", "Foco principal", "Versão usada", "Período baixado"], linhas))
        self.v.addWidget(c)
        linha = QHBoxLayout()
        linha.setSpacing(12)
        cb = Cartao("Bases de dados")
        for f in b.fontes:
            l = rotulo(f"<a href='{f['endereco']}'>{f['base']}</a><br><span style='font-size:8.5pt'>{f['grupo']} · {f['descricao']}</span>")
            l.setOpenExternalLinks(True)
            cb.add(l)
        cb.corpo.addStretch(1)
        linha.addWidget(cb, 1)
        col = QVBoxLayout()
        ca = Cartao("Arquivos para baixar", "No GitHub. O Excel abre no Excel e no LibreOffice.")
        for titulo, caminho in ARQUIVOS:
            l = rotulo(f"<a href='{REPOSITORIO}{caminho}'>{titulo}</a>")
            l.setOpenExternalLinks(True)
            ca.add(l)
        col.addWidget(ca)
        cm = Cartao("Como os números foram feitos")
        for t in [
            "Cada pixel entra na média da UGRHI com peso igual à fração da sua área dentro dela, multiplicada pelo cosseno da latitude. "
            "A média só é calculada quando pelo menos metade da área tem dado.",
            "As faltas seguem o RClimDex: o mês fica em branco com mais de 3 dias sem dado e o ano com mais de 15. "
            "Os dias dos satélites vão de 0 h a 24 h UTC.",
            "Os índices ETCCDI deste app foram conferidos contra o ClimdexSP em R, que por sua vez coincide com o pacote climdex.pcic.",
            "O CMORPH fica abaixo dos outros produtos em todo o Estado; a soma das 24 horas reproduz o arquivo diário oficial, "
            "então a diferença é do próprio produto. O IMERG usado é a versão Late Run v07.",
        ]:
            cm.add(rotulo(t))
        col.addWidget(cm)
        col.addStretch(1)
        linha.addLayout(col, 1)
        self.v.addLayout(linha)
        self.v.addStretch(1)


TELAS = {"visaoGeral": VisaoGeral, "mapa": Mapa, "series": Series, "extremos": Extremos, "validacao": Validacao,
         "postos": Postos, "produtos": Produtos}
