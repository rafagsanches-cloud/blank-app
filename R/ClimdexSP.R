# =============================================================================
#  ClimdexSP  -  Índices de extremos de precipitação (ETCCDI) no estilo RClimDex
#                para satélites (CHIRPS, IMERG, PERSIANN, CMORPH, GPCP) e
#                postos pluviométricos nas UGRHIs de São Paulo.
#
#  Funções principais
#    ler_chuva_excel()      lê as pastas do Excel geradas pelo programa chuva_sp
#    ler_rclimdex()         lê arquivo no formato RClimDex (ano mes dia prcp tmax tmin)
#    escrever_rclimdex()    grava série no formato RClimDex (para usar no RClimDex original)
#    qc_chuva()             controle de qualidade (negativos, extremos, outliers, repetições)
#    indices_climdex()      PRCPTOT, SDII, R10mm, R20mm, Rnnmm, CDD, CWD, R95p, R99p,
#                           R95pTOT, R99pTOT, Rx1day, Rx5day (anuais e mensais)
#    tendencia()            regressão linear (como no RClimDex) + Mann-Kendall + Sen
#    validar_satelite()     viés, r, RMSE, MAE, KGE, POD, FAR, CSI
#    dia_pluviometrico()    agrega série horária (UTC) no dia de leitura das 7h locais
#    rodar_climdexsp()      executa tudo em lote e grava CSV, PNG e Excel
#
#  Referências: Zhang et al. (2011) WIREs Clim Change 2:851-870 (ETCCDI);
#  Zhang & Yang (2004) RClimDex User Manual; Bronaugh (2020) climdex.pcic.
# =============================================================================

suppressPackageStartupMessages({
  library(readxl)
  library(openxlsx)
})

CLIMDEXSP_VERSAO <- "1.0.0"

# Diretório deste arquivo (para achar 00_fontes_dados.R ao usar source())
.climdexsp_dir <- local({
  d <- tryCatch(dirname(sys.frame(1)$ofile), error = function(e) NULL)
  if (is.null(d) || !nzchar(d)) "R" else d
})
if (file.exists(file.path(.climdexsp_dir, "00_fontes_dados.R"))) {
  source(file.path(.climdexsp_dir, "00_fontes_dados.R"), encoding = "UTF-8")
}

# -----------------------------------------------------------------------------
#  Leitura e escrita
# -----------------------------------------------------------------------------

#' Lê as planilhas geradas pelo chuva_sp.
#' tipo = "satelites": devolve formato longo (produto, data, regiao, chuva_mm)
#' tipo = "postos"   : devolve formato largo (data + uma coluna por posto)
ler_chuva_excel <- function(arquivo, escala = c("diario", "mensal", "anual"),
                            tipo = c("satelites", "postos")) {
  escala <- match.arg(escala)
  tipo <- match.arg(tipo)
  aba_esc <- c(diario = "Diário", mensal = "Mensal", anual = "Anual")[[escala]]
  if (tipo == "satelites") {
    aba <- paste0(aba_esc, "_UGRHI_satelites")
    t <- readxl::read_excel(arquivo, sheet = aba, guess_max = 1e5)
    t <- as.data.frame(t, check.names = FALSE)
    col_t <- names(t)[2]
    regioes <- setdiff(names(t), c("produto", col_t))
    longo <- data.frame(
      produto = rep(t$produto, times = length(regioes)),
      data = rep(t[[col_t]], times = length(regioes)),
      regiao = rep(regioes, each = nrow(t)),
      chuva_mm = unlist(t[regioes], use.names = FALSE),
      stringsAsFactors = FALSE
    )
    if (escala != "anual") longo$data <- as.Date(longo$data)
    return(longo)
  }
  aba <- paste0("Postos_", c(diario = "diário", mensal = "mensal", anual = "anual")[[escala]])
  t <- as.data.frame(readxl::read_excel(arquivo, sheet = aba, guess_max = 1e5), check.names = FALSE)
  if (escala != "anual") t[[1]] <- as.Date(t[[1]])
  names(t)[1] <- "data"
  t
}

