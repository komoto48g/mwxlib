#! python3
# -*- coding: utf-8 -*-
import wx
from mwx.controls import LParam, Button, Gauge, Indicator
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.g1 = wx.Gauge(self, range=24, size=(100,24))
        self.g2 = Gauge(self, range=24, size=(100,24), style=wx.BORDER_DOUBLE)
        self.sig = Indicator(self, size=(-1,24))
        
        self.btn = Button(self, label="", icon="v")
        self.param = LParam("value", (0,self.g1.Range,1), 0)
        
        self.layout(None, (
            (self.btn, 0), self.g1,
            (self.sig, 0), self.g2,
            self.param,
            ),
            row=2, expand=1,
            type='slider*', style='button', tw=0, h=22
        )
        @self.param.bind
        def set(p):
            self.g1.Value = p.value
            self.g2.Value = p.value
            self.sig.Value = p.value


if __name__ == '__main__':
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, dock=4)
    frm.Show()
    app.MainLoop()
