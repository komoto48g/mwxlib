#! python3
# -*- coding: utf-8 -*-
"""Template of Layer

Version: 1.0
Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import wx

from mwx.graphman import Frame

def _pack(items, orient=wx.HORIZONTAL):
    sizer = wx.BoxSizer(orient)
    sizer.AddMany(items)
    return sizer


@Frame.register
class Panel(wx.Panel):
    """Template panel
    """
    menukey = "Plugins/&Templates/"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        b1 = wx.Button(self, wx.ID_OK, "OK")
        b2 = wx.Button(self, wx.ID_CANCEL, "Exit")
        btn = wx.Button(self, label="Hello, wxPython!!")
        
        @btn.Bind(wx.EVT_BUTTON)
        def message(evt):
            wx.MessageBox(evt.EventObject.Label)
        
        self.SetSizer(
            _pack([
                (btn, 1, wx.EXPAND | wx.ALL, 2),
                _pack([
                        b1,
                        b2,
                    ]),
                ],
                orient=wx.VERTICAL
            )
        )
        self.Sizer.Fit(self)

if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(Panel, show=1)
    frm.Show()
    app.MainLoop()
