/*
 * Full-Viewport Interactive 3D Field Walkthrough for Phyelds.
 * Renders stacked computational fields (Sense -> Neighbors -> Gradient ->
 * Collect -> Channel -> Branching) with high-DPI 3D projection, zoom, and
 * configurable vertical layer separation.
 */
(function () {
  "use strict";

  const canvas = document.getElementById("wt-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const stageEl = document.getElementById("wt-stage") || canvas.parentElement;

  const GRID = 6;
  const NUM_NODES = GRID * GRID;
  const COMM_RADIUS = 1.65;
  const INF = 999;

  const STEPS = [
    {
      kicker: "Step 1 of 6 — Local Sensors",
      title: "What is a Computational Field?",
      desc:
        "<p>A <strong>computational field</strong> assigns a value to every device in the network at every moment in time.</p>" +
        "<p>Here, 36 devices sit on a 2D physical network. Every device runs the exact same Python function and reads its local sensors (<code>sense('source')</code> and <code>sense('target')</code>). Without neighbor communication, each device only knows its own local reading.</p>" +
        "<p><strong>Try it:</strong> Click any node to move the <span class='wt-dot wt-dot--source'></span><strong>Source</strong>, switch the bottom-left mode to move the <span class='wt-dot wt-dot--target'></span><strong>Target</strong>, or toggle <strong>Obstacles</strong>.</p>",
      code:
        "from phyelds.calculus import aggregate\n" +
        "from phyelds.libraries.device import sense\n\n" +
        "@aggregate\n" +
        "def sensor_field() -> str:\n" +
        "    if sense(\"source\"):\n" +
        "        return \"SOURCE\"\n" +
        "    if sense(\"target\"):\n" +
        "        return \"TARGET\"\n" +
        "    return \"IDLE\"",
      layers: [
        { id: "sensors", name: "Layer 0: Local Sensors (sense)", color: "#f59e0b" },
      ],
    },
    {
      kicker: "Step 2 of 6 — Space Only (1-Hop)",
      title: "Perceiving Immediate Neighbors",
      desc:
        "<p><code>neighbors(value)</code> is the spatial primitive: each device shares <code>value</code> with devices within communication range and receives their values back as a <code>NeighborhoodField</code>.</p>" +
        "<p>Above the physical network (Layer 0), <strong>Layer 1</strong> shows how many active neighbors each device hears: <code>len(neighbors(1).exclude_self())</code>. Boundary nodes and nodes adjacent to obstacles have fewer neighbors and lower elevation.</p>" +
        "<p><strong>Try it:</strong> Hover over any node to highlight its 1-hop <code>NeighborhoodField</code> in yellow, or toggle an <strong>Obstacle</strong> to see its neighbors adapt on the next round.</p>",
      code:
        "from phyelds.calculus import aggregate, neighbors\n\n" +
        "@aggregate\n" +
        "def neighbor_count() -> int:\n" +
        "    # Share 1 with neighbors; count who we hear (excluding self)\n" +
        "    field = neighbors(1)\n" +
        "    return len(field.exclude_self())",
      layers: [
        { id: "sensors", name: "Layer 0: Physical Network", color: "#94a3b8" },
        { id: "degree", name: "Layer 1: neighbors(1) count", color: "#f97316" },
      ],
    },
    {
      kicker: "Step 3 of 6 — Space + Time (Spreading G)",
      title: "The Gradient: Propagating Across the Network",
      desc:
        "<p>Combining local state across rounds (<code>remember</code>) with neighbor exchange (<code>neighbors</code>) lets information travel across the entire network.</p>" +
        "<p><code>distance_to(sense('target'))</code> computes a <strong>gradient</strong>: a 3D funnel sloping down toward the Target. Click <strong>Reset State</strong> and then <strong>+1 Round</strong> repeatedly to watch the wave expand one hop per round!</p>" +
        "<p><strong>Try it:</strong> Switch <strong>View</strong> to <em>3D Height Surface</em> or place a wall of <strong>Obstacles</strong>—the gradient self-heals around obstacles automatically.</p>",
      code:
        "from phyelds.calculus import aggregate\n" +
        "from phyelds.libraries.device import sense\n" +
        "from phyelds.libraries.distances import neighbors_distances\n" +
        "from phyelds.libraries.spreading import distance_to\n\n" +
        "@aggregate\n" +
        "def to_target() -> float:\n" +
        "    # G block: shortest metric distance to the target\n" +
        "    return distance_to(sense(\"target\"), neighbors_distances())",
      layers: [
        { id: "sensors", name: "Layer 0: Network & Obstacles", color: "#94a3b8" },
        { id: "grad_target", name: "Layer 1 (G): distance_to(target)", color: "#ec4899" },
      ],
    },
    {
      kicker: "Step 4 of 6 — Inward Flow (Collection C)",
      title: "Collecting Along a Gradient: Shortest Path",
      desc:
        "<p>Once Layer 1 forms a gradient potential toward the Target, we can flow data <strong>downhill</strong> along that potential using <code>collect_or(to_target, sense('source'))</code>.</p>" +
        "<p>In 3D you now see <strong>two stacked functions</strong>: Layer 1 (below) is the distance potential <code>to_target</code>, and Layer 2 (above) is the boolean field <code>on_path</code> that lights up every device along the shortest path from Source to Target.</p>" +
        "<p><strong>Try it:</strong> Drag the <strong>Layer Gap</strong> slider to separate the planes and see how each node on Layer 2 follows the parent pointers of Layer 1 below it.</p>",
      code:
        "@aggregate\n" +
        "def shortest_path() -> bool:\n" +
        "    distances = neighbors_distances()\n" +
        "    # Layer 1 (G): potential field sloping down to target\n" +
        "    to_target = distance_to(sense(\"target\"), distances)\n" +
        "    # Layer 2 (C): flow True from source downhill to target\n" +
        "    on_path = collect_or(to_target, sense(\"source\"))\n" +
        "    return on_path",
      layers: [
        { id: "grad_target", name: "Layer 1 (G): to_target potential", color: "#ec4899" },
        { id: "on_path", name: "Layer 2 (C): collect_or(to_target, source)", color: "#f59e0b" },
      ],
    },
    {
      kicker: "Step 5 of 6 — Functional Composition (G → C → G)",
      title: "Composing Three Fields into a Channel",
      desc:
        "<p>In aggregate computing, the field returned by one function is passed directly as the input to the next. Feeding <code>on_path</code> (Layer 2) as the source of a second gradient <code>distance_to(on_path, distances) &lt;= width</code> (Layer 3) dilates the path into a fault-tolerant <strong>Channel</strong> corridor.</p>" +
        "<p>Vertical alignment fibres connect every device across <strong>Layer 1 → Layer 2 → Layer 3</strong>, showing how three simple field functions stack into a self-healing collective behavior.</p>" +
        "<p><strong>Try it:</strong> Drag the <strong>Channel Width</strong> slider at the top of the 3D stage to widen or narrow the corridor live.</p>",
      code:
        "@aggregate\n" +
        "def channel(width: float = 1.6) -> bool:\n" +
        "    distances = neighbors_distances()\n" +
        "    # Layer 1 (G): distance to target\n" +
        "    to_target = distance_to(sense(\"target\"), distances)\n" +
        "    # Layer 2 (C): shortest path from source to target\n" +
        "    on_path = collect_or(to_target, sense(\"source\"))\n" +
        "    # Layer 3 (G): dilate path into a corridor of radius `width`\n" +
        "    return distance_to(on_path, distances) <= width",
      layers: [
        { id: "grad_target", name: "Layer 1 (G): distance_to(target)", color: "#ec4899" },
        { id: "on_path", name: "Layer 2 (C): collect_or (path)", color: "#f59e0b" },
        { id: "channel", name: "Layer 3 (G): distance_to(on_path) <= width", color: "#10b981" },
      ],
    },
    {
      kicker: "Step 6 of 6 — Branching & Alignment (if / else)",
      title: "Splitting Space into Isolated Domains",
      desc:
        "<p>What happens when we write <code>if in_channel: ... else: ...</code> inside an <code>@aggregate</code> function? Phyelds rewrites the AST so the <code>True</code> branch (<code>align_left</code>) and the <code>False</code> branch (<code>align_right</code>) execute in <strong>isolated communication domains</strong>.</p>" +
        "<p>On <strong>Layer 4 (top)</strong>, channel nodes compute an internal gradient from the Source (warm colors, elevated), while outside nodes compute an independent degree field (sky blue, lower plane). Red dashed links mark physical connections across the border—<strong>no messages cross between the two branches!</strong></p>",
      code:
        "@aggregate\n" +
        "def branched_channel(width: float = 1.6) -> float:\n" +
        "    in_channel = channel(width)\n" +
        "    if in_channel:\n" +
        "        # align_left: only channel nodes hear each other!\n" +
        "        return distance_to(sense(\"source\"), neighbors_distances())\n" +
        "    else:\n" +
        "        # align_right: isolated outside domain\n" +
        "        return -float(len(neighbors(1).exclude_self()))",
      layers: [
        { id: "grad_target", name: "Layer 1 (G): distance_to(target)", color: "#ec4899" },
        { id: "on_path", name: "Layer 2 (C): collect_or (path)", color: "#f59e0b" },
        { id: "channel", name: "Layer 3 (G): channel mask", color: "#10b981" },
        { id: "branch", name: "Layer 4 (if/else): align_left vs align_right", color: "#38bdf8" },
      ],
    },
  ];

  // State
  let currentStep = 0;
  let roundCount = 0;
  let playing = true;
  let viewMode = "stacked";
  let focusedLayer = null;
  let layerGap = 3.2;
  let channelWidth = 1.6;
  let clickMode = "source";
  let hoveredNode = null;
  let selectedNode = 8;

  // Camera
  const DEFAULT_YAW = -0.62;
  const DEFAULT_PITCH = 0.54;
  const DEFAULT_ZOOM = 1.0;
  let camYaw = DEFAULT_YAW;
  let camPitch = DEFAULT_PITCH;
  let camZoom = DEFAULT_ZOOM;
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let dragMoved = false;

  // Viewport logical size
  let viewW = 860;
  let viewH = 640;

  const nodes = [];
  const edges = [];

  function seededJitter(idx) {
    const s = Math.sin(idx * 127.1 + 311.7) * 43758.5453;
    return s - Math.floor(s) - 0.5;
  }

  function initNetwork() {
    nodes.length = 0;
    for (let r = 0; r < GRID; r++) {
      for (let c = 0; c < GRID; c++) {
        const id = r * GRID + c;
        const inner = r > 0 && r < GRID - 1 && c > 0 && c < GRID - 1;
        const jx = inner ? seededJitter(id) * 0.25 : 0;
        const jy = inner ? seededJitter(id + 99) * 0.25 : 0;
        nodes.push({
          id: id,
          x: c + jx,
          y: r + jy,
          source: id === 0,
          target: id === NUM_NODES - 1,
          obstacle: id === 14 || id === 21,
          degree: 0,
          dTarget: INF,
          parentTarget: null,
          onPath: false,
          dPath: INF,
          inChannel: false,
          branchLeftDist: INF,
          branchRightVal: 0,
        });
      }
    }
    rebuildEdges();
    resetFieldState();
  }

  function rebuildEdges() {
    edges.length = 0;
    for (let i = 0; i < NUM_NODES; i++) {
      for (let j = i + 1; j < NUM_NODES; j++) {
        const dist = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        if (dist <= COMM_RADIUS) {
          edges.push({ a: i, b: j, dist: dist });
        }
      }
    }
  }

  function activeNeighbors(id) {
    if (nodes[id].obstacle) return [];
    const list = [];
    for (const e of edges) {
      if (e.a === id && !nodes[e.b].obstacle) list.push({ id: e.b, dist: e.dist });
      else if (e.b === id && !nodes[e.a].obstacle) list.push({ id: e.a, dist: e.dist });
    }
    return list;
  }

  function resetFieldState() {
    roundCount = 0;
    for (const n of nodes) {
      n.degree = 0;
      n.dTarget = n.target && !n.obstacle ? 0.0 : INF;
      n.parentTarget = null;
      n.onPath = n.source && !n.obstacle;
      n.dPath = n.onPath ? 0.0 : INF;
      n.inChannel = false;
      n.branchLeftDist = n.source && !n.obstacle ? 0.0 : INF;
      n.branchRightVal = 0;
    }
    updateRoundBadge();
    updateInspector();
  }

  function stepRound() {
    roundCount += 1;
    const prev = nodes.map((n) => ({
      dTarget: n.dTarget,
      parentTarget: n.parentTarget,
      onPath: n.onPath,
      dPath: n.dPath,
      inChannel: n.inChannel,
      branchLeftDist: n.branchLeftDist,
    }));

    for (let i = 0; i < NUM_NODES; i++) {
      const n = nodes[i];
      if (n.obstacle) {
        n.degree = 0;
        n.dTarget = INF;
        n.parentTarget = null;
        n.onPath = false;
        n.dPath = INF;
        n.inChannel = false;
        n.branchLeftDist = INF;
        n.branchRightVal = 0;
        continue;
      }

      const nbrs = activeNeighbors(i);
      n.degree = nbrs.length;

      // Layer 1: distance_to(target)
      if (n.target) {
        n.dTarget = 0.0;
        n.parentTarget = null;
      } else {
        let best = INF;
        let bestParent = null;
        for (const nb of nbrs) {
          const cand = prev[nb.id].dTarget + nb.dist;
          if (cand < best) {
            best = cand;
            bestParent = nb.id;
          }
        }
        n.dTarget = Math.min(best, INF);
        n.parentTarget = bestParent;
      }

      // Layer 2: collect_or(to_target, source)
      let childOnPath = false;
      for (const nb of nbrs) {
        if (prev[nb.id].onPath && prev[nb.id].parentTarget === i) {
          childOnPath = true;
          break;
        }
      }
      n.onPath = Boolean((n.source && n.dTarget < INF) || childOnPath || (n.target && childOnPath));

      // Layer 3: distance_to(on_path) <= channelWidth
      if (n.onPath) {
        n.dPath = 0.0;
      } else {
        let bestP = INF;
        for (const nb of nbrs) {
          const cand = prev[nb.id].dPath + nb.dist;
          if (cand < bestP) bestP = cand;
        }
        n.dPath = Math.min(bestP, INF);
      }
      n.inChannel = n.dPath <= channelWidth;

      // Layer 4: Branching (if in_channel: align_left else: align_right)
      if (n.inChannel) {
        if (n.source) {
          n.branchLeftDist = 0.0;
        } else {
          let bestL = INF;
          for (const nb of nbrs) {
            if (prev[nb.id].inChannel) {
              const cand = prev[nb.id].branchLeftDist + nb.dist;
              if (cand < bestL) bestL = cand;
            }
          }
          n.branchLeftDist = Math.min(bestL, INF);
        }
        n.branchRightVal = 0;
      } else {
        n.branchLeftDist = INF;
        let alignedOutside = 0;
        for (const nb of nbrs) {
          if (!prev[nb.id].inChannel) alignedOutside += 1;
        }
        n.branchRightVal = alignedOutside;
      }
    }

    updateRoundBadge();
    updateInspector();
  }

  function resizeCanvas() {
    const rect = stageEl.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    viewW = Math.max(320, rect.width);
    viewH = Math.max(320, rect.height);
    canvas.width = Math.round(viewW * dpr);
    canvas.height = Math.round(viewH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    render();
  }

  function project3D(gx, gy, gz) {
    const cx = (GRID - 1) / 2;
    const cy = (GRID - 1) / 2;
    const x0 = gx - cx;
    const y0 = gy - cy;

    const cosY = Math.cos(camYaw);
    const sinY = Math.sin(camYaw);
    const cosP = Math.cos(camPitch);
    const sinP = Math.sin(camPitch);

    const rx = x0 * cosY - y0 * sinY;
    const ry = x0 * sinY + y0 * cosY;

    const baseScale = Math.min(viewW, viewH) * 0.115 * camZoom;
    const screenX = viewW * 0.5 + rx * baseScale;
    const screenY = viewH * 0.53 + (ry * sinP - gz * cosP) * baseScale;
    const depth = ry * cosP + gz * sinP;
    return { x: screenX, y: screenY, depth: depth };
  }

  function plasmaColor(t) {
    const clamped = Math.max(0, Math.min(1, t));
    const stops = [
      [245, 158, 11],
      [249, 115, 22],
      [225, 29, 116],
      [109, 40, 217],
    ];
    const pos = clamped * (stops.length - 1);
    const idx = Math.min(stops.length - 2, Math.floor(pos));
    const frac = pos - idx;
    const r = Math.round(stops[idx][0] + (stops[idx + 1][0] - stops[idx][0]) * frac);
    const g = Math.round(stops[idx][1] + (stops[idx + 1][1] - stops[idx][1]) * frac);
    const b = Math.round(stops[idx][2] + (stops[idx + 1][2] - stops[idx][2]) * frac);
    return `rgb(${r},${g},${b})`;
  }

  function nodeLayerAppearance(n, layerId) {
    if (n.obstacle) {
      return { color: "#475569", radius: 5.5, relief: 0, label: "OBS", valid: false };
    }
    if (layerId === "sensors") {
      if (n.source) return { color: "#f59e0b", radius: 9.5, relief: 0.25, label: "SOURCE", valid: true };
      if (n.target) return { color: "#10b981", radius: 9.5, relief: 0.25, label: "TARGET", valid: true };
      return { color: "#94a3b8", radius: 6, relief: 0, label: "", valid: true };
    }
    if (layerId === "degree") {
      const t = 1 - Math.min(1, n.degree / 8);
      return {
        color: plasmaColor(t * 0.8),
        radius: 8,
        relief: (n.degree / 8) * 0.95,
        label: String(n.degree),
        valid: true,
      };
    }
    if (layerId === "grad_target") {
      if (n.dTarget >= INF) {
        return { color: "#64748b", radius: 6, relief: 0, label: "∞", valid: false };
      }
      const t = Math.min(1, n.dTarget / 8.5);
      return {
        color: plasmaColor(t),
        radius: n.target ? 9.5 : 7.5,
        relief: Math.min(1.25, n.dTarget * 0.14),
        label: n.dTarget.toFixed(1),
        valid: true,
      };
    }
    if (layerId === "on_path") {
      if (n.onPath) {
        return { color: "#f59e0b", radius: 9.5, relief: 0.38, label: "True", valid: true };
      }
      return { color: "#475569", radius: 5.5, relief: 0, label: "", valid: false };
    }
    if (layerId === "channel") {
      if (n.inChannel) {
        return { color: "#10b981", radius: 8.8, relief: 0.35, label: "True", valid: true };
      }
      return { color: "#475569", radius: 5.5, relief: 0, label: "", valid: false };
    }
    if (layerId === "branch") {
      if (n.inChannel) {
        const t = n.branchLeftDist < INF ? Math.min(1, n.branchLeftDist / 8.5) : 1;
        return {
          color: plasmaColor(t * 0.85),
          radius: 8.8,
          relief: 0.42,
          label: n.branchLeftDist < INF ? n.branchLeftDist.toFixed(1) : "∞",
          valid: true,
        };
      }
      return {
        color: "#38bdf8",
        radius: 7,
        relief: -0.18,
        label: `-${n.branchRightVal}`,
        valid: true,
      };
    }
    return { color: "#94a3b8", radius: 6.5, relief: 0, label: "", valid: true };
  }

  let screenNodes = [];

  function render() {
    ctx.clearRect(0, 0, viewW, viewH);

    const stepObj = STEPS[currentStep];
    const allLayers = stepObj.layers;
    const layersToDraw =
      focusedLayer !== null
        ? allLayers.filter((l) => l.id === focusedLayer)
        : allLayers;

    const numL = layersToDraw.length;
    const totalSpan = viewMode === "stacked" && numL > 1 ? layerGap * (numL - 1) * 0.48 : 0;
    const layerSpacing = numL > 1 ? totalSpan / (numL - 1) : 0;
    const baseOffset = -totalSpan * 0.5;

    screenNodes = [];

    // 1. Vertical alignment fibres connecting each node across all stacked layers
    if (viewMode === "stacked" && numL > 1) {
      for (let i = 0; i < NUM_NODES; i++) {
        const n = nodes[i];
        if (n.obstacle) continue;
        const isFocus = i === hoveredNode || i === selectedNode;
        const pBottom = project3D(n.x, n.y, baseOffset);
        const topApp = nodeLayerAppearance(n, layersToDraw[numL - 1].id);
        const pTop = project3D(
          n.x,
          n.y,
          baseOffset + (numL - 1) * layerSpacing + topApp.relief * 0.42
        );
        ctx.save();
        ctx.beginPath();
        ctx.setLineDash(isFocus ? [5, 3] : [2, 5]);
        ctx.strokeStyle = isFocus ? "#fde047" : "rgba(148, 163, 184, 0.22)";
        ctx.lineWidth = isFocus ? 2.2 : 1.0;
        ctx.moveTo(pBottom.x, pBottom.y);
        ctx.lineTo(pTop.x, pTop.y);
        ctx.stroke();
        ctx.restore();
      }
    }

    // 2. Render each layer plane from bottom to top
    layersToDraw.forEach((layer, lIdx) => {
      const zPlane = baseOffset + lIdx * layerSpacing;

      const corners = [
        project3D(-0.55, -0.55, zPlane),
        project3D(GRID - 0.45, -0.55, zPlane),
        project3D(GRID - 0.45, GRID - 0.45, zPlane),
        project3D(-0.55, GRID - 0.45, zPlane),
      ];
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(corners[0].x, corners[0].y);
      for (let c = 1; c < 4; c++) ctx.lineTo(corners[c].x, corners[c].y);
      ctx.closePath();
      ctx.fillStyle = "rgba(24, 19, 36, 0.46)";
      ctx.strokeStyle = layer.color;
      ctx.lineWidth = 1.6;
      ctx.fill();
      ctx.stroke();

      // Layer label badge on the front-left corner of the plane
      const tagX = corners[3].x + 10;
      const tagY = corners[3].y - 10;
      ctx.font = "bold 12px sans-serif";
      const textW = ctx.measureText(layer.name).width;
      ctx.fillStyle = "rgba(17, 14, 23, 0.88)";
      ctx.strokeStyle = layer.color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.roundRect(tagX - 6, tagY - 13, textW + 12, 20, 5);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = layer.color;
      ctx.fillText(layer.name, tagX, tagY + 1);
      ctx.restore();

      const reliefScale = viewMode === "surface" ? 1.85 : 0.42;

      const layerPts = nodes.map((n) => {
        const app = nodeLayerAppearance(n, layer.id);
        const z = zPlane + app.relief * reliefScale;
        const p = project3D(n.x, n.y, z);
        const pBase = project3D(n.x, n.y, zPlane);
        return { n, app, p, pBase };
      });

      // Edges
      for (const e of edges) {
        const na = layerPts[e.a];
        const nb = layerPts[e.b];
        if (na.n.obstacle || nb.n.obstacle) continue;

        ctx.save();
        ctx.beginPath();

        if (layer.id === "branch") {
          const sameDomain = na.n.inChannel === nb.n.inChannel;
          if (!sameDomain) {
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = "rgba(239, 68, 68, 0.6)";
            ctx.lineWidth = 1.3;
          } else if (na.n.inChannel) {
            ctx.strokeStyle = "rgba(245, 158, 11, 0.85)";
            ctx.lineWidth = 2.4;
          } else {
            ctx.strokeStyle = "rgba(56, 189, 248, 0.48)";
            ctx.lineWidth = 1.4;
          }
        } else if (layer.id === "on_path") {
          const bothPath =
            na.n.onPath &&
            nb.n.onPath &&
            (na.n.parentTarget === nb.n.id || nb.n.parentTarget === na.n.id);
          ctx.strokeStyle = bothPath ? "#f59e0b" : "rgba(148, 163, 184, 0.2)";
          ctx.lineWidth = bothPath ? 3.4 : 1.0;
        } else if (layer.id === "channel") {
          const bothChan = na.n.inChannel && nb.n.inChannel;
          ctx.strokeStyle = bothChan ? "rgba(16, 185, 129, 0.85)" : "rgba(148, 163, 184, 0.2)";
          ctx.lineWidth = bothChan ? 2.5 : 1.0;
        } else {
          const isTreeEdge =
            layer.id === "grad_target" &&
            (na.n.parentTarget === nb.n.id || nb.n.parentTarget === na.n.id);
          ctx.strokeStyle = isTreeEdge
            ? "rgba(244, 114, 182, 0.8)"
            : "rgba(148, 163, 184, 0.25)";
          ctx.lineWidth = isTreeEdge ? 2.1 : 1.1;
        }

        ctx.moveTo(na.p.x, na.p.y);
        ctx.lineTo(nb.p.x, nb.p.y);
        ctx.stroke();
        ctx.restore();
      }

      // Highlight 1-hop neighborhood of focused node
      const focusId = hoveredNode !== null ? hoveredNode : selectedNode;
      if (focusId !== null && !nodes[focusId].obstacle) {
        const centerPt = layerPts[focusId];
        for (const nb of activeNeighbors(focusId)) {
          const nbPt = layerPts[nb.id];
          if (layer.id === "branch" && centerPt.n.inChannel !== nbPt.n.inChannel) {
            continue;
          }
          ctx.save();
          ctx.beginPath();
          ctx.strokeStyle = "#fde047";
          ctx.lineWidth = 2.6;
          ctx.moveTo(centerPt.p.x, centerPt.p.y);
          ctx.lineTo(nbPt.p.x, nbPt.p.y);
          ctx.stroke();
          ctx.restore();
        }
      }

      // Nodes sorted back-to-front
      const sorted = layerPts.slice().sort((a, b) => a.p.depth - b.p.depth);

      for (const item of sorted) {
        const { n, app, p, pBase } = item;

        if (Math.abs(p.y - pBase.y) > 2) {
          ctx.save();
          ctx.beginPath();
          ctx.strokeStyle = app.color;
          ctx.globalAlpha = 0.6;
          ctx.lineWidth = 2.2;
          ctx.moveTo(pBase.x, pBase.y);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();
          ctx.restore();
        }

        const isFocus = n.id === hoveredNode || n.id === selectedNode;
        ctx.save();
        ctx.beginPath();
        ctx.arc(p.x, p.y, app.radius + (isFocus ? 2.5 : 0), 0, Math.PI * 2);
        ctx.fillStyle = app.color;
        ctx.fill();
        ctx.lineWidth = isFocus ? 2.8 : 1.5;
        ctx.strokeStyle = isFocus ? "#fde047" : "#ffffff";
        ctx.stroke();

        if (n.source || n.target) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, app.radius + 5, 0, Math.PI * 2);
          ctx.strokeStyle = n.source ? "#f59e0b" : "#10b981";
          ctx.lineWidth = 2.2;
          ctx.stroke();
        }

        // Value label on top-most visible layer
        if (lIdx === layersToDraw.length - 1 && app.label) {
          ctx.font = "bold 10.5px monospace";
          ctx.fillStyle = "#ffffff";
          ctx.textAlign = "center";
          ctx.fillText(app.label, p.x, p.y - app.radius - 6);
        }
        ctx.restore();

        if (lIdx === layersToDraw.length - 1) {
          screenNodes.push({ id: n.id, x: p.x, y: p.y, r: app.radius + 8 });
        }
      }
    });
  }

  function updateRoundBadge() {
    const badge = document.getElementById("wt-round-badge");
    if (badge) badge.textContent = `Round ${roundCount}`;
  }

  function renderLayersBar() {
    const bar = document.getElementById("wt-layers-bar");
    if (!bar) return;
    const layers = STEPS[currentStep].layers;
    bar.innerHTML = "";

    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = "wt-layer-pill" + (focusedLayer === null ? " active" : "");
    allBtn.textContent = `All Stacked Layers (${layers.length})`;
    allBtn.addEventListener("click", () => {
      focusedLayer = null;
      renderLayersBar();
      render();
    });
    bar.appendChild(allBtn);

    layers.forEach((layer) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "wt-layer-pill" + (focusedLayer === layer.id ? " active" : "");
      btn.style.borderColor = layer.color;
      btn.innerHTML = `<span class="wt-layer-dot" style="background:${layer.color}"></span>${layer.name}`;
      btn.addEventListener("click", () => {
        focusedLayer = focusedLayer === layer.id ? null : layer.id;
        renderLayersBar();
        render();
      });
      bar.appendChild(btn);
    });
  }

  function updateInspector() {
    const idBadge = document.getElementById("wt-insp-id");
    const body = document.getElementById("wt-insp-body");
    if (!idBadge || !body) return;

    const id = hoveredNode !== null ? hoveredNode : selectedNode;
    if (id === null || !nodes[id]) return;
    const n = nodes[id];
    const nbrs = activeNeighbors(id);

    const role = n.obstacle
      ? "OBSTACLE"
      : n.source
      ? "SOURCE"
      : n.target
      ? "TARGET"
      : "Device";
    idBadge.textContent = `Node #${id} (${role})`;

    if (n.obstacle) {
      body.innerHTML =
        "<p>This node is disabled (<strong>Obstacle</strong>). It sends no messages and does not appear in neighbors' <code>NeighborhoodField</code>. Click it in <em>Obstacle</em> mode to re-enable it.</p>";
      return;
    }

    const nbrIds = nbrs.map((nb) => nb.id).join(", ") || "none";
    const dT = n.dTarget < INF ? n.dTarget.toFixed(2) : "∞";
    const dP = n.dPath < INF ? n.dPath.toFixed(2) : "∞";
    const alignBranch = n.inChannel
      ? "align_left (Channel)"
      : "align_right (Outside)";

    body.innerHTML =
      `<div class="wt-insp-grid">` +
      `<div class="wt-insp-row"><span class="wt-insp-key">Sensors</span><span class="wt-insp-val">source=${n.source}, target=${n.target}</span></div>` +
      `<div class="wt-insp-row"><span class="wt-insp-key">1-Hop Neighbors (${nbrs.length})</span><span class="wt-insp-val">[${nbrIds}]</span></div>` +
      `<div class="wt-insp-row"><span class="wt-insp-key">Layer 1: to_target</span><span class="wt-insp-val">${dT} (parent: ${n.parentTarget ?? "None"})</span></div>` +
      `<div class="wt-insp-row"><span class="wt-insp-key">Layer 2: on_path</span><span class="wt-insp-val">${n.onPath}</span></div>` +
      `<div class="wt-insp-row"><span class="wt-insp-key">Layer 3: in_channel</span><span class="wt-insp-val">${n.inChannel} (dist=${dP})</span></div>` +
      `<div class="wt-insp-row"><span class="wt-insp-key">Layer 4: Branch Scope</span><span class="wt-insp-val">${alignBranch}</span></div>` +
      `</div>`;
  }

  function setStep(idx) {
    currentStep = Math.max(0, Math.min(STEPS.length - 1, idx));
    focusedLayer = null;
    const s = STEPS[currentStep];

    document.querySelectorAll(".wt-step-btn").forEach((btn, i) => {
      btn.classList.toggle("active", i === currentStep);
    });

    document.getElementById("wt-step-kicker").textContent = s.kicker;
    document.getElementById("wt-step-title").textContent = s.title;
    document.getElementById("wt-step-desc").innerHTML = s.desc;
    document.getElementById("wt-code-display").textContent = s.code;

    const prevBtn = document.getElementById("wt-prev-step");
    const nextBtn = document.getElementById("wt-next-step");
    if (prevBtn) prevBtn.disabled = currentStep === 0;
    if (nextBtn) nextBtn.disabled = currentStep === STEPS.length - 1;

    renderLayersBar();
    updateInspector();
    render();
  }

  function findNodeAt(mx, my) {
    let best = null;
    let bestDist = 999;
    for (const sn of screenNodes) {
      const d = Math.hypot(mx - sn.x, my - sn.y);
      if (d <= sn.r && d < bestDist) {
        best = sn.id;
        bestDist = d;
      }
    }
    return best;
  }

  function canvasCoords(evt) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: evt.clientX - rect.left,
      y: evt.clientY - rect.top,
    };
  }

  canvas.addEventListener("mousedown", (evt) => {
    isDragging = true;
    dragMoved = false;
    dragStart = { x: evt.clientX, y: evt.clientY };
  });

  window.addEventListener("mousemove", (evt) => {
    if (isDragging) {
      const dx = evt.clientX - dragStart.x;
      const dy = evt.clientY - dragStart.y;
      if (Math.hypot(dx, dy) > 4) dragMoved = true;
      camYaw += dx * 0.008;
      camPitch = Math.max(0.18, Math.min(1.38, camPitch + dy * 0.007));
      dragStart = { x: evt.clientX, y: evt.clientY };
      render();
      return;
    }
    const rect = canvas.getBoundingClientRect();
    if (
      evt.clientX >= rect.left &&
      evt.clientX <= rect.right &&
      evt.clientY >= rect.top &&
      evt.clientY <= rect.bottom
    ) {
      const pt = canvasCoords(evt);
      const hit = findNodeAt(pt.x, pt.y);
      if (hit !== hoveredNode) {
        hoveredNode = hit;
        canvas.style.cursor = hit !== null ? "pointer" : "grab";
        updateInspector();
        render();
      }
    }
  });

  window.addEventListener("mouseup", (evt) => {
    if (!isDragging) return;
    isDragging = false;
    if (!dragMoved) {
      const pt = canvasCoords(evt);
      const hit = findNodeAt(pt.x, pt.y);
      if (hit !== null) {
        selectedNode = hit;
        const n = nodes[hit];
        if (clickMode === "source" && !n.target) {
          nodes.forEach((node) => (node.source = false));
          n.obstacle = false;
          n.source = true;
        } else if (clickMode === "target" && !n.source) {
          nodes.forEach((node) => (node.target = false));
          n.obstacle = false;
          n.target = true;
        } else if (clickMode === "obstacle" && !n.source && !n.target) {
          n.obstacle = !n.obstacle;
        }
        updateInspector();
        render();
      }
    }
  });

  canvas.addEventListener(
    "wheel",
    (evt) => {
      evt.preventDefault();
      const factor = evt.deltaY < 0 ? 1.08 : 0.92;
      camZoom = Math.max(0.55, Math.min(2.2, camZoom * factor));
      render();
    },
    { passive: false }
  );

  // Controls
  document.querySelectorAll(".wt-step-btn").forEach((btn) => {
    btn.addEventListener("click", () => setStep(Number(btn.dataset.step)));
  });

  document.getElementById("wt-prev-step").addEventListener("click", () => setStep(currentStep - 1));
  document.getElementById("wt-next-step").addEventListener("click", () => setStep(currentStep + 1));

  const playBtn = document.getElementById("wt-play");
  playBtn.addEventListener("click", () => {
    playing = !playing;
    playBtn.textContent = playing ? "Pause" : "Play";
  });

  document.getElementById("wt-step-round").addEventListener("click", () => {
    playing = false;
    playBtn.textContent = "Play";
    stepRound();
    render();
  });

  document.getElementById("wt-reset").addEventListener("click", () => {
    resetFieldState();
    render();
  });

  document.getElementById("wt-view-mode").addEventListener("change", (evt) => {
    viewMode = evt.target.value;
    render();
  });

  const gapSlider = document.getElementById("wt-gap-slider");
  if (gapSlider) {
    gapSlider.addEventListener("input", (evt) => {
      layerGap = parseFloat(evt.target.value);
      render();
    });
  }

  const widthSlider = document.getElementById("wt-width-slider");
  const widthVal = document.getElementById("wt-width-val");
  widthSlider.addEventListener("input", (evt) => {
    channelWidth = parseFloat(evt.target.value);
    widthVal.textContent = channelWidth.toFixed(1);
    stepRound();
    render();
  });

  const resetCamBtn = document.getElementById("wt-reset-cam");
  if (resetCamBtn) {
    resetCamBtn.addEventListener("click", () => {
      camYaw = DEFAULT_YAW;
      camPitch = DEFAULT_PITCH;
      camZoom = DEFAULT_ZOOM;
      render();
    });
  }

  document.querySelectorAll(".wt-mode-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      clickMode = pill.dataset.click;
      document.querySelectorAll(".wt-mode-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
    });
  });

  initNetwork();
  for (let r = 0; r < 10; r++) stepRound();
  setStep(0);

  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => resizeCanvas()).observe(stageEl);
  } else {
    window.addEventListener("resize", resizeCanvas);
  }
  resizeCanvas();

  setInterval(() => {
    if (playing) {
      stepRound();
      render();
    }
  }, 450);
})();
