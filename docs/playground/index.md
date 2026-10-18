# Playground

Write an aggregate program and watch it run on a network, in 3D, in your browser.
Python runs in [Pyodide](https://pyodide.org): nothing is installed on your machine
and your code is not sent anywhere.

[Open the playground](app.html){ .md-button .md-button--primary }

## How it works

- The editor holds a Python module: every device runs its last `@aggregate`
  function, once per round. The playground owns the network: how many devices
  there are, where they are, and what they sense.
- The editor completes names as you type, or on Ctrl+Space: the modules and functions
  of phyelds, your own names, and what comes after a dot, such as the methods of
  `neighbors(1).`.
- Select an expression and press **Watch** (Ctrl+Shift+Enter): its value on every
  device appears as a layer stacked under the result, which stays on top. Watching
  does not start the devices over; the arrows of a watch move it up or down the
  stack, and × removes it.
- The layer in front, which you pick in the list, chooses its colour map (plasma,
  viridis, diverging, or categories for ids) and how high its values rise, down to flat.
- The eye of a layer hides it from the stack. **One at a time** (S) shows only the layer
  in front, and ↑ and ↓ move through the stack. **2D** shows the layer in front from
  above, flat.
- Every `sense("name")` of the program becomes a switch on the selected device.
- Drag a device, in 3D or on the map, to move it. The sliders choose how many
  devices there are, from two to a hundred, and how far they hear; the devices
  that stay keep their state. The rounds run at the speed you pick, and the bar
  under the network says when a whole round changed nothing: the program is stable.
- **Run** (Ctrl+Enter) applies the code and starts every device over;
  **Stop** ends a program that never returns.
- **Share** copies a link that opens the playground with your program, its watches
  and how you were looking at them.
