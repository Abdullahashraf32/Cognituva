import sys
import os

libs_path = os.path.join(os.path.dirname(__file__), "libs")
wx_lib_path = os.path.join(libs_path, "wx")
if wx_lib_path not in sys.path:
  sys.path.insert(0, wx_lib_path)

import wx


class FilterDialog(wx.Dialog):
  def __init__(self, parent):
    super().__init__(parent, title="Filter Segments", size=(400, 500))

    bg_color = wx.Colour(250, 250, 250)
    fg_color = wx.Colour(0, 64, 128)
    input_bg = wx.Colour(255, 255, 255)
    staticbox_bg = wx.Colour(245, 245, 245)
    button_bg = wx.Colour(224, 224, 224)
    button_hover = wx.Colour(204, 224, 255)

    self.SetBackgroundColour(bg_color)

    self.styles = ["Bold", "Italic", "Underline"]
    self.alignments = [
      "Top Left", "Top Center", "Top Right",
      "Middle Left", "Middle Center", "Middle Right",
      "Bottom Left", "Bottom Center", "Bottom Right"
    ]
    self.selected_styles = {}
    self.selected_alignments = {}

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    main_sizer.Add(self._create_word_filter_section(fg_color, input_bg), 0, wx.EXPAND | wx.ALL, 10)
    main_sizer.Add(self._create_styles_section(fg_color, staticbox_bg), 0, wx.EXPAND | wx.ALL, 10)
    main_sizer.Add(self._create_alignments_section(fg_color, staticbox_bg), 0, wx.EXPAND | wx.ALL, 10)
    main_sizer.Add(self._create_other_options_section(fg_color, staticbox_bg), 0, wx.EXPAND | wx.ALL, 10)

    clear_btn = wx.Button(self, label="&Deselect All")
    clear_btn.SetBackgroundColour(button_bg)
    clear_btn.SetForegroundColour(wx.BLACK)

    clear_btn.Bind(wx.EVT_ENTER_WINDOW, lambda evt: clear_btn.SetBackgroundColour(button_hover))
    clear_btn.Bind(wx.EVT_LEAVE_WINDOW, lambda evt: clear_btn.SetBackgroundColour(button_bg))

    clear_btn.Bind(wx.EVT_BUTTON, lambda event: self.deselect_all())
    main_sizer.Add(clear_btn, 0, wx.ALIGN_CENTER | wx.ALL, 5)

    btn_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
    if btn_sizer:
      main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

    self.SetSizer(main_sizer)
    self.Layout()

    if self.styles:
      self.selected_styles[self.styles[0]].SetFocus()


  def _create_styles_section(self, fg_color, bg_color):
    box = wx.StaticBox(self, label="Text Styles")
    box.SetBackgroundColour(bg_color)
    sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

    for style in self.styles:
      cb = wx.CheckBox(self, label=style)
      cb.SetForegroundColour(fg_color)
      cb.SetBackgroundColour(bg_color)
      self.selected_styles[style] = cb
      sizer.Add(cb, 0, wx.ALL, 5)

    return sizer

  def _create_alignments_section(self, fg_color, bg_color):
    box = wx.StaticBox(self, label="Alignments")
    box.SetBackgroundColour(bg_color)
    sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

    for align in self.alignments:
      cb = wx.CheckBox(self, label=align)
      cb.SetForegroundColour(fg_color)
      cb.SetBackgroundColour(bg_color)
      self.selected_alignments[align] = cb
      sizer.Add(cb, 0, wx.ALL, 5)

    return sizer

  def _create_other_options_section(self, fg_color, bg_color):
    box = wx.StaticBox(self, label="Other Options")
    box.SetBackgroundColour(bg_color)
    sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

    self.recently_modified = wx.CheckBox(self, label="&Show only recently modified segments")
    self.recently_modified.SetForegroundColour(fg_color)
    self.recently_modified.SetBackgroundColour(bg_color)

    sizer.Add(self.recently_modified, 0, wx.ALL, 5)
    return sizer

  def _create_word_filter_section(self, fg_color, input_bg):
    sizer = wx.BoxSizer(wx.VERTICAL)

    self.filter_by_word_checkbox = wx.CheckBox(self, label="&Filter segments by word")
    self.case_sensitive_checkbox = wx.CheckBox(self, label="&Case sensitive")
    self.word_input = wx.TextCtrl(self)

    self.filter_by_word_checkbox.SetForegroundColour(fg_color)
    self.case_sensitive_checkbox.SetForegroundColour(fg_color)

    self.filter_by_word_checkbox.SetBackgroundColour(self.GetBackgroundColour())
    self.case_sensitive_checkbox.SetBackgroundColour(self.GetBackgroundColour())
    self.word_input.SetBackgroundColour(input_bg)

    self.case_sensitive_checkbox.Hide()
    self.word_input.Hide()

    self.filter_by_word_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_word_filter)

    sizer.Add(self.filter_by_word_checkbox, 0, wx.ALL, 5)
    sizer.Add(self.case_sensitive_checkbox, 0, wx.ALL, 5)
    sizer.Add(self.word_input, 0, wx.EXPAND | wx.ALL, 5)

    return sizer

  def deselect_all(self):
    for cb in self.selected_styles.values():
      cb.SetValue(False)
    for cb in self.selected_alignments.values():
      cb.SetValue(False)
    self.recently_modified.SetValue(False)
    self.filter_by_word_checkbox.SetValue(False)
    self.case_sensitive_checkbox.Hide()
    self.word_input.Hide()

    for cb in self.selected_styles.values():
      cb.Enable(True)
    for cb in self.selected_alignments.values():
      cb.Enable(True)
    self.recently_modified.Enable(True)

    self.Layout()

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

  def on_toggle_word_filter(self, event):
    enabled = self.filter_by_word_checkbox.IsChecked()

    self.case_sensitive_checkbox.Show(enabled)
    self.word_input.Show(enabled)

    for cb in self.selected_styles.values():
      cb.Enable(not enabled)
    for cb in self.selected_alignments.values():
      cb.Enable(not enabled)
    self.recently_modified.Enable(not enabled)

    self.Layout()

