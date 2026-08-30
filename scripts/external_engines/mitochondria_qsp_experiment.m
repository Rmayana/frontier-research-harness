args = argv();
if numel(args) != 3
  error("usage: mitochondria_qsp_experiment.m MODEL_DIR INPUT_JSON OUTPUT_JSON");
endif
model_dir = args{1};
input_path = args{2};
output_path = args{3};
request = jsondecode(fileread(input_path));
cd(model_dir);

% Load model code and defaults once for the whole experiment. Each condition
% receives fresh copies so overrides cannot leak into later conditions.
setup;
load("Varstruc_default.mat");
base_xo = xo_con;
base_param = param;
conditions = request.conditions;
results = {};

for condition_index = 1:numel(conditions)
  condition = conditions(condition_index);
  try
    xo_con = base_xo;
    param = base_param;
    for index = 1:numel(condition.initial_state_indices)
      xo_con(condition.initial_state_indices(index)) = condition.initial_state_values(index);
    endfor
    for index = 1:numel(condition.parameter_indices)
      param(condition.parameter_indices(index)) = condition.parameter_values(index);
    endfor
    condition_varstruc = Varstruc;
    condition_varstruc.NADtot_p44 = param(44);
    options = odeset("RelTol", 1e-6, "AbsTol", 1e-9);
    [time, states] = ode15s(
      @(t, x) Cell_dxdT(t, x, param, condition.atp_hydrolysis_rate, 100, condition_varstruc),
      [0 condition.duration_seconds], xo_con, options
    );
    selected = states(end, request.requested_state_indices);
    result = struct(
      "condition_id", condition.condition_id,
      "ok", true,
      "step_count", rows(states),
      "state_count", columns(states),
      "finite", all(isfinite(states(:))),
      "final_time_seconds", time(end),
      "requested_state_indices", request.requested_state_indices,
      "requested_final_values", selected
    );
  catch err
    result = struct(
      "condition_id", condition.condition_id,
      "ok", false,
      "error", err.message
    );
  end_try_catch
  results{end + 1} = result;

  % Persist after each condition. A hard timeout can then return an explicit
  % partial result instead of discarding every completed condition.
  checkpoint = struct(
    "complete", false,
    "timed_out", false,
    "completed_condition_count", numel(results),
    "requested_condition_count", numel(conditions),
    "results", {results}
  );
  file_id = fopen(output_path, "w");
  if file_id < 0
    error("cannot open output path");
  endif
  fprintf(file_id, "%s", jsonencode(checkpoint));
  fclose(file_id);
endfor

payload = struct(
  "complete", true,
  "timed_out", false,
  "completed_condition_count", numel(results),
  "requested_condition_count", numel(conditions),
  "results", {results}
);
file_id = fopen(output_path, "w");
if file_id < 0
  error("cannot open output path");
endif
fprintf(file_id, "%s", jsonencode(payload));
fclose(file_id);
