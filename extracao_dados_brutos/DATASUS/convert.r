if (!requireNamespace("read.dbc", quietly = TRUE)) {
  install.packages("read.dbc", repos = "https://cloud.r-project.org")
}

library(read.dbc)

pasta_dados <- "data/raw"

arquivos <- list.files(
  path = pasta_dados,
  pattern = "\\.dbc$",
  full.names = TRUE,
  ignore.case = TRUE
)

if (length(arquivos) == 0) {
  stop("Nenhum arquivo .dbc encontrado na pasta DATASUS.")
}

for (arquivo in arquivos) {
  dados <- read.dbc(arquivo)
  nome_csv <- paste0(tools::file_path_sans_ext(basename(arquivo)), ".csv")
  caminho_csv <- file.path(pasta_dados, nome_csv)

  write.csv(
    dados,
    caminho_csv,
    row.names = FALSE,
    fileEncoding = "UTF-8"
  )

  message("Convertido: ", basename(arquivo), " -> ", nome_csv)
}