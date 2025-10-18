import os
import sys
import json

libs_path = os.path.join(os.path.dirname(__file__), "libs")
if libs_path not in sys.path:
  sys.path.insert(0, libs_path)

import wx

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

def load_settings():
  try:
    if os.path.exists(SETTINGS_PATH):
      with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
  except Exception as e:
    print("Error loading settings:", e)
  return {}

def save_settings(settings):
  try:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
      json.dump(settings, f, indent=2)
  except Exception as e:
    print("Error saving settings:", e)

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

class TranscriptionSettingsDialog(wx.Dialog):
  def __init__(self, parent):
    super().__init__(parent, title="Transcription Settings", size=(420, 430))
    self.SetBackgroundColour("#f3f6fa")

    self.settings = load_settings()

    font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    self.SetFont(font)

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    def labeled_spin(label_text, setting_key, min_val, max_val, inc=1):
      row_sizer = wx.BoxSizer(wx.HORIZONTAL)
      label = wx.StaticText(self, label=label_text)
      label.SetMinSize((180, -1))
      spin = wx.SpinCtrlDouble(self, min=min_val, max=max_val, inc=inc)
      spin.SetValue(float(self.settings.get(setting_key, 1)))
      self.spin_controls[setting_key] = spin
      row_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
      row_sizer.Add(spin, 1)
      return row_sizer

    self.spin_controls = {}

    main_sizer.Add(wx.StaticText(self, label="Jump Forward/Backward Settings (in seconds):"),
                   0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

    main_sizer.Add(labeled_spin("Shift + Arrows (← →):", "shift_jump", 0.1, 30, 0.1), 0, wx.EXPAND | wx.ALL, 6)
    main_sizer.Add(labeled_spin("Ctrl + Arrows (← →):", "ctrl_jump", 0.1, 60, 0.1), 0, wx.EXPAND | wx.ALL, 6)
    main_sizer.Add(labeled_spin("Alt + Arrows (← →):", "alt_jump", 0.1, 30, 0.1), 0, wx.EXPAND | wx.ALL, 6)
    main_sizer.Add(labeled_spin("Ctrl+Shift + Arrows (← →):", "ctrl_shift_jump", 0.1, 60, 0.1), 0, wx.EXPAND | wx.ALL, 6)

    main_sizer.Add(wx.StaticText(self, label="\nVideo Preview Size:"), 0, wx.LEFT | wx.RIGHT, 12)
    size_sizer = wx.BoxSizer(wx.HORIZONTAL)
    self.video_width = wx.SpinCtrl(self, min=100, max=3000)
    self.video_width.SetValue(int(self.settings.get("video_width", 800)))
    self.video_height = wx.SpinCtrl(self, min=100, max=3000)
    self.video_height.SetValue(int(self.settings.get("video_height", 450)))
    size_sizer.Add(wx.StaticText(self, label="Width:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
    size_sizer.Add(self.video_width, 1, wx.RIGHT, 10)
    size_sizer.Add(wx.StaticText(self, label="Height:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
    size_sizer.Add(self.video_height, 1)
    main_sizer.Add(size_sizer, 0, wx.EXPAND | wx.ALL, 6)

    step_sizer = wx.BoxSizer(wx.HORIZONTAL)
    self.resize_step = wx.SpinCtrl(self, min=5, max=400)
    self.resize_step.SetValue(int(self.settings.get("resize_step", 40)))
    step_sizer.Add(wx.StaticText(self, label="Resize step (px):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
    step_sizer.Add(self.resize_step, 1)
    main_sizer.Add(step_sizer, 0, wx.EXPAND | wx.ALL, 6)

    nudge_row = wx.BoxSizer(wx.HORIZONTAL)
    nudge_label = wx.StaticText(self, label="Selection nudge (ms):")
    nudge_label.SetMinSize((180, -1))
    self.selection_nudge_ms = wx.SpinCtrl(self, min=1, max=20000)
    self.selection_nudge_ms.SetValue(int(self.settings.get("selection_nudge_ms", 200)))
    nudge_row.Add(nudge_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
    nudge_row.Add(self.selection_nudge_ms, 1)
    main_sizer.Add(nudge_row, 0, wx.EXPAND | wx.ALL, 6)

    self.pause_on_set_selection_end_checkbox = wx.CheckBox(self, label="Pause playback after setting selection end")
    self.pause_on_set_selection_end_checkbox.SetValue(self.settings.get("pause_on_set_selection_end", False))
    main_sizer.Add(self.pause_on_set_selection_end_checkbox, 0, wx.ALL, 10)

    self.replay_after_nudge_checkbox = wx.CheckBox(self, label="Replay selected part after nudge")
    self.replay_after_nudge_checkbox.SetValue(self.settings.get("replay_after_nudge", False))
    main_sizer.Add(self.replay_after_nudge_checkbox, 0, wx.ALL, 10)

    self.readonly_checkbox = wx.CheckBox(self, label="Enable Readonly Mode on Start")
    self.readonly_checkbox.SetValue(self.settings.get("readonly", True))
    main_sizer.Add(self.readonly_checkbox, 0, wx.ALL, 10)

    self.beep_checkbox = wx.CheckBox(self, label="Play beep sound during transcription")
    self.beep_checkbox.SetValue(self.settings.get("beep", False))
    main_sizer.Add(self.beep_checkbox, 0, wx.ALL, 10)

    action_sizer = wx.BoxSizer(wx.HORIZONTAL)
    action_label = wx.StaticText(self, label="After Transcription:")
    self.action_choice = wx.Choice(self, choices=[
      "Do nothing",
      "Show message",
      "Focus output",
      "Show tooltip"
    ])
    current_action = self.settings.get("after_action", "Show message")
    self.action_choice.SetSelection(self.action_choice.FindString(current_action))
    action_sizer.Add(action_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
    action_sizer.Add(self.action_choice, 1)
    main_sizer.Add(action_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

    btn_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
    if btn_sizer:
      main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

    self.SetSizer(main_sizer)
    self.Layout()

    first_spin = self.spin_controls.get("shift_jump")
    if first_spin:
      wx.CallAfter(first_spin.SetFocus)

    ok_button = self.FindWindowById(wx.ID_OK)
    if ok_button:
      ok_button.Bind(wx.EVT_BUTTON, self.on_save)

  def on_save(self, event):
    for spin in self.spin_controls.values():
      spin.Navigate()

    wx.CallAfter(self._save_and_close)

  def _save_and_close(self):
    self.settings["shift_jump"] = self.spin_controls["shift_jump"].GetValue()
    self.settings["ctrl_jump"] = self.spin_controls["ctrl_jump"].GetValue()
    self.settings["alt_jump"] = self.spin_controls["alt_jump"].GetValue()
    self.settings["ctrl_shift_jump"] = self.spin_controls["ctrl_shift_jump"].GetValue()

    self.settings["video_width"] = self.video_width.GetValue()
    self.settings["video_height"] = self.video_height.GetValue()
    self.settings["resize_step"] = self.resize_step.GetValue()
    self.settings["selection_nudge_ms"] = int(self.selection_nudge_ms.GetValue())
    self.settings["readonly"] = self.readonly_checkbox.GetValue()
    self.settings["beep"] = self.beep_checkbox.GetValue()
    self.settings["pause_on_set_selection_end"] = self.pause_on_set_selection_end_checkbox.GetValue()
    self.settings["replay_after_nudge"] = self.replay_after_nudge_checkbox.GetValue()
    self.settings["after_action"] = self.action_choice.GetStringSelection()

    save_settings(self.settings)
    self.EndModal(wx.ID_OK)

  def get_settings(self):
    return self.settings
