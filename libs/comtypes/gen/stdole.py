from enum import IntFlag

import comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 as __wrapper_module__
from comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 import (
    FONTNAME, OLE_YSIZE_HIMETRIC, IPicture, Checked, HRESULT,
    IFontDisp, _lcid, OLE_XPOS_CONTAINER, OLE_ENABLEDEFAULTBOOL,
    Picture, FONTITALIC, FontEvents, FONTSTRIKETHROUGH,
    FONTUNDERSCORE, OLE_COLOR, IEnumVARIANT, OLE_XSIZE_CONTAINER,
    GUID, IPictureDisp, BSTR, OLE_XSIZE_PIXELS, OLE_HANDLE, EXCEPINFO,
    StdFont, dispid, OLE_YPOS_PIXELS, _check_version,
    OLE_YPOS_HIMETRIC, DISPPROPERTY, IFontEventsDisp, IFont, IUnknown,
    Gray, DISPMETHOD, OLE_YPOS_CONTAINER, Library, Monochrome,
    OLE_YSIZE_PIXELS, typelib_path, OLE_OPTEXCLUSIVE,
    OLE_XSIZE_HIMETRIC, OLE_XPOS_PIXELS, StdPicture,
    OLE_XPOS_HIMETRIC, OLE_YSIZE_CONTAINER, VARIANT_BOOL, FONTSIZE,
    DISPPARAMS, IDispatch, FONTBOLD, OLE_CANCELBOOL, VgaColor,
    Default, COMMETHOD, Unchecked, Color, CoClass, Font
)


class OLE_TRISTATE(IntFlag):
    Unchecked = 0
    Checked = 1
    Gray = 2


class LoadPictureConstants(IntFlag):
    Default = 0
    Monochrome = 1
    VgaColor = 2
    Color = 4


__all__ = [
    'FONTNAME', 'OLE_YSIZE_HIMETRIC', 'OLE_YPOS_HIMETRIC', 'IPicture',
    'Checked', 'IFontDisp', 'IFontEventsDisp', 'OLE_XPOS_CONTAINER',
    'IFont', 'OLE_ENABLEDEFAULTBOOL', 'Picture', 'Gray',
    'OLE_YPOS_CONTAINER', 'Library', 'Monochrome', 'FONTITALIC',
    'FontEvents', 'OLE_YSIZE_PIXELS', 'FONTSTRIKETHROUGH',
    'OLE_TRISTATE', 'typelib_path', 'FONTUNDERSCORE',
    'LoadPictureConstants', 'OLE_COLOR', 'OLE_OPTEXCLUSIVE',
    'OLE_XSIZE_HIMETRIC', 'OLE_XPOS_PIXELS', 'StdPicture',
    'OLE_XSIZE_CONTAINER', 'OLE_YPOS_PIXELS', 'OLE_XPOS_HIMETRIC',
    'OLE_YSIZE_CONTAINER', 'FONTSIZE', 'IPictureDisp',
    'OLE_XSIZE_PIXELS', 'FONTBOLD', 'OLE_HANDLE', 'OLE_CANCELBOOL',
    'VgaColor', 'StdFont', 'Default', 'Unchecked', 'Color', 'Font'
]

