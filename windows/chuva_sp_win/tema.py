"""Cores, fontes e ícones (mesma paleta do app do Mac, do painel e do Streamlit)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QPolygonF

CORES_PRODUTO = {
    "CHIRPS": ("#2a78d6", "#3987e5"),
    "IMERG": ("#eb6834", "#d95926"),
    "PERSIANN": ("#1baf7a", "#199e70"),
    "CMORPH": ("#eda100", "#c98500"),
    "GPCP": ("#e87ba4", "#d55181"),
    "POSTOS": ("#008300", "#0ca30c"),
}


_preferencia: str | None = None  # "claro", "escuro" ou None (segue o Windows)


def definir_preferencia(tema: str | None) -> None:
    global _preferencia
    _preferencia = tema if tema in ("claro", "escuro") else None


def escuro() -> bool:
    if _preferencia:
        return _preferencia == "escuro"
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def cor_produto(p: str) -> QColor:
    claro, esc = CORES_PRODUTO.get(p, ("#52514e", "#c3c2b7"))
    return QColor(esc if escuro() else claro)


class T:
    """Tokens do tema atual (recalculados a cada troca de tema)."""

    fundo = cartao = borda = texto = secundario = grade = eixo = destaque = barra_lateral = ""

    @classmethod
    def atualizar(cls) -> None:
        if escuro():
            cls.fundo, cls.cartao, cls.borda = "#1f1f1f", "#2b2b2b", "#3b3b3b"
            cls.texto, cls.secundario = "#f2f2f2", "#b4b4b4"
            cls.grade, cls.eixo, cls.destaque = "#3a3a3a", "#5a5a5a", "#3987e5"
            cls.barra_lateral = "#262626"
        else:
            cls.fundo, cls.cartao, cls.borda = "#f3f3f3", "#ffffff", "#e3e3e3"
            cls.texto, cls.secundario = "#1b1b1b", "#5f5f5f"
            cls.grade, cls.eixo, cls.destaque = "#e6e6e6", "#c3c2b7", "#2a78d6"
            cls.barra_lateral = "#ebebeb"


def aplicar_paleta(app) -> None:
    T.atualizar()
    p = QPalette()
    p.setColor(QPalette.Window, QColor(T.fundo))
    p.setColor(QPalette.WindowText, QColor(T.texto))
    p.setColor(QPalette.Base, QColor(T.cartao))
    p.setColor(QPalette.AlternateBase, QColor(T.fundo))
    p.setColor(QPalette.Text, QColor(T.texto))
    p.setColor(QPalette.Button, QColor(T.cartao))
    p.setColor(QPalette.ButtonText, QColor(T.texto))
    p.setColor(QPalette.PlaceholderText, QColor(T.secundario))
    p.setColor(QPalette.Highlight, QColor(T.destaque))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipBase, QColor(T.cartao))
    p.setColor(QPalette.ToolTipText, QColor(T.texto))
    p.setColor(QPalette.Link, QColor(T.destaque))
    p.setColor(QPalette.Mid, QColor(T.borda))
    p.setColor(QPalette.Midlight, QColor(T.borda))
    app.setPalette(p)
    app.setStyleSheet(f"""
        QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget#pagina {{ background: {T.fundo}; }}
        QFrame#cartao {{ background: {T.cartao}; border: 1px solid {T.borda}; border-radius: 10px; }}
        QListWidget#lateral {{ background: {T.barra_lateral}; border: none; outline: none; }}
        QListWidget#lateral::item {{ padding-left: 8px; border-radius: 6px; color: {T.texto}; }}
        QListWidget#lateral::item:selected {{ background: {'#3a3a3a' if escuro() else '#dcdcdc'}; color: {T.texto}; }}
        QListWidget#lateral::item:hover:!selected {{ background: {'#303030' if escuro() else '#e4e4e4'}; }}
        QWidget#painelLateral {{ background: {T.barra_lateral}; }}
        QLabel#secundario {{ color: {T.secundario}; }}
        QToolBar {{ background: {T.fundo}; border: none; border-bottom: 1px solid {T.borda}; spacing: 8px; padding: 6px; }}
        QPushButton#segmento {{ border: 1px solid {T.borda}; padding: 4px 12px; background: {T.cartao}; color: {T.texto}; }}
        QPushButton#segmento:checked {{ background: {T.destaque}; color: white; border-color: {T.destaque}; }}
        QTableWidget {{ gridline-color: {T.borda}; border: 1px solid {T.borda}; border-radius: 6px; }}
        QHeaderView::section {{ background: {T.cartao}; color: {T.secundario}; border: none; border-bottom: 1px solid {T.borda}; padding: 4px 6px; font-weight: 600; }}
        QToolTip {{ background: {T.cartao}; color: {T.texto}; border: 1px solid {T.borda}; padding: 4px; }}
    """)


def fonte_titulo(tamanho: int = 22) -> QFont:
    f = QFont("Georgia")
    f.setStyleHint(QFont.Serif)
    f.setPointSize(tamanho)
    return f


def icone(nome: str, cor: str | None = None, tam: int = 20) -> QIcon:
    """Ícones simples desenhados à mão (iguais em qualquer Windows)."""
    pix = QPixmap(tam * 2, tam * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2, 2)
    c = QColor(cor or T.destaque or "#2a78d6")
    pen = QPen(c, 1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    s = tam
    if nome == "visaoGeral":
        p.drawPolyline(QPolygonF([QPointF(3, 14), QPointF(7, 9), QPointF(11, 12), QPointF(17, 5)]))
        p.drawLine(QPointF(3, 17), QPointF(17, 17))
    elif nome == "mapa":
        p.drawPolygon(QPolygonF([QPointF(3, 5), QPointF(8, 3), QPointF(12, 5), QPointF(17, 3), QPointF(17, 15),
                                 QPointF(12, 17), QPointF(8, 15), QPointF(3, 17)]))
        p.drawLine(QPointF(8, 3), QPointF(8, 15))
        p.drawLine(QPointF(12, 5), QPointF(12, 17))
    elif nome == "series":
        p.drawRoundedRect(QRectF(3, 4, 14, 13), 2, 2)
        p.drawLine(QPointF(3, 8), QPointF(17, 8))
        for x in (7, 10, 13):
            p.drawPoint(QPointF(x, 12))
    elif nome == "extremos":
        path = QPainterPath()
        path.addEllipse(QRectF(3, 5, 8, 6))
        path.addEllipse(QRectF(7, 3, 9, 8))
        p.drawPath(path.simplified())
        p.drawPolyline(QPolygonF([QPointF(10, 11), QPointF(8, 15), QPointF(11, 15), QPointF(9, 18)]))
    elif nome == "validacao":
        p.drawEllipse(QRectF(3, 3, 14, 14))
        p.drawPolyline(QPolygonF([QPointF(6.5, 10), QPointF(9, 12.5), QPointF(13.5, 7.5)]))
    elif nome == "postos":
        path = QPainterPath()
        path.moveTo(10, 18)
        path.cubicTo(4, 11, 4, 3, 10, 3)
        path.cubicTo(16, 3, 16, 11, 10, 18)
        p.drawPath(path)
        p.drawEllipse(QRectF(8, 7, 4, 4))
    elif nome == "produtos":
        p.drawEllipse(QRectF(3, 3, 14, 14))
        p.drawLine(QPointF(10, 9), QPointF(10, 14))
        p.drawPoint(QPointF(10, 6.5))
    elif nome == "exportar":
        p.drawLine(QPointF(10, 3), QPointF(10, 12))
        p.drawPolyline(QPolygonF([QPointF(6.5, 6.5), QPointF(10, 3), QPointF(13.5, 6.5)]))
        p.drawPolyline(QPolygonF([QPointF(5, 10), QPointF(4, 10), QPointF(4, 17), QPointF(16, 17), QPointF(16, 10), QPointF(15, 10)]))
    elif nome == "filtro":
        for y, (a, b) in zip((6, 10, 14), ((3, 17), (6, 14), (8.5, 11.5))):
            p.drawLine(QPointF(a, y), QPointF(b, y))
    p.end()
    del s
    return QIcon(pix)
