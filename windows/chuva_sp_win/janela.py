"""Janela principal: barra lateral com as análises, seletor de região, produtos e exportação."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QMessageBox, QSizePolicy, QStackedWidget, QToolBar, QToolButton,
                               QVBoxLayout, QWidget)

from .calculos import INDICES, csv_num, nome_indice
from .componentes import rotulo
from .dados import NOME_PRODUTO, PRODUTOS
from .tema import aplicar_paleta, icone
from .telas import ABAS, TELAS, Estado

ICONE_APP = Path(__file__).resolve().parent / "icone.png"


class Janela(QMainWindow):
    def __init__(self, estado: Estado):
        super().__init__()
        self.estado = estado
        self.setWindowTitle("Chuva SP")
        if ICONE_APP.exists():
            self.setWindowIcon(QIcon(str(ICONE_APP)))
        self.resize(1400, 900)
        self.setMinimumSize(1080, 700)
        self._pendente = False
        self._sujas = set()

        # barra de ferramentas: região, título da tela, produtos, exportar
        barra = QToolBar("Barra")
        barra.setMovable(False)
        barra.setIconSize(QSize(18, 18))
        barra.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(barra)
        self.regiao = QComboBox()
        self.regiao.setMinimumWidth(300)
        for r in estado.base.regioes:
            self.regiao.addItem(r.rotulo, r.sigla)
        self.regiao.setToolTip("Escolha o Estado inteiro ou uma UGRHI")
        self.regiao.currentIndexChanged.connect(lambda i: estado.alterar(regiao=self.regiao.itemData(i)))
        barra.addWidget(self.regiao)
        titulo = QWidget()
        tl = QVBoxLayout(titulo)
        tl.setContentsMargins(12, 0, 0, 0)
        tl.setSpacing(0)
        self.t_aba = rotulo("", negrito=True, quebra=False)
        self.t_reg = rotulo("", secundario=True, quebra=False)
        tl.addWidget(self.t_aba)
        tl.addWidget(self.t_reg)
        barra.addWidget(titulo)
        espaco = QWidget()
        espaco.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        barra.addWidget(espaco)
        self.b_prod = QToolButton()
        self.b_prod.setText("Produtos")
        self.b_prod.setIcon(icone("filtro"))
        self.b_prod.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.b_prod.setPopupMode(QToolButton.InstantPopup)
        self.b_prod.setToolTip("Mostrar ou esconder produtos nos gráficos")
        menu = QMenu(self.b_prod)
        self.acoes_prod = {}
        for p in PRODUTOS:
            a = menu.addAction(NOME_PRODUTO[p])
            a.setCheckable(True)
            a.setChecked(True)
            a.toggled.connect(lambda v, pp=p: self._alternar_produto(pp, v))
            self.acoes_prod[p] = a
        self.b_prod.setMenu(menu)
        barra.addWidget(self.b_prod)
        self.a_exportar = QAction(icone("exportar"), "Exportar CSV", self)
        self.a_exportar.setShortcut(QKeySequence("Ctrl+E"))
        self.a_exportar.setToolTip("Salvar os dados desta tela em CSV (abre no Excel) – Ctrl+E")
        self.a_exportar.triggered.connect(self.exportar_csv)
        barra.addAction(self.a_exportar)

        # menus
        m_arq = self.menuBar().addMenu("&Arquivo")
        m_arq.addAction(self.a_exportar)
        m_arq.addSeparator()
        m_arq.addAction("Sair", QKeySequence.Quit, self.close)
        m_ajuda = self.menuBar().addMenu("A&juda")
        m_ajuda.addAction("Sobre o Chuva SP", self.sobre)

        # barra lateral + telas
        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        lateral = QWidget()
        lateral.setObjectName("painelLateral")
        lateral.setFixedWidth(250)
        lv = QVBoxLayout(lateral)
        lv.setContentsMargins(10, 12, 10, 12)
        lv.addWidget(rotulo("Análises", secundario=True, tamanho=8.5, negrito=True))
        self.lista = QListWidget()
        self.lista.setObjectName("lateral")
        self.lista.setIconSize(QSize(18, 18))
        for chave, nome in ABAS:
            it = QListWidgetItem(icone(chave), nome)
            it.setData(Qt.UserRole, chave)
            it.setSizeHint(QSize(200, 34))
            self.lista.addItem(it)
        self.lista.currentRowChanged.connect(lambda i: estado.alterar(aba=ABAS[i][0]))
        lv.addWidget(self.lista, 1)
        lv.addWidget(rotulo("Satélites e postos, 1980–2026", secundario=True, tamanho=8.5))
        lv.addWidget(rotulo("Dados dentro do app; funciona sem internet.", secundario=True, tamanho=8))
        h.addWidget(lateral)
        self.pilha = QStackedWidget()
        self.telas = {}
        for chave, _ in ABAS:
            t = TELAS[chave](estado)
            self.telas[chave] = t
            self.pilha.addWidget(t)
        self.telas["extremos"].exportar_indices.connect(self.exportar_csv)
        self.telas["extremos"].exportar_rclimdex.connect(self.exportar_rclimdex)
        h.addWidget(self.pilha, 1)
        self.setCentralWidget(central)

        estado.mudou.connect(self._agendar)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._trocou_tema)
        self._sujas = set(self.telas)
        self._atualizar()

    # ---- atualização (adiada para juntar várias mudanças)
    def _agendar(self):
        self._sujas = set(self.telas)
        if not self._pendente:
            self._pendente = True
            QTimer.singleShot(0, self._atualizar)

    def _trocou_tema(self, *_):
        aplicar_paleta(QApplication.instance())
        for chave, nome in ABAS:
            self.lista.item([c for c, _ in ABAS].index(chave)).setIcon(icone(chave))
        self._agendar()

    def _atualizar(self):
        self._pendente = False
        e = self.estado
        i = [c for c, _ in ABAS].index(e.aba)
        for w, v in ((self.lista, i), (self.regiao, self.regiao.findData(e.regiao))):
            w.blockSignals(True)
            (w.setCurrentRow if w is self.lista else w.setCurrentIndex)(v)
            w.blockSignals(False)
        for p, a in self.acoes_prod.items():
            a.blockSignals(True)
            a.setChecked(p in e.visiveis)
            a.blockSignals(False)
        self.pilha.setCurrentWidget(self.telas[e.aba])
        self.t_aba.setText(dict(ABAS)[e.aba])
        self.t_reg.setText(e.rotulo_regiao)
        if e.aba in self._sujas:
            self.telas[e.aba].atualizar()
            self._sujas.discard(e.aba)

    def _alternar_produto(self, p, visivel):
        v = set(self.estado.visiveis)
        v.add(p) if visivel else v.discard(p)
        self.estado.alterar(visiveis=v)

    # ---- exportação
    def _salvar(self, texto: str, nome: str, filtro: str) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar", str(Path.home() / nome), filtro)
        if not caminho:
            return
        try:
            Path(caminho).write_text(texto, encoding="utf-8")
        except OSError as erro:
            QMessageBox.warning(self, "Chuva SP", f"Não consegui salvar o arquivo:\n{erro}")

    def csv_aba_atual(self) -> tuple:
        e, b = self.estado, self.estado.base
        reg = e.regiao
        L = []
        linha = lambda campos: L.append(";".join(str(c) for c in campos))  # noqa: E731
        if e.aba == "visaoGeral":
            nome = f"chuva_anual_{reg}.csv"
            linha(["ano"] + [NOME_PRODUTO[p] for p in PRODUTOS])
            series = [dict(b.serie_anual(p, reg)) for p in PRODUTOS]
            for a in sorted({a for s in series for a in s}):
                linha([a] + [csv_num(s.get(a), 1) for s in series])
        elif e.aba == "mapa":
            nome = f"mapa_{e.mapa_produto}_{e.mapa_modo}.csv"
            linha(["sigla", "ugrhi", "media_2001_2020_mm" if e.mapa_modo == "media" else "sen_mm_por_decada"])
            v = e.valores_mapa()
            for r in b.regioes:
                if r.sigla != "SP":
                    linha([r.sigla, r.rotulo, csv_num(v.get(r.sigla), 1)])
        elif e.aba == "series":
            nome = f"chuva_mensal_{reg}.csv"
            linha(["ano", "mes"] + [NOME_PRODUTO[p] for p in PRODUTOS])
            ss = [b.mensal.get((p, reg)) for p in PRODUTOS]
            for a in range(min(e.ano_inicial, e.ano_final), max(e.ano_inicial, e.ano_final) + 1):
                for m in range(1, 13):
                    linha([a, m] + [csv_num(s.valor(a, m) if s else None, 1) for s in ss])
        elif e.aba == "extremos":
            nome = f"indices_etccdi_{reg}.csv"
            linha(["produto", "ano"] + [nome_indice(i, e.parametros.nn) for i in INDICES])
            for p in PRODUTOS:
                r = b.indices(p, reg, e.parametros)
                if r:
                    for k, a in enumerate(r.anos):
                        linha([p, a] + [csv_num(r.valores[i][k], 2) for i in INDICES])
        elif e.aba == "validacao":
            nome = f"validacao_{reg}.csv"
            linha(["produto", "posto", "ugrhi", "rede", "dias_comuns", "r_diario", "r_mensal", "vies_pct", "kge", "csi"])
            for v in b.validacoes(reg):
                linha([v["produto"], v["estacao"], v["sigla"], v["rede"], v["diasComuns"], csv_num(v["rDiario"], 3),
                       csv_num(v["rMensal"], 3), csv_num(v["viesPct"], 1), csv_num(v["kge"], 3), csv_num(v["csi"], 3)])
        elif e.aba == "postos":
            nome = f"postos_{reg}.csv"
            linha(["codigo_ghcn", "nome", "rede", "codigo_original", "ugrhi", "lat", "lon", "altitude_m", "inicio", "fim", "dias_com_dado"])
            for p in self.telas["postos"].lista():
                linha([p["id"], p["nome"], p["rede"], p["codigoOriginal"], p["sigla"], csv_num(p["lat"], 4), csv_num(p["lon"], 4),
                       csv_num(p["altitude"], 0), p["inicio"], p["fim"], p["dias"]])
        else:
            nome = "produtos_satelite.csv"
            linha(["Produto", "Tipo de Sensor Principal", "Série Histórica", "Resolução Espacial", "Foco Principal", "Versão usada", "Período baixado"])
            for p in b.produtos:
                linha([p["produto"], p["sensor"], p["serie"], p["resolucao"], p["foco"], p["versao"], p["periodo"]])
        return nome, "﻿" + "\n".join(L) + "\n"  # BOM: o Excel reconhece os acentos

    def exportar_csv(self):
        nome, texto = self.csv_aba_atual()
        self._salvar(texto, nome, "CSV (*.csv)")

    def exportar_rclimdex(self, produto: str):
        s = self.estado.base.diario(produto, self.estado.regiao)
        if not s:
            return
        linhas = []
        for i, v in enumerate(s.valores):
            d = s.inicio + dt.timedelta(days=i)
            pr = f"{v:.1f}" if v == v else "-99.9"
            linhas.append(f"{d.year} {d.month} {d.day} {pr} -99.9 -99.9")
        self._salvar("\n".join(linhas) + "\n", f"{produto}_{self.estado.regiao}_rclimdex.txt", "Texto (*.txt)")

    def sobre(self):
        QMessageBox.about(self, "Chuva SP",
                          "<b>Chuva SP</b> 1.0<br>Chuva por satélite (CHIRPS, IMERG, PERSIANN, CMORPH, GPCP) e postos "
                          "pluviométricos (ANA e DAEE, via GHCN-Daily) nas UGRHIs de São Paulo, 1980–2026.<br><br>"
                          "Rafael Grecco Sanches")
