import wx
import os
import sys
import shutil
import threading
import time
import winsound
import re
from settings_utils import format_srt_time, format_segments_to_srt

libs_path = os.path.join(os.path.dirname(__file__), "libs")
sys.path.insert(0, libs_path)
if libs_path not in sys.path:
  sys.path.insert(0, libs_path)
cytolk_path = os.path.join(libs_path, "cytolk")
if cytolk_path not in sys.path:
  sys.path.insert(0, cytolk_path)

from faster_whisper import WhisperModel
from googletrans import Translator
import vlc
import comtypes.client
import tolk
from segment_list import SegmentListPanel
from dialogs import FilterDialog

MODEL_WARNINGS = {
  "medium": True,
  "large-v2": True
}

LANGUAGES = {
  "Arabic": "ar",
  "English": "en",
  "French": "fr",
  "German": "de",
  "Spanish": "es",
  "Italian": "it",
  "Russian": "ru",
  "Turkish": "tr",
  "Japanese": "ja",
  "Korean": "ko",
  "Chinese": "zh"
}

def get_model_cache_path(model):
  base = os.path.expanduser("~/.cache/huggingface")
  path_with_hub = os.path.join(base, "hub", f"models--Systran--faster-whisper-{model}")
  path_without_hub = os.path.join(base, f"models--Systran--faster-whisper-{model}")

  if os.path.isdir(path_with_hub):
    return path_with_hub
  elif os.path.isdir(path_without_hub):
    return path_without_hub
  else:
    return path_with_hub

def get_expected_model_size(model):
  return {
    "tiny": 75 * 1024 * 1024,
    "base": 142 * 1024 * 1024,
    "small": 466 * 1024 * 1024,
    "medium": int(1.5 * 1024 * 1024 * 1024),
    "large-v2": int(2.9 * 1024 * 1024 * 1024),
  }.get(model, 500 * 1024 * 1024)

class VLCPlayer:
  def __init__(self, panel):
    plugin_path = os.path.join(os.path.dirname(__file__), "libs", "plugins")
    os.environ["VLC_PLUGIN_PATH"] = plugin_path
    os.environ["VLC_VERBOSE"] = "-1"
    os.environ["LIBVA_DRIVER_NAME"] = " "
    args = [
  "--no-video-title-show",
  "--avcodec-hw=none",
  "--codec", "avcodec",
  "--vout", "win32",
  "--file-caching=500",
  "--no-xlib"
]
    self.instance = vlc.Instance(args)
    self.player = self.instance.media_player_new()
    self.panel = panel
    self.is_paused = False
    self.media = None
    self.panel.Bind(wx.EVT_SIZE, self.on_resize)

  def set_media(self, path):
    self.media = self.instance.media_new(path)
    self.player.set_media(self.media)
    handle = self.panel.GetHandle()
    self.player.set_hwnd(handle)
    time.sleep(0.1)

  def play(self):
    if self.panel:
      handle = self.panel.GetHandle()
      self.player.set_hwnd(handle)
    self.player.play()
    time.sleep(0.1)
    width, height = self.panel.GetSize()
    self.player.video_set_scale(0)
    self.player.video_set_aspect_ratio(f"{width}:{height}")

  def stop(self):
    self.player.stop()

  def pause(self):
    self.player.pause()
    self.is_paused = not self.is_paused

  def set_volume(self, volume):
    self.player.audio_set_volume(volume)

  def get_volume(self):
    return self.player.audio_get_volume()

  def set_rate(self, rate):
    self.player.set_rate(rate)

  def get_rate(self):
    return self.player.get_rate()

  def set_position(self, pos):
    self.player.set_position(pos)

  def get_position(self):
    return self.player.get_position()

  def seek_relative(self, seconds):
    if self.player:
      current_pos = self.player.get_time()
      new_pos = max(current_pos + int(seconds * 1000), 0)
      self.player.set_time(new_pos)

  def on_resize(self, event):
    if self.player and self.panel:
      handle = self.panel.GetHandle()
      self.player.set_hwnd(handle)

      width, height = self.panel.GetSize()
    
      self.player.video_set_scale(0)
      self.player.video_set_aspect_ratio(f"{width}:{height}")
    event.Skip()

