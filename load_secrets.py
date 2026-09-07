"""Load ALL keys from the app's AWS Secrets Manager secret into the environment.

The CI hub maps a known set of keys (AZURE_*, ENTRA_*, SDC_SNOWFLAKE_*, etc.) as
individual env vars in the App Runner task definition. Custom keys added via the
secrets broker's --extra flag (e.g. ADMIN_UPNS) are stored in the same secret but
not mapped — they silently vanish at runtime.

This script runs before gunicorn and fills the gap: it reads the entire secret and
prints shell export statements for every key that is not already set, so custom
keys are available without depending on the CI hub's key list. Existing env vars
are never overwritten.

Fails gracefully: if credentials, permissions, or the secret are unavailable, the
app starts normally with whatever the CI hub already injected.
"""
import json
import os
import re
import sys

SECRET_NAME = os.getenv("AWS_SECRET_NAME", "docker-apps/startup-evaluation-agent-hydra")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-west-2")

_SAFE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def main():
    try:
        import boto3
        client = boto3.client("secretsmanager", region_name=REGION)
        resp = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(resp["SecretString"])
    except Exception as exc:
        print(f"# load_secrets: {exc}", file=sys.stderr)
        return

    added = 0
    for key, value in secret.items():
        if not _SAFE_KEY.match(key):
            continue
        if key in os.environ:
            continue
        safe_value = str(value).replace("'", "'\"'\"'")
        print(f"export {key}='{safe_value}'")
        added += 1

    if added:
        print(f"# load_secrets: exported {added} key(s) from {SECRET_NAME}", file=sys.stderr)


if __name__ == "__main__":
    main()
