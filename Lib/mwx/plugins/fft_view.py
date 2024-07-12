#! python3
"""View of FFT/iFFT.
"""
import wx
import numpy as np
from numpy.fft import fft2,ifft2,fftshift,ifftshift

from mwx.graphman import Layer
from mwx.controls import Param


def fftcrop(src):
    """Crop src image in 2**N square ROI centered at (x, y)."""
    h, w = src.shape
    m = min(h, w)
    n = 1 if m < 2 else 2 ** int(np.log2(m) - 1) # +-m/2
    x, y = w//2, h//2
    return src[y-n:y+n, x-n:x+n]


class Plugin(Layer):
    """FFT view.
    
    FFT src (graph.buffer) to dst (output.buffer).
    Note:
        Rectangular regions will result in distorted patterns.
        長方形のリージョンは歪んだパターンになるので要注意
    """
    menukey = "Plugins/Extensions/&FFT view"
    caption = "FFT view"
    
    def Init(self):
        self.pchk = wx.CheckBox(self, label="logical unit")
        self.pchk.Value = True
        
        self.ftor = Param("mask", (2,4,8,16,32,64)) # masking area factor of 1/2
        
        self.layout((self.pchk,), title="normal FFT")
        self.layout((self.ftor,), title="inverse FFT", style='chkbox', tw=32)
        
        self.parent.define_key('C-f', self.newfft)
        self.parent.define_key('C-S-f', self.newifft)
    
    def Destroy(self):
        self.parent.undefine_key('C-f')
        self.parent.undefine_key('C-S-f')
        return Layer.Destroy(self)
    
    def newfft(self):
        """New FFT of graph to output."""
        frame = self.graph.frame
        if frame:
            self.message("FFT execution...")
            src = fftcrop(frame.roi)
            h, w = src.shape
            
            dst = fftshift(fft2(src))
            
            self.message("\b Loading image...")
            u = 1 / w
            if self.pchk.Value:
                u /= frame.unit
            self.output.load(dst, "*fft of {}*".format(frame.name),
                                  localunit=u)
            self.message("\b done")
    
    def newifft(self):
        """New inverse FFT of output to graph."""
        frame = self.output.frame
        if frame:
            self.message("iFFT execution...")
            src = frame.roi
            h, w = src.shape
            
            if self.ftor.check:
                y, x = np.ogrid[-h/2:h/2, -w/2:w/2]
                mask = np.hypot(y,x) > w / self.ftor.value
                src = src.copy() # apply mask to the copy
                src[mask] = 0
            
            dst = ifft2(ifftshift(src))
            
            self.message("\b Loading image...")
            self.graph.load(dst.real, "*ifft of {}*".format(frame.name),
                                      localunit=1/w/frame.unit)
            self.message("\b done")
