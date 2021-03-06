#! python3
# -*- coding: utf-8 -*-
"""mwxlib line plot for image

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from itertools import chain
import sys
import wx
try:
    import framework as mwx
    from utilus import funcall as _F
    from matplot2 import MatplotPanel
    from matplot2 import NORMAL, MARK, LINE, REGION
except ImportError:
    from . import framework as mwx
    from .utilus import funcall as _F
    from .matplot2 import MatplotPanel
    from .matplot2 import NORMAL, MARK, LINE, REGION
from matplotlib import patches
import numpy as np
from scipy import signal
## from scipy import ndimage as ndi


class LinePlot(MatplotPanel):
    """Line plot 1D base panel
    
    region : selected range (l,r) on the plot
    """
    def __init__(self, *args, **kwargs):
        MatplotPanel.__init__(self, *args, **kwargs)
        
        self.handler.update({ # DNA<LinePlot>
            NORMAL : {
               'escape pressed' : (NORMAL, self.OnEscapeSelection),
               'delete pressed' : (NORMAL, self.OnEscapeSelection),
               'Lbutton dclick' : (NORMAL, self.OnEscapeSelection),
             '*Lbutton pressed' : (NORMAL, self.OnDragLock),
                 '*Ldrag begin' : (REGION, self.OnDragBegin),
            },
            REGION : {
                  '*Ldrag move' : (REGION, self.OnDragMove),
                   '*Ldrag end' : (NORMAL, self.OnDragEnd),
            },
        })
        self.modeline.Show(0)
    
    def clear(self):
        MatplotPanel.clear(self)
        
        self.cursor.visible = 0
        
        self.axes.grid(True)
        self.axes.tick_params(labelsize='x-small')
        
        self.__region = None
        self.__annotations = []
        
        #<matplotlib.patches.Polygon>
        self.__vspan = self.axes.axvspan(0, 0,
            color='none', ls='dashed', lw=1, ec='black', visible=0, zorder=2)
    
    ## the limit for dragging region
    boundary = None
    
    @property
    def region(self):
        return self.__region
    
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
            self.__vspan.set_visible(1)
            self.__vspan.set_xy(((a,0), (a,1), (b,1), (b,0)))
        else:
            self.__vspan.set_visible(0)
        self.__region = v
        
    @region.deleter
    def region(self):
        self.region = None
    
    def annotate(self):
        for art in self.__annotations:
            art.remove()
        self.__annotations = []
        
        #<matplotlib.text.Annotation>
        def annotation(v, xy, xytext,
            xycoords='data', textcoords='offset points', **arrowprops):
            return self.axes.annotate('' if v is None else '{:g}'.format(v),
                    xy, xytext, xycoords, textcoords, arrowprops, size='small')
        
        if self.__region is not None:
            a, b = self.__region
            x = (b + a) / 2
            y = self.ylim[0] + 20/self.ddpu[1]
            if (b - a) > 60/self.ddpu[0]:
                p = annotation(b-a, (x,y), (-20,8), arrowstyle='-') # wide space
            else:
                p = annotation(b-a, (x,y), (16,16), arrowstyle='-', # narrow space
                        connectionstyle="angle,angleA=0,angleB=90,rad=8")
            self.__annotations = [
                annotation(a, (a,y), (-54,-3), arrowstyle='->'),
                annotation(b, (b,y), ( 16,-3), arrowstyle='->'),
                annotation(None, (a,y), (b,y), textcoords='data', arrowstyle='<->'),
                p,
            ]
    
    ## --------------------------------
    ## Motion/Drag actions (override)
    ## --------------------------------
    
    def region_test(self, evt):
        if self.region is not None:
            x = evt.xdata
            a, b = self.region
            d = 4 / self.ddpu[0]
            if   a+d < x < b-d: return 1 # insdie
            elif a-d < x < a+d: return 2 # left-edge
            elif b-d < x < b+d: return 3 # right-edge
            else: return 0 # outside
    
    def OnDraw(self, evt):
        """Called before canvas.draw"""
        self.annotate()
    
    def OnMotion(self, evt):
        MatplotPanel.OnMotion(self, evt)
        
        v = self.region_test(evt)
        if v == 1:
            self.set_wxcursor(wx.CURSOR_HAND) # insdie
        elif v in (2,3):
            self.set_wxcursor(wx.CURSOR_SIZEWE) # on-edge
        else:
            self.set_wxcursor(wx.CURSOR_ARROW) # outside or None
    
    def OnDragLock(self, evt):
        self.__lastpoint = evt.xdata
        self.__selection = self.region_test(evt)
    
    def OnDragBegin(self, evt):
        v = self.__selection
        if v == 1:
            self.set_wxcursor(wx.CURSOR_HAND) # inside
        elif v == 2:
            self.set_wxcursor(wx.CURSOR_SIZEWE) # left-edge
            self.__lastpoint = self.region[1]   # set origin right
        elif v == 3:
            self.set_wxcursor(wx.CURSOR_SIZEWE) # right-edge
            self.__lastpoint = self.region[0]   # set origin left
        else:
            self.set_wxcursor(wx.CURSOR_SIZEWE) # outside
    
    def OnDragMove(self, evt):
        x = evt.xdata
        if self.__selection != 1:
            l, r = self.xbound
            if   x < l: x = l
            elif x > r: x = r
            self.region = (self.__lastpoint, x)
        else:
            a, b = self.region
            d = x - self.__lastpoint
            if self.boundary is not None:
                l, r = self.boundary
                if a+d < l:
                    self.region = (l, l+b-a)
                elif b+d > r:
                    self.region = (r-b+a, r)
                else:
                    self.region = (a+d, b+d)
                    self.__lastpoint = x
            else:
                self.region = (a+d, b+d)
                self.__lastpoint = x
        self.draw()
    
    def OnDragEnd(self, evt):
        self.set_wxcursor(wx.CURSOR_ARROW)
    
    def OnEscapeSelection(self, evt):
        MatplotPanel.OnEscapeSelection(self, evt)
        
        self.set_wxcursor(wx.CURSOR_ARROW)
        self.region = None
        self.draw()


class Histogram(LinePlot):
    """LinePlot panel for histogram (Multi-graph : Single-frame)
    
    frame.image <uint8> (buffer ????????????) ?????????????????????????????????????????????????????????
    ????????????????????????????????????????????????????????????????????????????????????
    
    Attributes:
       __graphs : list of attached graph <matplot2g.GraphPlot>
        __frame : reference to the current frame
    """
    def __init__(self, *args, **kwargs):
        LinePlot.__init__(self, *args, **kwargs)
        
        self.handler.update({ # DNA<Histogram>
            NORMAL : {
                 'ctrl pressed' : (NORMAL, ), # Pan prohibits
                'space pressed' : (NORMAL, ), # ???
                    'z pressed' : (NORMAL, ), # Zoom prohibits
            },
        })
        self.context = { # DNA<GraphPlot>
            None: {
                 'frame_shown' : [ None, self.hreplot ],
              'frame_selected' : [ None, self.hreplot ],
              'frame_modified' : [ None, self.hplot ],
            }
        }
        self.modeline.Show(0)
        
        def destroy(evt):
            for graph in self.__graphs:
                self.detach(graph)
            evt.Skip()
        self.Bind(wx.EVT_WINDOW_DESTROY, destroy)
    
    def clear(self):
        LinePlot.clear(self)
        
        self.__graphs = []
        self.__frame = None
        
        #<matplotlib.lines.Line2D>
        self.__plot, = self.axes.plot([], [], lw=1, color='c', alpha=1)
        
        #<matplotlib.patches.Polygon>
        self.__fil = patches.Polygon([(0,0)], color='c', alpha=1)
        self.axes.add_patch(self.__fil)
    
    def attach(self, *graphs):
        for graph in graphs:
            if graph not in self.__graphs:
                self.__graphs.append(graph)
                graph.handler.append(self.context)
    
    def detach(self, *graphs):
        for graph in graphs:
            if graph in self.__graphs:
                self.__graphs.remove(graph)
                graph.handler.remove(self.context)
    
    @property
    def boundary(self):
        return [0,255]
    
    def calc(self, frame):
        img = frame.image
        if img.dtype == np.uint8:
            ## ??????????????????????????????????????????????????????????????????
            ## image ??? imconvert ????????????????????????????????????buffer ?????????
            ## bins = np.arange(0, img.max()+1)
            hist = np.bincount(img.ravel(), minlength=256)
            bins = np.arange(256)
        else:
            BINS = 256
            ## hist ??? [min:max] ?????? (BINS=256 ???) ????????????????????????
            ## bins ??? ???????????? [0:BINS] (257 ???) ????????????????????????
            hist, bins = np.histogram(img, BINS)
            bins = np.linspace(img.min(), img.max(), BINS)
            
        return bins, hist
    
    def hplot(self, frame):
        self.__frame = frame # update reference of the frame
        if frame:
            x, y = frame.__data = self.calc(frame) # histogram_data buffer
            self.__plot.set_data(x, y)
            self.xlim = x.min(), x.max()
            self.ylim = 0, y.max()
            self.region = None
            self.update_position()
            self.draw()
    
    def hreplot(self, frame):
        self.__frame = frame # update reference of the frame
        if frame:
            try:
                image = self.frmae.image
                h, w = image.shape
                x, y = frame.__data # reuse the data unless,
            except Exception:
                x, y = frame.__data = self.calc(frame) # histogram_data buffer
            
            self.__plot.set_data(x, y)
            self.xlim = x.min(), x.max()
            self.ylim = 0, y.max()
            
            a, b = frame.clim
            if a != self.xlim[0] or b != self.xlim[1]:
                self.region = (a, b)
            else:
                self.region = None
        else:
            self.__plot.set_data([],[])
            self.region = None
        
        self.update_position()
        self.draw()
    
    def writeln(self):
        if not self.modeline.IsShown():
            return
        frame = self.__frame
        if frame:
            x, y = frame.__data
            i, j = x.searchsorted(self.region) if self.region is not None else np.uint8(self.xlim)
            self.modeline.write(
            "[--] ---- {name} ({type}:{mode}) [{bins[0]}:{bins[1]}]".format(
                name = frame.name,
                type = frame.buffer.dtype,
                mode = "bincount",
                bins = (i, j % len(x))))
        else:
            self.modeline.write("")
    
    ## --------------------------------
    ## Motion/Drag actions (override)
    ## --------------------------------
    
    def OnDraw(self, evt):
        """Called before canvas.draw"""
        ## LinePlot.OnDraw(self, evt) ---> do not annotate
        
        if self.__frame:
            x, y = self.__frame.__data
            if len(x) > 1:
                i, j = x.searchsorted(self.region) if self.region is not None else (0,-1)
                self.__fil.set_xy(list(chain([(x[i],0)], zip(x[i:j],y[i:j]), [(x[j-1],0)])))
            else:
                self.__fil.set_xy([(0,0)])
        else:
            self.__fil.set_xy([(0,0)])
        self.writeln()
    
    def OnDragEnd(self, evt):
        LinePlot.OnDragEnd(self, evt)
        
        if self.__frame:
            self.xbound = self.region # ???????????????????????? region ??????
            self.region = None
            self.toolbar.push_current()
            self.draw()
            self.__frame.clim = self.xlim
            self.__frame.parent.draw()
    
    def OnEscapeSelection(self, evt):
        LinePlot.OnEscapeSelection(self, evt)
        self.OnHomePosition(evt)
        
        if self.__frame:
            self.__frame.clim = self.xlim
            self.__frame.parent.draw()
            self.hreplot(self.__frame)


class LineProfile(LinePlot):
    """LinePlot panel for line profile (Multi-graph : Single-frame)
    
    Attributes:
       __graphs : list of attached graph <matplot2g.GraphPlot>
        __frame : reference to the current frame
       __logicp : line axis in logical unit
    __linewidth : line width to integrate [pixel]
    """
    def __init__(self, *args, **kwargs):
        LinePlot.__init__(self, *args, **kwargs)
        
        self.handler.update({ # DNA<LineProfile>
            None : {
                 'left pressed' : [ None, self.OnRegionShift ],
                'right pressed' : [ None, self.OnRegionShift ],
                 '[+-] pressed' : [ None, self.OnLineWidth ], # [+-] using numpad
               'S-[;-] pressed' : [ None, self.OnLineWidth ], # [+-] using JP-keyboard
            },
            NORMAL : {
            'S-Lbutton pressed' : (LINE, self.OnDragLock, self.OnRegionLock),
            'M-Lbutton pressed' : (MARK, self.OnDragLock, self.OnMarkPeaks),
             '*Lbutton pressed' : (NORMAL, self.OnDragLock),
                 '*Ldrag begin' : (REGION, self.OnDragBegin),
            },
            REGION : {
                 'S-Ldrag move' : (REGION+LINE, self.OnRegionLock),
                 'M-Ldrag move' : (REGION+MARK, self.OnMarkPeaks, self.OnMarkSelectionBegin),
                  '*Ldrag move' : (REGION, self.OnDragMove),
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
        self.context = { # DNA<GraphPlot>
            None: {
                    'line_draw' : [ None, self.linplot ],
                   'line_drawn' : [ None, self.linplot ],
                    'line_move' : [ None, _F(self.linplot, fit=0) ],
                   'line_moved' : [ None, _F(self.linplot, fit=0) ],
                  'frame_shown' : [ None, _F(self.linplot, fit=0) ],
               'frame_modified' : [ None, _F(self.linplot, fit=0) ],
               'frame_selected' : [ None, _F(self.linplot, fit=0, force=0) ],
            }
        }
        self.modeline.Show(1)
        
        self.menu += [
            (),
            (mwx.ID_(511), "Logic length", "Set axis-unit in logic base", wx.ITEM_RADIO,
                lambda v: self.set_logic(1),
                lambda v: v.Check(self.__logicp)),
                
            (mwx.ID_(512), "Pixel length", "Set axis-unit in pxiel base", wx.ITEM_RADIO,
                lambda v: self.set_logic(0),
                lambda v: v.Check(not self.__logicp)),
        ]
        
        def destroy(evt):
            for graph in self.__graphs:
                self.detach(graph)
            evt.Skip()
        self.Bind(wx.EVT_WINDOW_DESTROY, destroy)
    
    def clear(self):
        LinePlot.clear(self)
        
        self.__graphs = []
        self.__frame = None
        
        #<matplotlib.lines.Line2D>
        self.__plot, = self.axes.plot([], [], lw=0.1, color='c', alpha=1, picker=True, pickradius=2)
        
        #<matplotlib.patches.Polygon>
        self.__fil = patches.Polygon([(0,0)], color='c', alpha=0.8)
        self.axes.add_patch(self.__fil)
        
        #<matplotlib.lines.Line2D>
        self.__hline = self.axes.axhline(0, color='gray', ls='dashed', lw=1, visible=0, zorder=2)
        
        self.__linewidth = 1
        self.__logicp = True
        
        self.selected.set_linestyle('')
    
    def attach(self, *graphs):
        for graph in graphs:
            if graph not in self.__graphs:
                self.__graphs.append(graph)
                graph.handler.append(self.context)
    
    def detach(self, *graphs):
        for graph in graphs:
            if graph in self.__graphs:
                self.__graphs.remove(graph)
                graph.handler.remove(self.context)
    
    def set_logic(self, p):
        prep = self.__logicp
        self.__logicp = p = bool(p)
        if self.__frame and prep != p: # replot if toggled
            u = self.__frame.unit
            ru = u if p else 1/u
            self.xlim *= ru
            x = self.__plot.get_xdata(orig=0)
            self.__plot.set_xdata(x * ru)
            if self.region is not None:
                self.region *= ru
            sel = self.Selector
            self.Selector = (sel[0] * ru, sel[1])
            self.draw()
    
    def set_linewidth(self, w):
        if 0 < w < 256:
            self.__linewidth = w
        if self.__frame:
            self.linplot(self.__frame, fit=0)
        self.writeln()
    
    @property
    def boundary(self):
        x = self.__plot.get_xdata(orig=0)
        if x.size:
            return x[[0,-1]]
    
    @property
    def plotdata(self):
        """plotted (xdata, ydata) in single plot"""
        return self.__plot.get_data(orig=0)
    
    def linplot(self, frame, fit=True, force=True):
        if not force:
            if frame is self.__frame:
                return
        self.__frame = frame # update reference of the frame
        if frame:
            sel = frame.selector
            if sel.shape[1] < 2:
                return
            
            xx, yy = sel[:,-2:] # get the last 2-selected line
            nx, ny = frame.xytopixel(xx, yy) # converts to pixel [ny,nx]
            lx = nx[1] - nx[0]
            ly = ny[1] - ny[0]
            if lx or ly:
                L = np.hypot(lx, ly) # pixel length
                nv = (-ly/L, lx/L)   # and norm vector to L
            else:
                L = 0
                nv = (0, 0)
            
            ## ??????????????????????????? L, ????????? N ?????????????????????????????????????????????
            lw = self.__linewidth
            N = int(L) + 1
            xs = np.linspace(nx[0], nx[1], N)
            ys = np.linspace(ny[0], ny[1], N)
            zs = np.zeros(N)
            h, w = frame.buffer.shape[:2]
            for k in np.arange(-(lw-1)/2, (lw+1)/2):
                x = xs + k * nv[0]
                y = ys + k * nv[1]
                mask = (0 < x) & (x < w) & (0 < y) & (y < h)
                if any(mask):
                    x = x[mask]
                    y = y[mask]
                    zi = frame.buffer[y.astype(int), x.astype(int)] # nearest: ???????????????????????????
                    ## zi = ndi.map_coordinates(frame.buffer, np.vstack((y, x))) # spline: ???????????????
                    if zi.dtype in (np.complex64, np.complex128):
                        zi = np.log(1 + abs(zi))
                    zs[mask] += zi
            zs /= lw
            
            if self.__logicp: # axis to logical length # ?????????????????????????????????
                L = np.hypot(xx[1]-xx[0], yy[1]-yy[0])
            
            ls = np.linspace(0, L, N)
            self.__plot.set_data(ls, zs)
            self.__plot.set_visible(1)
            
            if fit: # drawing area
                ly = self.ylim
                self.xlim = ls[0], ls[-1]
                self.ylim = ly[0], max(ly[1], max(zs))
            
        self.update_position()
        self.draw()
    
    def writeln(self):
        if not self.modeline.IsShown():
            return
        frame = self.__frame
        if frame:
            self.modeline.write(
            "[--] -{a}- {name} ({type}:{mode}) "
            "[{length}:{width}] {x} [{unit:g}/pixel]".format(
                name = frame.name,
                type = frame.buffer.dtype,
                mode = "nearest",
               width = self.__linewidth,
              length = len(self.plotdata[0]),
                unit = frame.unit if self.__logicp else 1,
                   x = '++' if self.__logicp else '--',
                   a = '%%' if not frame.buffer.flags.writeable else '--'))
        else:
            self.modeline.write("")
    
    ## --------------------------------
    ## Motion/Drag actions (override)
    ## --------------------------------
    
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
    
    def OnDraw(self, evt):
        """Called before canvas.draw"""
        LinePlot.OnDraw(self, evt)
        
        x, y = self.plotdata
        if x.size:
            self.__fil.set_xy(list(chain([(x[0],0)], zip(x,y), [(x[-1],0)])))
        self.writeln()
        
    def OnLineWidth(self, evt):
        n = -2 if evt.key[-1] == '-' else 2
        self.set_linewidth(self.__linewidth + n)
    
    def OnRegionShift(self, evt):
        if self.__frame and self.region is not None:
            u = self.__frame.unit
            if evt.key == "left": self.region -= u
            if evt.key == "right": self.region += u
            self.draw()
    
    def OnEscapeSelection(self, evt):
        self.__hline.set_visible(0)
        LinePlot.OnEscapeSelection(self, evt)
    
    def OnDragLineBegin(self, evt):
        self.set_wxcursor(wx.CURSOR_SIZENS)
    
    def OnRegionLock(self, evt):
        x, y = self.plotdata
        if x.size:
            xc, yc = evt.xdata, evt.ydata
            u = x[1] - x[0] # != frame.unit (?????????????????? dx=unit ??????????????????)
            v = (y < yc)
            if v.all():
                self.region = None # all y < yc
            elif v.any():
                xa = x[(x < xc) & v]
                xb = x[(x > xc) & v]
                a = xa[-1] if xa.any() else x[ 0] # left-under bound
                b = xb[ 0] if xb.any() else x[-1] # right-over bound
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
                self.region = x[[0,-1]] # all y > yc
            
            self.__hline.set_ydata(yc)
            self.__hline.set_visible(1)
            self.message("y = {:g}, xr = {}".format(yc, self.region))
            self.draw()
    
    def OnMarkPeaks(self, evt):
        x, y = self.plotdata
        if x.size:
            lw = 5
            window = np.hanning(lw)
            ys = np.convolve(window/window.sum(), y, mode='same')
            
            ## maxima = signal.find_peaks_cwt(ys, np.arange(lw,lw*2))
            maxima,_ = signal.find_peaks(ys, width=lw, prominence=20)
            
            ## minima = signal.find_peaks_cwt(-ys, np.arange(lw,lw*2))
            minima,_ = signal.find_peaks(-ys, width=lw, prominence=20)
            
            peaks = np.sort(np.append(maxima, minima))
            if peaks.size:
                self.Selector = x[peaks], y[peaks]
    
    def OnMarkErase(self, evt):
        del self.Selector
    
    def OnMarkSelectionBegin(self, evt):
        org = self.p_event
        xs, ys = self.Selector
        xc, yc = org.xdata, org.ydata
        ## xc, yc = evt.xdata, evt.ydata
        if xs.size:
            ld = np.hypot((xs-xc)*self.ddpu[0], (ys-yc)*self.ddpu[1])
            j = np.argmin(ld)
            self.__orgpoint = xs[j]
        self.set_wxcursor(wx.CURSOR_SIZEWE)
        self.draw()
    
    def OnMarkSelectionMove(self, evt):
        xs, ys = self.Selector
        xc, yc = evt.xdata, evt.ydata
        if xs.size:
            ld = np.hypot((xs-xc)*self.ddpu[0], (ys-yc)*self.ddpu[1])
            j = np.argmin(ld)
            if ld[j] < 20: # check display-dot distance, snap to the nearest mark
                xc = xs[j]
            self.region = (self.__orgpoint, xc)
            self.draw()


if __name__ == "__main__":
    from PIL import Image
    from mwx.matplot2g import GraphPlot
    
    def _imread(path):
        return Image.open(path)
    
    def _plot(axes):
        axes.grid(True)
        x = np.arange(-2,2,0.01)
        y = np.exp(-x*x)
        
        #<matplotlib.collections.PolyCollection>
        ## axes.fill_between(x, y, color='azure', alpha=1) # ??????????????????
        
        #<matplotlib.lines.Line2D>
        axes.plot(x, y, 'o-', ms=0, color='c', alpha=1, picker=True, pickradius=2) # ??????
        
        ## #<matplotlib.patches.Rectangle>
        ## axes.bar(x, y, width=0.02, color='c', ec='none', alpha=1) # ????????????
    
    app = wx.App()
    frm = mwx.Frame(None, title="Graph", size=(300,300))
    frm.graph = GraphPlot(frm, log=frm.statusbar, margin=None)
    frm.graph.handler.debug = 0
    
    frm.graph.unit = 0.1
    frm.graph.load(_imread("C:/usr/home/workspace/images/sample.bmp"), "sample")
    frm.graph.load(_imread("C:/usr/home/workspace/images/sample_diff.bmp"), "circ")
    ## frm.graph.frame.aspect_ratio = 2
    frm.Show()
    if 1:
        lfrm = mwx.Frame(None, title='Line')
        lfrm.graph = LinePlot(lfrm, log=lfrm.statusbar, size=(200,100))
        lfrm.graph.handler.debug = 4
        _plot(lfrm.graph.axes)
        lfrm.graph.update_position()
        lfrm.Show()
    if 0:
        hfrm = mwx.Frame(None, title="Histogram")
        hfrm.graph = Histogram(hfrm, log=hfrm.statusbar, size=(200,100))
        hfrm.graph.modeline.Show(1)
        hfrm.graph.attach(frm.graph)
        hfrm.graph.handler.debug = 4
        hfrm.Show()
    if 1:
        lpf = mwx.Frame(None, title="Line profile")
        lpf.graph = LineProfile(lpf, log=lpf.statusbar, size=(200,100))
        lpf.graph.attach(frm.graph)
        lpf.graph.handler.debug = 4
        lpf.Show()
    
    app.MainLoop()
