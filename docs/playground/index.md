# Playground

Write an aggregate program and watch it run on a network, in 3D, in your browser.
Python runs in [Pyodide](https://pyodide.org): nothing is installed on your machine
and your code is not sent anywhere.

[Open the playground](app.html){ .md-button .md-button--primary }

## How it works

- **Example** opens one of the examples, group by group, from the basics to swarms
  that move. Its search finds them by title, by summary, or by the functions they
  import, such as `gossip` or `sink_at`.
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
  in front, and ↑ and ↓ move through the stack; Shift+↑ and Shift+↓ move the watch in
  front up and down it. **2D** shows the layer in front from above, flat.
- Every `sense("name")` or `Sensor("name")` of the program becomes a switch on the
  selected device.
- Drag a device, in 3D or on the map, to move it. The sliders choose how many
  devices there are, from two to a hundred, and how far they hear at first; the
  devices that stay keep their state. Then the range of every device
  [adapts](../simulator.md#ranges-that-adapt) to keep about eight neighbours, as a
  swarm that gathers or scatters needs, and two devices hear each other when each is
  in range of the other. The rounds run at the speed you pick, and the bar
  under the network says when a whole round changed nothing: the program is stable.
- A program that sends a velocity (`velocity.send(v)`, from
  `phyelds.libraries.device`) moves its devices smoothly, at a top speed, in a world
  twice as wide as the arena, which the views then show from above; a velocity it
  returns is drawn as an arrow. The [swarm behaviours](../experimental/swarm.md) are
  ready to use. **Restart** (R) puts the devices back where you placed them.
- A line that ends with `# watch` is watched when the program runs, and `# watch name`
  watches that name of the line. A shape the program defines at the top of its module
  is drawn under the result, as the ground a swarm takes.
- **Run** (Ctrl+Enter) applies the code and starts every device over;
  **Stop** ends a program that never returns.
- **Share** copies a link that opens the playground with your program, its watches
  and how you were looking at them.
