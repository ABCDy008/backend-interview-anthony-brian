from typing import Any


def batch_create_openapi_extra() -> dict[str, Any]:
    """Return the OpenAPI request example for batch rate creation."""
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "rate_date": "2026-09-06",
                        "base_currency": "PHP",
                        "rates": [
                            {
                                "target_currency": "USD",
                                "side": "BUY",
                                "exchange_rate": "0.0161164831",
                            },
                            {
                                "target_currency": "USD",
                                "side": "SELL",
                                "exchange_rate": "0.0157973449",
                            },
                        ],
                    }
                }
            }
        }
    }


def batch_update_openapi_extra() -> dict[str, Any]:
    """Return the OpenAPI request example for batch rate replacement."""
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "rates": [
                            {
                                "target_currency": "USD",
                                "side": "BUY",
                                "exchange_rate": "0.0161164831",
                            },
                            {
                                "target_currency": "USD",
                                "side": "SELL",
                                "exchange_rate": "0.0157973449",
                            },
                        ]
                    }
                }
            }
        }
    }


def value_update_openapi_extra() -> dict[str, Any]:
    """Return the OpenAPI request example for a single rate update."""
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {"exchange_rate": "0.0161164831"}
                }
            }
        }
    }
