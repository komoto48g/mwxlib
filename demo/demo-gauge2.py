#! python
# -*- coding: utf-8 -*-
import time
import wx
import mwx
from mwx.controls import Gauge, LParam
from mwx.graphman import Layer, Frame, Thread


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.g1 = wx.Gauge(self, range=24, size=(100,24))
        self.g2 = Gauge(self, range=24, size=(100,24), style=wx.BORDER_DOUBLE)
        
        self.param = LParam("value", (0,24,1), 0)
        
        self.layout(None, (
            self.g1,
            self.g2,
            self.param,
            ),
            row=1, expand=1, hspacing=1, vspacing=1, show=1, visible=1,
            type='slider*', style='button', lw=-1, tw=0, cw=-1, h=22
        )
        
        @self.param.bind
        def set(p):
            self.g1.Value = p.value
            self.g2.Value = p.value
        
        @self.param.bind(target='check')
        def check(p):
            def start():
                while 1:
                    for x in range(0,24):
                        p.reset(x)
                        time.sleep(0.1)
                        if not self.thread.is_active:
                            return
            self.thread.Start(start)
        self.thread = Thread(self)


if __name__ == '__main__':
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, docking=4)
    frm.Show()
    app.MainLoop()
