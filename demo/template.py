#! python3
"""Template of Layer.
"""
import cv2
import wx

from mwx.controls import LParam
from mwx.graphman import Layer


class Plugin(Layer):
    """Plugin template ver.1
    """
    menukey = "Plugins/&Templates/&template ver.1"
    category = "Test"
    caption = True

    def Init(self):
        self.ksize = LParam("ksize", (1,99,2), 13) # kernel window size
        
        self.btn = wx.Button(self, label="Run", size=(-1,22))
        self.btn.Bind(wx.EVT_BUTTON, lambda v: self.run())
        
        self.layout(
            (self.ksize, self.btn),  # the list of objects stacked with the following style:
            title="Gaussian blur",   # subtitle of this layout group. otherwise None (no box)
            row=1, expand=0, show=1, # grouping style: row means the horizontal stack size
            type='vspin',            # control type: slider[*], [hv]spin, choice
            style='chkbox',          # control style: None, chkbox, button
            cw=-1, lw=50, tw=30      # w: width of [c]ontrol, [l]abel, [t]ext
        )

    def run(self):
        k = self.ksize.value
        src = self.graph.buffer
        if src is None:
            self.message("- No buffer")
            return
        dst = cv2.GaussianBlur(src, (k, k), 0.)
        self.output.load(dst, name="*gauss*")


if __name__ == "__main__":
    from mwx.testsuite import *

    with testPlugin() as frm:
        frm.load_plug(Plugin, show=1)
