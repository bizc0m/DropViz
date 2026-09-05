(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("graph-data").textContent);
  var COMMUNITY_COLORS = ["#4fb3a9", "#d99a5b", "#8f8fd9", "#d98fa0", "#8fbf8a", "#6fa8d9", "#c2a15c", "#5cb0d9"];
  var LOW_CONF_STROKE = "#d99a5b";

  function communityColor(i) { return COMMUNITY_COLORS[i % COMMUNITY_COLORS.length]; }

  // ---------------------------------------------------------------------
  // Admiralty Code : classes CSS pour les badges fiabilité (A-F) / crédibilité (1-6)
  // ---------------------------------------------------------------------
  function reliabilityClass(letter) {
    if (letter === "A" || letter === "B") return "good";
    if (letter === "C") return "mid";
    if (letter === "D" || letter === "E") return "bad";
    return "unknown";
  }
  function credibilityClass(n) {
    if (n <= 2) return "good";
    if (n <= 4) return "mid";
    return "unknown";
  }
  function admiraltyBadgesHtml(reliability, credibility) {
    return '<span class="badge-adm ' + reliabilityClass(reliability) + '" title="Admiralty: fiabilité de la source">' +
      'fiab. ' + reliability + '</span>' +
      '<span class="badge-adm ' + credibilityClass(credibility) + '" title="Admiralty: crédibilité suggérée (calculée, pas un jugement humain)">' +
      'créd. ' + credibility + '/6</span>';
  }

  // ---------------------------------------------------------------------
  // build working node/edge objects (world-space physics state)
  // ---------------------------------------------------------------------
  var nodeById = {};
  var nodes = DATA.nodes.map(function (n, i) {
    var angle = (i / DATA.nodes.length) * Math.PI * 2;
    var node = Object.assign({}, n, {
      x: Math.cos(angle) * 200 + (Math.random() - 0.5) * 40,
      y: Math.sin(angle) * 200 + (Math.random() - 0.5) * 40,
      vx: 0, vy: 0, fx: null, fy: null,
    });
    nodeById[node.id] = node;
    return node;
  });
  var edges = DATA.edges.map(function (e) {
    return Object.assign({}, e, { s: nodeById[e.source], t: nodeById[e.target] });
  }).filter(function (e) { return e.s && e.t; });

  var prMax = Math.max.apply(null, nodes.map(function (n) { return n.pagerank; }).concat([1e-9]));
  var prMin = Math.min.apply(null, nodes.map(function (n) { return n.pagerank; }).concat([0]));
  var wMax = Math.max.apply(null, edges.map(function (e) { return e.weight; }).concat([1]));

  function radiusOf(n) {
    var t = prMax > prMin ? (n.pagerank - prMin) / (prMax - prMin) : 0.5;
    return 5 + t * 16;
  }
  nodes.forEach(function (n) { n.r = radiusOf(n); });

  // ---------------------------------------------------------------------
  // physics: simple force simulation (repulsion + springs + centering)
  // ---------------------------------------------------------------------
  var REPULSION = 2600;
  var SPRING_K = 0.02;
  var DAMPING = 0.86;
  var CENTER_K = 0.006;
  var settled = false;

  function tick() {
    if (settled) return;
    var n = nodes.length;
    for (var i = 0; i < n; i++) {
      var a = nodes[i];
      if (a.fx != null) continue;
      var fx = -a.x * CENTER_K, fy = -a.y * CENTER_K;
      for (var j = 0; j < n; j++) {
        if (i === j) continue;
        var b = nodes[j];
        var dx = a.x - b.x, dy = a.y - b.y;
        var d2 = dx * dx + dy * dy + 0.01;
        var f = REPULSION / d2;
        var d = Math.sqrt(d2);
        fx += (dx / d) * f;
        fy += (dy / d) * f;
      }
      a.ax = fx; a.ay = fy;
    }
    edges.forEach(function (e) {
      var dx = e.t.x - e.s.x, dy = e.t.y - e.s.y;
      var d = Math.sqrt(dx * dx + dy * dy) || 1;
      var rest = 70 - Math.min(e.weight, wMax) * (30 / wMax);
      var f = SPRING_K * (d - rest);
      var fx = (dx / d) * f, fy = (dy / d) * f;
      if (e.s.fx == null) { e.s.ax += fx; e.s.ay += fy; }
      if (e.t.fx == null) { e.t.ax -= fx; e.t.ay -= fy; }
    });
    var energy = 0;
    nodes.forEach(function (a) {
      if (a.fx != null) { a.x = a.fx; a.y = a.fy; a.vx = 0; a.vy = 0; return; }
      a.vx = (a.vx + a.ax * 0.9) * DAMPING;
      a.vy = (a.vy + a.ay * 0.9) * DAMPING;
      a.x += a.vx;
      a.y += a.vy;
      energy += a.vx * a.vx + a.vy * a.vy;
    });
    if (energy / n < 0.002) settled = true;
  }

  // ---------------------------------------------------------------------
  // canvas + view transform
  // ---------------------------------------------------------------------
  var canvas = document.getElementById("graph-canvas");
  var ctx = canvas.getContext("2d");
  var stage = document.getElementById("stage");
  var view = { panX: 0, panY: 0, scale: 1 };
  var dpr = Math.max(1, window.devicePixelRatio || 1);

  function resize() {
    var rect = stage.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + "px";
    canvas.style.height = rect.height + "px";
    view.panX = rect.width / 2;
    view.panY = rect.height / 2;
  }
  window.addEventListener("resize", resize);
  resize();

  function worldToScreen(x, y) {
    return [x * view.scale + view.panX, y * view.scale + view.panY];
  }
  function screenToWorld(x, y) {
    return [(x - view.panX) / view.scale, (y - view.panY) / view.scale];
  }

  var cssVar = getComputedStyle(document.documentElement);
  var C_INK = cssVar.getPropertyValue("--ink").trim() || "#e8ecf1";
  var C_DIM = cssVar.getPropertyValue("--ink-dim").trim() || "#8996a6";
  var C_LINE = cssVar.getPropertyValue("--line").trim() || "#2a3441";

  var hoverNode = null, selectedNode = null, dragNode = null, panning = false;
  var lastMouse = { x: 0, y: 0 };
  var searchTerm = "";
  var matchedIds = null;

  function normalize(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  function neighborsOf(node) {
    var ids = new Set();
    edges.forEach(function (e) {
      if (e.s === node) ids.add(e.t.id);
      if (e.t === node) ids.add(e.s.id);
    });
    return ids;
  }

  function draw() {
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    var focusNeighbors = selectedNode ? neighborsOf(selectedNode) : (hoverNode ? neighborsOf(hoverNode) : null);
    var focusNode = selectedNode || hoverNode;

    edges.forEach(function (e) {
      var dim = matchedIds && !(matchedIds.has(e.s.id) && matchedIds.has(e.t.id));
      var faded = focusNode && e.s !== focusNode && e.t !== focusNode;
      var p1 = worldToScreen(e.s.x, e.s.y), p2 = worldToScreen(e.t.x, e.t.y);
      ctx.beginPath();
      ctx.moveTo(p1[0], p1[1]);
      ctx.lineTo(p2[0], p2[1]);
      ctx.lineWidth = Math.max(1, (0.6 + (e.weight / wMax) * 3) * Math.min(1.4, view.scale));
      ctx.setLineDash(e.lowConfidence ? [4, 3] : []);
      var alpha = (dim || faded) ? 0.08 : 0.22 + e.avgConfidence * 0.35;
      ctx.strokeStyle = e.lowConfidence ? hexA(LOW_CONF_STROKE, alpha) : hexA(C_DIM, alpha);
      ctx.stroke();
      ctx.setLineDash([]);
    });

    nodes.forEach(function (n) {
      var p = worldToScreen(n.x, n.y);
      var dim = matchedIds && !matchedIds.has(n.id);
      var faded = focusNeighbors && n !== focusNode && !focusNeighbors.has(n.id);
      var alpha = (dim || faded) ? 0.18 : 1;
      var r = p.length ? n.r * Math.min(1.6, Math.max(0.6, view.scale)) : n.r;

      ctx.beginPath();
      ctx.arc(p[0], p[1], r, 0, Math.PI * 2);
      ctx.fillStyle = hexA(communityColor(n.community), alpha);
      ctx.fill();
      if (n.lowConfidence) {
        ctx.setLineDash([2.5, 2]);
        ctx.strokeStyle = hexA(LOW_CONF_STROKE, alpha);
        ctx.lineWidth = 1.6;
        ctx.stroke();
        ctx.setLineDash([]);
      } else if (n === selectedNode) {
        ctx.strokeStyle = hexA(C_INK, alpha);
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }

      var showLabel = r > 9 * view.scale || n === hoverNode || n === selectedNode || (matchedIds && matchedIds.has(n.id));
      if (showLabel && !dim) {
        ctx.font = "500 " + Math.max(10, 11 * Math.min(1.3, view.scale)) + "px 'IBM Plex Sans', sans-serif";
        ctx.fillStyle = hexA(C_INK, alpha);
        ctx.textAlign = "center";
        ctx.fillText(n.label, p[0], p[1] - r - 6);
      }
    });

    ctx.restore();
  }

  function hexA(hex, a) {
    var c = hex.replace("#", "");
    if (c.length === 3) c = c.split("").map(function (ch) { return ch + ch; }).join("");
    var r = parseInt(c.substr(0, 2), 16), g = parseInt(c.substr(2, 2), 16), b = parseInt(c.substr(4, 2), 16);
    return "rgba(" + r + "," + g + "," + b + "," + a + ")";
  }

  function loop() {
    tick();
    draw();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  // ---------------------------------------------------------------------
  // hit testing + mouse interactions
  // ---------------------------------------------------------------------
  function nodeAt(sx, sy) {
    for (var i = nodes.length - 1; i >= 0; i--) {
      var n = nodes[i];
      var p = worldToScreen(n.x, n.y);
      var r = Math.max(n.r * view.scale, 6);
      var dx = sx - p[0], dy = sy - p[1];
      if (dx * dx + dy * dy <= r * r) return n;
    }
    return null;
  }

  var tooltip = document.getElementById("tooltip");

  canvas.addEventListener("mousemove", function (ev) {
    var rect = canvas.getBoundingClientRect();
    var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;

    if (dragNode) {
      var w = screenToWorld(sx, sy);
      dragNode.fx = w[0]; dragNode.fy = w[1];
      settled = false;
      tooltip.style.opacity = 0;
      return;
    }
    if (panning) {
      view.panX += ev.clientX - lastMouse.x;
      view.panY += ev.clientY - lastMouse.y;
      lastMouse = { x: ev.clientX, y: ev.clientY };
      return;
    }
    var hit = nodeAt(sx, sy);
    hoverNode = hit;
    canvas.style.cursor = hit ? "pointer" : "grab";
    if (hit) {
      showTooltip(hit, ev.clientX, ev.clientY);
    } else {
      tooltip.style.opacity = 0;
    }
  });

  canvas.addEventListener("mousedown", function (ev) {
    var rect = canvas.getBoundingClientRect();
    var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
    var hit = nodeAt(sx, sy);
    if (hit) {
      dragNode = hit;
      canvas.classList.add("dragging");
    } else {
      panning = true;
      lastMouse = { x: ev.clientX, y: ev.clientY };
      canvas.classList.add("dragging");
    }
  });

  window.addEventListener("mouseup", function () {
    if (dragNode) { dragNode.fx = null; dragNode.fy = null; settled = false; }
    dragNode = null;
    panning = false;
    canvas.classList.remove("dragging");
  });

  canvas.addEventListener("click", function (ev) {
    var rect = canvas.getBoundingClientRect();
    var hit = nodeAt(ev.clientX - rect.left, ev.clientY - rect.top);
    selectedNode = hit;
    renderPanel();
  });

  canvas.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var rect = canvas.getBoundingClientRect();
    var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
    var before = screenToWorld(sx, sy);
    var factor = Math.exp(-ev.deltaY * 0.001);
    view.scale = Math.min(4, Math.max(0.15, view.scale * factor));
    var after = screenToWorld(sx, sy);
    view.panX += (after[0] - before[0]) * view.scale;
    view.panY += (after[1] - before[1]) * view.scale;
  }, { passive: false });

  function showTooltip(n, cx, cy) {
    var flag = n.lowConfidence
      ? '<div class="t-flag">⚠ &lt; ' + DATA.meta.minCorroboratingSources + ' source(s)</div>'
      : (n.singleSourceHub ? '<div class="t-flag">⚠ hub à source unique</div>' : "");
    tooltip.innerHTML =
      '<div class="t-label">' + escapeHtml(n.label) + '</div>' +
      '<div class="t-meta">communauté #' + n.community + ' · ' + n.mentions + ' mention(s) · ' +
      n.sources.length + ' source(s)</div>' +
      '<div class="admiralty-row" style="margin:5px 0 0">' + admiraltyBadgesHtml(n.reliability, n.credibility) + '</div>' +
      flag;
    tooltip.style.left = (cx + 14) + "px";
    tooltip.style.top = (cy + 14) + "px";
    tooltip.style.opacity = 1;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // ---------------------------------------------------------------------
  // panneau latéral : légende par défaut, détail au clic
  // ---------------------------------------------------------------------
  var panelEl = document.getElementById("panel");

  function communityLabel(cid) {
    var top = nodes.filter(function (n) { return n.community === cid; })
      .sort(function (a, b) { return b.pagerank - a.pagerank; })[0];
    return top ? top.label : "communauté #" + cid;
  }

  function renderLegend() {
    var communities = Array.from(new Set(nodes.map(function (n) { return n.community; }))).sort(function (a, b) { return a - b; });
    var rows = communities.map(function (cid) {
      return '<div class="legend-row"><span class="legend-swatch" style="background:' + communityColor(cid) +
        '"></span>autour de « ' + escapeHtml(communityLabel(cid)) + ' »</div>';
    }).join("");

    panelEl.innerHTML =
      '<div class="panel-section"><h2>Légende</h2>' + rows +
      '<div class="legend-row"><span class="legend-swatch" style="border:1.5px dashed ' + LOW_CONF_STROKE +
      ';background:transparent"></span>faible confiance (peu de sources)</div>' +
      '<div class="legend-note">Taille des nœuds = importance (PageRank).<br>' +
      'Épaisseur des liens = fréquence de la relation.<br>' +
      'Trait pointillé = relation ou entité peu corroborée.<br><br>' +
      '<b>Admiralty Code</b> — fiab. = fiabilité de la source (A meilleure .. F inconnue, ' +
      'jugée à la main par source). créd. = crédibilité suggérée (1 confirmé .. 6 ne peut être ' +
      'jugée), calculée depuis la fiabilité + le nombre de documents indépendants. ' +
      'C\'est une heuristique, pas un verdict.<br><br>' +
      'Clique un nœud pour le détail. Molette pour zoomer, glisser pour déplacer.</div></div>';
  }

  function renderPanel() {
    if (!selectedNode) { renderLegend(); return; }
    var n = selectedNode;
    var rel = edges.filter(function (e) { return e.s === n || e.t === n; })
      .sort(function (a, b) { return b.weight - a.weight; });

    var warn = "";
    if (n.lowConfidence) {
      warn = '<div class="warn-badge">⚠ corroboré par &lt; ' + DATA.meta.minCorroboratingSources + ' source(s)</div>';
    } else if (n.singleSourceHub) {
      warn = '<div class="warn-badge">⚠ degré élevé, une seule source</div>';
    }

    var aliases = n.aliases.length
      ? '<div class="field-label">Alias observés</div><div class="chip-list">' +
        n.aliases.map(function (a) { return '<span class="chip">' + escapeHtml(a) + '</span>'; }).join("") + '</div>'
      : "";

    var relHtml = rel.map(function (e) {
      var other = e.s === n ? e.t : e.s;
      return '<div class="rel-item' + (e.lowConfidence ? ' low-conf' : '') + '">' +
        '<div class="rel-head"><span>→ ' + escapeHtml(other.label) + '</span><span>×' + e.weight + '</span></div>' +
        '<div>' + escapeHtml(e.predicates.join(", ")) + '</div>' +
        '<div class="admiralty-row" style="margin-top:4px">' + admiraltyBadgesHtml(e.reliability, e.credibility) + '</div>' +
        (e.snippets[0] ? '<div class="rel-snippet">« ' + escapeHtml(e.snippets[0]) + ' »</div>' : '') +
        '</div>';
    }).join("");

    panelEl.innerHTML =
      '<div class="node-detail">' +
      '<div class="label">' + escapeHtml(n.label) + '</div>' +
      '<span class="community-tag" style="background:' + hexA(communityColor(n.community), 0.18) +
      ';color:' + communityColor(n.community) + '">communauté #' + n.community + '</span>' +
      '<div class="admiralty-row">' + admiraltyBadgesHtml(n.reliability, n.credibility) + '</div>' +
      warn + aliases +
      '<div class="field-label">Mentions</div><div class="field-value mono">' + n.mentions +
      ' · PageRank ' + n.pagerank.toFixed(4) + ' · betweenness ' + n.betweenness.toFixed(4) + '</div>' +
      '<div class="field-label">Sources (' + n.sources.length + ')</div><div class="chip-list">' +
      n.sources.map(function (s) { return '<span class="chip">' + escapeHtml(s) + '</span>'; }).join("") + '</div>' +
      '<div class="field-label">Relations (' + rel.length + ')</div>' + relHtml +
      '</div>';
  }
  renderLegend();

  // ---------------------------------------------------------------------
  // recherche
  // ---------------------------------------------------------------------
  var searchInput = document.getElementById("search-input");
  var searchCount = document.getElementById("search-count");

  searchInput.addEventListener("input", function () {
    searchTerm = normalize(searchInput.value.trim());
    if (!searchTerm) { matchedIds = null; searchCount.textContent = ""; return; }
    var matched = nodes.filter(function (n) { return normalize(n.label).indexOf(searchTerm) !== -1; });
    matchedIds = new Set(matched.map(function (n) { return n.id; }));
    searchCount.textContent = matched.length + " résultat" + (matched.length > 1 ? "s" : "");
    if (matched.length === 1) {
      selectedNode = matched[0];
      renderPanel();
    }
  });
})();