class TranscriptionPanel(wx.Panel):
  def __init__(self, parent, on_back, announce_enabled=False):
    super().__init__(parent)
    self.on_back = on_back
    self.is_transcribing = False
    self.transcription_thread = None
    self.stop_event = threading.Event()
    self.last_saved_text = ""
    self.saved_path = None
    tolk.try_sapi(True)
    tolk.load()
    self.announce_enabled = announce_enabled

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    self.task_radio = wx.RadioBox(
      self, label="Choose Tas&k", choices=["Transcription", "Translation"],
      majorDimension=1, style=wx.RA_SPECIFY_ROWS
    )
    self.task_radio.Bind(wx.EVT_RADIOBOX, self.update_language_ui_visibility)
    main_sizer.Add(self.task_radio, 0, wx.ALL, 10)

    lang_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Language Settings")

    self.auto_detect_chk = wx.CheckBox(self, label="Auto-&detect source language")
    self.auto_detect_chk.SetValue(True)
    self.auto_detect_chk.Bind(wx.EVT_CHECKBOX, self.on_auto_detect_toggle)
    lang_box.Add(self.auto_detect_chk, 0, wx.ALL, 10)

    self.source_language_row = wx.BoxSizer(wx.HORIZONTAL)
    self.source_language_label = wx.StaticText(self, label="Choos&e Transcription Language:")
    self.source_language_row.Add(self.source_language_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
    self.source_language_combo = wx.ComboBox(self, choices=list(LANGUAGES.keys()), style=wx.CB_READONLY)
    self.source_language_combo.SetValue("English")
    self.source_language_combo.Disable()
    self.source_language_row.Add(self.source_language_combo, 1)
    lang_box.Add(self.source_language_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    self.target_language_row = wx.BoxSizer(wx.HORIZONTAL)
    self.target_language_label = wx.StaticText(self, label="Tar&get Language:")
    self.target_language_row.Add(self.target_language_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
    self.target_language_combo = wx.ComboBox(self, choices=list(LANGUAGES.keys()), style=wx.CB_READONLY)
    self.target_language_combo.SetValue("English")
    self.target_language_row.Add(self.target_language_combo, 1)
    lang_box.Add(self.target_language_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    main_sizer.Add(lang_box, 0, wx.ALL | wx.EXPAND, 10)

    video_controls = self.build_video_controls()
    main_sizer.Add(video_controls, 0, wx.EXPAND | wx.ALL, 10)

    self.setup_shortcuts()

    self.update_language_ui_visibility()

    model_row = wx.BoxSizer(wx.HORIZONTAL)
    model_label = wx.StaticText(self, label="Choose &Model:")
    model_row.Add(model_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
    self.model_combo = wx.ComboBox(self, choices=["tiny", "base", "small", "medium", "large-v2"], style=wx.CB_READONLY)
    self.model_combo.SetValue("small")
    self.model_combo.Bind(wx.EVT_COMBOBOX, self.on_model_changed)
    model_row.Add(self.model_combo, 1, wx.RIGHT, 5)

    self.download_btn = wx.Button(self, label=" Down&load")
    self.download_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    self.download_btn.SetBackgroundColour(wx.Colour(255, 128, 0))
    self.download_btn.SetForegroundColour(wx.Colour(255, 255, 255))
    self.download_btn.Bind(wx.EVT_BUTTON, self.handle_model_button)
    self.add_hover_effect(self.download_btn, wx.Colour(255, 128, 0))
    model_row.Add(self.download_btn, 0)
    main_sizer.Add(model_row, 0, wx.ALL | wx.EXPAND, 10)

    self.open_video_btn = wx.Button(self, label="&Open Video")
    self.open_video_btn.Bind(wx.EVT_BUTTON, self.on_open_video)
    main_sizer.Add(self.open_video_btn, 0, wx.ALL, 10)

    self.start_btn = wx.Button(self, label=" S&tart")
    self.start_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    self.start_btn.SetBackgroundColour(wx.Colour(102, 0, 204))
    self.start_btn.SetForegroundColour(wx.Colour(255, 255, 255))
    self.start_btn.Bind(wx.EVT_BUTTON, lambda evt: self.transcribe_video())
    self.add_hover_effect(self.start_btn, wx.Colour(102, 0, 204))
    main_sizer.Add(self.start_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)

    self.readonly_chk = wx.CheckBox(self, label="&Readonly")
    self.readonly_chk.SetValue(True)
    self.readonly_chk.Disable()
    self.readonly_chk.Bind(wx.EVT_CHECKBOX, self.toggle_readonly)
    main_sizer.Add(self.readonly_chk, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    self.filter_btn = wx.Button(self, label="&Filter By")
    self.filter_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_FIND, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    self.filter_btn.Bind(wx.EVT_BUTTON, self.on_open_filter_dialog)
    self.add_hover_effect(self.filter_btn, wx.Colour(0, 153, 255))
    main_sizer.Add(self.filter_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    output_box_sizer = wx.StaticBoxSizer(wx.VERTICAL, self, "Transcript Output")

    self.output_box = wx.TextCtrl(self, style=wx.TE_MULTILINE)
    self.output_box.SetEditable(False)

    self.segment_list_panel = SegmentListPanel(
  self,
  self.output_box,
  announce_callback=self.announce
)

    output_box_sizer.Add(self.segment_list_panel, 1, wx.ALL | wx.EXPAND, 5)
    output_box_sizer.Add(self.output_box, 1, wx.ALL | wx.EXPAND, 5)

    main_sizer.Add(output_box_sizer, 1, wx.ALL | wx.EXPAND, 10)

    self.output_box.Bind(wx.EVT_TEXT, self.on_output_box_updated)

    button_row = wx.BoxSizer(wx.HORIZONTAL)

    save_btn = wx.Button(self, label=" S&ave As")
    save_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    save_btn.SetBackgroundColour(wx.Colour(0, 102, 204))
    save_btn.SetForegroundColour(wx.Colour(255, 255, 255))
    save_btn.Bind(wx.EVT_BUTTON, self.save_result)
    self.add_hover_effect(save_btn, wx.Colour(0, 102, 204))
    button_row.Add(save_btn, 0, wx.RIGHT, 5)

    save_direct_btn = wx.Button(self, label=" &Save")
    save_direct_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_TICK_MARK, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    save_direct_btn.SetBackgroundColour(wx.Colour(0, 153, 76))
    save_direct_btn.SetForegroundColour(wx.Colour(255, 255, 255))
    save_direct_btn.Bind(wx.EVT_BUTTON, self.save_or_update_file)
    self.add_hover_effect(save_direct_btn, wx.Colour(0, 153, 76))
    button_row.Add(save_direct_btn, 0, wx.RIGHT, 5)

    back_btn = wx.Button(self, label=" &Back")
    back_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_GO_BACK, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    back_btn.SetBackgroundColour(wx.Colour(204, 0, 0))
    back_btn.SetForegroundColour(wx.Colour(255, 255, 255))
    back_btn.Bind(wx.EVT_BUTTON, self.confirm_exit)
    self.add_hover_effect(back_btn, wx.Colour(204, 0, 0))
    button_row.Add(back_btn, 0)

    main_sizer.Add(button_row, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    self.SetSizer(main_sizer)
    self.update_model_button_state()

    self.timer = wx.Timer(self)
    self.Bind(wx.EVT_TIMER, self.update_seek_slider, self.timer)

  def add_hover_effect(self, button, base_color):
    hover_color = wx.Colour(
      min(base_color.Red() + 30, 255),
      min(base_color.Green() + 30, 255),
      min(base_color.Blue() + 30, 255)
    )

    def on_enter(event):
      button.SetBackgroundColour(hover_color)
      button.Refresh()
      event.Skip()

    def on_leave(event):
      button.SetBackgroundColour(base_color)
      button.Refresh()
      event.Skip()

    button.Bind(wx.EVT_ENTER_WINDOW, on_enter)
    button.Bind(wx.EVT_LEAVE_WINDOW, on_leave)

  def setup_shortcuts(self):
    shortcut_actions = [
    {"key": (wx.ACCEL_CTRL, ord("P")), "handler": self.on_toggle_play},
    {"key": (wx.ACCEL_CTRL, wx.WXK_SPACE), "handler": self.on_pause_resume},
    {"key": (wx.ACCEL_SHIFT, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-1)},
    {"key": (wx.ACCEL_SHIFT, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(1)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-5)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(5)},
    {"key": (wx.ACCEL_ALT, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-10)},
    {"key": (wx.ACCEL_ALT, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(10)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-15)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(15)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_UP), "handler": lambda evt: self.adjust_volume(5)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_DOWN), "handler": lambda evt: self.adjust_volume(-5)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_UP), "handler": lambda evt: self.adjust_speed(0.1)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_DOWN), "handler": lambda evt: self.adjust_speed(-0.1)},
    {"key": (wx.ACCEL_CTRL, ord("R")), "handler": lambda evt: self.toggle_readonly(None)},
    {"key": (wx.ACCEL_CTRL, ord("O")), "handler": self.on_open_video},
    {"key": (wx.ACCEL_CTRL, ord("S")), "handler": lambda evt: self.save_or_update_file(None)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("S")), "handler": lambda evt: self.save_result(None)},
    {"key": (wx.ACCEL_CTRL, ord("T")), "handler": lambda evt: self.transcribe_video()},
    {"key": (wx.ACCEL_CTRL, wx.WXK_F4), "handler": lambda evt: self.confirm_exit(None)},
    {"key": (wx.ACCEL_CTRL, ord("D")), "handler": self.on_open_filter_dialog},
    ]

    accel_entries = []
    for action in shortcut_actions:
      accel_id = wx.NewIdRef()
      accel_entries.append(wx.AcceleratorEntry(*action["key"], accel_id))
      self.Bind(wx.EVT_MENU, action["handler"], id=accel_id.GetId())

    self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

  def toggle_readonly(self, event):
    current = self.readonly_chk.GetValue()
    self.readonly_chk.SetValue(not current)
    self.output_box.SetEditable(not self.readonly_chk.GetValue())
    if self.announce_enabled:
      msg = "Readonly On" if self.readonly_chk.GetValue() else "Readonly Off"
      self.announce(msg)

  def confirm_exit(self, event):
    self.cleanup()
    self.handle_unsaved_changes(self.on_back)

  def confirm_close(self, event):
    self.cleanup()
    def proceed():
      self.GetTopLevelParent().Destroy()
    self.handle_unsaved_changes(proceed)

  def handle_unsaved_changes(self, proceed_callback):
    if self.readonly_chk.IsChecked():
      proceed_callback()
      return

    current_text = self.output_box.GetValue()
    if current_text != self.last_saved_text:
      dlg = wx.MessageDialog(self, "Do you want to save your changes before exiting?", "Unsaved Changes", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
      result = dlg.ShowModal()
      dlg.Destroy()

      if result == wx.ID_YES:
        self.save_result(None)
        proceed_callback()
      elif result == wx.ID_NO:
        proceed_callback()
      else:
        return
    else:
      proceed_callback()

  def build_video_controls(self):
    video_sizer = wx.BoxSizer(wx.VERTICAL)

    self.video_panel = wx.Panel(self)
    self.video_panel.SetMinSize((800, 450))
    self.video_panel.SetBackgroundColour(wx.BLACK)
    video_sizer.Add(self.video_panel, 1, wx.EXPAND | wx.ALL, 10)

    self.vlc_player = VLCPlayer(self.video_panel)
    self.video_panel.Bind(wx.EVT_SIZE, self.vlc_player.on_resize)

    control_sizer = wx.BoxSizer(wx.HORIZONTAL)

    self.toggle_btn = wx.Button(self, label="&Play")
    self.toggle_btn.Bind(wx.EVT_BUTTON, self.on_toggle_play)
    control_sizer.Add(self.toggle_btn, 0, wx.RIGHT, 5)

    self.pause_btn = wx.Button(self, label="Pa&use/Resume")
    self.pause_btn.Bind(wx.EVT_BUTTON, self.on_pause_resume)
    control_sizer.Add(self.pause_btn, 0, wx.RIGHT, 5)

    self.seek_slider = wx.Slider(self, minValue=0, maxValue=1000, value=0)
    self.seek_slider.Bind(wx.EVT_SLIDER, self.on_seek)
    control_sizer.Add(wx.StaticText(self, label="Seek"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
    control_sizer.Add(self.seek_slider, 1)

    self.speed_slider = wx.Slider(self, minValue=5, maxValue=20, value=10)
    self.speed_slider.Bind(wx.EVT_SLIDER, self.on_speed_change)
    control_sizer.Add(wx.StaticText(self, label="Speed"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
    control_sizer.Add(self.speed_slider, 1)

    self.volume_slider = wx.Slider(self, minValue=0, maxValue=100, value=100)
    self.volume_slider.Bind(wx.EVT_SLIDER, self.on_volume_change)
    control_sizer.Add(wx.StaticText(self, label="Volume"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
    control_sizer.Add(self.volume_slider, 1, wx.EXPAND)

    video_sizer.Add(control_sizer, 0, wx.EXPAND | wx.ALL, 10)

    return video_sizer

  def announce(self, message):
    if self.announce_enabled and message:
      tolk.output(message, interrupt=True)

  def cleanup(self):
    if hasattr(self, "cleaned") and self.cleaned:
      return
    self.cleaned = True
    self.vlc_player.stop()
    tolk.unload()
    self.timer.Stop()

  def on_toggle_play(self, event):
    path = getattr(self, "file_path", None)
    if not path:
      wx.MessageBox("Please select a video file.", "Error")
      return

    state = self.vlc_player.player.get_state()
    if state in [vlc.State.NothingSpecial, vlc.State.Stopped, vlc.State.Ended]:
      self.vlc_player.set_media(path)
      self.vlc_player.play()
      wx.CallLater(100, self.finalize_play_setup)
    else:
      self.vlc_player.stop()
      self.toggle_btn.SetLabel("Play")
      self.timer.Stop()
      self.seek_slider.SetValue(0)
      if self.announce_enabled:
        self.announce("Stop")

  def finalize_play_setup(self):
    self.vlc_player.set_rate(self.speed_slider.GetValue() / 10)
    self.vlc_player.set_volume(self.volume_slider.GetValue())
    self.toggle_btn.SetLabel("Stop")
    self.timer.Start(500)
    if self.announce_enabled:
      self.announce("Play")

  def on_pause_resume(self, event):
    self.vlc_player.pause()
    if self.announce_enabled:
      self.announce("Pause" if self.vlc_player.is_paused else "Resume")

  def on_open_video(self, event):
    wildcard = (
      "Video files (*.mp4;*.mkv;*.avi;*.mov;*.webm)|*.mp4;*.mkv;*.avi;*.mov;*.webm|"
      "Subtitle files (*.srt;*.vtt;*.ass;*.sub)|*.srt;*.vtt;*.ass;*.sub|"
      "All files (*.*)|*.*"
    )

    with wx.FileDialog(self, "Open Video or Subtitle File", wildcard=wildcard,
                      style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
      if dialog.ShowModal() == wx.ID_CANCEL:
        return

      path = dialog.GetPath()
      ext = os.path.splitext(path)[1].lower()

      if ext in [".mp4", ".mkv", ".avi", ".mov", ".webm"]:
        self.file_path = path
        self.on_video_selected(None)

      elif ext in [".srt", ".vtt", ".ass", ".sub"]:
        self.load_subtitle_file(path)

      else:
        wx.MessageBox("Unsupported file type.", "Error", wx.ICON_ERROR)

  def load_subtitle_file(self, path):
    try:
      with open(path, "r", encoding="utf-8") as f:
        content = f.read()

      blocks = re.split(r"\n{2,}", content.strip())
      self.segment_list_panel.set_segments(blocks)
      self.output_box.SetValue(content)
      self.last_saved_text = content
      self.readonly_chk.Enable()

      if self.announce_enabled:
        self.announce("Subtitle loaded")

    except Exception as e:
      wx.MessageBox(f"Failed to load subtitle file:\n{e}", "Error", wx.ICON_ERROR)

  def on_open_filter_dialog(self, event=None):
    dlg = FilterDialog(self)
    if dlg.ShowModal() == wx.ID_OK:
      selected_filters = dlg.get_selected_filters()
      self.segment_list_panel.apply_filters(selected_filters)
    dlg.Destroy()

  def on_speed_change(self, event):
    self.vlc_player.set_rate(self.speed_slider.GetValue() / 10)

  def on_volume_change(self, event):
    self.vlc_player.set_volume(self.volume_slider.GetValue())

  def adjust_volume(self, delta):
    new_volume = min(max(self.vlc_player.get_volume() + delta, 0), 100)
    self.vlc_player.set_volume(new_volume)
    if self.announce_enabled:
      msg = "Volume Up" if delta > 0 else "Volume Down"
      if new_volume == 100 or new_volume == 0:
        msg += " (Limit)"
      elif new_volume == 50:
        msg += " (Default)"
      self.announce(msg)

  def adjust_speed(self, delta):
    current_rate = self.vlc_player.get_rate()
    new_rate = round(min(max(current_rate + delta, 0.5), 2.0), 1)

    if new_rate == current_rate:
      return  # No change, so no need to announce

    self.vlc_player.set_rate(new_rate)

    if self.announce_enabled:
      if new_rate > current_rate:
        msg = "Faster"
      else:
        msg = "Slower"

      if new_rate == 1.0:
        msg += " (Default)"

      self.announce(msg)

  def on_seek(self, event):
    value = self.seek_slider.GetValue() / 1000
    self.vlc_player.set_position(value)

  def update_seek_slider(self, event):
    pos = self.vlc_player.get_position()
    self.seek_slider.SetValue(int(pos * 1000))
    if pos >= 0.99:
      self.timer.Stop()
      self.toggle_btn.SetLabel("Play")
      self.seek_slider.SetValue(0)

  def on_segments_changed(self):
    if hasattr(self, "segment_list_panel"):
      srt_text = self.segment_list_panel.get_srt()
      self.output_box.SetValue(srt_text)
      self.last_saved_text = srt_text

  def on_output_box_updated(self, event):
    if not hasattr(self, "segment_list_panel"):
      return

    # لو في حالة التحديث جاي من panel مش من المستخدم، منقدر نعمل flag مؤقت لتجنّب التكرار
    if getattr(self, "_updating_from_segments", False):
      return

    text = self.output_box.GetValue().strip()
    if not text:
      return

    # نحاول نعمل parsing سريع للأسطر بصيغة SRT
    lines = re.split(r"\n{2,}", text)
    self.segment_list_panel.set_segments(lines)

  def on_video_selected(self, event):
    self.readonly_chk.Enable()

  def update_language_ui_visibility(self, event=None):
    task = self.task_radio.GetStringSelection()
    if task == "Transcription":
      self.auto_detect_chk.Show(True)
      self.source_language_label.SetLabel("Choose Transcription Language:")
      self.source_language_row.ShowItems(True)
      self.target_language_row.ShowItems(False)
    elif task == "Translation":
      self.auto_detect_chk.Show(True)
      self.source_language_label.SetLabel("Source Language:")
      self.source_language_row.ShowItems(True)
      self.target_language_row.ShowItems(True)
    self.Layout()
    self.video_panel.Layout()
    self.on_auto_detect_toggle(None)

  def on_auto_detect_toggle(self, event):
    if self.auto_detect_chk.IsShown() and self.auto_detect_chk.IsChecked():
      self.source_language_combo.Disable()
    else:
      self.source_language_combo.Enable()

  def is_model_downloaded(self, model):
    model_path = get_model_cache_path(model)
    return os.path.isdir(model_path) and any(os.scandir(model_path))

  def update_model_button_state(self):
    model = self.model_combo.GetValue()
    if self.is_model_downloaded(model):
      self.download_btn.SetLabel("U&ninstall")
    else:
      self.download_btn.SetLabel("Download")

  def on_model_changed(self, event):
    self.update_model_button_state()

  def handle_model_button(self, event):
    model = self.model_combo.GetValue()
    model_path = get_model_cache_path(model)

    if self.is_model_downloaded(model):
      dlg = wx.MessageDialog(self, f"Are you sure you want to uninstall model '{model}'?", "Confirm", wx.YES_NO | wx.ICON_WARNING)
      if dlg.ShowModal() == wx.ID_YES:
        shutil.rmtree(model_path)
        wx.MessageBox(f"Model '{model}' uninstalled.", "Done")
        self.download_btn.SetLabel("Download")
      dlg.Destroy()
    else:
      if MODEL_WARNINGS.get(model):
        warn_dlg = wx.MessageDialog(self, f"The model '{model}' is large and may consume significant memory.\nDo you want to continue?", "Warning", wx.OK | wx.CANCEL | wx.ICON_WARNING)
        result = warn_dlg.ShowModal()
        warn_dlg.Destroy()
        if result != wx.ID_OK:
          return

      self.download_btn.Disable()
      self.download_btn.SetLabel("Downloading...")

      loading_dialog = wx.Dialog(self, title="Downloading Model", style=wx.DEFAULT_DIALOG_STYLE)
      dialog_sizer = wx.BoxSizer(wx.VERTICAL)

      gauge = wx.Gauge(loading_dialog, range=100, style=wx.GA_HORIZONTAL)
      dialog_sizer.Add(wx.StaticText(loading_dialog, label=f"Downloading model '{model}'..."), 0, wx.ALL | wx.ALIGN_CENTER, 10)
      dialog_sizer.Add(gauge, 0, wx.ALL | wx.EXPAND, 10)

      loading_dialog.SetSizer(dialog_sizer)
      loading_dialog.Fit()

      def download_model():
        try:
          model_thread = threading.Thread(
            target=lambda: WhisperModel(model, download_root=os.path.expanduser("~/.cache/huggingface"))
          )
          model_thread.start()

          def pulse_animation():
            while model_thread.is_alive():
              wx.CallAfter(gauge.Pulse)
              winsound.Beep(1000, 200)
              time.sleep(1)

          pulse_thread = threading.Thread(target=pulse_animation)
          pulse_thread.start()

          model_thread.join()
          pulse_thread.join()

          wx.CallAfter(loading_dialog.Destroy)
          wx.CallAfter(wx.MessageBox, f"Model '{model}' downloaded.", "Success")
          wx.CallAfter(self.download_btn.SetLabel, "Uninstall")
        except Exception as e:
          wx.CallAfter(loading_dialog.Destroy)
          wx.CallAfter(wx.MessageBox, f"Error downloading model: {e}", "Error", wx.ICON_ERROR)
          wx.CallAfter(self.download_btn.Enable)

      threading.Thread(target=download_model).start()
      loading_dialog.ShowModal()

  def transcribe_video(self):
    if self.is_transcribing:
      self.stop_event.set()
      self.output_box.AppendText("\nStopping...\n")
      return

    video_path = self.file_path if hasattr(self, "file_path") else None
    if not video_path:
      wx.MessageBox("Please select a video file first.", "Error", wx.OK | wx.ICON_ERROR)
      return

    task_mode = self.task_radio.GetStringSelection()
    task = "transcribe" if task_mode == "Transcription" else "translate"
    if self.announce_enabled:
      msg = "Transcription Started" if task == "transcribe" else "Translation Started"
      self.announce(msg)

    language_code = None
    if not self.auto_detect_chk.IsChecked():
      language_label = self.source_language_combo.GetValue()
      language_code = LANGUAGES.get(language_label, "en")

    self.output_box.SetValue("Running...")
    self.is_transcribing = True
    self.stop_event.clear()
    self.start_btn.SetLabel("Stop")

    def run_transcription():
      try:
        model_size = self.model_combo.GetValue()
        model = WhisperModel(model_size, compute_type="int8", download_root=os.path.expanduser("~/.cache/huggingface"))
        segments = []
        segment_generator, _ = model.transcribe(video_path, task=task, language=language_code)

        for segment in segment_generator:
          if self.stop_event.is_set():
            wx.CallAfter(self.output_box.AppendText, "\nStopped by user.")
            break
          segments.append(segment)

        if not self.stop_event.is_set():
          try:
            if task == "translate":
              translator = Translator()
              translated_lines = []
              for idx, seg in enumerate(segments, start=1):
                translated = translator.translate(seg.text.strip(), 
        dest=LANGUAGES.get(self.target_language_combo.GetValue(), "en"))
                start = format_srt_time(seg.start)
                end = format_srt_time(seg.end)
                translated_lines.append(f"{idx}\n{start} --> {end}\n{translated.text}\n")
              srt_text = "\n".join(translated_lines)
            else:
              srt_text = format_segments_to_srt(segments)
              wx.CallAfter(self.segment_list_panel.set_segments, segments)
            wx.CallAfter(self.output_box.SetValue, srt_text)
            wx.CallAfter(lambda: setattr(self, "last_saved_text", srt_text))
            wx.CallAfter(self.output_box.SetFocus)
          except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Translation failed: {e}", "Error", wx.ICON_ERROR)

      except Exception as e:
        wx.CallAfter(wx.MessageBox, f"Error during transcription: {e}", "Error", wx.ICON_ERROR)
      finally:
        wx.CallAfter(self.reset_transcription_button)

    self.transcription_thread = threading.Thread(target=run_transcription)
    self.transcription_thread.start()

  def reset_transcription_button(self):
    self.is_transcribing = False
    self.start_btn.SetLabel("Start")
    self.start_btn.Enable()
    self.transcription_thread = None
    self.stop_event.clear()

  def save_result(self, event):
    with wx.FileDialog(self, "Save Output", wildcard="SubRip (*.srt)|*.srt|Text (*.txt)|*.txt",
                      style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
      if dialog.ShowModal() == wx.ID_CANCEL:
        return
      path = dialog.GetPath()
      content = self.output_box.GetValue()
      try:
        with open(path, "w", encoding="utf-8") as f:
          f.write(content)
        self.saved_path = path
        self.last_saved_text = content
      except Exception as e:
        wx.MessageBox(f"Failed to save file:\n{e}", "Error", wx.ICON_ERROR)

  def save_or_update_file(self, event):
    content = self.output_box.GetValue()

    if not self.saved_path:
      with wx.FileDialog(self, "Save Output", wildcard="SubRip (*.srt)|*.srt|Text (*.txt)|*.txt",
                        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
        if dialog.ShowModal() == wx.ID_CANCEL:
          return
        self.saved_path = dialog.GetPath()

    try:
      with open(self.saved_path, "w", encoding="utf-8") as f:
        f.write(content)
      self.last_saved_text = content
    except Exception as e:
      wx.MessageBox(f"Failed to save file:\n{e}", "Error", wx.ICON_ERROR)
