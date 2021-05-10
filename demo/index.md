# Demo Script and Gallery


## FSM


Though the idea of the Finite State Machine (FSM) is truly fundamental, is the most important framework of mwxlib. The catalogue of programming techniques that are simplified by FSM is astonishing: the key&mouse-event binder, inter-object communication, notify handler, thread-sentinel, and much more.

Check how the FSM works by running the test code:
[test-script](./test_fsm.py).


## mwx.Frame

The simplest frame, which consits of 
- simple menubar
- simple statusbar
- simple shell

[test-script](./test_frame.py)
![screenshot](./image/test_frame.png)


## mwx.Button

- The button is based on <wx.lib.platebtn>
- The panel is based on <wx.lib.scrolledpanel>, and extended to be foldable. (try it!)

[demo-script](./demo-buttons.py)
![screenshot (folded)](./image/demo-buttons(folded).png)
![screenshot (expanded)](./image/demo-buttons(expanded).png)


## mwx.menubar

The mwx.menubar is described as structured list.
Designed as WYSiWYG (see demo-code).

[demo-script](./demo-menu.py)
![screenshot](./image/demo-menubar.png)


## mwx.controls

The mwx.controls including,
- Knob
    - Param
    - LParam (linear version of Param)
- Button
- ToggleButton
- TextCtrl (text and button complex)
- Choice (text and combobox complex)

Those wx controls (not only shown above) are laid out by only one method `layout` of mwx.ControlPanel<wx.lib.scrolled.ScrolledPanel> as WYSiWYG (see demo-code).

[demo-script](./demo-widgets.py)
![screenshot](./image/demo-widgets.png)


## mwx.graphman.Layer

The graphman is a graphic window manager.
- Thread
- Layer (base of Plugins)
- Graph (matplotlib panel)
- Frame
    - two window matplotlib graphic window
    - stack frames
    - layer manager (load/unlodad/edit/inspect)
    - image loader (PIL)
    - index loader
    - session loader

[template-script](./template.py)
![screenshot](./image/template-layer.png)
