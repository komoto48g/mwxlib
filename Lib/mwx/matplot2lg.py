#! python3
"""mwxlib line plot for images.
"""
from itertools import chain
import io
import wx

from matplotlib import patches
import numpy as np
from scipy import signal
from scipy import ndimage

from . import framework as mwx
from .utilus import funcall as _F
from .controls import Clipboard
from .matplot2 import MatplotPanel
from .matplot2 import NORMAL, MARK, LINE, REGION


class LinePlot(MatplotPanel):
    """Line plot 1D base panel.
    
    region : selected range (l,r) on the plot
    """
    def __init__(self, *args, **kwargs):
        MatplotPanel.__init__(self, *args, **kwargs)
        
        self.handler.update({  # DNA<LinePlot>
            None : {
                   'region_set' : [None],
                 'region_unset' : [None],
                'canvas_resize' : [None, lambda v: self.draw()]
            },
            NORMAL : {
               'escape pressed' : (NORMAL, self.OnEscapeSelection),
               'delete pressed' : (NORMAL, self.OnEscapeSelection),
                  'M-a pressed' : (NORMAL, self.OnHomePosition),
                  'C-a pressed' : (NORMAL, self.OnHomePosition),
             'Lbutton dblclick' : (NORMAL, self.OnEscapeSelection, self.OnDragLock),
             '*Lbutton pressed' : (NORMAL, self.OnDragLock),
                 '*Ldrag begin' : (REGION, self.OnDragBegin),
            },
            REGION : {
                  '*Ldrag move' : (REGION, self.OnDragMove),
                   '*Ldrag end' : (NORMAL, self.OnDragEnd),
            },
        })
        self.modeline.Show(0)
        
        self.axes.grid(True)
        self.axes.tick_params(labelsize='x-small')
        
        self._region = None
        self._annotations = []
        
        ## MPL_VERSION >= (3,9,0)
        ## axhspan and axvspan now return Rectangles, not Polygons.
        
        # <matplotlib.patches.Polygon>
        # <matplotlib.patches.Rectangle>
        self._vspan = self.axes.axvspan(0, 0,
            color='none', ls='dashed', lw=1, ec='black', visible=0, zorder=2)

    @property
    def overlay_artists(self):
        return [self.selected,
                self._vspan, *self._annotations,
                ]

    ## The limit for dragging region.
    boundary = None

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, v):
        if v is not None:
            a = min(v)
            b = max(v)
            if self.boundary is not None:
                l, r = self.boundary
                if   a < l: a = l
                elif a > r: a = r
                if   b < l: b = l
                elif b > r: b = r
            v = np.array((a, b))
            self._vspan.set_visible(1)
            try:
                self._vspan.set_x(a)
                self._vspan.set_width(b-a)
            except AttributeError:
                self._vspan.set_xy(((a,0), (a,1), (b,1), (b,0)))
            self.handler('region_set', self.frame)
        else:
            self._vspan.set_visible(0)
            self.handler('region_unset', self.frame)
        self._region = v
        self.annotate()

    @region.deleter
    def region(self):
        self.region = None

    def annotate(self):
        for art in self._annotations:
            art.remove()
        del self._annotations[:]
        
        # <matplotlib.text.Annotation>
        def _A(v, xy, xytext, xycoords='data', textcoords='offset points', **arrowprops):
            return self.axes.annotate(
                    '' if v is None else '{:g}'.format(v),
                    xy, xytext, xycoords, textcoords, arrowprops, size='small')
        
        if self.region is not None:
            a, b = self.region
            x = (b + a) / 2
            y = self.ylim[0] + 20/self.ddpu[1]
            if (b - a) > 60/self.ddpu[0]:
                p = _A(b-a, (x,y), (-20,8), arrowstyle='-')  # wide space
            else:
                p = _A(b-a, (x,y), (16,16), arrowstyle='-',  # narrow space
                       connectionstyle="angle,angleA=0,angleB=90,rad=8")
            self._annotations = [
                _A(a, (a,y), (-54,-3), arrowstyle='->'),
                _A(b, (b,y), (+16,-3), arrowstyle='->'),
                _A(None, (a,y), (b,y), textcoords='data', arrowstyle='<->'),
                p,
            ]

    ## --------------------------------
    ## Region/Drag actions (override).
    ## --------------------------------

    def _test_region(self, evt):
        if self.region is not None:
            x = evt.xdata
            a, b = self.region
            d = 4 / self.ddpu[0]
            if   a+d < x < b-d: return 1  # insdie
            elif a-d < x < a+d: return 2  # left-edge
            elif b-d < x < b+d: return 3  # right-edge
            else: return 0  # outside

    def OnMotion(self, evt):
        MatplotPanel.OnMotion(self, evt)
        
        v = self._test_region(evt)
        if v == 1:
            self.set_wxcursor(wx.CURSOR_HAND)  # insdie
        elif v in (2,3):
            self.set_wxcursor(wx.CURSOR_SIZEWE)  # on-edge
        else:
            self.set_wxcursor(wx.CURSOR_ARROW)  # outside or None

    def OnDragLock(self, evt):
        self._lastpoint = evt.xdata
        self._selection = self._test_region(evt)

    def OnDragBegin(self, evt):
        v = self._selection
        if v == 1:
            self.set_wxcursor(wx.CURSOR_HAND)  # inside
        elif v == 2:
            self.set_wxcursor(wx.CURSOR_SIZEWE)  # left-edge
            self._lastpoint = self.region[1]     # set origin right
        elif v == 3:
            self.set_wxcursor(wx.CURSOR_SIZEWE)  # right-edge
            self._lastpoint = self.region[0]     # set origin left
        else:
            self.set_wxcursor(wx.CURSOR_SIZEWE)  # outside
        self.cursor.visible = False

    def OnDragMove(self, evt):
        x = evt.xdata
        if self._selection != 1:
            l, r = self.xbound
            if   x < l: x = l
            elif x > r: x = r
            self.region = (self._lastpoint, x)
        elif self.region is not None:
            a, b = self.region
            d = x - self._lastpoint
            if self.boundary is not None:
                l, r = self.boundary
                if a+d < l:
                    self.region = (l, l+b-a)
                elif b+d > r:
                    self.region = (r-b+a, r)
                else:
                    self.region = (a+d, b+d)
                    self._lastpoint = x
            else:
                self.region = (a+d, b+d)
                self._lastpoint = x
        else:
            self.message("- No region.")
        self.draw_overlay()  # Callback instead of invisible cursor.

    def OnDragEnd(self, evt):
        self.set_wxcursor(wx.CURSOR_ARROW)
        self.cursor.visible = True

    def OnEscapeSelection(self, evt):
        MatplotPanel.OnEscapeSelection(self, evt)
        
        self.set_wxcursor(wx.CURSOR_ARROW)
        self.cursor.visible = True
        self.region = None


