#! python3
"""mwxlib graph plot for images.
"""
import re
import os
import wx

from matplotlib import cm
from matplotlib import patches
from PIL import Image
import cv2
import numpy as np
from numpy import pi
from scipy import ndimage as ndi

from . import framework as mwx
from .framework import Menu
from .utilus import funcall as _F
from .controls import Clipboard
from .matplot2 import MatplotPanel
from .matplot2 import NORMAL, DRAGGING, PAN, ZOOM, MARK, LINE, REGION


def _to_array(x):
    if isinstance(x, (list, tuple)):
        x = np.array(x)
    return x


def _to_cvtype(src):
    """Convert the image to a type that can be applied to the cv2 function.
    Note:
        CV2 normally accepts uint8/16 and float32/64.
    """
    if src.dtype in (np.uint32, np.int32): return src.astype(np.float32)
    if src.dtype in (np.uint64, np.int64): return src.astype(np.float64)
    return src


def _to_buffer(img):
    if isinstance(img, Image.Image):
        # return np.asarray(img)  # ref
        return np.array(img)  # copy
    
    if isinstance(img, wx.Bitmap):  # bitmap to image
        img = img.ConvertToImage()
    
    if isinstance(img, wx.Image):  # image to RGB array; RGB to grayscale
        w, h = img.GetSize()
        img = np.frombuffer(img.GetDataBuffer(), dtype='uint8').reshape(h, w, 3)
    
    if not isinstance(img, np.ndarray):
        raise ValueError("targets must be arrays or images.")
    
    if img.ndim < 2:
        raise ValueError("targets must be 2d arrays.")
    
    if img.ndim > 2:
        return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return img


def _to_image(src, cutoff=0, threshold=None, binning=1):
    """Convert buffer to image <uint8>.
    
    >>> dst = (src-a) * 255 / (b-a)
    
    cf. convertScaleAbs(src[, dst[, alpha[, beta]]]) -> dst <uint8>
    
        >>> dst = |src * alpha + beta|
            alpha = 255 / (b-a)
            beta = -a * alpha
    
    Args:
        cutoff: cutoff score [%] to cut the lo/hi limits
        threshold: limit bytes of image (to make matplotlib light)
        binning: minimum binning number of src array
    """
    if src.dtype in (np.complex64, np.complex128):  # maybe fft pattern
        src = np.log(1 + abs(src))
    
    if threshold:
        ## Reduce the binning by itemsize before finally converting to <uint8>.
        ## Select the larger value between binning and threshold.
        n = max(binning, int(np.sqrt(src.nbytes / threshold / src.itemsize)) + 1)
    else:
        n = binning
    if n > 1:
        src = _to_cvtype(src)
        src = cv2.resize(src, None, fx=1/n, fy=1/n, interpolation=cv2.INTER_AREA)
    
    if src.dtype == np.uint8:  # RGB or gray image <uint8>
        return n, (0, 255), src
    
    if hasattr(cutoff, '__iter__'):  # cutoff vlim: (vmin, vmax) is specified.
        a, b = cutoff
    elif cutoff > 0:
        a = np.percentile(src, cutoff)
        b = np.percentile(src, 100-cutoff)
    else:
        a = src.min()
        b = src.max()
    
    r = (255 / (b - a)) if a < b else 1
    ## img = cv2.convertScaleAbs(src, alpha=r, beta=-r*a)  # 負数は絶対値になるので以下に変更．
    img = np.uint8((src - a) * r)
    img[src < a] = 0
    img[src > b] = 255
    return n, (a, b), img


def _get_filestamp(filename):
    """Check the modification timestamp of a file.
    
    Returns:
        float: Modification time for an existing file.
        False: If the file path is valid but the file does not exist.
        None: If the path is invalid.
        -1: If the input is a URL.
    """
    # url_re = r"https?://[\w/:%#$&?()~.=+-]+"
    url_re = r"https?://[\w/:%#$&?!@~.,;=+-]+"  # excluding ()
    try:
        return os.path.getmtime(filename)  # timestamp (modified time)
    except FileNotFoundError:
        return False  # valid path (but not found)
    except OSError:
        if re.match(url_re, filename):
            return -1  # URL path
    except Exception:
        pass
    return None  # invalid path or any other unexpected error


def _Property(name):
    return property(
        lambda self:    getattr(self.parent, name),
        lambda self, v: setattr(self.parent, name, v),
        lambda self:    delattr(self.parent, name))


