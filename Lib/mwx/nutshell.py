#! python3
# -*- coding: utf-8 -*-
"""mwxlib framework

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from functools import wraps
import traceback
import warnings
import keyword
import shlex
import time
import sys
import os
import re
import wx
from wx import stc
from wx.py import dispatcher
from wx.py import introspect
from wx.py import interpreter
from wx.py.shell import Shell
from wx.py.editwindow import EditWindow
import pydoc
import inspect
import builtins
import linecache
from pprint import pformat
from importlib import import_module
import contextlib
import copy
import dis
try:
    import utilus as ut
    from utilus import funcall as _F
    from framework import postcall, skip, Menu, CtrlInterface
except ImportError:
    from . import utilus as ut
    from .utilus import funcall as _F
    from .framework import postcall, skip, Menu, CtrlInterface


def editable(f):
    @wraps(f)
    def _f(self, *args, **kwargs):
        if self.CanEdit():
            return f(self, *args, **kwargs)
    return _f


def ask(f, prompt="Enter value", type=str):
    """Get response from the user using a dialog box."""
    @wraps(f)
    def _f(*v):
        with wx.TextEntryDialog(None, prompt, f.__name__) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                return f(type(dlg.Value))
    return _f


class EditorInterface(CtrlInterface):
    """Python code editor interface with Keymap
    
    Note: This class should be mixed-in `wx.stc.StyledTextCtrl`
    """
    def __init__(self):
        CtrlInterface.__init__(self)
        
        self.make_keymap('C-x')
        self.make_keymap('C-c')
        
        _P = self.post_command_hook
        
        self.handler.update({ # DNA<EditorInterface>
            None : {
            },
            -1 : { # original action of the Editor
                    '* pressed' : (0, skip, lambda v: self.message("ESC {}".format(v.key))),
                 '*alt pressed' : (-1, ),
                '*ctrl pressed' : (-1, ),
               '*shift pressed' : (-1, ),
             '*[LR]win pressed' : (-1, ),
            },
            0 : {
                    '* pressed' : (0, skip),
                   '* released' : (0, skip),
               'escape pressed' : (-1, _F(lambda v: self.message("ESC-"), alias="escape")),
               'insert pressed' : (0, _F(self.over, None, doc="toggle-over")),
               'C-left pressed' : (0, _F(self.WordLeft)),
              'C-right pressed' : (0, _F(self.WordRightEnd)),
             'C-S-left pressed' : (0, _F(self.selection_backward_word_or_paren)),
            'C-S-right pressed' : (0, _F(self.selection_forward_word_or_paren)),
               'C-S-up pressed' : (0, _F(self.LineUpExtend)),
             'C-S-down pressed' : (0, _F(self.LineDownExtend)),
                'C-S-c pressed' : (0, _F(self.Copy)),
                  'C-a pressed' : (0, _F(self.beginning_of_line)),
                  'C-e pressed' : (0, _F(self.end_of_line)),
                  'M-a pressed' : (0, _F(self.back_to_indentation)),
                  'M-e pressed' : (0, _F(self.end_of_line)),
                  'M-g pressed' : (0, ask(self.goto_line, "Line to goto:", lambda x:int(x)-1),
                                       _F(self.recenter),
                                       _F(self.SetFocus)),
                  'M-f pressed' : (10, _F(self.filter_text), self.on_filter_text_enter),
                  'C-k pressed' : (0, _F(self.kill_line)),
                  'C-l pressed' : (0, _F(self.recenter)),
                'C-S-l pressed' : (0, _F(self.recenter)),   # override delete-line
                  'C-t pressed' : (0, ),                    # override transpose-line
                'C-S-f pressed' : (0, _F(self.set_marker)), # override mark
              'C-space pressed' : (0, _F(self.set_marker)),
            'C-S-space pressed' : (0, _F(self.set_line_marker)),
          'C-backspace pressed' : (0, skip),
          'S-backspace pressed' : (0, _F(self.backward_kill_line)),
                'C-tab pressed' : (0, _F(self.insert_space_like_tab)),
              'C-S-tab pressed' : (0, _F(self.delete_backward_space_like_tab)),
                  'tab pressed' : (0, self.on_indent_line),
                'S-tab pressed' : (0, self.on_outdent_line),
                  ## 'C-/ pressed' : (0, ), # cf. C-a home
                  ## 'C-\ pressed' : (0, ), # cf. C-e end
                 'select_indic' : (10, self.filter_text, self.on_filter_text_enter),
                  'select_line' : (100, self.on_linesel_begin),
            },
            10 : {
                         'quit' : (0, self.on_filter_text_exit),
                    '* pressed' : (0, self.on_filter_text_exit),
                   'up pressed' : (10, skip),
                 'down pressed' : (10, skip),
                'enter pressed' : (0, self.on_filter_text_selection),
            },
            100 : {
                       'motion' : (100, self.on_linesel_motion),
                 'capture_lost' : (0, self.on_linesel_end),
             'Lbutton released' : (0, self.on_linesel_end),
            },
            'C-x' : {
                    '* pressed' : (0, _P), # skip to the parent.handler
                    '@ pressed' : (0, _P, _F(self.goto_marker)),
                  'S-@ pressed' : (0, _P, _F(self.goto_line_marker)),
            },
            'C-c' : {
                    '* pressed' : (0, _P), # skip to the parent.handler
                  'C-c pressed' : (0, _P, _F(self.goto_matched_paren)),
            },
        })
        
        self.Bind(wx.EVT_MOTION,
                  lambda v: self.handler('motion', v) or v.Skip())
        
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST,
                  lambda v: self.handler('capture_lost', v) or v.Skip())
        
        ## cf. wx.py.editwindow.EditWindow.OnUpdateUI => Check for brace matching
        self.Bind(stc.EVT_STC_UPDATEUI,
                  lambda v: self.match_paren()) # no skip
        
        def eof(evt):
            p = evt.Position
            lc = self.LineFromPosition(p)
            le = self.LineFromPosition(p + evt.Length)
            self.ShowLines(lc, le)
            evt.Skip()
        
        ## This event occurs when lines that are hidden should be made visible.
        self.Bind(stc.EVT_STC_NEEDSHOWN, eof)
        
        def indic(evt):
            i = self.IndicatorValue # current indicator(1) <- filter_text
            pos = evt.Position
            p = self.IndicatorStart(i, pos)
            q = self.IndicatorEnd(i, pos)
            self.goto_char(pos)
            self.handler('select_indic', self.GetTextRange(p, q)) or evt.Skip()
        
        self.Bind(stc.EVT_STC_INDICATOR_CLICK, indic)
        
        ## Keyword(2) setting
        self.SetLexer(stc.STC_LEX_PYTHON)
        self.SetKeyWords(0, ' '.join(keyword.kwlist))
        self.SetKeyWords(1, ' '.join(builtins.__dict__) + ' self this')
        
        ## AutoComp setting
        self.AutoCompSetAutoHide(False)
        self.AutoCompSetIgnoreCase(True)
        ## self.AutoCompSetSeparator(ord('\t')) => gen_autocomp
        self.AutoCompSetMaxWidth(80)
        self.AutoCompSetMaxHeight(10)
        
        ## To prevent @filling crash (Never access to DropTarget)
        ## [BUG 4.1.1] Don't allow DnD of text, file, whatever.
        self.SetDropTarget(None)
        
        ## Global style for all languages
        ## wx.Font style
        ##    family : DEFAULT, DECORATIVE, ROMAN, SCRIPT, SWISS, MODERN, TELETYPE
        ##     slant : NORMAL, SLANT, ITALIC
        ##    weight : NORMAL, LIGHT, BOLD
        ## underline : False
        ## font = wx.Font(9, wx.MODERN, wx.NORMAL, wx.NORMAL, False, "MS Gothic")
        ## self.StyleSetFont(stc.STC_STYLE_DEFAULT, font)
        
        ## self.StyleClearAll()
        ## self.SetSelForeground(True, wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT))
        ## self.SetSelBackground(True, wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT))
        
        ## The magin style for line numbers and symbols
        ## [0] for markers, 10 pixels wide, mask 0b11111
        ## [1] for numbers, 32 pixels wide, mask 0x01ffffff (~stc.STC_MASK_FOLDERS)
        ## [2] for borders,  1 pixels wide, mask 0xfe000000 ( stc.STC_MASK_FOLDERS)
        
        ## 32 bit margin mask
        ## [0] 1111,1111,1111,1111,1111,1111,1111,1111 = -1 for all markers
        ## [1] 0000,0001,1111,1111,1111,1111,1111,1111 = 0x01ffffff for markers
        ## [2] 1111,1110,0000,0000,0000,0000,0000,0000 = 0xfe000000 for folders
        
        self.SetMarginType(0, stc.STC_MARGIN_SYMBOL)
        self.SetMarginMask(0, 0b00111) # mask for markers (0,1,2)
        self.SetMarginWidth(0, 10)
        self.SetMarginSensitive(0, False)
        
        self.SetMarginType(1, stc.STC_MARGIN_NUMBER)
        self.SetMarginMask(1, 0b11000) # mask for pointer (3,4)
        self.SetMarginWidth(1, 32)
        self.SetMarginSensitive(1, False)
        
        self.SetMarginType(2, stc.STC_MARGIN_SYMBOL)
        self.SetMarginMask(2, stc.STC_MASK_FOLDERS) # mask for folders
        self.SetMarginWidth(2, 1)
        self.SetMarginSensitive(2, False) # cf. show_folder
        
        self.SetMarginLeft(2) # +1 margin at the left
        
        self.SetFoldFlags(0x10) # draw below if not expanded
        
        self.SetProperty('fold', '1') # Enable folder property
        
        ## if wx.VERSION >= (4,1,0):
        try:
            self.Bind(stc.EVT_STC_MARGINCLICK, self.OnMarginClick)
            self.Bind(stc.EVT_STC_MARGIN_RIGHT_CLICK, self.OnMarginRClick)
        except AttributeError:
            pass
        
        ## Custom markers (cf. MarkerAdd)
        self.MarkerDefine(0, stc.STC_MARK_CIRCLE, '#007ff0', '#007ff0') # o blue-mark
        self.MarkerDefine(1, stc.STC_MARK_ARROW,  '#000000', '#ffffff') # > white-arrow
        self.MarkerDefine(2, stc.STC_MARK_ARROW,  '#7f0000', '#ff0000') # > red-arrow
        self.MarkerDefine(3, stc.STC_MARK_SHORTARROW, 'blue', 'gray')   # >> blue-pointer
        self.MarkerDefine(4, stc.STC_MARK_SHORTARROW, 'red', 'yellow')  # >> red-pointer
        
        v = ('white', 'black')
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEROPEN,    stc.STC_MARK_BOXMINUS, *v)
        self.MarkerDefine(stc.STC_MARKNUM_FOLDER,        stc.STC_MARK_BOXPLUS,  *v)
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERSUB,     stc.STC_MARK_VLINE,    *v)
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERTAIL,    stc.STC_MARK_LCORNER,  *v)
        ## self.MarkerDefine(stc.STC_MARKNUM_FOLDEREND,     stc.STC_MARK_TCORNER, *v)
        ## self.MarkerDefine(stc.STC_MARKNUM_FOLDEROPENMID, stc.STC_MARK_TCORNER, *v)
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEREND,     stc.STC_MARK_VLINE, *v)
        self.MarkerDefine(stc.STC_MARKNUM_FOLDEROPENMID, stc.STC_MARK_VLINE, *v)
        self.MarkerDefine(stc.STC_MARKNUM_FOLDERMIDTAIL, stc.STC_MARK_VLINE, *v)
        
        ## Custom indicator for search-word
        try:
            self.IndicatorSetStyle(0, stc.STC_INDIC_TEXTFORE)
            self.IndicatorSetStyle(1, stc.STC_INDIC_ROUNDBOX)
        except AttributeError:
            self.IndicatorSetStyle(0, stc.STC_INDIC_PLAIN)
            self.IndicatorSetStyle(1, stc.STC_INDIC_ROUNDBOX)
        self.IndicatorSetForeground(0, "red")
        self.IndicatorSetForeground(1, "yellow")
        try:
            self.IndicatorSetHoverStyle(1, stc.STC_INDIC_ROUNDBOX)
            self.IndicatorSetHoverForeground(1, "blue")
        except AttributeError:
            pass
        
        ## Custom indicator for match_paren
        ## self.IndicatorSetStyle(2, stc.STC_INDIC_PLAIN)
        ## self.IndicatorSetForeground(2, "light gray")
        
        ## Custom style of control-char, wrap-mode
        ## self.UseTabs = False
        ## self.ViewEOL = True
        ## self.ViewWhiteSpace = True
        self.TabWidth = 4
        ## self.EOLMode = stc.STC_EOL_LF
        self.WrapMode = stc.STC_WRAP_NONE
        self.WrapIndentMode = stc.STC_WRAPINDENT_SAME
        self.IndentationGuides = stc.STC_IV_LOOKFORWARD
        
        self.__mark = -1
    
    ## custom constants embedded in stc
    stc.STC_P_WORD3 = 20
    stc.STC_STYLE_CARETLINE = 40
    
    ## --------------------------------
    ## Marker attributes of the editor
    ## --------------------------------
    
    def _Marker(marker, n):
        """Factory of marker property
        """
        def fget(self):
            return self.MarkerNext(0, 1<<n)
        
        def fset(self, line):
            if line != -1:
                self.MarkerDeleteAll(n)
                self.MarkerAdd(line, n)
                self.handler('{}_set'.format(marker), line)
            else:
                fdel(self)
        
        def fdel(self):
            line = fget(self)
            if line != -1:
                self.MarkerDeleteAll(n)
                self.handler('{}_unset'.format(marker), line)
        
        return property(fget, fset, fdel)
    
    white_arrow = _Marker("white-arrow", 1) # white-arrow_set/white-arrow_unset
    red_arrow = _Marker("red-arrow", 2) # red-arrow_set/red-arrow_unset
    linemark = _Marker("pointer", 3) # pointer_set/pointer_unset
    
    @property
    def markline(self):
        return self.MarkerNext(0, 1<<0)
    
    @markline.setter
    def markline(self, v):
        if v != -1:
            self.mark = self.PositionFromLine(v)
        else:
            del self.mark
    
    @markline.deleter
    def markline(self):
        del self.mark
    
    ## markline = _Marker("mark", 3) # mark_set/mark_unset
    
    @property
    def mark(self):
        return self.__mark
    
    @mark.setter
    def mark(self, v):
        if v != -1:
            self.__mark = v
            ln = self.LineFromPosition(v)
            self.MarkerDeleteAll(0)
            self.MarkerAdd(ln, 0)
            self.handler('mark_set', v)
        else:
            del self.mark
    
    @mark.deleter
    def mark(self):
        v = self.__mark
        if v != -1:
            self.__mark = -1
            self.MarkerDeleteAll(0)
            self.handler('mark_unset', v)
    
    def set_marker(self):
        self.mark = self.cpos
    
    def goto_marker(self):
        if self.mark != -1:
            self.EnsureVisible(self.markline)
            self.goto_char(self.mark)
            self.recenter()
    
    def set_line_marker(self):
        if self.linemark == self.cline:
            self.linemark = -1 # toggle marker
        else:
            self.linemark = self.cline
    
    def goto_line_marker(self):
        if self.linemark != -1:
            self.EnsureVisible(self.linemark)
            self.goto_line(self.linemark)
            self.recenter()
    
    def exchange_point_and_mark(self):
        p = self.cpos
        q = self.mark
        if q != -1:
            self.goto_char(q)
            self.recenter()
            self.mark = p
        else:
            self.post_message("No marks")
    
    ## --------------------------------
    ## Attributes of the editor
    ## --------------------------------
    py_styles = {
        stc.STC_P_DEFAULT       : 0,    # etc. space \r\n\\$\0 (non-identifier)
        stc.STC_P_OPERATOR      : 'op', # ops. `@=+-/*%<>&|^~!?.,:;([{<>}])
        stc.STC_P_COMMENTLINE   : 'comment',
        stc.STC_P_COMMENTBLOCK  : 'comment',
        stc.STC_P_NUMBER        : 'suji',
        stc.STC_P_STRING        : 'moji',
        stc.STC_P_STRINGEOL     : 'moji',
        stc.STC_P_CHARACTER     : 'moji',
        stc.STC_P_TRIPLE        : 'moji',
        stc.STC_P_TRIPLEDOUBLE  : 'moji',
        stc.STC_P_IDENTIFIER    : 'word',
        stc.STC_P_WORD2         : 'word',
        stc.STC_P_DECORATOR     : 'word',
        stc.STC_P_WORD          : 'keyword',
        stc.STC_P_CLASSNAME     : 'class',
        stc.STC_P_DEFNAME       : 'def',
    }
    
    def get_style(self, pos):
        c = self.get_char(pos)
        st = self.GetStyleAt(pos)
        sty = self.py_styles[st]
        if sty == 0:
            if c in ' \t': return 'space'
            if c in '\r\n': return 'linesep'
        if sty == 'op':
            if c in '.':
                if '...' in self.get_text(pos-2, pos+3):
                    return 'ellipsis'
                return 'word'
            if c in ",:;": return 'sep'
            if c in "({[": return 'lparen'
            if c in ")}]": return 'rparen'
        return sty
    
    def get_char(self, pos):
        """Returns the character at the position."""
        return chr(self.GetCharAt(pos))
    
    def get_text(self, start, end):
        """Retrieve a range of text.
        
        The range must be given as 0 <= start:end <= TextLength,
        otherwise it will be modified to be in [0:TextLength].
        """
        if start > end:
            start, end = end, start
        return self.GetTextRange(max(start, 0),
                                 min(end, self.TextLength))
    
    anchor = property(
        lambda self: self.GetAnchor(),
        lambda self,v: self.SetAnchor(v))
    
    cpos = property(
        lambda self: self.GetCurrentPos(),
        lambda self,v: self.SetCurrentPos(v))
    
    cline = property(
        lambda self: self.GetCurrentLine(),
        lambda self,v: self.SetCurrentPos(self.PositionFromLine(v)))
    
    @property
    def bol(self):
        """beginning of line"""
        text, lp = self.CurLine
        return self.cpos - lp
    
    @property
    def eol(self):
        """end of line"""
        text, lp = self.CurLine
        text = text.strip('\r\n') # remove linesep: '\r' and '\n'
        return (self.cpos - lp + len(text.encode()))
    
    @property
    def caretline(self):
        """Text of the range (bol, eol) at the caret-line
        
        Similar to CurLine, but with the trailing crlf truncated.
        For shells, the leading prompt is also be truncated due to overridden bol.
        """
        return self.GetTextRange(self.bol, self.eol)
    
    @property
    def expr_at_caret(self):
        """A syntax unit (expression) at the caret-line"""
        p = q = self.cpos
        lsty = self.get_style(p-1)
        rsty = self.get_style(p)
        if lsty == rsty == 'moji': # inside string
            return ''
        elif lsty == 'suji' or rsty == 'suji':
            styles = {'suji'}
        elif lsty in ('word', 'moji', 'rparen')\
          or rsty in ('word', 'moji', 'lparen'):
            styles = {'word', 'moji', 'paren'}
        else:
            return ''
        while 1:
            p, start, sty = self.get_preceding_atom(p)
            if sty not in styles:
                break
        while 1:
            end, q, sty = self.get_following_atom(q)
            if sty not in styles:
                break
        return self.GetTextRange(start, end).strip()
    
    @property
    def topic_at_caret(self):
        """Topic word at the caret or selected substring
        The caret scouts back and forth to scoop a topic.
        """
        topic = self.SelectedText
        if topic:
            return topic
        else:
            delims = "({[<>]}),:; \t\r\n"
            p = q = self.cpos
            if self.get_char(p-1) not in delims:
                self.WordLeft()
                p = self.cpos
            if self.get_char(q) not in delims:
                self.WordRightEnd()
                q = self.cpos
            self.cpos = self.anchor = p # save_excursion
            return self.GetTextRange(p, q)
    
    ## --------------------------------
    ## Python syntax and indentation
    ## --------------------------------
    py_indent_re  = r"if|else|elif|for|while|with|def|class|try|except|finally"
    py_outdent_re = r"else:|elif\s+.*:|except(\s+.*)?:|finally:"
    py_closing_re = r"break|pass|return|raise|continue"
    
    def on_indent_line(self, evt):
        if self.SelectedText:
            evt.Skip()
        else:
            self.py_indent_line()
    
    def on_outdent_line(self, evt):
        if self.SelectedText:
            evt.Skip()
        else:
            self.py_outdent_line()
    
    @editable
    def py_indent_line(self):
        """Indent the current line"""
        text = self.caretline  # w/ no-prompt
        lstr = text.lstrip()   # w/ no-indent
        p = self.bol + len(text) - len(lstr) # for multi-byte string
        offset = max(0, self.cpos - p)
        indent = self.py_calc_indent(self.cline) # check current/previous line
        self.Replace(self.bol, p, ' '*indent)
        self.goto_char(self.bol + indent + offset)
    
    @editable
    def py_outdent_line(self):
        """Outdent the current line"""
        text = self.caretline  # w/ no-prompt
        lstr = text.lstrip()   # w/ no-indent
        p = self.bol + len(text) - len(lstr) # for multi-byte string
        offset = max(0, self.cpos - p)
        indent = len(text) - len(lstr) - 4
        self.Replace(self.bol, p, ' '*indent)
        self.goto_char(self.bol + indent + offset)
    
    def py_calc_indent(self, line):
        """Calculate indent spaces from previous line."""
        text = self.GetLine(line - 1)
        lstr, indent = self.py_strip_indents(text) # check previous line
        try:
            tokens = list(shlex.shlex(lstr)) # strip comment
        except ValueError:
            return indent # no closing quotation/paren
        else:
            if not tokens:
                return indent
            if tokens[-1] == '\\':
                return indent + 2
            if tokens[-1] == ':' and re.match(self.py_indent_re, tokens[0]):
                return indent + 4
            if re.match(self.py_closing_re, tokens[0]):
                return indent - 4
        text = self.GetLine(line)
        lstr, _indent = self.py_strip_indents(text) # check current line
        if re.match(self.py_outdent_re, lstr):
            indent -= 4
        return indent
    
    @classmethod
    def py_strip_indents(self, text):
        """Returns left-stripped text and the number of indents."""
        text = self.py_strip_prompts(text)
        lstr = text.lstrip(' \t')
        indent = len(text) - len(lstr)
        return lstr, indent
    
    @classmethod
    def py_strip_prompts(self, text):
        """Returns text without a leading prompt."""
        for ps in (sys.ps1, sys.ps2, sys.ps3):
            if text.startswith(ps):
                text = text[len(ps):]
                break
        return text
    
    def py_eval_line(self, globals, locals):
        if self.CallTipActive():
            self.CallTipCancel()
        
        def _gen_text():
            text = self.SelectedText
            if text:
                yield text
            else:
                yield self.caretline
                yield self.expr_at_caret
        
        status = "No words"
        for text in filter(None, _gen_text()):
            try:
                obj = eval(text, globals, locals)
            except Exception as e:
                status = "- {}: {!r}".format(e, text)
            else:
                self.CallTipShow(self.cpos, pformat(obj))
                self.message(text)
                return
        self.message(status)
    
    def py_exec_region(self, globals, locals, filename):
        try:
            code = compile(self.Text, filename, "exec")
            exec(code, globals, locals)
            dispatcher.send(signal='Interpreter.push',
                            sender=self, command=None, more=False)
        except Exception as e:
            msg = traceback.format_exc()
            err = re.findall(r"^\s+File \"(.*?)\", line ([0-9]+)", msg, re.M)
            lines = [int(l) for f,l in err if f == filename]
            if lines:
                lx = lines[-1] - 1
                self.red_arrow = lx
                self.goto_line(lx)
                self.EnsureVisible(lx) # expand if folded
                self.EnsureCaretVisible()
            self.message("- {}".format(e))
            ## print(msg, file=sys.__stderr__)
        else:
            self.buffer.codename = filename
            self.buffer.code = code
            self.push_current()
            del self.red_arrow
            self.handler('py_region_executed', self)
            self.message("Evaluated {!r} successfully".format(filename))
    
    def py_get_region(self, line):
        """Line numbers of code head and tail containing the line.
        
        Note: It requires a code object compiled using py_exec_region.
              If the code doesn't exists, it returns the folding region.
        """
        if not self.buffer.code:
            return self.get_region(line)
        lc, le = 0, self.LineCount
        linestarts = list(dis.findlinestarts(self.buffer.code))
        for i, ln in reversed(linestarts):
            if line >= ln-1:
                lc = ln-1
                break
            le = ln-1
        return lc, le
    
    ## --------------------------------
    ## Fold / Unfold functions
    ## --------------------------------
    
    def is_folder_shown(self):
        return self.GetMarginSensitive(0)
    
    def show_folder(self, show=True, colour=None):
        """Show folder margin.
        
        Call me before set_style.
        Or else the margin color will be default light gray
        
        If show is True, the colour is used for margin hi-colour (default :g).
        If show is False, the colour is used for margin line colour (default :b)
        """
        if show:
            self.SetMarginWidth(2, 12)
            self.SetMarginSensitive(0, True)
            self.SetMarginSensitive(1, True)
            self.SetMarginSensitive(2, True)
            self.SetFoldMarginColour(True, self.CaretLineBackground)
            self.SetFoldMarginHiColour(True, colour or 'light gray')
        else:
            self.SetMarginWidth(2, 1)
            self.SetMarginSensitive(0, False)
            self.SetMarginSensitive(1, False)
            self.SetMarginSensitive(2, False)
            self.SetFoldMarginColour(True, colour or 'black')
            self.SetFoldMarginHiColour(True, colour or 'black')
    
    def OnMarginClick(self, evt): #<wx._stc.StyledTextEvent>
        lc = self.LineFromPosition(evt.Position)
        level = self.GetFoldLevel(lc) ^ stc.STC_FOLDLEVELBASE
        
        ## `level` indicates indent-header flag or indent-level number
        if level and evt.Margin == 2:
            self.toggle_fold(lc)
        else:
            self.handler('select_line', evt)
    
    def OnMarginRClick(self, evt): #<wx._stc.StyledTextEvent>
        """Popup context menu"""
        def _Icon(key):
            return wx.ArtProvider.GetBitmap(key, size=(16,16))
        
        Menu.Popup(self, [
            (wx.ID_DOWN, "&Fold ALL", _Icon(wx.ART_MINUS),
                lambda v: self.FoldAll(0)),
                
            (wx.ID_UP, "&Expand ALL", _Icon(wx.ART_PLUS),
                lambda v: self.FoldAll(1)),
        ])
    
    def toggle_fold(self, lc):
        """Similar to ToggleFold, but the top header containing
        the specified line switches between expanded and contracted.
        """
        while 1:
            la = self.GetFoldParent(lc) # get folding root
            if la == -1:
                break
            lc = la
        self.ToggleFold(lc)
        self.EnsureLineOnScreen(lc)
    
    def get_region(self, line):
        """Line numbers of folding head and tail containing the line."""
        lc = line
        le = lc + 1
        while 1:
            la = self.GetFoldParent(lc) # get folding root
            if la == -1:
                break
            lc = la
        while 1:
            level = self.GetFoldLevel(le) ^ stc.STC_FOLDLEVELBASE
            if level == 0 or level == stc.STC_FOLDLEVELHEADERFLAG:
                break
            le += 1
        return lc, le
    
    def on_linesel_begin(self, evt):
        p = evt.Position
        self.goto_char(p)
        self.cpos = q = self.eol
        self.CaptureMouse()
        if 1:
            lc = self.LineFromPosition(p)
            if not self.GetFoldExpanded(lc): # :not expanded
                self.CharRightExtend()
                q = self.cpos
                if q == self.TextLength:
                    q -= 1
        self._anchors = [p, q]
        evt.Skip()
    
    def on_linesel_motion(self, evt): #<wx._core.MouseEvent>
        p = self.PositionFromPoint(evt.Position)
        po, qo = self._anchors
        if p >= po:
            lc = self.LineFromPosition(p)
            text = self.GetLine(lc)
            self.cpos = p + len(text)
            self.anchor = po
            if not self.GetFoldExpanded(lc): # :not expanded
                self.CharRightExtend()
                self._anchors[1] = self.cpos
        else:
            self.cpos = p
            self.anchor = qo
        evt.Skip()
    
    def on_linesel_end(self, evt):
        del self._anchors
        if self.HasCapture():
            self.ReleaseMouse()
        evt.Skip()
    
    ## --------------------------------
    ## Preferences / Appearance
    ## --------------------------------
    
    def set_style(self, spec=None, **kwargs):
        spec = spec and spec.copy() or {}
        spec.update(kwargs)
        
        def _map(sc):
            return dict(kv.partition(':')[::2] for kv in sc.split(','))
        
        ## Apply the default style first
        default = spec.pop(stc.STC_STYLE_DEFAULT, '')
        if default:
            self.StyleSetSpec(stc.STC_STYLE_DEFAULT, default)
            self.StyleClearAll()
        
        ## Add style to the folding margin
        item = _map(spec.get(stc.STC_STYLE_LINENUMBER, ''))
        if item:
            ## Set colors used as a chequeboard pattern,
            ## lo (back) one of the colors
            ## hi (fore) the other color
            if self.GetMarginSensitive(2):
                ## 12 pixel chequeboard, fore being default colour
                self.SetFoldMarginColour(True, item.get('back'))
                self.SetFoldMarginHiColour(True, 'light gray')
            else:
                ## one pixel solid line, the same colour as the line number
                self.SetFoldMarginColour(True, item.get('fore'))
                self.SetFoldMarginHiColour(True, item.get('fore'))
        
        ## Custom style for caret and line colour
        item = _map(spec.pop(stc.STC_STYLE_CARETLINE, ''))
        if item:
            self.SetCaretLineVisible(0)
            if 'fore' in item:
                self.SetCaretForeground(item['fore'])
            if 'back' in item:
                self.SetCaretLineBackground(item['back'])
                self.SetCaretLineVisible(1)
            if 'size' in item:
                self.SetCaretWidth(int(item['size']))
                self.SetCaretStyle(stc.STC_CARETSTYLE_LINE)
            if 'bold' in item:
                self.SetCaretStyle(stc.STC_CARETSTYLE_BLOCK)
        
        ## Custom indicator for search-word
        item = _map(spec.pop(stc.STC_P_WORD3, ''))
        if item:
            self.IndicatorSetForeground(0, item.get('fore') or "red")
            self.IndicatorSetForeground(1, item.get('back') or "red")
            try:
                self.IndicatorSetHoverStyle(1, stc.STC_INDIC_ROUNDBOX)
                self.IndicatorSetHoverForeground(1, "blue")
            except AttributeError:
                pass
        
        for key, value in spec.items():
            self.StyleSetSpec(key, value)
    
    def match_paren(self):
        p = self.cpos
        if self.get_char(p-1) in ")}]>":
            q = self.BraceMatch(p-1)
            if q != -1:
                self.BraceHighlight(q, p-1) # matched the preceding char
                return q
            else:
                self.BraceBadLight(p-1)
        elif self.get_char(p) in "({[<":
            q = self.BraceMatch(p)
            if q != -1:
                self.BraceHighlight(p, q) # matched the following char
                return q
            else:
                self.BraceBadLight(p)
        else:
            self.BraceHighlight(-1,-1) # no highlight
    
    def over(self, mode=1):
        """Set insert or overtype.
        mode in {0:insert, 1:over, None:toggle}
        """
        self.Overtype = mode if mode is not None else not self.Overtype
    
    def wrap(self, mode=1):
        """Sets whether text is word wrapped.
        (override) mode in {0:no-wrap, 1:word-wrap, 2:char-wrap,
                            3:whitespace-wrap, None:toggle}
        """
        self.WrapMode = mode if mode is not None else not self.WrapMode
    
    def recenter(self, ln=None):
        """Scroll the cursor line to the center of screen.
        If ln=0, the cursor moves to the top of the screen.
        If ln=-1 (ln=n-1), moves to the bottom
        """
        n = self.LinesOnScreen() # lines completely visible
        m = n//2 if ln is None else ln % n if ln < n else n # ln[0:n]
        vl = self.calc_vline(self.cline)
        self.ScrollToLine(vl - m)
    
    def calc_vline(self, line):
        """Virtual line numberin the buffer window."""
        pos = self.PositionFromLine(line)
        w, h = self.PointFromPosition(pos)
        return self.FirstVisibleLine + h//self.TextHeight(0)
    
    def EnsureLineOnScreen(self, line):
        """Ensure a particular line is visible by scrolling the buffer
        without expanding any header line hiding it.
        """
        n = self.LinesOnScreen() # lines completely visible
        hl = self.FirstVisibleLine
        vl = self.calc_vline(line)
        if vl < hl:
            self.ScrollToLine(vl)
        elif vl > hl + n - 1:
            self.ScrollToLine(vl - n + 1)
    
    def EnsureLineMoreOnScreen(self, line):
        """Ensure a particular line is visible by scrolling the buffer
        without expanding any header line hiding it.
        If the line is at the screen edge, recenter it.
        """
        n = self.LinesOnScreen() # lines completely visible
        hl = self.FirstVisibleLine
        vl = self.calc_vline(line)
        if not hl < vl < hl + n - 1:
            self.ScrollToLine(vl - n//2)
    
    ## --------------------------------
    ## Search functions
    ## --------------------------------
    
    def get_right_paren(self, p):
        if self.get_char(p) in "({[<": # left-parentheses, <
            q = self.BraceMatch(p)
            return q if q < 0 else q+1
    
    def get_left_paren(self, p):
        if self.get_char(p-1) in ")}]>": # right-parentheses, >
            q = self.BraceMatch(p-1)
            return q
    
    def get_right_quotation(self, p):
        st = self.get_style(p)
        if st == 'moji':
            if self.get_style(p-1) == 'moji': # inside string
                return
            while self.get_style(p) == st and p < self.TextLength:
                p += 1
            return p
        if st == 'comment':
            text, lp = self.CurLine
            text = text[lp:]
            if text[0] in "\"\'":
                try:
                    lexer = shlex.shlex(text)
                    return p + len(lexer.get_token())
                except ValueError:
                    pass # no closing quotation
    
    def get_left_quotation(self, p):
        st = self.get_style(p-1)
        if st == 'moji':
            if self.get_style(p) == 'moji': # inside string
                return
            while self.get_style(p-1) == st and p > 0:
                p -= 1
            return p
        if st == 'comment':
            text, lp = self.CurLine
            text = text[:lp][::-1]
            if text[0] in "\"\'":
                try:
                    lexer = shlex.shlex(text)
                    return p - len(lexer.get_token())
                except ValueError:
                    pass # no closing quotation
    
    def get_following_atom(self, p):
        q = p
        st = self.get_style(p)
        if st == "lparen":
            q = self.BraceMatch(p)
            if q == -1:
                q = self.TextLength
                st = None # no closing paren
            else:
                q += 1
                st = 'paren' # closed
        else:
            while self.get_style(q) == st and q < self.TextLength:
                q += 1
        return p, q, st
    
    def get_preceding_atom(self, p):
        q = p
        st = self.get_style(p-1)
        if st == "rparen":
            p = self.BraceMatch(p-1)
            if p == -1:
                p = 0
                st = None # no closing paren
            else:
                st = 'paren' # closed
        else:
            while self.get_style(p-1) == st and p > 0:
                p -= 1
        return p, q, st
    
    def grep_forward(self, pattern):
        text = self.GetTextRange(self.eol, self.TextLength)
        errs = re.finditer(pattern, text, re.M)
        for err in errs:
            p, q = err.span()
            self.goto_char(q + self.eol)
            self.goto_char(self.bol)
            self.mark = self.cpos
            self.EnsureVisible(self.cline)
            yield err
    
    def grep_barckward(self, pattern):
        text = self.GetTextRange(0, self.cpos)
        errs = re.finditer(pattern, text, re.M)
        for err in reversed(list(errs)):
            p, q = err.span()
            self.goto_char(p)
            self.goto_char(self.bol)
            self.mark = self.cpos
            self.EnsureVisible(self.cline)
            yield err
    
    def search_text(self, text):
        """Yields raw-positions where `text` is found."""
        word = text.encode()
        raw = self.TextRaw
        pos = -1
        while 1:
            pos = raw.find(word, pos+1)
            if pos < 0:
                break
            yield pos
    
    def filter_text(self, text=None):
        self.__lines = []
        if not text:
            text = self.topic_at_caret
        if not text:
            self.message("- No words")
            for i in range(2):
                self.SetIndicatorCurrent(i)
                self.IndicatorClearRange(0, self.TextLength)
            return
        lw = len(text.encode()) # for multi-byte string
        lines = []
        for p in self.search_text(text):
            lines.append(self.LineFromPosition(p))
            for i in range(2):
                self.SetIndicatorCurrent(i)
                self.IndicatorFillRange(p, lw)
        self.__lines = sorted(set(lines)) # keep order, no duplication
        self.message("{}: {} found".format(text, len(lines)))
        self.parent.findData.FindString = text
    
    def on_filter_text_enter(self, evt):
        if not self.__lines:
            self.handler('quit', evt)
            return
        def _format(ln):
            return "{:4d} {}".format(ln+1, self.GetLine(ln).rstrip())
        self.AutoCompSetSeparator(ord('\n'))
        self.AutoCompShow(0, '\n'.join(map(_format, self.__lines))) # cf. gen_autocomp
        self.AutoCompSelect("{:4d}".format(self.cline+1))
        self.Bind(stc.EVT_STC_AUTOCOMP_SELECTION,
                  handler=self.on_filter_text_selection)
        ## evt.Skip()
    
    def on_filter_text_exit(self, evt):
        if self.AutoCompActive():
            self.AutoCompCancel()
        self.Unbind(stc.EVT_STC_AUTOCOMP_SELECTION,
                    handler=self.on_filter_text_selection)
        ## evt.Skip()
    
    def on_filter_text_selection(self, evt):
        line = self.__lines[self.AutoCompGetCurrent()]
        self.EnsureVisible(line) # expand if folded
        self.goto_line(line)
        self.recenter()
        self.on_filter_text_exit(evt)
    
    ## --------------------------------
    ## goto, skip, selection, etc.
    ## --------------------------------
    
    def goto_char(self, pos, selection=False):
        """Goto char position with selection."""
        if pos is None or pos < 0:
            return
        ## if pos < 0:
        ##     pos += self.TextLength + 1 # Counts end-of-buffer (+1:\0)
        ##     return
        if selection:
            self.cpos = pos
        else:
            self.GotoPos(pos)
        return True
    
    def goto_line(self, ln, selection=False):
        """Goto line with selection."""
        if ln is None or ln < 0:
            return
        ## if ln < 0:
        ##     ln += self.LineCount
        if selection:
            self.cline = ln
        else:
            self.GotoLine(ln)
        return True
    
    def skip_chars_forward(self, chars):
        p = self.cpos
        while self.get_char(p) in chars and p < self.TextLength:
            p += 1
        self.goto_char(p)
    
    def skip_chars_backward(self, chars):
        p = self.cpos
        while self.get_char(p-1) in chars and p > 0:
            p -= 1
        self.goto_char(p)
    
    def back_to_indentation(self):
        text = self.caretline # w/ no-prompt
        lstr = text.lstrip()  # w/ no-indent
        p = self.bol + len(text) - len(lstr) # for multi-byte string
        self.goto_char(p)
        self.ScrollToColumn(0)
    
    def beginning_of_line(self):
        self.goto_char(self.bol)
        self.ScrollToColumn(0)
    
    def end_of_line(self):
        self.goto_char(self.eol)
    
    def beginning_of_buffer(self):
        self.mark = self.cpos
        self.goto_char(0)
    
    def end_of_buffer(self):
        self.mark = self.cpos
        self.goto_char(self.TextLength)
    
    def goto_matched_paren(self):
        p = self.cpos
        return (self.goto_char(self.get_left_paren(p))
             or self.goto_char(self.get_right_paren(p))
             or self.goto_char(self.get_left_quotation(p))
             or self.goto_char(self.get_right_quotation(p)))
    
    def selection_forward_word_or_paren(self):
        p = self.cpos
        return (self.goto_char(self.get_right_paren(p), True)
             or self.goto_char(self.get_right_quotation(p), True)
             or self.WordRightEndExtend())
    
    def selection_backward_word_or_paren(self):
        p = self.cpos
        return (self.goto_char(self.get_left_paren(p), True)
             or self.goto_char(self.get_left_quotation(p), True)
             or self.WordLeftExtend())
    
    def selection_forward_atom(self):
        p, q, sty = self.get_following_atom(self.cpos)
        self.cpos = q
        return sty
    
    def selection_backward_atom(self):
        p, q, sty = self.get_preceding_atom(self.cpos)
        self.cpos = p
        return sty
    
    @contextlib.contextmanager
    def save_excursion(self):
        try:
            p = self.cpos
            q = self.anchor
            vpos = self.GetScrollPos(wx.VERTICAL)
            hpos = self.GetScrollPos(wx.HORIZONTAL)
            yield
        finally:
            self.GotoPos(p)
            self.SetAnchor(q)
            self.ScrollToLine(vpos)
            self.SetXOffset(hpos)
    
    @contextlib.contextmanager
    def pre_selection(self):
        try:
            p = self.cpos
            q = self.anchor
            yield
        finally:
            if p < q:
                self.cpos = p
            else:
                self.anchor = q
    
    @contextlib.contextmanager
    def off_readonly(self):
        try:
            r = self.ReadOnly
            self.ReadOnly = 0
            yield self
        finally:
            self.ReadOnly = r
    
    ## --------------------------------
    ## Edit: insert, eat, kill, comment
    ## --------------------------------
    comment_prefix = "## "
    
    @editable
    def comment_out_selection(self, from_=None, to_=None):
        """Comment out the selected text."""
        if from_ is not None: self.anchor = from_
        if to_ is not None: self.cpos = to_
        prefix = self.comment_prefix
        with self.pre_selection():
            text = re.sub("^", prefix, self.SelectedText, flags=re.M)
            ## Don't comment out the last (blank) line.
            lines = text.splitlines()
            if len(lines) > 1 and lines[-1].endswith(prefix):
                text = text[:-len(prefix)]
            self.ReplaceSelection(text)
    
    @editable
    def uncomment_selection(self, from_=None, to_=None):
        """Uncomment the selected text."""
        if from_ is not None: self.anchor = from_
        if to_ is not None: self.cpos = to_
        with self.pre_selection():
            text = re.sub("^#+ ", "", self.SelectedText, flags=re.M)
            self.ReplaceSelection(text)
    
    @editable
    def comment_out_line(self):
        if self.SelectedText:
            self.comment_out_selection()
        else:
            ## align with current or previous indent position
            self.back_to_indentation()
            text = self.GetLine(self.cline - 1)
            lstr, j = self.py_strip_indents(text)
            if lstr.startswith('#'):
                text = self.GetLine(self.cline)
                lstr, k = self.py_strip_indents(text)
                self.goto_char(self.bol + min(j, k))
            self.comment_out_selection(self.cpos, self.eol)
            self.LineDown()
    
    @editable
    def uncomment_line(self):
        if self.SelectedText:
            self.uncomment_selection()
        else:
            self.back_to_indentation()
            self.uncomment_selection(self.cpos, self.eol)
            self.LineDown()
    
    @editable
    def eat_white_forward(self):
        p = self.cpos
        self.skip_chars_forward(' \t')
        self.Replace(p, self.cpos, '')
    
    @editable
    def eat_white_backward(self):
        p = self.cpos
        self.skip_chars_backward(' \t')
        self.Replace(max(self.cpos, self.bol), p, '')
    
    @editable
    def kill_line(self):
        p = self.eol
        text, lp = self.CurLine
        if p == self.cpos:
            if self.get_char(p) == '\r': p += 1
            if self.get_char(p) == '\n': p += 1
        self.Replace(self.cpos, p, '')
    
    @editable
    def backward_kill_line(self):
        p = self.bol
        text, lp = self.CurLine
        if text[:lp] == sys.ps2: # caret at the prompt head
            p -= len(sys.ps2)
            lp -= len(sys.ps2)
        if text[:lp] == '' and p: # caret at the beginning of the line
            if self.get_char(p-1) == '\n': p -= 1
            if self.get_char(p-1) == '\r': p -= 1
        self.Replace(p, self.cpos, '')
    
    @editable
    def insert_space_like_tab(self):
        """Insert half-width spaces forward as if feeling like [tab].
        ???????????????????????????????????????????????????????????????
        """
        self.eat_white_forward()
        text, lp = self.CurLine
        self.WriteText(' ' * (4 - lp % 4))
    
    @editable
    def delete_backward_space_like_tab(self):
        """Delete half-width spaces backward as if feeling like [S-tab].
        ?????????+?????????????????????????????????????????????????????????
        """
        self.eat_white_forward()
        text, lp = self.CurLine
        for i in range(lp % 4 or 4):
            p = self.cpos
            if self.get_char(p-1) != ' ' or p == self.bol:
                break
            self.cpos = p-1
        self.ReplaceSelection('')


class Buffer:
    """Data class of buffer
    
    Attributes:
       filename : buffer-file-name
         lineno : marked lineno (>=1)
       codename : code-file-name (e.g. '<scratch>')
           code : code object compiled using py_exec_region
        mtdelta : timestamp delta (for checking external mod)
    """
    def __init__(self, data=None):
        (self.filename, self.lineno,
         self.codename, self.code) = data or (None, 0, None, None)
    
    def __eq__(self, buf):
        return (type(self) is type(buf)
            and self.filename == buf.filename
            and self.codename == buf.codename
            and self.code is buf.code)
    
    def __contains__(self, v):
        if isinstance(v, str):
            if v.startswith('<'):
                return v == self.codename
            else:
                return v == self.filename
        elif inspect.iscode(v) and self.code:
            return v is self.code\
                or v in self.code.co_consts
    
    @property
    def name(self):
        if self.codename and self.filename:
            return "{} {}".format(self.codename, self.filename)
        else:
            return self.codename or self.filename
    
    @property
    def filename(self):
        return self.__filename
    
    @filename.setter
    def filename(self, f):
        if f and os.path.isfile(f):
            self.__mtime = os.path.getmtime(f)
        else:
            self.__mtime = None
        self.__filename = f
    
    @property
    def mtdelta(self):
        f = self.filename
        if f and os.path.isfile(f):
            return os.path.getmtime(f) - self.__mtime


class Editor(EditorInterface, EditWindow):
    """Python code editor

    Attributes:
           Name : buffer-name (e.g. '*scratch*') => wx.Window.Name
         target : codename or filename (referred by debugger)
         buffer : current buffer
    buffer_list : list of all buffer data
   buffer_index : index of the currently loaded data
    """
    STYLE = {
        stc.STC_STYLE_DEFAULT     : "fore:#7f7f7f,back:#ffffb8,size:9,face:MS Gothic",
        stc.STC_STYLE_LINENUMBER  : "fore:#000000,back:#ffffb8,size:9",
        stc.STC_STYLE_BRACELIGHT  : "fore:#000000,back:#ffffb8,bold",
        stc.STC_STYLE_BRACEBAD    : "fore:#000000,back:#ff0000,bold",
        stc.STC_STYLE_CONTROLCHAR : "size:6",
        stc.STC_STYLE_CARETLINE   : "fore:#000000,back:#ffff7f,size:2", # optional
        stc.STC_P_DEFAULT         : "fore:#000000",
        stc.STC_P_OPERATOR        : "fore:#000000",
        stc.STC_P_IDENTIFIER      : "fore:#000000",
        stc.STC_P_COMMENTLINE     : "fore:#007f7f,back:#ffcfcf",
        stc.STC_P_COMMENTBLOCK    : "fore:#007f7f,back:#ffcfcf,eol",
        stc.STC_P_NUMBER          : "fore:#7f0000",
        stc.STC_P_STRINGEOL       : "fore:#000000,back:#ffcfcf",
        stc.STC_P_CHARACTER       : "fore:#7f7f7f",
        stc.STC_P_STRING          : "fore:#7f7f7f",
        stc.STC_P_TRIPLE          : "fore:#7f7f7f",
        stc.STC_P_TRIPLEDOUBLE    : "fore:#7f7f7f",
        stc.STC_P_CLASSNAME       : "fore:#7f00ff,bold",
        stc.STC_P_DEFNAME         : "fore:#0000ff,bold",
        stc.STC_P_WORD            : "fore:#0000ff",
        stc.STC_P_WORD2           : "fore:#b8007f",
        stc.STC_P_WORD3           : "fore:#ff0000,back:#ffff00", # optional for search word
        stc.STC_P_DECORATOR       : "fore:#e08040",
    }
    
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.message)
    
    @property
    def target(self):
        return self.buffer.codename or self.buffer.filename
    
    def __init__(self, parent, name="editor", **kwargs):
        EditWindow.__init__(self, parent, **kwargs)
        EditorInterface.__init__(self)
        
        self.__parent = parent  # parent:<ShellFrame>
                                # Parent:<AuiNotebook>
        self.Name = name
        self.buffer = Buffer()
        self.__buffers = []
        
        self.Bind(stc.EVT_STC_UPDATEUI, self.OnUpdate) # skip to brace matching
        
        self.Bind(stc.EVT_STC_SAVEPOINTLEFT, self.OnSavePointLeft)
        self.Bind(stc.EVT_STC_SAVEPOINTREACHED, self.OnSavePointReached)
        
        @self.handler.bind('focus_set')
        def activate(v):
            self.handler('editor_activated', self)
            v.Skip()
        
        @self.handler.bind('focus_kill')
        def inactivate(v):
            self.handler('editor_inactivated', self)
            v.Skip()
        
        def dispatch(v):
            """Fork mouse events to the parent"""
            self.parent.handler(self.handler.event, v)
            v.Skip()
        
        self.handler.update({ # DNA<Editor>
            None : {
                  'stc_updated' : [ None, ],
                 'buffer_saved' : [ None, self.on_activated ],
                'buffer_loaded' : [ None, self.on_activated ],
              'buffer_unloaded' : [ None, self.on_activated ],
             'editor_activated' : [ None, self.on_activated ],
           'editor_inactivated' : [ None, self.on_inactivated ],
              '*button* dclick' : [ None, dispatch ],
             '*button* pressed' : [ None, dispatch ],
            '*button* released' : [ None, dispatch ],
           'py_region_executed' : [ None, self.on_activated ],
            },
        })
        self.define_key('C-x k', self.clear_all)
        self.define_key('C-x C-k', self.pop_current)
        
        self.set_style(self.STYLE)
    
    def trace_position(self):
        text, lp = self.CurLine
        self.message("{:>6d}:{} ({})".format(self.cline, lp, self.cpos), pane=-1)
    
    def OnUpdate(self, evt): #<wx._stc.StyledTextEvent>
        if evt.Updated & (stc.STC_UPDATE_SELECTION | stc.STC_UPDATE_CONTENT):
            self.trace_position()
            self.handler('stc_updated', evt)
        evt.Skip()
    
    def OnSavePointLeft(self, evt):
        if self.buffer.filename:
            self.parent.handler('caption_page', self, '* ' + self.Name)
        evt.Skip()
    
    def OnSavePointReached(self, evt):
        if self.buffer.filename:
            self.parent.handler('caption_page', self, self.Name)
        evt.Skip()
    
    def on_activated(self, editor):
        """Called when editor:self is activated."""
        if self.buffer.mtdelta:
            self.message("{!r} has been modified externally."
                         .format(self.buffer.filename))
        title = "{} file: {}".format(self.Name, self.buffer.name)
        self.parent.handler('title_window', title)
        self.trace_position()
    
    def on_inactivated(self, editor):
        """Called when editor:self is inactivated."""
        pass
    
    @property
    def menu(self):
        """Yields context menu"""
        def _restore_buffer(f):
            if f != self.buffer.filename and self.confirm_load():
                self.restore_buffer(f)
                self.SetFocus()
        
        def _menu(j, data):
            f, ln = data.filename, data.lineno
            return (j, "{}:{}".format(f, ln), '', wx.ITEM_CHECK,
                lambda v: _restore_buffer(f),
                lambda v: v.Check(f == self.buffer.filename))
        
        return (_menu(j+1, x) for j, x in enumerate(self.__buffers))
    
    @property
    def buffer_list(self):
        return self.__buffers or [self.buffer]
    
    @property
    def buffer_index(self):
        return next((j for j, x in enumerate(self.__buffers)
                        if x.filename == self.buffer.filename), -1)
    
    def push_current(self):
        if self.buffer.filename:
            self.buffer.lineno = self.markline + 1
            j = self.buffer_index
            if j != -1:
                self.__buffers[j] = self.buffer
            else:
                self.__buffers.append(self.buffer)
    
    def pop_current(self):
        if self.buffer.filename:
            j = self.buffer_index
            del self.__buffers[j]
            self.clear() # not to push-current the previous buffer
            if self.__buffers:
                if j > len(self.__buffers) - 1:
                    j -= 1
                self.buffer = self.__buffers[j]
                self.load_file(self.buffer.filename, self.buffer.lineno)
        else:
            self.clear()
    
    def clear(self):
        with self.off_readonly():
            self.ClearAll() # clear cache
        self.EmptyUndoBuffer()
        self.SetSavePoint()
        self.buffer = Buffer()
        self.handler('buffer_unloaded', self)
    
    def clear_all(self):
        del self.__buffers[:]
        self.clear()
    
    def restore_buffer(self, f):
        """Restore buffer with spedified f:filename or code.
        
        Note: STC data such as `UndoBuffer` is not restored.
        """
        if f is self.buffer:
            return None
        for buffer in self.__buffers:
            if f in buffer or f is buffer:
                self.push_current() # save cache
                self.buffer = buffer
                if self.LoadFile(buffer.filename):
                    self.markline = buffer.lineno - 1
                    self.goto_marker()
                    self.handler('buffer_loaded', self)
                    return True
                return False
    
    def load_cache(self, f, lineno=0, globals=None):
        """Load cached script file using linecache.
        
        Note: The file will be reloaded without confirmation.
        """
        linecache.checkcache(f)
        lines = linecache.getlines(f, globals)
        if lines:
            self.push_current() # save cache
            with self.off_readonly():
                self.Text = ''.join(lines)
            self.EmptyUndoBuffer()
            self.SetSavePoint()
            self.markline = lineno - 1
            self.goto_marker()
            self.buffer = Buffer((f, lineno, None, None))
            self.push_current() # save current
            self.handler('buffer_loaded', self)
            return True
        return False
    
    def load_file(self, filename, lineno=0):
        """Wrapped method of LoadFile
        
        Note: The file will be reloaded without confirmation.
        """
        if not filename:
            return None
        f = os.path.abspath(filename)
        self.push_current() # save cache
        if self.LoadFile(f):
            self.markline = lineno - 1
            self.goto_marker()
            self.buffer = Buffer((f, lineno, None, None))
            self.push_current() # save current
            self.handler('buffer_loaded', self)
            ## self.message("Loaded {!r} successfully.".format(filename))
            return True
        return False
    
    def save_file(self, filename):
        """Wrapped method of SaveFile
        
        Note: The file will be overwritten without confirmation.
        """
        if not filename:
            return None
        f = os.path.abspath(filename)
        if self.SaveFile(f):
            self.buffer.filename = f
            self.push_current() # save current
            self.handler('buffer_saved', self)
            ## self.message("Saved {!r} successfully.".format(filename))
            return True
        return False
    
    def LoadFile(self, filename):
        """Load the contents of file into the editor.
        (override) Use default file-io-encoding and original eol-code.
        """
        try:
            with open(filename, "r", encoding='utf-8', newline='') as i:
                with self.off_readonly():
                    self.Text = i.read()
            self.EmptyUndoBuffer()
            self.SetSavePoint()
            return True
        except Exception:
            return False
    
    def SaveFile(self, filename):
        """Write the contents of the editor to file.
        (override) Use default file-io-encoding and original eol-code.
        """
        try:
            with open(filename, "w", encoding='utf-8', newline='') as o:
                o.write(self.Text)
            self.SetSavePoint()
            return True
        except Exception:
            return False
    
    def confirm_load(self):
        """Confirm the loading with the dialog."""
        if self.IsModified() and self.buffer.filename:
            if wx.MessageBox(
                    "You are leaving unsaved contents.\n\n"
                    "The contents will be discarded.\n"
                    "Continue loading?",
                    "Load",
                    style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                self.post_message("The load has been canceled.")
                return None
        return True
    
    def confirm_save(self):
        """Confirm the saving with the dialog."""
        if self.buffer.mtdelta:
            if wx.MessageBox( # Note: dialog makes focus off
                    "The file has been modified externally.\n\n"
                    "The contents will be overwritten.\n"
                    "Continue saving?",
                    "Save",
                    style=wx.YES_NO|wx.ICON_INFORMATION) != wx.YES:
                self.post_message("The save has been canceled.")
                return None
        elif not self.IsModified():
            self.post_message("No need to save.")
            return False
        return True


class Interpreter(interpreter.Interpreter):
    def __init__(self, *args, **kwargs):
        parent = kwargs.pop('interpShell')
        interpreter.Interpreter.__init__(self, *args, **kwargs)
        self.parent = parent
        self.globals = self.locals
    
    def runcode(self, code):
        """Execute a code object.
        (override) Add globals referenced by the debugger in the parent:shell.
        """
        try:
            exec(code, self.globals, self.locals)
        except SystemExit:
            raise
        except Exception:
            self.showtraceback()
    
    def showtraceback(self):
        """Display the exception that just occurred.
        (override) Pass the traceback info to the parent:shell.
        """
        interpreter.Interpreter.showtraceback(self)
        
        t, v, tb = sys.exc_info()
        v.lineno = tb.tb_next.tb_lineno
        v.filename = tb.tb_next.tb_frame.f_code.co_filename
        self.parent.handler('interp_error', v)
    
    def showsyntaxerror(self, filename=None):
        """Display the syntax error that just occurred.
        (override) Pass the syntax error info to the parent:shell.
        """
        interpreter.Interpreter.showsyntaxerror(self, filename)
        
        t, v, tb = sys.exc_info()
        self.parent.handler('interp_error', v)
    
    def getCallTip(self, *args, **kwargs):
        """Return call tip text for a command.
        (override) Ignore DeprecationWarning: for function,
                   `formatargspec` is deprecated since Python 3.5.
        """
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            return interpreter.Interpreter.getCallTip(self, *args, **kwargs)


class Nautilus(EditorInterface, Shell):
    """Nautilus in the Shell with Editor interface
    
    Features:
        All objects in the process can be accessed using
           self : the target of the shell
           this : the module which includes target
    
    Magic syntax:
      quoteback : x`y --> y=x  | x`y`z --> z=y=x
       pullback : x@y --> y(x) | x@y@z --> z(y(x))
        apropos : x.y? [not] p --> shows apropos (not-)matched by predicates p
                   equiv. apropos(x, y [,ignorecase ?:True,??:False] [,pred=p])
                   y can contain regular expressions.
                       (RE) \\a:[a-z], \\A:[A-Z] can be used in addition.
                   p can be atom, callable, type (e.g., int, str, ...),
                       and any predicates such as inspect.isclass.
    
    *      info :  ?x --> info(x) shows short information
    *      help : ??x --> help(x) shows full description
    *    system :  !x --> sx(x) executes command in external shell
    
    *  denotes original syntax defined in wx.py.shell,
       for which, at present version, enabled with USE_MAGIC switch being on
    
    Shell built-in utility:
        @p          synonym of print
        @pp         synonym of pprint
        @info       short info
        @help       full description
        @dive       clone the shell with new target
        @timeit     measure the duration cpu time
        @profile    profile the func(*args, **kwargs)
        @filling    inspection using wx.lib.filling.Filling
        @watch      inspection using wx.lib.inspection.InspectionTool
        @edit       open file with your editor (undefined)
        @load       load file in the buffer
        @where      filename and lineno or module
        @debug      open pdb or show event-watcher and widget-tree
    
    Autocomp key bindings:
           C-up : [0] retrieve previous history
         C-down : [0] retrieve next history
       M-j, C-j : [0] call tooltip of eval (for the word selected or focused)
       M-h, C-h : [0] call tooltip of help (for the func selected or focused)
            TAB : [1] history-comp-mode
            M-p : [1] retrieve previous history in comp-mode
            M-n : [1] retrieve next history in comp-mode
            M-. : [2] word-comp-mode
            M-/ : [3] apropos-comp-mode
            M-, : [4] text-comp-mode
            M-m : [5] module-comp-mode
    
    * Autocomps are incremental when pressed any alnums,
                and decremental when backspace.
    
    Enter key bindings:
        C-enter : insert-line-break
        M-enter : duplicate-command
    
    This module is based on wx.py.shell.
        Some of the original key bindings are overridden.
        To read the original key bindings, see 'wx.py.shell.HELP_TEXT'.
        The original key bindings are mapped in esc-map,
        e.g., if you want to do 'select-all', type [ESC C-a], not [C-a]
    
    The most convenient way to see the details of keymaps on the shell:
        >>> self.shell.handler @p
         or self.shell.handler @filling
    
    A flaky nutshell:
        With great oven by Robin Dunn,
        Half-baked by Patrik K. O'Brien,
        and the other half by K. O'moto.
    """
    STYLE = {
        stc.STC_STYLE_DEFAULT     : "fore:#7f7f7f,back:#202020,size:9,face:MS Gothic",
        stc.STC_STYLE_LINENUMBER  : "fore:#000000,back:#f0f0f0,size:9",
        stc.STC_STYLE_BRACELIGHT  : "fore:#ffffff,back:#202020,bold",
        stc.STC_STYLE_BRACEBAD    : "fore:#ffffff,back:#ff0000,bold",
        stc.STC_STYLE_CONTROLCHAR : "size:6",
        stc.STC_STYLE_CARETLINE   : "fore:#ffffff,back:#123460,size:2", # optional
        stc.STC_P_DEFAULT         : "fore:#cccccc",
        stc.STC_P_OPERATOR        : "fore:#cccccc",
        stc.STC_P_IDENTIFIER      : "fore:#cccccc",
        stc.STC_P_COMMENTLINE     : "fore:#42c18c,back:#004040",
        stc.STC_P_COMMENTBLOCK    : "fore:#42c18c,back:#004040,eol",
        stc.STC_P_NUMBER          : "fore:#ffc080",
        stc.STC_P_STRINGEOL       : "fore:#cccccc,back:#004040,eol",
        stc.STC_P_CHARACTER       : "fore:#a0a0a0",
        stc.STC_P_STRING          : "fore:#a0a0a0",
        stc.STC_P_TRIPLE          : "fore:#a0a0a0,back:#004040",
        stc.STC_P_TRIPLEDOUBLE    : "fore:#a0a0a0,back:#004040",
        stc.STC_P_CLASSNAME       : "fore:#61d6d6,bold",
        stc.STC_P_DEFNAME         : "fore:#3a96ff,bold",
        stc.STC_P_WORD            : "fore:#80c0ff",
        stc.STC_P_WORD2           : "fore:#ff80ff",
        stc.STC_P_WORD3           : "fore:#ff0000,back:#ffff00", # optional for search word
        stc.STC_P_DECORATOR       : "fore:#ff8040",
    }
    
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.message)
    
    @property
    def target(self):
        return self.__target
    
    @target.setter
    def target(self, obj):
        """Reset the shell target object; Rename the parent title
        """
        if not hasattr(obj, '__dict__'):
            raise TypeError("Unable to target primitive object: {!r}".format(obj))
        
        self.__target = obj
        self.interp.locals = obj.__dict__
        try:
            obj.self = obj
            obj.this = inspect.getmodule(obj)
            obj.shell = self # overwrite the facade <wx.py.shell.ShellFacade>
        except AttributeError:
            ## print("- cannot overwrite target vars: {!r}".format(e))
            pass
        self.parent.handler('title_window', obj)
    
    @property
    def locals(self):
        return self.interp.locals
    
    @locals.setter
    def locals(self, v): # internal use only
        self.interp.locals = v
    
    @locals.deleter
    def locals(self): # internal use only
        self.interp.locals = self.__target.__dict__
    
    @property
    def globals(self):
        return self.interp.globals
    
    @globals.setter
    def globals(self, v): # internal use only
        self.interp.globals = v
    
    @globals.deleter
    def globals(self): # internal use only
        self.interp.globals = self.__target.__dict__
    
    modules = None
    
    def __init__(self, parent, target, name="root",
                 introText=None,
                 startupScript=None,
                 execStartupScript=True,
                 **kwargs):
        Shell.__init__(self, parent,
                 locals=target.__dict__,
                 interpShell=self,
                 InterpClass=Interpreter,
                 introText=introText,
                 startupScript=startupScript,
                 execStartupScript=execStartupScript, # if True, executes ~/.py
                 **kwargs)
        EditorInterface.__init__(self)
        
        self.__parent = parent  # parent:<ShellFrame>
                                # Parent:<AuiNotebook>
        self.target = target
        self.Name = name
        self.buffer = Buffer() # overwrite buffer <wx.py.buffer>
        
        wx.py.shell.USE_MAGIC = True
        wx.py.shell.magic = self.magic # called when USE_MAGIC
        
        ## cf. sys.modules (shell.modules
        if not self.modules:
            force = wx.GetKeyState(wx.WXK_CONTROL)\
                  & wx.GetKeyState(wx.WXK_SHIFT)
            Nautilus.modules = ut.find_modules(force)
        
        self.Bind(stc.EVT_STC_UPDATEUI, self.OnUpdate) # skip to brace matching
        self.Bind(stc.EVT_STC_CALLTIP_CLICK, self.OnCallTipClick)
        
        @self.handler.bind('window_destroy')
        def destroy(v):
            self.handler('shell_deleted', self)
            v.Skip()
        
        @self.handler.bind('focus_set')
        def activate(v):
            self.handler('shell_activated', self)
            v.Skip()
        
        @self.handler.bind('focus_kill')
        def inactivate(v):
            self.handler('shell_inactivated', self)
            v.Skip()
        
        def clear(v):
            ## Clear selection and statusline, no skip.
            ## *do not* clear autocomp, so that the event can skip to AutoComp properly.
            ## if self.AutoCompActive():
            ##     self.AutoCompCancel() # may delete selection
            if self.CanEdit():
                self.ReplaceSelection("")
            self.message("")
        
        def fork(v):
            self.handler(self.handler.event, v)
        
        def dispatch(v):
            """Fork mouse events to the parent"""
            self.parent.handler(self.handler.event, v)
            v.Skip()
        
        self.handler.update({ # DNA<Nautilus>
            None : {
                  'stc_updated' : [ None, ],
                 'shell_cloned' : [ None, ],
                'shell_deleted' : [ None, self.on_deleted ],
              'shell_activated' : [ None, self.on_activated ],
            'shell_inactivated' : [ None, self.on_inactivated ],
                 'interp_error' : [ None, self.on_interp_error ],
              '*button* dclick' : [ None, dispatch ],
             '*button* pressed' : [ None, dispatch ],
            '*button* released' : [ None, dispatch ],
            },
            -1 : { # original action of the wx.py.shell
                    '* pressed' : (0, skip, self.on_exit_escmap),
                 '*alt pressed' : (-1, ),
                '*ctrl pressed' : (-1, ),
               '*shift pressed' : (-1, ),
             '*[LR]win pressed' : (-1, ),
                 '*f12 pressed' : (-2, self.on_exit_escmap, self.on_enter_notemode),
            },
            -2 : { # Note mode
                  'C-g pressed' : (0, self.on_exit_notemode),
                 '*f12 pressed' : (0, self.on_exit_notemode),
               'escape pressed' : (0, self.on_exit_notemode),
            },
            0 : { # Normal mode
                    '* pressed' : (0, skip),
               'escape pressed' : (-1, self.on_enter_escmap),
                'space pressed' : (0, self.OnSpace),
           '*backspace pressed' : (0, self.OnBackspace),
                'enter pressed' : (0, self.OnEnter),
              'C-enter pressed' : (0, _F(self.insertLineBreak)),
            'C-S-enter pressed' : (0, _F(self.insertLineBreak)),
              'S-enter pressed' : (0, _F(self.openLine)),
              'M-enter pressed' : (0, _F(self.duplicate_command)),
               '*enter pressed' : (0, ), # -> OnShowCompHistory ??????
                 'left pressed' : (0, self.OnBackspace),
               'C-left pressed' : (0, self.OnBackspace),
                  'C-[ pressed' : (0, _F(self.goto_previous_mark_arrow)),
                'C-S-[ pressed' : (0, _F(self.goto_previous_mark_arrow, selection=1)),
                  'C-] pressed' : (0, _F(self.goto_next_mark_arrow)),
                'C-S-] pressed' : (0, _F(self.goto_next_mark_arrow, selection=1)),
                 'M-up pressed' : (0, _F(self.goto_previous_white_arrow)),
               'M-down pressed' : (0, _F(self.goto_next_white_arrow)),
                'C-S-c pressed' : (0, skip),
                  'C-v pressed' : (0, _F(self.Paste)),
                'C-S-v pressed' : (0, _F(self.Paste, rectangle=1)),
             'S-insert pressed' : (0, _F(self.Paste)),
           'C-S-insert pressed' : (0, _F(self.Paste, rectangle=1)),
                  'C-j pressed' : (0, self.eval_line),
                  'M-j pressed' : (0, self.exec_region),
                  'C-h pressed' : (0, self.call_helpTip),
                  'M-h pressed' : (0, self.call_helpTip2),
                    '. pressed' : (2, self.OnEnterDot),
                  'tab pressed' : (1, self.call_history_comp),
                  'M-p pressed' : (1, self.call_history_comp),
                  'M-n pressed' : (1, self.call_history_comp),
                  'M-. pressed' : (2, self.call_word_autocomp),
                  'M-/ pressed' : (3, self.call_apropos_autocomp),
                  'M-, pressed' : (4, self.call_text_autocomp),
                  'M-m pressed' : (5, self.call_module_autocomp),
            },
            1 : { # history auto completion S-mode
                         'quit' : (0, clear),
                         'fork' : (0, self.on_indent_line),
                    '* pressed' : (0, fork),
                   'up pressed' : (0, fork),
                 'down pressed' : (0, fork),
                  '*up pressed' : (1, self.on_completion_forward_history),
                '*down pressed' : (1, self.on_completion_backward_history),
               'S-left pressed' : (1, skip),
              'S-left released' : (1, self.call_history_comp),
              'S-right pressed' : (1, skip),
             'S-right released' : (1, self.call_history_comp),
                  'tab pressed' : (1, self.on_completion_forward_history),
                'S-tab pressed' : (1, self.on_completion_backward_history),
                  'M-p pressed' : (1, self.on_completion_forward_history),
                  'M-n pressed' : (1, self.on_completion_backward_history),
                'enter pressed' : (0, lambda v: self.goto_char(self.eolc)),
               'escape pressed' : (0, clear),
            '[a-z0-9_] pressed' : (1, skip),
           '[a-z0-9_] released' : (1, self.call_history_comp),
            'S-[a-z\\] pressed' : (1, skip),
           'S-[a-z\\] released' : (1, self.call_history_comp),
                 '*alt pressed' : (1, ),
                '*ctrl pressed' : (1, ),
               '*shift pressed' : (1, ),
             '*[LR]win pressed' : (1, ),
             '*f[0-9]* pressed' : (1, ),
            },
            2 : { # word auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (2, self.on_completion_backward),
                 'down pressed' : (2, self.on_completion_forward),
                '*left pressed' : (2, skip),
               '*right pressed' : (2, skip),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (2, skip),
          '[a-z0-9_.] released' : (2, self.call_word_autocomp),
            'S-[a-z\\] pressed' : (2, skip),
           'S-[a-z\\] released' : (2, self.call_word_autocomp),
              '*delete pressed' : (2, skip),
             '*delete released' : (2, self.call_word_autocomp),
           '*backspace pressed' : (2, self.skipback_autocomp),
          '*backspace released' : (2, self.call_word_autocomp),
        'C-S-backspace pressed' : (2, ),
                  'C-j pressed' : (2, self.eval_line),
                  'M-j pressed' : (2, self.exec_region),
                  'C-h pressed' : (2, self.call_helpTip),
                  'M-h pressed' : (2, self.call_helpTip2),
                 '*alt pressed' : (2, ),
                '*ctrl pressed' : (2, ),
               '*shift pressed' : (2, ),
             '*[LR]win pressed' : (2, ),
             '*f[0-9]* pressed' : (2, ),
            },
            3 : { # apropos auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (3, self.on_completion_backward),
                 'down pressed' : (3, self.on_completion_forward),
                '*left pressed' : (3, skip),
               '*right pressed' : (3, skip),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (3, skip),
          '[a-z0-9_.] released' : (3, self.call_apropos_autocomp),
            'S-[a-z\\] pressed' : (3, skip),
           'S-[a-z\\] released' : (3, self.call_apropos_autocomp),
              '*delete pressed' : (3, skip),
           '*backspace pressed' : (3, self.skipback_autocomp),
          '*backspace released' : (3, self.call_apropos_autocomp),
        'C-S-backspace pressed' : (3, ),
                  'C-j pressed' : (3, self.eval_line),
                  'M-j pressed' : (3, self.exec_region),
                  'C-h pressed' : (3, self.call_helpTip),
                  'M-h pressed' : (3, self.call_helpTip2),
                 '*alt pressed' : (3, ),
                '*ctrl pressed' : (3, ),
               '*shift pressed' : (3, ),
             '*[LR]win pressed' : (3, ),
             '*f[0-9]* pressed' : (3, ),
            },
            4 : { # text auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (4, self.on_completion_backward),
                 'down pressed' : (4, self.on_completion_forward),
                '*left pressed' : (4, skip),
               '*right pressed' : (4, skip),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (4, skip),
          '[a-z0-9_.] released' : (4, self.call_text_autocomp),
            'S-[a-z\\] pressed' : (4, skip),
           'S-[a-z\\] released' : (4, self.call_text_autocomp),
              '*delete pressed' : (4, skip),
           '*backspace pressed' : (4, self.skipback_autocomp),
          '*backspace released' : (4, self.call_text_autocomp),
        'C-S-backspace pressed' : (4, ),
                  'C-j pressed' : (4, self.eval_line),
                  'M-j pressed' : (4, self.exec_region),
                  'C-h pressed' : (4, self.call_helpTip),
                  'M-h pressed' : (4, self.call_helpTip2),
                 '*alt pressed' : (4, ),
                '*ctrl pressed' : (4, ),
               '*shift pressed' : (4, ),
             '*[LR]win pressed' : (4, ),
             '*f[0-9]* pressed' : (4, ),
            },
            5 : { # module auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (5, self.on_completion_backward),
                 'down pressed' : (5, self.on_completion_forward),
                '*left pressed' : (5, skip),
               '*right pressed' : (5, skip),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
          '[a-z0-9_.,] pressed' : (5, skip),
         '[a-z0-9_.,] released' : (5, self.call_module_autocomp),
            'S-[a-z\\] pressed' : (5, skip),
           'S-[a-z\\] released' : (5, self.call_module_autocomp),
           '*backspace pressed' : (5, self.skipback_autocomp),
          '*backspace released' : (5, self.call_module_autocomp),
        'C-S-backspace pressed' : (5, ),
                 '*alt pressed' : (5, ),
                '*ctrl pressed' : (5, ),
               '*shift pressed' : (5, ),
             '*[LR]win pressed' : (5, ),
             '*f[0-9]* pressed' : (5, ),
            },
        })
        
        self.wrap(0)
        self.show_folder()
        self.set_style(self.STYLE)
        
        ## delete unnecessary arrows at startup
        del self.white_arrow
        del self.red_arrow
        
        self.__text = ''
        self.__time = 0
    
    def trace_position(self):
        text, lp = self.CurLine
        self.message("{:>6d}:{} ({})".format(self.cline, lp, self.cpos), pane=-1)
    
    def OnUpdate(self, evt): #<wx._stc.StyledTextEvent>
        if evt.Updated & (stc.STC_UPDATE_SELECTION | stc.STC_UPDATE_CONTENT):
            self.trace_position()
            if self.handler.current_state == 0:
                text = self.expr_at_caret
                if text and text != self.__text:
                    name, argspec, tip = self.interp.getCallTip(text)
                    if tip:
                        tip = tip.splitlines()[0]
                    self.message(tip) # clear if no tip
                    self.__text = text
            self.handler('stc_updated', evt)
        evt.Skip()
    
    def OnCallTipClick(self, evt):
        self.parent.handler('add_help', self.__calltip)
        evt.Skip()
    
    def OnSpace(self, evt):
        """Called when space pressed"""
        if not self.CanEdit():
            return
        
        cmdl = self.cmdlc
        if re.match(r"import\s*", cmdl)\
          or re.match(r"from\s*$", cmdl)\
          or re.match(r"from\s+([\w.]+)\s+import\s*", cmdl):
            self.ReplaceSelection(' ')
            self.handler('M-m pressed', None) # call_module_autocomp
            return
        evt.Skip()
    
    def OnBackspace(self, evt):
        """Called when backspace (or *left) pressed
        Backspace-guard from Autocomp eating over a prompt whitespace
        """
        if self.cpos == self.bolc:
            ## do not skip to prevent autocomp eats prompt,
            ## so not to backspace over the latest non-continuation prompt
            return
        evt.Skip()
    
    def OnEnter(self, evt):
        """Called when enter pressed"""
        if not self.CanEdit(): # go back to the end of command line
            self.goto_char(self.eolc)
            if self.eolc < self.bolc: # check if prompt is in valid state
                self.prompt()
                evt.Skip()
            return
        if self.AutoCompActive(): # skip to auto completion
            evt.Skip()
            return
        if self.CallTipActive():
            self.CallTipCancel()
        
        ## skip to wx.py.magic if cmdline begins with !(sx), ?(info), and ??(help)
        text = self.cmdline
        if not text or text[0] in '!?':
            evt.Skip()
            return
        
        ## cast magic for `@? (Note: PY35 supports @(matmul)-operator)
        tokens = list(ut.split_words(text))
        if any(x in tokens for x in '`@?$'):
            cmd = self.magic_interpret(tokens)
            if '\n' in cmd:
                self.Execute(cmd) # for multi-line commands
            else:
                self.run(cmd, verbose=0, prompt=0) # => push(cmd)
            return
        
        self.exec_cmdline()
        ## evt.Skip() # => processLine
    
    def OnEnterDot(self, evt):
        """Called when dot(.) pressed"""
        if not self.CanEdit():
            return
        
        p = self.cpos
        st = self.get_style(p-1)
        if st in ('moji', 'word', 'rparen'):
            pass
        elif st in (0, 'space', 'sep', 'lparen'):
            self.ReplaceSelection('self') # replace [.] --> [self.]
        else:
            self.handler('quit', evt) # => quit autocomp mode
        
        self.ReplaceSelection('.') # just write down a dot.
        evt.Skip(False)            # and do not skip to default autocomp mode
    
    def openLine(self):
        p = self.cpos
        self.insertLineBreak()
        self.cpos = self.anchor = p # save_excursion
    
    def duplicate_command(self, clear=True):
        if self.CanEdit():
            return
        cmd = self.MultilineCommand
        if cmd:
            self.mark = self.cpos
            if clear:
                self.clearCommand() # => move to the prompt end
            self.write(cmd.rstrip(), -1)
    
    def on_enter_escmap(self, evt):
        self.__caret_mode = self.CaretPeriod
        self.CaretPeriod = 0
        self.message("ESC-")
    
    def on_exit_escmap(self, evt):
        self.CaretPeriod = self.__caret_mode
        self.message("ESC {}".format(evt.key))
    
    def on_enter_notemode(self, evt):
        self.noteMode = True
        self.__caret_mode = self.CaretForeground
        self.CaretForeground = 'red'
        self.message("Note mode")
    
    def on_exit_notemode(self, evt):
        self.noteMode = False
        self.CaretForeground = self.__caret_mode
        self.goto_char(self.bolc)
        self.promptPosEnd = 0
        self.prompt()
        self.message("")
    
    def goto_previous_white_arrow(self):
        ln = self.MarkerPrevious(self.cline-1, 0b010) # previous white-arrow
        p = self.PositionFromLine(ln) + len(sys.ps1)
        self.goto_char(p if ln != -1 else 0)
    
    def goto_next_white_arrow(self):
        ln = self.MarkerNext(self.cline+1, 0b010) # next white-arrow
        p = self.PositionFromLine(ln) + len(sys.ps1)
        self.goto_char(p if ln != -1 else self.eolc)
    
    def goto_previous_mark_arrow(self, selection=False):
        ln = self.MarkerPrevious(self.cline-1, 0b110) # previous white/red-arrow
        self.goto_line(ln if ln != -1 else 0, selection)
    
    def goto_next_mark_arrow(self, selection=False):
        ln = self.MarkerNext(self.cline+1, 0b110) # next white/red-arrow
        self.goto_line(ln if ln != -1 else self.LineCount, selection)
    
    ## --------------------------------
    ## Magic caster of the shell
    ## --------------------------------
    
    @classmethod
    def magic(self, cmd):
        """Called before command pushed
        (override) disable old magic: `f x --> f(x)`
        """
        if cmd:
            if cmd[0:2] == '??': cmd = 'help({})'.format(cmd[2:])
            elif cmd[0] == '?': cmd = 'info({})'.format(cmd[1:])
            elif cmd[0] == '!': cmd = 'sx({!r})'.format(cmd[1:])
        return cmd
    
    @classmethod
    def magic_interpret(self, tokens):
        """Called when [Enter] command, or eval-time for tooltip
        Interpret magic syntax
           quoteback : x`y --> y=x
            pullback : x@y --> y(x)
             partial : x@(y1,...,yn) --> partial(y1,...,yn)(x)
             apropos : x.y?p --> apropos(x,y,...,p)
        
        Note: This is called before run, execute, and original magic.
        """
        sep1 = "`@=+-/*%<>&|^~;\t\r\n#"   # [`] ops, seps (no space, no comma)
        sep2 = "`@=+-/*%<>&|^~;, \t\r\n#" # [@] ops, seps
        
        def _popiter(ls, f):
            p = f if callable(f) else re.compile(f).match
            while ls and p(ls[0]):
                yield ls.pop(0)
        
        def _eats(r, sep):
            return ''.join(_popiter(r, "[ \t]"))\
                 + ''.join(_popiter(r, lambda c: c not in sep))
        
        lhs = ''
        tokens = list(tokens)
        for i, c in enumerate(tokens):
            rest = tokens[i+1:]
            
            if c == '@' and not lhs.strip('\r\n')\
              and any(x[0] in '\r\n' for x in rest): # @dcor
                pass
            elif c == '@':
                f = "{rhs}({lhs})"
                lhs = lhs.strip() or '_'
                rhs = _eats(rest, sep2).strip()
                if rhs in ("debug", "profile"):
                    lhs = re.sub(r"([\w.]+)\((.*)\)", # func(a,b,c) @debug
                                 r"\1, \2", lhs)      # --> func,a,b,c @debug
                else:
                    rhs = re.sub(r"^\((.*)\)",        # @(y1,,,yn)
                                 r"partial(\1)", rhs) # --> partial(y1,,,yn)
                return self.magic_interpret([f.format(lhs=lhs, rhs=rhs)] + rest)
            
            if c == '`':
                f = "{rhs} = {lhs}"
                lhs = lhs.strip() or '_'
                rhs = _eats(rest, sep1).strip()
                return self.magic_interpret([f.format(lhs=lhs, rhs=rhs)] + rest)
            
            if c == '?':
                head, sep, hint = lhs.rpartition('.')
                cc, pred = re.search(r"(\?+)\s*(.*)", c + ''.join(rest)).groups()
                return ("apropos({0}, {1!r}, ignorecase={2}, alias={0!r}, "
                        "pred={3!r}, locals=locals())".format(
                        head, hint.strip(), len(cc)<2, pred or None))
            
            if c == ';':
                return lhs + c + self.magic_interpret(rest)
            
            if c == sys.ps2.strip():
                rhs = ''.join(_popiter(rest, "[ \t\r\n]")) # feed
                return lhs + c + rhs + self.magic_interpret(rest)
            
            if c.startswith('#'):
                rhs = ''.join(_popiter(rest, "[^\r\n]")) # skip comment
                return lhs + c + rhs + self.magic_interpret(rest)
            
            lhs += c # store in lhs; no more processing
        return lhs
    
    def on_deleted(self, shell):
        """Called before shell:self is killed.
        Delete target shell to prevent referencing the dead shell.
        """
        try:
            del self.target.shell # delete the facade <wx.py.shell.ShellFacade>
        except AttributeError:
            pass
    
    def on_activated(self, shell):
        """Called when shell:self is activated.
        Reset localvars and builtins assigned for the shell target.
        
        Note: the target could be referred from other shells.
        """
        ## self.target = shell.target # Don't overwrite locals here
        self.parent.handler('title_window', self.target)
        self.trace_position()
        try:
            self.target.shell = self # overwrite the facade <wx.py.shell.ShellFacade>
        except AttributeError:
            pass
        
        ## To prevent the builtins from referring dead objects,
        ## Add utility functions to builtins each time when activated.
        builtins.help = self.help
        builtins.info = self.info
        builtins.dive = self.clone
        builtins.timeit = self.timeit
        try:
            builtins.debug = self.parent.debug
            builtins.load = self.parent.load
        except AttributeError:
            pass
    
    def on_inactivated(self, shell):
        """Called when shell:self is inactivated.
        Remove target localvars and builtins assigned for the shell target.
        """
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CallTipActive():
            self.CallTipCancel()
        try:
            del builtins.help
            del builtins.info
            del builtins.dive
            del builtins.timeit
            del builtins.debug
            del builtins.load
        except AttributeError:
            pass
    
    def on_text_input(self, text):
        """Called when [Enter] text (before push).
        Mark points, reset history point, etc.
        
        Note: text is raw input:str with no magic cast
        """
        if text.rstrip():
            self.__eolc_mark = self.eolc
            self.historyIndex = -1
    
    def on_text_output(self, text):
        """Called when [Enter] text (after push).
        Set markers at the last command line.
        
        Note: text is raw output:str with no magic cast
        """
        ln = self.cmdline_region[0]
        err = re.findall(r"^\s+File \"(.*?)\", line ([0-9]+)", text, re.M)
        self.MarkerAdd(ln, 1 if not err else 2) # 1:white-arrow 2:red-arrow
        return (not err)
    
    def on_interp_error(self, e):
        self.linemark = self.cmdline_region[0] + e.lineno - 1
    
    ## --------------------------------
    ## Attributes of the shell
    ## --------------------------------
    fragmwords = set(keyword.kwlist + dir(builtins)) # to be used in text-autocomp
    
    ## shell.history is an instance variable of the Shell.
    ## If del shell.history, the history of the class variable is used
    history = []
    
    bolc = property(lambda self: self.promptPosEnd, doc="beginning of command-line")
    eolc = property(lambda self: self.TextLength, doc="end of command-line")
    
    @property
    def bol(self):
        """beginning of line (override) excluding prompt"""
        text, lp = self.CurLine
        for ps in (sys.ps1, sys.ps2, sys.ps3):
            if text.startswith(ps):
                lp -= len(ps)
                break
        return self.cpos - lp
    
    @property
    def cmdlc(self):
        """cull command-line (excluding ps1:prompt)"""
        return self.GetTextRange(self.bol, self.cpos)
    
    @property
    def cmdline(self):
        """full command-(multi-)line (excluding ps1:prompt)"""
        return self.GetTextRange(self.bolc, self.eolc)
    
    def cmdline_atoms(self):
        q = self.bolc
        while q < self.eolc:
            p, q, st = self.get_following_atom(q)
            yield self.GetTextRange(p, q)
    
    @property
    def cmdline_region(self):
        lc = self.LineFromPosition(self.bolc)
        le = self.LineCount
        return lc, le
    
    ## cf. getCommand() -> caret-line that starts with a prompt
    ## cf. getMultilineCommand() -> [BUG 4.1.1] Don't use against the current prompt
    
    @property
    def Command(self):
        """Extract a command from the editor."""
        return self.getCommand()
    
    @property
    def MultilineCommand(self):
        """Extract a multi-line command from the editor."""
        region = self.get_region(self.cline)
        if region:
            p, q = (self.PositionFromLine(x) for x in region)
            p += len(sys.ps1)
            return self.GetTextRange(p, q)
        return ''
    
    def get_region(self, line):
        """Line numbers of prompt head and tail containing the line.
        (override)"""
        lc = line
        le = lc + 1
        while lc >= 0:
            text = self.GetLine(lc)
            if not text.startswith(sys.ps2):
                break
            lc -= 1
        if not text.startswith(sys.ps1): # bad region
            return None
        while le < self.LineCount:
            text = self.GetLine(le)
            if not text.startswith(sys.ps2):
                break
            le += 1
        return lc, le
    
    ## --------------------------------
    ## Execution methods of the shell
    ## --------------------------------
    
    def push(self, command, **kwargs):
        """Send command to the interpreter for execution.
        (override) Mark points before push.
        """
        try:
            self.on_text_input(command)
        except AttributeError:
            pass
        Shell.push(self, command, **kwargs)
    
    def addHistory(self, command):
        """Add command to the command history
        (override) if the command is new (i.e., not found in the head of the list).
                   Then, write the command to History buffer.
        """
        if not command:
            return
        
        ## ?????????????????? push ???????????????????????????????????????????????????
        ## bolc : beginning of command-line
        ## eolc : end of the output-buffer
        try:
            input = self.GetTextRange(self.bolc, self.__eolc_mark)
            output = self.GetTextRange(self.__eolc_mark, self.eolc)
            
            input = self.regulate_cmd(input)
            Shell.addHistory(self, input)
            
            noerr = self.on_text_output(output)
            if noerr:
                words = re.findall(r"\b[a-zA-Z_][\w.]+", input + output)
                self.fragmwords |= set(words)
            self.parent.handler('add_history', command, noerr)
        except AttributeError:
            ## execStartupScript ????????????????????? (owner) ??????????????????
            ## shell.__init__ ??????????????????????????????
            pass
    
    def execStartupScript(self, su):
        """Execute the user's PYTHONSTARTUP script if they have one.
        (override) Add globals when executing su:startupScript
                   Fix history point
        """
        ## self.globals = self.locals
        self.promptPosEnd = self.TextLength # fix history point
        if su and os.path.isfile(su):
            self.push("print('Startup script executed:', {0!r})\n".format(su))
            self.push("with open({0!r}) as _f: exec(_f.read())\n".format(su))
            self.push("del _f\n")
            self.interp.startupScript = su
        else:
            self.push("")
            self.interp.startupScript = None
    
    def Paste(self, rectangle=False):
        """Replace selection with clipboard contents.
        (override) Remove ps1 and ps2 from the multi-line command to paste.
                   Add offset in paste-rectangle mode.
                   Don't relplace the last crlf to ps.
        """
        if self.CanPaste() and wx.TheClipboard.Open():
            data = wx.TextDataObject()
            if wx.TheClipboard.GetData(data):
                text = data.GetText()
                command = text.rstrip()
                command = self.fixLineEndings(command)
                command = self.regulate_cmd(command)
                endl = text[len(command):] # the rest whitespace
                ps = sys.ps2
                if self.cpos == self.eolc: # caret at the end of the buffer
                    endl = endl.replace('\n', os.linesep + ps)
                _text, lp = self.CurLine
                if rectangle:
                    ps += ' ' * (lp - len(ps)) # add offset
                if lp == 0:
                    command = ps + command # paste-line
                command = command.replace('\n', os.linesep + ps)
                self.ReplaceSelection(command + endl)
            wx.TheClipboard.Close()
    
    def regulate_cmd(self, text):
        """Regulate text to executable command"""
        text = self.lstripPrompt(text) # strip a leading prompt
        lf = '\n'
        return (text.replace(os.linesep + sys.ps1, lf)
                    .replace(os.linesep + sys.ps2, lf)
                    .replace(os.linesep, lf))
    
    def clear(self):
        """Delete all text (override) put new prompt"""
        self.ClearAll()
        self.promptPosStart = 0 # CanEdit:True
        self.promptPosEnd = 0
        self.prompt()
    
    def write(self, text, pos=None):
        """Display text in the shell
        (override) Append text if it is writable at the position.
        """
        if pos is not None:
            if pos < 0:
                pos += self.TextLength + 1 # Counts end-of-buffer (+1:\0)
            self.goto_char(pos)
        if self.CanEdit():
            Shell.write(self, text) # => AddText
    
    ## input = classmethod(Shell.ask)
    
    def info(self, obj):
        """Short information"""
        doc = inspect.getdoc(obj)\
                or "No information about {}".format(obj)
        self.parent.handler('add_help', doc) or print(doc)
    
    def help(self, obj):
        """Full description"""
        ## if obj is None:
        ##     self.message("Currently redirected to stdin/stdout.")
        ##     wx.CallAfter(pydoc.help)
        ##     return
        doc = pydoc.plain(pydoc.render_doc(obj))\
                or "No description about {}".format(obj)
        self.parent.handler('add_help', doc) or print(doc)
    
    def eval(self, text):
        return eval(text, self.globals, self.locals)
    
    def exec(self, text):
        exec(text, self.globals, self.locals)
        dispatcher.send(signal='Interpreter.push',
                        sender=self, command=None, more=False)
    
    def exec_cmdline(self):
        """Execute command-line directly"""
        commands = []
        cmd = ''
        lines = ''
        for atom in self.cmdline_atoms():
            lines += atom
            if atom[0] not in '\r\n':
                continue
            line = self.lstripPrompt(lines)
            lstr = line.lstrip()
            if (lstr and lstr == line # no indent
                and not lstr.startswith('#') # no comment
                and not re.match(self.py_outdent_re, lstr)): # no outdent pattern
                if cmd:
                    commands.append(cmd) # Add stacked commands to the list
                cmd = line
            else:
                cmd += lines # multi-line command
            lines = ''
        if lines.startswith(sys.ps2):
            line = self.lstripPrompt(lines)
            lstr = line.lstrip()
            if lstr and lstr == line: # ps + no indent
                commands += [cmd, line]
            else:
                commands.append(cmd + lines)
        else:
            commands.append(cmd + lines)
        if len(commands) > 1:
            suffix = sys.ps2
            for j, cmd in enumerate(commands):
                if re.match(self.py_indent_re, cmd):
                    ## multi-line code-block ends with [\r\n... ]
                    if not cmd.endswith(os.linesep):
                        cmd = cmd.rstrip('\r\n') + os.linesep
                    if not cmd.endswith(suffix):
                        cmd = cmd + suffix
                else:
                    ## single line of code ends without [\r\n... ]
                    if cmd.endswith(suffix):
                        cmd = cmd[:-len(suffix)]
                    cmd = cmd.rstrip('\r\n')
                commands[j] = cmd
        
        self.Replace(self.bolc, self.eolc, '')
        self.__time = self.clock()
        for cmd in commands:
            self.write(cmd)
            self.processLine()
    
    def Execute(self, text):
        """Replace selection with text and run commands.
        (override) Check the clock time,
                   Patch `finally` miss-indentation
        """
        command = self.regulate_cmd(text)
        commands = []
        cmd = ''
        for line in command.splitlines():
            lstr = line.lstrip()
            if (lstr and lstr == line # no indent
                and not lstr.startswith('#') # no comment
                and not re.match(self.py_outdent_re, lstr)): # no outdent pattern
                if cmd:
                    commands.append(cmd) # Add the previous command to the list
                cmd = line
            else:
                cmd += '\n' + line # Multiline command; Add to the command
        commands.append(cmd)
        
        self.Replace(self.bolc, self.eolc, '')
        self.__time = self.clock()
        for cmd in commands:
            self.write(cmd.replace('\n', os.linesep + sys.ps2))
            self.processLine()
    
    def run(self, command, prompt=True, verbose=True):
        """Execute command as if it was typed in directly.
        (override) Check the clock time.
        """
        self.__time = self.clock()
        return Shell.run(self, command, prompt, verbose)
    
    @staticmethod
    def clock():
        try:
            return time.perf_counter()
        except AttributeError:
            return time.clock()
    
    def timeit(self, *args, **kwargs):
        t = self.clock()
        print("... duration time: {:g} s\n".format(t - self.__time), file=self)
    
    def clone(self, target):
        if not hasattr(target, '__dict__'):
            raise TypeError("Unable to target primitive object: {!r}".format(target))
        
        ## Make shell:clone in the console
        shell = Nautilus(self.parent, target, name="clone",
                         style=(wx.CLIP_CHILDREN | wx.BORDER_NONE))
        self.parent.handler('add_shell', shell)
        self.handler('shell_cloned', shell)
        return shell
    
    ## --------------------------------
    ## Auto-comp actions of the shell
    ## --------------------------------
    
    def autoCallTipShow(self, command, insertcalltip=True, forceCallTip=False):
        """Display argument spec and docstring in a popup window.
        (override) Swap anchors to not scroll to the end of the line,
                   and display a long hint at the insertion position.
        """
        vpos = self.GetScrollPos(wx.VERTICAL)
        hpos = self.GetScrollPos(wx.HORIZONTAL)
        Shell.autoCallTipShow(self, command, insertcalltip, forceCallTip)
        self.cpos, self.anchor = self.anchor, self.cpos
        ## self.EnsureCaretVisible()
        self.ScrollToLine(vpos)
        self.SetXOffset(hpos)
    
    def CallTipShow(self, pos, tip, N=11):
        """Show a call tip containing a definition near position pos.
        (override) Snip the tip of max N lines if it is too long.
                   Keep the tip for calltip-click event.
        """
        self.__calltip = tip
        lines = tip.splitlines()
        if len(lines) > N:
            lines[N+1:] = ["\n...(snip) This tips are too long... "
                           "Click to show more details."
                          ]
        Shell.CallTipShow(self, pos, '\n'.join(lines))
    
    def gen_autocomp(self, offset, words, sep=' '):
        """Call AutoCompShow for the specified words"""
        if words:
            self.AutoCompSetSeparator(ord(sep))
            self.AutoCompShow(offset, sep.join(words))
    
    def eval_line(self, evt):
        """Call ToolTip of the selected word or line"""
        if self.CallTipActive():
            self.CallTipCancel()
            
        def _gen_text():
            text = self.SelectedText
            if text:
                yield text
            else:
                yield self.Command
                yield self.expr_at_caret
                yield self.MultilineCommand
        
        status = "No words"
        for text in filter(None, _gen_text()):
            tokens = ut.split_words(text)
            try:
                cmd = self.magic_interpret(tokens)
                cmd = self.regulate_cmd(cmd)
                obj = self.eval(cmd)
            except Exception as e:
                status = "- {}: {!r}".format(e, text)
            else:
                self.CallTipShow(self.cpos, pformat(obj))
                self.message(cmd)
                return
        self.message(status)
    
    def exec_region(self, evt):
        """Call ToolTip of the selected region"""
        if self.CallTipActive():
            self.CallTipCancel()
        
        filename = "<input>"
        text = self.MultilineCommand
        if text:
            tokens = ut.split_words(text)
            try:
                cmd = self.magic_interpret(tokens)
                cmd = self.regulate_cmd(cmd)
                code = compile(cmd, filename, "exec")
                self.exec(code)
            except Exception as e:
                msg = traceback.format_exc()
                err = re.findall(r"^\s+File \"(.*?)\", line ([0-9]+)", msg, re.M)
                lines = [int(l) for f,l in err if f == filename]
                if lines:
                    region = self.get_region(self.cline)
                    self.linemark = region[0] + lines[-1] - 1
                self.message("- {}".format(e))
                ## print(msg, file=sys.__stderr__)
            else:
                del self.linemark
                self.message("Evaluated {!r} successfully".format(filename))
        else:
            self.message("No region")
    
    def call_helpTip2(self, evt):
        """Show help:str for the selected topic"""
        if self.CallTipActive():
            self.CallTipCancel()
        
        text = self.SelectedText or self.Command or self.expr_at_caret
        if text:
            try:
                text = introspect.getRoot(text, terminator='(')
                obj = self.eval(text)
            except Exception as e:
                self.message("- {} : {!r}".format(e, text))
            else:
                self.help(obj)
    
    def call_helpTip(self, evt):
        """Show tooltips for the selected topic"""
        if self.CallTipActive():
            self.CallTipCancel()
        
        text = self.SelectedText or self.Command or self.expr_at_caret
        if text:
            try:
                p = self.cpos
                c = self.get_char(p-1)
                self.autoCallTipShow(text,
                    c == '(' and p == self.eol) # => CallTipShow
            except Exception as e:
                self.message("- {} : {!r}".format(e, text))
    
    def clear_autocomp(self, evt):
        """Clear Autocomp, selection, and message"""
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CanEdit():
            self.ReplaceSelection("")
        self.message("")
    
    def skipback_autocomp(self, evt):
        """Don't eat backward prompt whitespace"""
        if self.cpos == self.bolc:
            ## Do not skip to prevent autocomp eats prompt
            ## so not to backspace over the latest non-continuation prompt
            self.handler('quit', evt)
        evt.Skip()
    
    def process_autocomp(self, evt):
        """Feel like pressing {tab}"""
        if self.AutoCompActive():
            wx.UIActionSimulator().KeyDown(wx.WXK_TAB)
        else:
            evt.Skip()
    
    def on_completion_forward(self, evt):
        if self.AutoCompActive():
            self.on_completion(evt, 1)
        else:
            self.handler('quit', evt)
        evt.Skip()
    
    def on_completion_backward(self, evt):
        if self.AutoCompActive():
            self.on_completion(evt, -1)
        else:
            self.handler('quit', evt)
        evt.Skip()
    
    def on_completion_forward_history(self, evt):
        self.on_completion(evt, 1) # ???????????????????????????
    
    def on_completion_backward_history(self, evt):
        self.on_completion(evt, -1) # ??????????????????????????????
    
    @postcall
    def on_completion(self, evt, step=0):
        """Show completion with selection"""
        try:
            N = len(self.__comp_words)
            j = self.__comp_ind + step
            j = 0 if j < 0 else j if j < N else N-1
            word = self.__comp_words[j]
            n = len(self.__comp_hint)
            p = self.cpos
            self.ReplaceSelection(word[n:]) # ????????????????????????????????????(?????????????????????)
            self.cpos = p # backward selection to the point
            self.__comp_ind = j
        except IndexError:
            self.message("no completion words")
    
    def call_history_comp(self, evt):
        """Called when history-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            cmdl = self.cmdlc
            if cmdl.isspace() or self.bol != self.bolc:
                self.handler('fork', evt) # fork [tab pressed] => on_indent_line
                return
            
            hint = cmdl.strip()
            ls = [x.replace('\n', os.linesep + sys.ps2)
                    for x in self.history if x.startswith(hint)] # case-sensitive match
            words = sorted(set(ls), key=ls.index, reverse=0)     # keep order, no duplication
            
            self.__comp_ind = 0
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.anchor = self.eolc # selection to eol
            self.on_completion(evt) # show completion always
            
            ## the latest history stacks in the head of the list (time-descending)
            self.message("[history] {} candidates matched"
                         " with {!r}".format(len(words), hint))
        except Exception:
            raise
    
    def call_text_autocomp(self, evt):
        """Called when text-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            cmdl = self.cmdlc
            hint = self.get_last_hint(cmdl)
            
            ls = [x for x in self.fragmwords if x.startswith(hint)] # case-sensitive match
            words = sorted(ls, key=lambda s:s.upper())
            
            self.__comp_ind = 0 if words else -1
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.gen_autocomp(len(hint), words)
            self.message("[text] {} candidates matched"
                         " with {!r}".format(len(words), hint))
        except Exception:
            raise
    
    def call_module_autocomp(self, evt):
        """Called when module-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            cmdl = self.cmdlc
            hint = self.get_last_hint(cmdl)
            
            m = re.match(r"from\s+([\w.]+)\s+import\s+(.*)", cmdl)
            if m:
                text, hints = m.groups()
                if hints and not hints.strip().endswith(','):
                    return
                if text not in sys.modules:
                    self.message("[module]>>> loading {}...".format(text))
                try:
                    modules = dir(import_module(text))
                except ImportError as e:
                    self.message("\b failed: {}".format(e))
                    return
            else:
                m = re.match(r"(import|from)\s+(.*)", cmdl)
                if m:
                    text, hints = m.groups()
                    if not hints or hints.strip().endswith(','):
                        self.message("[module]>>> waiting for key input...")
                        return
                    if hints.endswith(' '):  # Don't show comp-list
                        return
                    tail = hints.split(',')[-1] # the last one following `,`
                    if len(tail.split()) > 1:   # includes a separator, e.g., `as`
                        return
                    modules = self.modules
                else:
                    text, sep, hint = self.get_words_hint(cmdl)
                    obj = self.eval(text)
                    if not hasattr(obj, '__dict__'):
                        self.message("[module] primitive object: {}".format(obj))
                        return
                    modules = [k for k, v in vars(obj).items() if inspect.ismodule(v)]
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in modules if p.match(x)], key=lambda s:s.upper())
            
            j = next((k for k, w in enumerate(words) if P.match(w)),
                next((k for k, w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.gen_autocomp(len(hint), words)
            self.message("[module] {} candidates matched"
                         " with {!r} in {}".format(len(words), hint, text))
        except re.error as e:
            self.message("- re:miss compilation {!r} : {!r}".format(e, hint))
        except SyntaxError as e:
            self.handler('quit', evt)
            self.message("- {} : {!r}".format(e, text))
        except Exception:
            raise
    
    def call_word_autocomp(self, evt):
        """Called when word-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            text, sep, hint = self.get_words_hint(self.cmdlc)
            obj = self.eval(text)
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in ut.wdir(obj) if p.match(x)], key=lambda s:s.upper())
            
            j = next((k for k, w in enumerate(words) if P.match(w)),
                next((k for k, w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.gen_autocomp(len(hint), words)
            self.message("[word] {} candidates matched"
                         " with {!r} in {}".format(len(words), hint, text))
        except re.error as e:
            self.message("- re:miss compilation {!r} : {!r}".format(e, hint))
        except SyntaxError as e:
            self.handler('quit', evt)
            self.message("- {} : {!r}".format(e, text))
        except Exception as e:
            self.message("- {} : {!r}".format(e, text))
    
    def call_apropos_autocomp(self, evt):
        """Called when apropos mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            text, sep, hint = self.get_words_hint(self.cmdlc)
            obj = self.eval(text)
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in ut.wdir(obj) if p.search(x)], key=lambda s:s.upper())
            
            j = next((k for k, w in enumerate(words) if P.match(w)),
                next((k for k, w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.gen_autocomp(len(hint), words)
            self.message("[apropos] {} candidates matched"
                         " with {!r} in {}".format(len(words), hint, text))
        except re.error as e:
            self.message("- re:miss compilation {!r} : {!r}".format(e, hint))
        except SyntaxError as e:
            self.handler('quit', evt)
            self.message("- {} : {!r}".format(e, text))
        except Exception as e:
            self.message("- {} : {!r}".format(e, text))
    
    @staticmethod
    def get_last_hint(cmdl):
        return re.search(r"[\w.]*$", cmdl).group(0) # or ''
    
    @staticmethod
    def get_words_hint(cmdl):
        text = next(ut.split_words(cmdl, reverse=1), '')
        return text.rpartition('.') # -> text, sep, hint


if __name__ == "__main__":
    import mwx; mwx.deb() # noqa
