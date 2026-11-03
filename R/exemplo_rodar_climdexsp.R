# =============================================================================
#  Exemplo: roda o ClimdexSP para todos os produtos e UGRHIs da pasta do Excel
#  (na raiz do repositório)  Rscript R/exemplo_rodar_climdexsp.R
# =============================================================================
source("R/ClimdexSP.R", encoding = "UTF-8")

arquivo <- Sys.glob("saidas/Chuva_SP_*_satelites_e_postos.xlsx")
arquivo <- arquivo[length(arquivo)]
cat("Lendo", arquivo, "\n")

diario <- ler_chuva_excel(arquivo, escala = "diario", tipo = "satelites")
print(table(diario$produto[!is.na(diario$chuva_mm)]))

# 1) Índices ETCCDI para todos os produtos x 22 UGRHIs + Estado (período-base 1981-2010)
series <- series_satelite_ugrhi(diario)
res <- rodar_climdexsp(series, pasta_saida = "saidas/climdexsp", base = c(1981, 2010), nn = 50, graficos = FALSE)

# 2) Gráficos apenas para o Estado de São Paulo (um PNG por índice e produto)
sp <- series_satelite_ugrhi(diario, regioes = "Estado de São Paulo")
invisible(rodar_climdexsp(sp, pasta_saida = "saidas/climdexsp/estado_sp", base = c(1981, 2010), nn = 50, graficos = TRUE))

# 3) Validação: satélite x média dos postos por UGRHI
val <- comparar_com_postos(diario)
write.csv(val, "saidas/climdexsp/validacao_satelite_x_postos_ugrhi.csv", row.names = FALSE)

# 4) Resumo das tendências de PRCPTOT e Rx1day no Estado
tend <- res$tendencias
print(tend[grepl("Estado", tend$serie) & tend$indice %in% c("PRCPTOT", "Rx1day", "CDD", "R95p"),
           c("serie", "indice", "n", "sen_por_decada", "mk_p", "sinal")], row.names = FALSE)

# 5) Exporta a série do CHIRPS no Estado no formato RClimDex (para o RClimDex original)
s <- series[["CHIRPS | Estado de São Paulo"]]
escrever_rclimdex(s$data, s$prcp, "saidas/climdexsp/CHIRPS_Estado_SP_rclimdex.txt")
cat("\nResultados em saidas/climdexsp/\n")
