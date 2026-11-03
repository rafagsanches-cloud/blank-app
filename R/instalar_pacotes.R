# Pacotes usados pelo ClimdexSP e pela conversão das UGRHIs
pacotes <- c("sf", "readxl", "openxlsx", "shiny", "DT")
faltam <- setdiff(pacotes, rownames(installed.packages()))
if (length(faltam)) install.packages(faltam)
# opcional, para conferir os índices com a implementação de referência:
# install.packages("climdex.pcic")
