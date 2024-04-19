#! python3
"""Line profile.
"""
from mwx.graphman import Layer
from mwx.matplot2lg import LineProfile


class Plugin(Layer):
    """Line profile of the currently selected buffers.
    """
    menukey = "Plugins/Extensions/&Line profile\tCtrl+l"
    caption = "Line profile"
    dockable = False
    
    def Init(self):
        self.plot = LineProfile(self, log=self.message, size=(300,200))
        
        self.layout((self.plot,), expand=2, border=0)
        
        @self.handler.bind('page_shown')
        def activate(v):
            self.plot.attach(*self.parent.graphic_windows)
            self.plot.linplot(self.parent.selected_view.frame)
        
        @self.handler.bind('page_closed')
        def deactivate(v):
            self.plot.detach(*self.parent.graphic_windows)
