import sys
import os
import re
from functools import partial

libs_path = os.path.join(os.path.dirname(__file__), "libs")

wx_lib_path = os.path.join(libs_path, "wx")
if wx_lib_path not in sys.path:
  sys.path.insert(0, wx_lib_path)

import wx
from settings_utils import format_srt_time, format_segments_to_srt
from dialogs import FilterDialog, GoToDialog

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
    self.original_segments = []
    self.current_filters = None

    self.undo_stack = []
    self.redo_stack = []

    self.edit_segment_id = wx.NewIdRef()
    self.remove_segment_id = wx.NewIdRef()
    self.remove_all_segments_id = wx.NewIdRef()
    self.remove_format_selected_id = wx.NewIdRef()
    self.remove_format_all_id = wx.NewIdRef()
    self.select_all_id = wx.NewIdRef()
    self.last_selected_indices = []
    self.move_up_id = wx.NewIdRef()
    self.move_down_id = wx.NewIdRef()
    self.move_last_to_first_id = wx.NewIdRef()
    self.move_first_to_last_id = wx.NewIdRef()
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
      wx.AcceleratorEntry(wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_UP, self.move_up_id),
      wx.AcceleratorEntry(wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_DOWN, self.move_down_id),
      wx.AcceleratorEntry(wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_HOME, self.move_last_to_first_id),
      wx.AcceleratorEntry(wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_END, self.move_first_to_last_id),
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
    self.Bind(wx.EVT_MENU, self.move_segment_up, id=self.move_up_id)
    self.Bind(wx.EVT_MENU, self.move_segment_down, id=self.move_down_id)
    self.Bind(wx.EVT_MENU, self.move_last_to_first, id=self.move_last_to_first_id)
    self.Bind(wx.EVT_MENU, self.move_first_to_last, id=self.move_first_to_last_id)
   
  def on_listbox_focus(self, event):
    if self.last_selected_indices:
      listbox_count = self.listbox.GetCount()
    
      for i in range(listbox_count):
        self.listbox.Deselect(i)

      for idx in self.last_selected_indices:
        if 0 <= idx < listbox_count:
          self.listbox.Select(idx)

      first_valid_idx = next((i for i in self.last_selected_indices if 0 <= i < listbox_count), None)
      if first_valid_idx is not None:
        self.listbox.SetFirstItem(first_valid_idx)
        self.listbox.SetSelection(first_valid_idx)

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

  def reset(self):
    """Clear the current segment list and any selection."""
    self.listbox.Clear()
    self.listbox.SetSelection(wx.NOT_FOUND)
    self.segments = []

  def set_segments(self, lines):
    self.listbox.Clear()
    for line in lines:
      self.listbox.Append(str(line))
    if not self.current_filters:
      self.original_segments = list(lines)

  def set_segments_from_objects(self, segments):
    lines = []
    for i, seg in enumerate(segments, start=1):
      start = format_srt_time(seg.start)
      end = format_srt_time(seg.end)
      text = seg.text.strip()
      line = f"{i}\n{start} --> {end}\n{text}"
      lines.append(line)
    self.set_segments(lines)
    if not self.current_filters:
        self.original_segments = list(lines)

  def renumber_and_set_segments(self, lines):
    updated_lines = []
    for i, line in enumerate(lines, start=1):
      parts = line.strip().split("\n")
      if len(parts) < 3:
        updated_lines.append(line)
        continue
      _, timing, *text_lines = parts
      updated_text = "\n".join(text_lines)
      updated_lines.append(f"{i}\n{timing}\n{updated_text}")
    self.set_segments(updated_lines)

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

    edit_item = menu.Append(self.edit_segment_id, "Edit Segment\tF2")
    self.Bind(wx.EVT_MENU, lambda e: self.edit_segment(index), edit_item)

    menu.AppendSeparator()

    undo_item = menu.Append(wx.ID_ANY, "Undo\tCtrl+Z")
    redo_item = menu.Append(wx.ID_ANY, "Redo\tCtrl+Y")

    if not self.undo_stack:
      undo_item.Enable(False)
    if not self.redo_stack:
      redo_item.Enable(False)

    self.Bind(wx.EVT_MENU, lambda e: self.restore_state(self.undo_stack, self.redo_stack, "Undo"), undo_item)
    self.Bind(wx.EVT_MENU, lambda e: self.restore_state(self.redo_stack, self.undo_stack, "Redo"), redo_item)

    menu.AppendSeparator()
    select_all_item = menu.Append(self.select_all_id, "Select All Segments\tCtrl+A")
    self.Bind(wx.EVT_MENU, lambda e: self.select_all_segments(), select_all_item)

    remove_seg_menu = wx.Menu()
    remove_item = remove_seg_menu.Append(self.remove_segment_id, "Remove\tDelete")
    self.Bind(wx.EVT_MENU, lambda e: self.remove_item(index), remove_item)
    remove_all = remove_seg_menu.Append(self.remove_all_segments_id, "Remove All\tShift+Delete")
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
    move_menu = wx.Menu()
    move_up_item = move_menu.Append(self.move_up_id, "Move Segment Up\tAlt+Shift+Up")
    move_down_item = move_menu.Append(self.move_down_id, "Move Segment Down\tAlt+Shift+Down")
    move_last_to_first_item = move_menu.Append(self.move_last_to_first_id, "Move Last Segment to First\tAlt+Shift+Home")
    move_first_to_last_item = move_menu.Append(self.move_first_to_last_id, "Move First Segment to Last\tAlt+Shift+End")

    self.Bind(wx.EVT_MENU, self.move_segment_up, move_up_item)
    self.Bind(wx.EVT_MENU, self.move_segment_down, move_down_item)
    self.Bind(wx.EVT_MENU, self.move_last_to_first, move_last_to_first_item)
    self.Bind(wx.EVT_MENU, self.move_first_to_last, move_first_to_last_item)

    menu.AppendSubMenu(move_menu, "Move Segments")
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

  def apply_go_to(self, target_segment=None, range_start=None, range_end=None, exclusions=None):
    total_segments = self.listbox.GetCount()
    self.listbox.SetFocus()

    if target_segment is None and range_start is None and range_end is None:
      wx.MessageBox(
        "Segment Number cannot be empty.",
        "Input Required",
        wx.OK | wx.ICON_WARNING
      )
      return

    if target_segment is not None:
      if 1 <= target_segment <= total_segments:
        index = target_segment - 1
        for i in range(total_segments):
          self.listbox.Deselect(i)
        self.listbox.SetSelection(index)
        self.listbox.SetFirstItem(index)
        self.last_selected_indices = [index]
        if self.announce_callback:
          self.announce_callback(f"focused segment {target_segment}")
      else:
        wx.MessageBox(
          f"The segment number {target_segment} does not exist.",
          "Segment Not Found",
          wx.OK | wx.ICON_ERROR
        )
        return

    if (range_start is not None and range_end is None) or (range_start is None and range_end is not None):
      wx.MessageBox(
        "Both 'Start From' and 'End To' fields must be filled to select a range.",
        "Incomplete Range",
        wx.OK | wx.ICON_WARNING
      )
      return

    if range_start is not None and range_end is not None:
      if not (1 <= range_start <= total_segments):
        wx.MessageBox(
          f"The 'Start From' value {range_start} is out of range (must be between 1 and {total_segments}).",
          "Invalid Start",
          wx.OK | wx.ICON_ERROR
        )
        return

      if not (1 <= range_end <= total_segments):
        wx.MessageBox(
          f"The 'End To' value {range_end} is out of range (must be between 1 and {total_segments}).",
          "Invalid End",
          wx.OK | wx.ICON_ERROR
        )
        return

      if range_start > range_end:
        range_start, range_end = range_end, range_start

      for i in range(total_segments):
        self.listbox.Deselect(i)

      selections = []
      for i in range(range_start - 1, range_end):
        if exclusions and (i + 1) in exclusions:
          continue
        self.listbox.Select(i)
        selections.append(i)

      if selections:
        self.listbox.SetFirstItem(selections[0])
        self.listbox.SetSelection(selections[0])
        self.last_selected_indices = selections
        if self.announce_callback:
          self.announce_callback(f"selected segments {range_start} to {range_end} with exclusions")
      else:
        wx.MessageBox(
          "No segments were selected. All items may have been excluded.",
          "No Segments Selected",
          wx.OK | wx.ICON_INFORMATION
        )

  def move_segment_up(self, event):
    selections = self.listbox.GetSelections()
    if not selections or selections[0] == 0:
      return
    self.save_state()
    i = selections[0]
    above = i - 1
    items = self.listbox.GetItems()
    items[i], items[above] = items[above], items[i]
    self.renumber_and_set_segments(items)
    self.listbox.Select(above)
    self.last_selected_indices = [above]
    self.sync_output_box()
    if self.announce_callback:
      self.announce_callback("segment moved up")

  def move_segment_down(self, event):
    selections = self.listbox.GetSelections()
    if not selections or selections[0] == self.listbox.GetCount() - 1:
      return
    self.save_state()
    i = selections[0]
    below = i + 1
    items = self.listbox.GetItems()
    items[i], items[below] = items[below], items[i]
    self.renumber_and_set_segments(items)
    self.listbox.Select(below)
    self.last_selected_indices = [below]
    self.sync_output_box()
    if self.announce_callback:
      self.announce_callback("segment moved down")

  def move_last_to_first(self, event):
    count = self.listbox.GetCount()
    if count < 2:
      return
    self.save_state()
    items = self.listbox.GetItems()
    items[0], items[-1] = items[-1], items[0]
    self.renumber_and_set_segments(items)
    self.listbox.Select(0)
    self.last_selected_indices = [0]
    self.sync_output_box()
    if self.announce_callback:
      self.announce_callback("last segment moved to first")

  def move_first_to_last(self, event):
    count = self.listbox.GetCount()
    if count < 2:
      return
    self.save_state()
    items = self.listbox.GetItems()
    items[0], items[-1] = items[-1], items[0]
    self.renumber_and_set_segments(items)
    self.listbox.Select(count - 1)
    self.last_selected_indices = [count - 1]
    self.sync_output_box()
    if self.announce_callback:
      self.announce_callback("first segment moved to last")

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

    align_match = re.search(r"{\\an\d}", text)
    align_tag = align_match.group() if align_match else None

    self.reapply_tags(
      index,
      align_tag=align_tag,
      font_name=font_name,
      font_color=font_color,
      styles=current_styles
    )

  def reapply_tags(
    self,
    index,
    *,
    align_tag=None,
    font_name=None,
    font_color=None,
    styles=None
  ):
    selections = self.listbox.GetSelections()
    was_focused = index

    original = self.listbox.GetString(index)
    lines = original.strip().split("\n")
    if len(lines) < 3:
      return

    number, timing, *text_lines = lines
    text = "\n".join(text_lines)

    text = re.sub(r"{\\an\d}", "", text)
    text = re.sub(r"<font[^>]*?>", "", text).replace("</font>", "")
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

    formatted_text = "".join(open_tags) + text + "".join(close_tags)

    if align_tag:
      formatted_text = f"{align_tag}{formatted_text}"

    final_text = f"{number}\n{timing}\n{formatted_text}"

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


  def apply_filters(self, filters):
    segments = list(self.original_segments)
    if not segments:
      return

    self.current_filters = filters

    selected_styles = filters.get("styles", [])
    selected_alignments = filters.get("alignments", [])
    recent_only = filters.get("recent", False)

    filter_by_word = filters.get("filter_by_word", False)
    case_sensitive = filters.get("case_sensitive", False)
    word_query = filters.get("word_query", "").strip()

    def match_style(text):
      for style in selected_styles:
        tag = STYLE_TAGS.get(style.lower())
        if tag and f"<{tag}>" in text and f"</{tag}>" in text:
          continue
        else:
          return False
      return True if selected_styles else True

    def match_alignment(text):
      for align in selected_alignments:
        tag = ALIGN_TAGS.get(align)
        if tag and tag not in text:
          return False
      return True if selected_alignments else True

    def match_recent(index):
      if not recent_only:
        return True
      return index in self.last_selected_indices

    def match_word(text):
      if not filter_by_word or not word_query:
        return True

      query = re.sub(r'\s+', ' ', word_query.strip())
      text_to_check = re.sub(r'\s+', ' ', text.strip())

      if not case_sensitive:
        query = query.lower()
        text_to_check = text_to_check.lower()

      return query in text_to_check

    filtered = []
    for i, seg in enumerate(segments):
      lines = seg.strip().split("\n")
      if len(lines) < 3:
        continue
      _, _, *text_lines = lines
      text = "\n".join(text_lines)
      if (
        match_style(text)
        and match_alignment(text)
        and match_recent(i)
        and match_word(text)
      ):
        filtered.append(seg.strip())

    if (
      not selected_styles
      and not selected_alignments
      and not recent_only
      and not filter_by_word
    ):
      self.set_segments(self.original_segments)
    else:
      self.set_segments(filtered)

    self.sync_output_box()
