import wx
import os
import sys
import subprocess
import winsound
import threading

base_path = os.path.dirname(__file__)
ffmpeg_path = os.path.join(base_path, "libs", "bin", "ffmpeg.exe")
ffprobe_path = os.path.join(base_path, "libs", "bin", "ffprobe.exe")

class AudioVideoConverterPanel(wx.Panel):
  def __init__(self, parent, on_back):
      super().__init__(parent)
      self.input_paths = []
      self.on_back = on_back
      self.beep_running = False

      main_sizer = wx.BoxSizer(wx.VERTICAL)

      self.beep_checkbox = wx.CheckBox(self, label="&Beep while conversion is running")
      main_sizer.Add(self.beep_checkbox, 0, wx.ALL, 10)

      self.save_in_docs_checkbox = wx.CheckBox(self, label="Sa&ve output to  Documents")
      main_sizer.Add(self.save_in_docs_checkbox, 0, wx.ALL, 10)

      self.open_folder_checkbox = wx.CheckBox(self, label="O&pen containing folder after conversion")
      main_sizer.Add(self.open_folder_checkbox, 0, wx.ALL, 10)

      self.type_choice = wx.RadioBox(
          self, label="Select &Type",
          choices=["Audio", "Video"],
          majorDimension=1,
          style=wx.RA_SPECIFY_ROWS
      )
      self.type_choice.Bind(wx.EVT_RADIOBOX, self.on_type_change)
      main_sizer.Add(self.type_choice, 0, wx.ALL | wx.EXPAND, 10)

      format_sizer = wx.BoxSizer(wx.HORIZONTAL)
      format_sizer.Add(wx.StaticText(self, label="Output &Format:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.format_combo = wx.ComboBox(self, choices=[], style=wx.CB_READONLY)
      format_sizer.Add(self.format_combo, 1)
      main_sizer.Add(format_sizer, 0, wx.ALL | wx.EXPAND, 10)

      self.web_optimize = wx.CheckBox(self, label="&Web Optimize")
      self.web_optimize.Bind(wx.EVT_CHECKBOX, lambda evt: self.update_controls_state())
      self.web_optimize.Disable()
      main_sizer.Add(self.web_optimize, 0, wx.ALL, 10)

      video_options_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Vi&deo Options"), wx.VERTICAL)

      resolution_sizer = wx.BoxSizer(wx.HORIZONTAL)
      resolution_sizer.Add(wx.StaticText(self, label="W&idth:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.width_input = wx.TextCtrl(self)
      resolution_sizer.Add(self.width_input, 1, wx.RIGHT, 10)
      resolution_sizer.Add(wx.StaticText(self, label="&Height:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.height_input = wx.TextCtrl(self)
      resolution_sizer.Add(self.height_input, 1)
      video_options_box.Add(resolution_sizer, 0, wx.ALL | wx.EXPAND, 5)

      frame_sizer = wx.BoxSizer(wx.HORIZONTAL)
      frame_sizer.Add(wx.StaticText(self, label="Frame Rate:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.frame_rate_combo = wx.ComboBox(self, choices=["", "15", "24", "30", "60"], style=wx.CB_READONLY)
      frame_sizer.Add(self.frame_rate_combo, 1)
      video_options_box.Add(frame_sizer, 0, wx.ALL | wx.EXPAND, 5)

      main_sizer.Add(video_options_box, 0, wx.ALL | wx.EXPAND, 10)

      self.burnin_checkbox = wx.CheckBox(self, label="B&urn-in subtitle into video")
      self.burnin_checkbox.Bind(wx.EVT_CHECKBOX, self.on_burnin_toggle)
      main_sizer.Add(self.burnin_checkbox, 0, wx.ALL, 10)

      self.subtitle_panel = wx.Panel(self)
      subtitle_sizer = wx.BoxSizer(wx.VERTICAL)

      lang_sizer = wx.BoxSizer(wx.HORIZONTAL)
      lang_sizer.Add(wx.StaticText(self.subtitle_panel, label="&Subtitle Language:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.subtitle_lang_combo = wx.ComboBox(self.subtitle_panel, choices=["English", "Arabic", "French", "German"], style=wx.CB_READONLY)
      self.subtitle_lang_combo.SetSelection(0)
      lang_sizer.Add(self.subtitle_lang_combo, 1)

      encoding_sizer = wx.BoxSizer(wx.HORIZONTAL)
      encoding_sizer.Add(wx.StaticText(self.subtitle_panel, label="&Encoding:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.subtitle_encoding_combo = wx.ComboBox(self.subtitle_panel, choices=["UTF-8", "windows-1256", "ISO-8859-1", "Shift_JIS"], style=wx.CB_READONLY)
      self.subtitle_encoding_combo.SetSelection(0)
      encoding_sizer.Add(self.subtitle_encoding_combo, 1)

      self.play_after_burn_checkbox = wx.CheckBox(self.subtitle_panel, label="P&lay video after burn-in")
      subtitle_sizer.Add(self.play_after_burn_checkbox, 0, wx.TOP, 5)
      self.play_after_burn_checkbox.Hide()

      file_sizer = wx.BoxSizer(wx.HORIZONTAL)
      self.subtitle_path = wx.TextCtrl(self.subtitle_panel, style=wx.TE_READONLY)
      browse_sub_btn = wx.Button(self.subtitle_panel, label="B&rowse Subtitle")
      browse_sub_btn.Bind(wx.EVT_BUTTON, self.on_browse_subtitle)
      file_sizer.Add(self.subtitle_path, 1, wx.RIGHT, 5)
      file_sizer.Add(browse_sub_btn)

      subtitle_sizer.Add(lang_sizer, 0, wx.BOTTOM | wx.EXPAND, 5)
      subtitle_sizer.Add(encoding_sizer, 0, wx.BOTTOM | wx.EXPAND, 5)
      subtitle_sizer.Add(file_sizer, 0, wx.EXPAND)
      self.subtitle_panel.SetSizer(subtitle_sizer)
      self.subtitle_panel.Hide()
      main_sizer.Add(self.subtitle_panel, 0, wx.ALL | wx.EXPAND, 10)

      bitrate_sizer = wx.BoxSizer(wx.HORIZONTAL)
      bitrate_sizer.Add(wx.StaticText(self, label="Bi&trate (kbps):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.bitrate_combo = wx.ComboBox(self, choices=["64", "96", "128", "192", "256", "320"], style=wx.CB_READONLY)
      self.bitrate_combo.SetSelection(2)
      bitrate_sizer.Add(self.bitrate_combo, 1)
      main_sizer.Add(bitrate_sizer, 0, wx.ALL | wx.EXPAND, 10)

      self.channels_radio = wx.RadioBox(self, label="&Channels", choices=["Mono", "Stereo"], majorDimension=1, style=wx.RA_SPECIFY_ROWS)
      main_sizer.Add(self.channels_radio, 0, wx.ALL | wx.EXPAND, 10)

      volume_sizer = wx.BoxSizer(wx.HORIZONTAL)
      volume_sizer.Add(wx.StaticText(self, label="Volu&me (%):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.volume_combo = wx.ComboBox(self, choices=["50", "75", "100", "125", "150", "200"], style=wx.CB_READONLY)
      self.volume_combo.SetSelection(2)
      volume_sizer.Add(self.volume_combo, 1)
      main_sizer.Add(volume_sizer, 0, wx.ALL | wx.EXPAND, 10)

      sample_sizer = wx.BoxSizer(wx.HORIZONTAL)
      sample_sizer.Add(wx.StaticText(self, label="S&ample Rate (Hz):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
      self.sample_rate_combo = wx.ComboBox(self, choices=["8000", "16000", "22050", "32000", "44100", "48000", "96000"], style=wx.CB_READONLY)
      self.sample_rate_combo.SetSelection(4)
      sample_sizer.Add(self.sample_rate_combo, 1)
      main_sizer.Add(sample_sizer, 0, wx.ALL | wx.EXPAND, 10)

      input_file_sizer = wx.BoxSizer(wx.HORIZONTAL)
      self.input_path = wx.TextCtrl(self, style=wx.TE_READONLY)
      browse_btn = wx.Button(self, label="Ch&oose file")
      browse_btn.Bind(wx.EVT_BUTTON, self.on_browse)
      input_file_sizer.Add(self.input_path, 1, wx.RIGHT, 5)
      input_file_sizer.Add(browse_btn)
      main_sizer.Add(input_file_sizer, 0, wx.ALL | wx.EXPAND, 10)

      self.convert_btn = wx.Button(self, label="S&tart Conversion")
      self.convert_btn.Bind(wx.EVT_BUTTON, self.on_convert)
      main_sizer.Add(self.convert_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)

      back_btn = wx.Button(self, label="&Back")
      back_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_back())
      main_sizer.Add(back_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)

      self.SetSizer(main_sizer)

      self.on_type_change()

      self.update_controls_state()

  def update_controls_state(self):
    web_opt = self.web_optimize.IsChecked()
    self.width_input.Enable(not web_opt)
    self.height_input.Enable(not web_opt)
    self.frame_rate_combo.Enable(not web_opt)

  def on_type_change(self, event=None):
    is_audio = self.type_choice.GetStringSelection() == "Audio"
    audio_formats = [
  "mp3", "m4a", "wav", "wma", "aac", "ac3", "aiff", "aifc", "alac", "amr", "au", "caf", "dff", "dsf", "dts",
  "flac", "flp", "gsm", "kar", "m2a", "m4b", "m4p", "mlp", "mka", "mid",
  "mp2", "mpc", "oga", "ofr", "ofs", "oma", "opus", "ra", "rm", "sd2",
  "snd", "spx", "tta", "voc", "w64", "wv", "wvpk", "ogg", "pcm"
]
    video_formats = [
  "mp4", "3g2", "3gp", "amv", "asf", "avi", "avs", "drc", "f4p", "f4v", "fli",
  "flc", "flv", "gif", "m1v", "m2p", "m2ts", "m2v", "m4v", "mkv", "mlp",
  "mov", "mpe", "mpeg", "mpg", "mpg2", "mpv", "mxf", "mjp", "mjpeg",
  "nsv", "nut", "ogg", "ogv", "qt", "rm", "rmj", "rmvb", "roq", "svi",
  "ts", "vob", "viv", "vivo", "vp8", "vp9", "webm", "wmv", "yuv", "y4m"
]
    self.format_combo.SetItems(audio_formats if is_audio else video_formats)
    self.format_combo.SetSelection(0)
    
    self.sample_rate_combo.Show(is_audio)
    self.bitrate_combo.Show(is_audio)
    self.channels_radio.Show(is_audio)
    self.volume_combo.Show(is_audio)
    
    self.web_optimize.Enable(not is_audio)
    self.update_controls_state()
    
    self.width_input.Show(not is_audio)
    self.height_input.Show(not is_audio)
    self.frame_rate_combo.Show(not is_audio)
    self.burnin_checkbox.Show(not is_audio)

    show_burn_controls = not is_audio and self.burnin_checkbox.IsChecked()
    self.subtitle_panel.Show(show_burn_controls)
    self.play_after_burn_checkbox.Show(show_burn_controls)

    self.Layout()

  def on_browse(self, event):
    with wx.FileDialog(self, "Choose media files", wildcard="Media files (*.*)|*.*", style=wx.FD_OPEN | wx.FD_MULTIPLE) as dialog:
      if dialog.ShowModal() == wx.ID_OK:
        paths = dialog.GetPaths()
        if paths:
          self.input_paths = paths
          self.input_path.SetValue(paths[0])

          if self.type_choice.GetStringSelection() == "Video":
            width, height, framerate = self.get_video_info(paths[0])
            self.width_input.SetValue(width)
            self.height_input.SetValue(height)
            if framerate:
              if framerate not in self.frame_rate_combo.GetItems():
                self.frame_rate_combo.Insert(framerate, 0)
                self.frame_rate_combo.SetValue(framerate)

  def on_burnin_toggle(self, event):
    is_video = self.type_choice.GetStringSelection() == "Video"
    show_options = is_video and self.burnin_checkbox.IsChecked()
    self.subtitle_panel.Show(show_options)
    self.play_after_burn_checkbox.Show(show_options)
    self.Layout()
    self.Layout()

  def on_browse_subtitle(self, event):
    wildcard = ("Subtitle files (*.srt;*.ass;*.ssa;*.vtt;*.sub;*.idx;*.mpl;*.ttml)|"
                "*.srt;*.ass;*.ssa;*.vtt;*.sub;*.idx;*.mpl;*.ttml|"
                "All files (*.*)|*.*")
  
    with wx.FileDialog(self, "Choose subtitle file", wildcard=wildcard, style=wx.FD_OPEN) as dialog:
      if dialog.ShowModal() == wx.ID_OK:
        self.subtitle_path.SetValue(dialog.GetPath())

  def get_video_info(self, path):
    try:
      result = subprocess.run([
        ffprobe_path, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
      ], text=True, capture_output=True)

      lines = result.stdout.strip().splitlines()

      if len(lines) >= 3:
        width, height, framerate_raw = lines
        if "/" in framerate_raw:
          num, denom = framerate_raw.split("/")
          framerate = str(round(int(num) / int(denom))) if int(denom) != 0 else ""
        else:
          framerate = framerate_raw
        return width, height, framerate
    except Exception as e:
      return "", "", ""

  def burnin_subtitle_with_ffmpeg(self, input_path, subtitle_path, output_path):
    encoding = self.subtitle_encoding_combo.GetValue()

    subtitle_path = os.path.abspath(subtitle_path).replace('\\', '/').replace(":", "\\:")
    subtitle_filter = f"subtitles='{subtitle_path}':charenc={encoding}"

    command = [
      ffmpeg_path,
      "-i", input_path,
      "-vf", subtitle_filter,
      "-c:a", "copy",
      "-y", output_path
  ]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
      raise Exception(result.stderr)

  def open_containing_folder(self, folder_path):
    folder_path = os.path.abspath(folder_path)
    try:
      os.startfile(folder_path)
    except Exception as e:
      wx.MessageBox(f"Failed to open folder:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)

  def beep_loop(self, finish_event):
    while self.beep_running:
      winsound.Beep(1000, 200)
      wx.MilliSleep(300)
    if finish_event is not None:
      msg, title, style = finish_event
      wx.CallAfter(wx.MessageBox, msg, title, style)

  def on_convert(self, event):
    input_paths = getattr(self, "input_paths", None)
    if not input_paths:
      input_path = self.input_path.GetValue()
      input_paths = [input_path] if input_path else []

    output_ext = self.format_combo.GetValue()
    subtitle_file = self.subtitle_path.GetValue()

    if not input_paths or not output_ext:
      if not self.beep_checkbox.IsChecked():
        wx.MessageBox("Please fill in all required fields.", "Error", wx.OK | wx.ICON_ERROR)
        return
      else:
        self.beep_running = False
        finish_event = ("Please fill in all required fields.", "Error", wx.OK | wx.ICON_ERROR)
        threading.Thread(target=self.beep_loop, args=(finish_event,), daemon=True).start()
        return

    if self.type_choice.GetStringSelection() == "Video":
      try:
        width = int(self.width_input.GetValue())
        height = int(self.height_input.GetValue())
      except ValueError:
        if not self.beep_checkbox.IsChecked():
          wx.MessageBox("Please enter valid width and height.", "Error", wx.OK | wx.ICON_ERROR)
          return
        else:
          self.beep_running = False
          finish_event = ("Please enter valid width and height.", "Error", wx.OK | wx.ICON_ERROR)
          threading.Thread(target=self.beep_loop, args=(finish_event,), daemon=True).start()
          return

    finish_event = None
    if self.beep_checkbox.IsChecked():
      self.beep_running = True
      threading.Thread(target=self.beep_loop, args=(None,), daemon=True).start()

    try:
      for input_path in input_paths:
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        if self.save_in_docs_checkbox.IsChecked():
          documents_folder = os.path.join(os.path.expanduser("~"), "Documents")
          cognituva_folder = os.path.join(documents_folder, "cognituva")
          os.makedirs(cognituva_folder, exist_ok=True)
          output_path = os.path.join(cognituva_folder, f"{base_name}_converted.{output_ext}")
        else:
          dir_name = os.path.dirname(input_path)
          output_path = os.path.join(dir_name, f"{base_name}_converted.{output_ext}")

        if self.burnin_checkbox.IsChecked() and subtitle_file:
          try:
            self.burnin_subtitle_with_ffmpeg(input_path, subtitle_file, output_path)
            if self.play_after_burn_checkbox.IsChecked():
              os.startfile(output_path)
          except Exception as e:
            finish_event = (f"Subtitle burn-in failed:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            return
        else:
          try:
            command = [ffmpeg_path, "-i", input_path]
            if self.type_choice.GetStringSelection() == "Audio":
              command += ["-b:a", f"{self.bitrate_combo.GetValue()}k"]
              command += ["-ar", self.sample_rate_combo.GetValue()]
              command += ["-ac", "1" if self.channels_radio.GetSelection() == 0 else "2"]
              volume = self.volume_combo.GetValue()
              if volume != "100":
                command += ["-filter:a", f"volume={int(volume)/100}"]
            else:
              vf = []
              if self.width_input.GetValue() and self.height_input.GetValue():
                vf.append(f"scale={self.width_input.GetValue()}:{self.height_input.GetValue()}")
              if vf:
                command += ["-vf", ",".join(vf)]
              if self.frame_rate_combo.GetValue():
                command += ["-r", self.frame_rate_combo.GetValue()]
              if self.web_optimize.IsChecked():
                command += ["-c:v", "libx264", "-crf", "30", "-preset", "medium", "-movflags", "faststart"]
              else:
                command += ["-c:v", "libx264"]
            command += ["-y", output_path]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
              finish_event = (f"Conversion failed:\n{result.stderr}", "Error", wx.OK | wx.ICON_ERROR)
              return
          except Exception as e:
            finish_event = (f"Conversion failed:\n{str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            return

      finish_event = ("Conversion completed successfully!", "Success", wx.OK | wx.ICON_INFORMATION)

      if self.open_folder_checkbox.IsChecked() and input_paths:
        if self.save_in_docs_checkbox.IsChecked():
          self.open_containing_folder(cognituva_folder)
        else:
          first_dir = os.path.dirname(input_paths[0])
          self.open_containing_folder(first_dir)

    finally:
      self.beep_running = False
      if finish_event is not None:
        threading.Thread(target=self.beep_loop, args=(finish_event,), daemon=True).start()
