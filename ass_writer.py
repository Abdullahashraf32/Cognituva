import os
import tempfile
import re

def generate_ass_file(srt_text):
  def srt_time_to_ass(srt_time):
    h, m, s_ms = srt_time.split(":")
    s, ms = s_ms.split(",")
    return f"{h}:{m}:{s}.{ms[:2]}"

  def hex_to_ass_color(hex_color):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
      bgr = hex_color[4:6] + hex_color[2:4] + hex_color[0:2]
      return f"&H{bgr.upper()}&"
    return "&HFFFFFF&"

  def apply_tags(text):
    text = re.sub(r"<b>(.*?)</b>", r"{\\b1}\1{\\b0}", text, flags=re.DOTALL)
    text = re.sub(r"<i>(.*?)</i>", r"{\\i1}\1{\\i0}", text, flags=re.DOTALL)
    text = re.sub(r"<u>(.*?)</u>", r"{\\u1}\1{\\u0}", text, flags=re.DOTALL)

    def replace_font_tag(match):
      full_tag = match.group(0)
      content = match.group(1)

      face_match = re.search(r'face="([^"]+)"', full_tag)
      color_match = re.search(r'color="(#[0-9A-Fa-f]{6})"', full_tag)

      ass_code = ""
      if face_match:
        ass_code += f"\\fn{face_match.group(1)}"
      if color_match:
        ass_code += f"\\c{hex_to_ass_color(color_match.group(1))}"

      return f"{{{ass_code}}}{content}{{\\r}}"

    text = re.sub(r"<font[^>]*>(.*?)</font>", replace_font_tag, text, flags=re.DOTALL)

    text = text.replace("[br]", "\\N")

    return text

  dialogue_lines = []
  blocks = re.split(r"\n{2,}", srt_text.strip())
  for block in blocks:
    lines = block.strip().splitlines()
    if len(lines) >= 3:
      times = lines[1]
      start, end = times.split(" --> ")
      text_lines = lines[2:]
      text = "\\N".join(text_lines)
      styled_text = apply_tags(text)
      dialogue_lines.append(
        f"Dialogue: 0,{srt_time_to_ass(start)},{srt_time_to_ass(end)},Default,,0,0,0,,{styled_text}"
      )

  header = """[Script Info]
Title: Temp Subtitle
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

  full_text = header + "\n".join(dialogue_lines)

  temp_path = os.path.join(tempfile.gettempdir(), "temp_subtitle.ass")
  with open(temp_path, "w", encoding="utf-8") as f:
    f.write(full_text)
  return temp_path
