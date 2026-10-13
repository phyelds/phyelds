---
hide:
  - toc
---

# Playground

Write an aggregate program and run it here, in your browser. Python runs in
[Pyodide](https://pyodide.org): nothing is installed on your machine and your
code is not sent anywhere. The first run downloads Python, matplotlib and
phyelds (about 20 MB, a few seconds); after that, they come from the browser cache.

<div class="pg">
  <div class="pg-toolbar">
    <label for="pg-example">Example</label>
    <select id="pg-example"></select>
    <button id="pg-run" class="md-button md-button--primary" type="button">Run</button>
    <button id="pg-stop" class="md-button" type="button" disabled>Stop</button>
    <button id="pg-share" class="md-button" type="button">Share</button>
  </div>
  <p id="pg-summary" class="pg-summary"></p>
  <textarea id="pg-code" class="pg-code" spellcheck="false" autocapitalize="off" autocomplete="off" aria-label="Program"></textarea>
  <p id="pg-status" class="pg-status" role="status">Loading the examples…</p>
  <pre id="pg-console" class="pg-console" hidden></pre>
  <div id="pg-images" class="pg-images"></div>
</div>

<script src="playground.js"></script>

## How it works

- The program runs as a script, in an empty folder: what it prints appears under
  the editor, and so does every `.gif` or `.png` it saves. Save an animation with
  `RenderMode.SAVE` and a `.gif` name; figures left open are shown too.
- The [simulator](../simulator.md) and the [libraries](../concepts/libraries.md)
  work as on your machine, a few times slower: keep simulations small.
- **Stop** ends a program that runs too long; Python restarts at the next run.
- **Share** copies a link that opens the playground with your program.
