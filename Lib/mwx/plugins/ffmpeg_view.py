#! python3
"""FFmpeg wrapper.
"""
from subprocess import Popen, PIPE
import numpy as np
import os
import wx
import wx.media

from mwx.framework import _F
from mwx.graphman import Layer
from mwx.controls import Param, LParam, Icon, Button, TextBox


def read_info(path):
    command = ['ffprobe',
               '-i', path,
               '-loglevel', 'quiet',    # no verbose
               '-print_format', 'json', # -format json
               '-show_streams',         # -streams info
               ]
    with Popen(command, stdout=PIPE, stderr=PIPE) as fp:
        ret, err = fp.communicate()
        if not err:
            return eval(ret)


def capture_video(path, ss=0):
    command = ['ffmpeg',
               '-ss', f"{ss}",          # Note: placing -ss before -i will be faster,
               '-i', path,              #       but maybe not accurate.
               '-frames:v', '1',        # -frame one shot
               '-f', 'rawvideo',        # -format raw
               '-pix_fmt', 'rgb24',     # rgb24, gray, etc.
               'pipe:'                  # pipe to stdout: '-'
               ]
    bufsize = 4096  # w * h * 3
    buf = b""
    with Popen(command, stdout=PIPE) as fp:
        while 1:
            s = fp.stdout.read(bufsize)
            buf += s
            if len(s) < bufsize:
                break
    return np.frombuffer(buf, np.uint8)


def export_video(path, crop, ss, to, filename):
    command = ['ffmpeg',
               '-i', path,
               '-vf', f"{crop=}",
               '-ss', f"{ss}",
               '-to', f"{to}",
               '-y', filename,
               ]
    print('>', ' '.join(command))
    with Popen(command) as fp:
        ret, err = fp.communicate()


class MyFileDropLoader(wx.FileDropTarget):
    def __init__(self, target):
        wx.FileDropTarget.__init__(self)
        self.target = target

    def OnDropFiles(self, x, y, filenames):
        path = filenames[-1]  # Only the last one will be loaded.
        if len(filenames) > 1:
            print("- Drop only one file please."
                  "Loading {!r} ...".format(path))
        self.target.load_media(path)
        return True


