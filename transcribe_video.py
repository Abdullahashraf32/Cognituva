import os
import sys
import shutil
import threading
import time
import winsound
import re
from settings_utils import (
  load_settings,
  save_settings,
  format_srt_time,
  format_segments_to_srt,
  TranscriptionSettingsDialog
)

import tempfile
import json

libs_path = os.path.join(os.path.dirname(__file__), "libs")
if libs_path not in sys.path:
  sys.path.insert(0, libs_path)
cytolk_path = os.path.join(libs_path, "cytolk")
if cytolk_path not in sys.path:
  sys.path.insert(0, cytolk_path)

import comtypes.client
import tolk
import wx
import wx.adv
import vlc
from segment_list import SegmentListPanel
from dialogs import FilterDialog, GoToDialog, JumpToDialog
from ass_writer import generate_ass_file

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

  def set_position_by_time(self, seconds):
    self.player.set_time(int(seconds * 1000))

  def get_current_playback_seconds(self):
    return self.player.get_time() / 1000

  def get_duration_ms(self):
    if self.media is not None:
      try:
        self.media.parse_with_options(vlc.MediaParseFlag.local, 2000)
      except Exception:
        try:
          self.media.parse()
        except Exception:
          pass
      try:
        d = self.media.get_duration()
        if d and d > 0:
          return d
      except Exception:
        pass
    return self.player.get_length()


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
    self.output_modified = False
    self.saved_path = None
    tolk.try_sapi(True)
    tolk.load()
    self.announce_enabled = announce_enabled

    self.segment_queue = []
    self.segment_index = -1
    self.segment_timer = None

    self.segment_guard = None
    self.current_segment_end = None

    self._cached_total_ms = 0

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

    self.video_width = 800
    self.video_height = 450

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

    self.preferences_btn = wx.Button(self, label="Pr&eferences")
    self.preferences_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_LIST_VIEW, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    self.preferences_btn.Bind(wx.EVT_BUTTON, self.on_open_settings_dialog)
    self.add_hover_effect(self.preferences_btn, wx.Colour(102, 102, 255))
    main_sizer.Add(self.preferences_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    self.filter_btn = wx.Button(self, label="&Filter By")
    self.filter_btn.SetBitmap(wx.ArtProvider.GetBitmap(wx.ART_FIND, wx.ART_BUTTON, (16, 16)), wx.LEFT)
    self.filter_btn.Bind(wx.EVT_BUTTON, self.on_open_filter_dialog)
    self.add_hover_effect(self.filter_btn, wx.Colour(0, 153, 255))
    main_sizer.Add(self.filter_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    self.go_to_btn = wx.Button(self, label="&Go To")
    self.go_to_btn.Bind(wx.EVT_BUTTON, self.on_open_go_to_dialog)
    self.add_hover_effect(self.go_to_btn, wx.Colour(0, 204, 204))
    main_sizer.Add(self.go_to_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    self.jump_to_btn = wx.Button(self, label="&Jump To")
    self.jump_to_btn.Bind(wx.EVT_BUTTON, self.on_open_jump_to_dialog)
    self.add_hover_effect(self.jump_to_btn, wx.Colour(0, 128, 160))
    main_sizer.Add(self.jump_to_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    output_box_sizer = wx.StaticBoxSizer(wx.VERTICAL, self, "Transcript Output")

    self.output_box = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_DONTWRAP)
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
    self.shift_jump = 1
    self.ctrl_jump = 5
    self.alt_jump = 2
    self.ctrl_shift_jump = 10

    self.readonly_mode = True
    self.enable_beep = False
    self.after_transcription_action = "Show message"

    settings = self.load_settings_from_file()
    if settings:
      self.settings_cache = settings
      self.apply_settings(settings)
    else:
      self.apply_settings({
        "shift_forward": self.shift_forward_seconds,
        "shift_backward": self.shift_backward_seconds,
        "ctrl_forward": self.ctrl_forward_seconds,
        "ctrl_backward": self.ctrl_backward_seconds,
        "video_width": self.video_width,
        "video_height": self.video_height,
        "readonly": self.readonly_mode,
        "beep": self.enable_beep,
        "after_action": self.after_transcription_action
      })

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

  def load_settings_from_file(self, path=None):
    if path is None:
      path = os.path.join(os.path.dirname(__file__), "settings.json")
    try:
      with open(path, "r", encoding="utf-8") as f:
        settings = json.load(f)
        return settings
    except Exception:
      return None

  def setup_shortcuts(self):
    self.SetAcceleratorTable(wx.AcceleratorTable([]))
    shortcut_actions = [
    {"key": (wx.ACCEL_CTRL, ord("P")), "handler": self.on_toggle_play},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("P")), "handler": self.on_play_with_subtitles},
    {"key": (wx.ACCEL_CTRL, wx.WXK_SPACE), "handler": self.on_pause_resume},
    {"key": (wx.ACCEL_NORMAL, wx.WXK_F11), "handler": self.on_open_settings_dialog},
    {"key": (wx.ACCEL_SHIFT, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-self.shift_jump)},
    {"key": (wx.ACCEL_SHIFT, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(self.shift_jump)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-self.ctrl_jump)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(self.ctrl_jump)},
    {"key": (wx.ACCEL_ALT, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-self.alt_jump)},
    {"key": (wx.ACCEL_ALT, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(self.alt_jump)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_LEFT), "handler": lambda evt: self.vlc_player.seek_relative(-self.ctrl_shift_jump)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_RIGHT), "handler": lambda evt: self.vlc_player.seek_relative(self.ctrl_shift_jump)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_UP), "handler": lambda evt: self.adjust_volume(5)},
    {"key": (wx.ACCEL_CTRL, wx.WXK_DOWN), "handler": lambda evt: self.adjust_volume(-5)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_UP), "handler": lambda evt: self.adjust_speed(0.1)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_DOWN), "handler": lambda evt: self.adjust_speed(-0.1)},
    {"key": (wx.ACCEL_CTRL, ord("O")), "handler": self.on_open_video},
    {"key": (wx.ACCEL_CTRL, ord("S")), "handler": lambda evt: self.save_or_update_file(None)},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("S")), "handler": lambda evt: self.save_result(None)},
    {"key": (wx.ACCEL_CTRL, ord("T")), "handler": lambda evt: self.transcribe_video()},
    {"key": (wx.ACCEL_CTRL, wx.WXK_F4), "handler": lambda evt: self.confirm_exit(None)},
    {"key": (wx.ACCEL_CTRL, ord("D")), "handler": self.on_open_filter_dialog},
    {"key": (wx.ACCEL_CTRL, ord("G")), "handler": self.on_open_go_to_dialog},
    {"key": (wx.ACCEL_CTRL, ord("J")), "handler": self.on_open_jump_to_dialog},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("E")), "handler": self.on_announce_elapsed},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("R")), "handler": self.on_announce_remaining},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("T")), "handler": self.on_announce_total},
    {"key": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("C")), "handler": self.on_announce_current},
    {"key": (wx.ACCEL_CTRL, ord("R")), "handler": self.on_toggle_readonly},
    {"key": (wx.ACCEL_CTRL, wx.WXK_NUMPAD4), "handler": self.on_shrink_width},
    {"key": (wx.ACCEL_CTRL, wx.WXK_NUMPAD6), "handler": self.on_expand_width},
    {"key": (wx.ACCEL_CTRL, wx.WXK_NUMPAD8), "handler": self.on_expand_height},
    {"key": (wx.ACCEL_CTRL, wx.WXK_NUMPAD2), "handler": self.on_shrink_height},
    {"key": (wx.ACCEL_CTRL, ord("B")), "handler": self.on_toggle_beep},
    ]

    accel_entries = []
    for action in shortcut_actions:
      accel_id = wx.NewIdRef()
      accel_entries.append(wx.AcceleratorEntry(*action["key"], accel_id))
      self.Bind(wx.EVT_MENU, action["handler"], id=accel_id.GetId())

    self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))
    self.GetTopLevelParent().SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

  def confirm_exit(self, event):
    self.cleanup()
    self.handle_unsaved_changes(self.on_back)

  def confirm_close(self, event):
    self.cleanup()
    def proceed():
      self.GetTopLevelParent().Destroy()
    self.handle_unsaved_changes(proceed)

  def handle_unsaved_changes(self, proceed_callback):
    if not self.output_modified and self.output_box.GetValue() == self.last_saved_text:
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
    self.video_panel.SetMinSize((self.video_width, self.video_height))
    self.video_panel.SetBackgroundColour(wx.BLACK)
    video_sizer.Add(self.video_panel, 0, wx.ALIGN_CENTER | wx.ALL, 10)

    self.vlc_player = VLCPlayer(self.video_panel)
    self.video_panel.Bind(wx.EVT_SIZE, self.vlc_player.on_resize)

    control_sizer = wx.BoxSizer(wx.HORIZONTAL)

    self.toggle_btn = wx.Button(self, label="Play")
    menu = wx.Menu()

    item_play = menu.Append(wx.ID_ANY, "Play / Stop\tCtrl+P")
    item_sub_play = menu.Append(wx.ID_ANY, "Play with Subtitles\tCtrl+Shift+P")

    self.Bind(wx.EVT_MENU, self.on_toggle_play, item_play)
    self.Bind(wx.EVT_MENU, self.on_play_with_subtitles, item_sub_play)

    self.toggle_btn.Bind(wx.EVT_BUTTON, lambda evt: self.toggle_btn.PopupMenu(menu))
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
    if isinstance(message, dict):
      action = message.get("action")
      if action == "play_segments":
        segments = message.get("segments", [])
        self.play_given_segments(segments)
        return

    if self.announce_enabled and message:
      tolk.output(message, interrupt=True)

  def _warm_media_duration(self):
    try:
      d = self.vlc_player.get_duration_ms()
      if d and d > 0:
        self._cached_total_ms = d
    except:
      pass

  def cleanup(self):
    if hasattr(self, "cleaned") and self.cleaned:
      return
    if getattr(self, "segment_timer", None):
      try:
        self.segment_timer.Stop()
      except Exception:
        pass
    if getattr(self, "segment_guard", None):
      try:
        self.segment_guard.Stop()
      except Exception:
        pass
    self.segment_queue = []
    self.segment_index = -1
    if hasattr(self, "temp_subtitle_path") and os.path.exists(self.temp_subtitle_path):
      try:
        os.remove(self.temp_subtitle_path)
      except Exception:
        pass
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
      if getattr(self, "segment_timer", None):
        try:
          self.segment_timer.Stop()
        except Exception:
          pass
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

  def play_subtitles_from_text(self, srt_text, start_time=None, announce_message="Play with Subtitles"):
    temp_ass_path = generate_ass_file(srt_text)
    self.temp_subtitle_path = temp_ass_path

    if hasattr(self, "file_path"):
      self.vlc_player.set_media(self.file_path)
      self.vlc_player.media.add_option(f":sub-file={temp_ass_path}")
      if start_time:
        h, m, s_ms = start_time.split(":")
        s, ms = s_ms.split(",")
        total_seconds = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        self.vlc_player.media.add_option(f":start-time={total_seconds}")
      self.vlc_player.play()

      self.finalize_play_setup()
      if self.announce_enabled:
        self.announce(announce_message)
    else:
      wx.MessageBox("Please select a video file first.", "Error")

  def on_play_with_subtitles(self, event=None):
    srt_text = self.output_box.GetValue().strip()
    if not srt_text:
      wx.MessageBox("Output box is empty.", "No Subtitles")
      return

    state = self.vlc_player.player.get_state()

    if state == vlc.State.Playing:
      self.vlc_player.pause()
      if self.announce_enabled:
        self.announce("Pause with Subtitles")
      return

    if state == vlc.State.Paused:
      self.vlc_player.pause()
      self.timer.Start(500)
      if self.announce_enabled:
        self.announce("Resume with Subtitles")
      return

    self.play_subtitles_from_text(srt_text)

  def play_given_segments(self, segments):
    if not segments or not hasattr(self, "file_path"):
      wx.MessageBox("No video or segment to play.", "Error")
      return

    if getattr(self, "segment_timer", None):
      try:
        self.segment_timer.Stop()
      except Exception:
        pass
    if getattr(self, "segment_guard", None):
      try:
        self.segment_guard.Stop()
      except Exception:
        pass

    def parse_ts(ts):
      h, m, s_ms = ts.split(":")
      s, ms = s_ms.split(",")
      return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    temp_content = []
    ranges = []
    for i, (start, end, text) in enumerate(segments, 1):
      temp_content.append(f"{i}\n{start} --> {end}\n{text.strip()}\n")
      ranges.append((parse_ts(start), parse_ts(end)))
    srt_text = "\n".join(temp_content)

    self.segment_queue = ranges
    self.segment_index = 0

    self.play_subtitles_from_text(
      srt_text,
      start_time=segments[0][0],
      announce_message="Playing selected segments"
    )

    start_sec, end_sec = self.segment_queue[self.segment_index]
    self.current_segment_end = end_sec

    self.segment_guard = wx.Timer(self)
    self.Bind(wx.EVT_TIMER, self._on_segment_guard, self.segment_guard)
    self.segment_guard.Start(50)

  def stop_after_segment(self, event):
    if getattr(self, "segment_timer", None):
      try:
        self.segment_timer.Stop()
      except Exception:
        pass
    self.segment_queue = []
    self.segment_index = -1
    self.vlc_player.stop()
    self.seek_slider.SetValue(0)
    if self.announce_enabled:
      self.announce("Segment finished")

  def _start_segment(self, index):
    self.segment_index = index
    start_sec, end_sec = self.segment_queue[self.segment_index]
    state = self.vlc_player.player.get_state()
    if state in [vlc.State.NothingSpecial, vlc.State.Stopped, vlc.State.Ended]:
      if hasattr(self, "file_path") and self.file_path:
        self.vlc_player.set_media(self.file_path)
        self.vlc_player.media.add_option(f":start-time={start_sec}")
        self.vlc_player.play()
        wx.CallLater(100, self.finalize_play_setup)
    else:
      self.vlc_player.set_position_by_time(start_sec)
      wx.CallLater(120, lambda: self.vlc_player.set_position_by_time(start_sec))
    self.current_segment_end = end_sec

  def _on_segment_guard(self, event):
    now = self.vlc_player.get_current_playback_seconds()
    if self.current_segment_end is None:
      return
    if now >= self.current_segment_end - 0.03:
      self._advance_segment()

  def _advance_segment(self):
    next_index = self.segment_index + 1
    if next_index >= len(self.segment_queue):
      try:
        if getattr(self, "segment_guard", None):
          self.segment_guard.Stop()
      except Exception:
        pass
      self.segment_queue = []
      self.segment_index = -1
      self.current_segment_end = None
      self.vlc_player.stop()
      self.seek_slider.SetValue(0)
      if self.announce_enabled:
        self.announce("Segment(s) finished")
      return
    self._start_segment(next_index)

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
        self.vlc_player.set_media(self.file_path)
        wx.CallLater(10, self._warm_media_duration)
      elif ext in [".srt", ".vtt", ".ass", ".sub"]:
        self.load_subtitle_file(path)

      else:
        wx.MessageBox("Unsupported file type.", "Error", wx.ICON_ERROR)

  def on_open_settings_dialog(self, event=None):
    dlg = TranscriptionSettingsDialog(self)
    if dlg.ShowModal() == wx.ID_OK:
      settings = dlg.get_settings()
      self.settings_cache = settings

      self.apply_settings(settings)
      self.setup_shortcuts()

    dlg.Destroy()

  def load_subtitle_file(self, path):
    try:
      with open(path, "r", encoding="utf-8") as f:
        content = f.read()

      blocks = re.split(r"\n{2,}", content.strip())
      self.segment_list_panel.reset()
      self.segment_list_panel.set_segments(blocks)
      self.output_box.SetValue(self.wrap_text(content))
      self.last_saved_text = content
      self.saved_path = path

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

  def on_open_go_to_dialog(self, event=None):
    dlg = GoToDialog(self)
    if dlg.ShowModal() == wx.ID_OK:
      values = dlg.get_values()
      segment = values["go_to_segment"]
      use_range = values["use_range"]
      range_start = values["range_start"]
      range_end = values["range_end"]
      exclusions = values["exclusions"] if values["exclusions"] else None

      if use_range:
        self.segment_list_panel.apply_go_to(
          range_start=range_start,
          range_end=range_end,
          exclusions=exclusions
        )
      else:
        self.segment_list_panel.apply_go_to(
          target_segment=segment
        )

    dlg.Destroy()

  def on_open_jump_to_dialog(self, event=None):
    if not hasattr(self, "file_path"):
      wx.MessageBox("Please select a video file first.", "Error")
      return
    if getattr(self.vlc_player, "media", None) is None:
      self.vlc_player.set_media(self.file_path)
    try:
      current_ms = int(self.vlc_player.get_current_playback_seconds() * 1000)
    except:
      current_ms = 0
    if current_ms < 0:
      current_ms = 0
    dlg = JumpToDialog(self, initial_ms=current_ms)
    if dlg.ShowModal() == wx.ID_OK:
      t_ms = dlg.get_time_ms()
      duration_ms = self.vlc_player.get_duration_ms()
      if duration_ms > 0 and t_ms > duration_ms:
        wx.MessageBox("Entered time exceeds video duration.", "Error", wx.ICON_ERROR)
      else:
        if getattr(self.vlc_player, "media", None) is None:
          self.vlc_player.set_media(self.file_path)
        state = self.vlc_player.player.get_state()
        if state not in (vlc.State.Playing, vlc.State.Paused):
          self.vlc_player.play()
          wx.CallLater(120, lambda: self.vlc_player.set_position_by_time(t_ms / 1000.0))
        else:
          self.vlc_player.set_position_by_time(t_ms / 1000.0)
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
      return

    self.vlc_player.set_rate(new_rate)

    if self.announce_enabled:
      if new_rate > current_rate:
        msg = "Faster"
      else:
        msg = "Slower"

      if new_rate == 1.0:
        msg += " (Default)"

      self.announce(msg)

  def wrap_text(self, text, max_width=45):
    wrapped_lines = []
    for line in text.splitlines():
      while len(line) > max_width:
        split_at = line.rfind(" ", 0, max_width)
        if split_at == -1:
          split_at = max_width
        wrapped_lines.append(line[:split_at].strip())
        line = line[split_at:].strip()
      wrapped_lines.append(line)
    return "\n".join(wrapped_lines)

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
    if hasattr(self, "_updating_from_output") and self._updating_from_output:
      return
    self._updating_from_segments = True

    if hasattr(self, "segment_list_panel"):
      srt_text = self.segment_list_panel.get_srt()
      self.output_box.SetValue(self.wrap_text(srt_text))
      self.output_modified = True
      self._updating_from_segments = False

  def on_toggle_readonly(self, event=None):
    self.readonly_mode = not self.readonly_mode
    self.output_box.SetEditable(not self.readonly_mode)
    try:
      s = getattr(self, "settings_cache", {}) or {}
      s["readonly"] = self.readonly_mode
      self.settings_cache = s
      save_settings(s)
    except:
      pass
    if self.announce_enabled:
      self.announce("Readonly enabled" if self.readonly_mode else "Readonly disabled")

  def on_toggle_beep(self, event=None):
    self.enable_beep = not self.enable_beep
    try:
      s = getattr(self, "settings_cache", {}) or {}
      s["beep"] = self.enable_beep
      self.settings_cache = s
      save_settings(s)
    except:
      pass
    if self.announce_enabled:
      self.announce("Beep enabled" if self.enable_beep else "Beep disabled")

  def _persist_video_size(self):
    try:
      s = getattr(self, "settings_cache", {}) or {}
      s["video_width"] = self.video_width
      s["video_height"] = self.video_height
      self.settings_cache = s
      save_settings(s)
    except:
      pass

  def _resize_video(self, dw=0, dh=0, announce_label=""):
    min_w, min_h = 160, 120
    step = getattr(self, "resize_step", 40)
    self.video_width = max(min_w, int(self.video_width + (dw or 0)))
    self.video_height = max(min_h, int(self.video_height + (dh or 0)))
    if hasattr(self, "video_panel"):
      self.video_panel.SetMinSize((self.video_width, self.video_height))
      self.video_panel.SetSize((self.video_width, self.video_height))
      self.video_panel.Layout()
      self.Layout()
    self._persist_video_size()
    if self.announce_enabled and announce_label:
      self.announce(f"{announce_label} {self.video_width} by {self.video_height}")

  def on_shrink_width(self, event=None):
    step = getattr(self, "resize_step", 40)
    self._resize_video(dw=-step, dh=0, announce_label="Video size")

  def on_expand_width(self, event=None):
    step = getattr(self, "resize_step", 40)
    self._resize_video(dw=step, dh=0, announce_label="Video size")

  def on_expand_height(self, event=None):
    step = getattr(self, "resize_step", 40)
    self._resize_video(dw=0, dh=step, announce_label="Video size")

  def on_shrink_height(self, event=None):
    step = getattr(self, "resize_step", 40)
    self._resize_video(dw=0, dh=-step, announce_label="Video size")

  def _format_ms(self, ms):
    if ms is None or ms < 0:
      ms = 0
    h = ms // 3600000
    r = ms % 3600000
    m = r // 60000
    r2 = r % 60000
    s = r2 // 1000
    ms2 = r2 % 1000
    return h, m, s, ms2

  def _no_video_feedback(self):
    if self.announce_enabled:
      self.announce("No video is open")

  def on_announce_elapsed(self, event=None):
    if not hasattr(self, "file_path"):
      self._no_video_feedback()
      return
    cur_ms = int(max(0, self.vlc_player.get_current_playback_seconds() * 1000))
    h, m, s, _ = self._format_ms(cur_ms)
    self.announce(f"Elapsed {h} hours {m} minutes {s} seconds") if self.announce_enabled else None

  def on_announce_remaining(self, event=None):
    if not hasattr(self, "file_path"):
      self._no_video_feedback()
      return
    dur = self.vlc_player.get_duration_ms()
    cur_ms = int(max(0, self.vlc_player.get_current_playback_seconds() * 1000))
    if dur and dur > 0:
      rem = max(0, int(dur - cur_ms))
      h, m, s, _ = self._format_ms(rem)
      msg = f"Remaining {h} hours {m} minutes {s} seconds"
    else:
      msg = "Duration unknown"
    self.announce(msg) if self.announce_enabled else None

  def on_announce_total(self, event=None):
    if not hasattr(self, "file_path"):
      self._no_video_feedback()
      return

    if getattr(self.vlc_player, "media", None) is None:
      self.vlc_player.set_media(self.file_path)

    dur_ms = self._cached_total_ms or self.vlc_player.get_duration_ms()
    if dur_ms and dur_ms > 0:
      self._cached_total_ms = dur_ms
      msg = f"Total time {format_srt_time(dur_ms / 1000.0)}"
      if self.announce_enabled:
        self.announce(msg)
    else:
      if self.announce_enabled:
        self.announce("Loading duration, please try again")
      wx.CallLater(50, self._warm_media_duration)

  def on_announce_current(self, event=None):
    if not hasattr(self, "file_path"):
      self._no_video_feedback()
      return
    cur_ms = int(max(0, self.vlc_player.get_current_playback_seconds() * 1000))
    h, m, s, ms2 = self._format_ms(cur_ms)
    self.announce(f"Current time {h} hours {m} minutes {s} seconds {ms2} milliseconds") if self.announce_enabled else None

  def on_output_box_updated(self, event):
    if not hasattr(self, "segment_list_panel"):
      return

    if getattr(self, "_updating_from_segments", False):
      return

    self._updating_from_output = True

    text = self.output_box.GetValue().strip()
    if not text:
      return

    lines = re.split(r"\n{2,}", text)
    self.segment_list_panel.set_segments(lines)
    self.output_modified = True

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
      self.download_btn.SetLabel("&Download")

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
        self.download_btn.SetLabel("&Download")
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
          wx.CallAfter(self.download_btn.SetLabel, "U&ninstall")
        except Exception as e:
          wx.CallAfter(loading_dialog.Destroy)
          wx.CallAfter(wx.MessageBox, f"Error downloading model: {e}", "Error", wx.ICON_ERROR)
          wx.CallAfter(self.download_btn.Enable)

      threading.Thread(target=download_model).start()
      loading_dialog.ShowModal()

  def transcribe_video(self):
    from faster_whisper import WhisperModel
    if self.is_transcribing:
      self.stop_event.set()
      self.output_box.AppendText(self.wrap_text("\nStopping...\n"))
      return

    video_path = self.file_path if hasattr(self, "file_path") else None
    if not video_path:
      wx.MessageBox("Please select a video file first.", "Error", wx.OK | wx.ICON_ERROR)
      return

    task_mode = self.task_radio.GetStringSelection()
    task = "transcribe" if task_mode == "Transcription" else "translate"
    target_lang_label = self.target_language_combo.GetValue()
    target_lang_code = LANGUAGES.get(target_lang_label, "en")
    if self.announce_enabled:
      msg = "Transcription Started" if task == "transcribe" else "Translation Started"
      self.announce(msg)

    language_code = None
    if not self.auto_detect_chk.IsChecked():
      language_label = self.source_language_combo.GetValue()
      language_code = LANGUAGES.get(language_label, "en")
    target_lang_code = LANGUAGES.get(self.target_language_combo.GetValue(), "en")

    self.output_box.SetValue("Running...")
    if hasattr(self, "settings_cache"):
      self.apply_settings(self.settings_cache)
    self.is_transcribing = True
    self.stop_event.clear()
    self.start_btn.SetLabel("&Stop")

    def run_transcription():
      if self.enable_beep:
        self.start_beep()
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
              from googletrans import Translator
              translator = Translator()
              translated_lines = []
              for idx, seg in enumerate(segments, start=1):
                try:
                  translated = translator.translate(seg.text.strip(), dest=target_lang_code)
                  translated_text = translated.text
                except Exception as e:
                  translated_text = f"[Translation failed: {e}]"
                start = format_srt_time(seg.start)
                end = format_srt_time(seg.end)
                translated_lines.append(f"{idx}\n{start} --> {end}\n{translated.text}\n")
              srt_text = "\n".join(translated_lines)
            else:
              srt_text = format_segments_to_srt(segments)
              wx.CallAfter(self.segment_list_panel.set_segments, segments)
            wx.CallAfter(self.output_box.SetValue, srt_text)
            wx.CallAfter(lambda: setattr(self, "last_saved_text", srt_text))
            if self.after_transcription_action == "Show message":
              wx.CallAfter(wx.MessageBox, "Transcription complete.", "Done")
            elif self.after_transcription_action == "Show tooltip":
              wx.CallAfter(lambda: wx.adv.NotificationMessage(
    title=f"{'Transcription' if task == 'transcribe' else 'Translation'} Complete",
    message=f"{'Transcription' if task == 'transcribe' else 'Translation'} has finished successfully."
  ).Show(timeout=wx.adv.NotificationMessage.Timeout_Auto))
            elif self.after_transcription_action == "Focus output":
              def focus_output():
                self.output_box.SetFocus()
                self.output_box.Refresh()
                self.output_box.Update()

              wx.CallAfter(focus_output)
              wx.CallAfter(self.Raise)
              wx.CallAfter(self.output_box.SetFocus)
            elif self.after_transcription_action == "Do nothing":
              pass
          except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Translation failed: {e}", "Error", wx.ICON_ERROR)

      except Exception as e:
        wx.CallAfter(wx.MessageBox, f"Error during transcription: {e}", "Error", wx.ICON_ERROR)
      finally:
        if self.enable_beep:
          self.stop_beep()
        wx.CallAfter(self.reset_transcription_button)

    self.transcription_thread = threading.Thread(target=run_transcription)
    self.transcription_thread.start()

  def reset_transcription_button(self):
    self.is_transcribing = False
    self.start_btn.SetLabel("&Start")
    self.start_btn.Enable()
    self.transcription_thread = None
    self.stop_event.clear()

  def apply_settings(self, settings):
    self.shift_jump = settings.get("shift_jump", self.shift_jump)
    self.ctrl_jump = settings.get("ctrl_jump", self.ctrl_jump)
    self.alt_jump = settings.get("alt_jump", self.alt_jump)
    self.ctrl_shift_jump = settings.get("ctrl_shift_jump", self.ctrl_shift_jump)

    self.video_width = settings.get("video_width", self.video_width)
    self.video_height = settings.get("video_height", self.video_height)

    self.readonly_mode = settings.get("readonly", self.readonly_mode)
    self.enable_beep = settings.get("beep", self.enable_beep)
    self.after_transcription_action = settings.get("after_action", self.after_transcription_action)

    self.resize_step = int(settings.get("resize_step", 40))

    self.output_box.SetEditable(not self.readonly_mode)
    if hasattr(self, "video_panel"):
      self.video_panel.SetMinSize((self.video_width, self.video_height))
      self.video_panel.SetSize((self.video_width, self.video_height))
      self.video_panel.Layout()
      self.Layout()

  def start_beep(self):
    def beep_loop():
      while getattr(self, "_beep_active", False):
        winsound.Beep(1000, 300)
        time.sleep(0.5)
    self._beep_active = True
    self._beep_thread = threading.Thread(target=beep_loop)
    self._beep_thread.daemon = True
    self._beep_thread.start()

  def stop_beep(self):
    self._beep_active = False

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
        self.output_modified = False
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
      self.output_modified = False
    except Exception as e:
      wx.MessageBox(f"Failed to save file:\n{e}", "Error", wx.ICON_ERROR)
