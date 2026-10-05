"""BQ FinOps Agent - Main entry point."""

import argparse
import logging
import sys
from pathlib import Path

from config import Config
from secrets import bootstrap_secrets

bootstrap_secrets()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_analyze(args: argparse.Namespace, config: Config) -> None:
    """Run the analysis pipeline."""
    if args.sample:
        _run_sample_mode(config, args)
        return

    from pipeline import FinOpsAgent

    agent = FinOpsAgent(config)
    result = agent.run()

    print(f"\n{'='*60}")
    print(f"Analysis Complete - {config.project_id}")
    print(f"{'='*60}")
    print(f"Total Recommendations: {result['total_recommendations']}")
    print(f"Estimated Monthly Savings: ${result['total_monthly_savings']:,.2f}")
    print(f"Saved to BigQuery: {result['saved_count']} records")
    print(f"{'='*60}\n")

    if result.get('ai_summary'):
        summary = result['ai_summary']
        print("AI Summary:")
        print(f"  {summary.get('summary', 'N/A')}")
        print("\nPriority Actions:")
        for action in summary.get('priority_actions', []):
            print(f"  {action.get('rank')}. {action.get('action')} - ${action.get('expected_savings_monthly', 0):,.2f}/month")


def _run_sample_mode(config: Config, args: argparse.Namespace) -> None:
    """Run with sample data — no GCP credentials needed."""
    import samples.fake_clients  # noqa: patches google.cloud mocks
    from samples.data import generate_sample_recommendations
    from datetime import datetime

    print(f"\n{'='*60}")
    print("  BQ FinOps Agent — Sample Mode (demo)")
    print(f"{'='*60}")

    recs = generate_sample_recommendations()
    total_monthly = sum(r.get("estimated_savings_monthly", 0) for r in recs)

    print(f"\n[+] Results ({len(recs)} recommendations)\n")

    by_severity = {"high": [], "medium": [], "low": []}
    for r in recs:
        by_severity.setdefault(r["severity"], []).append(r)

    for sev in ["high", "medium", "low"]:
        label = {"high": "[!]", "medium": "[~]", "low": "[i]"}[sev]
        items = by_severity[sev]
        if not items:
            continue
        print(f"  {label} {sev.upper()} ({len(items)})")
        for r in items:
            savings = r.get("estimated_savings_monthly", 0)
            print(f"    - {r['title']}")
            print(f"      {r['description'][:80]}...")
            if savings > 0:
                print(f"      [$] Est. savings: ${savings:,.2f}/month")
            print()

    print(f"{'='*60}")
    print(f"  Total estimated monthly savings: ${total_monthly:,.2f}")
    print(f"  Total estimated yearly savings:  ${total_monthly * 12:,.2f}")
    print(f"{'='*60}\n")
    print("Run with real data: set GOOGLE_CLOUD_PROJECT & GEMINI_API_KEY, then:")
    print("  python main.py --mode analyze")


def cmd_report(args: argparse.Namespace, config: Config) -> None:
    """Generate a report from stored recommendations."""
    if args.sample:
        from report_html import _generate_html
        import samples.fake_clients
        from samples.data import generate_sample_recommendations
        from datetime import datetime
        recs = generate_sample_recommendations()
        out_path = Path(args.output or f"bq_finops_report_demo.html")
        _generate_html(recs, config.project_id or "demo", out_path)
        return

    storage = BQStorage(config.project_id, config.location)
    recs = storage.get_recommendations(limit=args.limit)

    total_monthly = sum(r.estimated_savings_monthly for r in recs)
    total_yearly = sum(r.total_savings_yearly for r in recs)

    print(f"\n{'='*60}")
    print(f"BQ FinOps Report - {config.project_id}")
    print(f"{'='*60}")
    print(f"Total Recommendations: {len(recs)}")
    print(f"Estimated Monthly Savings: ${total_monthly:,.2f}")
    print(f"Estimated Yearly Savings: ${total_yearly:,.2f}")
    print(f"{'='*60}\n")

    for rec in recs[:args.limit]:
        print(f"[{rec.severity.value.upper()}] {rec.title}")
        print(f"  Category: {rec.category.value}")
        print(f"  Savings: ${rec.estimated_savings_monthly:,.2f}/month")
        print(f"  {rec.description[:100]}...\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="BQ FinOps Agent")
    parser.add_argument("--mode", choices=["analyze", "report"], default="analyze")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path, help="Output path for HTML report (used with --mode report)")
    parser.add_argument("--config", type=Path, default=Path(".env"))
    parser.add_argument("--sample", action="store_true", help="Run with sample data (no GCP credentials needed)")

    args = parser.parse_args()

    config = Config.from_env()
    if not args.sample:
        errors = config.validate()
        if errors:
            logger.error("Config errors: %s", errors)
            return 1

    if args.mode == "analyze":
        cmd_analyze(args, config)
    elif args.mode == "report":
        cmd_report(args, config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
