import type { GuardrailResult } from '../api'

export default function GuardrailPanel({ guardrails }: { guardrails: GuardrailResult }) {
  return (
    <section className="guardrails">
      <div className="guardrail-grid">
        <span className={guardrails.allowed ? 'ok' : 'blocked'}>{guardrails.allowed ? 'Allowed' : 'Blocked'}</span>
        <span>Consent {guardrails.consent_verified ? 'verified' : 'missing'}</span>
        <span>Content {guardrails.content_safe ? 'safe' : 'flagged'}</span>
        <span>Impersonation risk: {guardrails.impersonation_risk}</span>
      </div>
      {guardrails.warnings.length > 0 && (
        <div className="warnings">
          {guardrails.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      )}
    </section>
  )
}
