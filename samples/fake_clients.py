"""Fake clients for sample mode — no GCP credentials needed."""


class FakeBigQueryClient:
    """Minimal fake BigQuery client for demo mode."""

    def __init__(self, *args, **kwargs):
        pass

    def query(self, sql, **kwargs):
        return FakeJob()

    def get_dataset(self, dataset_id):
        raise Exception("not found")

    def create_dataset(self, dataset):
        pass

    def insert_rows_json(self, table, rows):
        return []

    def connection(self):
        return FakeConnection()


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeJob:
    def result(self):
        return []


class FakeMonitoringClient:
    def __init__(self, *args, **kwargs):
        pass

    def project_path(self, project_id):
        return f"projects/{project_id}"

    def list_time_series(self, request):
        return []


# Monkey-patch imports
import sys
from unittest.mock import MagicMock

_sys_modules = sys.modules

# Patch google.cloud modules
for mod_name in [
    "google.cloud.bigquery",
    "google.cloud.monitoring_v3",
    "google.cloud.storage",
]:
    mock = MagicMock()
    if "bigquery" in mod_name:
        mock.Client.return_value = FakeBigQueryClient()
    elif "monitoring" in mod_name:
        mock.MetricServiceClient.return_value = FakeMonitoringClient()
    _sys_modules[mod_name] = mock

# Also patch submodules
for parent in ["google.cloud"]:
    if parent not in _sys_modules:
        _sys_modules[parent] = MagicMock()
