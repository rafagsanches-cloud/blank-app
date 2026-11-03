# =============================================================================
#  ClimdexSP - interface gráfica (Shiny), no espírito do RClimDex
#
#  Como abrir (na pasta raiz do repositório):
#     shiny::runApp("R/app_climdexsp.R")
#  ou no RStudio: abra este arquivo e clique em "Run App".
# =============================================================================

suppressPackageStartupMessages({
  library(shiny)
  library(DT)
})
source(file.path(if (file.exists("R/ClimdexSP.R")) "R" else ".", "ClimdexSP.R"), encoding = "UTF-8")

# Mesma cor por produto usada no aplicativo Streamlit (paleta categórica validada)
CORES_PRODUTOS <- c(CHIRPS = "#2a78d6", IMERG = "#eb6834", PERSIANN = "#1baf7a", CMORPH = "#eda100",
                    GPCP = "#e87ba4", POSTOS = "#008300")

achar_excel <- function() {
  cand <- Sys.glob(c("saidas/Chuva_SP_*_satelites_e_postos.xlsx", "../saidas/Chuva_SP_*_satelites_e_postos.xlsx"))
  if (length(cand)) cand[length(cand)] else ""
}

ui <- fluidPage(
  tags$head(tags$style(HTML("h2{color:#1F4E78} .well{background:#f4f7fb}"))),
  titlePanel("ClimdexSP – índices de extremos de chuva para São Paulo (satélites e postos)"),
  sidebarLayout(
    sidebarPanel(
      width = 3,
      h4("1. Dados"),
      textInput("arquivo", "Pasta do Excel (chuva_sp)", value = achar_excel()),
      fileInput("upload", "…ou envie um arquivo (.xlsx do chuva_sp ou .txt RClimDex)",
                accept = c(".xlsx", ".txt", ".csv")),
      radioButtons("tipo", "Tipo de série",
                   c("Satélite/postos por UGRHI" = "ugrhi", "Posto pluviométrico" = "posto", "Arquivo RClimDex" = "rclimdex")),
      conditionalPanel("input.tipo == 'ugrhi'",
                       selectInput("produto", "Produto", choices = NULL),
                       selectInput("regiao", "UGRHI / Estado", choices = NULL)),
      conditionalPanel("input.tipo == 'posto'", selectizeInput("posto", "Posto", choices = NULL)),
      h4("2. Parâmetros (RClimDex)"),
      fluidRow(column(6, numericInput("base_ini", "Base: início", 1981, 1950, 2030)),
               column(6, numericInput("base_fim", "Base: fim", 2010, 1950, 2030))),
      fluidRow(column(6, numericInput("nn", "Rnn (mm)", 50, 1, 500)),
               column(6, numericInput("limiar", "Dia úmido (mm)", 1, 0.1, 10, step = 0.1))),
      numericInput("limite_max", "QC: limite diário (mm)", 400, 50, 2000),
      checkboxInput("cruza", "CDD/CWD podem atravessar anos", TRUE),
      actionButton("calcular", "Calcular índices", class = "btn-primary", width = "100%"),
      br(), br(),
      downloadButton("baixar_xlsx", "Resultados (.xlsx)"),
      downloadButton("baixar_txt", "Série RClimDex (.txt)")
    ),
    mainPanel(
      width = 9,
      tabsetPanel(
        tabPanel("Série", plotOutput("g_serie", height = 300), plotOutput("g_anual", height = 280), tableOutput("t_resumo")),
        tabPanel("Controle de qualidade", tableOutput("t_qc_resumo"), DTOutput("t_qc")),
        tabPanel("Índices",
                 selectInput("indice", "Índice", choices = NULL, width = "300px"),
                 plotOutput("g_indice", height = 380), DTOutput("t_indices")),
        tabPanel("Tendências", DTOutput("t_tend")),
        tabPanel("Comparar produtos",
                 helpText("Mesmo índice, mesma UGRHI, todos os produtos (inclui a média dos postos)."),
                 selectInput("indice_cmp", "Índice", choices = NULL, width = "300px"),
                 plotOutput("g_cmp", height = 420), DTOutput("t_cmp")),
        tabPanel("Validação (sat x postos)",
                 helpText("Comparação diária entre cada satélite e a média simples dos postos da mesma UGRHI."),
                 DTOutput("t_val")),
        tabPanel("Produtos e bases",
                 h4("Produtos de satélite"), tableOutput("t_prod"),
                 h4("Versões usadas"), tableOutput("t_usados"),
                 h4("Bases de dados"), tableOutput("t_bases"))
      )
    )
  )
)