#' Inventário dos postos (aba Postos_inventario)
ler_inventario_postos <- function(arquivo) {
  as.data.frame(readxl::read_excel(arquivo, sheet = "Postos_inventario"))
}

#' Lê arquivo no formato RClimDex: ano mes dia prcp tmax tmin (falta = -99.9)
ler_rclimdex <- function(arquivo) {
  t <- utils::read.table(arquivo, header = FALSE, col.names = c("ano", "mes", "dia", "prcp", "tmax", "tmin"),
                         na.strings = c("-99.9", "-99.90", "-99"))
  data.frame(data = as.Date(sprintf("%04d-%02d-%02d", t$ano, t$mes, t$dia)), prcp = t$prcp)
}

#' Grava no formato RClimDex (tmax/tmin = -99.9 quando não houver)
escrever_rclimdex <- function(datas, prcp, arquivo, tmax = NULL, tmin = NULL) {
  n <- length(datas)
  f <- function(x) ifelse(is.na(x), -99.9, round(x, 1))
  tab <- data.frame(
    as.integer(format(datas, "%Y")), as.integer(format(datas, "%m")), as.integer(format(datas, "%d")),
    f(prcp), f(if (is.null(tmax)) rep(NA, n) else tmax), f(if (is.null(tmin)) rep(NA, n) else tmin)
  )
  utils::write.table(tab, arquivo, row.names = FALSE, col.names = FALSE, sep = " ")
  invisible(arquivo)
}

# Completa o calendário diário (dias ausentes viram NA)
completar_calendario <- function(datas, prcp) {
  datas <- as.Date(datas)
  ok <- !is.na(datas) & !duplicated(datas)
  datas <- datas[ok]
  prcp <- prcp[ok]
  todas <- seq(as.Date(paste0(format(min(datas), "%Y"), "-01-01")),
               as.Date(paste0(format(max(datas), "%Y"), "-12-31")), by = "day")
  data.frame(data = todas, prcp = prcp[match(todas, datas)])
}

# -----------------------------------------------------------------------------
#  Controle de qualidade (inspirado no QC do RClimDex)
# -----------------------------------------------------------------------------
qc_chuva <- function(datas, prcp, limite_max = 400, n_iqr = 3, n_repetidos = 4,
                     dias_secos_suspeitos = 120, remover_acima_limite = FALSE) {
  s <- completar_calendario(datas, prcp)
  x <- s$prcp
  flags <- list()
  marca <- function(i, problema) {
    if (length(i)) flags[[length(flags) + 1]] <<- data.frame(data = s$data[i], valor = x[i], problema = problema)
  }

  # 1) negativos -> falta
  i <- which(x < 0)
  marca(i, "valor negativo (removido)")
  x[i] <- NA

  # 2) acima do limite físico
  i <- which(x > limite_max)
  marca(i, sprintf("acima de %g mm/dia%s", limite_max, if (remover_acima_limite) " (removido)" else ""))
  if (remover_acima_limite) x[i] <- NA

  # 3) outliers por mês do ano (dias úmidos): > P75 + n_iqr * IQR
  mes <- as.integer(format(s$data, "%m"))
  for (m in 1:12) {
    v <- x[mes == m & !is.na(x) & x >= 1]
    if (length(v) < 20) next
    lim <- stats::quantile(v, 0.75) + n_iqr * stats::IQR(v)
    marca(which(mes == m & !is.na(x) & x > lim), sprintf("outlier (> P75 + %g*IQR do mês = %.1f mm)", n_iqr, lim))
  }

  # 4) mesmo valor (>= 1 mm) repetido em dias seguidos
  r <- rle(ifelse(is.na(x), -1, round(x, 1)))
  fim <- cumsum(r$lengths)
  ini <- fim - r$lengths + 1
  k <- which(r$values >= 1 & r$lengths >= n_repetidos)
  for (j in k) marca(ini[j]:fim[j], sprintf("valor %.1f repetido %d dias", r$values[j], r$lengths[j]))

  # 5) sequência muito longa de zeros (possível falta registrada como zero)
  k <- which(r$values == 0 & r$lengths >= dias_secos_suspeitos)
  for (j in k) marca(ini[j], sprintf("%d dias seguidos com zero a partir desta data", r$lengths[j]))

  fl <- if (length(flags)) do.call(rbind, flags) else data.frame(data = as.Date(character()), valor = numeric(), problema = character())
  fl <- fl[order(fl$data), ]
  resumo <- data.frame(
    dias = nrow(s), dias_com_dado = sum(!is.na(x)),
    pct_falhas = round(100 * mean(is.na(x)), 1), n_alertas = nrow(fl)
  )
  list(serie = data.frame(data = s$data, prcp = x), alertas = fl, resumo = resumo)
}

