# Chuva SP para macOS

App nativo (SwiftUI e Swift Charts) com a chuva do Estado de São Paulo por UGRHI: satélites CHIRPS, IMERG, PERSIANN, CMORPH e GPCP e os postos pluviométricos da ANA e do DAEE (GHCN-Daily), de 1980 a 2026. Os dados vão dentro do app (cerca de 8 MB), então ele funciona sem internet.

Requisitos: macOS 14 Sonoma ou mais novo (inclusive macOS 26 Tahoe), em Mac com Apple Silicon (M1, M2…) ou Intel.

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

A região (Estado ou UGRHI) é escolhida na barra de ferramentas. O botão **Exportar CSV** (ou ⌘E) salva os dados da tela atual num CSV que abre no Numbers e no Excel. Na tela de extremos dá para gravar a série diária de um produto no formato de entrada do RClimDex original.

Os índices do app são conferidos automaticamente contra o ClimdexSP em R (`macos/testar_calculos.sh`), que por sua vez coincide com o pacote `climdex.pcic`.

## Instalar a versão pronta

1. Baixe `Chuva-SP-macOS.zip` em <https://github.com/rafagsanches-cloud/blank-app/releases/tag/app-macos> e abra o arquivo (o Finder descompacta).
2. Arraste `Chuva SP.app` para a pasta Aplicativos.
3. Na primeira vez, o macOS avisa que não pode verificar o desenvolvedor, porque o app não é assinado por uma conta paga da Apple. Abra **Ajustes do Sistema > Privacidade e Segurança**, role até o aviso sobre "Chuva SP" e clique em **Abrir Mesmo Assim**. Também resolve, no Terminal:

   ```bash
   xattr -dr com.apple.quarantine "/Applications/Chuva SP.app"
   ```

A página da versão também mostra imagens de cada tela, geradas automaticamente a cada compilação.

## Compilar no seu Mac

Precisa só das Ferramentas de Linha de Comando do Xcode (não é preciso instalar o Xcode inteiro). No Terminal, dentro da pasta do repositório:

```bash
xcode-select --install          # só na primeira vez
bash macos/testar_calculos.sh   # opcional: confere os índices com o R
bash macos/construir_app.sh     # cria macos/build/Chuva SP.app
open "macos/build/Chuva SP.app"
```

Um app compilado na própria máquina abre direto, sem o aviso do item 3.

## Atualizar os dados

Depois de rodar o programa Python (`python -m chuva_sp`), gere de novo os dados do app e compile:

```bash
python macos/gerar_dados.py
bash macos/construir_app.sh
```