server <- function(input, output, session) {
  # Excel do chuva_sp: o enviado (se for .xlsx) ou o caminho digitado
  caminho <- reactive({
    up <- input$upload
    if (!is.null(up) && grepl("\\.xlsx$", up$name, ignore.case = TRUE)) up$datapath else input$arquivo
  })

  dados_ugrhi <- reactive({
    req(input$tipo != "rclimdex", nzchar(caminho()), file.exists(caminho()))
    withProgress(message = "Lendo planilha diária…", ler_chuva_excel(caminho(), "diario", "satelites"))
  })
  dados_postos <- reactive({
    req(input$tipo == "posto", file.exists(caminho()))
    withProgress(message = "Lendo postos…", list(diario = ler_chuva_excel(caminho(), "diario", "postos"),
                                                 inv = ler_inventario_postos(caminho())))
  })

  observeEvent(dados_ugrhi(), {
    d <- dados_ugrhi()
    updateSelectInput(session, "produto", choices = unique(d$produto))
    updateSelectInput(session, "regiao", choices = unique(d$regiao), selected = "Estado de São Paulo")
  })
  observeEvent(dados_postos(), {
    inv <- dados_postos()$inv
    rot <- setNames(inv$id, paste0(inv$id, " – ", inv$nome, " (", inv$rede, ", ", inv$ugrhi, ")"))
    updateSelectizeInput(session, "posto", choices = rot, server = TRUE)
  })

  serie <- reactive({
    if (input$tipo == "rclimdex") {
      req(input$upload)
      return(ler_rclimdex(input$upload$datapath))
    }
    if (input$tipo == "posto") {
      req(input$posto)
      d <- dados_postos()$diario
      return(data.frame(data = d$data, prcp = d[[input$posto]]))
    }
    req(input$produto, input$regiao)
    d <- dados_ugrhi()
    k <- d$produto == input$produto & d$regiao == input$regiao
    data.frame(data = d$data[k], prcp = d$chuva_mm[k])
  })
  nome_serie <- reactive({
    switch(input$tipo, ugrhi = paste(input$produto, "|", input$regiao), posto = input$posto, rclimdex = input$upload$name)
  })

  resultado <- eventReactive(input$calcular, {
    s <- serie()
    s <- s[!is.na(s$data), ]
    validate(need(sum(!is.na(s$prcp)) >= 365, "A série tem menos de um ano de dados."))
    q <- qc_chuva(s$data, s$prcp, limite_max = input$limite_max)
    ind <- suppressWarnings(indices_climdex(q$serie$data, q$serie$prcp, base = c(input$base_ini, input$base_fim),
                                            nn = input$nn, limiar_umido = input$limiar, cruza_anos = input$cruza))
    desc <- descricao_indices(input$nn)
    tend <- do.call(rbind, lapply(desc$indice, function(k) cbind(indice = k, tendencia(ind$anual$ano, ind$anual[[k]]))))
    list(qc = q, ind = ind, desc = desc, tend = tend, nome = nome_serie())
  })

  observeEvent(resultado(), {
    ch <- resultado()$desc$indice
    updateSelectInput(session, "indice", choices = ch, selected = "PRCPTOT")
    updateSelectInput(session, "indice_cmp", choices = ch, selected = "PRCPTOT")
  })

  output$g_serie <- renderPlot({
    s <- serie()
    plot(s$data, s$prcp, type = "h", col = "#2E75B6", xlab = "", ylab = "mm/dia", main = nome_serie(), las = 1)
  })
  output$g_anual <- renderPlot({
    s <- serie()
    a <- tapply(s$prcp, format(s$data, "%Y"), function(v) if (mean(is.na(v)) <= 15 / 365) sum(v, na.rm = TRUE) else NA)
    barplot(a, col = "#1F4E78", border = NA, las = 2, ylab = "mm/ano", main = "Total anual (anos com ≤15 dias de falha)")
  })
  output$t_resumo <- renderTable({
    s <- serie()
    data.frame(inicio = format(min(s$data)), fim = format(max(s$data)), dias = nrow(s),
               falhas_pct = round(100 * mean(is.na(s$prcp)), 1), media_anual_mm = round(365.25 * mean(s$prcp, na.rm = TRUE)))
  })

  output$t_qc_resumo <- renderTable(resultado()$qc$resumo)
  output$t_qc <- renderDT(datatable(resultado()$qc$alertas, options = list(pageLength = 15), rownames = FALSE))

  output$t_indices <- renderDT(datatable(round(resultado()$ind$anual, 2), options = list(pageLength = 15, scrollX = TRUE), rownames = FALSE))
  output$g_indice <- renderPlot({
    r <- resultado()
    req(input$indice %in% names(r$ind$anual))
    grafico_indice(r$ind$anual$ano, r$ind$anual[[input$indice]], paste(r$nome, "–", input$indice),
                   r$desc$unidade[r$desc$indice == input$indice])
  })
  output$t_tend <- renderDT({
    t <- merge(resultado()$desc, resultado()$tend, by = "indice", sort = FALSE)
    num <- vapply(t, is.numeric, TRUE)
    t[num] <- lapply(t[num], round, 4)
    datatable(t, options = list(pageLength = 20, scrollX = TRUE), rownames = FALSE)
  })

  comparacao <- reactive({
    req(input$tipo == "ugrhi", input$indice_cmp)
    d <- dados_ugrhi()
    d <- d[d$regiao == input$regiao, ]
    out <- lapply(unique(d$produto), function(p) {
      k <- d$produto == p
      ind <- suppressWarnings(indices_climdex(d$data[k], d$chuva_mm[k], base = c(input$base_ini, input$base_fim),
                                              nn = input$nn, limiar_umido = input$limiar))$anual
      data.frame(produto = p, ano = ind$ano, valor = ind[[input$indice_cmp]])
    })
    do.call(rbind, out)
  })
  output$g_cmp <- renderPlot({
    c <- comparacao()
    prods <- unique(c$produto)
    cores <- CORES_PRODUTOS[sub(" .*", "", prods)]
    cores[is.na(cores)] <- "#52514e"
    op <- par(mar = c(7, 4.5, 3, 1))
    on.exit(par(op))
    plot(range(c$ano), range(c$valor, na.rm = TRUE), type = "n", xlab = "", ylab = input$indice_cmp,
         main = paste(input$indice_cmp, "–", input$regiao), las = 1)
    grid(col = "grey85")
    for (i in seq_along(prods)) with(c[c$produto == prods[i], ], lines(ano, valor, col = cores[i], lwd = ifelse(grepl("POSTOS", prods[i]), 3, 2)))
    legend("bottom", inset = c(0, -0.32), xpd = TRUE, horiz = TRUE, legend = prods, col = cores, lwd = 2.5, bty = "n", cex = 0.9)
  })
  output$t_cmp <- renderDT({
    c <- comparacao()
    t <- do.call(rbind, lapply(split(c, c$produto), function(x) cbind(produto = x$produto[1], tendencia(x$ano, x$valor))))
    num <- vapply(t, is.numeric, TRUE)
    t[num] <- lapply(t[num], round, 4)
    datatable(t, rownames = FALSE, options = list(dom = "t"))
  })

  output$t_val <- renderDT({
    d <- dados_ugrhi()
    v <- comparar_com_postos(d)
    num <- vapply(v, is.numeric, TRUE)
    v[num] <- lapply(v[num], round, 3)
    datatable(v, options = list(pageLength = 25, scrollX = TRUE), rownames = FALSE, filter = "top")
  })

  output$t_prod <- renderTable(produtos_satelite)
  output$t_usados <- renderTable(produtos_usados)
  output$t_bases <- renderTable(bases_dados)

  output$baixar_xlsx <- downloadHandler(
    filename = function() paste0("ClimdexSP_", nome_arquivo(resultado()$nome), ".xlsx"),
    content = function(f) {
      r <- resultado()
      salvar_resultados_excel(list(indices = cbind(serie = r$nome, r$ind$anual), mensais = cbind(serie = r$nome, r$ind$mensal),
                                   tendencias = cbind(serie = r$nome, r$tend), limiares = cbind(serie = r$nome, r$ind$limiares),
                                   qc = r$qc$alertas, descricao = r$desc), f)
    }
  )
  output$baixar_txt <- downloadHandler(
    filename = function() paste0(nome_arquivo(nome_serie()), "_rclimdex.txt"),
    content = function(f) { s <- serie(); escrever_rclimdex(s$data, s$prcp, f) }
  )
}

shinyApp(ui, server)
