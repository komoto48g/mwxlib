#! python3
# -*- coding: utf-8 -*-
"""Template of Layer

Version: 1.0
Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import numpy as np
import cv2
import wx

from mwx.controls import Button, LParam
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    """Template layer
    """
    menukey = "Plugins/&Templates/"
    
    def Init(self):
        self.ksize = LParam("ksize", (1,99,2), 13) # "kernel window size"
        
        self.btn = Button(self, label="Run",
                          handler=lambda v: self.run(), icon='->')
        self.layout((
                self.ksize,
                self.btn,
            ),
            row=2, type='vspin', lw=30, tw=30
        )
    
    def run(self, N=2048):
        self.message("Processing randn...")
        k = self.ksize.value
        src = np.random.randn(N, N).astype(np.float32)
        dst = cv2.GaussianBlur(src, (k, k), 0)
        
        self.message("\b Loading...")
        self.graph.load(dst, name="*gauss*")
        
        self.message("\b ok")


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(Plugin, show=1)
    frm.Show()
    app.MainLoop()
