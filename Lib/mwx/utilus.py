#! python3
"""mwxlib core utilities.
"""
from contextlib import contextmanager
from functools import wraps
from bdb import BdbQuit
import traceback
import warnings
import time
import sys
import os
import re
import io
import tokenize
import fnmatch
import pkgutil
import pydoc
import inspect
from inspect import isclass, ismodule, ismethod, isbuiltin, isfunction
from pprint import pprint


@contextmanager
def ignore(*category):
    """Ignore warnings.
    
    It can be used as decorators as well as in with statements.
    cf. contextlib.suppress
    
    Note:
        ignore() does not ignore warnings.
        ignore(Warning) ignores all warnings.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category)
        yield


def warn(message, category=None, stacklevel=None):
    if stacklevel is None:
        frame = inspect.currentframe().f_back  # previous call stack frame
        skip = [frame.f_code.co_filename]
        stacklevel = 1
        while frame.f_code.co_filename in skip:
            frame = frame.f_back
            if not frame:
                break
            stacklevel += 1
    return warnings.warn(message, category, stacklevel+1)


def atom(v):
    ## Not a class, method, function, module, or any type (class, int, str, etc.).
    if (isclass(v) or ismethod(v) or isfunction(v) or isbuiltin(v)
            or ismodule(v) or isinstance(v, type)):
        return False
    ## Include the case where __name__ is manually defined for a class instance.
    return not hasattr(v, '__name__') or hasattr(v, '__class__')


def isobject(v):
    ## return atom(v) and hasattr(v, '__module__')
    return re.match(r"<([\w.]+) object at \w+>", repr(v))


def instance(*types):
    ## return lambda v: isinstance(v, types)
    def _pred(v):
        return isinstance(v, types)
    _pred.__name__ = "instance<{}>".format(','.join(p.__name__ for p in types))
    return _pred


def subclass(*types):
    ## return lambda v: issubclass(v, types)
    def _pred(v):
        return issubclass(v, types)
    _pred.__name__ = "subclass<{}>".format(','.join(p.__name__ for p in types))
    return _pred


def _Not(p):
    ## return lambda v: not p(v)
    def _pred(v):
        return not p(v)
    if isinstance(p, type):
        p = instance(p)
    _pred.__name__ = "not {}".format(p.__name__)
    return _pred


def _And(p, q):
    ## return lambda v: p(v) and q(v)
    def _pred(v):
        return p(v) and q(v)
    if isinstance(p, type):
        p = instance(p)
    if isinstance(q, type):
        q = instance(q)
    _pred.__name__ = "{} and {}".format(p.__name__, q.__name__)
    return _pred


def _Or(p, q):
    ## return lambda v: p(v) or q(v)
    def _pred(v):
        return p(v) or q(v)
    if isinstance(p, type):
        p = instance(p)
    if isinstance(q, type):
        q = instance(q)
    _pred.__name__ = "{} or {}".format(p.__name__, q.__name__)
    return _pred


def _Predicate(text, locals):
    tokens = [x for x in split_words(text.strip()) if not x.isspace()]
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


def apropos(obj, rexpr='', ignorecase=True, alias=None, pred=None, locals=None):
    """Prints a list of objects having expression rexpr in obj.
    """
    name = alias or typename(obj)
    
    if isinstance(pred, str):
        pred = _Predicate(pred, locals)
    
    if isinstance(pred, type):
        pred = instance(pred)
    
    if pred is not None:
        if not callable(pred):
            raise TypeError("{!r} is not callable".format(pred))
        try:
            pred(None)
        except (TypeError, ValueError):
            pass
    
    with ignore(DeprecationWarning):
        print("matching to {!r} in {} {} :{}".format(
              rexpr, name, type(obj), pred and pred.__name__))
        try:
            p = re.compile(rexpr, re.I if ignorecase else 0)
        except re.error as e:
            print("- re:miss compilation;", e)
        else:
            keys = sorted(filter(p.search, dir(obj)), key=lambda s: s.upper())
            n = 0
            for key in keys:
                try:
                    value = getattr(obj, key)
                    if pred and not pred(value):
                        continue
                    word = repr(value)
                    word = ' '.join(s.strip() for s in word.splitlines())
                    n += 1
                except Exception as e:
                    word = f"#<{e!r}>"
                if len(word) > 80:
                    word = word[:80] + '...'  # truncate words +3 ellipsis
                print("    {}.{:<36s} {}".format(name, key, word))
            if pred:
                print("found {} of {} words with :{}".format(n, len(keys), pred.__name__))
            else:
                print("found {} words.".format(len(keys)))


def typename(obj, docp=False, qualp=True):
    """Formatted object type name.
    """
    if not atom(obj):  # module, class, method, function, etc.
        if qualp:
            name = getattr(obj, '__qualname__', obj.__name__)
        else:
            name = obj.__name__
    elif hasattr(obj, '__class__'):  # class instance -> module.class
        name = obj.__class__.__name__
    else:
        return pydoc.describe(obj)  # atom -> short description
    
    modname = getattr(obj, '__module__', None)
    if modname:
        if qualp:
            name = modname + '.' + name
        else:
            if not modname.startswith(("__main__", "mwx")):
                name = modname + '..' + name
    
    if docp and callable(obj) and obj.__doc__:
        name += "<{!r}>".format(obj.__doc__.splitlines()[0])  # concat the first doc line
    return name


def where(obj):
    """Show @where (filename, lineno) the obj is defined
    """
    if inspect.isframe(obj):
        filename = obj.f_code.co_filename
        lineno = obj.f_lineno
        name = obj.f_code.co_name
        return "{}:{}:{}".format(filename, lineno, name)
    
    if inspect.iscode(obj):
        filename = obj.co_filename
        lineno = obj.co_firstlineno
        name = obj.co_name
        return "{}:{}:{}".format(filename, lineno, name)
    
    if inspect.istraceback(obj):
        filename = obj.tb_frame.f_code.co_filename
        lineno = obj.tb_lineno
        name = obj.tb_frame.f_code.co_name
        return "{}:{}:{}".format(filename, lineno, name)
    
    # if inspect.isbuiltin(obj):
    #     return None
    
    def _where(obj):
        obj = inspect.unwrap(obj)
        filename = inspect.getsourcefile(obj)
        src, lineno = inspect.getsourcelines(obj)
        name = src[0].rstrip()
        if not lineno:
            return filename
        return "{}:{}:{}".format(filename, lineno, name)
    
    try:
        try:
            return _where(obj)  # module, class, method, function, frame, or code
        except TypeError:
            return _where(obj.__class__)  # otherwise, class of the object
    except Exception:
        pass
    ## The source code cannot be retrieved.
    ## Try to get filename where the object is defined.
    try:
        try:
            return inspect.getfile(obj)  # compiled file?
        except TypeError:
            return inspect.getfile(obj.__class__)  # or a special class?
    except Exception:
        pass
    
    if hasattr(obj, '__module__'):
        return obj.__module__
    return None


def mro(obj):
    """Show @mro (method resolution order) of obj.
    
    Prints a list of filenames and lineno, or the module-names.
    """
    if not isinstance(obj, type):
        obj = type(obj)
    for base in obj.__mro__:
        print("  {:40s} {}".format(str(base), where(base)))


def pp(obj):
    pprint(obj, **pp.__dict__)


pp.indent = 1
pp.width = 80  # default 80
pp.depth = None
pp.compact = False
pp.sort_dicts = False


## --------------------------------
## Shell internal helper functions.
## --------------------------------

def split_words(text, reverse=False):
    """Generates words (python phrase) extracted from text.
    If reverse is True, process from tail to head.
    """
    tokens = list(split_tokens(text))
    if reverse:
        tokens = tokens[::-1]
    while tokens:
        words = []
        while 1:
            word = _extract_words_from_tokens(tokens, reverse)
            if not word:
                break
            words += word
        if words:
            yield ''.join(reversed(words) if reverse else words)
        if tokens:
            yield tokens.pop(0)  # sep-token


def split_parts(text, reverse=False):
    """Generates portions (words and parens) extracted from text.
    If reverse is True, process from tail to head.
    """
    tokens = list(split_tokens(text))
    if reverse:
        tokens = tokens[::-1]
    while tokens:
        words = _extract_words_from_tokens(tokens, reverse)
        if words:
            yield ''.join(reversed(words) if reverse else words)
        else:
            yield tokens.pop(0)  # sep-token


def split_tokens(text, comment=True):
    """Generates tokens extracted from text.
    If comment is True, generate comment tokens too.
    """
    try:
        fs = io.StringIO(text)
        tokens = tokenize.generate_tokens(fs.readline)
        j, k = 1, 0
        for type, string, start, end, line in tokens:
            l, m = start
            if type in (tokenize.INDENT, tokenize.DEDENT) or not string:
                ## Empty strings such as NEWLINE and ENDMARKER are also skipped.
                continue
            if type == tokenize.COMMENT and not comment:
                token = next(tokens)   # eats a trailing token
                string = token.string  # cr/lf or ''
                if m == 0:
                    continue  # line starting with a comment
            if l > j and m > 0:
                yield ' ' * m  # indent spaces
            elif m > k:
                yield ' ' * (m-k)  # white spaces
            j, k = end
            yield string
    except tokenize.TokenError:
        pass


def _extract_words_from_tokens(tokens, reverse=False):
    """Extracts pythonic expressions from tokens.
    
    Returns:
        A token list extracted including the parenthesis.
        If reverse is True, the order of the tokens will be reversed.
    """
    sep = "`@=+-/*%<>&|^~!?,:; \t\r\n#"
    p, q = "({[", ")}]"
    if reverse:
        p, q = q, p
    stack = []
    words = []
    for j, c in enumerate(tokens):
        if not c:
            continue
        if c in p:
            stack.append(c)
        elif c in q:
            if not stack:  # error("open-paren")
                break
            if c != q[p.index(stack.pop())]:  # error("mismatch-paren")
                break
        elif not stack and c[0] in sep:  # ok; starts with a char in sep
            break
        words.append(c)
        if not stack:  # ok
            j += 1  # to remove current token
            break
    else:
        # if stack: error("unclosed-paren")
        j = None
    del tokens[:j]  # remove extracted tokens (except the last one)
    return words


def walk_packages_no_import(path=None, prefix=''):
    """Yields module info recursively for all submodules on path.
    If path is None, yields all top-level modules on sys.path.
    """
    for info in pkgutil.iter_modules(path, prefix):
        yield info
        if info.ispkg:
            name = info.name.rpartition('.')[2]
            try:
                path = [os.path.join(info.module_finder.path, name)]
            except AttributeError:
                ## Actually, it doesn't get here.
                path = [os.path.join(info.module_finder.archive, name)]
            yield from walk_packages_no_import(path, info.name+'.')


def find_modules(force=False, verbose=True):
    """Find all modules available and write to log file.
    
    Similar to pydoc.help, it scans packages, but also submodules.
    This creates a log file in ~/.mwxlib and save the list.
    """
    fn = get_rootpath("deb-modules-{}.log".format(sys.winver))
    
    def _callback(path, modname, desc=''):
        if verbose:
            print("Scanning {:70s}".format(modname[:70]), end='\r')
        lm.append(modname)
    
    def _error(modname):
        if verbose:
            print("- Failed: {}".format(modname))
    
    if not force and os.path.exists(fn):
        with open(fn, 'r') as o:
            lm = eval(o.read())  # read and evaluate module list
        
        ## Check additional packages and modules.
        verbose = False
        for info in walk_packages_no_import(['.']):
            _callback('.', info.name)
    else:
        print(f"Please wait a moment while Py{sys.winver} gathers a list of "
               "all available modules... (This is executed once)")
        
        lm = list(sys.builtin_module_names)
        
        ## pydoc.ModuleScanner().run(_callback, key='', onerror=_error)
        
        ## Note: pkgutil.walk_packages must import all packages (not all modules!)
        ##       on the given path, in order to access the __path__ attribute.
        for info in pkgutil.walk_packages(onerror=_error):
            _callback(None, info.name)
        
        lm.sort(key=str.upper)
        with open(fn, 'w') as o:
            pprint(lm, stream=o)  # write module list
        print("The results were written in {!r}.".format(fn))
    return lm


def get_rootpath(fn):
    """Return pathname ~/.mwxlib/fn.
    If ~/.mwxlib/ does not exist, it will be created.
    """
    home = os.path.normpath(os.path.expanduser("~/.mwxlib"))
    if not os.path.exists(home):
        os.mkdir(home)
    return os.path.join(home, fn)


def fix_fnchars(filename, substr='_'):
    """Replace invalid filename characters with substr."""
    if os.name == 'nt':
        ## Replace Windows-invalid chars [:*?"<>|] with substr.
        ## Do not replace \\ or / to preserve folder structure.
        return re.sub(r'[:*?"<>|]', substr, filename)
    else:
        return filename


## --------------------------------
## Finite State Machine.
## --------------------------------

class SSM(dict):
    """Single State Machine/Context of FSM.
    """
    def __call__(self, event, *args, **kwargs):
        for act in self[event]:
            act(*args, **kwargs)

    def __repr__(self):
        return "<{} object at 0x{:X}>".format(self.__class__.__name__, id(self))

    def __str__(self):
        def _lstr(v):
            def _name(a):
                if callable(a):
                    return typename(a, docp=1, qualp=0)
                return repr(a)
            return ', '.join(_name(a) for a in v)
        return '\n'.join("{:>32} : {}".format(str(k), _lstr(v)) for k, v in self.items())

    def bind(self, event, action=None):
        """Append a transaction to the context."""
        assert callable(action) or action is None
        if event not in self:
            self[event] = []
        transaction = self[event]
        if action is None:
            return lambda f: self.bind(event, f)
        if action not in transaction:
            transaction.append(action)
        return action

    def unbind(self, event, action=None):
        """Remove a transaction from the context."""
        assert callable(action) or action is None
        if event not in self:
            return None
        transaction = self[event]
        if action is None:
            transaction.clear()
            return True
        if action in transaction:
            transaction.remove(action)
            return True
        return False


class FSM(dict):
    """Finite State Machine.
    
    Args:
        contexts: map of context <DNA>
            {state: {event: transaction (next_state, actions ...)}}
            
            * The state `None` is a wildcard (as executed any time).
            * An event (str) can include wildcards ``*?[]`` (fnmatch rule).
            * Actions must accept the same args as __call__.
    
    If no action, FSM carries out only a transition.
    The transition is always done before actions.
    
    To debug FSM handler, set ``debug`` switch as follows::
    
        [0] no trace, warnings only
        [1] trace when state transits
        [2] + when different event comes
        [3] + trace all events and actions
        [4] ++ all events (+ including state:None)
        [5] ++ all events (even if no actions + state:None)
        [8] +++ (max verbose level) to put all args and kwargs.
    
    Note:
        default=None is given as an argument to ``__init__``.
        If there is only one state, that state is used as the default.
    
    Note:
        There is no enter/exit event handler.
    """
    debug = 0

    default_state = None  # Used for define/undefine methods.

    current_state = property(lambda self: self.__state)
    previous_state = property(lambda self: self.__prev_state)

    current_event = property(lambda self: self.__event)
    previous_event = property(lambda self: self.__prev_event)

    @current_state.setter
    def current_state(self, state):
        self.__state = state
        self.__event = '*forced*'
        self.__debcall__(self.__event)

    def clear(self, state):
        """Reset current and previous states."""
        self.__state = state
        self.__prev_state = state
        self.__event = None
        self.__prev_event = None
        self.__matched_pattern = None

    def __init__(self, contexts=None, default=None):
        dict.__init__(self)  # update dict, however, it does not clear
        dict.clear(self)     # if and when __init__ is called, all contents are cleared
        if contexts is None:
            contexts = {}
        if default is None:  # if no default given, reset the first state as the default
            if self.default_state is None:
                default = next((k for k in contexts if k is not None), None)
        self.default_state = default
        self.clear(default)  # the first clear creates object localvars
        self.update(contexts)

    def __missing__(self, key):
        raise Exception("FSM logic-error: undefined state {!r}".format(key))

    def __repr__(self):
        return "<{} object at 0x{:X}>".format(self.__class__.__name__, id(self))

    def __str__(self):
        return '\n'.join("[ {!r} ]\n{!s}".format(k, v) for k, v in self.items())

    def __call__(self, event, *args, **kwargs):
        """Handle the event.
        
        First, call handlers with the state: None.
        Then call handlers with the current state.
        
        Returns:
            list or None depending on the handler
            
            - process the event (with actions) -> [retvals]
            - process the event (no actions) -> []
            - no event:transaction -> None
        """
        recept = False  # Is transaction performed?
        retvals = []  # retvals of actions
        self.__event = event
        if None in self:
            org = self.__state
            prev = self.__prev_state
            try:
                self.__state = None
                self.__prev_state = None
                ret = self.call(event, *args, **kwargs)  # None process
                if ret is not None:
                    recept = True
                    retvals += ret
            finally:
                if self.__state is None:  # restore original
                    self.__state = org
                    self.__prev_state = prev
        
        if self.__state is not None:
            ret = self.call(event, *args, **kwargs)  # normal process
            if ret is not None:
                recept = True
                retvals += ret
        
        ## Save the previous event for next handler debug call.
        self.__prev_event = self.__event
        self.__prev_state = self.__state
        if recept:
            return retvals

    def fork(self, event, *args, **kwargs):
        """Invoke the event handlers (internal use only).
        
        Similar to __call__, but ignore state: None.
        """
        self.__event = event
        ret = self.call(event, *args, **kwargs)
        self.__prev_event = self.__event
        return ret

    def call(self, event, *args, **kwargs):
        """Invoke the event handlers (internal use only).
        
        1. Transit the state.
        2. Try actions after transition.
        
        Returns:
            list or None depending on the handler
            
            - process the event (with actions) -> [retvals]
            - process the event (no actions) -> []
            - no event:transaction -> None
        """
        context = self[self.__state]
        if event in context:
            transaction = context[event]
            self.__prev_state = self.__state  # save previous state
            self.__state = transaction[0]     # the state transits here
            self.__debcall__(event, *args, **kwargs)  # check after transition
            retvals = []
            for act in transaction[1:]:
                ## Save the event before each action (for nested call).
                if self.__matched_pattern is None:
                    self.__event = event
                try:
                    ret = act(*args, **kwargs)  # call actions after transition
                    retvals.append(ret)
                except BdbQuit:
                    pass
                except Exception as e:
                    self.dump("- FSM exception: {!r}".format(e),
                              "  event  : {}".format(event),
                              "  from   : {}".format(self.__prev_state),
                              "  to     : {}".format(self.__state),
                              "  action : {}".format(typename(act)),
                              "  args   : {}".format(args),
                              "  kwargs : {}".format(kwargs),
                              "")
            self.__matched_pattern = None
            return retvals
        
        if isinstance(event, str):  # matching test using fnmatch
            for pat in context:
                if fnmatch.fnmatchcase(event, pat):
                    self.__matched_pattern = pat
                    return self.call(pat, *args, **kwargs)  # recursive call
        
        self.__debcall__(event, *args, **kwargs)  # check when no transition
        return None  # no event, no action

    def __debcall__(self, pattern, *args, **kwargs):
        v = self.debug
        if v and self.__state is not None:
            transaction = self[self.__prev_state].get(pattern) or []
            actions = ', '.join(typename(a, qualp=0) for a in transaction[1:])
            if (v > 0 and self.__prev_state != self.__state
             or v > 1 and self.__prev_event != self.__event
             or v > 2 and actions
             or v > 3):
                self.log("{c} {1} --> {2} [{0}] {a}".format(
                        self.__event, self.__prev_state, self.__state,
                        a='' if not actions else ('=> ' + actions),
                        c='*' if self.__prev_state != self.__state else ' '
                    ))
        elif v > 3:  # state is None
            transaction = self[None].get(pattern) or []
            actions = ', '.join(typename(a, qualp=0) for a in transaction[1:])
            if actions or v > 4:
                self.log("  None [{0}] {a}".format(
                        self.__event,
                        a='' if not actions else ('=> ' + actions)
                    ))
        if v > 7:  # max verbose level puts all args
            self.log("\t:", args, kwargs)

    @staticmethod
    def log(*args):
        print(*args, file=sys.__stdout__)

    @staticmethod
    def dump(*args):
        fn = get_rootpath("deb-dump.log")
        with open(fn, 'a') as o:
            print(time.strftime('!!! %Y/%m/%d %H:%M:%S'), file=o)
            print(*args, traceback.format_exc(), sep='\n', file=o)
        print(*args, traceback.format_exc(), sep='\n', file=sys.__stderr__)

    @staticmethod
    def duplicate(context):
        """Duplicate the transaction:list in the context.
        
        This method is used for the contexts given to :append and :update
        so that the original transaction (if they are lists) is not removed.
        """
        return {event: transaction[:] for event, transaction in context.items()}

    def validate(self, state):
        """Sort and move to end items with key which includes ``*?[]``."""
        context = self[state]
        ast = []
        bra = []
        for event in list(context):  # context mutates during iteration
            if re.search(r"\[.+\]", event):
                bra.append((event, context.pop(event)))  # event key has '[]'
            elif '*' in event or '?' in event:
                ast.append((event, context.pop(event)))  # event key has '*?'
        
        temp = sorted(context.items())  # normal event key
        context.clear()
        context.update(temp)
        context.update(sorted(bra, reverse=1))
        context.update(sorted(ast, reverse=1, key=lambda v: len(v[0])))

    def update(self, contexts):
        """Update each context or Add new contexts."""
        for k, v in contexts.items():
            if k in self:
                self[k].update(self.duplicate(v))
            else:
                self[k] = SSM(self.duplicate(v))  # new context
            self.validate(k)

    def append(self, contexts):
        """Append new contexts."""
        for k, v in contexts.items():
            if k in self:
                for event, transaction in v.items():
                    if event not in self[k]:
                        self[k][event] = transaction[:]  # copy the event:transaction
                        continue
                    for act in transaction[1:]:
                        self.bind(event, act, k, transaction[0])
            else:
                self[k] = SSM(self.duplicate(v))  # new context
            self.validate(k)

    def remove(self, contexts):
        """Remove old contexts."""
        for k, v in contexts.items():
            if k in self:
                for event, transaction in v.items():
                    if self[k].get(event) == transaction:
                        self[k].pop(event)  # remove the event:transaction
                        continue
                    for act in transaction[1:]:
                        self.unbind(event, act, k)
        ## Cleanup.
        for k, v in list(self.items()):  # self mutates during iteration
            if not v:
                del self[k]

    def bind(self, event, action=None, state=None, state2=None):
        """Append a transaction to the context.
        
        equiv. self[state] += {event : [state2, action]}
        
        The transaction is expected to be a list (not a tuple).
        If no action, it creates only the transition and returns @decor(binder).
        """
        assert isinstance(event, str)
        assert callable(action) or action is None
        
        if state not in self:
            warn(f"- FSM [{state!r}] context newly created.")
            self[state] = SSM()  # new context
        
        if state2 is None:
            state2 = state
        
        context = self[state]
        if event in context:
            if state2 != context[event][0]:
                warn(f"- FSM transaction may conflict ({event!r} : {state!r} --> {state2!r}).\n"
                     f"  The state {state2!r} is different from the original state.")
                pass
                context[event][0] = state2  # update transition
        else:
            if state2 not in self:
                warn(f"- FSM transaction may contradict ({event!r} : {state!r} --> {state2!r}).\n"
                     f"  The state {state2!r} is not found in the contexts.")
                pass
            context[event] = [state2]  # new event:transaction
        
        transaction = context[event]
        if action is None:
            return lambda f: self.bind(event, f, state, state2)
        
        if action in transaction:
            warn(f"- FSM duplicate transaction ({state!r} : {event!r}).")
        else:
            try:
                transaction.append(action)
            except AttributeError:
                warn(f"- FSM cannot append new transaction ({state!r} : {event!r}).\n"
                     f"  The transaction must be a list, not a tuple.")
        return action

    def unbind(self, event, action=None, state=None):
        """Remove a transaction from the context.
        
        equiv. self[state] -= {event : [?, action]}
        
        The transaction is expected to be a list (not a tuple).
        If no action, it will remove the transaction from the context.
        """
        assert callable(action) or action is None
        
        if state not in self:
            warn(f"- FSM [{state!r}] context does not exist.")
            return
        
        context = self[state]
        if event not in context:
            warn(f"- FSM has no such transaction ({state!r} : {event!r}).")
            return
        
        transaction = context[event]
        if action is None:
            for act in transaction[1:]:
                self.unbind(event, act, state)
            return True
        
        if action in transaction:
            try:
                transaction.remove(action)
                return True
            except AttributeError:
                warn(f"- FSM removing action from context ({state!r} : {event!r}).\n"
                     f"  The transaction must be a list, not a tuple")
        return False

    def binds(self, event, action=None, state=None, state2=None):
        """Append a one-time transaction to the context.
        
        Like `bind`, but unbinds itself after being called once.
        """
        if action is None:
            return lambda f: self.binds(event, f, state, state2)
        
        @wraps(action)
        def _act(*v, **kw):
            try:
                return action(*v, **kw)
            finally:
                self.unbind(event, _act, state)
        return self.bind(event, _act, state, state2)

    def define(self, event, action=None, /, *args, **kwargs):
        """Define event action.
        
        Note:
            The funcall kwargs `doc` and `alias` are reserved as kw-only-args.
        """
        state = self.default_state
        if action is None:
            self[state].pop(event, None)  # cf. undefine
            return lambda f: self.define(event, f, *args, **kwargs)
        
        f = funcall(action, *args, **kwargs)
        self.update({state: {event: [state, f]}})
        return action

    def undefine(self, event):
        """Delete event context."""
        self.define(event, None)


class TreeList:
    """Interface class for tree list control.
    
    >>> list[item:(key,value)]
        [[key, [item,
                item, ...]],
         [key, [item,
                branch => [key, [item,
                                 item, ...]],
                ...]],
        ]
    """
    def __init__(self, ls=None):
        self.__items = ls or []

    def __call__(self, k):
        return TreeList(self[k])

    def __len__(self):
        return len(self.__items)

    def __contains__(self, k):
        return self._getf(self.__items, k)

    def __iter__(self):
        return self.__items.__iter__()

    def __getitem__(self, k):
        if isinstance(k, str):
            return self._getf(self.__items, k)
        return self.__items.__getitem__(k)

    def __setitem__(self, k, v):
        if isinstance(k, str):
            return self._setf(self.__items, k, v)
        return self.__items.__setitem__(k, v)

    def __delitem__(self, k):
        if isinstance(k, str):
            return self._delf(self.__items, k)
        return self.__items.__delitem__(k)

    def _find_item(self, ls, key):
        for x in ls:
            if isinstance(x, (tuple, list)) and x and x[0] == key:
                if len(x) < 2:
                    raise ValueError(f"No value for {key=!r}")
                return x

    def _getf(self, ls, key):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self._getf(ls, a)
            if la is not None:
                return self._getf(la, b)
            return None
        li = self._find_item(ls, key)
        if li is not None:
            return li[-1]

    def _setf(self, ls, key, value):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self._getf(ls, a)
            if la is not None:
                return self._setf(la, b, value)
            p, key = key.rsplit('/', 1)
            return self._setf(ls, p, [[key, value]])  # ls[p].append([key, value])
        try:
            li = self._find_item(ls, key)
            if li is not None:
                try:
                    li[-1] = value  # assign value to item (ls must be a list)
                except TypeError:
                    li[-1][:] = value  # assign value to items:list
            else:
                ls.append([key, value])  # append to items:list
        except (ValueError, TypeError, AttributeError) as e:
            warn(f"- TreeList {e!r}: {key=!r}")

    def _delf(self, ls, key):
        if '/' in key:
            p, key = key.rsplit('/', 1)
            ls = self._getf(ls, p)
        ls.remove(next(x for x in ls if x and x[0] == key))


def get_fullargspec(f):
    """Get the names and default values of a callable object's parameters.
    If the object is a built-in function, it tries to get argument
    information from the docstring. If it fails, it returns None.
    
    Returns:
        args:           a list of the parameter names.
        varargs:        the name of the  * parameter or None.
        varkwargs:      the name of the ** parameter or None.
        defaults:       a dict mapping names from args to defaults.
        kwonlyargs:     a list of keyword-only parameter names.
        kwonlydefaults: a dict mapping names from kwonlyargs to defaults.
    
    Note:
        `self` parameter is not reported for bound methods.
    
    cf. inspect.getfullargspec
    """
    argv = []           # <before /> 0:POSITIONAL_ONLY
                        # <before *> 1:POSITIONAL_OR_KEYWORD
    varargs = None      # <*args>    2:VAR_POSITIONAL
    varkwargs = None    # <**kwargs> 4:VAR_KEYWORD
    defaults = {}       # 
    kwonlyargs = []     # <after *>  3:KEYWORD_ONLY
    kwonlydefaults = {}
    try:
        sig = inspect.signature(f)
        for k, v in sig.parameters.items():
            if v.kind in (v.POSITIONAL_ONLY, v.POSITIONAL_OR_KEYWORD):
                argv.append(k)
                if v.default != v.empty:
                    defaults[k] = v.default
            elif v.kind == v.VAR_POSITIONAL:
                varargs = k
            elif v.kind == v.KEYWORD_ONLY:
                kwonlyargs.append(k)
                if v.default != v.empty:
                    kwonlydefaults[k] = v.default
            elif v.kind == v.VAR_KEYWORD:
                varkwargs = k
    except ValueError:
        ## Builtin functions don't have an argspec that we can get.
        ## Try alalyzing the doc:str to get argspec info.
        ## 
        ## Wx builtin method doc is written in the following style:
        ## ```name(argspec) -> retval
        ## 
        ## ...(details)...
        ## ```
        doc = inspect.getdoc(f)
        for word in split_parts(doc or ''):  # Search pattern for `func(argspec)`.
            if word.startswith('('):
                argspec = word[1:-1]
                break
        else:
            return None  # no argument spec information
        if argspec:
            argparts = ['']
            for part in split_parts(argspec):  # Separate argument parts with commas.
                if not part.strip():
                    continue
                if part != ',':
                    argparts[-1] += part
                else:
                    argparts.append('')
            for v in argparts:
                m = re.match(r"(\w+):?", v)  # argv + kwonlyargs
                if m:
                    argv.append(m.group(1))
                    m = re.match(r"(\w+)(?::\w+)?=(.+)", v)  # defaults + kwonlydefaults
                    if m:
                        defaults.update([m.groups()])
                elif v.startswith('**'):  # <**kwargs>
                    varkwargs = v[2:]
                elif v.startswith('*'):  # <*args>
                    varargs = v[1:]
    return (argv, varargs, varkwargs,
            defaults, kwonlyargs, kwonlydefaults)


def funcall(f, *args, doc=None, alias=None, **kwargs):
    """Decorator of event handler.
    
    Check if the event argument can be omitted and if any other
    required arguments are specified in args and kwargs.
    
    Returns:
        lambda: Decorated function f as `alias<doc>`
        
        >>> Act1 = lambda *v,**kw: f(*(v+args), **(kwargs|kw))
        >>> Act2 = lambda *v,**kw: f(*args, **(kwargs|kw))
        
        `Act1` is returned (accepts event arguments) if event arguments
        cannot be omitted or if there are any remaining arguments
        that must be explicitly specified.
        Otherwise, `Act2` is returned (ignores event arguments).
    """
    assert callable(f)
    assert isinstance(doc, (str, type(None)))
    assert isinstance(alias, (str, type(None)))
    
    @wraps(f)
    def _Act(*v, **kw):
        kwargs.update(kw)
        return f(*v, *args, **kwargs)  # function with event args
    
    @wraps(f)
    def _Act2(*v, **kw):
        kwargs.update(kw)
        return f(*args, **kwargs)  # function with no explicit args
    
    action = _Act
    try:
        (argv, varargs, varkwargs, defaults,
            kwonlyargs, kwonlydefaults) = get_fullargspec(f)
    except Exception:
        warn(f"Failed to get the signature of {f}.")
        return f
    if not varargs:
        N = len(argv)
        i = len(args)
        assert i <= N, "too many args"
        ## Check remaining arguments that need to be specified explicitly.
        rest = set(argv[i:]) - set(defaults) - set(kwargs)
        if not rest:
            action = _Act2
    if alias:
        action.__name__ = str(alias)
    if doc:
        action.__doc__ = doc
    return action
