# key bindings

キー割り当て一覧

    global-map : (0 :default)
     ctl-x-map : 'C-x' ... extention map for the frame
      spec-map : 'C-c' ... spefific map for the editors and the shell
       esc-map : 'escape'


## Shell

Global bindings: 

	>>> self.shellframe.handler @p


## Nautilus

Modes:

     -- : [0] global-map
    TAB : [1] history-comp-mode
    M-. : [2] word-comp-mode
    M-/ : [3] apropos-comp-mode
    M-, : [4] text-comp-mode
    M-m : [5] module-comp-mode

Global bindings:

    >>> self.handler @p
