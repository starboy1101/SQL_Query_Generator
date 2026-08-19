from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_and_schema(client: TestClient) -> None:
    assert client.get("/health/live").status_code == 200
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    schema = client.get("/api/v1/schema")
    assert schema.status_code == 200
    assert {table["name"] for table in schema.json()["tables"]} == {"customers", "orders"}
    capabilities = client.get("/api/v1/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["execution_enabled"] is True
    assert capabilities.json()["max_rows_cap"] == 50


def test_readiness_fails_when_an_allowlisted_table_is_missing(settings: Settings) -> None:
    invalid = settings.model_copy(update={"allowed_tables": ("customers", "missing_table")})
    with TestClient(create_app(invalid)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["schema"] is False


def test_generate_and_execute_count(client: TestClient) -> None:
    response = client.post(
        "/api/v1/queries/generate",
        json={"question": "How many customers are there?", "execute": True},
        headers={"X-Request-ID": "test-request"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "test-request"
    assert body["execution"]["rows"] == [{"count": 2}]
    assert body["validation"]["tables"] == ["customers"]
    assert "LIMIT 25" in body["sql"]


def test_execute_rejects_mutation(client: TestClient) -> None:
    response = client.post("/api/v1/queries/execute", json={"sql": "DELETE FROM customers"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsafe_query"


def test_execute_safe_query_and_clamp_limit(client: TestClient) -> None:
    response = client.post(
        "/api/v1/queries/execute",
        json={"sql": "SELECT name FROM customers ORDER BY id LIMIT 999", "max_rows": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution"]["rows"] == [{"name": "Asha"}]
    assert "LIMIT 1" in body["sql"]


def test_execution_policy_is_enforced(settings: Settings) -> None:
    disabled = settings.model_copy(update={"allow_query_execution": False})
    with TestClient(create_app(disabled)) as client:
        response = client.post(
            "/api/v1/queries/generate",
            json={"question": "List customers", "execute": True},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "query_execution_disabled"


def test_direct_execution_has_an_independent_policy(settings: Settings) -> None:
    protected = settings.model_copy(update={"allow_direct_sql_execution": False})
    with TestClient(create_app(protected)) as client:
        response = client.post("/api/v1/queries/execute", json={"sql": "SELECT * FROM customers"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "direct_query_execution_disabled"


def test_generation_rate_limit(settings: Settings) -> None:
    limited = settings.model_copy(update={"rate_limit_requests_per_minute": 1})
    with TestClient(create_app(limited)) as client:
        first = client.post("/api/v1/queries/generate", json={"question": "List customers"})
        second = client.post("/api/v1/queries/generate", json={"question": "Count customers"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert second.json()["error"]["code"] == "rate_limit_exceeded"


def test_authenticated_cors_preflight_allows_api_key(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.options(
            "/api/v1/schema",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
    assert response.status_code == 200
    assert "x-api-key" in response.headers["access-control-allow-headers"].lower()


def test_request_validation_uses_stable_error_shape(client: TestClient) -> None:
    response = client.post("/api/v1/queries/generate", json={"question": "?"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_api_key_authentication(settings: Settings) -> None:
    protected = settings.model_copy(update={"api_key": "secret-key"})
    with TestClient(create_app(protected)) as client:
        denied = client.get("/api/v1/schema")
        allowed = client.get("/api/v1/schema", headers={"X-API-Key": "secret-key"})
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "authentication_required"
    assert allowed.status_code == 200


def test_model_output_is_repaired_once(client: TestClient) -> None:
    class RepairingBackend:
        responses = iter(["DELETE FROM customers", "SELECT id FROM customers"])

        @property
        def model_id(self) -> str:
            return "repair-test"

        def warmup(self) -> None:
            return None

        def generate(self, _generation_input: object) -> str:
            return next(self.responses)

    service = client.app.state.query_service
    service._settings = service._settings.model_copy(update={"max_repair_attempts": 1})
    service._llm = RepairingBackend()
    response = client.post("/api/v1/queries/generate", json={"question": "List customer IDs"})
    assert response.status_code == 200
    assert response.json()["model"] == "repair-test"
    assert "SELECT" in response.json()["sql"]
