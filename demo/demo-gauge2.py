#! python3
# -*- coding: utf-8 -*-
from __future__ import (division, print_function,
                        absolute_import, unicode_literals)
import time
import wx
from mwx.controls import Gauge, LParam
from mwx.graphman import Layer, Frame, Thread


class Plugin(Layer):
    menu = "Plugins/&Demo"
    
    def Init(self):
        self.g1 = wx.Gauge(self, range=24, size=(100,24))
        self.g2 = Gauge(self, range=24, size=(100,24), style=wx.BORDER_DOUBLE, tip="raibow gauge")
        
        self.param = LParam("value", (0,24,1), 0, tip="slider")
        
        self.layout(None, (
            self.g1,
            self.g2,
            self.param,
            ),
            row=1, expand=1, hspacing=1, vspacing=1, show=1, visible=1,
            type='slider*', style='chkbox', lw=-1, tw=0, cw=-1, h=22
        )
        
        @self.param.bind
        def set(p):
            self.g1.Value = p.value
            self.g2.Value = p.value
        
        @self.param.bind(target='check')
        def check(p):
            def start():
                x = 0
                while self.thread.is_active:
                    p.reset(x % 24) # update control
                    time.sleep(0.1)
                    x += 1
            if p.check:
                self.thread.Start(start)
            else:
                self.thread.Stop()
        self.thread = Thread(self)


if __name__ == '__main__':
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, dock=4)
    frm.Show()
    app.MainLoop()
