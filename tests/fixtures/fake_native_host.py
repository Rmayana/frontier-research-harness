"""Offline stdio peer for transport tests; never imports Codex or calls a model."""
import json
import sys


def emit(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if method == "initialize": emit({"id": request["id"], "result": {"userAgent": "offline-fixture"}})
    elif method == "initialized": pass
    elif method == "close-now": break
    elif method == "reject": emit({"id": request["id"], "error": {"code": -32602, "message": "invalid fixture input"}})
    elif method == "exercise":
        for _ in range(300): print("diagnostic" * 100, file=sys.stderr, flush=True)
        print("not json", flush=True)
        emit({"id": 9, "method": "item/tool/requestUserInput", "params": {"question": "choose"}})
        emit({"id": request["id"], "result": {"done": True}})
    elif method is None and "result" in request:
        emit({"method": "fixture/response", "params": request})
    else: emit({"id": request["id"], "result": {}})
