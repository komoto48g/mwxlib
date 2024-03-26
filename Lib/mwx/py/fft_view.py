#! python3
"""View of FFT/iFFT.
"""
import wx
import numpy as np
from numpy.fft import fft2,ifft2,fftshift,ifftshift
## from scipy.fftpack import fft,ifft,fft2,ifft2 Memory Leak? <scipy 0.16.1>
## import cv2

from jgdk import Layer, Param
import editor as edi


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
        self.parent.define_key('C-f', None)
        self.parent.define_key('C-S-f', None)
        return Layer.Destroy(self)
    
    def newfft(self, evt):
        """New FFT of graph to output."""
        frame = self.graph.frame
        if frame:
            self.message("FFT execution...")
            src = edi.fftcrop(frame.roi)
            h, w = src.shape
            
            dst = fftshift(fft2(src))
            
            self.message("\b Loading image...")
            u = 1 / w
            if self.pchk.Value:
                u /= frame.unit
            self.output.load(dst, "*fft of {}*".format(frame.name),
                                  localunit=u)
            self.message("\b done")
    
    def newifft(self, evt):
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
