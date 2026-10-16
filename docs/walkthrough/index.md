---
hide:
  - toc
---

# Interactive 3D Walkthrough: Building a Field Step by Step

Explore how **aggregate computing** works by building a **self-healing channel** from the ground up.
Step through the 6 stages below, rotate the **3D stacked fields** with your mouse, step round-by-round (or run continuously), and click nodes on the network to move the **Source**, **Target**, or **Obstacles** in real time.

<div class="wt-container">
  <!-- Stepper bar -->
  <div class="wt-steps" role="tablist" aria-label="Walkthrough steps">
    <button class="wt-step-btn active" data-step="0" type="button">
      <span class="wt-step-num">1</span>
      <span class="wt-step-label">Sensors &amp; Fields</span>
    </button>
    <button class="wt-step-btn" data-step="1" type="button">
      <span class="wt-step-num">2</span>
      <span class="wt-step-label">Space (<code>neighbors</code>)</span>
    </button>
    <button class="wt-step-btn" data-step="2" type="button">
      <span class="wt-step-num">3</span>
      <span class="wt-step-label">Time + Space (Gradient)</span>
    </button>
    <button class="wt-step-btn" data-step="3" type="button">
      <span class="wt-step-num">4</span>
      <span class="wt-step-label">Collect (Shortest Path)</span>
    </button>
    <button class="wt-step-btn" data-step="4" type="button">
      <span class="wt-step-num">5</span>
      <span class="wt-step-label">Compose (Channel)</span>
    </button>
    <button class="wt-step-btn" data-step="5" type="button">
      <span class="wt-step-num">6</span>
      <span class="wt-step-label">Branch (<code>if / else</code> Split)</span>
    </button>
  </div>

  <!-- Main two-column workspace -->
  <div class="wt-workspace">
    <!-- Left: 3D Viewport + Controls -->
    <div class="wt-stage">
      <div class="wt-toolbar">
        <div class="wt-toolbar-group">
          <button id="wt-play" class="md-button md-button--primary wt-btn" type="button">Pause</button>
          <button id="wt-step-round" class="md-button wt-btn" type="button">+1 Round</button>
          <button id="wt-reset" class="md-button wt-btn" type="button">Reset State</button>
          <span id="wt-round-badge" class="wt-badge">Round 0</span>
        </div>
        <div class="wt-toolbar-group">
          <label class="wt-control-label" for="wt-view-mode">3D Mode</label>
          <select id="wt-view-mode" class="wt-select">
            <option value="stacked">Stacked Layers (3D)</option>
            <option value="surface">3D Height Surface</option>
          </select>
          <label class="wt-control-label" for="wt-width-slider" id="wt-width-wrap">
            Width: <span id="wt-width-val">1.6</span>
          </label>
          <input id="wt-width-slider" type="range" min="0.8" max="3.2" step="0.2" value="1.6" class="wt-slider" />
        </div>
      </div>

      <div class="wt-canvas-wrap">
        <canvas id="wt-canvas" width="760" height="500" aria-label="Interactive 3D computational field visualization"></canvas>
        <div class="wt-canvas-hint">
          <span><strong>Drag</strong>: rotate 3D</span>
          <span><strong>Click node</strong>: set Source / Target / Obstacle</span>
          <span><strong>Hover node</strong>: inspect local state &amp; neighbors</span>
        </div>
        <div class="wt-click-mode">
          <span>Click node sets:</span>
          <button class="wt-mode-pill active" data-click="source" type="button">Source</button>
          <button class="wt-mode-pill" data-click="target" type="button">Target</button>
          <button class="wt-mode-pill" data-click="obstacle" type="button">Obstacle (on/off)</button>
        </div>
      </div>

      <!-- Layer legend / toggles -->
      <div id="wt-layers-bar" class="wt-layers-bar"></div>
    </div>

    <!-- Right: Narrative, Live Python Code, and Node Inspector -->
    <div class="wt-sidebar">
      <div class="wt-card">
        <div class="wt-card-kicker" id="wt-step-kicker">Step 1 of 6</div>
        <h2 class="wt-card-title" id="wt-step-title">What is a Computational Field?</h2>
        <div class="wt-card-body" id="wt-step-desc"></div>
        <div class="wt-nav-btns">
          <button id="wt-prev-step" class="md-button wt-btn" type="button">← Previous</button>
          <button id="wt-next-step" class="md-button md-button--primary wt-btn" type="button">Next Step →</button>
        </div>
      </div>

      <div class="wt-card">
        <div class="wt-card-header">
          <span>Python Aggregate Program (runs on every node)</span>
        </div>
        <pre class="wt-code-block"><code id="wt-code-display"></code></pre>
      </div>

      <div class="wt-card wt-inspector">
        <div class="wt-card-header">
          <span>Local Device Inspector</span>
          <span id="wt-insp-id" class="wt-badge">Hover or click a node</span>
        </div>
        <div id="wt-insp-body" class="wt-insp-body">
          Hover over any device in the 3D view to inspect its local sensors, its <code>remember</code> state, its <code>neighbors(...)</code> field, and its alignment path across all stacked layers.
        </div>
      </div>
    </div>
  </div>
</div>

<script src="walkthrough.js"></script>