class GoToDialog(wx.Dialog):
  def __init__(self, parent):
    super().__init__(parent, title="Go To Segment", size=(420, 330))
    self.SetBackgroundColour(wx.Colour("#f4f6fa"))

    font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    self.SetFont(font)

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    # Segment number input
    segment_sizer = wx.BoxSizer(wx.HORIZONTAL)
    lbl_segment = wx.StaticText(self, label="S&egment Number:")
    lbl_segment.SetForegroundColour(wx.Colour("#333333"))
    segment_sizer.Add(lbl_segment, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

    self.segment_input = wx.TextCtrl(self, style=wx.BORDER_SIMPLE)
    self.segment_input.SetBackgroundColour(wx.Colour("#ffffff"))
    self.segment_input.SetForegroundColour(wx.Colour("#222222"))
    segment_sizer.Add(self.segment_input, 1, wx.EXPAND)

    main_sizer.Add(segment_sizer, 0, wx.EXPAND | wx.ALL, 12)

    # Checkbox for enabling range
    self.range_checkbox = wx.CheckBox(self, label="&Select range of segments")
    self.range_checkbox.SetForegroundColour(wx.Colour("#1c1c1c"))
    self.range_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_range)
    main_sizer.Add(self.range_checkbox, 0, wx.ALL, 12)

    # Range input panel
    self.range_panel = wx.Panel(self)
    self.range_panel.SetBackgroundColour(wx.Colour("#eef1f7"))
    range_sizer = wx.FlexGridSizer(rows=3, cols=2, vgap=8, hgap=10)

    def create_label_input_pair(label_text, shortcut_key):
      label = wx.StaticText(self.range_panel, label=label_text)
      label.SetForegroundColour(wx.Colour("#444"))
      input_box = wx.TextCtrl(self.range_panel, style=wx.BORDER_SIMPLE)
      input_box.SetMinSize((80, -1))
      input_box.SetBackgroundColour(wx.Colour("#ffffff"))
      input_box.SetForegroundColour(wx.Colour("#222222"))
      input_box.SetFont(font)
      return label, input_box

    lbl_start, self.range_start_input = create_label_input_pair("S&tart From:", "t")
    lbl_end, self.range_end_input = create_label_input_pair("E&nd To:", "n")
    lbl_excl, self.range_exclusions_input = create_label_input_pair("&Exclusions:", "x")

    for label, ctrl in [
      (lbl_start, self.range_start_input),
      (lbl_end, self.range_end_input),
      (lbl_excl, self.range_exclusions_input)
    ]:
      range_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
      range_sizer.Add(ctrl, 1, wx.EXPAND)

    range_sizer.AddGrowableCol(1, 1)
    self.range_panel.SetSizer(range_sizer)
    main_sizer.Add(self.range_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
    self.range_panel.Hide()

    # OK / Cancel buttons
    btn_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
    if btn_sizer:
      main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 12)

    self.SetSizer(main_sizer)
    self.Layout()
    self.segment_input.SetFocus()

    # Hover effect for segment input
    self.segment_input.Bind(wx.EVT_ENTER_WINDOW, lambda e: self.segment_input.SetBackgroundColour("#f0f8ff"))
    self.segment_input.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.segment_input.SetBackgroundColour("#ffffff"))

    # OK button confirm cleanup
    ok_button = self.FindWindowById(wx.ID_OK)
    if ok_button:
      ok_button.Bind(wx.EVT_BUTTON, self.on_confirm)

  def on_toggle_range(self, event):
    show = self.range_checkbox.IsChecked()
    self.range_panel.Show(show)
    self.Layout()

  def on_confirm(self, event):
    self.segment_input.SetValue(self.segment_input.GetValue().strip())
    self.range_start_input.SetValue(self.range_start_input.GetValue().strip())
    self.range_end_input.SetValue(self.range_end_input.GetValue().strip())
    self.range_exclusions_input.SetValue(self.range_exclusions_input.GetValue().strip())
    event.Skip()

  def get_values(self):
    segment = self.segment_input.GetValue().strip()
    use_range = self.range_checkbox.IsChecked()
    range_start = self.range_start_input.GetValue().strip()
    range_end = self.range_end_input.GetValue().strip()
    exclusions = self.range_exclusions_input.GetValue().strip()

    exclusion_list = [int(x.strip()) for x in exclusions.split(',') if x.strip().isdigit()]

    return {
      "go_to_segment": int(segment) if segment.isdigit() else None,
      "use_range": use_range,
      "range_start": int(range_start) if range_start.isdigit() else None,
      "range_end": int(range_end) if range_end.isdigit() else None,
      "exclusions": exclusion_list
    }

