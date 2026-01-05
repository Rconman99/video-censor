
import json
import uuid
from datetime import datetime

QUEUE_PATH = "/Volumes/20tb/.video_censor_queue.json"

item = {
    "id": str(uuid.uuid4())[:8],
    "input_path": "/Volumes/20tb/Movies/The.Goonies.1985.1080p.AMZN.WEB-DL.DDP5.1.H.264-Kitsune/The.Goonies.1985.1080p.AMZN.WEB-DL.DDP5.1.H.264-Kitsune.mkv",
    "output_path": "/Volumes/20tb/cleanmovies/The.Goonies.1985.1080p.AMZN.WEB-DL.DDP5.1.H.264-Kitsune.CENSORED.mp4",
    "analysis_path": "/Volumes/20tb/cleanmovies/The.Goonies.1985.1080p.AMZN.WEB-DL.DDP5.1.H.264-Kitsune.CENSORED.analysis.json",
    "status": "review_ready",
    "filters": {
      "filter_language": True,
      "filter_sexual_content": True,
      "filter_nudity": True,
      "filter_romance_level": 0,
      "filter_violence_level": 0,
      "filter_mature_themes": False,
      "custom_block_phrases": [],
      "safe_cover_enabled": False
    },
    "profile_name": "Default",
    "progress": 1.0,
    "progress_stage": "Analysis Complete",
    "error_message": "",
    "added_at": datetime.now().isoformat(),
    "started_at": datetime.now().isoformat(),
    "completed_at": datetime.now().isoformat()
}

try:
    with open(QUEUE_PATH, 'r') as f:
        data = json.load(f)
except Exception:
    data = []

data.append(item)

with open(QUEUE_PATH, 'w') as f:
    json.dump(data, f, indent=2)

print(f"Successfully injected Goonies into queue at {QUEUE_PATH}")