class AxesImagePhantom:
    """Phantom of frame facade.
    
    Args:
        buf:  buffer
        name: buffer name
        show: show immediately when loaded
        **kwargs: frame attributes
    
    Note:
        Due to the problem of performance, the image pixel size could be reduced by binning.
    """
    def __init__(self, parent, buf, name, show=True, **kwargs):
        self.parent = parent
        
        ## Properties of the frame/image.
        self.__name = name
        self.__attributes = kwargs
        self.__pathname = kwargs.get('pathname')
        self.__mtime = _get_filestamp(self.__pathname)
        self.__annotation = kwargs.get('annotation', '')
        self.__localunit = kwargs.get('localunit')
        self.__center = kwargs.get('center', [0, 0])
        
        ## Conditions for image loading.
        self.__buf = _to_buffer(buf)
        bins, vlim, img = _to_image(self.__buf,
                                    cutoff=self.parent.score_percentile,
                                    threshold=self.parent.nbytes_threshold,
                                    )
        self.__bins = bins
        self.__cuts = vlim
        self.__art = parent.axes.imshow(img,
                                        cmap=cm.gray,
                                        aspect='equal',  # cf. aspect_ratio => xy_unit
                                        interpolation='nearest',
                                        visible=show,
                                        picker=True,
                                        )
        self.aspect_ratio = 1
        self.update_extent()

    def __getattr__(self, attr):
        return getattr(self.__art, attr)

    def __eq__(self, x):
        ## Called in `on_pick` and `__contains__` to check objects in.
        return x is self.__art

    def update_attr(self, attr):
        """Update frame-specifc attributes."""
        if not attr:
            return
        
        FLAG_ANNOTATION = 1
        FLAG_UPDATE_EXTENT = 2
        flag = 0
        if 'pathname' in attr:
            self.__pathname = attr['pathname']
            self.__mtime = _get_filestamp(self.__pathname)
            flag |= FLAG_ANNOTATION
        
        if 'annotation' in attr:
            self.__annotation = attr['annotation']
            if self.parent.frame is self:
                self.parent.infobar.ShowMessage(attr['annotation'])
            flag |= FLAG_ANNOTATION
        
        if 'center' in attr:
            v = list(attr['center'])  # for json format
            if v != self.__center:
                self.__center = v
                flag |= FLAG_UPDATE_EXTENT
        
        if 'localunit' in attr:
            v = attr['localunit']
            if v is None or np.isnan(v):  # nan => None: undefined.
                v = None
            elif np.isinf(v):
                raise ValueError("The unit value must not be inf")
            elif v <= 0:
                raise ValueError("The unit value must be greater than zero")
            if v != self.__localunit:
                self.__localunit = v
                flag |= FLAG_UPDATE_EXTENT
        
        self.__attributes.update(attr)
        
        if flag & FLAG_UPDATE_EXTENT:
            self.update_extent()
            self.parent.canvas.draw_idle()
        if flag:
            self.parent.handler('frame_updated', self)

    def update_buffer(self, buf=None):
        """Update buffer and the image (internal use only)."""
        if buf is not None:
            self.__buf = _to_buffer(buf)
        
        bins, vlim, img = _to_image(self.__buf,
                                    cutoff = self.parent.score_percentile,
                                    threshold = self.parent.nbytes_threshold,
                                    )
        self.__bins = bins
        self.__cuts = vlim
        self.__art.set_array(img)
        self.parent.handler('frame_modified', self)

    def update_extent(self):
        """Update logical extent of the image (internal use only)."""
        h, w = self.__buf.shape[:2]
        ux, uy = self.xy_unit
        w *= ux/2
        h *= uy/2
        cx, cy = self.center
        self.__art.set_extent((cx-w, cx+w, cy-h, cy+h))

    artist = property(
        lambda self: self.__art)

    binning = property(
        lambda self: self.__bins,
        doc="Binning value resulting from the score_percentile.")

    cuts = property(
        lambda self: self.__cuts,
        doc="Lower/Upper cutoff values of the buffer.")

    image = property(
        lambda self: self.__art.get_array(),
        doc="Displayed image array<uint8>.")

    clim = property(
        lambda self: self.__art.get_clim(),
        lambda self, v: self.__art.set_clim(v),
        doc="Lower/Upper color limit values of the buffer.")

    attributes = property(
        lambda self: self.__attributes,
        doc="Auxiliary info about the frame.")

    pathname = property(
        lambda self: self.__pathname,
        lambda self, v: self.update_attr({'pathname': v}),
        doc="Fullpath of the buffer, if bound to a file.")

    annotation = property(
        lambda self: self.__annotation,
        lambda self, v: self.update_attr({'annotation': v}),
        doc="Annotation of the buffer.")

    center = property(
        lambda self: self.__center,
        lambda self, v: self.update_attr({'center': v}),
        doc="Center coordinates of the frame in logical units.")

    localunit = property(
        lambda self: self.__localunit,
        lambda self, v: self.update_attr({'localunit': v}),
        doc="Logical length per pixel in arbitrary units [u/pix], or None if not assigned.")

    unit = property(
        lambda self: self.__localunit or self.parent.unit,
        lambda self, v: self.update_attr({'localunit': v}),
        doc="Logical length per pixel in arbitrary units [u/pix].")

    @property
    def xy_unit(self):
        """Logical length per pixel in arbitrary units [u/pix] for (X, Y) directions."""
        u = self.unit
        r = self.aspect_ratio
        return (u, u) if r == 1 else (u, u * r)

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self, v):
        self.__name = v
        self.parent.handler('frame_updated', self)

    @property
    def mtdelta(self):
        """Timestamp delta (for checking external mod).
        
        Returns:
            = 0: a file (or False if not found)
            > 0: a file modified externally
            < 0: a url file
            None: no file
        """
        try:
            return os.path.getmtime(self.pathname) - self.__mtime
        except Exception:
            return self.__mtime

    @property
    def index(self):
        """Page number in the parent view."""
        return self.parent.index(self)

    @property
    def roi(self):
        """Current buffer ROI (region of interest)."""
        if self.parent.region.size:
            nx, ny = self.xytopixel(self.region)
            sx = slice(max(0, nx[0]), nx[1])  # nx slice
            sy = slice(max(0, ny[1]), ny[0])  # ny slice 反転 (降順)
            return self.__buf[sy, sx]
        return None

    @roi.setter
    def roi(self, v):
        if not self.parent.region.size:
            raise ValueError("region is not selected.")
        self.roi[:] = v  # cannot broadcast input array into different shape
        self.update_buffer()

    @property
    def roi_or_buffer(self):
        return self.roi if self.parent.region.size else self.buffer

    @property
    def buffer(self):
        return self.__buf

    @buffer.setter
    def buffer(self, v):
        self.update_buffer(v)
        self.update_extent()

    def xytoc(self, x, y=None, nearest=True):
        """Convert xydata (x,y) -> data[(x,y)] value of neaerst pixel.
        If `nearest` is False, the return value is interpolated with spline.
        """
        h, w = self.__buf.shape[:2]
        nx, ny = self.xytopixel(x, y, cast=nearest)
        ## if np.any((nx<0) | (nx>=w) | (ny<0) | (ny>=h)):
        if np.any(nx<0) or np.any(nx>=w) or np.any(ny<0) or np.any(ny>=h):
            return
        if nearest:
            return self.__buf[ny, nx]  # nearest value
        return ndi.map_coordinates(self.__buf, np.vstack((ny, nx)))  # spline value

    def xytopixel(self, x, y=None, cast=True):
        """Convert xydata (x,y) -> [nx,ny] pixel.
        If `cast` is True, the return value will be integer pixel values.
        """
        def _cast(n):
            return np.int32(np.floor(np.round(n, 1)))
        if y is None:
            # warn("Setting xy data with single tuple.", DeprecationWarning)
            x, y = x
        x, y = _to_array(x), _to_array(y)
        l,r,b,t = self.__art.get_extent()
        ux, uy = self.xy_unit
        nx = (x - l) / ux
        ny = (t - y) / uy  # Y ピクセルインデクスは座標と逆
        if cast:
            return np.array((_cast(nx), _cast(ny)))
        return np.array((nx-0.5, ny-0.5))

    def xyfrompixel(self, nx, ny=None):
        """Convert pixel [nx,ny] -> (x,y) xydata (float number).
        """
        if ny is None:
            # warn("Setting xy data with single tuple.", DeprecationWarning)
            nx, ny = nx
        nx, ny = _to_array(nx), _to_array(ny)
        l,r,b,t = self.__art.get_extent()
        ux, uy = self.xy_unit
        x = l + (nx + 0.5) * ux
        y = t - (ny + 0.5) * uy  # Y ピクセルインデクスは座標と逆
        return np.array((x, y))

    selector = _Property('selector')
    markers = _Property('markers')
    region = _Property('region')

    @property
    def selector_pix(self):
        """Selected points array [[x], [y]] in pixels."""
        return self.xytopixel(self.selector)

    @selector_pix.setter
    def selector_pix(self, v):
        self.selector = self.xyfrompixel(v)

    @property
    def markers_pix(self):
        """Marked points data array [[x], [y]] in pixels."""
        return self.xytopixel(self.markers)

    @markers_pix.setter
    def markers_pix(self, v):
        self.markers = self.xyfrompixel(v)

    @property
    def region_pix(self):
        """Cropped points data array [[l,r], [b,t]] in pixels."""
        return self.xytopixel(self.region)

    @region_pix.setter
    def region_pix(self, v):
        self.region = self.xyfrompixel(v)