class LimitedNumericCtrl(wx.TextCtrl):
  def __init__(self, parent, max_len, value="0"):
    super().__init__(parent, value=str(value), style=wx.TE_PROCESS_ENTER)
    self.max_len = max_len
    self.Bind(wx.EVT_CHAR, self.on_char)
    self.Bind(wx.EVT_TEXT, self.on_text)

  def on_char(self, event):
    key = event.GetKeyCode()
    allowed_nav = [wx.WXK_BACK, wx.WXK_DELETE, wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_HOME, wx.WXK_END, wx.WXK_TAB]
    if key in allowed_nav:
      event.Skip()
      return
    if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
      event.Skip()
      return
    if 48 <= key <= 57 or wx.WXK_NUMPAD0 <= key <= wx.WXK_NUMPAD9:
      val = self.GetValue()
      if len(val) >= self.max_len and self.GetSelection() == (-1, -1):
        return
      event.Skip()
      return
    return

  def on_text(self, event):
    val = self.GetValue()
    if not val.isdigit() and val != "":
      digits_only = "".join(ch for ch in val if ch.isdigit())
      self.ChangeValue(digits_only[: self.max_len])
      self.SetInsertionPointEnd()
    elif len(val) > self.max_len:
      self.ChangeValue(val[: self.max_len])
      self.SetInsertionPointEnd()
    else:
      event.Skip()

  def get_int(self):
    v = self.GetValue().strip()
    if v == "":
      return 0
    try:
      return int(v)
    except:
      return 0


class JumpToDialog(wx.Dialog):
  def __init__(self, parent, initial_ms=0):
    super().__init__(parent, title="Jump To Time", size=(360, 220))
    try:
      base_ms = int(initial_ms)
    except:
      base_ms = 0
    if base_ms < 0:
      base_ms = 0
    h = base_ms // 3600000
    rem = base_ms % 3600000
    m = rem // 60000
    rem2 = rem % 60000
    s = rem2 // 1000
    ms = rem2 % 1000

    main = wx.BoxSizer(wx.VERTICAL)
    grid = wx.FlexGridSizer(rows=2, cols=4, vgap=8, hgap=10)

    self.hours  = LimitedNumericCtrl(self, max_len=2, value=h)
    self.minutes= LimitedNumericCtrl(self, max_len=2, value=m)
    self.seconds= LimitedNumericCtrl(self, max_len=2, value=s)
    self.millis = LimitedNumericCtrl(self, max_len=3, value=ms)

    grid.AddMany([
      (wx.StaticText(self, label="&Hours"), 0, wx.ALIGN_CENTER_VERTICAL),
      (wx.StaticText(self, label="&Minutes"), 0, wx.ALIGN_CENTER_VERTICAL),
      (wx.StaticText(self, label="&Seconds"), 0, wx.ALIGN_CENTER_VERTICAL),
      (wx.StaticText(self, label="Mi&lliseconds"), 0, wx.ALIGN_CENTER_VERTICAL),
      (self.hours, 1, wx.EXPAND),
      (self.minutes, 1, wx.EXPAND),
      (self.seconds, 1, wx.EXPAND),
      (self.millis, 1, wx.EXPAND),
    ])
    grid.AddGrowableCol(0, 1)
    grid.AddGrowableCol(1, 1)
    grid.AddGrowableCol(2, 1)
    grid.AddGrowableCol(3, 1)
    main.Add(grid, 1, wx.ALL | wx.EXPAND, 12)

    btns = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
    if btns:
      main.Add(btns, 0, wx.ALL | wx.EXPAND, 10)

    self.SetSizer(main)
    self.Layout()
    wx.CallAfter(self.hours.SetFocus)
    wx.CallAfter(self.hours.SelectAll)

  def get_time_ms(self):
    h  = max(0, self.hours.get_int())
    m  = max(0, self.minutes.get_int())
    s  = max(0, self.seconds.get_int())
    ms = max(0, self.millis.get_int())
    if m > 59: m = 59
    if s > 59: s = 59
    if ms > 999: ms = 999
    return ((h * 3600 + m * 60 + s) * 1000) + ms