class Plugin(Layer):
    """Media loader using FFMpeg (installation required).
    """
    menukey = "Plugins/Extensions/FFMpeg viewer"
    dockable = False

    def Init(self):
        self.mc = wx.media.MediaCtrl()
        self.mc.Create(self, size=(300,300),
                       style=wx.SIMPLE_BORDER,
                       szBackend=wx.media.MEDIABACKEND_WMP10
                       # szBackend=wx.media.MEDIABACKEND_DIRECTSHOW
        )
        self.mc.ShowPlayerControls()
        self.mc.Bind(wx.media.EVT_MEDIA_LOADED, self.OnMediaLoaded)
        
        self.mc.SetDropTarget(MyFileDropLoader(self))
        
        self._path = None
        
        self.ss = LParam("ss:",  # range/value will be set when loaded later.
                        handler=self.set_offset,
                        updater=self.get_offset,
                        )
        self.to = LParam("to:",  # range/value will be set when loaded later.
                        handler=self.set_offset,
                        updater=self.get_offset,
                        )
        self.crop = TextBox(self, icon="cut", size=(140,-1),
                        handler=self.set_crop,
                        updater=self.get_crop,
                        )
        self.rate = Param("rate", (1/8,1/4,1/2,1,2,4,8),
                        handler=self.set_rate,
                        )
        
        self.snp = Button(self, handler=self.snapshot, icon='clip')
        self.exp = Button(self, handler=self.export, icon='save')
        
        self.rw = Button(self, handler=lambda v: self.seekto(-100), icon='|<-')
        self.fw = Button(self, handler=lambda v: self.seekto(+100), icon='->|')
        
        self.layout((self.mc,), expand=2)
        self.layout((self.ss, self.to, self.rw, self.fw,
                     self.snp, self.crop, self.rate, self.exp),
                    expand=0, row=8, type='vspin', style='button', lw=32, cw=-1, tw=64)
        
        self.menu[0:5] = [
            (1, "&Load file", Icon('open'),
                lambda v: self.load_media()),
                
            (2, "&Snapshot", Icon('clip'),
                lambda v: self.snapshot(),
                lambda v: v.Enable(self._path is not None)),
            (),
        ]
        
        self.parent.handler.bind("unknown_format", self.load_media)
        
        self.handler.update({  # DNA<ffmpeg_viewer>
            None : {
               'C-left pressed' : (None, _F(self.seekd, -1000)),
              'C-right pressed' : (None, _F(self.seekd,  1000)),
            },
            0 : {  # MEDIASTATE_STOPPED
                         'play' : (2, ),
                'space pressed' : (2, _F(self.mc.Play)),
            },
            1 : {  # MEDIASTATE_PAUSED
                         'stop' : (0, ),
                'space pressed' : (2, _F(self.mc.Play)),
            },
            2 : {  # MEDIASTATE_PLAYING
                         'stop' : (0, ),
                        'pause' : (1, ),
                'space pressed' : (1, _F(self.mc.Pause)),
            },
        })
        
        self.mc.Bind(wx.media.EVT_MEDIA_PAUSE, lambda v: self.handler('pause', v))
        self.mc.Bind(wx.media.EVT_MEDIA_PLAY, lambda v: self.handler('play', v))
        self.mc.Bind(wx.media.EVT_MEDIA_STOP, lambda v: self.handler('stop', v))
        
        self.mc.Bind(wx.EVT_KEY_DOWN, self.on_hotkey_down)
        self.mc.Bind(wx.EVT_KEY_UP, self.on_hotkey_up)

    def Destroy(self):
        self.parent.handler.unbind("unknown_format", self.load_media)
        if self.mc:
            self.mc.Destroy()
        return Layer.Destroy(self)

    def OnShow(self, evt):
        if not evt.IsShown():
            if self.mc:
                self.mc.Stop()
        Layer.OnShow(self, evt)

    def OnMediaLoaded(self, evt):
        self.ss.range = (0, self.video_dur, 0.01)
        self.to.range = (0, self.video_dur, 0.01)
        self.Show()
        evt.Skip()

    def load_media(self, path=None):
        if path is None:
            with wx.FileDialog(self, "Choose a media file",
                    style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                path = dlg.Path
        self.mc.Load(path)  # -> True (always)
        self.info = read_info(path)
        if self.info:
            v = next(x for x in self.info['streams'] if x['codec_type'] == 'video')
            # self.video_fps = eval(v['r_frame_rate'])  # real base frame rate
            self.video_fps = eval(v['avg_frame_rate'])  # averaged frame rate
            self.video_dur = eval(v['duration'])        # duration [s]
            w, h = v['width'], v['height']
            try:
                if v['tags']['rotate'] in ('90', '270'):
                    w, h = h, w  # transpose
            except KeyError:
                pass
            self.video_size = w, h
            self._path = path
            self.message(f"Loaded {path!r} successfully.")
            return True
        else:
            self.message(f"Failed to load file {path!r}.")
            return False

    ## Correction for seek position. ▲理由は不明 (WMP10 backend only?)
    @property
    def DELTA(self):
        return int(1000 / self.mc.PlaybackRate)

    def set_offset(self, tc):
        """Set offset value by referring to ss/to value."""
        if self._path:
            self.mc.Seek(self.DELTA + int(tc.value * 1000))

    def get_offset(self, tc):
        """Get offset value and assigns it to ss/to value."""
        if self._path:
            tc.value = round(self.mc.Tell()) / 1000

    def set_crop(self):
        """Set crop area (W:H:Left:Top) to ROI."""
        frame = self.graph.frame
        if frame:
            try:
                w, h, xo, yo = map(float, self.crop.Value.split(':'))
                xo -= 0.5  # Correction with half-pixel offset.
                yo -= 0.5  # Select left-top corner position.
                nx = xo, xo+w
                ny = yo, yo+h
                frame.region = frame.xyfrompixel(nx, ny)
            except Exception as e:
                self.message("Failed to evaluate crop text;", e)

    def get_crop(self):
        """Get crop area (W:H:Left:Top) from ROI."""
        frame = self.graph.frame
        if frame:
            nx, ny = frame.xytopixel(frame.region)
            if nx.size:
                xo, xp = nx
                yp, yo = ny
                self.crop.Value = f"{xp-xo}:{yp-yo}:{xo}:{yo}"  # (W:H:left:top)
                return
        if self._path:
            self.crop.Value = "{}:{}:0:0".format(*self.video_size)

    def set_rate(self, rate):
        if self._path:
            self.mc.PlaybackRate = rate

    def get_rate(self):
        if self._path:
            return self.mc.PlaybackRate

    def seekto(self, offset):
        """Seek position with offset [ms] from the `to` position."""
        if self._path:
            t = self.to.value + offset/1000
            if 0 <= t < self.video_dur:
                self.to.value = round(t, 3)
            self.set_offset(self.to)

    def seekd(self, offset):
        """Seek position with offset [ms] from the current position."""
        if self._path:
            t = self.mc.Tell() + offset
            if 0 <= t < self.video_dur * 1000:
                self.mc.Seek(self.DELTA + t)

    def snapshot(self):
        """Create a snapshot of the current frame.
        Load the snapshot image into the graph window.
        """
        if not self._path:
            return
        t = self.mc.Tell()
        w, h = self.video_size
        buf = capture_video(self._path, t/1000).reshape((h,w,3))
        name = "{}-ss{}".format(os.path.basename(self._path), int(t))
        self.graph.load(buf, name)

    def export(self):
        """Export the cropped / clipped data to a media file."""
        if not self._path:
            return
        fout = "{}_clip".format(os.path.splitext(self._path)[0])
        with wx.FileDialog(self, "Save as",
                defaultDir=os.path.dirname(fout),
                defaultFile=os.path.basename(fout),
                wildcard="Media file (*.mp4)|*.mp4|"
                         "Animiation (*.gif)|*.gif",
                style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            fout = dlg.Path
        export_video(self._path,
                     self.crop.Value or "{}:{}:0:0".format(*self.video_size),
                     self.ss.value, self.to.value, fout)