class GraphPlot(MatplotPanel):
    """Graph panel for 2D graph.
    """
    def __init__(self, *args, **kwargs):
        MatplotPanel.__init__(self, *args, **kwargs)
        
        def _draw(evt):
            self.canvas.draw_idle()
        
        self.handler.update({  # DNA<GraphPlot>
            None : {
                  'frame_shown' : [None, ],  # show
                 'frame_hidden' : [None, ],  # show
                 'frame_loaded' : [None, ],  # load
                'frame_removed' : [None, ],  # del[] ! event arg is indices, not frames.
               'frame_selected' : [None, ],  # = focus_set
             'frame_deselected' : [None, ],  # = focus_kill
               'frame_modified' : [None, _F(self.writeln)],  # set[],load,roi  => update_buffer
                'frame_updated' : [None, _F(self.writeln)],  # unit,name,ratio => update_extent
                'frame_cmapped' : [None, _F(self.writeln)],  # cmap
                    'line_draw' : [None, ],
                   'line_drawn' : [None, _draw],
                    'line_move' : [None, ],
                   'line_moved' : [None, _draw],
                 'line_removed' : [None, _draw],
                    'mark_draw' : [None, ],
                   'mark_drawn' : [None, _draw],
                 'mark_removed' : [None, _draw],
                  'region_draw' : [None, ],
                 'region_drawn' : [None, _draw],
               'region_removed' : [None, _draw],
                 'M-up pressed' : [None, self.OnPageUp],
               'M-down pressed' : [None, self.OnPageDown],
               'pageup pressed' : [None, self.OnPageUp],
             'pagedown pressed' : [None, self.OnPageDown],
                 'home pressed' : [None, _F(self.select, index=0)],
                  'end pressed' : [None, _F(self.select, index=-1)],
                  'M-a pressed' : [None, _F(self.fit_to_canvas)],
                  'C-a pressed' : [None, _F(self.fit_to_axes)],
                  'C-i pressed' : [None, _F(self.invert_cmap)],
                  'C-k pressed' : [None, _F(self.kill_buffer)],
                'C-S-k pressed' : [None, _F(self.kill_all_buffers)],
                  'C-c pressed' : [None, _F(self.write_buffer_to_clipboard)],
                  'C-v pressed' : [None, _F(self.read_buffer_from_clipboard)],
            },
            NORMAL : {
                 'image_picked' : (NORMAL, self.OnImagePicked),
                  'line_picked' : (LINE, self.OnLineSelected),
                  'mark_picked' : (MARK, self.OnMarkSelected),
                'region_picked' : (REGION, self.OnRegionSelected),
                    'c pressed' : (MARK, self.OnMarkAppend),
            'c+Lbutton pressed' : (MARK, self.OnMarkAppend),
                    'r pressed' : (REGION, self.OnRegionAppend, self.OnEscapeSelection),
            'r+Lbutton pressed' : (REGION, self.OnRegionAppend, self.OnEscapeSelection),
            'M-Lbutton pressed' : (REGION, self.OnRegionAppend, self.OnEscapeSelection),
               'escape pressed' : (NORMAL, self.OnEscapeSelection, _draw),
                'shift pressed' : (NORMAL, self.on_picker_lock),
               'shift released' : (NORMAL, self.on_picker_unlock),
              'Lbutton pressed' : (NORMAL, self.OnDragLock),
            'S-Lbutton pressed' : (NORMAL, self.OnDragLock, self.OnSelectorAppend),
                 '*Ldrag begin' : (NORMAL+DRAGGING, self.OnDragBegin),
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
               'escape pressed' : (NORMAL, self.OnMarkDeselected, _draw),
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
               'escape pressed' : (NORMAL, self.OnRegionDeselected, _draw),
               'delete pressed' : (NORMAL, self.OnRegionRemove),
                'space pressed' : (PAN, self.OnPanBegin),
                 'ctrl pressed' : (PAN, self.OnPanBegin),
                    'c pressed' : (REGION, self.OnRegionCenter),
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
            (mwx.ID_(500), "&Invert Color", "Invert colormap", wx.ITEM_CHECK,
                lambda v: self.invert_cmap(),
                lambda v: v.Check(self.get_cmapstr()[-2:] == "_r")),
            (),
            (wx.ID_CLOSE, "&Kill buffer\t(C-k)", "Kill buffer", _Icon(wx.ART_DELETE),
                lambda v: self.kill_buffer(),
                lambda v: v.Enable(self.frame is not None)),
                
            (wx.ID_CLOSE_ALL, "&Kill all buffer\t(C-S-k)", "Kill buffers", _Icon(wx.ART_DELETE),
                lambda v: self.kill_all_buffers(),
                lambda v: v.Enable(self.frame is not None)),
        ]
        
        ## modeline menu: バッファリストメニューを追加する．
        def _menu(j, s):
            return (j, s, s, wx.ITEM_CHECK,
                lambda v: self.select(s),
                lambda v: v.Check(self.frame is not None and self.frame.name == s))
        
        self.modeline.Bind(wx.EVT_CONTEXT_MENU,
                           lambda v: Menu.Popup(self, (_menu(j, art.name)
                                                for j, art in enumerate(self.__Arts))))
        
        self.modeline.Show()
        self.writeln()
        self.Layout()

    def clear(self):
        MatplotPanel.clear(self)
        
        self.__Arts = []
        self.__index = None
        
        ## cf. self.figure.dpi = 80 dpi (0.3175 mm/pix)
        self.__unit = 1.0
        
        # <matplotlib.lines.Line2D>
        (self.marked,) = self.axes.plot([], [], "r+", ms=8, mew=1,
                                        picker=8)
        self.__marksel = []
        self.__markarts = []
        self.marked.set_clip_on(False)
        
        # <matplotlib.lines.Line2D>
        (self.rected,) = self.axes.plot([], [], "r+--", ms=4, lw=3/4,
                                        picker=4, alpha=0.8)
        self.__rectsel = []
        self.__rectarts = []
        self.rected.set_clip_on(False)
        
        self.__isPicked = None
        self.selected.set_picker(8)
        self.selected.set_clip_on(False)

    def get_uniqname(self, name):
        base = name = name or "*temp*"
        i = 1
        names = [art.name for art in self.__Arts]
        while name in names:
            i += 1
            name = "{}<{:d}>".format(base, i)
        return name

    def load(self, buf, name=None, pos=None, show=True, **kwargs):
        """Load a buffer with a name.
        
        Args:
            buf:  buffer array.
            name: buffer name (default to *temp*).
            pos:  Insertion position in the frame list.
            show: Show immediately when loaded.
            **kwargs: frame attributes.
        """
        assert buf is not None, "Load buffer must be an array or path:str (not None)"
        
        if isinstance(buf, str):
            buf = Image.open(buf)
        
        path = kwargs.get('pathname')
        paths = [art.pathname for art in self.__Arts]
        names = [art.name for art in self.__Arts]
        j = -1
        if path:
            if path in paths:
                j = paths.index(path)  # existing path
        elif name in names:
            j = names.index(name)  # existing frame
        if j != -1:
            art = self.__Arts[j]
            art.update_buffer(buf)   # => [frame_modified]
            art.update_attr(kwargs)  # => [frame_updated] localunit => [canvas_draw]
            art.update_extent()
            if show:
                self.select(j)
            return art
        
        name = self.get_uniqname(name)
        
        ## The first load of axes.imshow (=> self.axes.axis 表示を更新する).
        art = AxesImagePhantom(self, buf, name, show, **kwargs)
        
        j = len(self) if pos is None else pos
        self.__Arts.insert(j, art)
        self.handler('frame_loaded', art)
        if show:
            u = self.frame and self.frame.unit  # current frame unit
            self.select(j)
            ## Update view if the unit length is different from before selection.
            if u != art.unit:
                self.axes.axis(art.get_extent())
        return art

    def select(self, index):
        if isinstance(index, (str, AxesImagePhantom)):
            j = self.index(index)
        else:
            j = index
        
        for art in self.__Arts:  # Hide all frames
            art.set_visible(0)
        
        if j != self.__index and self.__index is not None:
            self.handler('frame_hidden', self.frame)
        
        if j is not None and self.__Arts:
            art = self.__Arts[j]
            art.set_visible(1)
            self.__index = j % len(self)
            self.handler('frame_shown', art)
        else:
            self.__index = None
        
        self.draw()
        self.writeln()
        self.trace_point(*self.selector)
        return self.frame

    def __iter__(self):
        for art in self.__Arts:
            yield art.buffer

    def __getitem__(self, j):
        if isinstance(j, str):
            j = self.index(j)
        
        buffers = [art.buffer for art in self.__Arts]
        if hasattr(j, '__iter__'):
            return [buffers[i] for i in j]
        return buffers[j]  # j can also be slicing

    def __setitem__(self, j, v):
        if v is None:
            raise ValueError("values must be buffers, not NoneType")
        
        if isinstance(j, str):
            return self.load(v, name=j)  # update buffer or new buffer
        
        if isinstance(j, slice) or hasattr(j, '__iter__'):
            raise ValueError("attempt to assign buffers via slicing or iterator")
        
        art = self.__Arts[j]
        art.update_buffer(v)  # update buffer
        art.update_extent()
        self.select(j)

    def __delitem__(self, j):
        if isinstance(j, str):
            j = self.index(j)
        
        if hasattr(j, '__iter__'):
            arts = [self.__Arts[i] for i in j]
        elif isinstance(j, slice):
            arts = self.__Arts[j]
        else:
            arts = [self.__Arts[j]]
        
        if arts:
            indices = [art.index for art in arts]  # frames to be removed
            for art in arts:
                art.remove()
                self.__Arts.remove(art)
            self.handler('frame_removed', indices)
            
            j = self.__index
            if j is not None:
                n = len(self)
                self.__index = None if n==0 else j if j<n else n-1
            self.select(self.__index)

    ## __len__ は bool() でも呼び出されるため，オブジェクト判定で偽を返すことがある (PY2).
    ## __nonzero__ : bool() を追加しておく必要がある (PY2).

    def __len__(self):
        return len(self.__Arts)

    def __nonzero__(self):
        return True

    def __bool__(self):
        return True

    def __contains__(self, j):
        if isinstance(j, str):
            return j in (art.name for art in self.__Arts)
        elif isinstance(j, np.ndarray):
            return any(j is art.buffer for art in self.__Arts)
        else:
            return j in self.__Arts

    def index(self, j):
        if isinstance(j, str):
            return next(i for i, art in enumerate(self.__Arts) if j == art.name)
        elif isinstance(j, np.ndarray):
            return next(i for i, art in enumerate(self.__Arts) if j is art.buffer)
        else:
            return self.__Arts.index(j)  # j:frame -> int

    def find_frame(self, j):
        if isinstance(j, str):
            return next((art for art in self.__Arts if j == art.name), None)
        elif isinstance(j, np.ndarray):
            return next((art for art in self.__Arts if j is art.buffer), None)
        else:
            return self.__Arts[j]  # j:int -> frame

    def get_all_frames(self, j=None):
        """List of arts <matplotlib.image.AxesImage>."""
        if j is None:
            yield from self.__Arts
        elif isinstance(j, str):
            yield from (art for art in self.__Arts if j in art.name)
        elif isinstance(j, np.ndarray):
            yield from (art for art in self.__Arts if j is art.buffer)

    ## --------------------------------
    ## Property of frame / drawer.
    ## --------------------------------

    ## Image bytes max for loading matplotlib (with wxAgg backend).
    nbytes_threshold = 24e6

    ## Image cutoff score percentiles.
    score_percentile = 0.005

    @property
    def all_frames(self):
        """List of arts <matplotlib.image.AxesImage>."""
        return self.__Arts

    @property
    def frame(self):
        """Current art <matplotlib.image.AxesImage>."""
        if self.__Arts and self.__index is not None:
            return self.__Arts[self.__index]

    @property
    def buffer(self):
        """Current buffer array."""
        if self.frame:
            return self.frame.buffer

    @buffer.setter
    def buffer(self, v):
        if self.frame:
            self.__setitem__(self.__index, v)
        else:
            self.load(v)

    @property
    def unit(self):
        """Logical length per pixel in arbitrary units [u/pix]."""
        return self.__unit

    @unit.setter
    def unit(self, v):
        if v == self.__unit:  # no effect
            return
        if v is None or np.isnan(v) or np.isinf(v):
            raise ValueError("The unit value must not be nan or inf")
        elif v <= 0:
            raise ValueError("The unit value must be greater than zero")
        else:
            self.__unit = v
            for art in self.__Arts:
                art.update_extent()
                self.handler('frame_updated', art)
            self.canvas.draw_idle()

    def kill_buffer(self):
        if self.frame:
            del self[self.__index]

    def kill_all_buffers(self):
        del self[:]

    def fit_to_axes(self):
        """Reset the view limits to the current frame extent."""
        if self.frame:
            self.axes.axis(self.frame.get_extent())  # reset xlim and ylim
            self.toolbar.update()
            self.toolbar.push_current()
            self.draw()

    def fit_to_canvas(self):
        """Reset the view limits to the canvas range."""
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
        """Called when focus is set (override)."""
        MatplotPanel.on_focus_set(self, evt)
        if self.frame:
            self.handler('frame_selected', self.frame)
            self.on_picker_unlock(evt)
        self.trace_point(*self.selector)

    def on_focus_kill(self, evt):
        """Called when focus is killed (override)."""
        MatplotPanel.on_focus_kill(self, evt)
        if self.frame:
            self.handler('frame_deselected', self.frame)
            self.on_picker_lock(evt)

    def get_cmapstr(self):
        if self.frame:
            return self.frame.get_cmap().name
        return ''

    def set_cmapstr(self, name):
        if self.frame:
            self.frame.set_cmap(name)
            self.handler('frame_cmapped', self.frame)
            self.draw()

    def invert_cmap(self):
        if self.frame:
            name = self.frame.get_cmap().name
            self.set_cmapstr(name + "_r" if name[-2:] != "_r" else name[:-2])

    def trace_point(self, x, y, type=NORMAL):
        """Puts (override) a message of points x and y."""
        if not hasattr(x, '__iter__'):  # called from OnMotion
            return self.trace_point([x], [y], type)
        
        frame = self.frame
        if frame:
            if len(x) == 0:  # no selection
                return
            
            if len(x) == 1:  # 1-selector trace point (called from markers.setter)
                x, y = x[0], y[0]
                z = frame.xytoc(x, y)
                nx, ny = frame.xytopixel(x, y)
                self.message(f"[{nx:-4d},{ny:-4d}] ({x:-8.3f},{y:-8.3f}) value: {z}")
                return
            
            if len(x) == 2:  # 2-selector trace line (called from selector.setter)
                nx, ny = frame.xytopixel(x, y)
                dx = x[1] - x[0]
                dy = y[1] - y[0]
                a = np.arctan2(dy, dx) * 180/pi
                lu = np.hypot(dy, dx)
                li = np.hypot(nx[1]-nx[0], ny[1]-ny[0])
                self.message(f"[Line] Length: {li:.1f} pixel ({lu:g}u) Angle: {a:.1f} deg")
            
            elif type == REGION:  # N-selector trace polygon (called from region.setter)
                nx, ny = frame.xytopixel(x, y)
                xo, xp = min(nx), max(nx)
                yo, yp = min(ny), max(ny)
                self.message(f"[Region] crop={xp-xo}:{yp-yo}:{xo}:{yo}")  # (W:H:left:top)

    def writeln(self):
        """Puts (override) attributes of current frame to the modeline."""
        if not self.modeline.IsShown():
            return
        frame = self.frame
        if frame:
            self.modeline.SetLabel(
                "[{page}/{maxpage}] -{a}- {name} ({data.dtype}:{cmap}{bins}) "
                "[{data.shape[1]}:{data.shape[0]}] {x} [{unit:g}/pix]".format(
                page = self.__index,
             maxpage = len(self),
                name = frame.name,
                data = frame.buffer,
                cmap = frame.get_cmap().name,
                bins = ' bin{}'.format(frame.binning) if frame.binning > 1 else '',
                unit = frame.unit,
                   x = '**' if frame.localunit else '--',
                   a = '%%' if not frame.buffer.flags.writeable else '--'))
        else:
            self.modeline.SetLabel(
                "[{page}/{maxpage}] ---- No buffer (-:-) [-:-] -- [{unit:g}/pix]".format(
                page = '-',
             maxpage = len(self),
                unit = self.__unit))

    ## --------------------------------
    ## 外部入出力／複合インターフェース．
    ## --------------------------------
    ## GraphPlot 間共有のグローバル変数
    clipboard_name = None
    clipboard_data = None

    def write_buffer_to_clipboard(self):
        """Write buffer data to clipboard."""
        frame = self.frame
        if not frame:
            self.message("No frame")
            return
        
        name = frame.name
        data = frame.roi_or_buffer
        GraphPlot.clipboard_name = name
        GraphPlot.clipboard_data = data
        bins, vlim, img = _to_image(data, frame.cuts)
        Clipboard.imwrite(img)
        self.message("Write buffer to clipboard.")

    def read_buffer_from_clipboard(self):
        """Read buffer data from clipboard."""
        name = GraphPlot.clipboard_name
        data = GraphPlot.clipboard_data
        if name:
            self.message("Read buffer from clipboard.")
            GraphPlot.clipboard_name = None
            GraphPlot.clipboard_data = None
        else:
            self.message("Read image from clipboard.")
            data = Clipboard.imread()
        if data is not None:
            self.load(data)

    def destroy_colorbar(self):
        if self.cbar:
            self.cbar = None
            cax = self.figure.axes[1]
            self.figure.delaxes(cax)
            self.canvas.draw_idle()
            self.handler.unbind('frame_cmapped', self.update_colorbar)
            self.handler.unbind('frame_shown', self.update_colorbar)

    def update_colorbar(self, frame):
        if self.cbar:
            self.cbar.update_normal(frame)
            self.canvas.draw_idle()
            self.figure.draw_without_rendering()

    def create_colorbar(self):
        """Make a colorbar.
        The colorbar is plotted in self.figure.axes[1] (second axes)
        """
        from mpl_toolkits.axes_grid1 import make_axes_locatable
        if self.frame:
            divider = make_axes_locatable(self.axes)
            cax = divider.append_axes('right', size=0.1, pad=0.1)
            self.cbar = self.figure.colorbar(self.frame, cax=cax)
            self.update_colorbar(self.frame)
            self.handler.bind('frame_cmapped', self.update_colorbar)
            self.handler.bind('frame_shown', self.update_colorbar)
        else:
            self.message("- A frame must exist to create a colorbar.")

    ## --------------------------------
    ## matplotlib interface.
    ## --------------------------------

    def on_pick(self, evt):  # <matplotlib.backend_bases.PickEvent>
        """Pickup image and other arts.
        Called (maybe) after mouse buttons are pressed.
        """
        ## canvas 全体に有効だが，分割された axes (colorbar 領域など) は無効．
        ## image - plot が重なっている場合，plot -> image の順に呼び出される．
        ## 多重呼び出しが起きないように __isPicked フラグで排他制御する．
        
        if evt.mouseevent.button != 1 or not evt.artist.get_visible():
            return
        
        if not evt.mouseevent.inaxes:
            return
        
        ## 画像が選択された場合．
        if evt.artist in self.__Arts:
            if self.__isPicked:
                self.__isPicked = None  # release pick guard
            else:
                self.handler('image_picked', evt)
        
        ## その他のプロットが選択された場合．
        else:
            if evt.artist is self.marked:
                self.__isPicked = 'mark'  # image pick gurad
                self.handler('mark_picked', evt)
                
            elif evt.artist is self.rected:
                self.__isPicked = 'region'  # image pick gurad
                self.handler('region_picked', evt)
                
            elif evt.artist is self.selected:
                if (self.selector.shape[1] < 2       # single selector
                  or wx.GetKeyState(wx.WXK_SHIFT)):  # or polygon mode
                    return
                self.__isPicked = 'line'  # image pick gurad
                self.handler('line_picked', evt)
            else:
                self.__isPicked = 'art'
                MatplotPanel.on_pick(self, evt)  # [art_picked]
        
        self.canvas.draw_idle()

    def on_picker_lock(self, evt):
        self.__isPicked = True

    def on_picker_unlock(self, evt):
        self.__isPicked = False

    def OnImagePicked(self, evt):  # <matplotlib.backend_bases.PickEvent>
        x = evt.mouseevent.xdata
        y = evt.mouseevent.ydata
        nx, ny = self.frame.xytopixel(x, y)
        evt.ind = (ny, nx)
        self.selector = self.frame.xyfrompixel(nx, ny)

    def _inaxes(self, evt):
        try:
            return evt.inaxes is not self.axes  # <matplotlib.backend_bases.MouseEvent>
        except AttributeError:
            return None  # <wx._core.KeyEvent>

    ## --------------------------------
    ## Pan/Zoom actions (override).
    ## --------------------------------
    ## antialiased, nearest, bilinear, bicubic, spline16,
    ## spline36, hanning, hamming, hermite, kaiser, quadric,
    ## catrom, gaussian, bessel, mitchell, sinc, lanczos, or none.
    interpolation_mode = 'bilinear'

    def OnDraw(self, evt):
        """Called before canvas.draw (overridden)."""
        if not self.interpolation_mode:
            return
        frame = self.frame
        if frame:
            ## [dots/pix] = [dots/u] * [u/pix]
            dots = self.ddpu[0] * frame.unit * frame.binning
            
            if frame.get_interpolation() == 'nearest' and dots < 1:
                frame.set_interpolation(self.interpolation_mode)
                
            elif frame.get_interpolation() != 'nearest' and dots > 1:
                frame.set_interpolation('nearest')

    def OnMotion(self, evt):
        """Called when mouse moves in axes (overridden)."""
        if self.selector.shape[1] < 2:
            self.trace_point(evt.xdata, evt.ydata)

    def OnPageDown(self, evt):
        """Next page."""
        i = self.__index
        if i is not None and i < len(self)-1:
            self.select(i + 1)

    def OnPageUp(self, evt):
        """Previous page."""
        i = self.__index
        if i is not None and i > 0:
            self.select(i - 1)

    def OnHomePosition(self, evt):
        self.fit_to_axes()

    def OnEscapeSelection(self, evt):
        xs, ys = self.selector
        del self.selector
        if len(xs) > 1:
            self.handler('line_removed', self.frame)

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
    ## Selector interface.
    ## --------------------------------

    def calc_point(self, x, y, centred=True, inaxes=False):
        """Computes the nearest pixelated point from a point (x, y).
        If centred, correct the points to the center of the nearest pixel.
        If inaxes, restrict the points in image area.
        """
        frame = self.frame
        if isinstance(x, (list, tuple)):
            x = np.array(x)
            y = np.array(y)
        l,r,b,t = frame.get_extent()
        if inaxes:
            x[x < l] = l
            x[x > r] = r
            y[y < b] = b
            y[y > t] = t
        nx, ny = frame.xytopixel(x, y)
        ux, uy = frame.xy_unit
        if centred:
            x = l + (nx + 0.5) * ux
            y = t - (ny + 0.5) * uy
            if inaxes:
                x[x > r] -= ux
                y[y < b] += uy
        else:
            x = l + nx * ux
            y = t - ny * uy
        return (x, y)

    def calc_shiftpoint(self, xo, yo, x, y, centred=True):
        """Restrict point (x, y) from (xo, yo) in pi/8 step angles.
        If centred, correct the point to the center of the nearest pixel.
        """
        dx, dy = x-xo, y-yo
        L = np.hypot(dy, dx)
        a = np.arctan2(dy, dx)
        aa = np.linspace(-pi, pi, 9) + pi/8  # 角度の検索範囲
        k = np.searchsorted(aa, a)
        x = xo + L * np.cos(aa[k] - pi/8)
        y = yo + L * np.sin(aa[k] - pi/8)
        return self.calc_point(x, y, centred)

    def OnSelectorAppend(self, evt):
        xs, ys = self.selector
        x, y = self.calc_point(evt.xdata, evt.ydata)
        self.selector = np.append(xs, x), np.append(ys, y)
        self.handler('line_drawn', self.frame)

    def OnDragLock(self, evt):
        pass

    def OnDragBegin(self, evt):
        if not self.frame or self._inaxes(evt):
            self.handler('quit', evt)
            return
        org = self.p_event  # the last pressed
        self.__lastpoint = self.calc_point(org.xdata, org.ydata)
        self.__orgpoints = self.selector

    def OnDragMove(self, evt, shift=False):
        x, y = self.calc_point(evt.xdata, evt.ydata)
        xo, yo = self.__lastpoint
        if shift:
            x, y = self.calc_shiftpoint(xo, yo, x, y)
        self.selector = np.append(xo, x), np.append(yo, y)
        self.handler('line_draw', self.frame)

    def OnDragShiftMove(self, evt):
        self.OnDragMove(evt, shift=True)

    def OnDragEscape(self, evt):
        self.selector = self.__orgpoints
        self.handler('line_draw', self.frame)
        
    def OnDragEnd(self, evt):
        x, y = self.calc_point(evt.xdata, evt.ydata)
        xo, yo = self.__lastpoint
        if x == xo and y == yo:
            self.selector = ([x], [y])
        self.handler('line_drawn', self.frame)

    ## --------------------------------
    ## Selector + Line interface.
    ## --------------------------------

    def OnLineSelected(self, evt):
        k = evt.ind[0]
        x = evt.mouseevent.xdata
        y = evt.mouseevent.ydata
        xs, ys = evt.artist.get_data(orig=0)
        dots = np.hypot(x-xs[k], y-ys[k]) * self.ddpu[0]
        self.__linesel = k if dots < 8 else None

    def OnLineDeselected(self, evt):  # <matplotlib.backend_bases.PickEvent>
        self.__linesel = None

    def OnLineDragBegin(self, evt):
        if not self.frame or self._inaxes(evt):
            self.handler('quit', evt)
            return
        org = self.p_event  # the last pressed
        self.__lastpoint = self.calc_point(org.xdata, org.ydata)
        self.__orgpoints = self.selector

    def OnLineDragMove(self, evt, shift=False):
        x, y = self.calc_point(evt.xdata, evt.ydata)
        xc, yc = self.__lastpoint
        xo, yo = self.__orgpoints
        j = self.__linesel
        if j is not None:
            if shift:
                i = j-1 if j else 1
                xo, yo = xo[i], yo[i]  # となりの点を基準とする
                x, y = self.calc_shiftpoint(xo, yo, x, y)
            xs, ys = self.selector
            xs[j], ys[j] = x, y
            self.selector = (xs, ys)
            self.handler('line_draw', self.frame)
        else:
            xs = xo + (x - xc)
            ys = yo + (y - yc)
            self.selector = (xs, ys)
            self.handler('line_move', self.frame)

    def OnLineDragShiftMove(self, evt):
        self.OnLineDragMove(evt, shift=True)

    def OnLineDragEscape(self, evt):
        self.selector = self.__orgpoints
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
        if self.selector.size and self.frame:
            ux, uy = self.frame.xy_unit
            du = {
                'up' : (0, +uy),
              'down' : (0, -uy),
              'left' : (-ux, 0),
             'right' : (+ux, 0),
            }
            self.selector += np.resize(du[evt.key], (2,1))
            self.handler('line_move', self.frame)

    def OnLineShiftEnd(self, evt):
        self.handler('line_moved', self.frame)

    ## --------------------------------
    ## Marker interface.
    ## --------------------------------

    ## Limit number of markers to display 最大(表示)数を制限する．
    maxnum_markers = 1000

    @property
    def markers(self):
        """Marked points data array [[x],[y]]."""
        xm, ym = self.marked.get_data(orig=0)
        return np.array((xm, ym))

    @markers.setter
    def markers(self, v):
        x, y = v
        if not hasattr(x, '__iter__'):
            x, y = [x], [y]
        elif len(x) > self.maxnum_markers:
            self.message("- Got too many markers ({}) to plot".format(len(x)))
            return
        self.marked.set_data(x, y)
        self.__marksel = []
        self.update_mark_art()
        self.handler('mark_drawn', self.frame)

    @markers.deleter
    def markers(self):
        if self.markers.size:
            self.marked.set_data([], [])
            self.__marksel = []
            self.update_mark_art()
            self.handler('mark_removed', self.frame)

    def get_current_mark(self):
        """Currently selected mark."""
        xm, ym = self.marked.get_data(orig=0)
        return np.take((xm, ym), self.__marksel, axis=1)

    def set_current_mark(self, x, y):
        xm, ym = self.marked.get_data(orig=0)
        j = self.__marksel
        if j:
            xm[j], ym[j] = x, y
            self.marked.set_data(xm, ym)
            self.update_mark_art(j, xm[j], ym[j])
        else:
            n = len(xm)
            k = len(x) if hasattr(x, '__iter__') else 1
            self.__marksel = list(range(n, n+k))
            xm, ym = np.append(xm, x), np.append(ym, y)
            self.marked.set_data(xm, ym)
            self.marked.set_visible(1)
            self.update_mark_art()
        self.selector = (x, y)

    def del_current_mark(self):
        j = self.__marksel
        if j:
            xm, ym = self.marked.get_data(orig=0)
            xm, ym = np.delete(xm, j), np.delete(ym, j)
            self.__marksel = []
            self.marked.set_data(xm, ym)
            n = len(xm)
            self.__marksel = [j[-1] % n] if n > 0 else []
            self.update_mark_art()

    def update_mark_art(self, *args):
        if args:
            for k, x, y in zip(*args):
                art = self.__markarts[k]  # art の再描画処理をして終了
                art.xy = x, y
            self.draw(self.marked)
            return
        for art in self.__markarts:  # or reset all arts
            art.remove()
        self.__markarts = []
        if self.marked.get_visible() and self.handler.current_state in (MARK, MARK+DRAGGING):
            N = self.maxnum_markers
            xm, ym = self.marked.get_data(orig=0)
            for k, (x, y) in enumerate(zip(xm[:N], ym[:N])):
                self.__markarts.append(
                  self.axes.annotate(k,  # <matplotlib.text.Annotation>
                    xy=(x,y), xycoords='data',
                    xytext=(6,6), textcoords='offset points',
                    bbox=dict(boxstyle="round", fc=(1,1,1,), ec=(1,0,0,)),
                    color='red', size=7,  # fontsize=8,
                  )
                )
            self.trace_point(*self.get_current_mark(), type=MARK)
        self.draw(self.marked)

    def OnMarkAppend(self, evt):
        xs, ys = self.selector
        if not self.__marksel and len(xs) > 0:
            self.set_current_mark(xs, ys)
            self.handler('mark_drawn', self.frame)
        self.update_mark_art()

    def OnMarkRemove(self, evt):
        if self.__marksel:
            self.del_current_mark()
            self.handler('mark_removed', self.frame)

    def OnMarkSelected(self, evt):  # <matplotlib.backend_bases.PickEvent>
        k = evt.ind[0]
        if evt.mouseevent.key == 'shift':  # 多重マーカー選択
            if k not in self.__marksel:
                self.__marksel += [k]
        else:
            self.__marksel = [k]
        self.update_mark_art()
        self.selector = self.get_current_mark()
        if self.selector.shape[1] > 1:
            self.handler('line_drawn', self.frame)  # 多重マーカー選択時

    def OnMarkDeselected(self, evt):  # <matplotlib.backend_bases.PickEvent>
        self.__marksel = []
        self.update_mark_art()

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
                'up' : (0,  uy),
              'down' : (0, -uy),
              'left' : (-ux, 0),
             'right' : ( ux, 0),
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
        self.selector = (xs, ys)
        self.trace_point(xs, ys, type=MARK)
        self.draw()

    def OnMarkSkipNext(self, evt):
        n = self.markers.shape[1]
        j = self.__marksel
        if j:
            self.next_mark((j[-1]+1) % n)
        elif n:
            self.next_mark(0)

    def OnMarkSkipPrevious(self, evt):
        n = self.markers.shape[1]
        j = self.__marksel
        if j:
            self.next_mark((j[-1]-1) % n)
        elif n:
            self.next_mark(-1)

    ## --------------------------------
    ## Region interface.
    ## --------------------------------

    @property
    def region(self):
        """Cropped rectangle points data array [[l,r], [b,t]]."""
        x, y = self.rected.get_data(orig=0)
        if len(x) and len(y):
            l, r = min(x), max(x)
            b, t = min(y), max(y)
            return np.array(((l,r), (b,t)))
        return np.resize(0., (2, 0))

    @region.setter
    def region(self, v):
        x, y = v
        if len(x) > 1:
            self.set_current_rect(x, y)
            self.handler('region_drawn', self.frame)

    @region.deleter
    def region(self):
        if self.region.size:
            self.del_current_rect()
            self.handler('region_removed', self.frame)

    def get_current_rect(self):
        """Currently selected region."""
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
            ## Modify range so that it does not exceed the extent.
            w, h = xb-xa, yb-ya
            if xa < l: xa, xb = l, l+w
            if xb > r: xa, xb = r-w, r
            if ya < b: ya, yb = b, b+h
            if yb > t: ya, yb = t-h, t
        x = [xa, xb, xb, xa, xa]
        y = [ya, ya, yb, yb, ya]
        self.rected.set_data(x, y)
        self.rected.set_visible(1)
        self.update_rect_art()

    def del_current_rect(self):
        self.__rectsel = []
        self.rected.set_data([], [])
        self.rected.set_visible(0)
        self.update_rect_art()

    def update_rect_art(self, *args):
        if args:
            art = self.__rectarts  # art の再描画処理をして終了
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
                    patches.Polygon(list(zip(x, y)),
                      color='red', ls='solid', lw=1/2, ec='white', alpha=0.2)
                  )
                )
            self.trace_point(x, y, type=REGION)
        self.draw(self.rected)

    def OnRegionCenter(self, evt):
        if self.region.size and self.frame:
            (l,r), (b,t) = self.region
            c = np.array(((l+r)/2, (b+t)/2))
            self.region += self.frame.center - c[:,None]

    def OnRegionAppend(self, evt):
        xs, ys = self.selector
        if len(xs) > 0 and self.frame:
            ux, uy = self.frame.xy_unit
            xs = (xs.min()-ux/2, xs.max()+ux/2)
            ys = (ys.max()+uy/2, ys.min()-uy/2)
            self.set_current_rect(xs, ys)
            self.update_rect_art()
            self.handler('region_drawn', self.frame)

    def OnRegionRemove(self, evt):
        if self.__rectsel:
            self.del_current_rect()
            self.handler('region_removed', self.frame)
        self.set_wxcursor(wx.CURSOR_ARROW)

    def OnRegionSelected(self, evt):  # <matplotlib.backend_bases.PickEvent>
        k = evt.ind[0]
        x = evt.mouseevent.xdata
        y = evt.mouseevent.ydata
        xs, ys = evt.artist.get_data(orig=0)
        dots = np.hypot(x-xs[k], y-ys[k]) * self.ddpu[0]
        self.__rectsel = [k] if dots < 8 else [0,1,2,3,4]  # リージョンの全選択
        self.update_rect_art()

    def OnRegionDeselected(self, evt):  # <matplotlib.backend_bases.PickEvent>
        self.__rectsel = []
        self.update_rect_art()
        self.set_wxcursor(wx.CURSOR_ARROW)

    def OnRegionDragBegin(self, evt):
        if not self.frame or self._inaxes(evt):
            self.handler('quit', evt)
            return
        org = self.p_event  # the last pressed
        self.__lastpoint = self.calc_point(org.xdata, org.ydata, centred=False)
        if not self.__rectsel:
            x, y = self.__lastpoint
            self.set_current_rect((x, x), (y, y))  # start new region
        self.__orgpoints = self.get_current_rect()

    def OnRegionDragMove(self, evt, shift=False, meta=False):
        x, y = self.calc_point(evt.xdata, evt.ydata, centred=False)
        xs, ys = self.get_current_rect()
        j = self.__rectsel  # corner-drag[1] or region-drag[4]
        if len(j) == 1:
            k = (j[0] + 2) % 4  # 選択された一点の対角点
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
            self.set_current_rect((xo, x), (yo, y))
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
        # self.__rectsel = [0,1,2,3,4]  # リージョンの全選択
        self.handler('region_drawn', self.frame)

    def OnRegionShift(self, evt):
        j = self.__rectsel
        if j and self.frame:
            ux, uy = self.frame.xy_unit
            du = {
                'up' : (0,  uy),
              'down' : (0, -uy),
              'left' : (-ux, 0),
             'right' : ( ux, 0),
            }
            dp = du[evt.key]
            p = self.get_current_rect().T
            if len(j) == 1:
                i = j[0]         # 選択されている点
                k = (i + 2) % 4  # 選択された一点の対角点
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
        if self.region.size:
            (l,r), (b,t) = self.region
            d = self.rected.pickradius / self.ddpu[0]
            x0 = l+d < x < r-d
            y0 = b+d < y < t-d
            x1 = l-d < x < l+d
            x2 = r-d < x < r+d
            y1 = b-d < y < b+d
            y2 = t-d < y < t+d
            if x0 and y0:
                # self.set_wxcursor(wx.CURSOR_HAND)  # insdie
                self.set_wxcursor(wx.CURSOR_ARROW)
            elif (x1 or x2) and y0:
                # self.set_wxcursor(wx.CURSOR_SIZEWE)  # on-x-edge
                self.set_wxcursor(wx.CURSOR_SIZING)
            elif x0 and (y1 or y2):
                # self.set_wxcursor(wx.CURSOR_SIZENS)  # on-y-edge
                self.set_wxcursor(wx.CURSOR_SIZING)
            elif x1 and y1 or x2 and y2:
                self.set_wxcursor(wx.CURSOR_SIZENESW)  # on-NE/SW-corner
            elif x1 and y2 or x2 and y1:
                self.set_wxcursor(wx.CURSOR_SIZENWSE)  # on-NW/SE-corner
            else:
                self.set_wxcursor(wx.CURSOR_ARROW)  # outside
