import json
import os

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

def save_settings(settings):
  try:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
      json.dump(settings, f)
  except Exception as e:
    print("Error saving settings:", e)

def load_settings():
  try:
    if os.path.exists(SETTINGS_PATH):
      with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
  except Exception as e:
    print("Error loading settings:", e)
  return {}

def format_srt_time(seconds):
  hours = int(seconds // 3600)
  minutes = int((seconds % 3600) // 60)
  secs = int(seconds % 60)
  milliseconds = int((seconds - int(seconds)) * 1000)
  return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"

def format_segments_to_srt(segments):
  lines = []
  for idx, segment in enumerate(segments, start=1):
    start = format_srt_time(segment.start)
    end = format_srt_time(segment.end)
    text = segment.text.strip()
    lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
  return "\n".join(lines)

