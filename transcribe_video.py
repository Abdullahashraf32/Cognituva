import wx

class TranscriptionPanel(wx.Panel):
  def __init__(self, parent, on_back):
    super().__init__(parent)
    self.on_back = on_back

    instruction = wx.StaticText(self, label="Feature under construction...")

    back_btn = wx.Button(self, label="Back")
    back_btn.Bind(wx.EVT_BUTTON, lambda event: self.on_back())

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(instruction, 0, wx.ALL | wx.CENTER, 20)
    sizer.Add(back_btn, 0, wx.ALL | wx.CENTER, 10)

    self.SetSizer(sizer)
