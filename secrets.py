"""Read secrets from Google Secret Manager at runtime."""

import os
import tempfile

logger = __import__('logging').getLogger(__name__)


def bootstrap_secrets() -> None:
    """
    Bootstrap secrets for production deployment on Cloud Run.

    Supports two authentication modes:

    1. SA Key Mode (GCP_SECRET_MODE=true):
       Reads SA key and Gemini key from Secret Manager.
       Writes SA key to temp file, sets GOOGLE_APPLICATION_CREDENTIALS.

    2. Workload Identity Mode (WORKLOAD_IDENTITY=true, default for Cloud Run):
       Skips SA key entirely — Cloud Run service account authenticates automatically.
       Only reads Gemini API key from Secret Manager if not already set.
    """
    # If credentials already mounted by Cloud Run --set-secrets, skip
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if cred_path and os.path.isfile(cred_path):
        return

    # Workload Identity mode: no SA key needed, skip GCP auth bootstrap
    if os.environ.get("WORKLOAD_IDENTITY") == "true":
        _fetch_gemini_key()
        return

    # SA Key mode: read from Secret Manager
    if os.environ.get("GCP_SECRET_MODE") != "true":
        return

    from google.cloud import secretmanager

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        logger.warning("No GOOGLE_CLOUD_PROJECT set, skipping secret bootstrap")
        return

    client = secretmanager.SecretManagerServiceClient()

    # SA key — write to temp file for GOOGLE_APPLICATION_CREDENTIALS
    sa_key_name = f"projects/{project_id}/secrets/finops-sa-key/versions/latest"
    try:
        resp = client.access_secret_version(name=sa_key_name)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(resp.payload.data.decode("utf-8"))
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
        logger.info("SA key loaded from Secret Manager")
    except Exception as e:
        logger.warning("SA key not found in Secret Manager: %s", e)

    # Gemini API key
    _fetch_gemini_key_from_client(client, project_id)


def _fetch_gemini_key() -> None:
    """Fetch Gemini API key from Secret Manager (Workload Identity mode)."""
    if os.environ.get("GEMINI_API_KEY"):
        return

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        logger.warning("No GOOGLE_CLOUD_PROJECT set, cannot fetch Gemini key")
        return

    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    _fetch_gemini_key_from_client(client, project_id)


def _fetch_gemini_key_from_client(client, project_id: str) -> None:
    """Common logic to fetch Gemini key from Secret Manager."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        return
    try:
        gemini_name = f"projects/{project_id}/secrets/finops-gemini-key/versions/latest"
        resp = client.access_secret_version(name=gemini_name)
        os.environ["GEMINI_API_KEY"] = resp.payload.data.decode("utf-8")
        logger.info("Gemini API key loaded from Secret Manager")
    except Exception as e:
        logger.warning("Gemini key not found in Secret Manager: %s", e)
