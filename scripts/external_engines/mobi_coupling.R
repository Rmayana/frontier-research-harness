suppressPackageStartupMessages(library(ospsuite))
suppressPackageStartupMessages(library(jsonlite))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop("expected MoBi PKML model and coupling request paths")
simulation <- loadSimulation(args[[1]])
request <- fromJSON(args[[2]], simplifyVector = FALSE)
if (length(request$transfers) < 1) stop("at least one transfer is required")

applied <- list()
for (transfer in request$transfers) {
  if (transfer$target_kind == "PARAMETER") {
    target <- getParameter(transfer$target_path, simulation)
    if (is.null(target)) stop(paste("MoBi target parameter not found:", transfer$target_path))
    base_value <- toBaseUnit(quantity = target, values = transfer$target_value, unit = transfer$target_unit)
    setParameterValues(parameters = target, values = base_value)
  } else if (transfer$target_kind == "MOLECULE_INITIAL") {
    target <- getMolecule(transfer$target_path, simulation)
    if (is.null(target)) stop(paste("MoBi target molecule not found:", transfer$target_path))
    base_value <- toBaseUnit(quantity = target, values = transfer$target_value, unit = transfer$target_unit)
    setMoleculeInitialValues(molecules = target, values = base_value)
  } else {
    stop(paste("unsupported MoBi target kind:", transfer$target_kind))
  }
  if (!isTRUE(all.equal(target$value, base_value))) {
    stop(paste("MoBi target value was not applied:", transfer$target_path))
  }
  applied[[length(applied) + 1]] <- list(
    target_kind = transfer$target_kind,
    target_path = transfer$target_path,
    target_value = transfer$target_value,
    target_unit = transfer$target_unit
  )
}

result <- runSimulations(simulations = simulation)[[1]]
outputs <- list()
for (path in request$requested_output_paths) {
  if (!(path %in% result[["allQuantityPaths"]])) stop(paste("MoBi output path not found:", path))
  values <- getOutputValues(result, quantitiesOrPaths = path)
  data <- values[["data"]]
  if (nrow(data) < 1) stop(paste("MoBi output is empty:", path))
  outputs[[length(outputs) + 1]] <- list(
    quantity_path = path,
    time_unit = values[["metaData"]][["Time"]][["unit"]],
    value_unit = values[["metaData"]][[path]][["unit"]],
    times = as.list(data[["Time"]]),
    values = as.list(data[[path]])
  )
}

cat(toJSON(list(
  ospsuite_version = as.character(packageVersion("ospsuite")),
  applied_transfers = applied,
  outputs = outputs
), auto_unbox = TRUE, digits = 17))
