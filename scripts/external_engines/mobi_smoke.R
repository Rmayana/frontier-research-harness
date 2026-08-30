suppressPackageStartupMessages(library(ospsuite))
suppressPackageStartupMessages(library(jsonlite))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("expected one MoBi PKML model path")
simulation <- loadSimulation(args[[1]])
result <- runSimulations(simulations = simulation)[[1]]
paths <- result[["allQuantityPaths"]]
if (length(paths) < 1) stop("MoBi model produced no output paths")
values <- getOutputValues(result, quantitiesOrPaths = paths[[1]])
if (nrow(values[["data"]]) < 1) stop("MoBi model output contains no values")
cat(toJSON(list(
  ospsuite_version = as.character(packageVersion("ospsuite")),
  output_count = length(paths),
  selected_output = paths[[1]],
  value_count = nrow(values[["data"]])
), auto_unbox = TRUE))
