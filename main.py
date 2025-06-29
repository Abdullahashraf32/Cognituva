import wx
from edit_pdf import PDFEditorPanel
from transcribe_video import TranscriptionPanel
from audio_video_converter import AudioVideoConverterPanel

class MainMenu(wx.Frame):
  def __init__(self):
    super().__init__(None, title="Cognituva", size=(600, 400))
    
    self.container = wx.BoxSizer(wx.VERTICAL)
    self.SetSizer(self.container)

    self.current_panel = None
    self.show_main_menu()

  def show_main_menu(self):
    if self.current_panel:
      self.current_panel.Destroy()

    menu_panel = wx.Panel(self)
    self.current_panel = menu_panel

    sizer = wx.BoxSizer(wx.VERTICAL)

    transcribe_btn = wx.Button(menu_panel, label="Transcribe Video")
    transcribe_btn.Bind(wx.EVT_BUTTON, self.open_transcribe)

    edit_pdf_btn = wx.Button(menu_panel, label="Edit PDF")
    edit_pdf_btn.Bind(wx.EVT_BUTTON, self.open_pdf_editor)

    convert_btn = wx.Button(menu_panel, label="Audio/Video Converter")
    convert_btn.Bind(wx.EVT_BUTTON, self.open_converter)

    sizer.Add(transcribe_btn, 0, wx.ALL | wx.EXPAND, 10)
    sizer.Add(edit_pdf_btn, 0, wx.ALL | wx.EXPAND, 10)
    sizer.Add(convert_btn, 0, wx.ALL | wx.EXPAND, 10)

    menu_panel.SetSizer(sizer)

    self.container.Clear(True)
    self.container.Add(menu_panel, 1, wx.EXPAND)
    self.Layout()

    wx.CallAfter(transcribe_btn.SetFocus)

  def open_pdf_editor(self, event=None):
    panel = PDFEditorPanel(self, on_back=self.show_main_menu)
    self.show_panel(panel)

  def open_transcribe(self, event=None):
    panel = TranscriptionPanel(self, on_back=self.show_main_menu)
    self.show_panel(panel)

  def open_converter(self, event=None):
    panel = AudioVideoConverterPanel(self, on_back=self.show_main_menu)
    self.show_panel(panel)

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
