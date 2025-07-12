import sys
import os
from settings_utils import load_settings, save_settings

libs_path = os.path.join(os.path.dirname(__file__), "libs")

if libs_path not in sys.path:
  sys.path.insert(0, libs_path)

wx_lib_path = os.path.join(libs_path, "wx")
if wx_lib_path not in sys.path:
  sys.path.insert(0, wx_lib_path)

import wx
class MainMenu(wx.Frame):
  def __init__(self):
    super().__init__(None, title="Cognituva", size=(600, 400))
    
    self.settings = load_settings()
    self.container = wx.BoxSizer(wx.VERTICAL)
    self.SetSizer(self.container)

    self.current_panel = None
    self.show_main_menu()
    self.Bind(wx.EVT_CLOSE, self.on_close)

  def show_main_menu(self):
    if self.current_panel:
      self.current_panel.Destroy()

    menu_panel = wx.Panel(self)
    self.current_panel = menu_panel

    sizer = wx.BoxSizer(wx.VERTICAL)

    transcribe_btn = wx.Button(menu_panel, label="Transcribe Video")
    transcribe_btn.Bind(wx.EVT_BUTTON, self.open_transcribe)
    self.announce_shortcuts_chk = wx.CheckBox(menu_panel, label="Enable shortcut announcements")
    self.announce_shortcuts_chk.SetValue(self.settings.get("announce_shortcuts", True))
    self.announce_shortcuts_chk.Bind(wx.EVT_CHECKBOX, self.on_toggle_announce)

    convert_btn = wx.Button(menu_panel, label="Audio/Video Converter")
    convert_btn.Bind(wx.EVT_BUTTON, self.open_converter)

    sizer.Add(transcribe_btn, 0, wx.ALL | wx.EXPAND, 10)
    sizer.Add(convert_btn, 0, wx.ALL | wx.EXPAND, 10)

    menu_panel.SetSizer(sizer)

    self.container.Clear(True)
    self.container.Add(menu_panel, 1, wx.EXPAND)
    self.Layout()

    wx.CallAfter(transcribe_btn.SetFocus)

  def open_transcribe(self, event=None):
    from transcribe_video import TranscriptionPanel
    announce = self.settings.get("announce_shortcuts", True)
    panel = TranscriptionPanel(self, on_back=self.show_main_menu, announce_enabled=announce)
    self.show_panel(panel)

  def open_converter(self, event=None):
    from audio_video_converter import AudioVideoConverterPanel
    panel = AudioVideoConverterPanel(self, on_back=self.show_main_menu)
    self.show_panel(panel)

  def on_toggle_announce(self, event):
    self.settings["announce_shortcuts"] = self.announce_shortcuts_chk.GetValue()
    save_settings(self.settings)

  def on_close(self, event):
    if hasattr(self, "current_panel") and hasattr(self.current_panel, "confirm_close"):
      self.current_panel.confirm_close(event)
    else:
      self.Destroy()

  def show_panel(self, new_panel):
    if self.current_panel:
      self.current_panel.Destroy()
    self.current_panel = new_panel
    self.container.Clear(True)
    self.container.Add(new_panel, 1, wx.EXPAND)
    self.Layout()
    wx.CallAfter(new_panel.SetFocus)

if __name__ == "__main__":
  app = wx.App(False)
  frame = MainMenu()
  frame.Show()
  app.MainLoop()
