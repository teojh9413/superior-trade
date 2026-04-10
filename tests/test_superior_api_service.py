from services.superior_api_service import describe_error_payload, is_error_payload, parse_backtest_record


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


def test_is_error_payload_allows_success_payload_with_message() -> None:
    payload = {
        "id": "01abc",
        "status": "pending",
        "message": "Backtest created. Call PUT /:id/status with action \"start\" to begin.",
    }

    assert is_error_payload(payload) is False


def test_parse_backtest_record_accepts_camel_case_fields() -> None:
    record = parse_backtest_record(
        {
            "id": "01abc",
            "status": "completed",
            "resultUrl": "https://example.com/result.json",
            "createdAt": "2026-04-10T00:00:00Z",
            "updatedAt": "2026-04-10T00:01:00Z",
            "completedAt": "2026-04-10T00:02:00Z",
        }
    )

    assert record.backtest_id == "01abc"
    assert record.result_url == "https://example.com/result.json"
    assert record.created_at == "2026-04-10T00:00:00Z"
    assert record.updated_at == "2026-04-10T00:01:00Z"
    assert record.completed_at == "2026-04-10T00:02:00Z"
