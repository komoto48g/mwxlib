#! python3
# -*- coding: utf-8 -*-
from __future__ import (division, print_function,
                        absolute_import, unicode_literals)
import time
import wx
from mwx.controls import Gauge
from mwx.graphman import Layer, Frame, Thread


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.g1 = wx.Gauge(self, range=24, size=(100,24))
        self.g2 = Gauge(self, range=24, size=(100,24), style=wx.BORDER_DOUBLE)
        
        self.layout(None, (
            self.g1,
            self.g2,
            ),
            expand=1,
        )
        self.g1.Value = 24
        self.g2.Value = 24


if __name__ == '__main__':
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, docking=4)
    frm.Show()
    app.MainLoop()
