import wx 
import re
from functools import partial
from settings_utils import format_srt_time, format_segments_to_srt

STYLE_TAGS = {
  "bold": "b",
  "italic": "i",
  "underline": "u",
}

COLOR_TAGS = {
  "White": "#FFFFFF",
  "Black": "#000000",
  "Gray": "#808080",
  "Light Gray": "#D3D3D3",
  "Dark Gray": "#404040",
  "Red": "#FF0000",
  "Dark Red": "#8B0000",
  "Orange": "#FFA500",
  "Dark Orange": "#FF8C00",
  "Brown": "#A52A2A",
  "Yellow": "#FFFF00",
  "Gold": "#FFD700",
  "Green": "#00FF00",
  "Dark Green": "#006400",
  "Lime": "#32CD32",
  "Olive": "#808000",
  "Blue": "#0000FF",
  "Light Blue": "#ADD8E6",
  "Sky Blue": "#87CEEB",
  "Dark Blue": "#00008B",
  "Cyan": "#00FFFF",
  "Teal": "#008080",
  "Magenta": "#FF00FF",
  "Purple": "#800080",
  "Violet": "#EE82EE",
  "Pink": "#FFC0CB",
  "Hot Pink": "#FF69B4",
  "Indigo": "#4B0082",
}

FONT_NAMES = [
  "Arial", "Arial Black", "Bahnschrift", "Bahnschrift Condensed", "Calibri", "Cambria", "Candara",
  "Comic Sans MS", "Consolas", "Courier New", "Franklin Gothic Medium", "Georgia", "Impact",
  "Lucida Console", "Lucida Sans Unicode", "Segoe UI", "Tahoma", "Times New Roman", "Trebuchet MS",
  "Verdana", "Palatino Linotype", "Book Antiqua", "Century Gothic", "Garamond",
  "Microsoft Sans Serif", "Symbol",
]

ALIGN_TAGS = {
  "Top Left": r"{\an7}", "Top Center": r"{\an8}", "Top Right": r"{\an9}",
  "Middle Left": r"{\an4}", "Middle Center": r"{\an5}", "Middle Right": r"{\an6}",
  "Bottom Left": r"{\an1}", "Bottom Center": r"{\an2}", "Bottom Right": r"{\an3}",
}


class SegmentListPanel(wx.Panel):
  def __init__(self, parent, output_box, announce_callback=None, on_update=None):
    super().__init__(parent)
    self.output_box = output_box
    self.announce_callback = announce_callback
    self.on_update = on_update

    self.undo_stack = []
    self.redo_stack = []

    self.edit_segment_id = wx.NewIdRef()
    self.remove_segment_id = wx.NewIdRef()
    self.remove_all_segments_id = wx.NewIdRef()
    self.remove_format_selected_id = wx.NewIdRef()
    self.remove_format_all_id = wx.NewIdRef()
    self.select_all_id = wx.NewIdRef()
    self.last_selected_indices = []
    self.align_shortcuts = {
  (wx.ACCEL_SHIFT, ord('R')): ("Top Right", r"{\an9}"),
  (wx.ACCEL_CTRL, ord('R')): ("Middle Right", r"{\an6}"),
  (wx.ACCEL_ALT, ord('R')): ("Bottom Right", r"{\an3}"),
  (wx.ACCEL_SHIFT, ord('E')): ("Top Center", r"{\an8}"),
  (wx.ACCEL_CTRL, ord('E')): ("Middle Center", r"{\an5}"),
  (wx.ACCEL_ALT, ord('E')): ("Bottom Center", r"{\an2}"),
  (wx.ACCEL_SHIFT, ord('L')): ("Top Left", r"{\an7}"),
  (wx.ACCEL_CTRL, ord('L')): ("Middle Left", r"{\an4}"),
  (wx.ACCEL_ALT, ord('L')): ("Bottom Left", r"{\an1}"),
}

    sizer = wx.BoxSizer(wx.VERTICAL)
    self.listbox = wx.ListBox(self, style=wx.LB_EXTENDED)
    self.listbox.Bind(wx.EVT_SET_FOCUS, self.on_listbox_focus)
    sizer.Add(self.listbox, 1, wx.EXPAND | wx.ALL, 5)
    self.SetSizer(sizer)

    self.save_state()

    self.listbox.Bind(wx.EVT_CONTEXT_MENU, self.on_right_click)
    self.setup_shortcuts()

  def setup_shortcuts(self):
    bold_id = wx.NewIdRef()
    italic_id = wx.NewIdRef()
    underline_id = wx.NewIdRef()
    undo_id = wx.NewIdRef()
    redo_id = wx.NewIdRef()

    entries = [
      wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('B'), bold_id),
      wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('I'), italic_id),
      wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('U'), underline_id),
      wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F2, self.edit_segment_id),
      wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_DELETE, self.remove_segment_id),
      wx.AcceleratorEntry(wx.ACCEL_SHIFT, wx.WXK_DELETE, self.remove_all_segments_id),
      wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_DELETE, self.remove_format_selected_id),
      wx.AcceleratorEntry(wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_DELETE, self.remove_format_all_id),
      wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('A'), self.select_all_id),
      wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('Z'), undo_id),
wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('Y'), redo_id),
    ]

    for (mod, key), (label, tag) in self.align_shortcuts.items():
      align_id = wx.NewIdRef()
      handler = partial(self.apply_alignment_tag, tag, label)
      self.Bind(wx.EVT_MENU, handler, id=align_id)
      entries.append(wx.AcceleratorEntry(mod, key, align_id))

    self.SetAcceleratorTable(wx.AcceleratorTable(entries))

    self.Bind(wx.EVT_MENU, lambda e: self.toggle_style("bold"), id=bold_id)
    self.Bind(wx.EVT_MENU, lambda e: self.toggle_style("italic"), id=italic_id)
    self.Bind(wx.EVT_MENU, lambda e: self.toggle_style("underline"), id=underline_id)
    self.Bind(wx.EVT_MENU, lambda e: self.edit_selected_segment(), id=self.edit_segment_id)
    self.Bind(wx.EVT_MENU, lambda e: self.remove_selected_items(), id=self.remove_segment_id)
    self.Bind(wx.EVT_MENU, lambda e: self.clear_all(), id=self.remove_all_segments_id)
    self.Bind(wx.EVT_MENU, lambda e: self.remove_format_selected("all"), id=self.remove_format_selected_id)
    self.Bind(wx.EVT_MENU, lambda e: self.select_all_segments(), id=self.select_all_id)
    self.Bind(wx.EVT_MENU, lambda e: self.restore_state(self.undo_stack, self.redo_stack, "Undo"), id=undo_id)
    self.Bind(wx.EVT_MENU, lambda e: self.restore_state(self.redo_stack, self.undo_stack, "Redo"), id=redo_id)
   
  def on_listbox_focus(self, event):
    if self.last_selected_indices:
      for i in range(self.listbox.GetCount()):
        self.listbox.Deselect(i)
      for idx in self.last_selected_indices:
        self.listbox.Select(idx)
      self.listbox.SetFirstItem(self.last_selected_indices[0])
      self.listbox.SetSelection(self.last_selected_indices[0])
    event.Skip()

  def edit_selected_segment(self):
    selections = self.listbox.GetSelections()
    if selections:
      self.last_selected_indices = selections
      self.edit_segment(selections[0])

  def remove_selected_items(self):
    selections = self.listbox.GetSelections()
    if not selections:
      return
    self.last_selected_indices = selections
    self.save_state()
    for index in reversed(selections):
      self.remove_item(index)
    if self.announce_callback:
      self.announce_callback("segment(s) removed")

  def remove_format_selected(self, fmt_type):
    selections = self.listbox.GetSelections()
    if not selections:
      return
    self.last_selected_indices = selections
    self.save_state()
    for index in selections:
      self.remove_format(index, fmt_type)
    if self.announce_callback:
      self.announce_callback("format removed from selected segment(s)")
    if self.last_selected_indices:
      self.listbox.SetFirstItem(self.last_selected_indices[0])
      self.listbox.SetSelection(self.last_selected_indices[0])

  def set_segments(self, lines):
    self.listbox.Clear()
    for line in lines:
      self.listbox.Append(str(line))

  def set_segments_from_objects(self, segments):
    lines = []
    for i, seg in enumerate(segments, start=1):
      start = format_srt_time(seg.start)
      end = format_srt_time(seg.end)
      text = seg.text.strip()
      line = f"{i}\n{start} --> {end}\n{text}"
      lines.append(line)
    self.set_segments(lines)

  def save_state(self):
    self.undo_stack.append(list(self.listbox.GetItems()))
    self.redo_stack.clear()

  def restore_state(self, stack_from, stack_to, action_name):
    if not stack_from:
      if self.announce_callback:
        self.announce_callback(f"nothing to {action_name.lower()}")
      return
    stack_to.append(list(self.listbox.GetItems()))
    state = stack_from.pop()
    self.set_segments(state)
    self.sync_output_box()
    if self.announce_callback:
      self.announce_callback(f"{action_name} performed")

  def on_right_click(self, event):
    selections = self.listbox.GetSelections()
    if not selections:
      return
    index = selections[0]

    menu = wx.Menu()

    edit_item = menu.Append(wx.ID_ANY, "Edit Segment")
    self.Bind(wx.EVT_MENU, lambda e: self.edit_segment(index), edit_item)

    menu.AppendSeparator()

    undo_item = menu.Append(wx.ID_ANY, "Undo")
    redo_item = menu.Append(wx.ID_ANY, "Redo")

    if not self.undo_stack:
      undo_item.Enable(False)
    if not self.redo_stack:
      redo_item.Enable(False)

    self.Bind(wx.EVT_MENU, lambda e: self.restore_state(self.undo_stack, self.redo_stack, "Undo"), undo_item)
    self.Bind(wx.EVT_MENU, lambda e: self.restore_state(self.redo_stack, self.undo_stack, "Redo"), redo_item)

    menu.AppendSeparator()
    select_all_item = menu.Append(wx.ID_ANY, "Select All Segments")
    self.Bind(wx.EVT_MENU, lambda e: self.select_all_segments(), select_all_item)

    remove_seg_menu = wx.Menu()
    remove_item = remove_seg_menu.Append(wx.ID_ANY, "Remove")
    self.Bind(wx.EVT_MENU, lambda e: self.remove_item(index), remove_item)
    remove_all = remove_seg_menu.Append(wx.ID_ANY, "Remove All")
    self.Bind(wx.EVT_MENU, lambda e: self.clear_all(), remove_all)
    menu.AppendSubMenu(remove_seg_menu, "Remove Segments")

    menu.AppendSeparator()

    alignment_menu = wx.Menu()
    for label, tag in ALIGN_TAGS.items():
      item = alignment_menu.Append(wx.ID_ANY, label)
      self.Bind(wx.EVT_MENU, lambda e, t=tag: self.apply_tag(index, tag=t, tag_type="align"), item)
    menu.AppendSubMenu(alignment_menu, "Alignment")

    font_main_menu = wx.Menu()
    font_name_menu = wx.Menu()
    for font_name in FONT_NAMES:
      item = font_name_menu.Append(wx.ID_ANY, font_name)
      self.Bind(wx.EVT_MENU, lambda e, f=font_name: self.apply_tag(index, tag=f, tag_type="font"), item)
    font_main_menu.AppendSubMenu(font_name_menu, "Font Name")

    font_color_menu = wx.Menu()
    for color_name, hex_code in COLOR_TAGS.items():
      item = font_color_menu.Append(wx.ID_ANY, color_name)
      self.Bind(wx.EVT_MENU, lambda e, c=hex_code: self.apply_tag(index, tag=c, tag_type="color"), item)
    font_main_menu.AppendSubMenu(font_color_menu, "Font Color")

    for style in STYLE_TAGS:
      item = font_main_menu.Append(wx.ID_ANY, style.capitalize())
      self.Bind(wx.EVT_MENU, lambda e, s=style: self.toggle_style(s, [index]), item)

    menu.AppendSubMenu(font_main_menu, "Font")

    remove_menu = wx.Menu()
    items = {
      "Remove Font Name": "font", "Remove Font Color": "color",
      "Remove Bold": "bold", "Remove Italic": "italic", "Remove Underline": "underline",
      "Remove Alignment": "align", "Remove All Formats (Selected Segment)": "all"
    }
    for label, fmt_type in items.items():
      item = remove_menu.Append(wx.ID_ANY, label)
      self.Bind(wx.EVT_MENU, lambda e, t=fmt_type: self.remove_format(index, t), item)

    all_seg_item = remove_menu.Append(wx.ID_ANY, "Remove All Formats (All Segments)")
    self.Bind(wx.EVT_MENU, self.remove_all_formats_all_segments, all_seg_item)

    menu.AppendSubMenu(remove_menu, "Remove Format")
    self.PopupMenu(menu)
    menu.Destroy()

  def edit_segment(self, index):
    if index == wx.NOT_FOUND:
      return
    selected_segment = self.listbox.GetString(index).strip()
    if not selected_segment:
      return
    all_text = self.output_box.GetValue()
    start_pos = all_text.find(selected_segment)
    if start_pos == -1:
      return
    end_pos = start_pos + len(selected_segment)
    self.output_box.SetFocus()
    self.output_box.SetSelection(start_pos, end_pos)

  def remove_item(self, index):
    self.listbox.Delete(index)
    self.sync_output_box()

  def clear_all(self):
    dlg = wx.MessageDialog(self, "Are you sure that you need to remove all segments?", "Confirm Remove All", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
    if dlg.ShowModal() == wx.ID_YES:
      self.listbox.Clear()
      self.sync_output_box()
    dlg.Destroy()

  def select_all_segments(self):
    count = self.listbox.GetCount()
    if count == 0:
      return
    for i in range(count):
      self.listbox.Select(i)
    self.listbox.SetSelection(0)
    self.listbox.SetFirstItem(0)
    self.listbox.SetFocus()
    if self.announce_callback:
      self.announce_callback("all segments selected")
    self.last_selected_indices = list(range(count))

  def toggle_style(self, style_key, indices=None):
    if indices is None:
      indices = self.listbox.GetSelections()
    if not indices:
      return
    self.last_selected_indices = indices

    tag = STYLE_TAGS[style_key]
    status_messages = []
    first_visible = self.listbox.GetTopItem()

    for index in indices:
      original = self.listbox.GetString(index)
      lines = original.strip().split("\n")
      if len(lines) < 3:
        continue

      number, timing, *text_lines = lines
      text = "\n".join(text_lines)

      if f"<{tag}>" in text and f"</{tag}>" in text:
        text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
        status = f"{style_key.capitalize()} off"
      else:
        text = f"<{tag}>{text}</{tag}>"
        status = f"{style_key.capitalize()} on"

      final_text = f"{number}\n{timing}\n{text}"
      self.listbox.SetString(index, final_text)
      status_messages.append(status)

    for i in range(self.listbox.GetCount()):
      self.listbox.Deselect(i)
    for sel in indices:
      self.listbox.Select(sel)

    self.listbox.SetFirstItem(first_visible)
    self.sync_output_box()
    self.listbox.SetFocus()

    if self.announce_callback and status_messages:
      self.announce_callback(status_messages[0])
    if self.last_selected_indices:
      self.listbox.SetFirstItem(self.last_selected_indices[0])
      self.listbox.SetSelection(self.last_selected_indices[0])

  def apply_alignment_tag(self, tag, label, event):
    selections = self.listbox.GetSelections()
    if not selections:
      return

    self.last_selected_indices = list(selections)
    first_visible = self.listbox.GetTopItem()
    focused_index = self.last_selected_indices[0] if self.last_selected_indices else wx.NOT_FOUND

    self.listbox.Freeze()

    for index in self.last_selected_indices:
      original = self.listbox.GetString(index)
      lines = original.strip().split("\n")
      if len(lines) < 3:
        continue

      number, timing, *text_lines = lines
      text = "\n".join(text_lines)

      match = re.search(r"{\\an\d}", text)
      current_alignment = match.group() if match else None

      if current_alignment == tag:
        text = text.replace(current_alignment, "")
        status = f"{label} alignment removed"
      else:
        text = re.sub(r"{\\an\d}", "", text)
        text = f"{tag}{text}"
        status = f"{label} alignment applied"

      final_text = f"{number}\n{timing}\n{text}"
      self.listbox.SetString(index, final_text)

    self.listbox.Thaw()

    for i in range(self.listbox.GetCount()):
      self.listbox.Deselect(i)
    for idx in self.last_selected_indices:
      self.listbox.Select(idx)

    if focused_index != wx.NOT_FOUND:
      wx.CallAfter(self.listbox.SetFirstItem, focused_index)
      wx.CallAfter(self.listbox.SetSelection, focused_index)
      wx.CallAfter(self.listbox.EnsureVisible, focused_index)
      wx.CallAfter(self.listbox.SetFocus)

    self.sync_output_box()

    if self.announce_callback and status:
      self.announce_callback(status)

  def apply_tag(self, index, tag, tag_type=None):
    self.last_selected_indices = [index]
    original = self.listbox.GetString(index)
    lines = original.strip().split("\n")
    if len(lines) < 3:
      return
    number, timing, *text_lines = lines
    text = "\n".join(text_lines)

    current_styles = set()
    for key, html_tag in STYLE_TAGS.items():
      if f"<{html_tag}>" in text:
        current_styles.add(key)

    font_name = None
    font_color = None

    match_name = re.search(r'face="([^"]+)"', text)
    if match_name:
      font_name = match_name.group(1)

    match_color = re.search(r'color="(#?[A-Fa-f0-9]{6})"', text)
    if match_color:
      font_color = match_color.group(1)

    if tag_type == "font":
      font_name = tag
    elif tag_type == "color":
      font_color = tag

    self.reapply_tags(index, font_name=font_name, font_color=font_color, styles=current_styles)

  def reapply_tags(
    self,
    index,
    *,
    align_tag=None,
    font_name=None,
    font_color=None,
    styles=None  # styles = set(["bold", "italic", "underline"])
  ):
    selections = self.listbox.GetSelections()
    was_focused = index

    original = self.listbox.GetString(index)
    lines = original.strip().split("\n")
    if len(lines) < 3:
      return

    number, timing, *text_lines = lines
    text = "\n".join(text_lines)

    text = re.sub(r"{\\an\d}", "", text)  # alignment
    text = re.sub(r"<font[^>]*?>", "", text).replace("</font>", "")  # font tag
    for tag in STYLE_TAGS.values():
      text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")

    open_tags = []
    close_tags = []

    font_attrs = []
    if font_name:
      font_attrs.append(f'face="{font_name}"')
    if font_color:
      font_attrs.append(f'color="{font_color}"')
    if font_attrs:
      open_tags.append(f'<font {" ".join(font_attrs)}>')
      close_tags.insert(0, '</font>')

    ordered_styles = ["bold", "italic", "underline"]
    for style in reversed(ordered_styles):
      if styles and style in styles:
        tag = STYLE_TAGS[style]
        open_tags.append(f"<{tag}>")
        close_tags.insert(0, f"</{tag}>")

    text = "".join(open_tags) + text + "".join(close_tags)

    if align_tag:
      text = f"{align_tag}{text}"

    final_text = f"{number}\n{timing}\n{text}"

    self.listbox.SetString(index, final_text)

    for i in range(self.listbox.GetCount()):
      self.listbox.Deselect(i)
    for sel in selections:
      self.listbox.Select(sel)

    self.listbox.SetFirstItem(was_focused)
    self.listbox.SetSelection(was_focused)

    self.listbox.Refresh()
    self.sync_output_box()
    self.listbox.SetFocus()
    if self.last_selected_indices:
      self.listbox.SetFirstItem(self.last_selected_indices[0])
      self.listbox.SetSelection(self.last_selected_indices[0])

  def remove_format(self, index, fmt_type):
    original = self.listbox.GetString(index)
    lines = original.strip().split("\n")
    if len(lines) < 3:
      return
    number, timing, *text_lines = lines
    text = "\n".join(text_lines)
    if fmt_type == "font":
      text = re.sub(r'face="[^"]+"', '', text)
    elif fmt_type == "color":
      text = re.sub(r'color="#?[A-Fa-f0-9]{6}"', '', text)
    elif fmt_type in STYLE_TAGS:
      tag = STYLE_TAGS[fmt_type]
      text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
      if fmt_type in self.active_styles:
        self.active_styles.remove(fmt_type)
    elif fmt_type == "align":
      text = re.sub(r"{\\an\d}", "", text)
    elif fmt_type == "all":
      text = re.sub(r"{\\an\d}", "", text)
      text = re.sub(r"<font[^>]*?>", "", text).replace("</font>", "")
      for tag in STYLE_TAGS.values():
        text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    text = re.sub(r'\s+', ' ', text).strip()
    self.listbox.SetString(index, f"{number}\n{timing}\n{text}")
    self.sync_output_box()

  def remove_all_formats_all_segments(self, event=None):
    dlg = wx.MessageDialog(self, "Are you sure you want to remove all formatting from all segments?", "Confirm", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
    if dlg.ShowModal() != wx.ID_YES:
      dlg.Destroy()
      return
    dlg.Destroy()
    self.save_state()
    for i in range(self.listbox.GetCount()):
      self.remove_format(i, "all")
    if self.announce_callback:
      self.announce_callback("format removed from all segments")

  def sync_output_box(self):
    full_text = "\n\n".join(self.listbox.GetItems())
    self.output_box.SetValue(full_text)
    if self.on_update:
      self.on_update()
