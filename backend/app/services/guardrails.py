import re

from app.config import Settings
from app.models import GuardrailResult


class GuardrailService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def validate_consent(self, consent_confirmed: bool) -> GuardrailResult:
        allowed = bool(consent_confirmed) or not self.settings.require_voice_consent
        return GuardrailResult(
            allowed=allowed,
            consent_verified=bool(consent_confirmed),
            content_safe=True,
            impersonation_risk="low",
            block_reason=None if allowed else "consent_not_confirmed",
        )

    def check_content(self, transcript: str) -> GuardrailResult:
        text = transcript.lower()
        blocked_patterns = [
            "how to make a bomb",
            "kill yourself",
            "shoot up",
            "child sexual",
            "minor sexual",
            "bypass authentication",
            "deepfake",
            "fraud script",
            "illegal drugs",
        ]
        matched = next((pattern for pattern in blocked_patterns if pattern in text), None)
        return GuardrailResult(
            allowed=matched is None,
            consent_verified=True,
            content_safe=matched is None,
            impersonation_risk="low",
            block_reason=f"unsafe_content:{matched}" if matched else None,
        )

    def check_impersonation(self, transcript: str) -> GuardrailResult:
        text = transcript.lower()
        high_risk_patterns = [
            r"\bi am (elon musk|taylor swift|joe biden|narendra modi|donald trump)\b",
            r"\bthis is your bank\b",
            r"\btransfer the money\b",
            r"\bwire the funds\b",
            r"\bverify my identity as\b",
            r"\bfinancial authorization\b",
        ]
        high = any(re.search(pattern, text) for pattern in high_risk_patterns)
        allowed = not (self.settings.block_impersonation and high)
        return GuardrailResult(
            allowed=allowed,
            consent_verified=True,
            content_safe=True,
            impersonation_risk="high" if high else "low",
            block_reason="impersonation_or_fraud_risk" if not allowed else None,
        )

    def check_pii(self, transcript: str) -> GuardrailResult:
        checks = {
            "Possible SSN detected.": r"\b\d{3}-\d{2}-\d{4}\b",
            "Possible credit card number detected.": r"\b(?:\d[ -]*?){13,16}\b",
            "Possible password disclosure detected.": r"\b(password|passcode|pin is|my pin)\b",
            "Possible bank account or routing number detected.": r"\b(routing number|account number)\b",
            "Possible private medical information detected.": r"\b(diagnosed with|medical record|prescription)\b",
            "Possible home address detected.": r"\b\d{2,5}\s+[a-z0-9 .'-]+\s+(street|st|avenue|ave|road|rd|lane|ln|drive|dr)\b",
        }
        warnings = [message for message, pattern in checks.items() if re.search(pattern, transcript, re.I)]
        return GuardrailResult(
            allowed=True,
            consent_verified=True,
            content_safe=True,
            impersonation_risk="low",
            pii_detected=bool(warnings),
            warnings=warnings,
        )

    def combine(
        self,
        consent: GuardrailResult,
        content: GuardrailResult,
        impersonation: GuardrailResult,
        pii: GuardrailResult,
        warnings: list[str],
    ) -> GuardrailResult:
        return GuardrailResult(
            allowed=consent.allowed and content.allowed and impersonation.allowed,
            consent_verified=consent.consent_verified,
            content_safe=content.content_safe,
            impersonation_risk=impersonation.impersonation_risk,
            pii_detected=pii.pii_detected,
            warnings=[*pii.warnings, *warnings],
            block_reason=consent.block_reason or content.block_reason or impersonation.block_reason,
        )
