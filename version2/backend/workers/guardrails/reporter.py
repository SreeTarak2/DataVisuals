"""Guardrail Reporter - Generates human-readable reports for guardrail violations"""

from typing import List, Dict, Any
from datetime import datetime
from workers.guardrails.models import GuardrailResult, GuardrailViolation


class GuardrailReporter:
    """Generates clear, actionable reports for data quality issues"""

    def __init__(self):
        pass

    def generate_summary(self, result: GuardrailResult) -> str:
        """Generate a concise summary of validation results"""
        if result.passed:
            return (
                f"✅ Data Quality Check PASSED\n\n"
                f"Dataset '{result.dataset_id}' passed all {result.total_rules_checked} quality checks.\n"
                f"No critical issues found. Data is safe for AI analysis."
            )

        summary_lines = [
            "⚠️ Data Quality Check FAILED",
            "",
            f"Dataset: {result.dataset_id}",
            f"Timestamp: {result.validation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"📊 Summary:",
            f"  • Rules Checked: {result.total_rules_checked}",
            f"  • Total Violations: {result.total_violations}",
            f"  • Critical Issues: {result.critical_violations}",
            f"  • Warnings: {result.warning_violations}",
            "",
            f"🚫 Status: {result.status.upper()}",
            f"   Reason: {result.quarantine_reason or 'N/A'}",
            "",
            "📋 Detailed Violations:",
        ]

        critical_violations = [
            v for v in result.violations if self._is_critical(v.rule_id, result)
        ]
        warning_violations = [
            v for v in result.violations if not self._is_critical(v.rule_id, result)
        ]

        violation_num = 1

        if critical_violations:
            summary_lines.append("\n🔴 CRITICAL ISSUES (Must Fix):")
            for violation in critical_violations:
                summary_lines.extend(self._format_violation(violation, violation_num))
                violation_num += 1

        if warning_violations:
            summary_lines.append("\n🟡 WARNINGS (Should Review):")
            for violation in warning_violations:
                summary_lines.extend(self._format_violation(violation, violation_num))
                violation_num += 1

        summary_lines.extend(
            [
                "",
                "💡 Recommended Actions:",
                "  1. Review the violating rows using the row indices provided",
                "  2. Clean or correct the data issues",
                "  3. Re-upload the corrected dataset",
                "  4. Contact support if you believe this is an error",
            ]
        )

        return "\n".join(summary_lines)

    def _is_critical(self, rule_id: str, result: GuardrailResult) -> bool:
        """Determine if a violation is critical"""
        return result.critical_violations > 0

    def _format_violation(self, violation: GuardrailViolation, num: int) -> List[str]:
        """Format a single violation for the report"""
        lines = [
            f"\n  [{num}] Column: '{violation.column_name}'",
            f"      Issue: {violation.message}",
            f"      Affected Rows: {violation.violation_count} total",
        ]

        if violation.row_indices:
            row_samples = violation.row_indices[:5]
            lines.append(f"      Sample Row Indices: {row_samples}")

        if violation.sample_values and violation.sample_values[0] is not None:
            sample_strs = [str(v)[:50] for v in violation.sample_values[:3]]
            lines.append(f"      Sample Values: {sample_strs}")

        return lines

    def generate_email_report(
        self, result: GuardrailResult, user_email: str
    ) -> Dict[str, Any]:
        """Generate email-ready report content"""
        status_emoji = "✅" if result.passed else "⚠️"
        status_text = "PASSED" if result.passed else "FAILED"

        subject = f"{status_emoji} Data Quality Check {status_text} for Dataset {result.dataset_id}"

        if result.passed:
            body = f"""
            <html>
            <body>
                <h2>{status_emoji} Great News! Data Quality Check PASSED</h2>
                <p>Your dataset <strong>{result.dataset_id}</strong> has successfully passed all quality checks.</p>
                <p><strong>Summary:</strong></p>
                <ul>
                    <li>Rules Checked: {result.total_rules_checked}</li>
                    <li>Violations Found: 0</li>
                </ul>
                <p>Your data is now being processed and will be available for AI analysis shortly.</p>
            </body>
            </html>
            """
        else:
            body = f"""
            <html>
            <body>
                <h2>{status_emoji} Action Required: Data Quality Check FAILED</h2>
                <p>Your dataset <strong>{result.dataset_id}</strong> has failed quality checks and has been quarantined.</p>

                <p><strong>Issue Summary:</strong></p>
                <ul>
                    <li>Critical Issues: {result.critical_violations}</li>
                    <li>Warnings: {result.warning_violations}</li>
                    <li>Total Violations: {result.total_violations}</li>
                </ul>

                <p><strong>Reason:</strong> {result.quarantine_reason or "N/A"}</p>

                <p><strong>Next Steps:</strong></p>
                <ol>
                    <li>Log in to your dashboard to view detailed violation reports</li>
                    <li>Download the sample of violating rows</li>
                    <li>Clean your data and re-upload</li>
                </ol>

                <p>Need help? <a href="mailto:support@datasage.ai">Contact Support</a></p>
            </body>
            </html>
            """

        return {"to": user_email, "subject": subject, "body": body, "is_html": True}

    def generate_api_response(self, result: GuardrailResult) -> Dict[str, Any]:
        """Generate API response format for guardrail results"""
        return {
            "dataset_id": result.dataset_id,
            "status": result.status,
            "passed": result.passed,
            "validation_timestamp": result.validation_timestamp.isoformat(),
            "summary": {
                "total_rules": result.total_rules_checked,
                "total_violations": result.total_violations,
                "critical_violations": result.critical_violations,
                "warning_violations": result.warning_violations,
            },
            "quarantine_reason": result.quarantine_reason,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "column": v.column_name,
                    "message": v.message,
                    "violation_count": v.violation_count,
                    "sample_rows": v.row_indices[:5],
                    "sample_values": [str(val)[:100] for val in v.sample_values[:3]]
                    if v.sample_values
                    else [],
                }
                for v in result.violations
            ],
            "human_readable_summary": self.generate_summary(result),
        }


__all__ = ["GuardrailReporter"]
