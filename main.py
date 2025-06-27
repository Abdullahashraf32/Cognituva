import wx
from edit_pdf import PDFEditorFrame
from transcribe_video import TranscriptionFrame

class MainMenu(wx.Frame):
  def __init__(self):
    super().__init__(None, title="Cognituva", size=(400, 200))
    panel = wx.Panel(self)

    transcribe_btn = wx.Button(panel, label="Transcribe Video")
    transcribe_btn.Bind(wx.EVT_BUTTON, self.open_transcribe)

    edit_pdf_btn = wx.Button(panel, label="Edit PDF")
    edit_pdf_btn.Bind(wx.EVT_BUTTON, self.open_pdf_editor)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(transcribe_btn, 0, wx.ALL | wx.EXPAND, 10)
    sizer.Add(edit_pdf_btn, 0, wx.ALL | wx.EXPAND, 10)

    panel.SetSizer(sizer)

  def open_pdf_editor(self, event):
    frame = PDFEditorFrame()
    frame.Show()

  def open_transcribe(self, event):
    frame = TranscriptionFrame()
    frame.Show()

if __name__ == "__main__":
  app = wx.App(False)
  frame = MainMenu()
  frame.Show()
  app.MainLoop()
