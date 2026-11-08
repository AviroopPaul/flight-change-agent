"""Credentials for Gemini on Vertex AI.

Local runs use Application Default Credentials (`gcloud auth application-default login`).
LiveKit Cloud is not on GCP, so it has no metadata server for ADC. There the agent reads a
service-account key (Vertex AI User role only) from the GOOGLE_CREDENTIALS_JSON secret.
"""

import json
import os

from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def vertex_credentials() -> service_account.Credentials | None:
    """The key from GOOGLE_CREDENTIALS_JSON, or None to let the SDK use ADC."""
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        return None
    return service_account.Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
