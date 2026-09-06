from typing import Any


def buy_openapi_extra() -> dict[str, Any]:
    """Return the OpenAPI request examples for BUY transactions."""
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "foreignAmount": {
                            "summary": "Buy a specified foreign amount",
                            "value": {
                                "transaction_timestamp": "2026-09-06T10:30:00Z",
                                "target_currency": "USD",
                                "foreign_amount": "100.0000000000",
                            },
                        },
                        "baseAmount": {
                            "summary": "Spend a specified base amount",
                            "value": {
                                "transaction_timestamp": "2026-09-06T10:30:00Z",
                                "target_currency": "USD",
                                "base_amount": "5825.0000000000",
                            },
                        },
                    }
                }
            }
        }
    }


def sell_openapi_extra() -> dict[str, Any]:
    """Return the OpenAPI request examples for SELL transactions."""
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "foreignAmount": {
                            "summary": "Sell a specified foreign amount",
                            "value": {
                                "transaction_timestamp": "2026-09-06T10:30:00Z",
                                "target_currency": "USD",
                                "foreign_amount": "100.0000000000",
                            },
                        },
                        "baseAmount": {
                            "summary": "Receive a specified base amount",
                            "value": {
                                "transaction_timestamp": "2026-09-06T10:30:00Z",
                                "target_currency": "USD",
                                "base_amount": "5910.0000000000",
                            },
                        },
                    }
                }
            }
        }
    }


def cross_sell_openapi_extra() -> dict[str, Any]:
    """Return the OpenAPI request examples for cross-sell transactions."""
    return {
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "sourceAmount": {
                            "summary": "Exchange a source amount",
                            "value": {
                                "transaction_timestamp": "2026-09-06T10:30:00Z",
                                "source_currency": "USD",
                                "target_currency": "JPY",
                                "source_amount": "100.0000000000",
                            },
                        },
                        "targetAmount": {
                            "summary": "Request a target amount",
                            "value": {
                                "transaction_timestamp": "2026-09-06T10:30:00Z",
                                "source_currency": "USD",
                                "target_currency": "JPY",
                                "target_amount": "10000.0000000000",
                            },
                        },
                    }
                }
            }
        }
    }