# -----------------------------------------------------------------------------
#  Índices ETCCDI de precipitação
# -----------------------------------------------------------------------------

# Maior sequência (dias) de uma condição, opcionalmente atravessando anos
.maior_sequencia <- function(cond, ano, cruza_anos = TRUE) {
  anos <- sort(unique(ano))
  res <- setNames(rep(NA_real_, length(anos)), anos)
  if (cruza_anos) {
    # sequências atribuídas ao ano em que terminam (padrão climdex.pcic)
    cc <- ifelse(is.na(cond), FALSE, cond)
    r <- rle(cc)
    fim <- cumsum(r$lengths)
    for (a in anos) {
      k <- which(r$values & ano[fim] == a)
      res[as.character(a)] <- if (length(k)) max(r$lengths[k]) else 0
    }
  } else {
    for (a in anos) {
      cc <- cond[ano == a]
      cc[is.na(cc)] <- FALSE
      r <- rle(cc)
      res[as.character(a)] <- if (any(r$values)) max(r$lengths[r$values]) else 0
    }
  }
  res
}

indices_climdex <- function(datas, prcp, base = c(1981, 2010), limiar_umido = 1, nn = 50,
                            cruza_anos = TRUE, max_faltas_mes = 3, max_faltas_ano = 15) {
  s <- completar_calendario(datas, prcp)
  x <- s$prcp
  ano <- as.integer(format(s$data, "%Y"))
  mes <- as.integer(format(s$data, "%m"))
  anos <- sort(unique(ano))

  # Período-base para os percentis (dias úmidos); se não houver dado, usa a série toda
  na_base <- ano >= base[1] & ano <= base[2]
  umidos_base <- x[na_base & !is.na(x) & x >= limiar_umido]
  base_usada <- base
  if (length(umidos_base) < 100) {
    umidos_base <- x[!is.na(x) & x >= limiar_umido]
    base_usada <- range(ano[!is.na(x)])
    warning(sprintf("Período-base %d-%d sem dados suficientes; usando %d-%d.", base[1], base[2], base_usada[1], base_usada[2]))
  }
  p95 <- unname(stats::quantile(umidos_base, 0.95, type = 8, na.rm = TRUE))
  p99 <- unname(stats::quantile(umidos_base, 0.99, type = 8, na.rm = TRUE))

  faltas_ano <- tapply(is.na(x), ano, sum)
  ano_ok <- faltas_ano <= max_faltas_ano

  por_ano <- function(f) {
    v <- sapply(anos, function(a) {
      xa <- x[ano == a]
      if (all(is.na(xa))) return(NA_real_)
      f(xa)
    })
    v[!ano_ok] <- NA
    v
  }
  umido <- function(v) !is.na(v) & v >= limiar_umido

  x5 <- stats::filter(x, rep(1, 5), sides = 1)  # soma de 5 dias terminando no dia
  rx5 <- sapply(anos, function(a) suppressWarnings(max(x5[ano == a], na.rm = TRUE)))
  rx5[!is.finite(rx5) | !ano_ok] <- NA

  prcptot <- por_ano(function(v) sum(v[umido(v)]))
  r95p <- por_ano(function(v) sum(v[umido(v) & v > p95]))
  r99p <- por_ano(function(v) sum(v[umido(v) & v > p99]))
  cdd <- .maior_sequencia(!is.na(x) & x < limiar_umido, ano, cruza_anos)
  cwd <- .maior_sequencia(!is.na(x) & x >= limiar_umido, ano, cruza_anos)
  cdd[!ano_ok] <- NA
  cwd[!ano_ok] <- NA

  anual <- data.frame(
    ano = anos,
    PRCPTOT = prcptot,
    SDII = por_ano(function(v) if (sum(umido(v))) sum(v[umido(v)]) / sum(umido(v)) else 0),
    R10mm = por_ano(function(v) sum(!is.na(v) & v >= 10)),
    R20mm = por_ano(function(v) sum(!is.na(v) & v >= 20)),
    Rnnmm = por_ano(function(v) sum(!is.na(v) & v >= nn)),
    CDD = unname(cdd),
    CWD = unname(cwd),
    R95p = r95p,
    R99p = r99p,
    R95pTOT = ifelse(prcptot > 0, 100 * r95p / prcptot, NA),
    R99pTOT = ifelse(prcptot > 0, 100 * r99p / prcptot, NA),
    Rx1day = por_ano(function(v) max(v, na.rm = TRUE)),
    Rx5day = rx5,
    dias_faltantes = as.integer(faltas_ano),
    check.names = FALSE
  )
  names(anual)[names(anual) == "Rnnmm"] <- paste0("R", nn, "mm")

  # Mensais: Rx1day, Rx5day e PRCPTOT (mês com >3 faltas = NA)
  chave <- paste(ano, mes)
  um <- unique(data.frame(ano = ano, mes = mes))
  mensal <- do.call(rbind, lapply(seq_len(nrow(um)), function(i) {
    k <- chave == paste(um$ano[i], um$mes[i])
    xm <- x[k]
    ok <- sum(is.na(xm)) <= max_faltas_mes && any(!is.na(xm))
    data.frame(
      ano = um$ano[i], mes = um$mes[i],
      PRCPTOT = if (ok) sum(xm[umido(xm)]) else NA,
      Rx1day = if (ok) max(xm, na.rm = TRUE) else NA,
      Rx5day = if (ok) suppressWarnings(max(x5[k], na.rm = TRUE)) else NA
    )
  }))
  mensal$Rx5day[!is.finite(mensal$Rx5day)] <- NA

  list(
    anual = anual, mensal = mensal,
    limiares = data.frame(p95_mm = p95, p99_mm = p99, base_ini = base_usada[1], base_fim = base_usada[2],
                          limiar_umido = limiar_umido, nn = nn)
  )
}

