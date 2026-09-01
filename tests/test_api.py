def rate_payload(side="BUY"):
    return {
        "rate_date": "2026-02-02",
        "base_currency": "PHP",
        "quote_currency": "USD",
        "side": side,
        "rate": "55.00000000",
    }


def usd_rate_payload(rate="62.487000"):
    return {
        "currency_code": "PHP",
        "currency_name": "Philippine Peso",
        "rate_per_usd": rate,
    }


def test_rate_lookup_and_transaction_snapshot(client):
    assert client.post("/rates", json=usd_rate_payload()).status_code == 201
    response = client.post(
        "/transactions",
        json={
            "transaction_timestamp": "2026-02-02T10:15:00+08:00",
            "base_currency": "PHP",
            "quote_currency": "USD",
            "side": "BUY",
            "foreign_amount": "100.00",
        },
    )
    assert response.status_code == 409


def test_missing_rate_returns_conflict(client):
    response = client.post(
        "/transactions",
        json={
            "transaction_timestamp": "2026-02-02T10:15:00+08:00",
            "base_currency": "PHP",
            "quote_currency": "USD",
            "side": "SELL",
            "base_amount": "5500.00",
        },
    )
    assert response.status_code == 409


def test_rate_can_be_read_updated_and_deleted(client):
    created = client.post("/rates", json=usd_rate_payload()).json()
    rate_id = created["id"]
    assert client.get(f"/rates/{rate_id}").status_code == 200

    updated = client.put(
        f"/rates/{rate_id}", json=usd_rate_payload("63.000000")
    )
    assert updated.status_code == 200
    assert updated.json()["rate_per_usd"] == "63.000000"
    assert client.delete(f"/rates/{rate_id}").status_code == 204
    assert client.get(f"/rates/{rate_id}").status_code == 404


def test_amounts_are_mutually_exclusive(client):
    response = client.post(
        "/transactions",
        json={
            "transaction_timestamp": "2026-02-02T10:15:00+08:00",
            "base_currency": "PHP",
            "quote_currency": "USD",
            "side": "BUY",
            "foreign_amount": "100.00",
            "base_amount": "5500.00",
        },
    )
    assert response.status_code == 422
