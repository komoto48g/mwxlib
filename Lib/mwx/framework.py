#! python3
# -*- coding: utf-8 -*-
"""mwxlib framework

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import

__version__ = "0.47.5"
__author__ = "Kazuya O'moto <komoto@jeol.co.jp>"

from collections import OrderedDict
from functools import partial
from functools import wraps
import traceback
import datetime
import keyword
import shlex
import time
import sys
import os
import re
import wx
from wx import aui
from wx import stc
from wx import core
from wx.py.shell import Shell
from wx.py.editwindow import EditWindow
from wx.py.filling import FillingFrame
import wx.lib.eventwatcher as ew
import numpy as np
import fnmatch
import pkgutil
import pydoc
import warnings
import inspect
from inspect import (isclass, ismodule, ismethod, isbuiltin,
                     isfunction, isgenerator)
from pprint import pprint, pformat
from six.moves import builtins
## from six import PY3
from pdb import Pdb, bdb
import linecache
try:
    from importlib import reload
except ImportError:
    pass

LITERAL_TYPE = (str,) if sys.version_info >= (3,0) else (str,unicode)


def atom(v):
    return not hasattr(v, '__name__')


def isobject(v):
    ## return atom(v) and hasattr(v, '__module__')
    return re.match(r"<([\w.]+) object at \w+>", repr(v))


def instance(*types):
    ## return lambda v: isinstance(v, types)
    def _pred(v):
        return isinstance(v, types)
    _pred.__name__ = str("instance<{}>".format(','.join(p.__name__ for p in types)))
    return _pred


def subclass(*types):
    ## return lambda v: issubclass(v, types)
    def _pred(v):
        return issubclass(v, types)
    _pred.__name__ = str("subclass<{}>".format(','.join(p.__name__ for p in types)))
    return _pred


def _Not(p):
    ## return lambda v: not p(v)
    if isinstance(p, type):
        p = instance(p)
    def _pred(v):
        return not p(v)
    _pred.__name__ = str("not {}".format(p.__name__))
    return _pred


def _And(p, q):
    ## return lambda v: p(v) and q(v)
    if isinstance(p, type):
        p = instance(p)
    if isinstance(q, type):
        q = instance(q)
    def _pred(v):
        return p(v) and q(v)
    _pred.__name__ = str("{} and {}".format(p.__name__, q.__name__))
    return _pred


def _Or(p, q):
    ## return lambda v: p(v) or q(v)
    if isinstance(p, type):
        p = instance(p)
    if isinstance(q, type):
        q = instance(q)
    def _pred(v):
        return p(v) or q(v)
    _pred.__name__ = str("{} or {}".format(p.__name__, q.__name__))
    return _pred


def predicate(text, locals=None):
    tokens = [x for x in split_into_words(text.strip()) if not x.isspace()]
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'not' or c == '~':
            tokens[j:j+2] = ["_Not({})".format(tokens[j+1])]
        j += 1
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'and' or c == '&':
            tokens[j-1:j+2] = ["_And({},{})".format(tokens[j-1], tokens[j+1])]
            continue
        j += 1
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'or' or c == '|':
            tokens[j-1:j+2] = ["_Or({},{})".format(tokens[j-1], tokens[j+1])]
            continue
        j += 1
    return eval(' '.join(tokens) or 'None', None, locals)


def Dir(obj):
    """As the standard dir, but also listup fields of COM object
    
    Create COM object with [win32com.client.gencache.EnsureDispatch]
    for early-binding to get what methods and params are available.
    """
    keys = dir(obj)
    try:
        ## if hasattr(obj, '_prop_map_get_'):
        ##     keys += obj._prop_map_get_.keys()
        if hasattr(obj, '_dispobj_'):
            keys += dir(obj._dispobj_)
    finally:
        return keys


def apropos(obj, rexpr, ignorecase=True, alias=None, pred=None, locals=None):
    """Put a list of objects having expression `rexpr in `obj
    """
    name = alias or typename(obj)
    rexpr = (rexpr.replace('\\a','[a-z0-9]')  #\a: identifier chars (custom rule)
                  .replace('\\A','[A-Z0-9]')) #\A: 
    
    if isinstance(pred, LITERAL_TYPE):
        pred = predicate(pred, locals)
    
    if isinstance(pred, type):
        pred = instance(pred)
    
    if pred:
        if not callable(pred):
            raise TypeError("{!r} is not callable".format(pred))
        try:
            pred(None)
        except (TypeError, ValueError):
            pass
    
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        
        print("matching to {!r} in {} {} :{}".format(
              rexpr, name, type(obj), pred and typename(pred)))
        try:
            p = re.compile(rexpr, re.I if ignorecase else 0)
            keys = sorted(filter(p.search, Dir(obj)), key=lambda s:s.upper())
            n = 0
            for key in keys:
                try:
                    value = getattr(obj, key)
                    if pred and not pred(value):
                        continue
                    word = repr(value)
                    word = ' '.join(s.strip() for s in word.splitlines())
                    n += 1
                except (TypeError, ValueError):
                    continue
                except Exception as e:
                    word = '#<{!r}>'.format(e)
                if len(word) > 80:
                    word = word[:80] + '...' # truncate words +3 ellipsis
                print("    {}.{:<36s} {}".format(name, key, word))
            if pred:
                print("... found {} of {} words with :{}".format(n, len(keys), typename(pred)))
            else:
                print("... found {} words.".format(len(keys)))
        except re.error as e:
            print("- re:miss compilation {!r} : {!r}".format(e, rexpr))


def typename(obj, docp=False, qualp=False):
    """Typename of the obj object
    
    retval-> module:obj<doc>       when obj is callable and qualp=False
             module:class.obj<doc> when obj is callable and qualp=True
             module:class<doc>     when obj is a class or an instance of a class
             repr<obj>             otherwise
    """
    if hasattr(obj, '__name__'): # class, module, method, function, etc.
        if qualp:
            if hasattr(obj, '__qualname__'):
                name = obj.__qualname__
            elif hasattr(obj, 'im_class'): 
                name = obj.im_class.__name__ + '.' + obj.__name__
            else:
                name = obj.__name__
        else:
            name = obj.__name__
        
        if hasattr(obj, '__module__'): # module:name
            if obj.__module__ not in (None, '__main__', 'mwx.framework'):
                name = obj.__module__ + ':' + name
        
    elif hasattr(obj, '__module__'): # atom -> module.class
        name = obj.__module__ + '.' + obj.__class__.__name__
        
    else:
        ## return "{!r}<{!r}>".format(obj, pydoc.describe(obj))
        ## return repr(obj)
        return str(type(obj))
    
    if docp and callable(obj) and obj.__doc__:
        name += "<{!r}>".format(obj.__doc__.splitlines()[0]) # concat the first doc line
    return name


def get_words_hint(cmd):
    text = get_words_backward(cmd)
    return text.rpartition('.')


def get_words_backward(text, sep=None):
    """Get words (from text at left side of caret)"""
    tokens = split_tokens(text)[::-1]
    words = extract_words_from_tokens(tokens, sep, reverse=1)
    return ''.join(reversed(words))


def get_words_forward(text, sep=None):
    """Get words (from text at right side of caret)"""
    tokens = split_tokens(text)
    words = extract_words_from_tokens(tokens, sep)
    return ''.join(words)


def split_tokens(text):
    lexer = shlex.shlex(text)
    lexer.wordchars += '.'
    ## lexer.whitespace = '\r\n' # space(tab) is not a white
    lexer.whitespace = '' # nothing is white (for multiline analysis)
    ## return list(lexer)
    
    p = re.compile(r"([a-zA-Z])[\"\']") # [bfru]-string, and more?
    ls = []
    n = 0
    try:
        for token in lexer:
            m = p.match(token)
            if m:
                ls.append(m.group(1))
                return ls + split_tokens(text[n+1:])
            ls.append(token)
            n += len(token)
    except ValueError:
        pass
    return ls


def split_into_words(text):
    phrases = []
    tokens = split_tokens(text)
    while tokens:
        words = extract_words_from_tokens(tokens)
        phrases.append(''.join(words) or tokens.pop(0)) # list extracted words or a separator
    return phrases
    ## return [x for x in phrases if not x.isspace()] # nospace


def extract_words_from_tokens(tokens, sep=None, reverse=False):
    """Extract pythonic expressions from `tokens
    default `sep includes `@, binary-ops, and whitespaces, etc.
    """
    if sep is None:
        sep = "`@=+-/*%<>&|^~,:; \t\r\n!?" # OPS; SEPARATOR_CHARS; !?
    p, q = "({[", ")}]"
    if reverse:
        p,q = q,p
    stack = []
    words = []
    for j,c in enumerate(tokens):
        if c in p:
            stack.append(c)
        elif c in q:
            if not stack: # error("open-paren", c)
                break
            if c != q[p.index(stack.pop())]: # error("mismatch-paren", c)
                break
        elif not stack and c in sep: # ok
            break
        words.append(c) # stack word
    else:
        j = None
        if stack: # error("unclosed-paren", ''.join(stack))
            pass
    del tokens[:j] # 取り出したトークンは消す
    return words   # 取り出したトークンリスト (to be ''.joined to make a pyrepr)


def find_modules(force=False, verbose=True):
    """Find all modules available and write to log file.
    
    Similar to pydoc.help, it scans packages, but also the submodules.
    This creates a log file in ~/.deb and save the list.
    """
    try:
        reload(sys)
        sys.setdefaultencoding('utf-8') # <= PY2
    except AttributeError:
        pass
    
    f = os.path.expanduser("~/.deb/deb-modules-{}.log".format(sys.winver))
    if not force and os.path.exists(f):
        with open(f, 'r') as o:
            return eval(o.read()) # read and eval a list of modules
    else:
        print("Please wait a moment "
              "while Py{} gathers a list of all available modules... "
              "(This is executed once)".format(sys.winver))
        
        lm = list(sys.builtin_module_names)
        
        def _callback(path, modname, desc):
            lm.append(modname)
            if verbose:
                print('\b'*80 + "Scanning {:70s}".format(modname[:70]), end='',
                    file=sys.__stdout__)
        
        def _error(modname):
            if verbose:
                print('\b'*80 + "- failed: {}".format(modname),
                    file=sys.__stdout__)
        
        with warnings.catch_warnings():
            warnings.simplefilter('ignore') # ignore problems during import
            
            ## pydoc.ModuleScanner().run(_callback, key='', onerror=_error)
            for _importer, modname, _ispkg in pkgutil.walk_packages(onerror=_error):
                _callback(None, modname, '')
        
        lm.sort(key=str.upper)
        with open(f, 'w') as o:
            pprint(lm, stream=o) # write modules
        
        print('\b'*80 + "The results were written in {!r}.".format(f))
        return lm


## --------------------------------
## Finite State Machine
## --------------------------------
if not os.path.exists(os.path.expanduser("~/.deb")): # deb 専ディレクトリをホームに作成します
    os.mkdir(os.path.expanduser("~/.deb"))


class SSM(OrderedDict):
    """Single State Machine/Context of FSM
    """
    def __call__(self, event, *args):
        for act in self[event]:
            act(*args)
    
    def __repr__(self):
        return "<{} object at 0x{:X}>".format(typename(self), id(self))
    
    def __str__(self):
        def name(a):
            if callable(a):
                return typename(a, docp=1, qualp=0)
            return repr(a) # index
        return '\n'.join("{:>32} : {}".format(
            k, ', '.join(name(a) for a in v)) for k,v in self.items())


class FSM(dict):
    """Finite State Machine
    
    contexts : map of context
        { state : initial state
            { event : event key <str>
                transaction (next_state, *actions ...) }
        }
        state `None` is a wildcard (as executed any time)
        event is a string that can include wildcards `*?[]` (fnmatch rule)
        actions must accept the same *args of function as __call__(*args)
        
    If no action, FSM carries out only a transition.
    The transition is always done before actions.

Attributes:
    debug : verbose level
        [1] dump when state transits
        [2] + different event comes
        [3] + executed actions (excepting None-state)
        [4] + executed actions (including None-state)
        [5] ++ all events and actions (if any)
        [6] ++ all events (even if no actions)
        [8] +++ max verbose level to put all args
    default_state : referred as default state sucn as global-map
        default=None is given as an argument of the init.
        If there is only one state, that state will be the default.
    current_state : referred as the current state
   previous_state : (read-only, internal use only)
    current_event : (read-only, internal use only)
    """
    debug = 0
    default_state = None
    current_event = property(lambda self: self.__event)
    current_state = property(lambda self: self.__state)
    previous_state = property(lambda self: self.__prev_state)
    
    @current_state.setter
    def current_state(self, state):
        self.__state = state
        self.__event = '*forced*'
        self.__debcall__(self.__event)
    
    def clear(self, state):
        """Reset current and previous states"""
        self.default_state = state
        self.__state = self.__prev_state = state
        self.__event = self.__prev_event = None
    
    def __init__(self, contexts=None, default=None):
        dict.__init__(self) # update dict, however, it does not clear
        dict.clear(self)    # if and when __init__ is called, all contents are cleared
        self.clear(default) # the first clear creates object localvars
        self.update(contexts or {}) # this may do the next clear
        
        ## if there is only one state, reset that state as the default
        keys = list(self)
        if len(keys) == 1 and default is None:
            self.clear(keys[0])
    
    def __missing__(self, key):
        raise Exception("FSM:logical error - undefined state {!r}".format(key))
    
    def __repr__(self):
        return "<{} object at 0x{:X}>".format(typename(self), id(self))
    
    def __str__(self):
        return '\n'.join("[ {!r} ]\n{!s}".format(k,v) for k,v in self.items())
    
    def __call__(self, event, *args):
        self.__event = event
        
        ret = []
        if None in self:
            org = self.__state
            prg = self.__prev_state
            try:
                self.__state = None
                ret += self.call(event, *args) # `None` process
            finally:
                if self.__state is None: # restore original
                    self.__state = org
                    self.__prev_state = prg
        
        if self.__state is not None:
            ret += self.call(event, *args) # normal process
        
        ## self.__prev_state = self.__state
        self.__prev_event = event
        return ret
    
    def fork(self, *args):
        """Invoke the current event"""
        if self.__state == self.__prev_state: # possibly results in an infinite loop
            raise Exception("FSM:logic error - a fork cannot fork itself")
        return self.call(self.__event, *args)
    
    def call(self, event, *args):
        context = self[self.__state]
        
        if event in context:
            transaction = context[event]
            
            self.__prev_state = self.__state # save previous state
            self.__state = transaction[0] # the state transits here
            
            self.__debcall__(event, *args) # check after transition
            
            retvals = []
            for act in transaction[1:]:
                try:
                    ret = act(*args) # try actions after transition
                    retvals.append(ret)
                    
                except RuntimeError as e:
                    self.dump("- FSM:runtime error {!r}".format(e),
                              "   event : {}".format(event),
                              "    from : {}".format(self.__prev_state),
                              "   state : {}".format(self.__state),
                              "  action : {}".format(typename(act)))
                    traceback.print_exc()
                    
                except Exception as e:
                    self.dump("- FSM:exception {!r}".format(e),
                              "   event : {}".format(event),
                              "    from : {}".format(self.__prev_state),
                              "   state : {}".format(self.__state),
                              "  action : {}".format(typename(act)))
                    traceback.print_exc()
            return retvals
        else:
            ## matching test using fnmatch ファイル名規約によるマッチングテスト
            for pat in context:
                if fnmatch.fnmatchcase(event, pat):
                    return self.call(pat, *args) # recursive call with matched pattern
        
        self.__debcall__(event, *args) # check when no transition
        return []
    
    def __debcall__(self, pattern, *args):
        v = self.debug
        if v and self.__state is not None:
            transaction = self[self.__prev_state].get(pattern) or []
            actions = ', '.join(typename(a) for a in transaction[1:])
            if (v > 0 and self.__prev_state != self.__state
             or v > 1 and self.__prev_event != self.__event
             or v > 2 and actions
             or v > 3):
                self.log("{c} {1} --> {2} {0!r} {a}".format(
                    self.__event, self.__prev_state, self.__state,
                    a = '' if not actions else ('=> ' + actions),
                    c = '*' if self.__prev_state != self.__state else ' '))
        
        elif v > 3: # state is None
            transaction = self[None].get(pattern) or []
            actions = ', '.join(typename(a) for a in transaction[1:])
            if (v > 4 and actions
             or v > 5):
                self.log("\t& {0!r} {a}".format(
                    self.__event,
                    a = '' if not actions else ('=> ' + actions)))
        
        if v > 7: # max verbose level puts all args
            self.log(*args)
    
    @staticmethod
    def log(*args):
        print(*args, file=sys.__stdout__)
    
    @staticmethod
    def dump(*args):
        print(*args, file=sys.__stderr__, sep='\n')
        
        f = os.path.expanduser("~/.deb/deb-dump.log")
        with open(f, 'a') as o:
            print(time.strftime('!!! %Y/%m/%d %H:%M:%S'), file=o)
            print(*args, sep='\n', end='\n\n', file=o)
            print(traceback.format_exc(), file=o)
    
    @staticmethod
    def copy(context):
        """Copy the transaction:list in the context
        
        This method is used for the contexts given to :append and :update
        so that those elements (if they are lists) is not removed when unbound.
        """
        return {event:transaction[:] for event, transaction in context.items()}
    
    def validate(self, state):
        """Sort and move to end items with key which includes `*?[]`"""
        context = self[state]
        ast = []
        bra = []
        for event in list(context): #? OrderedDict mutated during iteration
            if re.search(r"\[.+\]", event):
                bra.append((event, context.pop(event))) # event key has '[]'
            elif '*' in event or '?' in event:
                ast.append((event, context.pop(event))) # event key has '*?'
        
        temp = sorted(context.items()) # normal event key
        context.clear()
        context.update(temp)
        context.update(sorted(bra, reverse=1))
        context.update(sorted(ast, reverse=1, key=lambda v:len(v[0])))
    
    def update(self, contexts):
        """Update each context or Add new contexts"""
        for k,v in contexts.items():
            if k in self:
                self[k].update(self.copy(v))
            else:
                self[k] = SSM(self.copy(v))
            self.validate(k)
    
    def append(self, contexts):
        """Append new contexts"""
        for k,v in contexts.items():
            if k in self:
                for event, transaction in v.items():
                    for act in transaction[1:]:
                        self.bind(event, act, k, transaction[0])
            else:
                self[k] = SSM(self.copy(v))
            self.validate(k)
    
    def remove(self, contexts):
        """Remove old contexts"""
        for k,v in contexts.items():
            if k in self:
                for event, transaction in v.items():
                    if self[k].get(event) is transaction: # remove the event
                        self[k].pop(event)
                        continue
                    for act in transaction[1:]:
                        self.unbind(event, act, k)
    
    def hook(self, event, action=None, state=None):
        if not action:
            return lambda f: self.hook(event, f, state)
        
        def _hook(*args, **kwargs):
            action(*args, **kwargs)
            self.unbind(event, _hook) # release hook once called,
        
        return self.bind(event, _hook)
    
    def bind(self, event, action=None, state=None, state2=None):
        """Append a transaction to the context
        equiv. self[state] += {event : [state2, action]}
        The transaction is exepcted to be a list (not a tuple).
        When action is not given, this does nothing, but returns @decor(event-binder).
        """
        if not action:
            return lambda f: self.bind(event, f, state, state2)
        
        warn = self.log
        
        if state not in self:
            warn("- FSM:warning - [{!r}] context newly created.".format(state))
            self[state] = SSM()
        
        context = self[state]
        if state2 is None:
            state2 = state
        
        if event in context:
            if state2 != context[event][0]:
                warn("- FSM:warning - transaction may conflict"
                     " (state {2!r} and the original state is not the same)"
                     " {0!r} : {1!r} --> {2!r}".format(event, state, state2))
                pass
                context[event][0] = state2 # update transition
        else:
            ## if state2 not in self:
            ##     warn("- FSM:warning - transaction may contradict"
            ##          " (state {2!r} is not found in the contexts)"
            ##          " {0!r} : {1!r} --> {2!r}".format(event, state, state2))
            ##     pass
            context[event] = [state2] # new event:transaction
        
        if action not in context[event]:
            try:
                context[event].append(action)
            except AttributeError:
                warn("- FSM:warning - appending action to context"
                     "({!r} : {!r}) must be a list, not tuple".format(state, event))
        return action
    
    def unbind(self, event, action, state=None):
        """Remove a transaction from the context
        equiv. self[state] -= {event : [*, action]}
        The transaction is exepcted to be a list (not a tuple).
        """
        warn = self.log
        
        if state not in self:
            warn("- FSM:warning - [{!r}] context does not exist.".format(state))
            return
        
        context = self[state]
        if event in context and action in context[event]:
            try:
                context[event].remove(action)
                if len(context[event]) == 1:
                    context.pop(event)
            except AttributeError:
                warn("- FSM:warning - removing action from context"
                     "({!r} : {!r}) must be a list, not tuple".format(state, event))


## --------------------------------
## Hotkey control interface
## --------------------------------

speckeys = {
    wx.WXK_ALT                  : 'alt',
    wx.WXK_BACK                 : 'backspace',
    wx.WXK_CANCEL               : 'break',
    wx.WXK_CAPITAL              : 'caps_lock',
    wx.WXK_CONTROL              : 'ctrl',
    wx.WXK_DELETE               : 'delete',
    wx.WXK_DOWN                 : 'down',
    wx.WXK_END                  : 'end',
    wx.WXK_ESCAPE               : 'escape',
    wx.WXK_F1                   : 'f1',
    wx.WXK_F2                   : 'f2',
    wx.WXK_F3                   : 'f3',
    wx.WXK_F4                   : 'f4',
    wx.WXK_F5                   : 'f5',
    wx.WXK_F6                   : 'f6',
    wx.WXK_F7                   : 'f7',
    wx.WXK_F8                   : 'f8',
    wx.WXK_F9                   : 'f9',
    wx.WXK_F10                  : 'f10',
    wx.WXK_F11                  : 'f11',
    wx.WXK_F12                  : 'f12',
    wx.WXK_F13                  : 'f13',
    wx.WXK_F14                  : 'f14',
    wx.WXK_F15                  : 'f15',
    wx.WXK_F16                  : 'f16',
    wx.WXK_F17                  : 'f17',
    wx.WXK_F18                  : 'f18',
    wx.WXK_F19                  : 'f19',
    wx.WXK_F20                  : 'f20',
    wx.WXK_F21                  : 'f21',
    wx.WXK_F22                  : 'f22',
    wx.WXK_F23                  : 'f23',
    wx.WXK_F24                  : 'f24',
    wx.WXK_HOME                 : 'home',
    wx.WXK_INSERT               : 'insert',
    wx.WXK_LEFT                 : 'left',
    wx.WXK_NONE                 : 'none',
    wx.WXK_NUMLOCK              : 'num_lock',
    wx.WXK_NUMPAD_ADD           : '+',
    wx.WXK_NUMPAD_DECIMAL       : 'dec',
    wx.WXK_NUMPAD_DELETE        : 'delete',
    wx.WXK_NUMPAD_DIVIDE        : '/',
    wx.WXK_NUMPAD_DOWN          : 'down',
    wx.WXK_NUMPAD_END           : 'end',
    wx.WXK_NUMPAD_ENTER         : 'enter',
    wx.WXK_NUMPAD_HOME          : 'home',
    wx.WXK_NUMPAD_INSERT        : 'insert',
    wx.WXK_NUMPAD_LEFT          : 'left',
    wx.WXK_NUMPAD_MULTIPLY      : '*',
    wx.WXK_NUMPAD_PAGEDOWN      : 'pagedown',
    wx.WXK_NUMPAD_PAGEUP        : 'pageup',
    wx.WXK_NUMPAD_RIGHT         : 'right',
    wx.WXK_NUMPAD_SUBTRACT      : '-',
    wx.WXK_NUMPAD_UP            : 'up',
    wx.WXK_NUMPAD0              : '0',
    wx.WXK_NUMPAD1              : '1',
    wx.WXK_NUMPAD2              : '2',
    wx.WXK_NUMPAD3              : '3',
    wx.WXK_NUMPAD4              : '4',
    wx.WXK_NUMPAD5              : '5',
    wx.WXK_NUMPAD6              : '6',
    wx.WXK_NUMPAD7              : '7',
    wx.WXK_NUMPAD8              : '8',
    wx.WXK_NUMPAD9              : '9',
    wx.WXK_PAGEDOWN             : 'pagedown',
    wx.WXK_PAGEUP               : 'pageup',
    wx.WXK_PAUSE                : 'break',
    wx.WXK_RETURN               : 'enter',
    wx.WXK_RIGHT                : 'right',
    wx.WXK_SCROLL               : 'scroll_lock',
    wx.WXK_SHIFT                : 'shift',
    wx.WXK_SNAPSHOT             : 'snapshot',
    wx.WXK_SPACE                : 'space',
    wx.WXK_TAB                  : 'tab',
    wx.WXK_UP                   : 'up',
    wx.WXK_WINDOWS_LEFT         : 'Lwin',
    wx.WXK_WINDOWS_MENU         : 'appskey',
    wx.WXK_WINDOWS_RIGHT        : 'Rwin',
    ## wx.WXK_CONTROL_A            : 'a',
    ## wx.WXK_CONTROL_B            : 'b',
    ## wx.WXK_CONTROL_C            : 'c',
    ## wx.WXK_CONTROL_D            : 'd',
    ## wx.WXK_CONTROL_E            : 'e',
    ## wx.WXK_CONTROL_F            : 'f',
    ## wx.WXK_CONTROL_G            : 'g',
    ## wx.WXK_CONTROL_H            : 'h', # 8=WXK_BACK (C-h)
    ## wx.WXK_CONTROL_I            : 'i', # 9=WXK_TAB (C-i)
    ## wx.WXK_CONTROL_J            : 'j',
    ## wx.WXK_CONTROL_K            : 'k',
    ## wx.WXK_CONTROL_L            : 'l',
    ## wx.WXK_CONTROL_M            : 'm', # 13=WXK_RETURN (C-m)
    ## wx.WXK_CONTROL_N            : 'n',
    ## wx.WXK_CONTROL_O            : 'o',
    ## wx.WXK_CONTROL_P            : 'p',
    ## wx.WXK_CONTROL_Q            : 'q',
    ## wx.WXK_CONTROL_R            : 'r',
    ## wx.WXK_CONTROL_S            : 's',
    ## wx.WXK_CONTROL_T            : 't',
    ## wx.WXK_CONTROL_U            : 'u',
    ## wx.WXK_CONTROL_V            : 'v',
    ## wx.WXK_CONTROL_W            : 'w',
    ## wx.WXK_CONTROL_X            : 'x',
    ## wx.WXK_CONTROL_Y            : 'y',
    ## wx.WXK_CONTROL_Z            : 'z',
}

def speckey_state(key):
    k = next((k for k,v in speckeys.items() if v == key), None)
    if k:
        return wx.GetKeyState(k) #cf. wx.GetMouseState


def hotkey(evt):
    """Interpret evt.KeyCode as Hotkey string and overwrite evt.key.
    The modifiers are arranged in the same order as matplotlib as
    [LR]win + ctrl + alt(meta) + shift.
    """
    key = evt.GetKeyCode()
    mod = ""
    for k,v in ((wx.WXK_WINDOWS_LEFT, 'Lwin-'),
                (wx.WXK_WINDOWS_RIGHT, 'Rwin-'),
                (wx.WXK_CONTROL, 'C-'),
                (wx.WXK_ALT,     'M-'),
                (wx.WXK_SHIFT,   'S-')):
        if key != k and wx.GetKeyState(k):
            mod += v
    
    key = speckeys.get(key) or chr(key).lower()
    evt.key = mod + key
    return evt.key


def regulate_key(key):
    return (key.replace("ctrl+",  "C-") # modifier keys abbreviation
               .replace("alt+",   "M-")
               .replace("shift+", "S-")
               .replace("win+", "win-")
               .replace("M-C-", "C-M-") # modifier key regulation C-M-S-
               .replace("S-M-", "M-S-")
               .replace("S-C-", "C-S-"))


## --------------------------------
## Interfaces of Controls
## --------------------------------

def funcall(f, doc=None, alias=None, **kwargs):
    """Decorator as curried function
    equiv. (lambda *v: f`alias<doc:str>(*v, **kwargs))
    """
    assert(isinstance(doc, (LITERAL_TYPE, type(None))))
    assert(isinstance(alias, (LITERAL_TYPE, type(None))))
    
    @wraps(f)
    def _Act(*v):
        return f(*v, **kwargs) # ufunc with one event args
    action = _Act
    
    ## event 引数などが省略できるかどうかチェックし，
    ## 省略できる場合 (kwargs で必要な引数が与えられる場合) その関数を返す
    ## 
    ## Check if the event argument etc. can be omitted,
    ## If it can be (if required arguments are given by kwargs) return the function.
    ## 
    def explicit_args(args, defaults):
        ## k = len(args) - n - len(kwargs) # NG
        ## defaults と kwargs がかぶることがある．次のようにして引数を数える
        n = len(defaults or ())
        xargs = args[:-n] if n else args # explicit, non-default args that must be given
        k = len(xargs)                   # if k > 0: kwargs must give the rest (xargs)
        for kw in kwargs:
            if kw not in args:
                raise TypeError("{} got an unexpected keyword {!r}".format(f, kw))
            if kw in xargs:
                k -= 1
        return k
    
    if not inspect.isbuiltin(f):
        try:
            args, _varargs, _keywords, defaults,\
              _kwonlyargs, _kwonlydefaults, _annotations = inspect.getfullargspec(f) # PY3
        except AttributeError:
            args, _varargs, _keywords, defaults = inspect.getargspec(f) # PY2
        
        k = explicit_args(args, defaults)
        if k == 0 or inspect.ismethod(f) and k == 1: # 暗黙の引数 'self' は除く
            @wraps(f)
            def _Act2(*v):
                return f(**kwargs) # function with no explicit args
            action = _Act2
    else:
        ## Builtin functions don't have an argspec that we can get.
        ## Try alalyzing the doc:str to get argspec info.
        try:
            m = re.search(r"(\w+)\((.*)\)", inspect.getdoc(f))
            name, argspec = m.groups()
            args = [x for x in argspec.strip().split(',') if x]
            defaults = re.findall(r"\w+\s*=(\w+)", argspec)
            k = explicit_args(args, defaults)
            if k == 0:
                @wraps(f)
                def _Act3(*v):
                    return f(**kwargs) # function with no explicit args
                action = _Act3
        except TypeError:
            raise
        except Exception:
            pass
    
    action.__name__ = str(alias or f.__name__)
    action.__doc__ = doc or f.__doc__
    return action


def postcall(f):
    """A decorator of wx.CallAfter
    Post event message to call `f in app.
    Wx posts the message that forces calling `f to take place in the main thread.
    """
    @wraps(f)
    def _f(*args, **kwargs):
        wx.CallAfter(f, *args, **kwargs)
    return _f


def skip(v):
    v.Skip()


class CtrlInterface(object):
    """Mouse/Key event interface class
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self):
        self.__key = ''
        self.__handler = FSM({None:{}})
        
        ## self.Bind(wx.EVT_KEY_DOWN, self.on_hotkey_press)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_hotkey_press)
        self.Bind(wx.EVT_KEY_UP, self.on_hotkey_release)
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mousewheel)
        
        self.Bind(wx.EVT_LEFT_UP, lambda v: self.mouse_handler('Lbutton released', v))
        self.Bind(wx.EVT_RIGHT_UP, lambda v: self.mouse_handler('Rbutton released', v))
        self.Bind(wx.EVT_MIDDLE_UP, lambda v: self.mouse_handler('Mbutton released', v))
        self.Bind(wx.EVT_LEFT_DOWN, lambda v: self.mouse_handler('Lbutton pressed', v))
        self.Bind(wx.EVT_RIGHT_DOWN, lambda v: self.mouse_handler('Rbutton pressed', v))
        self.Bind(wx.EVT_MIDDLE_DOWN, lambda v: self.mouse_handler('Mbutton pressed', v))
        self.Bind(wx.EVT_LEFT_DCLICK, lambda v: self.mouse_handler('Lbutton dclick', v))
        self.Bind(wx.EVT_RIGHT_DCLICK, lambda v: self.mouse_handler('Rbutton dclick', v))
        self.Bind(wx.EVT_MIDDLE_DCLICK, lambda v: self.mouse_handler('Mbutton dclick', v))
        
        self.Bind(wx.EVT_MOUSE_AUX1_UP, lambda v: self.mouse_handler('Xbutton1 released', v))
        self.Bind(wx.EVT_MOUSE_AUX2_UP, lambda v: self.mouse_handler('Xbutton2 released', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DOWN, lambda v: self.mouse_handler('Xbutton1 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DOWN, lambda v: self.mouse_handler('Xbutton2 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DCLICK, lambda v: self.mouse_handler('Xbutton1 dclick', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DCLICK, lambda v: self.mouse_handler('Xbutton2 dclick', v))
        
        ## self.Bind(wx.EVT_MOTION, lambda v: self.window_handler('motion', v))
        self.Bind(wx.EVT_SET_FOCUS, lambda v: self.window_handler('focus_set', v))
        self.Bind(wx.EVT_KILL_FOCUS, lambda v: self.window_handler('focus_kill', v))
        self.Bind(wx.EVT_ENTER_WINDOW, lambda v: self.window_handler('window_enter', v))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda v: self.window_handler('window_leave', v))
    
    def on_hotkey_press(self, evt): #<wx._core.KeyEvent>
        """Called when key down"""
        if evt.EventObject is not self:
            evt.Skip()
            return
        key = hotkey(evt)
        self.__key = regulate_key(key + '+')
        self.handler('{} pressed'.format(key), evt) or evt.Skip()
    
    def on_hotkey_release(self, evt): #<wx._core.KeyEvent>
        """Called when key up"""
        key = hotkey(evt)
        self.__key = ''
        self.handler('{} released'.format(key), evt) or evt.Skip()
    
    def on_mousewheel(self, evt): #<wx._core.MouseEvent>
        """Called when wheel event
        Trigger event: 'key+wheel[up|down|right|left] pressed'
        """
        if evt.GetWheelAxis():
            p = 'right' if evt.WheelRotation > 0 else 'left'
        else:
            p = 'up' if evt.WheelRotation > 0 else 'down'
        evt.key = self.__key + "wheel{}".format(p)
        self.handler('{} pressed'.format(evt.key), evt) or evt.Skip()
    
    def mouse_handler(self, event, evt): #<wx._core.MouseEvent>
        """Called when mouse event
        Trigger event: 'key+[LMRX]button pressed/released/dclick'
        """
        event = self.__key + event # 'C-M-S-K+[LMRX]button pressed/released/dclick'
        key, sep, st = event.rpartition(' ') # removes st:'pressed/released/dclick'
        evt.key = key or st
        self.handler(event, evt) or evt.Skip()
        try:
            self.SetFocusIgnoringChildren() # let the panel accept keys
        except AttributeError:
            pass
    
    def window_handler(self, event, evt): #<wx._core.FocusEvent> #<wx._core.MouseEvent>
        self.handler(event, evt) or evt.Skip()


class KeyCtrlInterfaceMixin(object):
    """Keymap interface mixin
    
    This interface class defines extended keymaps for inherited class handler.
    The class that mixes this in must have,
      - handler <FSM>
      - message <statusbar>
    
    keymap : event key name that excluds 'pressed'
        global-map : 0 (default)
         ctl-x-map : 'C-x'
          spec-map : 'C-c'
           esc-map : 'escape'
    """
    message = print
    
    def make_keymap(self, keymap, state=0, default=0):
        """Make a basis of extension map in the handler.
        """
        def _Pass(v):
            self.message("{} {}".format(keymap, v.key))
        _Pass.__name__ = str('pass')
        
        keyevent = keymap +' pressed'
        
        self.handler.update({ #<KeyCtrlInterfaceMixin handler>
            state : {
                       keyevent : [ keymap, self.prefix_command_hook, skip ],
            },
            keymap : {
                         'quit' : [ default, ],
                    '* pressed' : [ default, _Pass ],
                 '*alt pressed' : [ keymap, _Pass ],
                '*ctrl pressed' : [ keymap, _Pass ],
               '*shift pressed' : [ keymap, _Pass ],
             '*[LR]win pressed' : [ keymap, _Pass ],
            },
        })
    
    def prefix_command_hook(self, evt):
        win = wx.Window.FindFocus()
        if isinstance(win, wx.TextEntry) and win.StringSelection\
        or isinstance(win, stc.StyledTextCtrl) and win.SelectedText:
          # or any other of pre-selection-p?
            self.handler('quit', evt)
            return
        self.message(evt.key + '-')
    
    def define_key(self, keymap, action=None, doc=None, alias=None, **kwargs):
        """Define [map key] action at default state
        If no action, invalidates the key and returns @decor(key-binder).
        key must be in C-M-S order (ctrl + alt(meta) + shift).
        """
        state = self.handler.default_state
        map, sep, key = regulate_key(keymap).rpartition(' ')
        map = map.strip()
        if not map:
            map = state
        elif map == '*':
            map = None
        elif map not in self.handler: # make key map automatically
            self.make_keymap(map)
        
        self.handler[map][key+' pressed'] = transaction = [state] # overwrite transaction
        self.handler.validate(map)
        if action:
            transaction.append(funcall(action, doc, alias, **kwargs))
            return action
        return lambda f: self.define_key(keymap, f, doc, alias, **kwargs)


## --------------------------------
## wx Framework and Designer
## --------------------------------

def ID_(id):
    ## Free ID - どこで使っているか検索できるように
    ## do not use [ID_LOWEST(4999):ID_HIGHEST(5999)]
    id += wx.ID_HIGHEST
    assert(not wx.ID_LOWEST <= id <= wx.ID_HIGHEST)
    return id


## def pack(self, *args, orient=wx.HORIZONTAL, style=None, label=None):
def pack(self, *args, **kwargs):
    """Do layout

Usage:
    self.SetSizer(
        pack(self,
            (label, 0, wx.ALIGN_CENTER|wx.LEFT, 4),
            ( ctrl, 1, wx.ALIGN_CENTER|wx.LEFT, 4),
        )
    )
    *args : wx objects `obj (with some packing directives)
          - (obj, 1) -> sized with ratio 1 (orient と同方向)
                        他に 0 以外を指定しているオブジェクトとエリアを分け合う
          - (obj, 1, wx.EXPAND) -> expanded with ratio 1 (orient と垂直方向)
          - (obj, 0, wx.ALIGN_CENTER|wx.LEFT, 4) -> center with 4 pixel at wx.LEFT
          - ((-1,-1), 1, wx.EXPAND) -> stretched space
          - (-1,-1) -> padding space
          - None -> phantom
 **kwargs : 
   orient : HORIZONTAL or VERTICAL
    style : (proportion, flag, border) :default (0, wx.EXPAND|wx.ALL, 0)
            flag-expansion -> EXPAND, SHAPED
            flag-border -> TOP, BOTTOM, LEFT, RIGHT, ALL
            flag-align -> ALIGN_CENTER, ALIGN_LEFT, ALIGN_TOP, ALIGN_RIGHT, ALIGN_BOTTOM,
                          ALIGN_CENTER_VERTICAL, ALIGN_CENTER_HORIZONTAL
    label : label of StaticBox
    """
    orient = kwargs.get("orient") or wx.HORIZONTAL
    style = kwargs.get("style") or (0, wx.EXPAND|wx.ALL, 0)
    label = kwargs.get("label")
    
    if label is not None:
        box = wx.StaticBox(self, -1, label)
        sizer = wx.StaticBoxSizer(box, orient)
    else:
        sizer = wx.BoxSizer(orient)
    
    def flatten(a):
        return (x for y in a for x in (flatten(y) if isinstance(y, list) else (y,)))
    
    for item in flatten(args):
        if not item:
            if item is None:
                item = (0,0), 0,0,0, # dummy spacing with null style
            else:
                item = (0,0) # padding with specified style
        try:
            sizer.Add(item, *style) # using style
        except TypeError:
            sizer.Add(*item) # using item-specific style
    return sizer


class TreeList(object):
    def __init__(self, ls=None):
        self.__items = ls or []
    
    def __getattr__(self, attr):
        return getattr(self.__items, attr)
    
    def __contains__(self, k):
        return self.getf(self.__items, k)
    
    def __iter__(self):
        return self.__items.__iter__()
    
    def __getitem__(self, k):
        if isinstance(k, LITERAL_TYPE):
            return self.getf(self.__items, k)
        return self.__items.__getitem__(k)
    
    def __setitem__(self, k, v):
        if isinstance(k, LITERAL_TYPE):
            return self.setf(self.__items, k, v)
        return self.__items.__setitem__(k, v)
    
    def __delitem__(self, k):
        if isinstance(k, LITERAL_TYPE):
            return self.delf(self.__items, k)
        return self.__items.__delitem__(k)
    
    def __str__(self):
        return pformat(self.__items)
    
    def items(self, root=None):
        """Generates all branches [key, value(s)]"""
        for branch in root or self:
            if not branch:
                continue
            key, data = branch[0], branch[-1]
            if not isinstance(data, (list, tuple)):
                yield branch
            else:
                for v in self.items(data):
                    yield v
    
    @classmethod
    def getf(self, ls, key):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self.getf(ls, a)
            if la is not None:
                return self.getf(la, b)
            return # None item
        return next((x[-1] for x in ls if x and x[0] == key), None)
    
    @classmethod
    def setf(self, ls, key, value):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self.getf(ls, a)
            if la is not None:
                return self.setf(la, b, value)
            p, key = key.rsplit('/', 1)
            return self.setf(ls, p, [[key, value]]) # >>> ls[p].append([key, value])
        try:
            li = next((x for x in ls if x and x[0] == key), None)
            if li is not None:
                if isinstance(value, list):
                    li[-1][:] = value # assign value:list to items:list
                else:
                    li[-1] = value # assign value to item (li must be a list)
            else:
                ls.append([key, value]) # append to items:list
        except (TypeError, AttributeError) as e:
            print("- TreeList:warning {!r}: key={!r}".format(e, key))
    
    @classmethod
    def delf(self, ls, key):
        if '/' in key:
            p, key = key.rsplit('/', 1)
            ls = self.getf(ls, p)
        ls.remove(next(x for x in ls if x and x[0] == key))


class Menu(wx.Menu):
    """Construct menu
    
    item: (id, text, hint, style, icon,  ... Menu.Append arguments
             action, updater, highlight) ... Menu Event handlers
    where,
      style -> menu style (ITEM_NORMAL, ITEM_CHECK, ITEM_RADIO)
       icon -> menu icon (bitmap)
     action -> EVT_MENU handler
    updater -> EVT_UPDATE_UI handler
  highlight -> EVT_MENU_HIGHLIGHT handler
    """
    def __init__(self, owner, values):
        wx.Menu.__init__(self)
        self.owner = owner
        
        for item in values:
            if not item:
                self.AppendSeparator()
                continue
            id = item[0]
            handlers = [x for x in item if callable(x)]
            icons =  [x for x in item if isinstance(x, wx.Bitmap)]
            argv = [x for x in item if x not in handlers and x not in icons]
            if isinstance(id, int):
                menu_item = wx.MenuItem(self, *argv)
                if icons:
                    menu_item.SetBitmaps(*icons)
                self.Append(menu_item)
                try:
                    self.owner.Bind(wx.EVT_MENU, handlers[0], id=id)
                    self.owner.Bind(wx.EVT_UPDATE_UI, handlers[1], id=id)
                    self.owner.Bind(wx.EVT_MENU_HIGHLIGHT, handlers[2], id=id)
                except IndexError:
                    pass
            else:
                subitems = argv.pop()
                submenu = Menu(owner, subitems)
                submenu_item = wx.MenuItem(self, wx.ID_ANY, *argv)
                submenu_item.SetSubMenu(submenu)
                if icons:
                    submenu_item.SetBitmaps(*icons)
                self.Append(submenu_item)
                self.Enable(submenu_item.Id, len(subitems)) # Disable an empty menu
                submenu.Id = submenu_item.Id # <- ID_ANY
    
    @staticmethod
    def Popup(parent, menu, *args, **kwargs):
        menu = Menu(parent, menu)
        parent.PopupMenu(menu, *args, **kwargs)
        menu.Destroy()


class MenuBar(wx.MenuBar, TreeList):
    """Construct menubar as is ordered menu:list
    リストの順番どおりに GUI 上にマップしたメニューバーを構築する
    
    root:TreeList is a nested list (as directory structrue)
    ├ [key, [item,
    │        item,...]],
    ：
    ├ [key, [item,
    │        item,
    │        submenu => [key, [item,
    ：        ...               item,...]],
    """
    def __init__(self, *args, **kwargs):
        wx.MenuBar.__init__(self, *args, **kwargs)
        TreeList.__init__(self)
    
    def getmenu(self, root, key):
        key = key.replace('\\','/')
        if '/' in key:
            a, b = key.split('/', 1)
            branch = self.getmenu(root, a)
            return self.getmenu(branch, b)
        if root is None:
            return next((menu for menu,label in self.Menus if menu.Title == key), None)
        ## return next((item.SubMenu for item in root.MenuItems if item.Text == key), None)
        return next((item.SubMenu for item in root.MenuItems if item.ItemLabel == key), None)
    
    def update(self, key):
        """Call when the menulist is changed,
        Updates items of the menu that has specified `key: root/branch
        """
        if self.Parent:
            menu = self.getmenu(None, key)
            if not menu:     # 新規のメニューアイテムを挿入する
                self.reset() # リセットして終了
                return
            
            for item in menu.MenuItems: # remove and delete all items
                menu.Delete(item)
            
            menu2 = Menu(self.Parent, self[key]) # new menu2 to swap menu
            for item in menu2.MenuItems:
                menu.Append(menu2.Remove(item)) # 重複しないようにいったん切り離して追加する
            
            if hasattr(menu, 'Id'):
                self.Enable(menu.Id, menu.MenuItemCount > 0) # 空のサブメニューは無効にする
    
    def reset(self):
        """Call when the menulist is changed,
        Recreates menubar if the Parent were attached by SetMenuBar
        """
        if self.Parent:
            for j in range(self.GetMenuCount()): # remove and del all top-level menu
                menu = self.Remove(0)
                menu.Destroy()
            
            for j, (key, values) in enumerate(self):
                menu = Menu(self.Parent, values) # 空のメインメニューでも表示に追加する
                self.Append(menu, key)
                if not values:
                    self.EnableTop(j, False) # 空のメインメニューは無効にする


class StatusBar(wx.StatusBar):
    """Construct statusbar with read/write
    
   field : list of field widths
    pane : index of status text field
    """
    lock = None
    
    def __init__(self, *args, **kwargs):
        wx.StatusBar.__init__(self, *args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        text = ' '.join(str(v) for v in args)
        if not self.lock:
            return self.write(text, **kwargs)
        return text
    
    def resize(self, field):
        self.SetFieldsCount(len(field))
        self.SetStatusWidths(list(field)) # oldver requires list type
    
    def write(self, text, pane=0):
        if text and text[0] == '\b':
            text = self.read(pane) + text[1:]
        self.SetStatusText(text, pane % self.GetFieldsCount())
        return text
    
    def read(self, pane=0):
        return self.GetStatusText(pane % self.GetFieldsCount())


class Frame(wx.Frame, KeyCtrlInterfaceMixin):
    """Frame base class
    
    menubar : MenuBar
  statusbar : StatusBar
  inspector : Inspector frame of the shell
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        
        self.inspector = ShellFrame(None, target=self)
        
        ## statusbar/menubar などのカスタマイズを行う
        ## レイアウト系コマンドは statusbar/menubar の作成後
        
        self.menubar = MenuBar()
        self.menubar["File"] = [
            (ID_(1), "&Inspector\tF12", "Shell for object inspection", wx.ITEM_CHECK,
                lambda v: (self.inspector.Show(),
                           self.inspector.shell.SetFocus()),
                lambda v: v.Check(self.inspector.IsShown())),
            (),
            (wx.ID_EXIT, "E&xit\tCtrl-w", "Exit the program",
                lambda v: self.Close()),
                
            (wx.ID_ABOUT, "&About\tF1", "About this software",
                lambda v: self.About()),
        ]
        self.SetMenuBar(self.menubar)
        self.menubar.reset()
        
        ## ステータスバーを作成し，起動されたタイマーのカウントを出力する
        self.statusbar = StatusBar(self)
        self.statusbar.resize((-1,78))
        self.SetStatusBar(self.statusbar)
        
        ## ステータスバーに時刻表示 (/msec)
        ## self.timer = wx.PyTimer(
        ##     lambda: self.statusbar.write(time.strftime('%m/%d %H:%M'), pane=-1))
        self.timer = wx.Timer(self)
        self.timer.Start(1000)
        
        @partial(self.Bind, wx.EVT_TIMER)
        def on_timer(evt):
            self.statusbar.write(time.strftime('%m/%d %H:%M'), pane=-1)
        
        ## AcceleratorTable mimic
        @partial(self.Bind, wx.EVT_CHAR_HOOK)
        def hook_char(evt):
            """Called when key down"""
            if isinstance(evt.EventObject, wx.TextEntry): # prior to handler
                evt.Skip()
            else:
                self.handler('{} pressed'.format(hotkey(evt)), evt) or evt.Skip()
        
        def close(v):
            """Close the window"""
            self.Close()
        
        self.__handler = FSM({ #<Frame handler>
                0 : {
                    '* pressed' : (0, skip),
                  'M-q pressed' : (0, close),
                },
            },
            default = 0
        )
        self.make_keymap('C-x')
    
    def About(self):
        wx.MessageBox(__import__('__main__').__doc__ or 'no information',
                        caption="About this software")
    
    def Destroy(self):
        try:
            self.timer.Stop()
            ## del self.timer
            self.inspector.Destroy() # inspector is not my child
        finally:
            return wx.Frame.Destroy(self)


class MiniFrame(wx.MiniFrame, KeyCtrlInterfaceMixin):
    """MiniFrame base class
    
    menubar : MenuBar (not created by default)
  statusbar : StatusBar (not shown by default)
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self, *args, **kwargs):
        wx.MiniFrame.__init__(self, *args, **kwargs)
        
        ## To disable, self.SetMenuBar(None)
        self.menubar = MenuBar()
        self.SetMenuBar(self.menubar)
        
        self.statusbar = StatusBar(self)
        self.statusbar.Show(0)
        self.SetStatusBar(self.statusbar)
        
        ## To default close,
        ## >>> self.Unbind(wx.EVT_CLOSE)
        
        self.Bind(wx.EVT_CLOSE, lambda v: self.Show(0)) # hide only
        
        ## AcceleratorTable mimic
        @partial(self.Bind, wx.EVT_CHAR_HOOK)
        def hook_char(evt):
            """Called when key down"""
            if isinstance(evt.EventObject, wx.TextEntry): # prior to handler
                evt.Skip()
            else:
                self.handler('{} pressed'.format(hotkey(evt)), evt) or evt.Skip()
        
        def close(v):
            """Close the window"""
            self.Close()
        
        self.__handler = FSM({ #<MiniFrame handler>
                0 : {
                    '* pressed' : (0, skip),
                  'M-q pressed' : (0, close),
                },
            },
            default = 0
        )
        self.make_keymap('C-x')
    
    def Destroy(self):
        return wx.MiniFrame.Destroy(self)


class ShellFrame(MiniFrame):
    """MiniFrame of shell for inspection, debug, and break `target
-------------------------------------------------------------------
     target : Inspection target `self, any wx.Object, otherwise __main__
      shell : Nautilus Inspector shell based on <wx.py.shell.Shell>
      ghost : Notebook <Editor> as an tooltip ghost in the shell
    scratch : temporary buffer for scratch text
       Help : temporary buffer for help
        Log : logging buffer
    History : shell history (read only)

Prefix:
        C-x : extension map for the frame
        C-c : specific map for the editors and the shell

Global bindings:
        C-f : Find text
        M-f : Filter text
    """
    def __init__(self, parent, target=None, title=None, size=(1000,500),
                 style=wx.DEFAULT_FRAME_STYLE, **kwargs):
        MiniFrame.__init__(self, parent, size=size, style=style)
        
        if target is None:
            target = __import__('__main__')
        
        self.Title = title or "Nautilus - {!r}".format(target)
        
        self.statusbar.resize((-1,120))
        self.statusbar.Show(1)
        
        self.scratch = Editor(self)
        self.Help = Editor(self)
        self.Log = Editor(self)
        self.History = Editor(self)
        
        self.shell = Nautilus(self, target, **kwargs)
        
        ## self.Log.ViewEOL = True
        self.Log.ViewWhiteSpace = True
        
        self.ghost = aui.AuiNotebook(self, size=(600,400),
            style = (aui.AUI_NB_DEFAULT_STYLE|aui.AUI_NB_BOTTOM)
                  &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB|aui.AUI_NB_MIDDLE_CLICK_CLOSE)
        )
        self.ghost.AddPage(self.scratch, "*scratch*")
        self.ghost.AddPage(self.Help,    "*Help*")
        self.ghost.AddPage(self.Log,     "Log")
        self.ghost.AddPage(self.History, "History")
        
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)
        self._mgr.AddPane(self.shell, aui.AuiPaneInfo().Name("shell").CenterPane())
        self._mgr.AddPane(self.ghost, aui.AuiPaneInfo().Name("ghost").Right().Show(0)
            .Caption("Ghost in the Shell").CaptionVisible(1).Gripper(0))
        self._mgr.Update()
        
        self.findDlg = None
        self.findData = wx.FindReplaceData(wx.FR_DOWN|wx.FR_MATCHCASE)
        
        self.Bind(wx.EVT_FIND, self.OnFindNext)
        self.Bind(wx.EVT_FIND_NEXT, self.OnFindNext)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnFindClose)
        
        _F = funcall
        
        self.handler.update({ #<ShellFrame handler>
            0 : {
                   'f1 pressed' : (0, self.About),
                  'M-f pressed' : (0, self.OnFilterText),
                  'C-f pressed' : (0, self.OnFindText),
                   'f3 pressed' : (0, self.OnFindNext),
                 'S-f3 pressed' : (0, self.OnFindPrev),
                  'f11 pressed' : (0, _F(self.PopupWindow, show=None, doc="Toggle the ghost")),
                'S-f11 pressed' : (0, _F(self.PopupWindow, show=True, doc="Show the ghost")),
                  'f12 pressed' : (0, _F(self.Close, alias="close", doc="Close the window")),
                'S-f12 pressed' : (0, _F(self.shell.clear)),
                'C-f12 pressed' : (0, _F(self.shell.clone)),
            },
        })
        
        @self.define_key('C-x j', win=self.scratch, doc="Show scratch window")
        @self.define_key('C-x l', win=self.Log, doc="Show Log window")
        @self.define_key('C-x h', win=self.Help, doc="Show Help window")
        @self.define_key('C-x S-h', win=self.History, doc="Show History")
        def popup(v, win, show=True):
            self.PopupWindow(win, show)
        
        @self.define_key('S-f11', loop=True)
        @self.define_key('Xbutton1', p=-1)
        @self.define_key('Xbutton2', p=+1)
        @self.define_key('C-x p', p=-1)
        @self.define_key('C-x n', p=1)
        def other_editor(v, p=1, loop=False):
            "Focus moves to other editor"
            j = self.ghost.Selection + p
            if loop:
                j %= self.ghost.PageCount
            self.ghost.SetSelection(j)
        
        @self.define_key('C-x left', p=-1)
        @self.define_key('C-x right', p=1)
        def other_window(v, p=1):
            "Focus moves to other window"
            pages = [w for w in self.all_pages if w.IsShownOnScreen()]
            j = (pages.index(self.current_editor) + p) % len(pages)
            pages[j].SetFocus()
        
        @self.define_key('C-S-d', clear=0)
        @self.define_key('C-d', clear=1)
        def duplicate(v, clear):
            """Duplicate an expression at the caret-line"""
            win = self.current_editor
            text = win.SelectedText or win.expr_at_caret
            if text:
                if clear:
                    self.shell.clearCommand()
                self.shell.write(text, -1)
            self.shell.SetFocus()
        
        f = os.path.expanduser("~/.deb/deb-logging.log")
        if os.path.exists(f):
            with self.fopen(f) as i:
                self.Log.Value = i.read()
    
    def fopen(self, f, *args):
        try:
            return open(f, *args, newline='') # PY3
        except TypeError:
            return open(f, *args) # PY2
    
    def Destroy(self):
        try:
            f = os.path.expanduser("~/.deb/deb-logging.log")
            with self.fopen(f, 'w') as o:
                o.write(self.Log.Value)
            
            f = os.path.expanduser("~/.deb/deb-history.log")
            with self.fopen(f, 'w') as o:
                o.write("#! Last updated: <{}>\r\n".format(datetime.datetime.now()))
                o.write(self.History.Value)
        finally:
            self._mgr.UnInit()
            return MiniFrame.Destroy(self)
    
    def About(self, evt=None):
        self.Help.SetValue('\n\n'.join((
            "#<module 'mwx' from {!r}>".format(__file__),
            "Author: {!r}".format(__author__),
            "Version: {!s}".format(__version__),
            ## __doc__,
            self.__doc__,
            self.shell.__doc__,
            
            "================================\n" # Thanks to wx.py.shell
            "#{!r}".format(wx.py.shell),
            "Author: {!r}".format(wx.py.version.__author__),
            "Version: {!s}".format(wx.py.version.VERSION),
            wx.py.__doc__,
            wx.py.shell.__doc__,
            "*original{}".format(wx.py.shell.HELP_TEXT.lower()),
            
            "================================\n" # Thanks are also due to phoenix
            "#{!r}".format(wx),
            "To show the credit, press C-M-Mbutton.",
            ))
        )
        self.PopupWindow(self.Help)
    
    def PopupWindow(self, win=None, show=True):
        """Popup ghost window
        win : the editor window in the gohst
       show : True, False, otherwise None:toggle
        """
        if show is None:
            show = not self.ghost.IsShown()
            self.ghost.Show(show) # when floating ghost, has the Shown flag no effect?
        self._mgr.GetPane(self.ghost).Show(show)
        self._mgr.Update()
        if win:
            j = self.ghost.GetPageIndex(win) # win=None -> -1
            self.ghost.SetSelection(j)
            self.shell.SetFocus()
    
    ## --------------------------------
    ## Find text dialog
    ## --------------------------------
    
    @property
    def all_pages(self):
        return [self.shell] + [self.ghost.GetPage(i)
                                for i in range(self.ghost.PageCount)]
    
    @property
    def current_editor(self):
        win = wx.Window.FindFocus()
        if win in self.all_pages:
            return win
        if win.Parent:
            if self.ghost in win.Parent.Children: # floating ghost ?
                return self.ghost.CurrentPage # select the Editor window
        return self.shell # otherwise, select the default editor
    
    def OnFilterText(self, evt):
        win = self.current_editor
        text = win.topic_at_caret
        if not text:
            ## win.apply_filter(0, 0)
            for i in range(2):
                win.SetIndicatorCurrent(i)
                win.IndicatorClearRange(0, win.TextLength)
            return
        word = text.encode() # for multi-byte string
        raw = win.TextRaw
        lw = len(word)
        pos = -1
        n = 0
        while 1:
            pos = raw.find(word, pos+1)
            if pos < 0:
                break
            ## win.apply_filter(pos, lw)
            for i in range(2):
                win.SetIndicatorCurrent(i)
                win.IndicatorFillRange(pos, lw)
            n += 1
        self.statusbar("{}: {} found".format(text, n))
        self.findData.FindString = text
    
    ## *** The following code is a modification of <wx.py.frame.Frame> ***
    
    def OnFindText(self, evt):
        if self.findDlg is not None:
            self.findDlg.SetFocus()
            return
        
        win = self.current_editor
        self.findData.FindString = win.topic_at_caret
        self.findDlg = wx.FindReplaceDialog(win, self.findData, "Find",
                            style=wx.FR_NOWHOLEWORD|wx.FR_NOUPDOWN)
        self.findDlg.Show()
    
    def OnFindNext(self, evt, backward=False): #<wx._core.FindDialogEvent>
        if self.findDlg:
            self.findDlg.Close()
            self.findDlg = None
        
        data = self.findData
        down_p = data.Flags & wx.FR_DOWN
        if (backward and down_p) or (not backward and not down_p):
            data.Flags ^= wx.FR_DOWN # toggle up/down flag
        
        win = self.current_editor # or self.findDlg.Parent <EditWindow>
        win.DoFindNext(data)
    
    def OnFindPrev(self, evt):
        self.OnFindNext(evt, backward=True)
    
    def OnFindClose(self, evt): #<wx._core.FindDialogEvent>
        self.findDlg.Destroy()
        self.findDlg = None


class EditorInterface(CtrlInterface, KeyCtrlInterfaceMixin):
    """Python code editor interface with Keymap
    """
    message = print
    
    def __init__(self):
        CtrlInterface.__init__(self)
        
        def fork_parent(v):
            try:
                self.parent.handler(self.handler.current_event, v)
            except AttributeError:
                pass
        
        _F = funcall
        
        self.handler.update({ #<Editor handler>
            -1 : {  # original action of the Editor
                    '* pressed' : (0, skip, lambda v: self.message("ESC {}".format(v.key))),
                 '*alt pressed' : (-1, ),
                '*ctrl pressed' : (-1, ),
               '*shift pressed' : (-1, ),
             '*[LR]win pressed' : (-1, ),
            },
            0 : {
             '*button* pressed' : (0, skip, fork_parent),
            '*button* released' : (0, skip, fork_parent),
                     '* dclick' : (0, skip, fork_parent),
                    '* pressed' : (0, skip),
                   '* released' : (0, skip),
               'escape pressed' : (-1, _F(lambda v: self.message("ESC-"), alias="escape")),
               'insert pressed' : (0, _F(lambda v: self.over(None), "toggle-over")),
                   'f9 pressed' : (0, _F(lambda v: self.wrap(None), "toggle-fold-type")),
                  'C-l pressed' : (0, _F(lambda v: self.recenter(), "recenter")),
                'C-S-l pressed' : (0, _F(lambda v: self.recenter(-1), "recenter-bottom")),
               'C-M-up pressed' : (0, _F(lambda v: self.ScrollLines(-2), "scroll-up")),
             'C-M-down pressed' : (0, _F(lambda v: self.ScrollLines(+2), "scroll-down")),
               'C-left pressed' : (0, _F(self.WordLeft)),
              'C-right pressed' : (0, _F(self.WordRightEnd)),
               'C-S-up pressed' : (0, _F(self.LineUpExtend)),
             'C-S-down pressed' : (0, _F(self.LineDownExtend)),
             'C-S-left pressed' : (0, _F(self.selection_backward_word_or_paren)),
            'C-S-right pressed' : (0, _F(self.selection_forward_word_or_paren)),
                  'C-a pressed' : (0, _F(self.beggining_of_line)),
                  'C-e pressed' : (0, _F(self.end_of_line)),
                  'M-a pressed' : (0, _F(self.back_to_indentation)),
                  'M-e pressed' : (0, _F(self.end_of_line)),
                  'C-k pressed' : (0, _F(self.kill_line)),
                'C-S-f pressed' : (0, _F(self.set_mark)), # override key
              'C-space pressed' : (0, _F(self.set_mark)),
              'S-space pressed' : (0, skip),
          'C-backspace pressed' : (0, skip),
          'S-backspace pressed' : (0, _F(self.backward_kill_line)),
                'C-tab pressed' : (0, _F(self.insert_space_like_tab)),
              'C-S-tab pressed' : (0, _F(self.delete_backward_space_like_tab)),
                  ## 'C-d pressed' : (0, ),
                  ## 'C-/ pressed' : (0, ), # cf. C-a home
                  ## 'C-\ pressed' : (0, ), # cf. C-e end
                ## 'M-S-, pressed' : (0, _F(self.goto_char, pos=0, doc="beginning-of-buffer")),
                ## 'M-S-. pressed' : (0, _F(self.goto_char, pos=-1, doc="end-of-buffer")),
            },
        })
        self.handler.clear(0)
        
        self.make_keymap('C-x')
        self.define_key('C-x *', skip) # skip to parent frame always
        
        self.make_keymap('C-c')
        self.define_key('C-c *', skip) # skip to parent frame always
        
        self.define_key('C-c C-c', self.goto_matched_paren)
        
        ## cf. wx.py.editwindow.EditWindow.OnUpdateUI => Check for brace matching
        self.Bind(stc.EVT_STC_UPDATEUI,
                  lambda v: self.match_paren()) # no skip
        
        ## Keyword(2) setting
        self.SetLexer(stc.STC_LEX_PYTHON)
        self.SetKeyWords(0, ' '.join(keyword.kwlist))
        self.SetKeyWords(1, ' '.join(builtins.__dict__))
        
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
        
        ## Set the mask and width
        ## [1] 32bit mask 1111,1110,0000,0000,0000,0000,0000,0000
        ## [2] 32bit mask 0000,0001,1111,1111,1111,1111,1111,1111
        
        self.SetMarginType(0, stc.STC_MARGIN_SYMBOL)
        self.SetMarginMask(0, 0b0111) # mask for default markers
        ## self.SetMarginMask(0, -1) # mask for all markers
        self.SetMarginWidth(0, 10)
        
        self.SetMarginType(1, stc.STC_MARGIN_NUMBER)
        self.SetMarginMask(1, 0b1000) # default: no symbols
        self.SetMarginWidth(1, 0) # default: no margin
        
        self.SetMarginType(2, stc.STC_MARGIN_SYMBOL)
        self.SetMarginMask(2, stc.STC_MASK_FOLDERS) # mask for folders
        self.SetMarginWidth(2, 0) # default: no margin
        
        self.SetMarginLeft(2) # +1 margin at the left
        
        ## Custom markers (cf. MarkerAdd)
        self.MarkerDefine(0, stc.STC_MARK_CIRCLE, '#0080f0', "#0080f0") # o blue-mark
        self.MarkerDefine(1, stc.STC_MARK_ARROW,  '#000000', "#ffffff") # > white-arrow
        self.MarkerDefine(2, stc.STC_MARK_ARROW,  '#7f0000', "#ff0000") # > red-arrow
        self.MarkerDefine(3, stc.STC_MARK_SHORTARROW, 'blue', "gray")   # >> pointer
        
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
        if wx.VERSION < (4,1,0):
            self.IndicatorSetStyle(0, stc.STC_INDIC_PLAIN)
            self.IndicatorSetStyle(1, stc.STC_INDIC_ROUNDBOX)
        else:
            self.IndicatorSetStyle(0, stc.STC_INDIC_TEXTFORE)
            self.IndicatorSetStyle(1, stc.STC_INDIC_ROUNDBOX)
        self.IndicatorSetForeground(0, "red")
        self.IndicatorSetForeground(1, "yellow")
        
        ## Custom indicator for match_paren
        self.IndicatorSetStyle(2, stc.STC_INDIC_PLAIN)
        self.IndicatorSetForeground(2, "light gray")
        
        ## Custom style of control-char, wrap-mode
        ## self.ViewEOL = True
        ## self.ViewWhiteSpace = True
        ## self.TabWidth = 4
        ## self.UseTabs = False
        self.WrapMode = 0
        self.WrapIndentMode = 1
        
        self.__mark = None
    
    ## custom constants embedded in stc
    stc.STC_P_WORD3 = 16
    
    mark = property(
        lambda self: self.get_mark(),
        lambda self,v: self.set_mark(v),
        lambda self: self.del_mark())
    
    def get_mark(self):
        return self.__mark
    
    def set_mark(self, pos=None):
        if pos is None:
            pos = self.cur
        self.__mark = pos
        self.MarkerDeleteAll(0) # exclusive mark (like emacs)
        self.MarkerAdd(self.LineFromPosition(pos), 0)
    
    def del_mark(self):
        self.__mark = None
        self.MarkerDeleteAll(0)
    
    def set_style(self, spec=None, **kwargs):
        spec = spec and spec.copy() or {}
        spec.update(kwargs)
        
        def _map(sc):
            return dict(kv.partition(':')[::2] for kv in sc.split(','))
        
        if "STC_STYLE_DEFAULT" in spec:
            self.StyleSetSpec(stc.STC_STYLE_DEFAULT, spec.pop("STC_STYLE_DEFAULT"))
            self.StyleClearAll()
        
        if "STC_STYLE_LINENUMBER" in spec:
            lsc = _map(spec.get("STC_STYLE_LINENUMBER"))
            
            self.SetMarginWidth(1, 32)
            self.SetMarginWidth(2, 1)
            self.SetProperty('fold', '0')
            ## Set colors used as a chequeboard pattern.
            ## Being one pixel solid line, the back and fore should be the same.
            self.SetFoldMarginColour(True, lsc.get('fore')) # back: one of the colors
            self.SetFoldMarginHiColour(True, lsc.get('fore')) # fore: the other color
        
        ## Custom style for caret and line colour
        if "STC_STYLE_CARETLINE" in spec:
            lsc = _map(spec.pop("STC_STYLE_CARETLINE"))
            
            self.SetCaretLineVisible(0)
            if 'fore' in lsc:
                self.SetCaretForeground(lsc['fore'])
            if 'back' in lsc:
                self.SetCaretLineBackground(lsc['back'])
                self.SetCaretLineVisible(1)
            if 'size' in lsc:
                self.SetCaretWidth(int(lsc['size']))
                self.SetCaretStyle(stc.STC_CARETSTYLE_LINE)
            if 'bold' in lsc:
                self.SetCaretStyle(stc.STC_CARETSTYLE_BLOCK)
        
        ## Custom indicator for search-word
        if "STC_P_WORD3" in spec:
            lsc = _map(spec.get("STC_P_WORD3"))
            
            self.IndicatorSetForeground(0, lsc.get('fore') or "red")
            self.IndicatorSetForeground(1, lsc.get('back') or "red")
        
        for key, value in spec.items():
            self.StyleSetSpec(getattr(stc, key), value)
    
    ## def apply_filter(self, pos, length):
    ##     if wx.VERSION < (4,1,0):
    ##         self.StartStyling(pos, 0x1f)
    ##     else:
    ##         self.StartStyling(pos)
    ##     self.SetStyling(length, stc.STC_P_WORD3)
    
    ## def match_paren(self):
    ##     if wx.VERSION < (4,1,0):
    ##         return self._match_paren()
    ##     self.SetIndicatorCurrent(2)
    ##     self.IndicatorClearRange(0, self.TextLength)
    ##     p = self._match_paren()
    ##     if p:
    ##         self.IndicatorFillRange(p, self.cur-p)
    
    def match_paren(self):
        cur = self.cur
        if self.following_char in "({[<":
            pos = self.BraceMatch(cur)
            if pos != -1:
                self.BraceHighlight(cur, pos) # matched to following char
                return pos
            else:
                self.BraceBadLight(cur)
        elif self.preceding_char in ")}]>":
            pos = self.BraceMatch(cur-1)
            if pos != -1:
                self.BraceHighlight(pos, cur-1) # matched to preceding char
                return pos
            else:
                self.BraceBadLight(cur-1)
        else:
            self.BraceHighlight(-1,-1) # no highlight
    
    def over(self, mode=1):
        """Set overwt(insertion) mode. toggle when mode is None"""
        self.Overtype = mode if mode is not None else not self.Overtype
        self.Refresh()
    
    def wrap(self, mode=1):
        """Set fold type (override) of wrap
        mode in {0:no-wrap, 1:word-wrap (2:no-word-wrap), None:toggle}
        """
        self.WrapMode = mode if mode is not None else not self.WrapMode
    
    def recenter(self, ln=None):
        """Scroll the cursor line to the center of screen (ln default None)
        if ln=0, the cursor goes top of the screen. ln=-1 the bottom
        """
        n = self.LinesOnScreen() # lines completely visible
        lc = self.lcur - (n//2 if ln is None else ln%n if ln < n else n)
        self.ScrollToLine(lc)
    
    ## --------------------------------
    ## Attributes of the editor
    ## --------------------------------
    following_char = property(lambda self: chr(self.GetCharAt(self.cur)))
    preceding_char = property(lambda self: chr(self.GetCharAt(self.cur-1)))
    
    @property
    def following_symbol(self):
        """Similar to following_char, but skips whites"""
        ln = self.GetTextRange(self.cur, self.eol)
        return next((c for c in ln if not c.isspace()), '')
    
    @property
    def preceding_symbol(self):
        """Similar to preceding_char, but skips whites"""
        ln = self.GetTextRange(self.bol, self.cur)[::-1]
        return next((c for c in ln if not c.isspace()), '')
    
    ## CurrentPos, cf. Anchor
    cur = property(
        lambda self: self.GetCurrentPos(),
        lambda self,v: self.SetCurrentPos(v))
    
    ## CurrentLine
    lcur = property(
        lambda self: self.GetCurrentLine(),
        lambda self,v: self.SetCurrentLine(v))
    
    @property
    def bol(self):
        """beginning of line"""
        text, lp = self.CurLine
        return self.cur - lp
    
    @property
    def eol(self):
        """end of line"""
        text, lp = self.CurLine
        if text.endswith(os.linesep):
            lp += len(os.linesep)
        return (self.cur - lp + len(text.encode()))
    
    @property
    def expr_at_caret(self):
        """Pythonic expression at the caret
        The caret scouts back and forth to scoop a chunk of expression.
        """
        text, lp = self.CurLine
        ls, rs = text[:lp], text[lp:]
        lhs = get_words_backward(ls) # or ls.rpartition(' ')[-1]
        rhs = get_words_forward(rs) # or rs.partition(' ')[0]
        return (lhs + rhs).strip()
    
    @property
    def topic_at_caret(self):
        """Topic word at the caret or selected substring
        The caret scouts back and forth to scoop a topic.
        """
        return self.get_selection_or_topic()
    
    @property
    def right_paren(self):
        if self.following_char in "({[<":
            return self.BraceMatch(self.cur) # (0 <= cur < pos+1)
        return -1
    
    @property
    def left_paren(self):
        if self.preceding_char in ")}]>":
            return self.BraceMatch(self.cur-1) # (0 <= pos < cur-1)
        return -1
    
    @property
    def right_quotation(self):
        text = self.GetTextRange(self.cur, self.TextLength)
        if text and text[0] in "\"\'":
            try:
                lexer = shlex.shlex(text)
                return self.cur + len(lexer.get_token())
            except ValueError:
                pass # no closing quotation
        return -1
    
    @property
    def left_quotation(self):
        text = self.GetTextRange(0, self.cur)[::-1]
        if text and text[0] in "\"\'":
            try:
                lexer = shlex.shlex(text)
                return self.cur - len(lexer.get_token())
            except ValueError:
                pass # no closing quotation
        return -1
    
    ## --------------------------------
    ## Goto, Skip, Selection, etc.
    ## --------------------------------
    
    def clear(self):
        """Delete all text"""
        self.ClearAll()
    
    def goto_char(self, pos):
        if pos < 0:
            pos += self.TextLength + 1 # end-of-buffer (+1:\0)
        self.GotoPos(pos)
        return self.cur
    
    def goto_line(self, ln):
        if ln < 0:
            ln += self.LineCount
        self.GotoLine(ln)
        return self.cur
    
    def skip_chars_forward(self, rexpr=r'\s'):
        p = re.compile(rexpr)
        while p.search(self.following_char):
            c = self.cur
            if c == self.TextLength:
                break
            self.GotoPos(c + 1)
        return self.cur
    
    def skip_chars_backward(self, rexpr=r'\s'):
        p = re.compile(rexpr)
        while p.search(self.preceding_char):
            c = self.cur
            if c == 0:
                break
            self.GotoPos(c - 1)
        return self.cur
    
    def back_to_indentation(self):
        self.ScrollToColumn(0)
        self.GotoPos(self.bol)
        return self.skip_chars_forward(r'\s')
    
    def beggining_of_line(self):
        self.GotoPos(self.bol)
        self.ScrollToColumn(0)
        return self.cur
    
    def end_of_line(self):
        self.GotoPos(self.eol)
        return self.cur
    
    def goto_matched_paren(self):
        p = self.right_paren
        if p != -1:
            return self.GotoPos(p+1)
        p = self.left_paren
        if p != -1:
            return self.GotoPos(p)
        q = self.right_quotation
        if q != -1:
            return self.GotoPos(q)
        q = self.left_quotation
        if q != -1:
            return self.GotoPos(q)
    
    def selection_forward_word_or_paren(self):
        p = self.right_paren
        if p != -1:
            return self.SetCurrentPos(p+1) # forward selection to parenthesized words
        q = self.right_quotation
        if q != -1:
            return self.SetCurrentPos(q) # forward selection to quoted words
        self.WordRightEndExtend()  # otherwise, extend selection forward word
    
    def selection_backward_word_or_paren(self):
        p = self.left_paren
        if p != -1:
            return self.SetCurrentPos(p) # backward selection to parenthesized words
        q = self.left_quotation
        if q != -1:
            return self.SetCurrentPos(q) # forward selection to quoted words
        self.WordLeftExtend() # otherwise, extend selection backward word
    
    def get_selection_or_topic(self):
        """selected substring or topic word at the caret"""
        topic = self.SelectedText
        if topic:
            return topic
        with self.save_excursion():
            ## org = self.cur # save-excursion
            p = q = self.cur
            if not self.preceding_char.isspace():
                self.WordLeft()
                p = self.cur
            if not self.following_char.isspace():
                self.WordRightEnd()
                q = self.cur
            ## self.GotoPos(org) # restore-excursion
            return self.GetTextRange(p, q)
    
    def save_excursion(self):
        class Excursion(object):
            def __init__(self, win):
                self._win = win
            
            def __enter__(self):
                self.pos = self._win.cur
                self.vpos = self._win.GetScrollPos(wx.VERTICAL)
                self.hpos = self._win.GetScrollPos(wx.HORIZONTAL)
            
            def __exit__(self, t, v, tb):
                self._win.GotoPos(self.pos)
                self._win.ScrollToLine(self.vpos)
                self._win.SetXOffset(self.hpos)
            
        return Excursion(self)
    
    ## --------------------------------
    ## Edit /eat /kill
    ## --------------------------------
    
    def eat_white_forward(self):
        p = self.cur
        q = self.skip_chars_forward(r'\s')
        self.Replace(p, q, '')
    
    def eat_white_backward(self):
        p = self.cur
        q = self.skip_chars_backward(r'\s')
        self.Replace(max(q, self.bol), p, '')
    
    def kill_line(self):
        if self.CanEdit():
            p = self.eol
            text, lp = self.CurLine
            if p == self.cur:
                if self.GetTextRange(p, p+2) == '\r\n': p += 2
                elif self.GetTextRange(p, p+1) == '\n': p += 1
            self.Replace(self.cur, p, '')
    
    def backward_kill_line(self):
        if self.CanEdit():
            p = self.bol
            text, lp = self.CurLine
            if text[:lp] == '' and p: # caret at the beginning of the line
                p -= len(os.linesep)
            elif text[:lp] == sys.ps2: # caret at the prompt head
                p -= len(sys.ps2)
            self.Replace(p, self.cur, '')
    
    def insert_space_like_tab(self):
        """Enter half-width spaces forward as if feeling like a tab
        タブの気持ちになって半角スペースを前向きに入力する
        """
        self.eat_white_forward()
        _text, lp = self.CurLine
        self.write(' ' * (4 - lp % 4))
    
    def delete_backward_space_like_tab(self):
        """Delete half-width spaces backward as if feeling like a shift+tab
        シフト+タブの気持ちになって半角スペースを後ろ向きに消す
        """
        self.eat_white_forward()
        _text, lp = self.CurLine
        for i in range(lp % 4 or 4):
            p = self.cur
            if self.preceding_char != ' ' or p == self.bol:
                break
            self.cur = p-1
        self.ReplaceSelection('')


class Editor(EditWindow, EditorInterface):
    """Python code editor
    """
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.statusbar)
    
    PALETTE_STYLE = { #<Editor>
      # Default style for all languages
        "STC_STYLE_DEFAULT"     : "fore:#000000,back:#ffffb8,face:MS Gothic,size:9",
        "STC_STYLE_CARETLINE"   : "fore:#000000,back:#ffff7f,size:2",
        "STC_STYLE_LINENUMBER"  : "fore:#000000,back:#ffffb8,size:9",
        "STC_STYLE_BRACELIGHT"  : "fore:#000000,back:#ffffb8,bold",
        "STC_STYLE_BRACEBAD"    : "fore:#000000,back:#ff0000,bold",
        "STC_STYLE_CONTROLCHAR" : "size:9",
      # Python lexical style
        "STC_P_DEFAULT"         : "fore:#000000,back:#ffffb8",
        "STC_P_IDENTIFIER"      : "fore:#000000",
        "STC_P_COMMENTLINE"     : "fore:#007f7f,back:#ffcfcf",
        "STC_P_COMMENTBLOCK"    : "fore:#007f7f,back:#ffcfcf,eol",
        "STC_P_CHARACTER"       : "fore:#7f7f7f",
        "STC_P_STRING"          : "fore:#7f7f7f",
        "STC_P_TRIPLE"          : "fore:#7f7f7f,eol",
        "STC_P_TRIPLEDOUBLE"    : "fore:#7f7f7f,eol",
        "STC_P_STRINGEOL"       : "fore:#7f7f7f",
        "STC_P_WORD"            : "fore:#0000ff",
        "STC_P_WORD2"           : "fore:#b8007f",
        "STC_P_WORD3"           : "fore:#ff0000,back:#ffff00", # custom style for search word
        "STC_P_DEFNAME"         : "fore:#0000ff,bold",
        "STC_P_CLASSNAME"       : "fore:#0000ff,bold",
        "STC_P_DECORATOR"       : "fore:#e08040",
        "STC_P_OPERATOR"        : "",
        "STC_P_NUMBER"          : "fore:#7f0000",
    }
    
    def __init__(self, parent, **kwargs):
        EditWindow.__init__(self, parent, **kwargs)
        EditorInterface.__init__(self)
        
        self.__parent = parent #= self.Parent, but not always if whose son is floating
        
        ## To prevent @filling from *HARD-CRASH*
        ## We never allow DnD of text, file, etc.
        self.SetDropTarget(None)
        
        self.set_style(self.PALETTE_STYLE)


class Nautilus(Shell, EditorInterface):
    """Nautilus in the Shell with Editor interface
--------------------------------------------------
Features:
    All objects in the process can be accessed
    using
        self : the target of the shell,
        this : the module which includes target.
    
    So as you are diving into the sea of python process,
    watch, change, and break everything in the target.
    
    Nautilus supports you to dive confortably with
    special syntax, several utilities, five autocomp modes, etc.
    See below.

Magic syntax:
   quoteback : x`y --> y=x  | x`y`z --> z=y=x
    pullback : x@y --> y(x) | x@y@z --> z(y(x))
     apropos : x.y? [not] p --> shows apropos (not-)matched by predicates `p
                equiv. apropos(x, y [,ignorecase ?:True,??:False] [,pred=p])
                y can contain regular expressions.
                    (RE) \\a:[a-z], \\A:[A-Z] can be used in addition.
                p can be ?atom, ?callable, ?type (e.g., int,str,etc.),
                    and any predicates imported from inspect module
                    such as isclass, ismodule, isfunction, etc.
  
  *     info :  ?x (x@?) --> info(x) shows short information
  *     help : ??x (x@??) --> help(x) shows full description
  *   system :  !x (x@!) --> sx(x) executes command in external shell
  
  * denotes original syntax defined in wx.py.shell,
    for which, at present version, enabled with USE_MAGIC switch being on

Shell built-in utility:
    @p          synonym of print
    @pp         synonym of pprint
    @info   @?  short info
    @help   @?? full description
    @dive       clone the shell with new target
    @debug      debug the callable object using pdb
    @timeit     measure the duration cpu time
    @execute    exec in the locals (PY2-compatible)
    @filling    inspection using wx.lib.filling.Filling
    @watch      inspection using wx.lib.inspection.InspectionTool
    @edit       open with your editor (undefined)
    @file       inspect.getfile -> str
    @code       inspect.getsource -> str
    @module     inspect.getmodule -> module
    @where      (filename, lineno) or the module
    @debug      pdb in the shell

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
  * Autocomps are incremental when pressed any alnums, and decremental when backspace.

Enter key bindings:
     C-enter : insert-line-break

This module is based on the implementation of wx.py.shell.
    Some of the original key bindings are overridden in the FSM framework.
    To read the original key bindings, see 'wx.py.shell.HELP_TEXT'.
    The original key bindings are mapped in esc-map, i.e.,
    e.g., if you want to do 'select-all', type [ESC C-a], not [C-a]

The most convenient way to see the details of keymaps on the shell:
    >>> self.shell.handler @p
     or self.shell.handler @filling

Flaky nutshell:
    Half-baked by Patrik K. O'Brien,
    and the other half by K. O'moto.
    """
    target = property(lambda self: self.__target)
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.statusbar)
    
    @target.setter
    def target(self, target):
        if not hasattr(target, '__dict__'):
            raise TypeError("cannot target primitive objects")
        target.self = target
        target.this = inspect.getmodule(target)
        target.shell = self # overwrite the facade <wx.py.shell.ShellFacade>
        
        self.__target = target
        self.interp.locals.update(target.__dict__)
        try:
            self.parent.Title = re.sub("(.*) - (.*)",
                                       "\\1 - {!r}".format(target),
                                       self.parent.Title)
        except AttributeError:
            pass
    
    ## Default classvar string to Execute when starting the shell was deprecated.
    ## You should better describe the starter in your script ($PYTHONSTARTUP:~/.py)
    ## SHELLSTARTUP = ""
    
    PALETTE_STYLE = { #<Shell>
     ## Default style for all languages
        "STC_STYLE_DEFAULT"     : "fore:#cccccc,back:#202020,face:MS Gothic,size:9",
        "STC_STYLE_CARETLINE"   : "fore:#ffffff,back:#012456,size:2",
        "STC_STYLE_LINENUMBER"  : "fore:#000000,back:#f0f0f0,size:9",
        "STC_STYLE_BRACELIGHT"  : "fore:#ffffff,back:#202020,bold",
        "STC_STYLE_BRACEBAD"    : "fore:#ffffff,back:#ff0000,bold",
        "STC_STYLE_CONTROLCHAR" : "size:9",
     ## Python lexical style
        "STC_P_DEFAULT"         : "fore:#cccccc,back:#202020",
        "STC_P_IDENTIFIER"      : "fore:#cccccc",
        "STC_P_COMMENTLINE"     : "fore:#42c18c,back:#004040",
        "STC_P_COMMENTBLOCK"    : "fore:#42c18c,back:#004040,eol",
        "STC_P_CHARACTER"       : "fore:#a0a0a0",
        "STC_P_STRING"          : "fore:#a0a0a0",
        "STC_P_TRIPLE"          : "fore:#a0a0a0,back:#004040,eol",
        "STC_P_TRIPLEDOUBLE"    : "fore:#a0a0a0,back:#004040,eol",
        "STC_P_STRINGEOL"       : "fore:#808080",
        "STC_P_WORD"            : "fore:#80a0ff",
        "STC_P_WORD2"           : "fore:#ff80ff",
        "STC_P_WORD3"           : "fore:#ff0000,back:#ffff00", # optional for search word
        "STC_P_DEFNAME"         : "fore:#e0c080,bold",
        "STC_P_CLASSNAME"       : "fore:#e0c080,bold",
        "STC_P_DECORATOR"       : "fore:#e08040",
        "STC_P_OPERATOR"        : "",
        "STC_P_NUMBER"          : "fore:#ffc080",
    }
    
    def __init__(self, parent, target, locals=None,
                        introText = None,
                    startupScript = None,
                execStartupScript = True):
        Shell.__init__(self, parent, locals=target.__dict__,
                        introText = introText,
                    startupScript = startupScript,
                execStartupScript = execStartupScript) # if True, executes ~/.py
        EditorInterface.__init__(self)
        
        if locals:
            self.interp.locals.update(locals)
        
        self.modules = find_modules(speckey_state('ctrl')
                                  & speckey_state('shift'))
        
        self.__parent = parent #= self.Parent, but not always if whose son is floating
        self.__target = target # see interp <wx.py.interpreter.Interpreter>
        self.__root = None
        
        wx.py.shell.USE_MAGIC = True
        wx.py.shell.magic = self.magic # called when USE_MAGIC
        
        ## このシェルはプロセス内で何度もコールされることが想定されます．
        ## デバッグポイントとして使用される場合，また，クローンされる場合がそうです．
        ## ビルトインがデッドオブジェクトを参照することにならないように以下の方法で回避します．
        ## 
        ## This shell is expected to be called many times in the process,
        ## e.g., when used as a break-point and when cloned.
        ## To prevent the builtins from referring dead objects, we use the following method.
        ## 
        ## Assign objects each time it is activated so that the target
        ## does not refer to dead objects in the shell clones (to be deleted).
        def activate(evt):
            if evt.Active:
                self.handler('shell_activated', self)
            else:
                self.handler('shell_inactivated', self)
                if self.AutoCompActive():
                    self.AutoCompCancel()
                if self.CallTipActive():
                    self.CallTipCancel()
            evt.Skip()
        self.parent.Bind(wx.EVT_ACTIVATE, activate)
        
        self.on_activated(self) # call once manually
        
        ## Keywords(2) setting for *STC_P_WORD*
        self.SetKeyWords(0, ' '.join(keyword.kwlist))
        self.SetKeyWords(1, ' '.join(builtins.__dict__) + ' self this')
        
        ## EditWindow.OnUpdateUI は Shell.OnUpdateUI とかぶってオーバーライドされるので
        ## ここでは別途 EVT_STC_UPDATEUI ハンドラを追加する (EVT_UPDATE_UI ではない !)
        
        self.Bind(stc.EVT_STC_UPDATEUI, self.OnUpdate) # skip to brace matching
        
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        
        ## テキストドラッグの禁止
        ## We never allow DnD of text, file, etc.
        self.SetDropTarget(None)
        
        ## some AutoComp settings
        self.AutoCompSetAutoHide(False)
        self.AutoCompSetIgnoreCase(True)
        
        def clear(v):
            ## Clear selection and statusline, no skip.
            ## *do not* clear autocomp, so that the event can skip to AutoComp properly.
            ## if self.AutoCompActive():
            ##     self.AutoCompCancel() # may delete selection
            if self.CanEdit():
                self.ReplaceSelection("")
            self.message("")
        
        def fork(v):
            self.handler.fork(v) # fork event to 0=default
        
        _F = funcall
        
        self.handler.update({ #<Shell handler>
            None : {
                'shell_cloned' : [ None, ],
             'shell_activated' : [ None, self.on_activated ],
           'shell_inactivated' : [ None, self.on_inactivated ],
            },
            -1 : { # original action of the wx.py.shell
                    '* pressed' : (0, skip, lambda v: self.message("ESC {}".format(v.key))),
                 '*alt pressed' : (-1, ),
                '*ctrl pressed' : (-1, ),
               '*shift pressed' : (-1, ),
             '*[LR]win pressed' : (-1, ),
            },
            0 : { # Normal mode
             ## '*f[0-9]* pressed' : (0, ), # -> function keys skip to the parent
                    '* pressed' : (0, skip),
               'escape pressed' : (-1, self.OnEscape),
                'space pressed' : (0, self.OnSpace),
           '*backspace pressed' : (0, self.OnBackspace),
                '*left pressed' : (0, self.OnBackspace),
               '*enter pressed' : (0, ), # -> OnShowCompHistory 無効
                'enter pressed' : (0, self.OnEnter),
              'C-enter pressed' : (0, _F(self.insertLineBreak)),
            'C-S-enter pressed' : (0, _F(self.insertLineBreak)),
                 ## 'C-up pressed' : (0, _F(lambda v: self.OnHistoryReplace(+1), "prev-command")),
               ## 'C-down pressed' : (0, _F(lambda v: self.OnHistoryReplace(-1), "next-command")),
               ## 'C-S-up pressed' : (0, ), # -> Shell.OnHistoryInsert(+1) 無効
             ## 'C-S-down pressed' : (0, ), # -> Shell.OnHistoryInsert(-1) 無効
                 'M-up pressed' : (0, _F(self.goto_previous_mark)),
               'M-down pressed' : (0, _F(self.goto_next_mark)),
                  ## 'C-a pressed' : (0, _F(self.beggining_of_command_line)),
                  ## 'C-e pressed' : (0, _F(self.end_of_command_line)),
                  'M-j pressed' : (0, self.call_tooltip2),
                  'C-j pressed' : (0, self.call_tooltip),
                  'M-h pressed' : (0, self.call_helpTip2),
                  'C-h pressed' : (0, self.call_helpTip),
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
                    '* pressed' : (0, fork),
                  '*up pressed' : (1, self.on_completion_forward), # 古いヒストリへ進む
                '*down pressed' : (1, self.on_completion_backward), # 新しいヒストリへ戻る
               'S-left pressed' : (1, skip),
              'S-right pressed' : (1, skip),
              'shift* released' : (1, self.call_history_comp),
                  'tab pressed' : (1, self.on_completion_forward),
                'S-tab pressed' : (1, self.on_completion_backward),
                  'M-p pressed' : (1, self.on_completion_forward),
                  'M-n pressed' : (1, self.on_completion_backward),
                'enter pressed' : (0, lambda v: self.goto_char(-1)),
               'escape pressed' : (0, clear),
            '[a-z0-9_] pressed' : (1, skip),
           '[a-z0-9_] released' : (1, self.call_history_comp),
            'S-[a-z\\] pressed' : (1, skip),
           'S-[a-z\\] released' : (1, self.call_history_comp),
                  ## 'M-. pressed' : (2, clear, self.call_word_autocomp),
                  ## 'M-/ pressed' : (3, clear, self.call_apropos_autocomp),
                  ## 'M-, pressed' : (4, clear, self.call_text_autocomp),
                 '*alt pressed' : (1, ),
                '*ctrl pressed' : (1, ),
               '*shift pressed' : (1, ),
             '*[LR]win pressed' : (1, ),
             '*f[0-9]* pressed' : (1, ),
            },
            2 : { # word auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (2, self.on_completion_backward, skip),
                 'down pressed' : (2, self.on_completion_forward, skip),
               'S-left pressed' : (2, skip),
              'S-right pressed' : (2, skip),
              'shift* released' : (2, self.call_word_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (2, skip),
          '[a-z0-9_.] released' : (2, self.call_word_autocomp),
            'S-[a-z\\] pressed' : (2, skip),
           'S-[a-z\\] released' : (2, self.call_word_autocomp),
              '*delete pressed' : (2, skip),
           '*backspace pressed' : (2, self.skipback_autocomp, skip),
          '*backspace released' : (2, self.call_word_autocomp, self.decrback_autocomp),
                  'M-j pressed' : (2, self.call_tooltip2),
                  'C-j pressed' : (2, self.call_tooltip),
                  'M-h pressed' : (2, self.call_helpTip2),
                  'C-h pressed' : (2, self.call_helpTip),
                  ## 'M-. pressed' : (2, self.on_completion),
                  ## 'M-/ pressed' : (3, clear, self.call_apropos_autocomp),
                  ## 'M-, pressed' : (4, clear, self.call_text_autocomp),
                 '*alt pressed' : (2, ),
                '*ctrl pressed' : (2, ),
               '*shift pressed' : (2, ),
             '*[LR]win pressed' : (2, ),
             '*f[0-9]* pressed' : (2, ),
            },
            3 : { # apropos auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (3, self.on_completion_backward, skip),
                 'down pressed' : (3, self.on_completion_forward, skip),
               'S-left pressed' : (3, skip),
              'S-right pressed' : (3, skip),
              'shift* released' : (3, self.call_apropos_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (3, skip),
          '[a-z0-9_.] released' : (3, self.call_apropos_autocomp),
            'S-[a-z\\] pressed' : (3, skip),
           'S-[a-z\\] released' : (3, self.call_apropos_autocomp),
              '*delete pressed' : (3, skip),
           '*backspace pressed' : (3, self.skipback_autocomp, skip),
          '*backspace released' : (3, self.call_apropos_autocomp, self.decrback_autocomp),
                  'M-j pressed' : (3, self.call_tooltip2),
                  'C-j pressed' : (3, self.call_tooltip),
                  'M-h pressed' : (3, self.call_helpTip2),
                  'C-h pressed' : (3, self.call_helpTip),
                  ## 'M-. pressed' : (2, clear, self.call_word_autocomp),
                  ## 'M-/ pressed' : (3, self.on_completion),
                  ## 'M-, pressed' : (4, clear, self.call_text_autocomp),
                 '*alt pressed' : (3, ),
                '*ctrl pressed' : (3, ),
               '*shift pressed' : (3, ),
             '*[LR]win pressed' : (3, ),
             '*f[0-9]* pressed' : (3, ),
            },
            4 : { # text auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (4, self.on_completion_backward, skip),
                 'down pressed' : (4, self.on_completion_forward, skip),
               'S-left pressed' : (4, skip),
              'S-right pressed' : (4, skip),
              'shift* released' : (4, self.call_text_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (4, skip),
          '[a-z0-9_.] released' : (4, self.call_text_autocomp),
            'S-[a-z\\] pressed' : (4, skip),
           'S-[a-z\\] released' : (4, self.call_text_autocomp),
              '*delete pressed' : (4, skip),
           '*backspace pressed' : (4, self.skipback_autocomp, skip),
          '*backspace released' : (4, self.call_text_autocomp),
                  'M-j pressed' : (4, self.call_tooltip2),
                  'C-j pressed' : (4, self.call_tooltip),
                  'M-h pressed' : (4, self.call_helpTip2),
                  'C-h pressed' : (4, self.call_helpTip),
                  ## 'M-. pressed' : (2, clear, self.call_word_autocomp),
                  ## 'M-/ pressed' : (3, clear, self.call_apropos_autocomp),
                  ## 'M-, pressed' : (4, self.on_completion),
                 '*alt pressed' : (4, ),
                '*ctrl pressed' : (4, ),
               '*shift pressed' : (4, ),
             '*[LR]win pressed' : (4, ),
             '*f[0-9]* pressed' : (4, ),
            },
            5 : { # module auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (5, self.on_completion_backward, skip),
                 'down pressed' : (5, self.on_completion_forward, skip),
               'S-left pressed' : (5, skip),
              'S-right pressed' : (5, skip),
              'shift* released' : (5, self.call_module_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, fork),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (5, skip),
          '[a-z0-9_.] released' : (5, self.call_module_autocomp),
            'S-[a-z\\] pressed' : (5, skip),
           'S-[a-z\\] released' : (5, self.call_module_autocomp),
           '*backspace pressed' : (5, self.skipback_autocomp, skip),
          '*backspace released' : (5, self.call_module_autocomp),
                 '*alt pressed' : (5, ),
                '*ctrl pressed' : (5, ),
               '*shift pressed' : (5, ),
             '*[LR]win pressed' : (5, ),
             '*f[0-9]* pressed' : (5, ),
            },
        })
        
        self.set_style(self.PALETTE_STYLE)
        
        ## Enable folder at margin=2
        self.SetProperty('fold', '1')
        self.SetMarginWidth(2, 12)
        self.SetMarginSensitive(2, True)
        self.SetFoldMarginColour(True, "#f0f0f0") # cf. STC_STYLE_LINENUMBER:back
        self.SetFoldMarginHiColour(True, "#c0c0c0")
        self.Bind(stc.EVT_STC_MARGINCLICK, self.OnMarginClick)
        self.Bind(stc.EVT_STC_MARGIN_RIGHT_CLICK, self.OnMarginRClick)
        
        self.debugger = Debugger(parent=self.parent,
                                 stdin=self.interp.stdin,
                                 stdout=self.interp.stdout)
        
        self.__text = ''
        self.__start = 0
        self.__bolc_marks = [self.bolc]
        self.__eolc_marks = [self.eolc]
    
    def OnDestroy(self, evt):
        evt.Skip()
    
    def OnUpdate(self, evt): #<wx._stc.StyledTextEvent>
        if evt.Updated & (stc.STC_UPDATE_SELECTION | stc.STC_UPDATE_CONTENT):
            text, lp = self.CurLine
            self.message("{:>6d}:{} ({})".format(self.lcur, lp, self.cur), pane=1)
            if self.handler.current_state == 0:
                text = self.expr_at_caret
                if text != self.__text:
                    name, argspec, tip = self.interp.getCallTip(text)
                    if tip:
                        tip = tip.splitlines()[0]
                    self.message(tip)
                    self.__text = text
        evt.Skip()
    
    ## --------------------------------
    ## Fold/Unfold feature
    ## --------------------------------
    
    def OnMarginClick(self, evt):
        lc = self.LineFromPosition(evt.Position)
        level = self.GetFoldLevel(lc) ^ stc.STC_FOLDLEVELBASE # header-flag or indent-level
        
        ## if level == stc.STC_FOLDLEVELHEADERFLAG: # fold the top-level header only
        if level: # fold any if the indent level is non-zero
            self.toggle_fold(lc)
    
    def OnMarginRClick(self, evt):
        lc = self.LineFromPosition(evt.Position)
        level = self.GetFoldLevel(lc) ^ stc.STC_FOLDLEVELBASE
        Menu.Popup(self, [
            (1, "&Fold ALL", wx.ArtProvider.GetBitmap(wx.ART_MINUS, size=(16,16)),
                lambda v: self.fold_all()),
                
            (2, "&Expand ALL", wx.ArtProvider.GetBitmap(wx.ART_PLUS, size=(16,16)),
                lambda v: self.unfold_all()),
        ])
    
    def toggle_fold(self, lc=None):
        """Toggle fold/unfold the header including the given line"""
        if lc is None:
            lc = self.lcur
        while 1:
            lp = self.GetFoldParent(lc)
            if lp == -1:
                break
            lc = lp
        self.ToggleFold(lc)
    
    def fold_all(self):
        """Fold all headers"""
        ln = self.LineCount
        lc = 0
        while lc < ln:
            level = self.GetFoldLevel(lc) ^ stc.STC_FOLDLEVELBASE
            if level == stc.STC_FOLDLEVELHEADERFLAG:
                self.SetFoldExpanded(lc, False)
                le = self.GetLastChild(lc, -1)
                if le > lc:
                    self.HideLines(lc+1, le)
                lc = le
            lc = lc + 1
    
    def unfold_all(self):
        """Unfold all toplevel headers"""
        ln = self.LineCount
        lc = 0
        while lc < ln:
            level = self.GetFoldLevel(lc) ^ stc.STC_FOLDLEVELBASE
            if level == stc.STC_FOLDLEVELHEADERFLAG:
                self.SetFoldExpanded(lc, True)
                le = self.GetLastChild(lc, -1)
                if le > lc:
                    self.ShowLines(lc+1, le)
                lc = le
            lc = lc + 1
    
    ## --------------------------------
    ## Special keymap of the shell
    ## --------------------------------
    
    def OnEscape(self, evt):
        """Called when escape pressed"""
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CallTipActive():
            self.CallTipCancel()
        if self.eolc < self.bolc: # check if prompt is in valid state
            self.prompt()
        self.message("ESC-")
    
    def OnSpace(self, evt):
        """Called when space pressed"""
        if not self.CanEdit():
            return
        
        if re.match(r"(import|from)\s*$", self.cmdlc)\
        or re.match(r"from\s+([\w.]+)\s+import\s*$", self.cmdlc):
            self.ReplaceSelection(' ')
            self.handler('M-m pressed', None) # call_module_autocomp
            return
        evt.Skip()
    
    def OnBackspace(self, evt):
        """Called when backspace pressed"""
        if self.cur == self.bolc:
            ## do not skip to prevent autocomp eats prompt
            ##      so not to backspace over the latest non-continuation prompt
            if self.AutoCompActive():
                self.AutoCompCancel()
            return
        evt.Skip()
    
    def OnEnter(self, evt):
        """Called when enter pressed"""
        if not self.CanEdit(): # go back to the end of command line
            self.goto_char(-1)
            return
        
        if self.AutoCompActive(): # skip to auto completion
            evt.Skip()
            return
        
        if self.eolc < self.bolc: # check if prompt is in valid state
            self.prompt()
            evt.Skip()
            return
        
        text = self.GetTextRange(self.bolc, self.eolc) #.lstrip()
        
        if self.CallTipActive():
            self.CallTipCancel()
        
        ## skip to wx.py.magic if text begins with !(sx), ?(info), and ??(help)
        if not text or text[0] in '!?':
            evt.Skip()
            return
        
        ## cast magic for `@? (Note: PY35 supports @(matmal)-operator)
        tokens = split_tokens(text)
        if any(x in tokens for x in '`@?$'):
            cmd = self.magic_interpret(tokens)
            if '\n' in cmd:
                self.Execute(cmd) # for multi-line commands
            else:
                self.run(cmd, verbose=0, prompt=0)
                self.message(cmd)
            return
        
        ## normal execute/run
        if '\n' in text:
            self.Execute(text) # for multi-line commands
        else:
            evt.Skip()
    
    def OnEnterDot(self, evt):
        """Called when dot(.) pressed"""
        sep = "`@=+-/*%<>&|^~,:; \t\r\n!?([{" # OPS; SEPARATOR_CHARS; !? and open-parens
        
        if not self.CanEdit():
            return
        
        st = self.GetStyleAt(self.cur-1)
        
        if self.following_char.isalnum(): # e.g., self[.]abc, 0[.]123, etc.,
            self.handler('quit', evt)
        elif st in (1,2,5,8,9,12): # comment, num, word, class, def
            self.handler('quit', evt)
            pass
        elif st in (3,4,6,7,13): # string, char, triplet, eol
            pass
        elif self.preceding_symbol in sep:
            self.ReplaceSelection("self")
        
        self.ReplaceSelection('.') # just write down a dot.
        evt.Skip(False)            # and do not skip to default autocomp mode
    
    ## --------------------------------
    ## Magic caster of the shell
    ## --------------------------------
    
    def magic_interpret(self, tokens):
        """Called when [Enter] command, or eval-time for tooltip
        Interpret magic syntax
           quoteback : x`y --> y=x
            pullback : x@y --> y(x)
             partial : x@(y1,...,yn) --> partial(y1,...,yn)(x)
             apropos : x.y?p --> apropos(x,y,...,p)
        
        Note: This is called before run, execute, and original magic.
        """
        sep1 = "`@=+-/*%<>&|^~;\t\r\n"   # [`] SEPARATOR_CHARS; nospace, nocomma
        sep2 = "`@=+-/*%<>&|^~;, \t\r\n" # [@] SEPARATOR_CHARS;
        
        for j,c in enumerate(tokens):
            l, r = tokens[:j], tokens[j+1:]
            
            if c == '@':
                f = "{rhs}({lhs})"
                if r and r[0] == '*':
                    f = "{rhs}(*{lhs})" # x@*y --> y(*x)
                    r.pop(0)
                while r and r[0].isspace(): # skip whites
                    r.pop(0)
                
                lhs = ''.join(l).strip() or '_'
                rhs = ''.join(extract_words_from_tokens(r, sep2)).strip()
                
                rhs = re.sub(r"(\(.*\))$",      # x@(y1,...,yn)
                             r"partial\1", rhs) # --> partial(y1,...,yn)(x)
                
                return self.magic_interpret([f.format(lhs=lhs, rhs=rhs)] + r)
            
            if c == '`':
                f = "{rhs}={lhs}"
                lhs = ''.join(l).strip() or '_'
                rhs = ''.join(extract_words_from_tokens(r, sep1)).strip()
                return self.magic_interpret([f.format(lhs=lhs, rhs=rhs)] + r)
            
            if c == '?':
                head, sep, hint = ''.join(l).rpartition('.')
                cc, pred = re.search(r"(\?+)\s*(.*)", c+''.join(r)).groups()
                
                return ("apropos({0}, {1!r}, ignorecase={2}, alias={0!r}, "
                        "pred={3!r}, locals=self.shell.interp.locals)".format(
                        head, hint.strip(), len(cc) < 2, pred or None))
            
            if c == sys.ps2.strip():
                s = ''
                while r and r[0].isspace(): # eat whites
                    s += r.pop(0)
                return ''.join(l) + c + s + self.magic_interpret(r)
            
            if c in ';\r\n':
                return ''.join(l) + c + self.magic_interpret(r)
            
        return ''.join(tokens)
    
    def magic(self, cmd):
        """Called before command pushed
        (override) with magic: f x --> f(x) disabled
        """
        if cmd:
            if cmd[0:2] == '??': cmd = 'help({})'.format(cmd[2:])
            elif cmd[0] == '?': cmd = 'info({})'.format(cmd[1:])
            elif cmd[0] == '!': cmd = 'sx({!r})'.format(cmd[1:])
        return cmd
    
    def setBuiltinKeywords(self):
        """Create pseudo keywords as part of builtins (override)"""
        Shell.setBuiltinKeywords(self)
        
        ## Add some useful global abbreviations to builtins
        builtins.typename = typename
        builtins.apropos = apropos
        builtins.reload = reload
        builtins.partial = partial
        ## builtins.pp = pprint # see below; optional args.
        builtins.p = print
        builtins.watch = watch
        builtins.filling = filling
        builtins.file = inspect.getfile
        builtins.code = inspect.getsource
        builtins.module = inspect.getmodule
        
        def where(obj):
            try:
                ## class, method, function, traceback, frame, or code object was expected
                return (inspect.getsourcefile(obj),
                        inspect.getsourcelines(obj)[1])
            except TypeError:
                return inspect.getmodule(obj)
        builtins.where = where
        
        def pp(x):
            pprint(x, width=pp.width, compact=pp.compact)
        pp.width = 100 # default 80
        pp.compact = False
        builtins.pp = pp
    
    def on_activated(self, shell):
        """Called when activated"""
        target = shell.target # assert(shell is self)
        
        target.self = target
        target.this = inspect.getmodule(target)
        target.shell = self # overwrite the facade <wx.py.shell.ShellFacade>
        
        builtins.help = self.help # utilities functions to builtins (not locals)
        builtins.info = self.info # if locals could have the same name functions.
        builtins.dive = self.clone
        builtins.debug = self.debug
        builtins.timeit = self.timeit
        builtins.execute = postcall(self.Execute)
        builtins.puts = postcall(lambda v: self.write(str(v)))
    
    def on_inactivated(self, shell):
        """Called when inactivated"""
        del builtins.help
        del builtins.info
        del builtins.dive
        del builtins.debug
        del builtins.timeit
        del builtins.execute
        del builtins.puts
    
    def on_text_input(self, text):
        """Called when [Enter] text (before push)
        Mark points, reset history point, etc.
        
        Note: text is raw input:str with no magic cast
        """
        if text.rstrip():
            self.__bolc_marks.append(self.bolc)
            self.__eolc_marks.append(self.eolc)
            self.historyIndex = -1
    
    def on_text_output(self, text):
        """Called when [Enter] text (after push)
        Set markers at the last command line.
        
        Note: text is raw output:str with no magic cast
        """
        ln = self.LineFromPosition(self.__bolc_marks[-1]) # Line to set marker
        err = re.findall(r"File \"(.*)\", line ([0-9]+)(.*)", text) # check traceback
        if not err:
            self.MarkerAdd(ln, 1) # white-arrow
        else:
            self.MarkerAdd(ln, 2) # error-arrow
        return not err
    
    ## --------------------------------
    ## Attributes of the shell
    ## --------------------------------
    fragmwords = set(keyword.kwlist + dir(builtins)) # to be used in text-autocomp
    
    ## shell.history is an instance variable of the Shell.
    ## If del shell.history, the history of the class variable is used
    history = []
    
    def push(self, command, **kwargs):
        """Send command to the interpreter for execution.
        (override) mark points before push.
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
        
        ## この段階では push された直後で，次のようになっている
        ## bolc : beginning of command-line
        ## eolc : end of the output-buffer
        try:
            ## input = self.GetTextRange(self.bolc, self.__eolc_marks[-1])
            input = self.GetTextRange(self.__bolc_marks[-1], self.__eolc_marks[-1])
            output = self.GetTextRange(self.__eolc_marks[-1], self.eolc)
            
            input = self.regulate_cmd(input).lstrip()
            
            repeat = (self.history and self.history[0] == input)
            if not repeat and input:
                Shell.addHistory(self, input)
            
            noerr = self.on_text_output(output.strip(os.linesep))
            
            ed = self.parent.History
            ed.ReadOnly = 0
            ed.write(command + os.linesep)
            ln = ed.LineFromPosition(ed.TextLength - len(command)) # line to set marker
            if noerr:
                ed.MarkerAdd(ln, 1) # white-marker
                self.fragmwords |= set(re.findall(r"\b[a-zA-Z_][\w.]+", input + output))
            else:
                ed.MarkerAdd(ln, 2) # error-marker
            ed.ReadOnly = 1
        except AttributeError:
            ## execStartupScript 実行時は出力先 (owner) が存在しないのでパス
            pass
    
    @staticmethod
    def regulate_cmd(text):
        lf = '\n'
        return (text.replace(os.linesep + sys.ps1, lf)
                    .replace(os.linesep + sys.ps2, lf)
                    .replace(os.linesep, lf))
    
    ## def _In(self, j):
    ##     """Input command:str"""
    ##     return self.GetTextRange(self.__bolc_marks[j],
    ##                              self.__eolc_marks[j])
    ## 
    ## def _Out(self, j):
    ##     """Output result:str"""
    ##     ms = self.__bolc_marks[1:] + [self.bolc]
    ##     le = len(os.linesep)
    ##     return self.GetTextRange(self.__eolc_marks[j] + le,
    ##                              ms[j] - len(sys.ps1) - le)
    
    def goto_previous_mark(self):
        marks = self.__bolc_marks + [self.bolc]
        j = np.searchsorted(marks, self.cur, 'left')
        if j > 0:
            self.goto_char(marks[j-1])
    
    def goto_next_mark(self):
        marks = self.__bolc_marks + [self.bolc]
        j = np.searchsorted(marks, self.cur, 'right')
        if j < len(marks):
            self.goto_char(marks[j])
    
    def clear(self):
        """Delete all text (override) and put new prompt"""
        self.ClearAll()
        
        self.promptPosStart = 0
        self.promptPosEnd = 0
        self.more = False
        self.prompt()
        self.__bolc_marks = []
        self.__eolc_marks = []
    
    def write(self, text, pos=None):
        """Display text in the shell (override) with :option pos"""
        if pos is not None:
            self.goto_char(pos)
        if self.CanEdit():
            Shell.write(self, text)
    
    def wrap(self, mode=1):
        """Sets whether text is word wrapped (override) with
        mode in {0:no-wrap, 1:word-wrap (2:no-word-wrap), None:toggle}
        """
        EditorInterface.wrap(self, mode)
    
    ## input = classmethod(Shell.ask)
    
    bolc = property(lambda self: self.promptPosEnd, doc="beginning of command-line")
    eolc = property(lambda self: self.TextLength, doc="end of command-line")
    
    @property
    def bol(self):
        """beginning of line (override) excluding prompt"""
        text, lp = self.CurLine
        for p in (sys.ps1, sys.ps2, sys.ps3):
            if text.startswith(p):
                lp -= len(p)
                break
        return (self.cur - lp)
    
    ## cf. getCommand(), getMultilineCommand() ... caret-line-text that has a prompt (>>>)
    
    @property
    def cmdlc(self):
        """cull command-line (with no prompt)"""
        return self.GetTextRange(self.bol, self.cur)
    
    ## @property
    ## def cmdln(self):
    ##     """full command-(multi-)line (with prompts)"""
    ##     return self.GetTextRange(self.bolc, self.eolc)
    
    ## def beggining_of_command_line(self):
    ##     self.goto_char(self.bolc)
    ##     self.ScrollToColumn(0)
    
    ## def end_of_command_line(self):
    ##     self.goto_char(self.eolc)
    
    def indent_line(self):
        """Auto-indent the current line"""
        line = self.GetTextRange(self.bol, self.eol) # no-prompt
        lstr = line.strip()
        indent = self.calc_indent()
        pos = max(self.bol + len(indent),
                  self.cur + len(indent) - (len(line) - len(lstr)))
        self.Replace(self.bol, self.eol, indent + lstr)
        self.goto_char(pos)
    
    def calc_indent(self):
        """Calculate indent spaces from prefious line"""
        ## cf. wx.py.shell.Shell.prompt
        line = self.GetLine(self.lcur - 1)
        for p in (sys.ps1, sys.ps2, sys.ps3):
            if line.startswith(p):
                line = line[len(p):]
                break
        lstr = line.lstrip()
        if not lstr:
            indent = line.strip(os.linesep)
        else:
            indent = line[:(len(line)-len(lstr))]
            if line.strip()[-1] == ':':
                m = re.match(r"[a-z]+", lstr)
                if m and m.group(0) in (
                    'if','else','elif','for','while','with',
                    'def','class','try','except','finally'):
                    indent += ' '*4
        return indent
    
    ## --------------------------------
    ## Utility functions of the shell 
    ## --------------------------------
    
    def about(self):
        """About the shell (to be overridden)"""
        print("#<module 'mwx' from {!r}>".format(__file__),
              "Author: {!r}".format(__author__),
              "Version: {!s}".format(__version__),
              "#{!r}".format(wx.py.shell), sep='\n')
        return Shell.about(self)
    
    def Paste(self):
        """Replace selection with clipboard contents.
        (override) Remove ps1 and ps2 from command to be pasted
        """
        if self.CanPaste() and wx.TheClipboard.Open():
            data = wx.TextDataObject()
            if wx.TheClipboard.GetData(data):
                self.ReplaceSelection('')
                text = data.GetText()
                text = self.lstripPrompt(text)
                text = self.fixLineEndings(text)
                command = self.regulate_cmd(text).rstrip()
                self.write(command.replace('\n', os.linesep + sys.ps2))
            wx.TheClipboard.Close()
    
    def info(self, obj=None):
        """Short information"""
        if obj is None:
            obj = self
        doc = inspect.getdoc(obj)\
          or "No information about {}".format(obj)
        try:
            ed = self.parent.Help
            ed.SetValue(doc)
            self.parent.PopupWindow(ed)
        except AttributeError:
            print(doc)
    
    def help(self, obj=None):
        """Full description"""
        ## if obj is None:
        ##     self.message("The stream is piped from stdin.")
        ##     wx.CallAfter(pydoc.help)
        ##     return
        doc = pydoc.plain(pydoc.render_doc(obj))\
          or "No description about {}".format(obj)
        try:
            ed = self.parent.Help
            ed.SetValue(doc)
            self.parent.PopupWindow(ed)
        except AttributeError:
            print(doc)
    
    def eval(self, text):
        ## return eval(text, self.target.__dict__)
        return eval(text, self.interp.locals)
    
    def Execute(self, text):
        """Replace selection with text, run commands,
        (override) and check the clock time
        """
        self.__start = self.clock()
        
        ## *** The following code is a modification of <wx.py.shell.Shell.Execute>
        ##     We override (and simplified) it to make up for missing `finally`.
        lf = '\n'
        text = self.fixLineEndings(text)
        text = self.lstripPrompt(text)
        text = self.regulate_cmd(text)
        commands = []
        c = ''
        for line in text.split(lf):
            lstr = line.lstrip()
            if (lstr and lstr == line and not any(
                lstr.startswith(x) for x in ('else', 'elif', 'except', 'finally'))):
                if c:
                    commands.append(c) # Add the previous command to the list
                c = line
            else:
                c += lf + line # Multiline command. Add to the command
        commands.append(c)
        
        self.Replace(self.bolc, self.eolc, '')
        for c in commands:
            self.write(c.replace(lf, os.linesep + sys.ps2))
            self.processLine()
    
    def run(self, command, **kwargs):
        """Execute command as if it was typed in directly
        (override) and check the clock time
        """
        self.__start = self.clock()
        
        return Shell.run(self, command, **kwargs)
    
    @staticmethod
    def clock():
        try:
            return time.perf_counter()
        except AttributeError:
            return time.clock()
    
    def timeit(self, *args, **kwargs):
        t = self.clock()
        print("... duration time: {:g} s".format(t-self.__start), file=self)
    
    def clone(self, target=None):
        if target is None:
            target = self.target
        elif not hasattr(target, '__dict__'):
            raise TypeError("cannot dive into a primitive object")
        
        frame = deb(target,
             ## size=self.Size,
             title="Clone of Nautilus - {!r}".format(target))
        
        self.handler('shell_cloned', frame.shell)
        frame.shell.__root = self
        return frame.shell
    
    ## --------------------------------
    ## Debug functions of the shell
    ## --------------------------------
    
    def hook(self, wxobj, binder, target=None):
        if not target:
            return partial(self.hook, wxobj, binder)
        @wraps(target)
        def _hook(*args, **kwargs):
            self.debug(target, *args, **kwargs)
            wxobj.Unbind(binder, handler=_hook) # release hook once called
        wxobj.Bind(binder, _hook) # add hook for the event-binder
        return target
    
    def debug(self, target, *args, **kwargs):
        if isinstance(target, wx.Window):
            self.debugger.dump(target)
            return
        if not callable(target):
            raise TypeError("{} is not callable".format(target))
        if inspect.isbuiltin(target):
            print("- cannot break {!r}".format(target))
            return
        try:
            self.write("#>> starting debugger (Enter n(ext) to continue)\n", -1)
            self.parent.Show()
            self.parent.Log.clear()
            self.parent.PopupWindow(self.parent.Log)
            self.redirectStdin()
            self.redirectStdout()
            wx.CallLater(1000, wx.EndBusyCursor) # cancel the egg timer
            wx.CallAfter(self.Execute, 'step') # step into the target
            self.handler("debug_begin", target, *args, **kwargs)
            self.debugger.open(inspect.currentframe())
            target(*args, **kwargs)
        except bdb.BdbQuit:
            pass
        finally:
            self.debugger.close()
            self.prompt()
            self.handler("debug_end", target, *args, **kwargs)
    
    ## --------------------------------
    ## Auto-comp actions of the shell
    ## --------------------------------
    
    def CallTipShow(self, pos, tip):
        """Call standard ToolTip (override) and write the tips to scratch"""
        Shell.CallTipShow(self, pos, tip)
        try:
            if tip:
                self.parent.scratch.SetValue(tip)
        except AttributeError:
            pass
    
    def gen_autocomp(self, offset, words):
        """Call AutoCompShow for the specified words"""
        try:
            self.AutoCompShow(offset, ' '.join(words))
        except AssertionError: # for phoenix >= 4.1.1
            pass
    
    def gen_tooltip(self, text):
        """Call ToolTip of the selected word or focused line"""
        if self.CallTipActive():
            self.CallTipCancel()
        try:
            try:
                cmd = self.magic_interpret(split_tokens(text))
                obj = self.eval(cmd)
                text = cmd
            except Exception as e:
                obj = self.eval(text)
            self.CallTipShow(self.cur, pformat(obj))
            self.message(text)
        except Exception as e:
            self.message("- {}: {!r}".format(e, text))
    
    def call_tooltip2(self, evt):
        """Call ToolTip of the selected word or repr"""
        self.gen_tooltip(self.SelectedText or self.expr_at_caret)
    
    def call_tooltip(self, evt):
        """Call ToolTip of the selected word or command line"""
        self.gen_tooltip(self.SelectedText or self.getCommand() or self.expr_at_caret)
    
    def call_helpTip2(self, evt):
        try:
            text = self.SelectedText or self.expr_at_caret
            if text:
                self.help(self.eval(text))
        except Exception as e:
            self.message("- {} : {!r}".format(e, text))
    
    def call_helpTip(self, evt):
        """Show tooltips for the selected topic"""
        if self.CallTipActive():
            self.CallTipCancel()
        self.OnCallTipAutoCompleteManually(True) # autoCallTipShow or autoCompleteShow
        if not self.CallTipActive():
            text = self.SelectedText or self.expr_at_caret
            if text:
                self.autoCallTipShow(text, False, True)
    
    def clear_autocomp(self, evt):
        """Clear Autocomp, selection, and message"""
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CanEdit():
            self.ReplaceSelection("")
        self.message("")
    
    def skipback_autocomp(self, evt):
        """Backspace-guard from Autocomp eating over a prompt white"""
        if self.cur == self.bolc:
            ## Do not skip to prevent autocomp eats prompt
            ## so not to backspace over the latest non-continuation prompt
            if self.AutoCompActive():
                self.AutoCompCancel()
            self.handler('quit', evt)
    
    def decrback_autocomp(self, evt):
        if self.following_char.isalnum() and self.preceding_char == '.':
            pos = self.cur
            self.WordRight()
            self.cur = pos # backward selection to anchor point
        elif self.cur == self.bol:
            self.handler('quit', evt)
    
    def on_completion_forward(self, evt):
        self.on_completion(evt, 1)
    
    def on_completion_backward(self, evt):
        self.on_completion(evt, -1)
    
    @postcall
    def on_completion(self, evt, step=0):
        """Show completion with selection"""
        try:
            N = len(self.__comp_words)
            j = self.__comp_ind + step
            j = 0 if j < 0 else j if j < N else N-1
            word = self.__comp_words[j]
            n = len(self.__comp_hint)
            pos = self.cur
            self.ReplaceSelection(word[n:]) # 選択された範囲を変更する(または挿入する)
            self.cur = pos # backward selection to anchor point
            self.__comp_ind = j
        except IndexError:
            self.message("no completion words")
    
    def call_history_comp(self, evt):
        """Called when history-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            hint = self.cmdlc
            if hint.isspace() or self.bol != self.bolc:
                self.handler('quit', evt)
                self.indent_line()
                return
            
            hint = hint.strip()
            ls = [x.replace('\n', os.linesep + sys.ps2)
                    for x in self.history if x.startswith(hint)] # case-sensitive match
            words = sorted(set(ls), key=ls.index, reverse=0)     # keep order, no duplication
            
            self.__comp_ind = 0
            self.__comp_hint = hint
            self.__comp_words = words
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
            hint = re.search(r"[\w.]*$", self.cmdlc).group(0) # get the last word or ''
            
            ls = [x for x in self.fragmwords if x.startswith(hint)] # case-sensitive match
            words = sorted(ls, key=lambda s:s.upper())
            j = 0 if words else -1
            
            self.__comp_ind = j
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
            hint = re.search(r"[\w.]*$", self.cmdlc).group(0) # get the last word or ''
            
            m = re.match(r"from\s+([\w.]+)\s+import\s+(.*)", self.cmdlc)
            if m:
                text = m.group(1)
                modules = [x[len(text)+1:] for x in self.modules if x.startswith(text)]
                modules = [x for x in modules if x and '.' not in x]
            else:
                m = re.match(r"(import|from)\s+(.*)", self.cmdlc)
                if m:
                    if not hint:
                        return
                    text = '.'
                    modules = self.modules
                else:
                    text, sep, hint = get_words_hint(self.cmdlc)
                    obj = self.eval(text or 'self')
                    ## modules = [k for k,v in inspect.getmembers(obj, inspect.ismodule)]
                    modules = [k for k,v in vars(obj).items() if inspect.ismodule(v)]
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in modules if p.match(x)], key=lambda s:s.upper())
            
            j = next((k for k,w in enumerate(words) if P.match(w)),
                next((k for k,w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.gen_autocomp(len(hint), words)
            self.message("[module] {} candidates matched"
                         " with {!r} in {}".format(len(words), hint, text))
            
        except re.error as e:
            self.message("- re:miss compilation {!r} : {!r}".format(e, hint))
            
        except Exception as e:
            self.message("- {} : {!r}".format(e, text))
    
    def call_word_autocomp(self, evt):
        """Called when word-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            text, sep, hint = get_words_hint(self.cmdlc)
            obj = self.eval(text)
            
            if isinstance(obj, (bool,int,float,type(None))):
                self.handler('quit', evt)
                self.message("- Nothing to complete")
                return
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in Dir(obj) if p.match(x)], key=lambda s:s.upper())
            
            j = next((k for k,w in enumerate(words) if P.match(w)),
                next((k for k,w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.gen_autocomp(len(hint), words)
            self.message("[word] {} candidates matched"
                         " with {!r} in {}".format(len(words), hint, text))
            
        except re.error as e:
            self.message("- re:miss compilation {!r} : {!r}".format(e, hint))
            
        except Exception as e:
            self.message("- {} : {!r}".format(e, text))
    
    def call_apropos_autocomp(self, evt):
        """Called when apropos mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            text, sep, hint = get_words_hint(self.cmdlc)
            obj = self.eval(text)
            
            if isinstance(obj, (bool,int,float,type(None))):
                self.handler('quit', evt)
                self.message("- Nothing to complete")
                return
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in Dir(obj) if p.search(x)], key=lambda s:s.upper())
            
            j = next((k for k,w in enumerate(words) if P.match(w)),
                next((k for k,w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.gen_autocomp(len(hint), words)
            self.message("[apropos] {} candidates matched"
                         " with {!r} in {}".format(len(words), hint, text))
            
        except re.error as e:
            self.message("- re:miss compilation {!r} : {!r}".format(e, hint))
            
        except Exception as e:
            self.message("- {} : {!r}".format(e, text))


class Debugger(Pdb):
    """Graphical debugger of the phoenix, by the phoenix, for the phoenix
    
    + set_trace -> reset -> set_step -> sys.settrace
                   reset -> forget
    > user_line (user_call)
    > bp_commands
    > interaction -> setup -> execRcLines
      - print_stack_entry
      - cmd:cmdloop --> readline<module>
      - cmd:preloop
            line = cmd:precmd(line)
            stop = cmd:onecmd(line)
            stop = cmd:postcmd(stop, line)
    (Pdb)
            user_call => interaction
            user_return => interaction
            user_exception => interaction
      - cmd:postloop
    [EOF]
    """
    indent = "  "
    prefix1 = "> "
    prefix2 = "--> "
    verbose = False
    
    def __init__(self, parent, *args, **kwargs):
        Pdb.__init__(self, *args, **kwargs)
        
        self.prompt = self.indent + '(Pdb) ' # (overwrite)
        self.parent = parent
        self.logger = parent.Log
        self.viewer = None
        self.module = None
        self.namespace = {}
    
    def __del__(self):
        self.close()
    
    def message(self, msg, indent=-1, **kwargs):
        """(override) Add indent to msg"""
        prefix = self.indent if indent < 0 else ' ' * indent
        print(prefix + str(msg), file=self.stdout, **kwargs)
    
    def open(self, frame=None, verbose=False):
        self.verbose = verbose
        self.viewer = filling(target=self.namespace, label='locals')
        Pdb.set_trace(self, frame)
    
    def close(self):
        self.set_quit()
        if self.viewer:
            self.viewer.Close()
        self.viewer = None
        self.module = None
    
    def print_stack_entry(self, frame_lineno, prompt_prefix=None):
        """Print the stack entry frame_lineno (frame, lineno).
        (override) Change prompt_prefix
        """
        if not self.verbose:
            return
        if prompt_prefix is None:
            prompt_prefix = '\n' + self.indent + self.prefix2
        ## Pdb.print_stack_entry(self, frame_lineno, prompt_prefix)
        frame, lineno = frame_lineno
        if frame is self.curframe:
            prefix = self.indent + self.prefix1
        else:
            prefix = self.indent
        self.message(prefix +
            self.format_stack_entry(frame_lineno, prompt_prefix), indent=0)
    
    def set_break(self, filename, lineno, *args, **kwargs):
        self.logger.MarkerAdd(lineno-1, 1) # new breakpoint
        return Pdb.set_break(self, filename, lineno, *args, **kwargs)
    
    def set_quit(self):
        ## if self.verbose:
        ##     print("stacked frame")
        ##     for frame_lineno in self.stack:
        ##         self.message(self.format_stack_entry(frame_lineno))
        return Pdb.set_quit(self)
    
    ## Override Bdb methods
    
    def user_call(self, frame, argument_list):
        """--Call--"""
        print(frame)
        self.message("$(argument_list) = {!r}".format((argument_list)))
        Pdb.user_call(self, frame, argument_list)
    
    def user_line(self, frame):
        Pdb.user_line(self, frame)
    
    def user_return(self, frame, return_value):
        """--Return--"""
        self.message("$(return_value) = {!r}".format((return_value)))
        Pdb.user_return(self, frame, return_value)
    
    def user_exception(self, frame, exc_info):
        """--Exception--"""
        self.message("$(exc_info) = {!r}".format((exc_info)))
        Pdb.user_exception(self, frame, exc_info)
    
    def bp_commands(self, frame):
        """--Break--"""
        return Pdb.bp_commands(self, frame)
    
    def interaction(self, frame, traceback):
        Pdb.interaction(self, frame, traceback)
    
    def preloop(self):
        """Hook method executed once when the cmdloop() method is called.
        (override) output buffer to the logger (cf. pdb._print_lines)
        """
        frame = self.curframe
        module = inspect.getmodule(frame)
        if module:
            filename = frame.f_code.co_filename
            breaklist = self.get_file_breaks(filename)
            lines = linecache.getlines(filename, frame.f_globals)
            lc = frame.f_lineno # current line number
            lx = self.tb_lineno.get(frame) # exception
            
            ## Update logger (text and marker)
            if self.module is not module:
                self.logger.Text = ''.join(lines)
            
            for ln in breaklist:
                self.logger.MarkerAdd(ln-1, 1) # (B ) breakpoints
            if lx is not None:
                self.logger.MarkerAdd(lx-1, 2) # (>>) exception
            if 1:
                self.logger.MarkerDeleteAll(3)
                self.logger.MarkerAdd(lc-1, 3) # (->) pointer
            
            self.logger.goto_char(self.logger.PositionFromLine(lc-1))
            wx.CallAfter(self.logger.recenter)
            
            ## Update view of the namespace
            try:
                self.namespace.clear()
                self.namespace.update(frame.f_locals)
                tree = self.viewer.filling.tree
                tree.display()
                ## tree.Expand(tree.root)
            except RuntimeError:
                pass
        self.module = module
        Pdb.preloop(self)
    
    def postloop(self):
        """Hook method executed once when the cmdloop() method is about to return."""
        lineno = self.curframe.f_lineno
        self.logger.MarkerDeleteAll(0)
        self.logger.MarkerAdd(lineno-1, 0) # (=>) last pointer
        Pdb.postloop(self)
    
    ew.buildWxEventMap()
    ew.addModuleEvents(wx.aui)
    ew.addModuleEvents(wx.stc)
    
    @staticmethod
    def dump(wxobj):
        """Dump all event handlers bound to wxobj"""
        for event, actions in wxobj.__deb__handler__.items():
            name = ew._eventIdMap[event]
            print("  {}: {!r}".format(event, name))
            for act in actions:
                file = inspect.getsourcefile(act)
                lines = inspect.getsourcelines(act)
                print("{}{}:{}:{}".format(
                      ' '*9, file, lines[1], lines[0][0].rstrip()))


def _EvtHandler_Bind(self, event, handler=None, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
    """
    Bind an event to an event handler.
    (override) to return handler
    """
    assert isinstance(event, wx.PyEventBinder)
    if handler is None:
        return lambda f: _EvtHandler_Bind(self, event, f, source, id, id2)
    assert source is None or hasattr(source, 'GetId')
    if source is not None:
        id  = source.GetId()
    event.Bind(self, id, id2, handler)
    ## record all handlers: single state machine
    if not hasattr(self, '__deb__handler__'):
        self.__deb__handler__ = {}
    if event.typeId in self.__deb__handler__:
        self.__deb__handler__[event.typeId] += [handler]
    else:
        self.__deb__handler__[event.typeId] = [handler]
    return handler
core.EvtHandler.Bind = _EvtHandler_Bind


def _EvtHandler_Unbind(self, event, source=None, id=wx.ID_ANY, id2=wx.ID_ANY, handler=None):
    """
    Disconnects the event handler binding for event from `self`.
    Returns ``True`` if successful.
    (override) to remove handler
    """
    if source is not None:
        id  = source.GetId()
    ## remove the specified handler or all handlers
    if handler is None:
        self.__deb__handler__[event.typeId].clear()
    else:
        self.__deb__handler__[event.typeId].remove(handler)
    return event.Unbind(self, id, id2, handler)
core.EvtHandler.Unbind = _EvtHandler_Unbind


def deb(target=None, app=None, startup=None, **kwargs):
    """Dive into the process from your diving point
    for debug, break, and inspection of the target
    --- Put me at break-point.
    
    target : object or module. Default None sets target as __main__.
       app : an instance of App.
                Default None may create a local App and the mainloop.
                If app is given and not started the mainloop yet,
                the app will enter the mainloop herein.
   startup : called after started up (not before)
  **kwargs : Nautilus arguments
    locals : additional context (localvars:dict) to the shell
    execStartupScript : First, execute your script ($PYTHONSTARTUP:~/.py)

Note:
    PyNoAppError will be raised when the App is missing in process.
    When this may cause bad traceback, please restart.
    """
    if app is None:
        app = wx.GetApp() or wx.App()
    
    frame = ShellFrame(None, target, **kwargs)
    frame.Show()
    frame.shell.SetFocus()
    frame.Unbind(wx.EVT_CLOSE) # EVT_CLOSE surely close window
    if startup:
        try:
            startup(frame.shell)
            frame.shell.handler.bind("shell_cloned", startup)
        except Exception:
            traceback.print_exc()
            frame.shell.write(traceback.format_exc())
            frame.shell.prompt()
    
    if not isinstance(app, wx.App):
        print("- deb: argument app has unexpected type {!r}".format(typename(app)))
        pass
    elif not app.GetMainLoop():
        app.MainLoop()
    return frame


def watch(target=None, **kwargs):
    """Diver's watch to go deep into the wx process to inspect the target
    Wx.py tool for watching tree structure and events across the wx.Objects
    
  **kwargs : InspectionTool arguments
    pos, size, conifg, locals, and app
    """
    from wx.lib.inspection import InspectionTool
    if target:
        kwargs.update(locals=target.__dict__)
    it = InspectionTool()
    it.Init(**kwargs)
    it.Show(target)
    return it


def filling(target=None, label=None, **kwargs):
    """Wx.py tool for watching ingredients of the target
    """
    from wx.py.filling import FillingFrame
    frame = FillingFrame(rootObject=target,
                         rootLabel=label or typename(target),
                         static=False, # update each time pushed
                         **kwargs)
    frame.filling.text.WrapMode = 0
    frame.Show()
    return frame


if __name__ == '__main__':
    SHELLSTARTUP = """
if 1:
    self
    self.inspector
    root = self.inspector.shell
    """
    from scipy import constants as const
    np.set_printoptions(linewidth=256) # default 75
    
    app = wx.App()
    frm = Frame(None,
        title = repr(Frame),
        style = wx.DEFAULT_FRAME_STYLE, #&~(wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX),
        size=(200,80),
    )
    frm.editor = Editor(frm)
    
    frm.handler.debug = 0
    frm.editor.handler.debug = 0
    frm.inspector.handler.debug = 0
    frm.inspector.shell.handler.debug = 4
    frm.inspector.shell.Execute(SHELLSTARTUP)
    frm.inspector.shell.SetFocus()
    frm.inspector.shell.wrap(1)
    frm.inspector.Show()
    frm.Show()
    app.MainLoop()
