"""Probe readiness without recording URLs, private data or credentials."""
import argparse
import json
import sys
import time
from urllib.request import urlopen

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Same-origin /api/ready endpoint')
    args = parser.parse_args()
    started = time.monotonic()
    try:
        with urlopen(args.url, timeout=5) as response:
            payload = json.load(response)
        ready = payload.get('status') == 'ready'
    except Exception:
        ready = False
    print(json.dumps({'event': 'readiness_probe', 'ready': ready, 'duration_ms': round((time.monotonic()-started)*1000)}))
    sys.exit(0 if ready else 1)
