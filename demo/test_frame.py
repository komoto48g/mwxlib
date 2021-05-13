#! python
# -*- coding: shift-jis -*-
"""Test of framework
"""
from __future__ import (division, print_function,
                        absolute_import, unicode_literals)
import wx
import mwx


if __name__ == "__main__":
    app = wx.App()
    frm = mwx.Frame(None, pos=(0,0))
    frm.Title = repr(frm)
    frm.panel = mwx.Editor(frm)
    ## frm.panel = mwx.Nautilus(frm, target=frm)
    frm.Show()
    app.MainLoop()
