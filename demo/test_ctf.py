#! python3
# -*- coding: shift-jis -*-
from __future__ import (division, print_function,
                        absolute_import, unicode_literals)
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
        self.Df = LParam('df[nm]', (-500, 500, 0.1), 200.0, updater=self.sherzerf)
        self.Cs = LParam('cs[mm]', (-5, 5, 0.01), 0.0)
        self.layout(None, (
            self.Df,
            self.Cs,
            Button(self, "Run", lambda v: self.run()),
            ),
            type=None, style='button', lw=40, tw=40
        )
        self.run() # first drawing
    
    def sherzerf(self, lp):
        """Sherzer focus
        Defined as: sin(2*pi/3) = 0.866
        """
        cs = self.Cs.value * 1e6 # [mm --> nm]
        lp.std_value = np.sqrt(4/3 * cs * el)
        lp.reset()
    
    def run(self):
        ## X, Y = 10 * np.mgrid[-N:N,-N:N]/N
        r = 20 * np.arange(-N/2, N/2) / N
        X, Y = np.meshgrid(r, r)
        lu = 20 / N
        df = self.Df.value
        cs = self.Cs.value * 1e6 # [mm --> nm]
        
        def ctf(k):
            """CTF at k [nm-1]"""
            return sin(pi * (1/2 * cs * el**3 * k**4 - df * el * k**2))
        
        if 0:
            del self.Arts
            ## ax = self.graph.axes
            ## ax.grid(False)
            ## ax.spines['left'].set_position('center')
            ## ax.spines['bottom'].set_position('center')
            self.Arts = self.graph.axes.plot(r[N:], ctf(r[N:]), 'y-', lw=1)
        
        Z = ctf(np.hypot(X, Y))
        self.graph.load((255 * Z ** 2).astype(np.uint8), 'ctf', localunit=lu)


if __name__ == '__main__':
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, docking=4)
    frm.Show()
    app.MainLoop()