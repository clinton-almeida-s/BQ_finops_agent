"""Gemini AI agent for BQ FinOps analysis."""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Prompt templates
SUMMARY_PROMPT = """
You are a BigQuery FinOps expert. Analyze the following cost optimization data and provide actionable recommendations.

## Analysis Data
{analysis_data}

## Output Format
Return JSON only with this structure:
{{
  "summary": "2-3 sentence executive summary",
  "priority_actions": [
    {{
      "rank": 1,
      "action": "Specific action to take",
      "expected_savings_monthly": 123.45,
      "effort": "low|medium|high",
      "risk": "low|medium|high"
    }}
  ],
  "insights": ["Key insight 1", "Key insight 2"],
  "next_steps": ["Step 1", "Step 2"]
}}
"""


class GeminiAgent:
    """AI agent using Gemini API for analysis."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialize Gemini client."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    def analyze_recommendations(self, recommendations: list[dict]) -> dict:
        """Get AI-powered analysis of recommendations."""
        client = self._get_client()

        # Summarize recommendations
        total_savings = sum(r.get("estimated_savings_monthly", 0) for r in recommendations)
        high_severity = [r for r in recommendations if r.get("severity") == "high"]

        analysis_data = {
            "total_recommendations": len(recommendations),
            "total_monthly_savings": total_savings,
            "high_severity_count": len(high_severity),
            "categories": list(set(r.get("category") for r in recommendations)),
            "top_recommendations": recommendations[:5],
        }

        prompt = SUMMARY_PROMPT.format(
            analysis_data=json.dumps(analysis_data, indent=2, default=str)
        )

        try:
            response = client.generate_content(prompt)
            text = response.text

            # Extract JSON
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            return json.loads(text)
        except Exception as e:
            logger.error("Gemini analysis failed: %s", e)
            return {"error": str(e)}

    def explain_finding(self, finding: dict) -> str:
        """Get plain English explanation of a finding."""
        client = self._get_client()

        prompt = f"""
        Explain this BigQuery cost finding in simple terms for a business audience:

        Title: {finding.get('title', 'N/A')}
        Description: {finding.get('description', 'N/A')}
        Estimated Savings: ${finding.get('estimated_savings_monthly', 0):,.2f}/month

        Provide a 2-3 sentence explanation of what the issue is and why it matters.
        """

        try:
            response = client.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error("Explanation failed: %s", e)
            return "Explanation unavailable."
