#! python3
# -*- coding: utf-8 -*-
"""Template of Layer

Version: 1.0
Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import wx
import cv2
from mwx.controls import LParam
from mwx.graphman import Layer, Frame


class Plugin(Layer):
    """Plugin template ver.1
    """
    menu = "Plugins/&Template"
    menustr = "&template ver.1"
    category = "Test"
    caption = True
    
    def Init(self):
        self.ksize = LParam("ksize", (1,99,2), 13, tip="kernel window size")
        
        self.btn = wx.Button(self, label="Run", size=(-1,22))
        self.btn.Bind(wx.EVT_BUTTON, lambda v: self.run())
        
        self.layout(
            (self.ksize, self.btn),  # the list of objects stacked with the following style:
            title="Gaussian blur",   # subtitle of this layout group. otherwise None (no box)
            row=1, expand=0, show=1, # grouping style: row means the horizontal stack size
            type='vspin',            # control style: slider[*], [hv]spin, choice
            cw=-1, lw=36, tw=30      # w: width of [c]ontrol, [l]abel, [t]ext
        )
    
    def Destroy(self):
        return Layer.Destroy(self)
    
    def init_session(self, session):
        self.reset_params(session.get('params'))
    
    def save_session(self, session):
        session['params'] = self.parameters
    
    def run(self):
        k = self.ksize.value
        src = self.graph.buffer
        dst = cv2.GaussianBlur(src, (k,k), 0.)
        self.output.load(dst, name='*gauss*')


if __name__ == "__main__":
    app = wx.App()
    frm = Frame(None)
    frm.load_plug(__file__, show=1, dock=4)
    frm.load_buffer("./sample.bmp")
    frm.Show()
    app.MainLoop()
