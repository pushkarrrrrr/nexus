import json

from starlette.testclient import TestClient

from services.api.nexus_api.main import app


def test_websocket_connection_and_echo():
    client = TestClient(app)
    with client.websocket_connect("/ws/nexus?client_surface=dashboard&session_id=test_sess") as ws:
        # 1. Receive welcome event
        welcome = ws.receive_json()
        assert welcome["event_type"] == "dag.updated"
        assert welcome["session_id"] == "test_sess"
        assert welcome["payload"]["status"] == "connected"

        # 2. Send valid client event
        client_event = {
            "event_type": "request.submit",
            "session_id": "test_sess",
            "payload": {"prompt": "test goal"},
        }
        ws.send_text(json.dumps(client_event))

        # 3. Receive acknowledgement
        ack = ws.receive_json()
        assert ack["event_type"] == "audit.recorded"
        assert ack["session_id"] == "test_sess"
        assert ack["payload"]["received_event"] == "request.submit"
        assert ack["payload"]["status"] == "acknowledged"


def test_websocket_invalid_json():
    client = TestClient(app)
    with client.websocket_connect("/ws/nexus?client_surface=ambient&session_id=err_sess") as ws:
        welcome = ws.receive_json()
        assert welcome["payload"]["status"] == "connected"

        # Send invalid JSON
        ws.send_text("this-is-not-json{{{")
        err = ws.receive_json()
        assert err["event_type"] == "error"
        assert "Invalid JSON" in err["payload"]["error"]
