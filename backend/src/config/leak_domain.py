import json
from pathlib import Path
LEAK_DOMAIN = json.loads(
    (Path(__file__).parents[1] / 'constants' / 'leak.json').read_text()
)
