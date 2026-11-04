# Chuva SP para Windows

Versão para Windows 10 e 11 (64 bits) do app do Mac, com as mesmas sete telas, os mesmos dados e os mesmos cálculos. Mostra a chuva do Estado de São Paulo por UGRHI: satélites CHIRPS, IMERG, PERSIANN, CMORPH e GPCP e os postos pluviométricos da ANA e do DAEE (GHCN-Daily), de 1980 a 2026. Os dados vão dentro do programa, então ele funciona sem internet.

O app é escrito em Python com Qt (PySide6) e lê a mesma pasta de dados do app do Mac (`macos/ChuvaSP/Dados`). Os índices ETCCDI são calculados por uma tradução direta do núcleo em Swift, e os dois são conferidos contra o ClimdexSP em R.

## O que o app faz

| Tela | Conteúdo |
|---|---|
| Visão geral | Chuva média, tendência, postos e correlação com os pluviômetros; chuva anual por produto; chuva média por mês; tabela de tendências |
| Mapa das UGRHIs | Média 2001–2020 ou tendência de Sen por UGRHI, com ranking; clique numa UGRHI para escolhê-la; opção de mostrar os postos |
| Séries mensais e diárias | Chuva mês a mês num intervalo de anos e dia a dia num ano escolhido |
| Extremos (RClimDex) | Os 13 índices ETCCDI recalculados no próprio app, com período-base, limiar do dia úmido e limiar do Rnnmm ajustáveis; tendências de Sen, Mann-Kendall e regressão linear |
| Satélite × postos | Distribuição das métricas (r, viés, KGE, CSI) por posto e as medianas |
| Postos pluviométricos | Lista com busca e ordenação; número de postos com dado em cada ano |
| Produtos e fontes | A tabela de produtos, as bases de dados e links para os arquivos |

A região (Estado ou UGRHI) fica na caixa do canto superior esquerdo. O botão Produtos esconde ou mostra séries nos gráficos. Exportar CSV (ou Ctrl+E) salva os dados da tela atual num CSV separado por ponto e vírgula, que o Excel abre com os acentos certos. Na tela de extremos dá para gravar a série diária de um produto no formato de entrada do RClimDex original.

O app segue o tema claro ou escuro do Windows e se ajusta a janelas pequenas (a partir de 900 × 600): os cartões passam para uma coluna e as tabelas largas rolam para o lado dentro do próprio cartão.

## Instalar a versão pronta

Baixe em <https://github.com/rafagsanches-cloud/blank-app/releases/tag/app-windows> um dos dois arquivos:

- `ChuvaSP-Instalador.exe`: instala para o seu usuário, sem pedir senha de administrador, e cria atalho no menu Iniciar (e na área de trabalho, se você marcar). Desinstala pelo painel de aplicativos do Windows.
- `ChuvaSP-Windows-portatil.zip`: não instala nada. Extraia a pasta onde quiser (até num pen drive) e abra `ChuvaSP.exe`.

Na primeira vez, o Windows pode mostrar a tela azul "O Windows protegeu o computador", porque o programa não tem assinatura digital paga. Clique em "Mais informações" e depois em "Executar assim mesmo". Isso só acontece uma vez.

A página da versão também traz imagens de cada tela nos temas claro e escuro, geradas automaticamente no Windows a cada compilação.

## Rodar a partir do código

Precisa do Python 3.10 ou mais novo (<https://www.python.org/downloads/>, marque "Add python.exe to PATH" na instalação). No Prompt de Comando, dentro da pasta do repositório:

```bat
py -3 -m pip install "PySide6>=6.7"
py -3 windows\ChuvaSP.py
```

Opções úteis: `--regiao UGRHI13` abre já numa UGRHI, `--aba extremos` abre numa tela (`visaoGeral`, `mapa`, `series`, `extremos`, `validacao`, `postos`, `produtos`) e `--tema escuro` ou `--tema claro` ignora o tema do Windows.

Para conferir os cálculos com o R:

```bat
py -3 windows\testar_calculos.py
```

O resultado esperado é "2911 comparações, 0 falhas".

## Gerar o instalador no seu PC

Clique duas vezes em `windows\construir_windows.bat`. Ele instala o PySide6 e o PyInstaller, roda o teste dos cálculos e cria `dist\ChuvaSP\ChuvaSP.exe`. Para gerar também o instalador, instale o Inno Setup 6 (<https://jrsoftware.org/isdl.php>) e compile `windows\instalador.iss`; o arquivo sai em `dist_instalador\`.

No GitHub, o fluxo `.github/workflows/app-windows.yml` faz tudo isso numa máquina Windows a cada mudança na pasta `windows/` ou nos dados e publica a versão.

## Atualizar os dados

Os dois apps usam a mesma pasta de dados. Depois de rodar o programa Python (`python -m chuva_sp`), gere os dados de novo e abra o app:

```bat
py -3 macos\gerar_dados.py
py -3 windows\ChuvaSP.py
```

Para usar outra pasta de dados sem mexer no repositório, defina a variável de ambiente `CHUVASP_DADOS` com o caminho dela.
