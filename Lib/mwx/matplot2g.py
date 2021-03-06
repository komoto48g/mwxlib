#! python3
# -*- coding: utf-8 -*-
"""mwxlib graph for image

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
import traceback
import sys
import wx
try:
    import framework as mwx
    from utilus import funcall as _F
    from matplot2 import MatplotPanel
    from matplot2 import NORMAL, DRAGGING, PAN, ZOOM, MARK, LINE, REGION
except ImportError:
    from . import framework as mwx
    from .utilus import funcall as _F
    from .matplot2 import MatplotPanel
    from .matplot2 import NORMAL, DRAGGING, PAN, ZOOM, MARK, LINE, REGION
from matplotlib import cm
from matplotlib import patches
from PIL import Image
from PIL import ImageFile
import cv2
import numpy as np
from numpy import pi, nan
from scipy import ndimage as ndi


def imbuffer(img):
    if isinstance(img, (Image.Image, ImageFile.ImageFile)):
        ## return np.asarray(img) # ref
        return np.array(img) # copy
    
    if isinstance(img, wx.Bitmap):
        img = img.ConvertToImage()
    
    if isinstance(img, wx.Image):
        w, h = img.GetSize()
        buf = np.frombuffer(img.GetDataBuffer(), dtype='uint8')
        return buf.reshape(h, w, 3)
    return img


def imconvert(src, cutoff=0, threshold=24e6, binning=1):
    """Convert buffer to dst<uint8> := (src-a) * 255/(b-a)
    
