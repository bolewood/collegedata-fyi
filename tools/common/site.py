"""Site name and origins for pipeline tools.

Constants, plus one helper that reads the API origin for runtime calls. Keep
the constants in step with web/src/lib/site.ts.
"""

from typing import Mapping, Optional

SITE_NAME = "Quadfile"
SITE_ORIGIN = "https://www.quadfile.org"
API_ORIGIN = "https://api.quadfile.org"

# Runtime default only; display (docs, examples, generated data) uses API_ORIGIN.
# Runtime calls go to the project origin so a credentialed request never
# depends on a redirect from the custom API host.
PROJECT_ORIGIN = "https://isduwmygvmdozhpvzaix.supabase.co"


def runtime_api_origin(env: Optional[Mapping[str, str]] = None) -> str:
    """API origin for a runtime call: SUPABASE_URL, then NEXT_PUBLIC_SUPABASE_URL,
    then PROJECT_ORIGIN. Never defaults to the custom API host."""
    if env is None:
        import os

        env = os.environ
    for key in ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"):
        value = (env.get(key) or "").strip()
        if value:
            return value.rstrip("/")
    return PROJECT_ORIGIN
