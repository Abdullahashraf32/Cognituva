import sys
sys.path.insert(0, "libs")

import wx

class TranscriptionFrame(wx.Frame):
  def __init__(self):
    super().__init__(parent=None, title="Transcribe Video", size=(600, 400))
    panel = wx.Panel(self)

    instruction = wx.StaticText(panel, label="Feature under construction...")

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(instruction, 0, wx.ALL | wx.CENTER, 20)

    panel.SetSizer(sizer)

if __name__ == "__main__":
  app = wx.App(False)
  frame = TranscriptionFrame()
  frame.Show()
  app.MainLoop()