# Descrição dos índices (como na tabela do RClimDex)
descricao_indices <- function(nn = 50) {
  data.frame(
    indice = c("PRCPTOT", "SDII", "R10mm", "R20mm", paste0("R", nn, "mm"), "CDD", "CWD",
               "R95p", "R99p", "R95pTOT", "R99pTOT", "Rx1day", "Rx5day"),
    nome = c("Precipitação total anual em dias úmidos", "Índice simples de intensidade diária",
             "Dias com chuva >= 10 mm", "Dias com chuva >= 20 mm", sprintf("Dias com chuva >= %d mm", nn),
             "Máximo de dias secos consecutivos", "Máximo de dias úmidos consecutivos",
             "Chuva em dias muito úmidos (> P95)", "Chuva em dias extremamente úmidos (> P99)",
             "Fração da chuva anual em dias > P95", "Fração da chuva anual em dias > P99",
             "Máxima chuva em 1 dia", "Máxima chuva em 5 dias consecutivos"),
    unidade = c("mm", "mm/dia", "dias", "dias", "dias", "dias", "dias", "mm", "mm", "%", "%", "mm", "mm"),
    stringsAsFactors = FALSE
  )
}

# -----------------------------------------------------------------------------
#  Tendências: linear (RClimDex) + Mann-Kendall + Sen
# -----------------------------------------------------------------------------
mann_kendall <- function(x) {
  x <- x[!is.na(x)]
  n <- length(x)
  if (n < 8) return(c(S = NA, tau = NA, p = NA))
  S <- 0
  for (k in 1:(n - 1)) S <- S + sum(sign(x[(k + 1):n] - x[k]))
  emp <- table(x)
  varS <- (n * (n - 1) * (2 * n + 5) - sum(emp * (emp - 1) * (2 * emp + 5))) / 18
  Z <- if (S > 0) (S - 1) / sqrt(varS) else if (S < 0) (S + 1) / sqrt(varS) else 0
  c(S = S, tau = S / (n * (n - 1) / 2), p = 2 * stats::pnorm(-abs(Z)))
}

