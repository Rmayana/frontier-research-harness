"""Seed historical database fixtures without reintroducing a production runner."""
import json
from uuid import uuid4
from frontier_research_harness.scientific_contracts import canonical_sha256


def seed_experiment(workspace, name="pulse", model_input=None, *, question="Historical fixture",
                    provenance=None, raw_output=None, status="SUCCEEDED", interpretation=None):
    identifier = str(uuid4())
    value = model_input or {}
    output = raw_output if raw_output is not None else {"value": 1}
    workspace.connection.execute(
        "INSERT INTO frontier_science_experiments(experiment_id,created_at,question,model_name,model_version,"
        "input_hash,input_json,output_json,interpretation,provenance_json,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (identifier, "2026-01-01T00:00:00Z", question, name, "historical-test-v1", canonical_sha256(value),
         json.dumps(value), json.dumps(output), interpretation, json.dumps(provenance or [{"kind":"fixture"}]), status))
    workspace.connection.commit()
    return {"experiment_id":identifier, "status":status, "raw_output":output}


def seed_calculation(workspace, target_id, inputs, *, units):
    identifier = str(uuid4())
    workspace.connection.execute(
        "INSERT INTO frontier_science_calculations VALUES(?,?,?,?,?,?,?,?)",
        (identifier, "2026-01-01T00:00:00Z", target_id, "historical", "1", canonical_sha256(inputs),
         json.dumps({"inputs":inputs,"units":units}), json.dumps({"status":"CALCULATED"})))
    workspace.connection.commit()
    return {"calculation_id":identifier}
