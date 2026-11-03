# =============================================================================
#  ClimdexSP - Bases de dados de chuva (satélites e estações) para São Paulo
#  Autor: Rafael Grecco Sanches
# =============================================================================

# -----------------------------------------------------------------------------
#  Bases de dados (lista indicada - mantida como está)
# -----------------------------------------------------------------------------
#  - EPAGRI/CIRAM ........ https://ciram.epagri.sc.gov.br/index.php/imagem-de-satelite/
#  - NOAA Satellites ..... https://www.nesdis.noaa.gov/
#  - TRMM ................ https://gpm.nasa.gov/missions/trmm
#  - DAEE ................ https://sibh.sp.gov.br/
#  - ANA (todas as estações superficiais convencionais e automáticas)
#                          https://www.snirh.gov.br/hidroweb/
# -----------------------------------------------------------------------------
bases_dados <- data.frame(
  base = c(
    "EPAGRI/CIRAM",
    "NOAA Satellites",
    "TRMM",
    "DAEE",
    "ANA (todas as estações superficiais convencionais e automáticas)"
  ),
  endereco = c(
    "https://ciram.epagri.sc.gov.br/index.php/imagem-de-satelite/",
    "https://www.nesdis.noaa.gov/",
    "https://gpm.nasa.gov/missions/trmm",
    "https://sibh.sp.gov.br/",
    "https://www.snirh.gov.br/hidroweb/"
  ),
  stringsAsFactors = FALSE
)

# -----------------------------------------------------------------------------
#  Produtos de precipitação por satélite
# -----------------------------------------------------------------------------
produtos_satelite <- data.frame(
  Produto = c("CHIRPS", "IMERG (GPM)", "PERSIANN", "CMORPH"),
  `Tipo de Sensor Principal` = c(
    "Infravermelho + Estações",
    "Micro-ondas + Radar",
    "Infravermelho + IA",
    "Micro-ondas \"Morfado\""
  ),
  `Série Histórica` = c("Desde 1981", "Desde 2000", "Desde 1983 (versão CDR)", "Desde 2002"),
  `Resolução Espacial` = c("~5 km", "~10 km", "~25 km", "~8 km"),
  `Foco Principal` = c(
    "Monitoramento agrícola e tendências de seca a longo prazo.",
    "Precisão física de tempestades, neve e meteorologia global.",
    "Padrões de nuvens e estimativas baseadas em aprendizado de máquina.",
    "Movimento contínuo de precipitação e taxas de chuva em tempo real."
  ),
  check.names = FALSE,
  stringsAsFactors = FALSE
)

# Versões efetivamente baixadas pelo programa (chuva_sp, em Python) e onde estão
produtos_usados <- data.frame(
  produto = c("CHIRPS", "IMERG", "PERSIANN", "CMORPH", "GPCP"),
  versao = c(
    "CHIRPS v3.0 RNL diário (0,05°)",
    "GPM IMERG v07 Late Run (0,1°, 30 min)",
    "PERSIANN-CDR v01r01 diário (0,25°)",
    "CMORPH CDR v1.0 horário (0,25°)",
    "GPCP v2.3 mensal (2,5°) e v1.3 diário (1°)"
  ),
  inicio = c("1981-01-01", "1998-01-01", "1983-01-01", "1998-01-01", "1979-01-01"),
  acesso = c(
    "s3://eu-central-1.opendata.source.coop/wfp/chirps-rnl-daily/",
    "s3://dynamical-nasa-imerg/nasa-imerg-analysis-late/ (Icechunk/Zarr)",
    "s3://noaa-cdr-precip-persiann-pds/",
    "s3://noaa-cdr-precip-cmorph-pds/",
    "s3://noaa-cdr-precip-gpcp-monthly-pds/ e s3://noaa-cdr-precip-gpcp-daily-pds/"
  ),
  stringsAsFactors = FALSE
)

# Estações: o programa usa o GHCN-Daily (NOAA), que redistribui postos ANA e DAEE de SP
estacoes_usadas <- data.frame(
  fonte = c("GHCN-Daily (NOAA)", "ANA HidroWeb", "DAEE / SIBH", "INMET automáticas"),
  conteudo = c(
    "~1.070 postos de SP (ANA e DAEE), diário, 1980 até ~2005",
    "convencionais (diário) e telemétricas (15 min) - rodar localmente",
    "postos pluviométricos do Estado - exportar do SIBH",
    "horário desde 2000 - portal.inmet.gov.br/dadoshistoricos"
  ),
  stringsAsFactors = FALSE
)