sen_slope <- function(t, x) {
  ok <- !is.na(x) & !is.na(t)
  t <- t[ok]
  x <- x[ok]
  n <- length(x)
  if (n < 3) return(NA_real_)
  ij <- utils::combn(n, 2)
  stats::median((x[ij[2, ]] - x[ij[1, ]]) / (t[ij[2, ]] - t[ij[1, ]]))
}

tendencia <- function(t, x) {
  ok <- !is.na(x)
  n <- sum(ok)
  if (n < 8) {
    return(data.frame(n = n, ols_por_decada = NA, erro_padrao = NA, p_ols = NA,
                      sen_por_decada = NA, mk_tau = NA, mk_p = NA, sinal = NA))
  }
  fit <- summary(stats::lm(x ~ t))$coefficients
  mk <- mann_kendall(x)
  sen <- sen_slope(t, x)
  data.frame(
    n = n,
    ols_por_decada = 10 * fit[2, 1], erro_padrao = 10 * fit[2, 2], p_ols = fit[2, 4],
    sen_por_decada = 10 * sen, mk_tau = unname(mk["tau"]), mk_p = unname(mk["p"]),
    sinal = ifelse(mk["p"] < 0.05, ifelse(sen > 0, "aumento significativo", "redução significativa"), "sem tendência significativa")
  )
}

# -----------------------------------------------------------------------------
#  Validação satélite x pluviômetro
# -----------------------------------------------------------------------------
validar_satelite <- function(obs, est, limiar = 1) {
  ok <- !is.na(obs) & !is.na(est)
  o <- obs[ok]
  e <- est[ok]
  if (length(o) < 30) return(data.frame(n = length(o)))
  r <- stats::cor(o, e)
  beta <- mean(e) / mean(o)
  gama <- (stats::sd(e) / mean(e)) / (stats::sd(o) / mean(o))
  h <- sum(o >= limiar & e >= limiar)
  f <- sum(o < limiar & e >= limiar)
  m <- sum(o >= limiar & e < limiar)
  data.frame(
    n = length(o), media_obs = mean(o), media_sat = mean(e),
    vies_pct = 100 * (sum(e) - sum(o)) / sum(o), r_pearson = r,
    rmse = sqrt(mean((e - o)^2)), mae = mean(abs(e - o)),
    kge = 1 - sqrt((r - 1)^2 + (beta - 1)^2 + (gama - 1)^2),
    pod = h / (h + m), far = f / (h + f), csi = h / (h + f + m)
  )
}

# -----------------------------------------------------------------------------
#  Série horária (UTC) -> dia pluviométrico (leitura às 7h locais)
# -----------------------------------------------------------------------------
dia_pluviometrico <- function(data_hora_utc, chuva, hora_leitura = 7, fuso = -3,
                              rotulo = c("inicio", "fim"), horas_minimas = 24) {
  rotulo <- match.arg(rotulo)
  local <- as.POSIXct(data_hora_utc, tz = "UTC") + fuso * 3600
  # cada hora é atribuída ao período [7h do dia D, 7h do dia D+1)
  dia <- as.Date(local - hora_leitura * 3600, tz = "UTC")
  if (rotulo == "fim") dia <- dia + 1
  soma <- tapply(chuva, dia, function(v) if (sum(!is.na(v)) >= horas_minimas) sum(v, na.rm = TRUE) else NA)
  data.frame(data = as.Date(names(soma)), prcp = as.numeric(soma))
}