cf. convertScaleAbs(src[, dst[, alpha[, beta]]]) -> dst
      dst<uint8> := |src * alpha + beta| ... abs.value
        alpha = 255 / (b-a)
         beta = -a * alpha
    
    cutoff : cutoff score percentiles cuts the upper/lower limits given by the tolerances [%]
 threshold : limit bytes of image (to make matplotlib light)
   binning : minimum binning number of src array
    """
    if src.dtype in (np.complex64, np.complex128): # maybe fft pattern
        src = np.log(1 + abs(src))
    
    bins = binning
    if threshold:
        ## Converted to <uint8(=1byte)> finally, binning should be reduced by itemsize.
        n = int(np.sqrt(src.nbytes / threshold / src.itemsize)) + 1
        if bins < n:
            bins = n # binning or threshold; Select the larger one.
    
    if bins > 1:
        ## cv2.resize accepts uint8, uint16, float32, and float64 only..
        if src.dtype in (np.uint32, np.int32): src = src.astype(np.float32)
        if src.dtype in (np.uint64, np.int64): src = src.astype(np.float64)
        
        ## src = src[::bins,::bins]
        src = cv2.resize(src, None, fx=1/bins, fy=1/bins, interpolation=cv2.INTER_AREA)
    
    if src.dtype == np.uint8:
        return bins, (0,255), src
    
    if hasattr(cutoff, '__iter__'):
        a, b = cutoff
    elif cutoff > 0:
        a = np.percentile(src, cutoff)
        b = np.percentile(src, 100-cutoff)
    else:
        a = src.min()
        b = src.max()
    
    r = (255 / (b - a)) if a < b else 1
    ## img = cv2.convertScaleAbs(src, alpha=r, beta=-r*a) # ????????????????????????????????????????????????
    img = np.uint8((src - a) * r) # copy buffer
    img[src < a] = 0
    img[src > b] = 255
    return bins, (a,b), img


def _Property(name):
    return property(
        lambda self:   getattr(self.parent, name),
        lambda self,v: setattr(self.parent, name, v),
        lambda self:   delattr(self.parent, name))


class AxesImagePhantom(object):
    """Phantom of frame facade
    
    Args:
            buf : buffer
           name : buffer name
           show : show immediately when loaded
         aspect : initial aspect ratio <float>
      localunit : initial localunit
     attributes : additional info:dict
    
    Attributes:
           unit : logical length per pixel arb.unit [u/pixel]
          image : image <numpy.ndarray> (dtype:uint8)
         buffer : raw buffer <numpy.ndarray>
        binning : binning size of image
                  ( ????????)? Current verision of wxagg limits < 24M bytes?
                  The image pixel size must be reduced by resizing or binning.
     attributes : optional. miscellaneous info about the frame/buffer
       pathname : optional. fullpath of buffer, when bounds to file
     annotation : optional. annotation of the buffer
    """
    def __init__(self, parent, buf, name, show=True,
                 localunit=None, aspect=1.0, **attributes):
        self.__owner = parent
        self.__name = name
        self.__localunit = localunit or None # [+] value, no assertion
        self.__aspect_ratio = aspect
        self.__attributes = attributes
        self.__attributes['localunit'] = self.__localunit
        self.__buf = imbuffer(buf)
        bins, vlim, img = imconvert(self.__buf,
                cutoff = self.parent.score_percentile,
             threshold = self.parent.nbytes_threshold,
        )
        self.__bins = bins
        self.__vlim = vlim
        self.__art = parent.axes.imshow(img,
                  cmap = cm.gray,
                aspect = 'equal',
         interpolation = 'nearest',
               visible = show,
                picker = True,
        )
        self.update_extent() # this determines the aspect ratio
    
    def __getattr__(self, attr):
        return getattr(self.__art, attr)
    
    def __eq__(self, x):
        return x is self.__art
    
    parent = property(lambda self: self.__owner)
    artist = property(lambda self: self.__art)
    name = property(lambda self: self.__name)
    image = property(lambda self: self.__art.get_array())
    buffer = property(lambda self: self.__buf)
    binning = property(lambda self: self.__bins)
    vlim = property(lambda self: self.__vlim)
    
    clim = property(
        lambda self: self.__art.get_clim(),
        lambda self,v: self.__art.set_clim(v))
    
    attributes = property(lambda self: self.__attributes)
    
    pathname = property(
        lambda self: self.__attributes.get('pathname'),
        lambda self,v: self.update_attributes({'pathname': v}))
    
    annotation = property(
        lambda self: self.__attributes.get('annotation', ''),
        lambda self,v: self.update_attributes({'annotation': v}))
    
    def update_attributes(self, attr=None, **kwargs):
        """Update frame-specifc attributes
        The frame holds any attributes with dictionary
        There are some keys which acts as the value setter when given,
        `annotation` also shows the message with infobar
        `localunit` also updates the frame.unit
        """
        attr = attr or {}
        attr.update(kwargs)
        self.__attributes.update(attr)
        
        if 'localunit' in attr:
            self.unit = attr['localunit']
        
        if 'pathname' in attr:
            self.parent.handler('frame_updated', self)
        
        if 'annotation' in attr:
            v = attr['annotation']
            if self.parent.frame is self:
                self.parent.infobar.ShowMessage(v)
            self.parent.handler('frame_updated', self)
    
    selector = _Property('Selector')
    markers = _Property('Markers')
    region = _Property('Region')
    
    @name.setter
    def name(self, v):
        self.__name = v
        self.parent.handler('frame_updated', self)
    
    @property
    def localunit(self):
        return self.__localunit
    
    @property
    def unit(self):
        return self.__localunit or self.parent.globalunit
    
    @unit.setter
    def unit(self, v):
        u = self.unit
        if v in (None, nan):
            v = self.parent.globalunit
            self.__localunit = None
        elif v <= 0:
            raise Exception("The unit value must be greater than zero.")
        else:
            if v == self.__localunit: # no effect when v is localunit
                return
            self.__localunit = v
        self.__attributes['localunit'] = self.__localunit
        self.update_extent()
        self.parent.update_markup_ratio(v/u)
        self.parent.handler('frame_updated', self)
    
    @unit.deleter
    def unit(self):
        self.unit = None
    
    @property
    def xy_unit(self):
        u = self.__localunit or self.parent.globalunit
        return (u, u * self.__aspect_ratio)
    
    @property
    def aspect_ratio(self):
        """aspect ratio of logical unit"""
        return self.__aspect_ratio
    
    @aspect_ratio.setter
    def aspect_ratio(self, v):
        if v == self.__aspect_ratio:
            return
        self.__aspect_ratio = v or 1.0
        self.update_extent()
        self.parent.handler('frame_updated', self)
    
    @property
    def index(self):
        """self page number in the parent book"""
        return self.parent.index(self)
    
    def update_buffer(self, buf=None):
        """Update buffer and the image"""
        if buf is not None:
            self.__buf = imbuffer(buf)
        
        bins, vlim, img = imconvert(self.__buf,
                cutoff = self.parent.score_percentile,
             threshold = self.parent.nbytes_threshold,
        )
        self.__bins = bins
        self.__vlim = vlim
        self.__art.set_array(img)
        self.parent.handler('frame_modified', self)
    
    def update_extent(self):
        """Update logical extent of the image"""
        h, w = self.__buf.shape[:2]
        ux, uy = self.xy_unit
        w *= ux/2
        h *= uy/2
        self.__art.set_extent((-w,w,-h,h))
    
    @property
    def roi(self):
        """buffer in ROI (region of interest)"""
        if self.parent.Region.size:
            nx, ny = self.xytopixel(self.parent.Region)
            sx = slice(max(0,nx[0]), nx[1]) # nx slice
            sy = slice(max(0,ny[1]), ny[0]) # ny slice ?????? (??????)
            return self.__buf[sy,sx]
        return self.__buf
    
    @roi.setter
    def roi(self, v):
        self.roi[:] = v # cannot broadcast input array into different shape
        self.update_buffer()
    
    @buffer.setter
    def buffer(self, v):
        self.update_buffer(v)
    
    def xytoc(self, x, y=None, nearest=True):
        """Convert xydata (x,y) -> data[(x,y)] value of neaerst pixel
        if nearest is False, retval is interpolated with spline
        """
        h, w = self.__buf.shape[:2]
        nx, ny = self.xytopixel(x, y, cast=nearest)
        ## if np.any((nx<0) | (nx>=w) | (ny<0) | (ny>=h)):
        if np.any(nx<0) or np.any(nx>=w) or np.any(ny<0) or np.any(ny>=h):
            return
        if nearest:
            return self.__buf[ny, nx] # nearest value
        return ndi.map_coordinates(self.__buf, np.vstack([ny, nx])) # spline value
    
    def xytopixel(self, x, y=None, cast=True):
        """Convert xydata (x,y) -> [ny,nx] pixel (cast to integer)"""
        def pixel_cast(n):
            """Convert pixel-based length to pixel number"""
            return np.int32(np.floor(np.round(n, 1)))
        if y is None:
            x, y = x
        if not isinstance(x, np.ndarray): x = np.array(x)
        if not isinstance(y, np.ndarray): y = np.array(y)
        l,r,b,t = self.__art.get_extent()
        ux, uy = self.xy_unit
        nx = (x - l) / ux
        ny = (t - y) / uy # Y ??????????????????????????????????????????
        if cast:
            return (pixel_cast(nx), pixel_cast(ny))
        return (nx-0.5, ny-0.5)
    
    def xyfrompixel(self, nx, ny=None):
        """Convert pixel [nx,ny] -> (x,y) xydata (float number)"""
        if ny is None:
            nx, ny = nx
        if not isinstance(nx, np.ndarray): nx = np.array(nx)
        if not isinstance(ny, np.ndarray): ny = np.array(ny)
        l,r,b,t = self.__art.get_extent()
        ux, uy = self.xy_unit
        x = l + (nx + 0.5) * ux
        y = t - (ny + 0.5) * uy # Y ??????????????????????????????????????????
        return (x, y)


class Clipboard:
    """Clipboard interface of images
    
    This does not work unless wx.App exists.
    The clipboard data cannot be transferred unless wx.Frame exists.
    """
    verbose = True
    
    @staticmethod
    def imread():
        try:
            do = wx.BitmapDataObject()
            wx.TheClipboard.Open() or print("- Unable to open the clipboard")
            wx.TheClipboard.GetData(do)
            bmp = do.GetBitmap()
            img = bmp.ConvertToImage()
            buf = np.array(img.GetDataBuffer()) # do copy, don't ref
            if Clipboard.verbose:
                print("From clipboard {:.1f} Mb data".format(buf.nbytes/1e6))
            w, h = img.GetSize()
            return buf.reshape(h, w, 3)
        finally:
            wx.TheClipboard.Close()
    
    @staticmethod
    def imwrite(buf):
        try:
            h, w = buf.shape[:2]
            if buf.ndim < 3:
                ## buf = np.array([buf] * 3).transpose((1,2,0)) # convert to gray bitmap
                buf = buf.repeat(3, axis=1)
            img = wx.Image(w, h, buf.tobytes())
            bmp = img.ConvertToBitmap()
            do = wx.BitmapDataObject(bmp)
            wx.TheClipboard.Open() or print("- Unable to open the clipboard")
            wx.TheClipboard.SetData(do)
            if Clipboard.verbose:
                print("To clipboard: {:.1f} Mb data".format(buf.nbytes/1e6))
        finally:
            wx.TheClipboard.Close()


class GraphPlot(MatplotPanel):
    """Graph panel for 2D graph
    
    Attributes:
           axes : a figure axes <matplotlib.axes.Axes>
          frame : current art <matplotlib.image.AxesImage>
         buffer : current data array <numpy.ndarray>; complex is not supported.
          image : current image array <numpy.ndarray>; uint8
           unit : logical length per pixel arb.unit [u/pixel]
            roi : current buffer in ROI (region of interest)
    
    Aritists:
       Selector : selected points array ([x],[y])
        Markers : marked points data array ([x],[y])
         Region : rectangle points data array ((l,r),(b,t))
    
    Constants:
    nbytes_threshold : image size threshold (for display)
    score_percentile : image cutoff percentiles
    """
    def __init__(self, *args, **kwargs):
        MatplotPanel.__init__(self, *args, **kwargs)
        
        def draw_idle(v):
            self.canvas.draw_idle()
        
        self.handler.update({ # DNA<GraphPlot>
            None : {
                  'frame_shown' : [ None ], # show
                 'frame_hidden' : [ None ], # show
                 'frame_loaded' : [ None ], # load
                'frame_removed' : [ None ], # del[] ! event arg is indices, not frames.
               'frame_selected' : [ None ], # = focus_set
             'frame_deselected' : [ None ], # = focus_kill
               'frame_modified' : [ None ], # set[],load,roi, (frame.update_buffer)
               #'frame_updated' : [ None ], # unit,name,ratio (frame.update_extent)
                'frame_updated' : [ None, _F(self.writeln) ],
                'frame_cmapped' : [ None ], # cmap
                    'line_draw' : [ None ],
                   'line_drawn' : [ None, draw_idle ],
                    'line_move' : [ None ],
                   'line_moved' : [ None, draw_idle ],
                 'line_removed' : [ None, draw_idle ],
                    'mark_draw' : [ None ],
                   'mark_drawn' : [ None, draw_idle ],
                 'mark_removed' : [ None, draw_idle ],
                  'region_draw' : [ None ],
                 'region_drawn' : [ None, draw_idle ],
               'region_removed' : [ None, draw_idle ],
            },
            NORMAL : {
                 'image_picked' : (NORMAL, self.OnImagePicked),
                  'line_picked' : (LINE, self.OnLineSelected),
                  'mark_picked' : (MARK, self.OnMarkSelected),
                'region_picked' : (REGION, self.OnRegionSelected),
                    'c pressed' : (MARK, self.OnMarkAppend),
                    'r pressed' : (REGION, self.OnRegionAppend, self.OnEscapeSelection),
            'r+Lbutton pressed' : (REGION, self.OnRegionAppend, self.OnEscapeSelection),
            'M-Lbutton pressed' : (REGION, self.OnRegionAppend, self.OnEscapeSelection),
               'escape pressed' : (NORMAL, self.OnEscapeSelection, draw_idle),
                'shift pressed' : (NORMAL, self.on_picker_lock),
               'shift released' : (NORMAL, self.on_picker_unlock),
              'Lbutton pressed' : (NORMAL, self.OnDragLock),
            'S-Lbutton pressed' : (NORMAL, self.OnDragLock, self.OnSelectorAppend),
                 '*Ldrag begin' : (NORMAL+DRAGGING, self.OnDragBegin),
                 'M-up pressed' : (NORMAL, self.OnPageUp),
               'M-down pressed' : (NORMAL, self.OnPageDown),
               'pageup pressed' : (NORMAL, self.OnPageUp),
             'pagedown pressed' : (NORMAL, self.OnPageDown),
                 'home pressed' : (NORMAL, _F(self.select, j=0)),
                  'end pressed' : (NORMAL, _F(self.select, j=-1)),
                  'M-a pressed' : (NORMAL, _F(self.fit_to_canvas)),
                  'C-a pressed' : (NORMAL, _F(self.update_axis)),
                  'C-c pressed' : (NORMAL, _F(self.write_buffer_to_clipboard)),
                  'C-v pressed' : (NORMAL, _F(self.read_buffer_from_clipboard)),
                  'C-k pressed' : (NORMAL, _F(self.kill_buffer)),
                'C-S-k pressed' : (NORMAL, _F(self.kill_buffer_all)),
                  'C-i pressed' : (NORMAL, _F(self.invert_cmap)),
            },
            NORMAL+DRAGGING : {
                         'quit' : (NORMAL, ),
                    'r pressed' : (REGION+DRAGGING, self.OnRegionAppend, self.OnRegionDragBegin, self.OnEscapeSelection),
                  'alt pressed' : (REGION+DRAGGING, self.OnRegionAppend, self.OnRegionDragBegin, self.OnEscapeSelection),
               'escape pressed' : (NORMAL+DRAGGING, self.OnDragEscape),
                 'S-Ldrag move' : (NORMAL+DRAGGING, self.OnDragShiftMove),
                  '*Ldrag move' : (NORMAL+DRAGGING, self.OnDragMove),
                   '*Ldrag end' : (NORMAL, self.OnDragEnd),
            },
            LINE : {
                 'image_picked' : (NORMAL, self.OnLineDeselected),
                  'line_picked' : (LINE, self.OnLineSelected),
                  'mark_picked' : (MARK, self.OnLineDeselected, self.OnMarkSelected),
                'region_picked' : (REGION, self.OnLineDeselected, self.OnRegionSelected),
                    'c pressed' : (MARK, self.OnMarkAppend),
                    'r pressed' : (REGION, self.OnRegionAppend, self.OnEscapeSelection),
                   'up pressed' : (LINE, self.OnLineShift),
                 'down pressed' : (LINE, self.OnLineShift),
                 'left pressed' : (LINE, self.OnLineShift),
                'right pressed' : (LINE, self.OnLineShift),
                  'up released' : (LINE, self.OnLineShiftEnd),
                'down released' : (LINE, self.OnLineShiftEnd),
                'left released' : (LINE, self.OnLineShiftEnd),
               'right released' : (LINE, self.OnLineShiftEnd),
               'escape pressed' : (NORMAL, ),
               'delete pressed' : (NORMAL, self.OnEscapeSelection),
                'space pressed' : (PAN, self.OnPanBegin),
                 'ctrl pressed' : (PAN, self.OnPanBegin),
                    'z pressed' : (ZOOM, self.OnZoomBegin),
              'Rbutton pressed' : (LINE, self.on_menu_lock),
             'Rbutton released' : (LINE, self.on_menu),
                 '*Ldrag begin' : (LINE+DRAGGING, self.OnLineDragBegin),
            },
            LINE+DRAGGING : {
                         'quit' : (LINE, ),
               'escape pressed' : (LINE, self.OnLineDragEscape),
                 'S-Ldrag move' : (LINE+DRAGGING, self.OnLineDragShiftMove),
                  '*Ldrag move' : (LINE+DRAGGING, self.OnLineDragMove),
                   '*Ldrag end' : (LINE, self.OnLineDragEnd),
            },
            MARK : {
                 'image_picked' : (NORMAL, self.OnMarkDeselected, self.OnImagePicked),
                  'line_picked' : (LINE, self.OnMarkDeselected, self.OnLineSelected),
                  'mark_picked' : (MARK, self.OnMarkSelected),
                'region_picked' : (REGION, self.OnMarkDeselected, self.OnRegionSelected),
                   'up pressed' : (MARK, self.OnMarkShift),
                 'down pressed' : (MARK, self.OnMarkShift),
                 'left pressed' : (MARK, self.OnMarkShift),
                'right pressed' : (MARK, self.OnMarkShift),
                  'up released' : (MARK, self.OnMarkShiftEnd),
                'down released' : (MARK, self.OnMarkShiftEnd),
                'left released' : (MARK, self.OnMarkShiftEnd),
               'right released' : (MARK, self.OnMarkShiftEnd),
                    'n pressed' : (MARK, self.OnMarkSkipNext),
                    'p pressed' : (MARK, self.OnMarkSkipPrevious),
               'escape pressed' : (NORMAL, self.OnMarkDeselected, draw_idle),
               'delete pressed' : (MARK, self.OnMarkRemove),
                'space pressed' : (PAN, self.OnPanBegin),
                 'ctrl pressed' : (PAN, self.OnPanBegin),
                    'z pressed' : (ZOOM, self.OnZoomBegin),
                 '*Ldrag begin' : (MARK+DRAGGING, self.OnMarkDragBegin),
              'Rbutton pressed' : (MARK, self.on_menu_lock),
             'Rbutton released' : (MARK, self.on_menu),
            },
            MARK+DRAGGING : {
                         'quit' : (MARK, ),
               'escape pressed' : (MARK, self.OnMarkDragEscape),
                  '*Ldrag move' : (MARK+DRAGGING, self.OnMarkDragMove),
                   '*Ldrag end' : (MARK, self.OnMarkDragEnd),
            },
            REGION : {
                 'image_picked' : (NORMAL, self.OnRegionDeselected, self.OnImagePicked),
                  'line_picked' : (LINE, self.OnRegionDeselected, self.OnLineSelected),
                  'mark_picked' : (MARK, self.OnRegionDeselected, self.OnMarkSelected),
                'region_picked' : (REGION, self.OnRegionSelected),
                  'axes motion' : (REGION, self.OnRegionMotion),
                   'up pressed' : (REGION, self.OnRegionShift),
                 'down pressed' : (REGION, self.OnRegionShift),
                 'left pressed' : (REGION, self.OnRegionShift),
                'right pressed' : (REGION, self.OnRegionShift),
                  'up released' : (REGION, self.OnRegionShiftEnd),
                'down released' : (REGION, self.OnRegionShiftEnd),
                'left released' : (REGION, self.OnRegionShiftEnd),
               'right released' : (REGION, self.OnRegionShiftEnd),
               'escape pressed' : (NORMAL, self.OnRegionDeselected, draw_idle),
               'delete pressed' : (NORMAL, self.OnRegionRemove),
                'space pressed' : (PAN, self.OnPanBegin),
                 'ctrl pressed' : (PAN, self.OnPanBegin),
                    'z pressed' : (ZOOM, self.OnZoomBegin),
                 '*Ldrag begin' : (REGION+DRAGGING, self.OnRegionDragBegin),
              'Rbutton pressed' : (REGION, self.on_menu_lock),
             'Rbutton released' : (REGION, self.on_menu),
            },
            REGION+DRAGGING : {
                         'quit' : (REGION, ),
               'escape pressed' : (REGION, self.OnRegionDragEscape),
                 'S-Ldrag move' : (REGION+DRAGGING, self.OnRegionDragShiftMove),
               'M-S-Ldrag move' : (REGION+DRAGGING, self.OnRegionDragMetaMove),
                 'M-Ldrag move' : (REGION+DRAGGING, self.OnRegionDragMetaMove),
                  '*Ldrag move' : (REGION+DRAGGING, self.OnRegionDragMove),
                   '*Ldrag end' : (REGION, self.OnRegionDragEnd),
            },
        })
        
        def _Icon(key):
            return wx.ArtProvider.GetBitmap(key, size=(16,16))
        
        self.menu += [
            (),
            (wx.ID_COPY, "&Copy buffer\t(C-c)", "Copy buffer to clipboard", _Icon(wx.ART_COPY),
                lambda v: self.write_buffer_to_clipboard(),
                lambda v: v.Enable(self.frame is not None)),
                
            (wx.ID_PASTE, "&Paste buffer\t(C-v)", "Paste from clipboard", _Icon(wx.ART_PASTE),
                lambda v: self.read_buffer_from_clipboard()),
            (),
            (mwx.ID_(510), "&Invert Color", "Invert colormap", wx.ITEM_CHECK,
                lambda v: self.invert_cmap(),
                lambda v: v.Check(self.get_cmap()[-2:] == "_r")),
            (),
            (wx.ID_CLOSE, "&Kill buffer\t(C-k)", "Kill buffer", _Icon(wx.ART_DELETE),
                lambda v: self.kill_buffer(),
                lambda v: v.Enable(self.frame is not None)),
                
            (wx.ID_CLOSE_ALL, "&Kill all buffer\t(C-S-k)", "Kill buffers", _Icon(wx.ART_DELETE),
                lambda v: self.kill_buffer_all(),
                lambda v: v.Enable(self.frame is not None)),
        ]
        
        ## modeline menu: ????????????????????????????????????????????????
        def _menu(j, s):
            return (j, s, s, wx.ITEM_CHECK,
                lambda v: self.select(s),
                lambda v: v.Check(self.frame is not None and self.frame.name == s))
        
        self.modeline.Bind(wx.EVT_CONTEXT_MENU, lambda v:
            mwx.Menu.Popup(self,
                (_menu(j, art.name) for j, art in enumerate(self.__Arts))))
        
        self.modeline.Show(1)
        self.Layout()
    
    def clear(self):
        MatplotPanel.clear(self)
        
        self.__Arts = []
        self.__index = None
        
        ## cf. self.figure.dpi = 80dpi (0.3175mm/pixel)
        self.__unit = 1.0
        
        #<matplotlib.lines.Line2D>
        (self.marked,) = self.axes.plot([], [], "r+", ms=8, mew=1,
                                        picker=True, pickradius=4)
        self.__marksel = []
        self.__markarts = []
        self.marked.set_pickradius(8) # for backward compatibility
        self.marked.set_clip_on(False)
        
        #<matplotlib.lines.Line2D>
        (self.rected,) = self.axes.plot([], [], "r+--", ms=4, lw=3/4,
                                        picker=True, pickradius=4, alpha=0.8)
        self.__rectsel = []
        self.__rectarts = []
        self.rected.set_pickradius(4) # for backward compatibility
        self.rected.set_clip_on(False)
        
        self.__isPicked = None
        self.selected.set_picker(True)
        self.selected.set_pickradius(8)
        self.selected.set_clip_on(False)
    
    def get_uniqname(self, name):
        base = name = name or "*temp*"
        i = 1
        while name in self:
            i += 1
            name = "{}({:d})".format(base, i)
        return name
    
    def load(self, buf, name=None, pos=None, show=True,
             localunit=None, aspect=1.0, **attributes):
        if buf is None:
            return
        
        if name in self: # existing frame
            j = self.index(name)
            art = self.__Arts[j]
            art.update_buffer(buf)      # => frame_modified
            art.update_extent()         # => ?
            art.unit = localunit        # => frame_updated
            art.aspect_ratio = aspect   # => frame_updated
            art.update_attributes(attributes) # => frame_updated?
            if show:
                self.select(j)
            return art
        
        name = self.get_uniqname(name)
        
        ## ?????????????????? axes.imshow (=> self.axes.axis ?????????????????????)
        art = AxesImagePhantom(self, buf, name, show, localunit, aspect, **attributes)
        
        j = len(self) if pos is None else pos
        self.__Arts.insert(j, art)
        self.handler('frame_loaded', art)
        if show:
            self.select(j)
        return art
    
    def select(self, j):
        if isinstance(j, (str, AxesImagePhantom)): # given name:str or frame:art
           j = self.index(j)
           if j is None:
               return
        
        for art in self.__Arts: # ?????????????????????????????????????????????
            art.set_visible(0)
        
        if j != self.__index and self.__index is not None:
            self.handler('frame_hidden', self.frame)
        
        if j is not None:
            u = self.frame and self.frame.unit
            try:
                self.__Arts[j].set_visible(1)
                self.__index = j % len(self)
                self.handler('frame_shown', self.frame)
            except Exception as e:
                self.message("- error in select: {}".format(e))
                return
            
            ## ???????????????????????????????????????????????????????????????
            if u != self.frame.unit:
                ## self.update_axis()
                self.axes.axis(self.frame.get_extent())
        else:
            self.__index = None
        
        self.draw()
        self.writeln()
        self.trace_point(*self.Selector, type=NORMAL)
        
        return self.frame
    
    def __getitem__(self, j):
        if isinstance(j, str):
            return self.__getitem__(self.index(j))
        
        buffers = [art.buffer for art in self.__Arts]
        if isinstance(j, list):
            return [buffers[i] for i in j]
        
        return buffers[j] # j can also be slicing
    
    def __setitem__(self, j, v):
        if isinstance(j, str):
            try:
                return self.__setitem__(self.index(j), v) # overwrite buffer
            except Exception:
                return self.load(v, name=j) # new buffer
        
        if isinstance(j, (slice, list)):
            raise ValueError("attempt to assign buffers into slice")
        
        if v is None:
            self.__delitem__(j)
        else:
            art = self.__Arts[j]
            art.update_buffer(v)
            art.update_extent()
            self.select(j)
    
    def __delitem__(self, j):
        if isinstance(j, str):
            return self.__delitem__(self.index(j))
        
        if isinstance(j, list):
            arts = [self.__Arts[i] for i in j]
        elif isinstance(j, slice):
            arts = self.__Arts[j]
        else:
            arts = [self.__Arts[j]]
        
        if arts:
            indices = [art.index for art in arts] # frames to be removed
            for art in arts:
                art.remove()
                self.__Arts.remove(art)
            self.handler('frame_removed', indices)
            
            j = self.__index
            if j is not None:
                n = len(self)
                self.__index = None if n==0 else j if j<n else n-1
            self.select(self.__index)
    
    ## __len__ ??? bool() ??????????????????????????????????????????????????????????????????????????????????????? (PY2)
    ## __nonzero__ : bool() ???????????????????????????????????? (PY2)
    
    def __len__(self):
        return len(self.__Arts)
    
    def __nonzero__(self):
        return True
    
    def __bool__(self):
        return True
    
    def __contains__(self, j):
        if isinstance(j, str):
            return j in (art.name for art in self.__Arts)
        else:
            return j in self.__Arts
    
    def index(self, j):
        if isinstance(j, str):
            ## return next(i for i,art in enumerate(self.__Arts) if art.name == j)
            names = [art.name for art in self.__Arts]
            return names.index(j) # -> ValueError: `j` is not in list
        return self.__Arts.index(j)
    
    def find_frame(self, j):
        if isinstance(j, str):
            return next((art for art in self.__Arts if art.name == j), None)
        return self.__Arts[j]
    
    ## --------------------------------
    ## Property of frame / drawer
    ## --------------------------------
    
    ## image bytes max when loading matplotlib wxagg backend
    nbytes_threshold = 24e6
    
    ## cutoff score percentiles
    score_percentile = 0.01
    
    @property
    def all_frames(self):
        """list of arts <matplotlib.image.AxesImage>"""
        return self.__Arts
    
    @property
    def frame(self):
        """current art <matplotlib.image.AxesImage>"""
        if self.__Arts and self.__index is not None:
            return self.__Arts[self.__index]
    
    buffer = property(
        lambda self: self.frame and self.frame.buffer,
        lambda self,v: self.__setitem__(self.__index, v),
        lambda self: self.__delitem__(self.__index),
        doc = "current buffer array")
    
    newbuffer = property(
        lambda self: None,
        lambda self,v: self.load(v),
        doc = "new buffer loader")
    
    @property
    def unit(self):
        """logical length per pixel arb.unit [u/pixel]"""
        return self.__unit
    
    @unit.setter
    def unit(self, v):
        if v in (None, nan):
            raise Exception("The globalunit must be non-nil value.")
        elif v <= 0:
            raise Exception("The unit value must be greater than zero.")
        else:
            if v == self.__unit:  # no effect unless unit changes
                return
            u = self.__unit
            self.__unit = v
            for art in self.__Arts:
                art.update_extent()
            else:
                self.update_markup_ratio(v/u)
            for art in self.__Arts:
                self.handler('frame_updated', art)
    
    globalunit = unit
    
    def update_markup_ratio(self, r):
        """Modify markup objects position"""
        if self.Selector.size: self.Selector *= r
        if self.Markers.size: self.Markers *= r
        if self.Region.size: self.Region *= r
        self.draw()
        self.writeln()
        
    def kill_buffer(self):
        if self.buffer is not None:
            del self.buffer
    
    def kill_buffer_all(self):
        del self[:]
    
    def update_axis(self):
        """Reset display range (xylim's), update home position"""
        if self.frame:
            self.axes.axis(self.frame.get_extent()) # reset xlim and ylim
            self.update_position()
            self.draw()
    
    def fit_to_canvas(self):
        """fit display range (xylim's) to canvas"""
        x, y = self.xlim, self.ylim
        w, h = self.canvas.GetSize()
        r = h/w
        u = (y[1] - y[0]) / (x[1] - x[0])
        if u > r:
            cx = (x[1] + x[0]) / 2
            dx = (y[1] - y[0]) / 2 / r
            self.xlim = cx-dx, cx+dx
        else:
            cy = (y[1] + y[0]) / 2
            dy = (x[1] - x[0]) / 2 * r
            self.ylim = cy-dy, cy+dy
        self.draw()
    
    def on_focus_set(self, evt):
        """Called when focus is set (override)"""
        MatplotPanel.on_focus_set(self, evt)
        if self.frame:
            self.handler('frame_selected', self.frame)
    
    def on_focus_kill(self, evt):
        """Called when focus is killed (override)"""
        MatplotPanel.on_focus_kill(self, evt)
        if self.frame:
            self.handler('frame_deselected', self.frame)
            self.on_picker_lock(evt)
    
    def get_cmap(self):
        if self.frame:
            return self.frame.get_cmap().name
        return ''
    
    def set_cmap(self, name):
        if self.frame:
            self.frame.set_cmap(name)
            self.handler('frame_cmapped', self.frame)
            self.draw()
            self.writeln()
    
    def invert_cmap(self):
        if self.frame:
            name = self.frame.get_cmap().name
            self.set_cmap(name + "_r" if name[-2:] != "_r" else name[:-2])
    
    def trace_point(self, x, y, type=None):
        """Puts (override) a message of points x and y"""
        if self.frame:
            if not hasattr(x, '__iter__'): # called from OnMotion
                nx, ny = self.frame.xytopixel(x, y)
                z = self.frame.xytoc(x, y)
                self.message("[{:-4d}, {:-4d}]"
                    " ({:-8.3f}, {:-8.3f}) value: {}".format(nx, ny, x, y, z))
                return
            
            if len(x) == 0: # no selection
                return
            
            if len(x) == 1: # 1-Selector trace point (called from Marker:setter)
                return self.trace_point(x[0], y[0], type)
            
            if len(x) == 2: # 2-Selector trace line (called from Selector:setter)
                nx, ny = self.frame.xytopixel(x, y)
                dx = x[1] - x[0]
                dy = y[1] - y[0]
                a = np.arctan2(dy, dx) * 180/pi
                lu = np.hypot(dy, dx)
                li = np.hypot(nx[1]-nx[0], ny[1]-ny[0])
                self.message("[Line] "
                    "Length: {:.1f} pixel ({:g}u) "
                    "Angle: {:.1f} deg".format(li, lu, a))
                
            elif type == REGION: # N-Selector trace polygon (called from Region:setter)
                nx, ny = self.frame.xytopixel(x, y)
                xo, yo = min(nx), min(ny) # top-left
                xr, yr = max(nx), max(ny) # bottom-right
                self.message("[Region] "
                    "Shape: [{0:4d}, {1:4d}] "
                    "crop={0}:{1}:{2}:{3}".format(xr-xo, yr-yo, xo, yo)) # (W:H:left:top)
    
    def writeln(self):
        """Puts (override) attributes of current frame to the modeline"""
        if not self.modeline.IsShown():
            return
        if self.frame:
            self.modeline.write(
            "[{page}/{maxpage}] -{a}- {name} ({data.dtype}:{cmap}{bins}) "
            "[{data.shape[1]}:{data.shape[0]}] {x} [{unit:g}/pixel]".format(
                page = self.__index,
             maxpage = len(self),
                name = self.frame.name,
                data = self.frame.buffer,
                cmap = self.frame.get_cmap().name,
                bins = ' bin{}'.format(self.frame.binning) if self.frame.binning > 1 else '',
                unit = self.frame.unit,
                   x = '**' if self.frame.localunit else '--',
                   a = '%%' if not self.frame.buffer.flags.writeable else '--'))
        else:
            self.modeline.write(
            "[{page}/{maxpage}] ---- No buffer (-:-) [-:-] -- [{unit:g}/pixel]".format(
                page = '-',
             maxpage = len(self),
                unit = self.__unit))
    
    ## --------------------------------
    ## ????????????????????????????????????????????????
    ## --------------------------------
    ## GraphPlot ?????????????????????????????????
    clipboard_name = None
    clipboard_data = None
    
    def write_buffer_to_clipboard(self):
        """Copy - Write buffer data to clipboard"""
        if not self.frame:
            self.message("No frame")
            return
        try:
            self.message("Write buffer to clipboard")
            name = self.frame.name
            data = self.frame.roi
            GraphPlot.clipboard_name = name
            GraphPlot.clipboard_data = data
            bins, vlim, img = imconvert(data, self.frame.vlim, threshold=None)
            Clipboard.imwrite(img)
        except Exception as e:
            self.message("- Failure in clipboard: {}".format(e))
            traceback.print_exc()
    
    def read_buffer_from_clipboard(self):
        """Paste - Read buffer data from clipboard"""
        try:
            name = GraphPlot.clipboard_name
            data = GraphPlot.clipboard_data
            if name:
                self.message("Read buffer from clipboard")
                self.load(data)
                GraphPlot.clipboard_name = None
                GraphPlot.clipboard_data = None
            else:
                self.message("Read image from clipboard")
                self.load(Clipboard.imread())
        except Exception as e:
            self.message("- No data in clipboard: {}".format(e))
            traceback.print_exc()
    
    def create_colorbar(self):
        """make colorbar
        The colorbar is plotted in self.figure.axes[1] (second axes)
        """
        from mpl_toolkits.axes_grid1 import make_axes_locatable
        if self.frame:
            divider = make_axes_locatable(self.axes)
            cax = divider.append_axes('right', size=0.1, pad=0.1)
            cbar = self.figure.colorbar(self.frame, cax=cax)
            @self.handler.bind('frame_cmapped')
            @self.handler.bind('frame_shown')
            def update_cmap(frame):
                cbar.update_normal(frame)
                cbar.draw_all()
                self.canvas.draw_idle()
            update_cmap(self.frame)
        else:
            self['*dummy*'] = np.random.rand(2,2) # dummy
            self.create_colorbar()
            del self['*dummy*']
    
    ## --------------------------------
    ## matplotlib interfaces
    ## --------------------------------
    
    def on_pick(self, evt): #<matplotlib.backend_bases.PickEvent>
        """Pickup image and other arts
        Called (maybe) after mouse buttons are pressed.
        """
        ## canvas ??????????????????????????????????????? axes (colorbar ????????????) ?????????
        ## image ??? plot ??????????????????????????????plot -> image ???????????????????????????
        ##  ?????????????????????????????????????????? isPicked ??????????????????????????????
        
        if evt.mouseevent.button != 1 or not evt.artist.get_visible():
            return
        
        if not evt.mouseevent.inaxes:
            return
        
        ## ??????????????????????????????
        if evt.artist in self.__Arts:
            if self.__isPicked:
                self.__isPicked = None # release pick guard
            else:
                self.handler('image_picked', evt)
            
        ## ????????????????????????????????????????????????
        else:
            if evt.artist is self.marked:
                self.__isPicked = 'mark' # image pick gurad
                self.handler('mark_picked', evt)
                
            elif evt.artist is self.rected:
                self.__isPicked = 'region' # image pick gurad
                self.handler('region_picked', evt)
                
            elif evt.artist is self.selected:
                if (self.Selector.shape[1] < 2      # single selector
                  or wx.GetKeyState(wx.WXK_SHIFT)): # or polygon mode
                    return
                self.__isPicked = 'line' # image pick gurad
                self.handler('line_picked', evt)
            else:
                self.__isPicked = 'art'
                MatplotPanel.on_pick(self, evt) # [art_picked]
        self.canvas.draw_idle()
    
    def on_picker_lock(self, evt):
        self.__isPicked = True
    
    def on_picker_unlock(self, evt):
        self.__isPicked = False
    
    def OnImagePicked(self, evt): #<matplotlib.backend_bases.PickEvent>
        x = evt.mouseevent.xdata
        y = evt.mouseevent.ydata
        nx, ny = self.frame.xytopixel(x, y)
        x, y = self.frame.xyfrompixel(nx, ny)
        evt.ind = (ny, nx)
        self.Selector = (x, y)
    
    def _inaxes(self, evt):
        try:
            return evt.inaxes is not self.axes #<matplotlib.backend_bases.MouseEvent>
        except AttributeError:
            return None #<wx._core.KeyEvent>
    
    ## --------------------------------
    ## Pan/Zoom actions (override)
    ## --------------------------------
    ## antialiased, nearest, bilinear, bicubic, spline16,
    ## spline36, hanning, hamming, hermite, kaiser, quadric,
    ## catrom, gaussian, bessel, mitchell, sinc, lanczos, or none
    interpolation_mode = 'bilinear'
    
    def OnDraw(self, evt):
        """Called before canvas.draw (overridden)"""
        if not self.interpolation_mode:
            return
        if self.frame:
            ## [dots/pixel] = [dots/u] * [u/pixel]
            dots = self.ddpu[0] * self.frame.unit * self.frame.binning
            
            if self.frame.get_interpolation() == 'nearest' and dots < 1:
                self.frame.set_interpolation(self.interpolation_mode)
                
            elif self.frame.get_interpolation() != 'nearest' and dots > 1:
                self.frame.set_interpolation('nearest')
    
    def OnMotion(self, evt):
        """Called when mouse moves in axes (overridden)"""
        if self.frame and self.Selector.shape[1] < 2:
            self.trace_point(evt.xdata, evt.ydata, type=NORMAL)
    
    def OnPageDown(self, evt):
        """next page"""
        if self.frame and self.__index < len(self)-1:
            self.select(self.__index + 1)
    
    def OnPageUp(self, evt):
        """previous page"""
        if self.frame and self.__index > 0:
            self.select(self.__index - 1)
    
    def OnHomePosition(self, evt):
        self.update_axis()
    
    def OnEscapeSelection(self, evt):
        xs, ys = self.Selector
        del self.Selector
        if len(xs) > 1:
            self.handler('line_removed', self.frame)
    
    ## def zoomlim(self, lim, M, c=None): # virtual call from OnZoom, OnScrollZoom
    ##     if c is None:
    ##         c = (lim[1] + lim[0]) / 2
    ##     y = c - M * (c - lim)
    ##     if self.frame:
    ##         if abs(y[1] - y[0]) > self.frame.unit or M > 1:
    ##             return y
    
    def OnXAxisPanZoom(self, evt, c=None):
        org = self.p_event
        M = np.exp(-(evt.x - org.x)/100)
        if c is None:
            c = org.xdata
        self.xlim = self.zoomlim(self.xlim, M, c)
        self.ylim = self.zoomlim(self.ylim, M)
        org.x, org.y = evt.x, evt.y
        self.draw()
    
    def OnYAxisPanZoom(self, evt, c=None):
        org = self.p_event
        M = np.exp(-(evt.y - org.y)/100)
        if c is None:
            c = org.ydata
        self.xlim = self.zoomlim(self.xlim, M)
        self.ylim = self.zoomlim(self.ylim, M, c)
        org.x, org.y = evt.x, evt.y
        self.draw()
    
    ## --------------------------------
    ## Selector interface
    ## --------------------------------
    
    def calc_point(self, x, y, centred=True):
        """Restrict point (x,y) in image area
        if centred, correct the point to the center of the nearest pixel.
        """
        l,r,b,t = self.frame.get_extent()
        nx, ny = self.frame.xytopixel(
            x = l if x < l else r if x > r else x,
            y = b if y < b else t if y > t else y,
        )
        ux, uy = self.frame.xy_unit
        x = l + nx * ux
        y = t - ny * uy
        if centred:
            x = x + ux/2 if x < r else x - ux/2
            y = y - uy/2 if y > b else y + uy/2
        return (x, y)
    
    def calc_shiftpoint(self, xo, yo, x, y, centred=True):
        dx, dy = x-xo, y-yo
        L = np.hypot(dy,dx)
        a = np.arctan2(dy,dx)
        aa = np.linspace(-pi,pi,9) + pi/8 # ?????????????????????
        k = np.searchsorted(aa, a)
        x = xo + L * np.cos(aa[k] - pi/8)
        y = yo + L * np.sin(aa[k] - pi/8)
        return self.calc_point(x, y, centred)
    
    def OnSelectorAppend(self, evt):
        xs, ys = self.Selector
        x, y = self.calc_point(evt.xdata, evt.ydata)
        self.Selector = np.append(xs, x), np.append(ys, y)
        self.handler('line_drawn', self.frame)
    
    def OnDragLock(self, evt):
        ## pressed/drug ???????????????????????????
        pass
    
    def OnDragBegin(self, evt):
        if not self.frame or self._inaxes(evt):
            self.handler('quit', evt)
            return
        org = self.p_event # the last pressed
        self.__lastpoint = self.calc_point(org.xdata, org.ydata)
        self.__orgpoints = self.Selector
    
    def OnDragMove(self, evt, shift=False):
        x, y = self.calc_point(evt.xdata, evt.ydata)
        xo, yo = self.__lastpoint
        if shift:
            x, y = self.calc_shiftpoint(xo, yo, x, y)
        self.Selector = ([xo,x], [yo,y])
        self.handler('line_draw', self.frame)
    
    def OnDragShiftMove(self, evt):
        self.OnDragMove(evt, shift=True)
    
    def OnDragEscape(self, evt):
        self.Selector = self.__orgpoints
        self.handler('line_draw', self.frame)
        
    def OnDragEnd(self, evt):
        x, y = self.calc_point(evt.xdata, evt.ydata)
        xo, yo = self.__lastpoint
        if x == xo and y == yo:
            self.Selector = (x, y)
        self.handler('line_drawn', self.frame)
    
    ## --------------------------------
    ## Selector +Line interface
    ## --------------------------------
    
    def OnLineSelected(self, evt):
        k = evt.ind[0]
        x = evt.mouseevent.xdata
        y = evt.mouseevent.ydata
        xs, ys = evt.artist.get_data(orig=0)
        dots = np.hypot(x-xs[k], y-ys[k]) * self.ddpu[0]
        self.__linesel = k if dots < 8 else None
    
    def OnLineDeselected(self, evt): #<matplotlib.backend_bases.PickEvent>
        self.__linesel = None
    
    def OnLineDragBegin(self, evt):
        if not self.frame or self._inaxes(evt):
            self.handler('quit', evt)
            return
        org = self.p_event # the last pressed
        self.__lastpoint = self.calc_point(org.xdata, org.ydata)
        self.__orgpoints = self.Selector
    
    def OnLineDragMove(self, evt, shift=False):
        x, y = self.calc_point(evt.xdata, evt.ydata)
        xc, yc = self.__lastpoint
        xo, yo = self.__orgpoints
        j = self.__linesel
        if j is not None:
            if shift:
                i = j-1 if j else 1
                xo, yo = xo[i], yo[i] # ?????????????????????????????????
                x, y = self.calc_shiftpoint(xo, yo, x, y)
            xs, ys = self.Selector
            xs[j], ys[j] = x, y
            self.Selector = (xs, ys)
            self.handler('line_draw', self.frame)
        else:
            xs = xo + (x - xc)
            ys = yo + (y - yc)
            self.Selector = (xs, ys)
            self.handler('line_move', self.frame)
    
    def OnLineDragShiftMove(self, evt):
        self.OnLineDragMove(evt, shift=True)
    
    def OnLineDragEscape(self, evt):
        self.Selector = self.__orgpoints
        if self.__linesel:
            self.handler('line_drawn', self.frame)
        else:
            self.handler('line_moved', self.frame)
    
    def OnLineDragEnd(self, evt):
        if self.__linesel:
            self.handler('line_drawn', self.frame)
        else:
            self.handler('line_moved', self.frame)
    
    def OnLineShift(self, evt):
        if self.Selector.size and self.frame:
            ux, uy = self.frame.xy_unit
            du = {
                'up' : ( 0., uy),
              'down' : ( 0.,-uy),
              'left' : (-ux, 0.),
             'right' : ( ux, 0.),
            }
            self.Selector += np.resize(du[evt.key], (2,1))
            self.handler('line_move', self.frame)
    
    def OnLineShiftEnd(self, evt):
        self.handler('line_moved', self.frame)
    
    ## --------------------------------
    ## Region interface
    ## --------------------------------
    
    @property
    def Region(self):
        """Region of interest [l,r] [b,t]"""
        x, y = self.rected.get_data(orig=0)
        if len(x) and len(y):
            xo, x = min(x), max(x)
            yo, y = min(y), max(y)
            return np.array(((xo, x), (yo, y)))
        return np.resize(0., (2,0))
    
    @Region.setter
    def Region(self, v):
        x, y = v
        if len(x) > 1:
            self.set_current_rect(x, y)
            self.handler('region_drawn', self.frame)
    
    @Region.deleter
    def Region(self):
        if self.Region.size:
            self.del_current_rect()
            self.handler('region_removed', self.frame)
    
    def get_current_rect(self):
        """Currently selected region"""
        if self.__rectsel:
            x, y = self.rected.get_data(orig=0)
            return np.array((x, y))
    
    def set_current_rect(self, x, y):
        if len(x) == 2:
            (xa,xb), (ya,yb) = x, y
            self.__rectsel = [2]
        else:
            l,r,b,t = self.frame.get_extent()
            xa, xb = min(x), max(x)
            ya, yb = min(y), max(y)
            ## if (xa < l or xb > r) or (ya < b or yb > t):
            ##     return
            ## Modify range so that it does not exceed the extent
            w, h = xb-xa, yb-ya
            if xa < l: xa, xb = l, l+w
            if xb > r: xa, xb = r-w, r
            if ya < b: ya, yb = b, b+h
            if yb > t: ya, yb = t-h, t
        x = [xa, xb, xb, xa, xa]
        y = [ya, ya, yb, yb, ya]
        self.rected.set_data(x, y)
        self.rected.set_visible(1)
        self.update_art_of_region()
    
    def del_current_rect(self):
        self.__rectsel = []
        self.rected.set_data([], [])
        self.rected.set_visible(0)
        self.update_art_of_region()
    
    def update_art_of_region(self, *args):
        if args:
            art = self.__rectarts # art ?????????????????????????????????
            art.xy = args
            self.draw(self.rected)
            return
        for art in self.__rectarts:
            art.remove()
        self.__rectarts = []
        if self.rected.get_visible() and self.handler.current_state in (REGION, REGION+DRAGGING):
            x, y = self.rected.get_data(orig=0)
            if x.size:
                self.__rectarts.append(
                  self.axes.add_patch(
                    patches.Polygon(list(zip(x,y)),
                      color='red', ls='solid', lw=1/2, ec='white', alpha=0.2)
                  )
                )
            self.trace_point(x, y, type=REGION)
        self.draw(self.rected)
    
    def OnRegionAppend(self, evt):
        xs, ys = self.Selector
        if len(xs) > 0 and self.frame:
            ux, uy = self.frame.xy_unit
            xs = (xs.min()-ux/2, xs.max()+ux/2)
            ys = (ys.max()+uy/2, ys.min()-uy/2)
            self.set_current_rect(xs, ys)
            self.update_art_of_region()
            self.handler('region_drawn', self.frame)
    
    def OnRegionRemove(self, evt):
        if self.__rectsel:
            self.del_current_rect()
            self.handler('region_removed', self.frame)
        self.set_wxcursor(wx.CURSOR_ARROW)
    
    def OnRegionSelected(self, evt): #<matplotlib.backend_bases.PickEvent>
        k = evt.ind[0]
        x = evt.mouseevent.xdata
        y = evt.mouseevent.ydata
        xs, ys = evt.artist.get_data(orig=0)
        dots = np.hypot(x-xs[k], y-ys[k]) * self.ddpu[0]
        self.__rectsel = [k] if dots < 8 else [0,1,2,3,4] # ???????????????????????????
        self.update_art_of_region()
    
    def OnRegionDeselected(self, evt): #<matplotlib.backend_bases.PickEvent>
        self.__rectsel = []
        self.update_art_of_region()
        self.set_wxcursor(wx.CURSOR_ARROW)
    
    def OnRegionDragBegin(self, evt):
        if not self.frame or self._inaxes(evt):
            self.handler('quit', evt)
            return
        org = self.p_event # the last pressed
        self.__lastpoint = self.calc_point(org.xdata, org.ydata, centred=False)
        if not self.__rectsel:
            x, y = self.__lastpoint
            self.set_current_rect((x,x), (y,y)) # start new region
        self.__orgpoints = self.get_current_rect()
    
    def OnRegionDragMove(self, evt, shift=False, meta=False):
        x, y = self.calc_point(evt.xdata, evt.ydata, centred=False)
        xs, ys = self.get_current_rect()
        j = self.__rectsel # corner-drag[1] or region-drag[4]
        if len(j) == 1:
            k = (j[0] + 2) % 4 # ?????????????????????????????????
            xo, yo = xs[k], ys[k]
            if shift:
                x, y = self.calc_shiftpoint(xo, yo, x, y, centred=False)
            elif meta:
                ux, uy = self.frame.xy_unit
                nn = (1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192)
                n = max(abs(x-xo)/ux, abs(y-yo)/uy)
                i = np.searchsorted(nn, n)
                x = xo + nn[i] * np.sign(x-xo) * ux
                y = yo + nn[i] * np.sign(y-yo) * uy
            self.set_current_rect((xo,x), (yo,y))
        else:
            xc, yc = self.__lastpoint
            xo, yo = self.__orgpoints
            xs = xo + (x - xc)
            ys = yo + (y - yc)
            self.set_current_rect(xs, ys)
        self.handler('region_draw', self.frame)
    
    def OnRegionDragShiftMove(self, evt):
        self.OnRegionDragMove(evt, shift=True)
    
    def OnRegionDragMetaMove(self, evt):
        self.OnRegionDragMove(evt, meta=True)
        
    def OnRegionDragEscape(self, evt):
        self.set_current_rect(*self.__orgpoints)
        self.handler('region_drawn', self.frame)
    
    def OnRegionDragEnd(self, evt):
        self.__rectsel = [0,1,2,3,4] # ???????????????????????????
        self.handler('region_drawn', self.frame)
    
    def OnRegionShift(self, evt):
        j = self.__rectsel
        if j and self.frame:
            ux, uy = self.frame.xy_unit
            du = {
                'up' : ( 0., uy),
              'down' : ( 0.,-uy),
              'left' : (-ux, 0.),
             'right' : ( ux, 0.),
            }
            dp = du[evt.key]
            p = self.get_current_rect().T
            if len(j) == 1:
                i = j[0]        # ????????????????????????
                k = (i + 2) % 4 # ?????????????????????????????????
                p[i] += dp
                self.set_current_rect(*p[[k,i]].T)
            else:
                p += dp
                self.set_current_rect(*p.T)
            self.handler('region_draw', self.frame)
    
    def OnRegionShiftEnd(self, evt):
        self.handler('region_drawn', self.frame)
    
    def OnRegionMotion(self, evt):
        x, y = evt.xdata, evt.ydata
        if self.Region.size:
            (l,r), (b,t) = self.Region
            d = self.rected.pickradius / self.ddpu[0]
            x0 = l+d < x < r-d
            y0 = b+d < y < t-d
            x1 = l-d < x < l+d
            x2 = r-d < x < r+d
            y1 = b-d < y < b+d
            y2 = t-d < y < t+d
            if x0 and y0:
                ## self.set_wxcursor(wx.CURSOR_HAND) # insdie
                self.set_wxcursor(wx.CURSOR_ARROW)
            elif (x1 or x2) and y0:
                ## self.set_wxcursor(wx.CURSOR_SIZEWE) # on-x-edge
                self.set_wxcursor(wx.CURSOR_SIZING)
            elif x0 and (y1 or y2):
                ## self.set_wxcursor(wx.CURSOR_SIZENS) # on-y-edge
                self.set_wxcursor(wx.CURSOR_SIZING)
            elif x1 and y1 or x2 and y2:
                self.set_wxcursor(wx.CURSOR_SIZENESW) # on-NE/SW-corner
            elif x1 and y2 or x2 and y1:
                self.set_wxcursor(wx.CURSOR_SIZENWSE) # on-NW/SE-corner
            else:
                self.set_wxcursor(wx.CURSOR_ARROW) # outside
    
    ## --------------------------------
    ## Markers interface
    ## --------------------------------
    
    ## plot markers ??????(??????)??????????????????
    maxnum_markers = 1000
    
    @property
    def Markers(self):
        """Marked poitns [[x],[y]]"""
        xm, ym = self.marked.get_data(orig=0)
        return np.array((xm, ym))
    
    @Markers.setter
    def Markers(self, v):
        x, y = v
        if len(x) > self.maxnum_markers:
            self.message("- got too many markers ({}) to plot".format(len(x)))
            return
        self.marked.set_data(x, y)
        self.__marksel = []
        self.update_art_of_mark()
        self.handler('mark_drawn', self.frame)
    
    @Markers.deleter
    def Markers(self):
        if self.Markers.size:
            self.marked.set_data([], [])
            self.__marksel = []
            self.update_art_of_mark()
            self.handler('mark_removed', self.frame)
    
    def get_current_mark(self):
        """Currently selected mark"""
        xm, ym = self.marked.get_data(orig=0)
        return np.take((xm, ym), self.__marksel, axis=1)
    
    def set_current_mark(self, x, y):
        xm, ym = self.marked.get_data(orig=0)
        j = self.__marksel
        if j:
            xm[j], ym[j] = x, y
            self.marked.set_data(xm, ym)
            self.update_art_of_mark(j, xm[j], ym[j])
        else:
            n = len(xm)
            k = len(x) if hasattr(x, '__iter__') else 1
            self.__marksel = list(range(n, n+k))
            xm, ym = np.append(xm, x), np.append(ym, y)
            self.marked.set_data(xm, ym)
            self.marked.set_visible(1)
            self.update_art_of_mark()
        self.Selector = (x, y)
    
    def del_current_mark(self):
        j = self.__marksel
        if j:
            xm, ym = self.marked.get_data(orig=0)
            xm, ym = np.delete(xm,j), np.delete(ym,j)
            self.__marksel = []
            self.marked.set_data(xm, ym)
            n = len(xm)
            self.__marksel = [j[-1] % n] if n > 0 else []
            self.update_art_of_mark()
    
    def update_art_of_mark(self, *args):
        if args:
            for k,x,y in zip(*args):
                art = self.__markarts[k] # art ?????????????????????????????????
                art.xy = x, y
            self.draw(self.marked)
            return
        for art in self.__markarts: # or reset all arts
            art.remove()
        self.__markarts = []
        if self.marked.get_visible() and self.handler.current_state in (MARK, MARK+DRAGGING):
            N = self.maxnum_markers
            xm, ym = self.marked.get_data(orig=0)
            for k, (x,y) in enumerate(zip(xm[:N],ym[:N])):
                self.__markarts.append(
                  self.axes.annotate(k, #<matplotlib.text.Annotation>
                    xy=(x,y), xycoords='data',
                    xytext=(6,6), textcoords='offset points',
                    bbox=dict(boxstyle="round", fc=(1,1,1,), ec=(1,0,0,)),
                    color='red', size=7, #fontsize=8,
                  )
                )
            self.Selector = self.get_current_mark()
            self.trace_point(*self.Selector, type=MARK)
        self.draw(self.marked)
    
    def OnMarkAppend(self, evt):
        xs, ys = self.Selector
        if not self.__marksel and len(xs) > 0:
            self.set_current_mark(xs, ys)
            self.handler('mark_drawn', self.frame)
        self.update_art_of_mark()
    
    def OnMarkRemove(self, evt):
        if self.__marksel:
            self.del_current_mark()
            self.handler('mark_removed', self.frame)
    
    def OnMarkSelected(self, evt): #<matplotlib.backend_bases.PickEvent>
        k = evt.ind[0]
        if evt.mouseevent.key == 'shift': # ????????????????????????
            if k not in self.__marksel:
                self.__marksel += [k]
        else:
            self.__marksel = [k]
        self.update_art_of_mark()
        
        if self.Selector.shape[1] > 1:
            self.handler('line_drawn', self.frame) # ???????????????????????????
    
    def OnMarkDeselected(self, evt): #<matplotlib.backend_bases.PickEvent>
        self.__marksel = []
        self.update_art_of_mark()
    
    def OnMarkDragBegin(self, evt):
        if not self.frame or self._inaxes(evt):
            self.handler('quit', evt)
            return
        self.__orgpoints = self.get_current_mark()
    
    def OnMarkDragMove(self, evt):
        x, y = self.calc_point(evt.xdata, evt.ydata)
        self.set_current_mark(x, y)
        self.handler('mark_draw', self.frame)
    
    def OnMarkDragEscape(self, evt):
        self.set_current_mark(*self.__orgpoints)
        self.handler('mark_drawn', self.frame)
    
    def OnMarkDragEnd(self, evt):
        self.handler('mark_drawn', self.frame)
    
    def OnMarkShift(self, evt):
        j = self.__marksel
        if j and self.frame:
            ux, uy = self.frame.xy_unit
            du = {
                'up' : ( 0., uy),
              'down' : ( 0.,-uy),
              'left' : (-ux, 0.),
             'right' : ( ux, 0.),
            }
            p = self.get_current_mark() + np.resize(du[evt.key], (2,1))
            self.set_current_mark(*p)
            self.handler('mark_draw', self.frame)
    
    def OnMarkShiftEnd(self, evt):
        self.handler('mark_drawn', self.frame)
    
    def next_mark(self, j):
        self.__marksel = [j]
        xs, ys = self.get_current_mark()
        self.xlim += xs[-1] - (self.xlim[1] + self.xlim[0]) / 2
        self.ylim += ys[-1] - (self.ylim[1] + self.ylim[0]) / 2
        self.Selector = (xs, ys)
        self.trace_point(xs, ys, type=MARK)
        self.draw()
    
    def OnMarkSkipNext(self, evt):
        n = self.Markers.shape[1]
        j = self.__marksel
        if j:
            self.next_mark((j[-1]+1) % n)
        elif n:
            self.next_mark(0)
    
    def OnMarkSkipPrevious(self, evt):
        n = self.Markers.shape[1]
        j = self.__marksel
        if j:
            self.next_mark((j[-1]-1) % n)
        elif n:
            self.next_mark(-1)


if __name__ == "__main__":
    app = wx.App()
    frm = mwx.Frame(None)
    frm.graph = GraphPlot(frm,
                          log=frm.statusbar,
                          margin=(.1,.1,.9,.9),
                          size=(300,240))
    frm.handler.debug = 0
    frm.graph.handler.debug = 4
    
    def _imread(path):
        return Image.open(path)
    
    frm.graph.load(_imread(u"C:/usr/home/workspace/images/sample.bmp"), "sample")
    frm.graph.load(_imread(u"C:/usr/home/workspace/images/????????????.bmp"), "????????????")
    frm.graph.load(_imread(u"C:/usr/home/workspace/images/sample_circ.bmp"), "sample data")
    
    frm.graph.newbuffer = np.uint8(255 * np.random.randn(512,512,3))
    
    frm.graph.frame.aspect_ratio = 1.1
    frm.graph.frame.unit = 0.123
    
    frm.graph.create_colorbar()
    
    def _plot(graph, r=10):
        """????????????????????????"""
        ux = uy = graph.unit
        t = np.arange(0,4,0.01) * pi
        x = r * ux * np.cos(t)
        y = r * uy * np.sin(t)
        graph.axes.plot(x, y, 'r-', lw=0.5)
    ## _plot(frm.graph)
    
    frm.Fit()
    frm.Show()
    app.MainLoop()