class Histogram(LinePlot):
    """LinePlot panel for histogram (Multi-graph : Single-frame).
    
    frame.image <uint8> (buffer ではない) を参照して，ヒストグラムをプロットする．
    常に整数ビット画像となるので，高速なビンづめ法で計算する．
    """
    def __init__(self, *args, **kwargs):
        LinePlot.__init__(self, *args, **kwargs)
        
        self.handler.update({  # DNA<Histogram>
            NORMAL : {
                 'ctrl pressed' : (NORMAL, ),  # Pan prohibits
                'space pressed' : (NORMAL, ),  # 〃
                    'z pressed' : (NORMAL, ),  # Zoom prohibits
            },
        })
        self.context = {  # DNA<GraphPlot>
            None: {
                 'frame_shown' : [None, self.hreplot],
              'frame_selected' : [None, self.hreplot],
              'frame_modified' : [None, self.hplot],
            }
        }
        self.modeline.Show(0)
        
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self._views = []    # A list of attached view <matplot2g.GraphPlot>.
        self._frame = None  # Reference to the current frame.
        
        # <matplotlib.lines.Line2D>
        self._plot, = self.axes.plot([], [], lw=1, color='c', alpha=1)
        
        # <matplotlib.patches.Polygon>
        self._fill = patches.Polygon([(0,0)], color='c', alpha=1)
        self.axes.add_patch(self._fill)

    def OnDestroy(self, evt):
        for view in self._views:
            self.detach(view)
        evt.Skip()

    def attach(self, view):
        if view not in self._views:
            self._views.append(view)
            view.handler.append(self.context)

    def detach(self, view):
        if view in self._views:
            self._views.remove(view)
            view.handler.remove(self.context)

    @property
    def boundary(self):
        return [0, 255]

    def calc(self, frame):
        BINS = 256
        img = frame.image
        if img.dtype == np.uint8:
            ## 整数ビット画像は，高速なビンづめ法で計算する．
            hist = np.bincount(img.ravel(), minlength=BINS)
            bins = np.arange(BINS)
        else:
            ## hist は [min:max] 段階 (256 BINS) で保持されている．
            ## bins は 端数含め [0:BINS] (257 コ) あるので１個減す．
            hist, bins = np.histogram(img, BINS)
            bins = np.linspace(img.min(), img.max(), BINS)
        return bins, hist

    def hplot(self, frame):
        self._frame = frame  # Update reference of the frame.
        if frame:
            x, y = frame.__data = self.calc(frame)  # histogram_data buffer
            self._plot.set_data(x, y)
            self.xlim = x.min(), x.max()
            self.ylim = 0, y.max()
            self.region = None
            self.draw()

    def hreplot(self, frame):
        self._frame = frame  # Update reference of the frame.
        if frame:
            try:
                x, y = frame.__data  # Reuse cached data.
            except Exception:
                x, y = frame.__data = self.calc(frame)  # new histogram_data buffer
            
            self._plot.set_data(x, y)
            self.xlim = x.min(), x.max()
            self.ylim = 0, y.max()
            
            a, b = frame.clim
            if a != self.xlim[0] or b != self.xlim[1]:
                self.region = (a, b)
            else:
                self.region = None
        else:
            self._plot.set_data([], [])
            self.region = None
        self.draw()

    def writeln(self):
        if not self.modeline.IsShown():
            return
        frame = self._frame
        if frame:
            x, y = frame.__data
            if self.region is not None:
                i, j = x.searchsorted(self.region)
            else:
                i, j = np.uint8(self.xlim)
            self.modeline.SetLabel(
                "[--] ---- {name} ({type}:{mode}) [{}:{}]".format(i, j,
                    name=frame.name,
                    type=frame.buffer.dtype,
                    mode='-',
                ))
        else:
            self.modeline.SetLabel("")

    def annotate(self):
        """Do nothing (override)."""
        pass

    ## --------------------------------
    ## Region/Drag actions (override).
    ## --------------------------------

    def OnDraw(self, evt):
        """Draw plots and fills (override).
        Call each time the drawing should be updated.
        """
        if self._frame:
            x, y = self._frame.__data
            if len(x) > 1:
                if self.region is not None:
                    i, j = x.searchsorted(self.region)
                else:
                    i, j = (0, -1)
                self._fill.set_xy(list(chain([(x[i], 0)], zip(x[i:j], y[i:j]), [(x[j-1], 0)])))
            else:
                self._fill.set_xy([(0, 0)])
        else:
            self._fill.set_xy([(0, 0)])
        self.writeln()

    def OnDragEnd(self, evt):
        LinePlot.OnDragEnd(self, evt)
        
        if self._frame:
            self.xbound = self.region  # 拡大表示したのち region 消去
            self.region = None
            self.toolbar.push_current()
            self.draw()
            self._frame.clim = self.xlim
            self._frame.parent.draw()

    def OnEscapeSelection(self, evt):
        LinePlot.OnEscapeSelection(self, evt)
        
        if self._frame:
            self._frame.clim = self.xlim
            self._frame.parent.draw()
            self.hreplot(self._frame)


