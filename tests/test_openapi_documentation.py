from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_exchange_rate_request_examples_are_present_in_openapi():
    schema = app.openapi()

    batch_operation = schema["paths"]["/exchange-rates/batch"]["post"]
    batch_example = batch_operation["requestBody"]["content"]["application/json"]["example"]

    assert batch_example["base_currency"] == "PHP"
    assert batch_example["rates"][0]["exchange_rate"] == "0.0161164831"
    assert batch_example["rates"][1]["exchange_rate"] == "0.0157973449"


def test_transaction_request_examples_are_present_in_openapi():
    schema = app.openapi()

    buy_examples = schema["paths"]["/transactions/purchases"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]
    cross_sell_examples = schema["paths"]["/transactions/exchanges"]["post"]["requestBody"][
        "content"
    ]["application/json"]["examples"]

    assert buy_examples["foreignAmount"]["value"]["target_currency"] == "USD"
    assert "sourceAmount" in cross_sell_examples
    assert "targetAmount" in cross_sell_examples


def test_delete_rate_batch_rejects_non_iso_base_currency():
    response = client.delete("/exchange-rates/2026-09-06/ZZZ")

    assert response.status_code == 422
    assert response.json()["detail"] == "currency code must be a valid ISO 4217 code"
