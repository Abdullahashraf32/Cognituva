import wx
import os
import sys
import shutil
import threading
import time
import winsound

libs_path = os.path.join(os.path.dirname(__file__), "libs")
sys.path.insert(0, libs_path)

from faster_whisper import WhisperModel

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

def format_segments_to_srt(segments):
  def format_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"

  lines = []
  for idx, segment in enumerate(segments, start=1):
    start = format_srt_time(segment.start)
    end = format_srt_time(segment.end)
    text = segment.text.strip()
    lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
  return "\n".join(lines)

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

class TranscriptionPanel(wx.Panel):
  def __init__(self, parent, on_back):
    super().__init__(parent)
    self.on_back = on_back
    self.is_transcribing = False
    self.transcription_thread = None
    self.stop_event = threading.Event()

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    self.file_btn = wx.FilePickerCtrl(self, message="Select Video File")
    main_sizer.Add(self.file_btn, 0, wx.ALL | wx.EXPAND, 10)

    self.task_radio = wx.RadioBox(
      self, label="Choose Task", choices=["Transcription", "Translation"], majorDimension=1, style=wx.RA_SPECIFY_ROWS
    )
    self.task_radio.Bind(wx.EVT_RADIOBOX, self.update_language_ui_visibility)
    main_sizer.Add(self.task_radio, 0, wx.ALL, 10)

    self.auto_detect_chk = wx.CheckBox(self, label="Auto-detect source language")
    self.auto_detect_chk.SetValue(True)
    self.auto_detect_chk.Bind(wx.EVT_CHECKBOX, self.on_auto_detect_toggle)
    main_sizer.Add(self.auto_detect_chk, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    self.source_language_row = wx.BoxSizer(wx.HORIZONTAL)
    self.source_language_label = wx.StaticText(self, label="Choose Transcription Language:")
    self.source_language_row.Add(self.source_language_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
    self.source_language_combo = wx.ComboBox(self, choices=list(LANGUAGES.keys()), style=wx.CB_READONLY)
    self.source_language_combo.SetValue("English")
    self.source_language_combo.Disable()
    self.source_language_row.Add(self.source_language_combo, 1)
    main_sizer.Add(self.source_language_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

    self.target_language_row = wx.BoxSizer(wx.HORIZONTAL)
    self.target_language_label = wx.StaticText(self, label="Target Language:")
    self.target_language_row.Add(self.target_language_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
    self.target_language_combo = wx.ComboBox(self, choices=list(LANGUAGES.keys()), style=wx.CB_READONLY)
    self.target_language_combo.SetValue("English")
    self.target_language_row.Add(self.target_language_combo, 1)
    main_sizer.Add(self.target_language_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

    self.update_language_ui_visibility()

    model_row = wx.BoxSizer(wx.HORIZONTAL)
    model_label = wx.StaticText(self, label="Choose Model:")
    model_row.Add(model_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
    self.model_combo = wx.ComboBox(self, choices=["tiny", "base", "small", "medium", "large-v2"], style=wx.CB_READONLY)
    self.model_combo.SetValue("small")
    self.model_combo.Bind(wx.EVT_COMBOBOX, self.on_model_changed)
    model_row.Add(self.model_combo, 1, wx.RIGHT, 5)
    self.download_btn = wx.Button(self, label="Download")
    self.download_btn.Bind(wx.EVT_BUTTON, self.handle_model_button)
    model_row.Add(self.download_btn, 0)
    main_sizer.Add(model_row, 0, wx.ALL | wx.EXPAND, 10)

    self.start_btn = wx.Button(self, label="Start")
    self.start_btn.Bind(wx.EVT_BUTTON, lambda evt: self.transcribe_video())
    main_sizer.Add(self.start_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)

    self.output_box = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
    main_sizer.Add(self.output_box, 1, wx.ALL | wx.EXPAND, 10)

    save_btn = wx.Button(self, label="Save Result")
    save_btn.Bind(wx.EVT_BUTTON, self.save_result)
    main_sizer.Add(save_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    back_btn = wx.Button(self, label="Back")
    back_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_back())
    main_sizer.Add(back_btn, 0, wx.ALIGN_LEFT | wx.ALL, 10)

    self.SetSizer(main_sizer)
    self.update_model_button_state()

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
      self.download_btn.SetLabel("Uninstall")
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

    video_path = self.file_btn.GetPath()
    if not video_path:
      wx.MessageBox("Please select a video file first.", "Error", wx.OK | wx.ICON_ERROR)
      return

    task_mode = self.task_radio.GetStringSelection()
    task = "transcribe" if task_mode == "Transcription" else "translate"

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
          srt_text = format_segments_to_srt(segments)
          wx.CallAfter(self.output_box.SetValue, srt_text)

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
    with wx.FileDialog(self, "Save Output", wildcard="SubRip (*.srt)|*.srt|Text (*.txt)|*.txt", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
      if dialog.ShowModal() == wx.ID_CANCEL:
        return
      path = dialog.GetPath()
      content = self.output_box.GetValue()
      with open(path, "w", encoding="utf-8") as f:
        f.write(content)
