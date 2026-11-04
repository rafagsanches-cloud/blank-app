@echo off
rem Gera o Chuva SP para Windows a partir do codigo (precisa do Python 3.10 ou mais novo).
rem Uso: clique duas vezes neste arquivo ou rode "windows\construir_windows.bat" na pasta do repositorio.
cd /d "%~dp0\.."
py -3 -m pip install --upgrade "PySide6>=6.7" "pyinstaller>=6.10" || goto erro
py -3 windows\testar_calculos.py || goto erro
py -3 -m PyInstaller --noconfirm --clean --windowed --name ChuvaSP --icon windows\icone.ico ^
  --add-data "macos\ChuvaSP\Dados;Dados" --add-data "windows\chuva_sp_win\icone.png;chuva_sp_win" ^
  --paths windows --exclude-module tkinter windows\ChuvaSP.py || goto erro
echo.
echo Pronto: dist\ChuvaSP\ChuvaSP.exe
pause
exit /b 0
:erro
echo.
echo Algo deu errado; veja as mensagens acima.
pause
exit /b 1
