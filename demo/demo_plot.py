#! python3
import sys
import wx
import numpy as np
from numpy import pi,exp,sin,cos

sys.path.append("../Lib")
from mwx.controls import LParam
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    menukey = "Plugins/&Demo/"
    
    def Init(self):
        axes = self.graph.axes
        ## axes.clear()
        axes.set_title("Nautilus")
        axes.set_xlabel("x")
        axes.set_ylabel("y")
        axes.grid(True)
        axes.axis((-2, 2, -2, 2))
        axes.set_aspect(1)
        
        self.A = LParam('A', (0, 1, 0.01), 0.5, handler=self.run)
        self.B =  LParam('B', (0, 0.1, 0.001), 0.05, handler=self.run)
        
        self.layout((
                self.A,
                self.B,
            ),
            title="Params",
            expand=0, show=1,
            type='slider*', cw=100, lw=20, tw=40, h=22,
        )
        self.run(None)
    
    def run(self, lp):
        a = self.A.value
        b = self.B.value
        t = np.arange(0, 10.01, 0.01) * 2*pi
        r = a * exp(b * t)
        x = r * cos(t)
        y = r * sin(t)
        self.Arts = self.graph.axes.plot(x, y, 'y-', lw=1)
        self.graph.canvas.draw()


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(Plugin, show=1, dock=4)
    frm.Show()
    app.MainLoop()
