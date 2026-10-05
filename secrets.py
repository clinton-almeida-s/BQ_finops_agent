"""Read secrets from Google Secret Manager at runtime."""

import os
import tempfile


def bootstrap_secrets() -> None:
    """
    When running on Cloud Run with --set-secrets, Google mounts secrets
    as files at known paths. This function reads those files and sets
    the appropriate environment variables so the Google client libraries
    can pick them up automatically.
    """
    # GOOGLE_APPLICATION_CREDENTIALS is mounted as a file by Cloud Run
    # when using --set-secrets. The client library reads this env var
    # and loads credentials from the file path it points to.
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if cred_path and os.path.isfile(cred_path):
        # Already set correctly by Cloud Run --set-secrets
        return

    # Fallback: read from Secret Manager if GCP_SECRET_MODE is enabled
    if os.environ.get("GCP_SECRET_MODE") != "true":
        return

    from google.cloud import secretmanager

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        return

    client = secretmanager.SecretManagerServiceClient()

    # SA key
    sa_key_name = f"projects/{project_id}/secrets/finops-sa-key/versions/latest"
    try:
        resp = client.access_secret_version(name=sa_key_name)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(resp.payload.data.decode("utf-8"))
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    except Exception:
        pass  # SA key may not be needed if Workload Identity is used

    # Gemini API key (pass through — already mounted by Cloud Run --set-secrets)
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        try:
            gemini_name = f"projects/{project_id}/secrets/finops-gemini-key/versions/latest"
            resp = client.access_secret_version(name=gemini_name)
            os.environ["GEMINI_API_KEY"] = resp.payload.data.decode("utf-8")
        except Exception:
            pass