# -----------------------------------------------------------------------------
#  Gráficos (R base, como os PNG do RClimDex)
# -----------------------------------------------------------------------------
grafico_indice <- function(ano, valor, titulo, unidade = "", arquivo = NULL) {
  if (!is.null(arquivo)) grDevices::png(arquivo, width = 900, height = 520, res = 110)
  ok <- !is.na(valor)
  graphics::plot(ano, valor, type = "o", pch = 16, col = "#1F4E78", lwd = 1.5,
                 xlab = "Ano", ylab = unidade, main = titulo, las = 1)
  graphics::grid(col = "grey85")
  if (sum(ok) >= 8) {
    tr <- tendencia(ano, valor)
    fit <- stats::lm(valor ~ ano)
    graphics::lines(ano[ok], stats::fitted(fit), col = "#C00000", lwd = 2, lty = 2)
    graphics::lines(stats::lowess(ano[ok], valor[ok], f = 0.5), col = "grey40", lwd = 1.5)
    graphics::mtext(sprintf("Linear: %+.2f %s/década (p = %.3f) | Sen: %+.2f/década | MK p = %.3f",
                            tr$ols_por_decada, unidade, tr$p_ols, tr$sen_por_decada, tr$mk_p),
                    side = 3, line = 0.2, cex = 0.8)
  }
  if (!is.null(arquivo)) grDevices::dev.off()
  invisible(NULL)
}

# -----------------------------------------------------------------------------
#  Execução em lote (equivalente ao "Indices calculation" do RClimDex)
# -----------------------------------------------------------------------------

# Nome de arquivo seguro, sem perder as letras acentuadas ("São Paulo" -> "Sao_Paulo")
nome_arquivo <- function(x) {
  y <- chartr("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
              "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC", enc2utf8(x))
  gsub("^_|_$", "", gsub("_+", "_", gsub("[^A-Za-z0-9]+", "_", y)))
}

#' series: lista nomeada; cada elemento é um data.frame com colunas data e prcp
rodar_climdexsp <- function(series, pasta_saida = "saidas/climdexsp", base = c(1981, 2010),
                            nn = 50, limiar_umido = 1, graficos = TRUE, qc = TRUE, ...) {
  dir.create(pasta_saida, showWarnings = FALSE, recursive = TRUE)
  if (graficos) dir.create(file.path(pasta_saida, "graficos"), showWarnings = FALSE)
  dir.create(file.path(pasta_saida, "indices_por_serie"), showWarnings = FALSE)
  desc <- descricao_indices(nn)
  todos_ind <- list(); todas_tend <- list(); todos_qc <- list(); todos_lim <- list(); todos_mens <- list()

  for (nome in names(series)) {
    s <- series[[nome]]
    s <- s[!is.na(s$data), ]
    if (sum(!is.na(s$prcp)) < 365) {
      message("  (pulando ", nome, ": menos de 1 ano de dados)")
      next
    }
    message("ClimdexSP: ", nome)
    if (qc) {
      q <- qc_chuva(s$data, s$prcp, ...)
      if (nrow(q$alertas)) todos_qc[[nome]] <- cbind(serie = nome, q$alertas)
      s <- q$serie
    }
    ind <- suppressWarnings(indices_climdex(s$data, s$prcp, base = base, nn = nn, limiar_umido = limiar_umido))
    a <- ind$anual
    todos_ind[[nome]] <- cbind(serie = nome, a)
    todos_mens[[nome]] <- cbind(serie = nome, ind$mensal)
    todos_lim[[nome]] <- cbind(serie = nome, ind$limiares)
    for (k in desc$indice) {
      todas_tend[[paste(nome, k)]] <- cbind(serie = nome, indice = k, tendencia(a$ano, a[[k]]))
      if (graficos) {
        arq <- file.path(pasta_saida, "graficos", paste0(nome_arquivo(nome), "_", k, ".png"))
        grafico_indice(a$ano, a[[k]], paste(nome, "-", k), desc$unidade[desc$indice == k], arq)
      }
    }
    utils::write.csv(a, file.path(pasta_saida, "indices_por_serie", paste0(nome_arquivo(nome), "_indices.csv")), row.names = FALSE)
  }
  res <- list(
    indices = do.call(rbind, todos_ind),
    mensais = do.call(rbind, todos_mens),
    tendencias = do.call(rbind, todas_tend),
    qc = if (length(todos_qc)) do.call(rbind, todos_qc) else data.frame(),
    limiares = do.call(rbind, todos_lim),
    descricao = desc
  )
  rownames(res$tendencias) <- NULL
  salvar_resultados_excel(res, file.path(pasta_saida, "ClimdexSP_resultados.xlsx"))
  invisible(res)
}

