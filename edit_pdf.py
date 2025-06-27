import sys
sys.path.insert(0, "libs")

import wx
import fitz

class PDFEditorPanel(wx.Panel):
  def __init__(self, parent, on_back):
    super().__init__(parent)
    self.on_back = on_back

    open_btn = wx.Button(self, label="Open PDF")
    open_btn.Bind(wx.EVT_BUTTON, self.on_open_pdf)

    save_btn = wx.Button(self, label="Save as New PDF")
    save_btn.Bind(wx.EVT_BUTTON, self.on_save_pdf)

    back_btn = wx.Button(self, label="Back")
    back_btn.Bind(wx.EVT_BUTTON, lambda event: self.on_back())

    self.text_area = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_DONTWRAP)

    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    btn_sizer.Add(open_btn, 0, wx.ALL, 5)
    btn_sizer.Add(save_btn, 0, wx.ALL, 5)
    btn_sizer.Add(back_btn, 0, wx.ALL, 5)

    main_sizer = wx.BoxSizer(wx.VERTICAL)
    main_sizer.Add(btn_sizer, 0, wx.ALIGN_LEFT)
    main_sizer.Add(self.text_area, 1, wx.ALL | wx.EXPAND, 10)

    self.SetSizer(main_sizer)

  def on_open_pdf(self, event):
    with wx.FileDialog(self, "Open PDF file", wildcard="PDF files (*.pdf)|*.pdf",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
      if fileDialog.ShowModal() == wx.ID_CANCEL:
        return

      path = fileDialog.GetPath()
      self.load_pdf(path)

  def load_pdf(self, path):
    try:
      doc = fitz.open(path)
      text = ""
      for page in doc:
        text += page.get_text() + "\n\n"
      self.text_area.SetValue(text.strip())
    except Exception as e:
      wx.MessageBox(f"Error loading PDF: {e}", "Error", wx.OK | wx.ICON_ERROR)

  def on_save_pdf(self, event):
    with wx.FileDialog(self, "Save PDF as", wildcard="PDF files (*.pdf)|*.pdf",
                       style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as saveDialog:
      if saveDialog.ShowModal() == wx.ID_CANCEL:
        return

      save_path = saveDialog.GetPath()
      self.save_pdf(save_path)

  def save_pdf(self, path):
    try:
      text = self.text_area.GetValue()
      doc = fitz.open()
      page = doc.new_page()

      lines = text.splitlines()
      y = 50
      for line in lines:
        if y > 800:
          page = doc.new_page()
          y = 50
        page.insert_text((50, y), line, fontsize=12)
        y += 20

      doc.save(path)
      wx.MessageBox("PDF saved successfully.", "Success", wx.OK | wx.ICON_INFORMATION)
    except Exception as e:
      wx.MessageBox(f"Error saving PDF: {e}", "Error", wx.OK | wx.ICON_ERROR)
