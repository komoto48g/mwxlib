#! python3
# -*- coding: utf-8 -*-
"""Graphical debugger
   of the phoenix, by the phoenix, for the phoenix

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from functools import wraps
from bdb import BdbQuit
from pdb import Pdb
import pdb
import sys
import re
import inspect
import threading
from importlib import import_module
import wx
try:
    from utilus import FSM, where
except ImportError:
    from .utilus import FSM, where


def echo(f):
    @wraps(f)
    def _f(*args, **kwargs):
        if echo.debug > 0:
            print("<{!r}>".format(f.__name__))
        return f(*args, **kwargs)
    return _f
echo.debug = 0


class Debugger(Pdb):
    """Graphical debugger with extended Pdb
    
    Args:
         parent : shellframe
          stdin : shell.interp.stdin
         stdout : shell.interp.stdout
    
    Attributes:
           busy : The flag of being running now
        verbose : Verbose messages are output from Pdb
         editor : Editor to show the stack frame
          shell : Shell for debug
    
    Key bindings:
            C-g : quit
            C-q : quit
            C-n : next
            C-r : return
            C-s : step
    """
    prefix1 = "> "
    prefix2 = "-> "
    verbose = False
    use_rawinput = False
    indent = property(lambda self: ' ' * self.__indents)
    prompt = property(lambda self: ' ' * self.__indents + '(Pdb) ',
                      lambda self,v: None) # fake setter
    parent = property(lambda self: self.__shellframe)
    handler = property(lambda self: self.__handler)
    
    @property
    def target(self):
        if self.editor:
            return self.editor.target
    
    @property
    def interactive_shell(self):
        return self.__shell
    
    @interactive_shell.setter
    def interactive_shell(self, v):
        self.__shell = v
        ## Don't use rawinput
        self.stdin = self.__shell.interp.stdin
        self.stdout = self.__shell.interp.stdout
    
    @property
    def busy(self):
        """The current state is debug mode
        True from entering `set_trace` until the end of `set_quit`
        """
        ## cf. (self.handler.current_state == 1)
        try:
            return self.curframe is not None
        except AttributeError:
            pass
    
    @property
    def tracing(self):
        """The current state is trace mode
        """
        ## cf. (self.handler.current_state == 2)
        return self.__hookpoint is not None
    
    def __init__(self, parent, *args, **kwargs):
        Pdb.__init__(self, *args, **kwargs)
        
        self.__shellframe = parent
        self.__hookpoint = None
        self.__indents = 0
        self.interactive_shell = parent.rootshell
        self.editor = None
        self.code = None
        
        def _input(msg):
            ## redirects prompt input such as cl(ear)
            self.message(msg, indent=0)
            return self.stdin.readline()
        pdb.input = _input
        
        def _help():
            self.parent.handler('add_help', pdb.__doc__)
        pdb.help = _help
        
        def dispatch(v):
            self.parent.handler(self.handler.event, v)
        
        self.__handler = FSM({ # DNA<Debugger>
            0 : {
                  'debug_begin' : (1, self.on_debug_begin, dispatch),
                  'trace_begin' : (2, dispatch),
            },
            1 : {
                        'abort' : (0, ), # [C-g] unwatch
                    'debug_end' : (0, self.on_debug_end, dispatch),
                   'debug_mark' : (1, self.on_debug_mark, dispatch),
                   'debug_next' : (1, self.on_debug_next, dispatch),
                  'C-g pressed' : (1, lambda v: self.send_input('q')),
                  'C-q pressed' : (1, lambda v: self.send_input('q')),
                  'C-n pressed' : (1, lambda v: self.send_input('n')),
                  'C-s pressed' : (1, lambda v: self.send_input('s')),
                  'C-r pressed' : (1, lambda v: self.send_input('r')),
                  'C-@ pressed' : (1, lambda v: self.jump_to_entry()),
            },
            2 : {
                    'trace_end' : (0, dispatch),
                   'trace_hook' : (2, self.on_trace_hook, dispatch),
                  'debug_begin' : (1, self.on_debug_begin, dispatch),
            },
        })
    
    def jump_to_entry(self):
        """Jump to the first lineno of the code"""
        self.send_input('j {}'.format(self.editor.markline+1))
    
    def add_marker(self, lineno, style):
        """Add a mrker to lineno, with the following style markers:
        [1] white-arrow for breakpoints
        [2] red-arrow for exception
        """
        self.editor.MarkerAdd(lineno-1, style)
    
    def send_input(self, c):
        """Send input:str @postcall"""
        def _send():
            self.stdin.input = c
        wx.CallAfter(_send)
    
    def message(self, msg, indent=-1):
        """(override) Add prefix and insert msg at the end of command-line."""
        shell = self.interactive_shell
        shell.goto_char(shell.eolc)
        prefix = self.indent if indent < 0 else ' ' * indent
        print("{}{}".format(prefix, msg), file=self.stdout)
    
    def watch(self, bp):
        """Start tracing"""
        if not self.busy: # don't set while debugging
            if not bp:
                self.unwatch()
                return
            elif not bp[0]: # no target
                return
            self.__hookpoint = bp
            self.reset()
            sys.settrace(self.trace_dispatch)
            threading.settrace(self.trace_dispatch)
            self.handler('trace_begin', bp)
    
    def unwatch(self):
        """End tracing"""
        if not self.busy: # don't unset while debugging
            bp = self.__hookpoint
            self.reset()
            sys.settrace(None)
            threading.settrace(None)
            ## delete bp *after* setting dispatcher -> None
            self.__hookpoint = None
            if bp:
                self.handler('trace_end', bp)
            else:
                ## Called to abort when the debugger is invalid status:
                ## e.g., (self.handler.current_state > 0 and not self.busy)
                self.handler('abort')
    
    def debug(self, target, *args, **kwargs):
        if not callable(target):
            wx.MessageBox("Not a callable object.\n\n"
                          "Unable to debug {!r}.".format(target))
            return
        if self.busy:
            wx.MessageBox("Debugger is running.\n\n"
                          "Enter [q]uit to exit debug mode.")
            return
        self.unwatch()
        try:
            frame = inspect.currentframe().f_back
            self.set_trace(frame)
            target(*args, **kwargs)
        except BdbQuit:
            pass
        except Exception as e:
            wx.CallAfter(wx.MessageBox,
                         "Debugger is closed.\n\n{}".format(e))
        finally:
            self.set_quit()
            return
    
    ## --------------------------------
    ## Actions for handler
    ## --------------------------------
    
    def on_debug_begin(self, frame):
        """Called before set_trace
        Note: self.busy -> False or None
        """
        shell = self.interactive_shell
        self.__hookpoint = None
        self.__interactive = shell.cpos
        self.stdin.input = '' # clear stdin buffer
        def _continue():
            if wx.IsBusy():
                wx.EndBusyCursor()
            shell.prompt()
            shell.SetFocus()
        wx.CallAfter(_continue)
    
    def on_debug_mark(self, frame):
        """Called when interaction"""
        code = frame.f_code
        filename = code.co_filename
        firstlineno = code.co_firstlineno
        lineno = frame.f_lineno
        m = re.match("<frozen (.*)>", filename)
        if m:
            module = import_module(m.group(1))
            filename = inspect.getfile(module)
        
        editor = self.parent.find_editor(filename) or self.parent.Log
        if self.code != code:
            editor.load_cache(filename)
            editor.push_current(filename, firstlineno) # save current
            editor.markline = firstlineno - 1 # (o) entry:marker
            for ln in self.get_file_breaks(filename):
                self.add_marker(ln, 1)
        if filename == editor.target:
            editor.linemark = lineno - 1 # (->) pointer:marker
            editor.goto_line_marker()
        self.editor = editor
        self.code = code
    
    def on_debug_next(self, frame):
        """Called in preloop (cmdloop)"""
        pos = self.__interactive
        def _post():
            shell = self.interactive_shell
            out = shell.GetTextRange(pos, shell.cpos)
            if out == self.prompt or out.endswith(self.prompt*2):
                shell.cpos -= len(self.prompt) # backward selection
                shell.ReplaceSelection('')
                shell.goto_char(-1)
                shell.prompt()
            self.__interactive = shell.cpos
        wx.CallAfter(_post)
    
    def on_debug_end(self, frame):
        """Called after set_quit
        Note: self.busy -> True (until this stage)
        """
        self.__indents = 0
        self.__interactive = None
        del self.editor.linemark
        self.editor = None
        self.code = None
        main = threading.main_thread()
        thread = threading.current_thread()
        if thread is not main:
            ## terminates the reader (main-thread)
            self.send_input('\n')
        def _continue():
            if wx.IsBusy():
                wx.EndBusyCursor()
        wx.CallAfter(_continue)
    
    def on_trace_hook(self, frame):
        """Called when a breakppoint is reached"""
        self.__indents = 2
        self.__hookpoint = None
        self.interactive_shell.write('\n', -1) # move to eolc and insert LFD
        self.message(where(frame.f_code), indent=0)
    
    ## --------------------------------
    ## Override Bdb methods
    ## --------------------------------
    
    def dispatch_line(self, frame):
        """Invoke user function and return trace function for line event.
        (override) Watch the breakpoint
        """
        if self.__hookpoint:
            target, line = self.__hookpoint
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            if target == filename:
                if lineno >= line:
                    self.handler('trace_hook', frame)
                    self.handler('debug_begin', frame)
                else:
                    return None
            else:
                return None
        return Pdb.dispatch_line(self, frame)
    
    def dispatch_call(self, frame, arg):
        """Invoke user function and return trace function for call event.
        (override) Watch the breakpoint
        """
        if self.__hookpoint:
            target, line = self.__hookpoint
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            if target == filename:
                if lineno <= line: # continue to dispatch_line
                    return self.trace_dispatch
                else:
                    return None
            else:
                return None
        return Pdb.dispatch_call(self, frame, arg)
    
    def dispatch_return(self, frame, arg):
        if self.__hookpoint:
            return None
        return Pdb.dispatch_return(self, frame, arg)
    
    def dispatch_exception(self, frame, arg):
        if self.__hookpoint:
            return None
        return Pdb.dispatch_exception(self, frame, arg)
    
    def set_trace(self, frame=None):
        if self.busy:
            wx.MessageBox("Debugger is running.\n\n"
                          "Enter [q]uit to exit debug mode.")
            return
        if not frame:
            frame = inspect.currentframe().f_back
        self.handler('debug_begin', frame)
        Pdb.set_trace(self, frame)
    
    def set_break(self, filename, lineno, *args, **kwargs):
        self.add_marker(lineno, 1)
        return Pdb.set_break(self, filename, lineno, *args, **kwargs)
    
    def set_quit(self):
        try:
            Pdb.set_quit(self)
        finally:
            self.handler('debug_end', self.curframe)
            return
    
    ## --------------------------------
    ## Override Pdb methods
    ## --------------------------------
    
    @echo
    def print_stack_entry(self, frame_lineno, prompt_prefix=None):
        """Print the stack entry frame_lineno (frame, lineno).
        (override) Change prompt_prefix;
                   Add pointer:marker when step next or jump
        """
        frame, lineno = frame_lineno
        self.handler('debug_mark', frame)
        if self.verbose:
            Pdb.print_stack_entry(self, frame_lineno,
                prompt_prefix or '\n' + self.indent + self.prefix2)
    
    @echo
    def user_call(self, frame, argument_list):
        """--Call--
        (override) Show message to record the history
                   Add indent spaces
        """
        if not self.verbose:
            self.message("{}{}".format(self.prefix1, where(frame)), indent=0)
        self.__indents += 2
        Pdb.user_call(self, frame, argument_list)
    
    @echo
    def user_line(self, frame):
        """--Next--"""
        Pdb.user_line(self, frame)
    
    @echo
    def user_return(self, frame, return_value):
        """--Return--
        (override) Show message to record the history
                   Remove indent spaces
        """
        self.message("$(retval) = {!r}".format(return_value), indent=0)
        Pdb.user_return(self, frame, return_value)
        self.__indents -= 2
    
    @echo
    def user_exception(self, frame, exc_info):
        """--Exception--
        (override) Update exception:markers
        """
        t, v, tb = exc_info
        self.add_marker(tb.tb_lineno, 2)
        self.message(tb.tb_frame, indent=0)
        Pdb.user_exception(self, frame, exc_info)
    
    @echo
    def bp_commands(self, frame):
        """--Break--
        (override) Update breakpoint:markers every time the frame changes
        """
        filename = frame.f_code.co_filename
        breakpoints = self.get_file_breaks(filename)
        for lineno in breakpoints:
            self.add_marker(lineno, 1)
        return Pdb.bp_commands(self, frame)
    
    @echo
    def preloop(self):
        """Hook method executed once when the cmdloop() method is called."""
        self.handler('debug_next', self.curframe)
        Pdb.preloop(self)
    
    @echo
    def postloop(self):
        """Hook method executed once when the cmdloop() method is about to return."""
        Pdb.postloop(self)


if __name__ == "__main__":
    from mwx import Frame
    
    app = wx.App()
    frm = Frame(None)
    if 1:
        self = frm.shellframe
        shell = frm.shellframe.rootshell
        dbg = Debugger(self)
        self.debugger = dbg
        dbg.handler.debug = 4
        dbg.verbose = 0
        echo.debug = 1
        self.Show()
    frm.Show()
    app.MainLoop()
