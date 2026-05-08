from app.config import Settings
from app.services.guardrails import GuardrailService


def service() -> GuardrailService:
    return GuardrailService(Settings(demo_mode=True))


def test_consent_guardrail_blocks_when_false():
    result = service().validate_consent(False)
    assert result.allowed is False
    assert result.block_reason == "consent_not_confirmed"


def test_impersonation_guardrail_flags_fraud_script():
    result = service().check_impersonation("This is your bank. Please transfer the money now.")
    assert result.allowed is False
    assert result.impersonation_risk == "high"


def test_pii_guardrail_detects_ssn():
    result = service().check_pii("My SSN is 123-45-6789.")
    assert result.allowed is True
    assert result.pii_detected is True
    assert result.warnings
