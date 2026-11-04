# Chuva em São Paulo por UGRHI: satélites e postos pluviométricos (1980–2026)

Este repositório reúne três peças que trabalham juntas:

1. `chuva_sp/` – programa em Python que baixa as estimativas de chuva por satélite (CHIRPS, IMERG, PERSIANN, CMORPH e GPCP) e os postos pluviométricos de SP, calcula a chuva média de cada uma das 22 UGRHIs e grava tudo em Excel, nas escalas anual, mensal, diária e horária.
2. `streamlit_app.py` – aplicativo para consultar séries, mapas, extremos, postos e validação, baixar as planilhas e buscar novos períodos direto das fontes.
3. `R/` – o **ClimdexSP**, programa em R no estilo do RClimDex: controle de qualidade, índices ETCCDI de precipitação, tendências (linear, Mann-Kendall e Sen), validação satélite × posto e interface gráfica em Shiny. Inclui também a conversão dos limites das UGRHIs para objeto `sf`.

Os arquivos já processados estão em `saidas/` e `dados/`, prontos para uso.

## App para Mac

`macos/` tem o **Chuva SP**, app nativo para macOS (SwiftUI e Swift Charts, Apple Silicon e Intel, macOS 14 ou mais novo). Ele traz os mesmos dados deste repositório dentro dele e funciona sem internet: visão geral, mapa clicável das UGRHIs, séries mensais e diárias, índices ETCCDI recalculáveis como no RClimDex, validação satélite × postos e lista de postos. Instalação e compilação: [`macos/LEIAME.md`](macos/LEIAME.md).

## Arquivos prontos

| Arquivo | Conteúdo |
|---|---|
| `saidas/Chuva_SP_1980-2026_satelites_e_postos.xlsx` | Pasta principal (ver planilhas abaixo) |
| `saidas/Chuva_SP_horario_CMORPH_1998-2026.xlsx` | CMORPH horário, 22 UGRHIs + Estado |
| `saidas/Chuva_SP_horario_IMERG_1998-2026.xlsx` | IMERG horário, 22 UGRHIs + Estado |
| `saidas/climdexsp/` | Resultados do ClimdexSP (índices, tendências, QC, gráficos do Estado) |
| `dados/ugrhi/UGRHI_SP_shapefile.zip` | Shapefile das 22 UGRHIs (SIRGAS/WGS84 geográfico) |
| `dados/ugrhi/ugrhi_sp.rds` | Os mesmos limites como objeto `sf` do R |
| `dados/ugrhi/UGRHI_SP.gpkg` | GeoPackage |
| `dados/processados/` | Séries em Parquet/CSV usadas pelo aplicativo |

Planilhas da pasta principal:

- `LEIA-ME`, `Produtos`, `Fontes`, `UGRHIs`: documentação, a tabela de produtos e a lista de bases de dados.
- `Anual_UGRHI_satelites`, `Mensal_UGRHI_satelites`, `Diário_UGRHI_satelites`: uma linha por produto e data, com as 22 UGRHIs e o Estado nas colunas. Use o filtro da coluna `produto`. A linha `POSTOS (média simples)` é a média aritmética dos postos de cada UGRHI (mínimo de 3 postos no dia).
- `Postos_inventario`, `Postos_n_por_ano`, `Postos_anual`, `Postos_mensal`, `Postos_diário`: os 1.067 postos de SP, um por coluna.
- `Validacao_sat_x_postos`: viés, correlação, RMSE, MAE, KGE e POD/FAR/CSI de cada satélite contra cada posto (pixel × ponto).

Os dados horários ficam em pastas separadas porque o Excel aceita no máximo 1.048.576 linhas por planilha, e cada produto horário tem cerca de 250 mil horas.

## Produtos de satélite

| Produto | Tipo de Sensor Principal | Série Histórica | Resolução Espacial | Foco Principal |
|---|---|---|---|---|
| CHIRPS | Infravermelho + Estações | Desde 1981 | ~5 km | Monitoramento agrícola e tendências de seca a longo prazo. |
| IMERG (GPM) | Micro-ondas + Radar | Desde 2000 | ~10 km | Precisão física de tempestades, neve e meteorologia global. |
| PERSIANN | Infravermelho + IA | Desde 1983 (versão CDR) | ~25 km | Padrões de nuvens e estimativas baseadas em aprendizado de máquina. |
| CMORPH | Micro-ondas "Morfado" | Desde 2002 | ~8 km | Movimento contínuo de precipitação e taxas de chuva em tempo real. |

Versões efetivamente usadas:

| Produto | Versão | Período baixado | Grade | Onde está |
|---|---|---|---|---|
| CHIRPS | v3.0 RNL, diário | 1981 → último dia publicado | 0,05° | `s3://eu-central-1.opendata.source.coop/wfp/chirps-rnl-daily` |
| IMERG | v07 Late Run, 30 min | 1998 → hoje | 0,1° | `s3://dynamical-nasa-imerg` (Icechunk/Zarr) |
| PERSIANN | CDR v01r01, diário | 1983 → último mês publicado | 0,25° | `s3://noaa-cdr-precip-persiann-pds` |
| CMORPH | CDR v1.0 ajustado, horário | 1998 → último mês publicado | 0,25° | `s3://noaa-cdr-precip-cmorph-pds` |
| GPCP | v2.3 mensal / v1.3 diário | 1980 (mensal), 1996 (diário) | 2,5° / 1° | `s3://noaa-cdr-precip-gpcp-*-pds` |

O GPCP entrou como referência de longo prazo porque é o único destes produtos que cobre 1980. O IMERG v07 já incorpora o período TRMM (1998–2014), por isso a série começa em 1998 e não em 2000.

## Bases de dados

Lista indicada, mantida no código R (`R/00_fontes_dados.R`) exatamente como pedida:

- [EPAGRI/CIRAM](https://ciram.epagri.sc.gov.br/index.php/imagem-de-satelite/)
- NOAA Satellites
- TRMM
- DAEE
- ANA (todas as estações superficiais convencionais e automáticas)

### Postos pluviométricos

Os postos vêm do GHCN-Daily (NOAA), que redistribui as séries diárias da rede da ANA e do DAEE. Em SP são 1.067 postos com dados a partir de 1980 (944 do DAEE e 123 da ANA), somando 6,5 milhões de valores diários. O código original de cada posto (por exemplo `02345067` da ANA ou `E3-052` do DAEE) está no inventário.

A maioria dessas séries termina entre 1997 e 2005. Para os anos recentes, o programa tem módulos prontos para a ANA (`chuva_sp/estacoes/ana.py`: web service SOAP e leitura dos arquivos exportados do HidroWeb), para o INMET (`inmet.py`: estações automáticas horárias desde 2000) e para o DAEE/SIBH (`daee.py`: leitura de arquivos exportados do portal).

> **Limitação desta versão.** O ambiente de nuvem em que os arquivos foram gerados não tinha acesso aos servidores da ANA, do DAEE/SIBH, do INMET, da NASA (Earthdata) nem do CHC/UCSB. Por isso os satélites foram baixados de cópias oficiais na AWS, e os postos recentes e as séries horárias de estação não entraram nesta rodada. Na sua máquina, basta rodar `python -m chuva_sp --ana --inmet` para acrescentá-los.

## Como usar

### Python (baixar tudo e gerar o Excel)

```bash
pip install -r requirements.txt
python -m chuva_sp                       # satélites + postos + validação + Excel
python -m chuva_sp --produtos CHIRPS     # só alguns produtos
python -m chuva_sp --ana --inmet         # inclui ANA e INMET (precisa de acesso a esses sites)
```

Os downloads ficam em cache por ano/mês em `dados/cache/`; rodar de novo só busca o que falta. A primeira rodada completa leva de uma a duas horas, conforme a conexão (o CMORPH horário, com ~250 mil arquivos, é a parte mais longa).

### Aplicativo

```bash
streamlit run streamlit_app.py
```

Abas: séries por UGRHI e escala, mapa das médias e tendências, extremos ETCCDI, postos, validação, produtos e fontes, e download/busca de dados.

### ClimdexSP (R)

Pacotes: `sf`, `readxl`, `openxlsx`, `shiny`, `DT` (rode `R/instalar_pacotes.R`).

```r
# interface gráfica, no espírito do RClimDex
shiny::runApp("R/app_climdexsp.R")

# em lote: todos os produtos x 22 UGRHIs + Estado
source("R/exemplo_rodar_climdexsp.R")

# uso direto das funções
source("R/ClimdexSP.R")
d   <- ler_chuva_excel("saidas/Chuva_SP_1980-2026_satelites_e_postos.xlsx", "diario", "satelites")
s   <- series_satelite_ugrhi(d, produtos = "CHIRPS", regioes = "13 - Tietê/Jacaré")[[1]]
q   <- qc_chuva(s$data, s$prcp)
ind <- indices_climdex(q$serie$data, q$serie$prcp, base = c(1981, 2010), nn = 50)
tendencia(ind$anual$ano, ind$anual$PRCPTOT)

# limites das UGRHIs como objeto sf
source("R/01_ugrhi_para_R.R")
ugrhi <- carregar_ugrhi()
```

O ClimdexSP calcula PRCPTOT, SDII, R10mm, R20mm, Rnnmm, CDD, CWD, R95p, R99p, R95pTOT, R99pTOT, Rx1day e Rx5day (anuais e mensais). Os resultados foram conferidos contra o pacote `climdex.pcic` com a série do CHIRPS para o Estado, de 1981 a 2025: os 11 índices principais coincidem em todos os anos. A função `escrever_rclimdex()` exporta qualquer série no formato de entrada do RClimDex original.

## Primeiros resultados (Estado de São Paulo)

Média anual da chuva no Estado e tendência de Sen sobre toda a série de cada produto (teste de Mann-Kendall):

| Produto | Anos | Média 2001–2020 (mm) | Tendência (mm/década) | p (MK) |
|---|---|---|---|---|
| CHIRPS | 1981–2025 | 1.475 | −73 | 0,001 |
| IMERG | 1998–2025 | 1.500 | −110 | 0,025 |
| PERSIANN | 1983–2025 | 1.515 | −57 | 0,022 |
| CMORPH | 1998–2025 | 1.257 | −169 | <0,001 |
| GPCP | 1980–2025 | 1.482 | −55 | 0,013 |
| Postos (média) | 1980–1999 | – | −29 | 0,59 |

Todos os produtos de satélite indicam redução da chuva anual no Estado, influenciada pelos anos secos recentes (2014, 2020–2021, 2024). O CMORPH fica cerca de 18% abaixo dos demais em todo o período; conferi que a soma das 24 horas reproduz o arquivo diário oficial do CMORPH, então a diferença é do produto. Na validação contra os postos, a correlação diária mediana foi 0,52 para o CHIRPS, 0,41 para o PERSIANN, 0,39 para o IMERG e 0,38 para o CMORPH; na escala mensal sobe para 0,78–0,93. A comparação do IMERG e do CMORPH usa só 51 postos, porque poucas séries do GHCN passam de 1998.

## Métodos

Média areal. Cada pixel recebe peso igual à fração da sua área dentro da UGRHI, multiplicada por cos(latitude). Pixels sem dado são ignorados, e a média só é calculada quando pelo menos metade da área tem dado. O Estado é a soma das 22 UGRHIs.

Escalas e faltas. Seguem as regras do RClimDex/ETCCDI: o dia falta se alguma hora faltar, o mês se faltarem mais de 3 dias e o ano se faltarem mais de 15. Por isso o ano corrente aparece vazio na escala anual. Os produtos horários estão em UTC, com uma coluna extra no horário de Brasília (UTC−3); o dia vai de 00 a 24 UTC. A função `dia_pluviometrico()` do ClimdexSP reagrega a série horária no dia de leitura das 7h, convenção dos pluviômetros.

Validação. Cada posto é comparado com o pixel do satélite que o contém, nos dias em que os dois têm dado. Como o dia do pluviômetro (7h às 7h) não coincide com o dia UTC, o programa testa defasagens de −1, 0 e +1 dia e usa a de maior correlação média: 0 para CHIRPS e PERSIANN e +1 dia para o IMERG.

## Limites das UGRHIs

O arquivo enviado (`dados/brutos/sibh_ugrhis_sp.csv`, exportado do GeoServer do SIBH) tinha dois problemas, corrigidos tanto em Python quanto em R: as coordenadas estavam na ordem latitude/longitude e os nomes vinham com acentuação corrompida (UTF-8 gravado duas vezes). Também foi corrigido "Jundaí" para "Jundiaí". A área total resultante é de 249.193 km².

## Estrutura

```
chuva_sp/            pacote Python (satelites/, estacoes/, agregacao, validacao, excel, pipeline)
streamlit_app.py     aplicativo web (Streamlit)
macos/               app nativo para Mac (SwiftUI), dados embutidos e scripts de compilação
R/                   ClimdexSP, app Shiny, fontes de dados, conversão das UGRHIs
dados/brutos/        CSV original das UGRHIs
dados/ugrhi/         shapefile, GeoPackage, GeoJSON simplificado e .rds
dados/processados/   séries processadas (Parquet/CSV)
saidas/              pastas de trabalho do Excel e resultados do ClimdexSP
```

## Citações

- Funk et al. (2015), *Scientific Data* 2:150066 (CHIRPS); Climate Hazards Center CHIRPS3, doi:10.15780/G2JQ0P
- Huffman et al. (2023), GPM IMERG Late Precipitation L3 Half Hourly 0.1° V07, NASA GES DISC
- Ashouri et al. (2015), *BAMS* 96:69–83 (PERSIANN-CDR)
- Xie et al. (2017), *J. Hydrometeorology* 18:1617–1641 (CMORPH CDR)
- Adler et al. (2018), *Atmosphere* 9:138 (GPCP v2.3)
- Menne et al. (2012), *J. Atmos. Oceanic Technol.* 29:897–910 (GHCN-Daily)
- Zhang et al. (2011), *WIREs Climate Change* 2:851–870 (índices ETCCDI)
