from services.superior_api_service import describe_error_payload


def test_describe_error_payload_includes_error_message_and_details() -> None:
    payload = {
        "error": "validation_error",
        "message": "Invalid backtest config",
        "details": {"config": "'exit_pricing' is a required property"},
    }

    message = describe_error_payload(payload)

    assert "validation_error" in message
    assert "Invalid backtest config" in message
    assert "exit_pricing" in message
