import wx

class FilterDialog(wx.Dialog):
  def __init__(self, parent):
    super().__init__(parent, title="Filter Segments", size=(400, 500))

    self.styles = ["Bold", "Italic", "Underline"]
    self.alignments = [
      "Top Left", "Top Center", "Top Right",
      "Middle Left", "Middle Center", "Middle Right",
      "Bottom Left", "Bottom Center", "Bottom Right"
    ]

    self.selected_styles = {}
    self.selected_alignments = {}
    self.recently_modified = wx.CheckBox(self, label="Show only recently modified segments")

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    # Group 1: Text Styles
    style_box = wx.StaticBox(self, label="Text Styles")
    style_sizer = wx.StaticBoxSizer(style_box, wx.VERTICAL)

    first_checkbox = None  # 🔸 متغير لحفظ أول CheckBox
    for idx, style in enumerate(self.styles):
      cb = wx.CheckBox(self, label=style)
      if idx == 0:
        first_checkbox = cb  # ✅ نحفظ أول CheckBox
      self.selected_styles[style] = cb
      style_sizer.Add(cb, 0, wx.ALL, 5)

    # Group 2: Alignments
    align_box = wx.StaticBox(self, label="Alignments")
    align_sizer = wx.StaticBoxSizer(align_box, wx.VERTICAL)
    for align in self.alignments:
      cb = wx.CheckBox(self, label=align)
      self.selected_alignments[align] = cb
      align_sizer.Add(cb, 0, wx.ALL, 5)

    # Group 3: Other Options
    other_box = wx.StaticBox(self, label="Other Options")
    other_sizer = wx.StaticBoxSizer(other_box, wx.VERTICAL)
    other_sizer.Add(self.recently_modified, 0, wx.ALL, 5)

    self.filter_by_word_checkbox = wx.CheckBox(self, label="Filter segments by word")
    self.case_sensitive_checkbox = wx.CheckBox(self, label="Case sensitive")
    self.case_sensitive_checkbox.Hide()

    self.word_input = wx.TextCtrl(self)
    self.word_input.Hide()

    self.filter_by_word_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_word_filter)

    word_filter_sizer = wx.BoxSizer(wx.VERTICAL)
    word_filter_sizer.Add(self.filter_by_word_checkbox, 0, wx.ALL, 5)
    word_filter_sizer.Add(self.case_sensitive_checkbox, 0, wx.ALL, 5)
    word_filter_sizer.Add(self.word_input, 0, wx.EXPAND | wx.ALL, 5)

    main_sizer.Add(word_filter_sizer, 0, wx.EXPAND | wx.ALL, 10)

    # Buttons
    btn_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)

    # Add groups to main layout
    main_sizer.Add(style_sizer, 0, wx.EXPAND | wx.ALL, 10)
    main_sizer.Add(align_sizer, 0, wx.EXPAND | wx.ALL, 10)

    clear_btn = wx.Button(self, label="&Deselect All")
    clear_btn.Bind(wx.EVT_BUTTON, lambda event: self.deselect_all())
    main_sizer.Add(clear_btn, 0, wx.ALIGN_CENTER | wx.ALL, 5)

    main_sizer.Add(other_sizer, 0, wx.EXPAND | wx.ALL, 10)
    if btn_sizer:
      main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

    self.SetSizer(main_sizer)
    self.Layout()

    # ✅ بعد ترتيب العناصر، نحط الـ Focus
    if first_checkbox:
      first_checkbox.SetFocus()

  def get_selected_filters(self):
    selected_styles = [k for k, cb in self.selected_styles.items() if cb.IsChecked()]
    selected_alignments = [k for k, cb in self.selected_alignments.items() if cb.IsChecked()]
    recent_only = self.recently_modified.IsChecked()
    filter_by_word = self.filter_by_word_checkbox.IsChecked()
    case_sensitive = self.case_sensitive_checkbox.IsChecked()
    word_query = self.word_input.GetValue().strip()

    return {
      "styles": selected_styles,
      "alignments": selected_alignments,
      "recent": recent_only,
      "filter_by_word": filter_by_word,
      "case_sensitive": case_sensitive,
      "word_query": word_query,
    }

  def deselect_all(self):
    """Uncheck all checkboxes in the filter dialog."""
    for cb in self.selected_styles.values():
      cb.SetValue(False)
    for cb in self.selected_alignments.values():
      cb.SetValue(False)
    self.recently_modified.SetValue(False)

  def on_toggle_word_filter(self, event):
    enabled = self.filter_by_word_checkbox.IsChecked()

    # Show/hide word input and case checkbox
    self.case_sensitive_checkbox.Show(enabled)
    self.word_input.Show(enabled)

    # Disable/enable the other controls
    for cb in self.selected_styles.values():
      cb.Enable(not enabled)
    for cb in self.selected_alignments.values():
      cb.Enable(not enabled)
    self.recently_modified.Enable(not enabled)

    self.Layout()
