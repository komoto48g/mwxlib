#! python3
# -*- coding: shift-jis -*-
import wx
import cv2
import numpy as np
from numpy import pi,sin
import mwx
from mwx.controls import LParam, Button
from mwx.graphman import Layer, Frame

N = 1024
el = 1.968758541778089e-3 # elambda [nm] at 300kV 

class Plugin(Layer):
    def Init(self):
        self.Df = LParam('df[nm]', (-500, 500, 0.1), 100.0, handler=self.run)
        self.Cs = LParam('cs[mm]', (-5, 5, 0.01), 0.0, handler=self.run)
        self.layout((
                self.Df,
                self.Cs,
                Button(self, "Run", self.run),
            ),
            type=None, style='button', lw=40, tw=40
        )
        self.run() # first drawing
    
    def run(self, *v):
        r = 20 * np.arange(-N/2, N/2) / N
        X, Y = np.meshgrid(r, r)
        lu = 20 / N
        df = self.Df.value
        cs = self.Cs.value * 1e6 # [mm --> nm]
        
        def ctf(k):
            """CTF at k [nm-1]"""
            return sin(pi * (1/2 * cs * el**3 * k**4 - df * el * k**2))
        
        if 1:
            ## ax = self.graph.axes
            ## ax.grid(False)
            ## ax.spines['left'].set_position('center')
            ## ax.spines['bottom'].set_position('center')
            self.Arts = self.graph.axes.plot(r[N:], ctf(r[N:]), 'y-', lw=1)
        
        Z = ctf(np.hypot(X, Y))
        self.graph.load((255 * Z ** 2).astype(np.uint8), 'ctf', localunit=lu)


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, dock=4)
    frm.Show()
    app.MainLoop()
