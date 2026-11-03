# =============================================================================
#  Limites das UGRHIs de São Paulo -> objeto sf do R (+ shapefile e GeoPackage)
#
#  Entrada : dados/brutos/sibh_ugrhis_sp.csv (exportado do GeoServer do SIBH/DAEE)
#  Saídas  : dados/ugrhi/ugrhi_sp.rds        (objeto sf para o R)
#            dados/ugrhi/UGRHI_SP.gpkg       (GeoPackage)
#            dados/ugrhi/UGRHI_SP_shp/       (shapefile, se shp = TRUE)
#  O shapefile pronto para baixar também está em dados/ugrhi/UGRHI_SP_shapefile.zip
#
#  O CSV tem dois problemas que este script corrige:
#   1) a geometria WKT está com os eixos trocados (latitude, longitude);
#   2) os nomes vêm com acentuação corrompida (UTF-8 gravado duas vezes).
# =============================================================================

suppressPackageStartupMessages(library(sf))

ler_ugrhi_csv <- function(arquivo = "dados/brutos/sibh_ugrhis_sp.csv") {
  tab <- utils::read.csv(arquivo, stringsAsFactors = FALSE, encoding = "UTF-8")

  # 1) acentos: desfaz a dupla codificação ("TietÃª" -> "Tietê")
  corrige <- function(x) {
    y <- iconv(x, from = "UTF-8", to = "latin1")
    Encoding(y) <- "UTF-8"
    ifelse(is.na(y), x, y)
  }
  nome <- corrige(tab$nome)
  nome <- gsub("/ ", "/", nome, fixed = TRUE)
  nome <- sub("Jundaí", "Jundiaí", nome, fixed = TRUE)  # erro de digitação na fonte

  # 2) geometria: troca (lat, lon) -> (lon, lat) com uma matriz de permutação
  geom <- sf::st_as_sfc(tab$the_geom) * matrix(c(0, 1, 1, 0), 2, 2)
  geom <- sf::st_make_valid(sf::st_set_crs(geom, 4326))

  ugrhi <- sf::st_sf(
    codigo = as.integer(tab$codigo),
    sigla = sprintf("UGRHI%02d", as.integer(tab$codigo)),
    nome = nome,
    fonte = tab$fonte,
    geometry = geom
  )
  ugrhi$area_km2 <- as.numeric(sf::st_area(sf::st_transform(ugrhi, 5880))) / 1e6  # SIRGAS 2000 / Brazil Polyconic
  ugrhi[order(ugrhi$codigo), ]
}

exportar_ugrhi <- function(ugrhi, pasta = "dados/ugrhi", shp = FALSE) {
  dir.create(pasta, showWarnings = FALSE, recursive = TRUE)
  saveRDS(ugrhi, file.path(pasta, "ugrhi_sp.rds"))
  gpkg <- file.path(pasta, "UGRHI_SP.gpkg")
  sf::st_write(ugrhi, gpkg, layer = "ugrhi_sp", delete_dsn = file.exists(gpkg), quiet = TRUE)
  if (shp) {
    dir.create(file.path(pasta, "UGRHI_SP_shp"), showWarnings = FALSE)
    arq <- file.path(pasta, "UGRHI_SP_shp", "UGRHI_SP.shp")
    sf::st_write(ugrhi, arq, layer_options = "ENCODING=UTF-8", delete_dsn = file.exists(arq), quiet = TRUE)
  }
  invisible(ugrhi)
}

# Carrega o objeto já convertido (ou converte na primeira vez)
carregar_ugrhi <- function(pasta = "dados/ugrhi") {
  rds <- file.path(pasta, "ugrhi_sp.rds")
  if (file.exists(rds)) return(readRDS(rds))
  exportar_ugrhi(ler_ugrhi_csv(), pasta)
}

if (sys.nframe() == 0) {
  u <- ler_ugrhi_csv()
  exportar_ugrhi(u)
  print(sf::st_drop_geometry(u))
  cat(sprintf("\nÁrea total: %.0f km²\n", sum(u$area_km2)))
}