salvar_resultados_excel <- function(res, arquivo) {
  wb <- openxlsx::createWorkbook()
  cab <- openxlsx::createStyle(textDecoration = "bold", fgFill = "#1F4E78", fontColour = "white")
  abas <- list(
    "Indices_anuais" = res$indices, "Indices_mensais" = res$mensais, "Tendencias" = res$tendencias,
    "Limiares_P95_P99" = res$limiares, "Controle_qualidade" = res$qc, "Descricao_indices" = res$descricao
  )
  if (exists("produtos_satelite")) abas[["Produtos_satelite"]] <- produtos_satelite
  if (exists("bases_dados")) abas[["Bases_de_dados"]] <- bases_dados
  for (nm in names(abas)) {
    if (is.null(abas[[nm]]) || !nrow(abas[[nm]])) next
    openxlsx::addWorksheet(wb, nm)
    openxlsx::writeData(wb, nm, abas[[nm]], headerStyle = cab)
    openxlsx::freezePane(wb, nm, firstRow = TRUE)
    openxlsx::setColWidths(wb, nm, cols = seq_along(abas[[nm]]), widths = "auto")
  }
  openxlsx::saveWorkbook(wb, arquivo, overwrite = TRUE)
  invisible(arquivo)
}

# -----------------------------------------------------------------------------
#  Atalhos para os dados do chuva_sp
# -----------------------------------------------------------------------------

#' Monta a lista de séries (produto x região) a partir da aba diária
series_satelite_ugrhi <- function(longo, produtos = NULL, regioes = NULL) {
  if (!is.null(produtos)) longo <- longo[longo$produto %in% produtos, ]
  if (!is.null(regioes)) longo <- longo[longo$regiao %in% regioes, ]
  chaves <- unique(longo[c("produto", "regiao")])
  out <- lapply(seq_len(nrow(chaves)), function(i) {
    k <- longo$produto == chaves$produto[i] & longo$regiao == chaves$regiao[i]
    d <- longo[k, c("data", "chuva_mm")]
    names(d) <- c("data", "prcp")
    d[!is.na(d$data), ]
  })
  names(out) <- paste(chaves$produto, chaves$regiao, sep = " | ")
  out
}

#' Comparação satélite x média dos postos por UGRHI (aba diária)
comparar_com_postos <- function(longo, limiar = 1) {
  postos <- longo[longo$produto == "POSTOS (média simples)", ]
  sats <- setdiff(unique(longo$produto), "POSTOS (média simples)")
  res <- list()
  for (p in sats) for (r in unique(postos$regiao)) {
    o <- postos[postos$regiao == r, ]
    e <- longo[longo$produto == p & longo$regiao == r, ]
    m <- merge(o[c("data", "chuva_mm")], e[c("data", "chuva_mm")], by = "data", suffixes = c("_obs", "_sat"))
    v <- validar_satelite(m$chuva_mm_obs, m$chuva_mm_sat, limiar)
    res[[paste(p, r)]] <- cbind(produto = p, regiao = r, v)
  }
  out <- do.call(rbind, lapply(res, function(d) { for (c in setdiff(names(res[[1]]), names(d))) d[[c]] <- NA; d[names(res[[1]])] }))
  rownames(out) <- NULL
  out
}
