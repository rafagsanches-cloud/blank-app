"""Chuva SP para Windows – ponto de entrada.

Rodar a partir do código:   python windows/ChuvaSP.py
Argumentos opcionais:       --aba <nome> --regiao <sigla> --tema claro|escuro
Capturas de tela (teste):   python windows/ChuvaSP.py --capturas <pasta> [--tema escuro]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


def argumento(nome: str):
    a = sys.argv
    return a[a.index(nome) + 1] if nome in a and a.index(nome) + 1 < len(a) else None


def capturar(janela, pasta: Path, tema: str) -> None:
    from PySide6.QtWidgets import QApplication

    pasta.mkdir(parents=True, exist_ok=True)
    cenarios = [("1_visao_geral", "visaoGeral", "SP"), ("2_mapa", "mapa", "UGRHI13"), ("3_series", "series", "UGRHI05"),
                ("4_extremos", "extremos", "UGRHI13"), ("5_validacao", "validacao", "SP"), ("6_postos", "postos", "UGRHI13"),
                ("7_produtos", "produtos", "SP")]
    for nome, aba, reg in cenarios:
        janela.estado.alterar(aba=aba, regiao=reg)
        for _ in range(5):
            QApplication.processEvents()
        janela.grab().save(str(pasta / f"{nome}_janela_{tema}.png"))
        tela = janela.telas[aba]
        tela.interno.adjustSize()
        tela.interno.grab().save(str(pasta / f"{nome}_{tema}.png"))
        print("captura:", nome, tema, flush=True)


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Chuva SP")
    app.setOrganizationName("Rafael Grecco Sanches")
    app.setStyle("Fusion")
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))
    tema = argumento("--tema")
    if tema in ("claro", "escuro"):
        QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Dark if tema == "escuro" else Qt.ColorScheme.Light)

    from chuva_sp_win.dados import BaseDados
    from chuva_sp_win.janela import Janela
    from chuva_sp_win.tema import aplicar_paleta, definir_preferencia
    from chuva_sp_win.telas import ABAS, Estado

    definir_preferencia(tema)

    aplicar_paleta(app)
    try:
        base = BaseDados()
    except Exception as erro:  # dados ausentes ou corrompidos
        QMessageBox.critical(None, "Chuva SP", f"Não consegui ler os dados do aplicativo.\n\n{erro}")
        return 1
    estado = Estado(base)
    aba, reg = argumento("--aba"), argumento("--regiao")
    if aba in dict(ABAS):
        estado.aba = aba
    if reg in base.por_sigla:
        estado.regiao = reg
    janela = Janela(estado)
    janela.show()
    pasta = argumento("--capturas")
    if pasta:
        capturar(janela, Path(pasta), tema or "claro")
        return 0
    return app.exec()


if __name__ == "__main__":
    if os.environ.get("QT_QPA_PLATFORM") is None and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.exit(main())
