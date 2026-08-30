args = argv();
if numel(args) != 2
  error("usage: mitochondria_qsp_smoke.m MODEL_DIR OUTPUT_JSON");
endif
model_dir = args{1};
output_path = args{2};
cd(model_dir);
setup;
load("Varstruc_default.mat");
Varstruc.NADtot_p44 = param(44);
duration_seconds = 0.0001;
atp_hydrolysis_rate = 0.5e-3;
options = odeset("RelTol", 1e-6, "AbsTol", 1e-9);
[time, states] = ode15s(
  @(t, x) Cell_dxdT(t, x, param, atp_hydrolysis_rate, 100, Varstruc),
  [0 duration_seconds], xo_con, options
);
payload = struct(
  "state_count", columns(states),
  "step_count", rows(states),
  "finite", all(isfinite(states(:))),
  "final_time_seconds", time(end),
  "minimum_final_state", min(states(end, :)),
  "maximum_final_state", max(states(end, :)),
  "atp_hydrolysis_rate", atp_hydrolysis_rate
);
file_id = fopen(output_path, "w");
if file_id < 0
  error("cannot open output path");
endif
fprintf(file_id, "%s", jsonencode(payload));
fclose(file_id);
