# Playground

Write an aggregate program and watch it run on a network, in 3D, in your browser.
Python runs in [Pyodide](https://pyodide.org): nothing is installed on your machine
and your code is not sent anywhere.

[Open the playground](app.html){ .md-button .md-button--primary }

## How it works

- The editor holds a Python module: every device runs its last `@aggregate`
  function, once per round. The playground owns the network: how many devices
  there are, where they are, and what they sense.
- Select an expression and press **Watch** (Ctrl+Shift+Enter): its value on every
  device appears as a layer stacked above the result. Watching does not start the
  devices over, and each layer can be removed again.
- Every `sense("name")` of the program becomes a switch on the selected device.
- **Run** (Ctrl+Enter) applies the code and starts every device over;
  **Stop** ends a program that never returns.
- **Share** copies a link that opens the playground with your program.
