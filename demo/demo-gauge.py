#! python
# -*- coding: utf-8 -*-
import time
import wx
from mwx.controls import Gauge
from mwx.graphman import Layer, Frame, Thread


class Plugin(Layer):
    def Init(self):
        self.g1 = wx.Gauge(self, range=100, size=(100,24))
        self.g2 = Gauge(self, range=24, size=(100,24), style=wx.BORDER_DOUBLE)
        
        self.layout(None, (
            self.g1,
            self.g2,
            ),
            expand=1,
        )
        self.thread = Thread(self)
        self.thread.Start(self.count)
    
    def count(self):
        while 1:
            for x in range(0,24):
                self.g2.Value = x
                time.sleep(0.1)
                if not self.thread.is_active:
                    return


if __name__ == '__main__':
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, docking=4)
    frm.Show()
    app.MainLoop()