class LineProfile(LinePlot):
    """LinePlot panel for line profile (Multi-graph : Single-frame).
    """
    def __init__(self, *args, **kwargs):
        LinePlot.__init__(self, *args, **kwargs)
        
        self.handler.update({  # DNA<LineProfile>
            None : {
                 'left pressed' : [None, self.OnRegionShift],
                'right pressed' : [None, self.OnRegionShift],
                 '[+-] pressed' : [None, self.OnLineWidth],  # [+-] using numpad
               'S-[;-] pressed' : [None, self.OnLineWidth],  # [+-] using JP-keyboard
            },
            NORMAL : {
            'S-Lbutton pressed' : (LINE, self.OnDragLock, self.OnRegionLock),
            'M-Lbutton pressed' : (MARK, self.OnDragLock, self.OnMarkPeaks),
             '*Lbutton pressed' : (NORMAL, self.OnDragLock),
                 '*Ldrag begin' : (REGION, self.OnDragBegin),
            },
            REGION : {
                 'S-Ldrag move' : (REGION+LINE, self.OnRegionLock, self.OnDragLineBegin),
                 'M-Ldrag move' : (REGION+MARK, self.OnMarkPeaks, self.OnMarkSelectionBegin),
                  '*Ldrag move' : (REGION, self.OnDragMove, self.OnDragTrace),
                   '*Ldrag end' : (NORMAL, self.OnDragEnd),
            },
            LINE: {
                   '* released' : (NORMAL, ),
                'S-Ldrag begin' : (REGION+LINE, self.OnDragLineBegin),
            },
            REGION+LINE : {
                 'S-Ldrag move' : (REGION+LINE, self.OnRegionLock),
                  '*Ldrag move' : (REGION, self.OnDragMove),
                   '*Ldrag end' : (NORMAL, self.OnDragEnd),
            },
            MARK : {
                   '* released' : (NORMAL, self.OnMarkErase),
                'M-Ldrag begin' : (REGION+MARK, self.OnMarkSelectionBegin),
            },
            REGION+MARK : {
                 'M-Ldrag move' : (REGION+MARK, self.OnMarkSelectionMove),
                  '*Ldrag move' : (REGION, self.OnDragMove),
                   '*Ldrag end' : (NORMAL, self.OnDragEnd),
            },
        })
        self.context = {  # DNA<GraphPlot>
            None: {
                    'line_draw' : [None, self.linplot],
                   'line_drawn' : [None, self.linplot],
                    'line_move' : [None, _F(self.linplot, fit=0)],
                   'line_moved' : [None, _F(self.linplot, fit=0)],
                  'frame_shown' : [None, _F(self.linplot, fit=0)],
               'frame_modified' : [None, _F(self.linplot, fit=0)],
               'frame_selected' : [None, _F(self.linplot, fit=1, force=0)],
            }
        }
        self.modeline.Show(1)
        
        self.menu += [
            (mwx.ID_(210), "&Copy data", "Copy data to clipboard",
                lambda v: self.write_data_to_clipboard()),
            (),
            (mwx.ID_(211), "Logic length", "Set axis-unit in logic base", wx.ITEM_RADIO,
                lambda v: self.set_logic(1),
                lambda v: v.Check(self._logicp)),
                
            (mwx.ID_(212), "Pixel length", "Set axis-unit in pxiel base", wx.ITEM_RADIO,
                lambda v: self.set_logic(0),
                lambda v: v.Check(not self._logicp)),
        ]
        
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        self._views = []    # A list of attached view <matplot2g.GraphPlot>.
        self._frame = None  # Reference to the current frame.
        
        # <matplotlib.lines.Line2D>
        self._plot, = self.axes.plot([], [], lw=0.1, color='c', alpha=1,
                                      picker=True, pickradius=2)
        
        # <matplotlib.patches.Polygon>
        self._fill = patches.Polygon([(0,0)], color='c', alpha=0.8)
        self.axes.add_patch(self._fill)
        
        # <matplotlib.lines.Line2D>
        self._hline = self.axes.axhline(0, color='gray', ls='dashed', lw=1,
                                         visible=0, zorder=2)
        
        self._linewidth = 1  # Line width to integrate [pixel].
        self._logicp = True  # Line axis in logical unit.
        
        self.selected.set_linestyle('')

    @property
    def overlay_artists(self):
        return [self.selected, self._hline,
                self._vspan, *self._annotations,
                ]

    def OnDestroy(self, evt):
        for view in self._views:
            self.detach(view)
        evt.Skip()

    def attach(self, view):
        if view not in self._views:
            self._views.append(view)
            view.handler.append(self.context)

    def detach(self, view):
        if view in self._views:
            self._views.remove(view)
            view.handler.remove(self.context)

    def set_logic(self, p):
        prep = self._logicp
        self._logicp = p = bool(p)
        if self._frame and prep != p:  # Replot if toggled.
            u = self._frame.unit
            ru = u if p else 1/u
            self.xlim *= ru
            x = self._plot.get_xdata(orig=0)
            self._plot.set_xdata(x * ru)
            if self.region is not None:
                self.region *= ru
            sel = self.selector
            self.selector = (sel[0] * ru, sel[1])
            self.draw()

    def set_linewidth(self, w):
        if 0 < w < 256:
            self._linewidth = w
        if self._frame:
            self.linplot(self._frame, fit=0)
        self.writeln()

    @property
    def boundary(self):
        x = self._plot.get_xdata(orig=0)
        if x.size:
            return x[[0,-1]]

    @property
    def plotdata(self):
        """Plotted (xdata, ydata) in single plot."""
        return self._plot.get_data(orig=0)

    def calc_average(self):
        x, y = self.plotdata
        if self.region is not None:
            a, b = self.region
            y = y[(a <= x) & (x <= b)]
        if y.size:
            return y.mean()

    def linplot(self, frame, fit=True, force=True):
        if not force:
            if frame is self._frame:
                return
        self._frame = frame  # Update reference of the frame.
        if frame:
            sel = frame.selector
            if sel.shape[1] < 2:
                return
            if len(frame.buffer.shape) > 2:  # RGB image
                return
            
            xx, yy = sel[:,-2:]  # Get the last 2-selected line.
            nx, ny = frame.xytopixel(xx, yy)  # Converts to pixel [ny,nx]
            lx = nx[1] - nx[0]
            ly = ny[1] - ny[0]
            if lx or ly:
                L = np.hypot(lx, ly)  # pixel length
                nv = (-ly/L, lx/L)    # and norm vector to L
            else:
                L = 0
                nv = (0, 0)
            
            ## ピクセル空間：長さ L, サイズ N 分割でラインプロファイルをとる．
            lw = self._linewidth
            N = int(L) + 1
            xs = np.linspace(nx[0], nx[1], N)
            ys = np.linspace(ny[0], ny[1], N)
            zs = np.zeros(N)
            h, w = frame.buffer.shape[:2]
            for k in np.arange(-(lw-1)/2, (lw+1)/2):
                x = xs + k * nv[0]
                y = ys + k * nv[1]
                mask = (0 <= x) & (x < w) & (0 <= y) & (y < h)
                if any(mask):
                    x = x[mask]
                    y = y[mask]
                    zi = frame.buffer[y.astype(int), x.astype(int)]  # nearest: 速くてそこそこ正確
                    # zi = ndimage.map_coordinates(frame.buffer, np.vstack((y, x)))  # spline: 遅いが正確
                    if zi.dtype in (np.complex64, np.complex128):
                        zi = np.log(1 + abs(zi))
                    zs[mask] += zi
            zs /= lw
            
            if self._logicp:  # axis to logical length  # 論理長さ空間を使用する
                L = np.hypot(xx[1]-xx[0], yy[1]-yy[0])
            
            ls = np.linspace(0, L, N)
            self._plot.set_data(ls, zs)
            self._plot.set_visible(1)
            
            if fit and len(ls) > 1:  # drawing area
                ly = self.ylim
                self.xlim = ls[0], ls[-1]
                self.ylim = ly[0], max(ly[1], max(zs))
        self.draw()

    def writeln(self):
        if not self.modeline.IsShown():
            return
        frame = self._frame
        if frame:
            self.modeline.SetLabel(
                "[--] -{a}- {name} ({type}:{mode}) "
                "[{length}:{width}] {x} [{unit:g}/pix]".format(
                    name=frame.name,
                    type=frame.buffer.dtype,
                    mode="logic" if self._logicp else "pixel",
                    width=self._linewidth,
                    length=len(self.plotdata[0]),
                    unit=frame.unit,
                    x='**' if frame.localunit else '--',
                    a='%%' if not frame.buffer.flags.writeable else '--'
                ))
        else:
            self.modeline.SetLabel("")

    def write_data_to_clipboard(self):
        """Write plot data to clipboard."""
        X, Y = self.plotdata
        with io.StringIO() as o:
            for x, y in zip(X, Y):
                o.write("{:g}\t{:g}\n".format(x, y))
            Clipboard.write(o.getvalue())
            self.message("Write data to clipboard.")

    ## --------------------------------
    ## Region/Drag actions (override).
    ## --------------------------------

    def OnDraw(self, evt):
        """Draw plots and fills (override).
        Call each time the drawing should be updated.
        """
        x, y = self.plotdata
        if x.size:
            self._fill.set_xy(list(chain([(x[0], 0)], zip(x, y), [(x[-1], 0)])))
        self.writeln()

    def OnHomePosition(self, evt):
        """Go back to home position."""
        x, y = self.plotdata
        if x.size and y.size:
            self.xlim = x[0], x[-1]
            self.ylim = 0, y.max()
            self.toolbar.update()
            self.toolbar.push_current()
            self.draw()

    def OnHomeXPosition(self, evt):
        x = self.plotdata[0]
        if x.size:
            self.xlim = x[0], x[-1]
            self.toolbar.push_current()
            self.draw()

    def OnHomeYPosition(self, evt):
        y = self.plotdata[1]
        if y.size:
            self.ylim = 0, y.max()
            self.toolbar.push_current()
            self.draw()

    def OnLineWidth(self, evt):
        n = -2 if evt.key[-1] == '-' else 2
        self.set_linewidth(self._linewidth + n)

    def OnRegionShift(self, evt):
        if self._frame and self.region is not None:
            u = self._frame.unit if self._logicp else 1
            if evt.key == "left": self.region -= u
            if evt.key == "right": self.region += u
            self.draw_overlay()

    def OnEscapeSelection(self, evt):
        self._hline.set_visible(0)
        LinePlot.OnEscapeSelection(self, evt)

    ## --------------------------------
    ## Region-(H)Line/Drag actions.
    ## --------------------------------

    def OnDragLineBegin(self, evt):
        self.set_wxcursor(wx.CURSOR_SIZENS)

    def OnDragTrace(self, evt):
        """Show average value."""
        y = self.calc_average()
        if y is not None:
            self.message(f"ya = {y:g}")

    def OnRegionLock(self, evt):
        """Show FWHM region."""
        x, y = self.plotdata
        if x.size:
            xc, yc = evt.xdata, evt.ydata
            u = x[1] - x[0]  # != frame.unit (斜め線の場合 dx=unit とは限らない)
            v = (y < yc)
            self._hline.set_ydata([yc])
            self._hline.set_visible(1)
            if v.all():
                self.region = None  # all y < yc
            elif v.any():
                xa = x[(x < xc) & v]
                xb = x[(x > xc) & v]
                a = xa[-1] if xa.any() else x[0]  # left-under bound
                b = xb[0] if xb.any() else x[-1]  # right-over bound
                if (b-a-u)/u > 1e-3:
                    if a > x[0]:
                        n = np.where(x == a)[0][0]
                        if y[n] != y[n+1]:
                            a = x[n] + (x[n+1]-x[n]) / (y[n+1]-y[n]) * (yc-y[n])
                    if b < x[-1]:
                        n = np.where(x == b)[0][0] - 1
                        if y[n] != y[n+1]:
                            b = x[n] + (x[n+1]-x[n]) / (y[n+1]-y[n]) * (yc-y[n])
                    self.region = (a, b)
                else:
                    self.region = None
            else:
                self.region = x[[0,-1]]  # all y > yc
            self.message(f"yc = {yc:g}")
            self.draw_overlay()  # Callback instead of invisible cursor.

    ## --------------------------------
    ## Region-Mark/Drag actions.
    ## --------------------------------
    peak_blur_ratio = 0.01
    peak_prominence_ratio = 0.1

    def OnMarkPeaks(self, evt):
        """Set markers on peaks."""
        x, y = self.plotdata
        if x.size > 1:
            # lw = 5
            ux = x[1] - x[0]  # equal spacing length
            lw = max(1, self.peak_blur_ratio * (self.xbound[1] - self.xbound[0]) / ux)
            lp = self.peak_prominence_ratio * (self.ybound[1] - self.ybound[0])
            # window = np.hanning(lw)
            # window = signal.windows.gaussian(lw, std=lw/6)
            # ys = np.convolve(window/window.sum(), y, mode='same')
            ys = ndimage.gaussian_filter1d(y, sigma=lw/6)
            
            maxima, _ = signal.find_peaks(ys, prominence=lp)
            minima, _ = signal.find_peaks(-ys, prominence=lp)
            
            peaks = np.sort(np.append(maxima, minima))
            if peaks.size:
                self.selector = x[peaks], y[peaks]
            self.message(f"Peak detection: blur {lw=:g}, prom {lp=:g}")

    def OnMarkErase(self, evt):
        """Erase markers on peaks."""
        ## del self.selector
        self.OnEscapeSelection(evt)

    def OnMarkSelectionBegin(self, evt):
        org = self.p_event
        xs, ys = self.selector
        xc, yc = org.xdata, org.ydata
        ## xc, yc = evt.xdata, evt.ydata
        if xs.size:
            ld = np.hypot((xs-xc)*self.ddpu[0], (ys-yc)*self.ddpu[1])
            j = np.argmin(ld)
            self._orgpoint = xs[j]
        self.set_wxcursor(wx.CURSOR_SIZEWE)

    def OnMarkSelectionMove(self, evt):
        xs, ys = self.selector
        xc, yc = evt.xdata, evt.ydata
        if xs.size:
            ld = np.hypot((xs-xc)*self.ddpu[0], (ys-yc)*self.ddpu[1])
            j = np.argmin(ld)
            if ld[j] < 20:  # check display-dot distance, snap to the nearest mark
                xc = xs[j]
                yc = ys[j]
                self.message(f"({xc:g}, {yc:g})")
            self.region = (self._orgpoint, xc)
            self.draw_overlay()  # Callback instead of invisible cursor.
