#! python3
import sys
import wx

sys.path.append("../Lib")
from mwx.controls import LParam, Gauge, Indicator
from mwx.graphman import Layer


class Plugin(Layer):
    menukey = "Plugins/&Demo/"
    
    def Init(self):
        self.g1 = wx.Gauge(self, range=24, size=(100,24))
        self.g2 = Gauge(self, range=24, size=(100,24))
        
        self.sig = Indicator(self, size=(-1,24))
        self.param = LParam("value", (0, 24, 1), 0, handler=self.update)
        self.blink = LParam("blink", (0, 1000, 10), 500)
        
        self.layout((
                self.g1, None,
                self.g2, None,
                self.param,
                (self.sig, 0),
                self.blink,
            ),
            row=2, expand=1,
            type='slider*', lw=40, tw=40, h=22,
        )
        self.timer = wx.Timer(self)
        self.timer.Start(1000)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
    
    def update(self, p):
        self.g1.Value = p.value
        self.g2.Value = p.value
        self.sig.Value = p.value
    
    def OnTimer(self, evt):
        self.sig.Value = self.param.value
        self.sig.blink(self.blink.value)
    
    def Destroy(self):
        try:
            self.timer.Stop()
        finally:
            return Layer.Destroy(self)


if __name__ == "__main__":
    from mwx.testsuite import *
    with Plugman() as frm:
        frm.load_plug(Plugin, show=1)
