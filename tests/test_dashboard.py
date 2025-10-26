from __future__ import annotations

import threading
import time
from http.server import ThreadingHTTPServer

import requests

from agentforge_cli import constants
from agentforge_cli.config import load_config
from agentforge_cli.dashboard import run_dashboard
from agentforge_cli.queue import TaskStore


def test_dashboard_serves_html(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTFORGE_HOME", str(tmp_path))
    constants.refresh_paths()
    store = TaskStore(constants.TASK_DB)
    store.add_task("dashboard task")
    store.close()

    server = run_dashboard(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        time.sleep(0.1)
        response = requests.get(f"http://{host}:{port}/", timeout=5)
        assert response.status_code == 200
        assert "Queue Status" in response.text

        response = requests.get(
            f"http://{host}:{port}/model?target=anthropic:{constants.DEFAULT_MODELS[0]}",
            allow_redirects=False,
            timeout=5,
        )
        assert response.status_code in {302, 303}
        config = load_config()
        assert config["models"]["primary"]["name"] == constants.DEFAULT_MODELS[0]
    finally:
        server.shutdown()
        thread.join(timeout=2)
