(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("propagation-data").textContent);
  var TYPE_COLORS = { original: "#4fb3a9", retweet: "#6fa8d9", quote: "#d99a5b", reply: "#8996a6" };

  function typeColor(t) { return TYPE_COLORS[t] || TYPE_COLORS.reply; }
  function hexA(hex, a) {
    var c = hex.replace("#", "");
    if (c.length === 3) c = c.split("").map(function (ch) { return ch + ch; }).join("");
    var r = parseInt(c.substr(0, 2), 16), g = parseInt(c.substr(2, 2), 16), b = parseInt(c.substr(4, 2), 16);
    return "rgba(" + r + "," + g + "," + b + "," + a + ")";
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function fmtTime(iso) {
    var d = new Date(iso);
    return d.toISOString().replace("T", " ").slice(0, 16) + "Z";
  }

  var allPosts = DATA.posts.map(function (p) { return Object.assign({}, p, { _t: new Date(p.postedAt).getTime() }); });
  var postById = {};
  allPosts.forEach(function (p) { postById[p.id] = p; });
  var treePosts = allPosts.filter(function (p) { return p.reached; });

  var tMin = Math.min.apply(null, allPosts.map(function (p) { return p._t; }));
  var tMax = Math.max.apply(null, allPosts.map(function (p) { return p._t; }));
  var tSpan = Math.max(tMax - tMin, 1);

  var maxLane = Math.max.apply(null, treePosts.map(function (p) { return p.lane || 0; }).concat([0]));
  var maxEngagement = Math.max.apply(null, allPosts.map(function (p) { return p.likes + p.retweets + p.replies; }).concat([1]));

  var timeFilter = null;  // {start, end} en ms, ou null

  // =======================================================================
  // Burst strip
  // =======================================================================
  var burstCanvas = document.getElementById("burst-canvas");
  var burstCtx = burstCanvas.getContext("2d");
  var dpr = Math.max(1, window.devicePixelRatio || 1);
  var N_BUCKETS = 60;
  var bucketCounts = new Array(N_BUCKETS).fill(0);
  allPosts.forEach(function (p) {
    var idx = Math.min(N_BUCKETS - 1, Math.floor(((p._t - tMin) / tSpan) * N_BUCKETS));
    bucketCounts[idx]++;
  });
  var maxBucket = Math.max.apply(null, bucketCounts.concat([1]));

  function resizeBurst() {
    var rect = burstCanvas.getBoundingClientRect();
    burstCanvas.width = rect.width * dpr;
    burstCanvas.height = rect.height * dpr;
    burstCanvas.style.width = rect.width + "px";
    burstCanvas.style.height = rect.height + "px";
    drawBurst();
  }

  function timeToX(t, width, margin) {
    return margin + ((t - tMin) / tSpan) * (width - 2 * margin);
  }

  function drawBurst() {
    var w = burstCanvas.width / dpr, h = burstCanvas.height / dpr;
    var margin = 12;
    burstCtx.save();
    burstCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    burstCtx.clearRect(0, 0, burstCanvas.width, burstCanvas.height);

    // bandes de bursts
    DATA.bursts.forEach(function (b) {
      var x1 = timeToX(new Date(b.start).getTime(), w, margin);
      var x2 = timeToX(new Date(b.end).getTime(), w, margin);
      burstCtx.fillStyle = hexA("#d99a5b", 0.14);
      burstCtx.fillRect(x1, 8, Math.max(2, x2 - x1), h - 24);
    });

    // filtre temporel actif
    if (timeFilter) {
      var fx1 = timeToX(timeFilter.start, w, margin), fx2 = timeToX(timeFilter.end, w, margin);
      burstCtx.strokeStyle = "#4fb3a9";
      burstCtx.lineWidth = 1.5;
      burstCtx.strokeRect(fx1, 8, Math.max(2, fx2 - fx1), h - 24);
    }

    // histogramme
    var bw = (w - 2 * margin) / N_BUCKETS;
    burstCtx.fillStyle = "#8996a6";
    for (var i = 0; i < N_BUCKETS; i++) {
      var bh = (bucketCounts[i] / maxBucket) * (h - 28);
      burstCtx.fillRect(margin + i * bw + 0.5, h - 16 - bh, Math.max(1, bw - 1), bh);
    }

    // axe temps (début/fin)
    burstCtx.fillStyle = "#8996a6";
    burstCtx.font = "10px 'IBM Plex Mono', monospace";
    burstCtx.textAlign = "left";
    burstCtx.fillText(fmtTime(new Date(tMin).toISOString()), margin, h - 4);
    burstCtx.textAlign = "right";
    burstCtx.fillText(fmtTime(new Date(tMax).toISOString()), w - margin, h - 4);
    burstCtx.restore();
  }

  burstCanvas.addEventListener("click", function (ev) {
    var rect = burstCanvas.getBoundingClientRect();
    var margin = 12;
    var frac = (ev.clientX - rect.left - margin) / (rect.width - 2 * margin);
    var clickTime = tMin + frac * tSpan;
    var hitBurst = DATA.bursts.find(function (b) {
      return clickTime >= new Date(b.start).getTime() && clickTime <= new Date(b.end).getTime();
    });
    timeFilter = hitBurst ? { start: new Date(hitBurst.start).getTime(), end: new Date(hitBurst.end).getTime() } : null;
    drawBurst();
    drawTree();
  });

  window.addEventListener("resize", function () { resizeBurst(); resizeTree(); });
  resizeBurst();

  // =======================================================================
  // Arbre horizontal (racine à gauche)
  // =======================================================================
  var treeCanvas = document.getElementById("tree-canvas");
  var treeCtx = treeCanvas.getContext("2d");
  var treeStage = document.getElementById("tree-stage");
  var view = { panX: 40, panY: 0, scale: 1 };
  var DEPTH_SPACING = 90, LANE_SPACING = 26;

  function resizeTree() {
    var rect = treeStage.getBoundingClientRect();
    treeCanvas.width = rect.width * dpr;
    treeCanvas.height = rect.height * dpr;
    treeCanvas.style.width = rect.width + "px";
    treeCanvas.style.height = rect.height + "px";
    view.panY = rect.height / 2 - (maxLane * LANE_SPACING) / 2;
    drawTree();
  }

  function worldToScreen(depth, lane) {
    return [depth * DEPTH_SPACING * view.scale + view.panX, lane * LANE_SPACING * view.scale + view.panY];
  }

  var hoverPost = null, selectedPost = null, panning = false, lastMouse = { x: 0, y: 0 };

  function inTimeFilter(p) {
    return !timeFilter || (p._t >= timeFilter.start && p._t <= timeFilter.end);
  }

  function drawTree() {
    var w = treeCanvas.width / dpr, h = treeCanvas.height / dpr;
    treeCtx.save();
    treeCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    treeCtx.clearRect(0, 0, treeCanvas.width, treeCanvas.height);

    treePosts.forEach(function (p) {
      if (p.parentId == null) return;
      var parent = postById[p.parentId];
      if (!parent || !parent.reached) return;
      var p1 = worldToScreen(parent.depth, parent.lane), p2 = worldToScreen(p.depth, p.lane);
      var dim = !inTimeFilter(p);
      treeCtx.beginPath();
      treeCtx.moveTo(p1[0], p1[1]);
      treeCtx.bezierCurveTo(p1[0] + 30 * view.scale, p1[1], p2[0] - 30 * view.scale, p2[1], p2[0], p2[1]);
      treeCtx.strokeStyle = hexA(typeColor(p.type), dim ? 0.08 : 0.55);
      treeCtx.lineWidth = Math.max(1, 1.3 * view.scale);
      treeCtx.stroke();
    });

    treePosts.forEach(function (p) {
      var pos = worldToScreen(p.depth, p.lane);
      var dim = !inTimeFilter(p);
      var engagement = p.likes + p.retweets + p.replies;
      var r = (3 + (engagement / maxEngagement) * 9) * Math.min(1.6, Math.max(0.7, view.scale));
      treeCtx.beginPath();
      treeCtx.arc(pos[0], pos[1], r, 0, Math.PI * 2);
      treeCtx.fillStyle = hexA(typeColor(p.type), dim ? 0.15 : 1);
      treeCtx.fill();
      if (p === selectedPost) {
        treeCtx.strokeStyle = "#e8ecf1";
        treeCtx.lineWidth = 1.6;
        treeCtx.stroke();
      }
      if (p.id === DATA.meta.seedPostId) {
        treeCtx.strokeStyle = "#e8ecf1";
        treeCtx.lineWidth = 1;
        treeCtx.beginPath();
        treeCtx.arc(pos[0], pos[1], r + 4, 0, Math.PI * 2);
        treeCtx.stroke();
      }
    });

    treeCtx.restore();
  }

  function nodeAt(sx, sy) {
    for (var i = treePosts.length - 1; i >= 0; i--) {
      var p = treePosts[i];
      var pos = worldToScreen(p.depth, p.lane);
      var dx = sx - pos[0], dy = sy - pos[1];
      if (dx * dx + dy * dy <= 100) return p;
    }
    return null;
  }

  var tooltip = document.getElementById("tooltip");

  treeCanvas.addEventListener("mousemove", function (ev) {
    var rect = treeCanvas.getBoundingClientRect();
    var sx = ev.clientX - rect.left, sy = ev.clientY - rect.top;
    if (panning) {
      view.panX += ev.clientX - lastMouse.x;
      view.panY += ev.clientY - lastMouse.y;
      lastMouse = { x: ev.clientX, y: ev.clientY };
      drawTree();
      return;
    }
    var hit = nodeAt(sx, sy);
    hoverPost = hit;
    treeCanvas.style.cursor = hit ? "pointer" : "grab";
    if (hit) {
      tooltip.innerHTML =
        '<div class="t-label">' + escapeHtml(hit.account) + ' · ' + hit.type + '</div>' +
        '<div class="t-meta">' + fmtTime(hit.postedAt) + '<br>' +
        (hit.likes + hit.retweets + hit.replies) + ' engagement</div>';
      tooltip.style.left = (ev.clientX + 14) + "px";
      tooltip.style.top = (ev.clientY + 14) + "px";
      tooltip.style.opacity = 1;
    } else {
      tooltip.style.opacity = 0;
    }
  });

  treeCanvas.addEventListener("mousedown", function (ev) {
    var rect = treeCanvas.getBoundingClientRect();
    var hit = nodeAt(ev.clientX - rect.left, ev.clientY - rect.top);
    if (!hit) {
      panning = true;
      lastMouse = { x: ev.clientX, y: ev.clientY };
      treeCanvas.classList.add("dragging");
    }
  });
  window.addEventListener("mouseup", function () { panning = false; treeCanvas.classList.remove("dragging"); });

  treeCanvas.addEventListener("click", function (ev) {
    var rect = treeCanvas.getBoundingClientRect();
    var hit = nodeAt(ev.clientX - rect.left, ev.clientY - rect.top);
    selectedPost = hit;
    renderPanel();
    drawTree();
  });

  treeCanvas.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var factor = Math.exp(-ev.deltaY * 0.001);
    view.scale = Math.min(4, Math.max(0.2, view.scale * factor));
    drawTree();
  }, { passive: false });

  // =======================================================================
  // panneau latéral
  // =======================================================================
  var panelEl = document.getElementById("panel");

  function renderDefaultPanel() {
    var seedRows = DATA.seedCandidates.slice(0, 5).map(function (c) {
      var mark = c.postId === DATA.meta.seedPostId ? " ★" : "";
      return '<div class="legend-row"><span class="legend-swatch" style="background:transparent"></span>' +
        escapeHtml(c.postId) + mark + ' — score ' + c.score.toFixed(2) +
        ' (' + c.treeSize + ' posts, prof. ' + c.treeDepth + ')</div>';
    }).join("");

    var propRows = DATA.propagators.slice(0, 15).map(function (p) {
      return '<tr><td>' + escapeHtml(p.account) + '</td><td>' + p.nPosts + '</td><td>' +
        p.totalEngagement + '</td><td>' + p.betweenness.toFixed(3) + '</td></tr>';
    }).join("");

    panelEl.innerHTML =
      '<div class="panel-section"><h2>Légende</h2>' +
      '<div class="legend-row"><span class="legend-swatch" style="background:' + TYPE_COLORS.original + '"></span>original</div>' +
      '<div class="legend-row"><span class="legend-swatch" style="background:' + TYPE_COLORS.retweet + '"></span>retweet</div>' +
      '<div class="legend-row"><span class="legend-swatch" style="background:' + TYPE_COLORS.quote + '"></span>quote</div>' +
      '<div class="legend-row"><span class="legend-swatch" style="background:' + TYPE_COLORS.reply + '"></span>reply</div>' +
      '<div class="legend-note">Taille des nœuds = engagement (likes+RT+réponses). ' +
      'Anneau blanc = graine retenue. Clique une bande orange dans la frise du haut ' +
      "pour isoler ce burst dans l'arbre.</div></div>" +

      '<div class="panel-section"><h2>Candidats graine (' + DATA.seedCandidates.length + ')</h2>' + seedRows + '</div>' +

      '<div class="panel-section"><h2>Top propagateurs</h2>' +
      '<table class="prop-table"><thead><tr><th>Compte</th><th>Posts</th><th>Engag.</th><th>Betw.</th></tr></thead>' +
      '<tbody>' + propRows + '</tbody></table></div>';
  }

  function renderPanel() {
    if (!selectedPost) { renderDefaultPanel(); return; }
    var p = selectedPost;
    var childrenCount = treePosts.filter(function (x) { return x.parentId === p.id; }).length;
    panelEl.innerHTML =
      '<div class="post-detail">' +
      '<div class="label">' + escapeHtml(p.account) + '</div>' +
      '<span class="type-badge" style="color:' + typeColor(p.type) + '">' + p.type + '</span>' +
      (p.content ? '<div class="content">« ' + escapeHtml(p.content) + ' »</div>' : '<div class="content" style="opacity:.5">(pas de contenu texte)</div>') +
      '<div class="field-label">Horodatage</div><div class="field-value mono">' + fmtTime(p.postedAt) + '</div>' +
      '<div class="field-label">Engagement</div><div class="field-value mono">' +
      p.likes + ' likes · ' + p.retweets + ' RT · ' + p.replies + ' réponses</div>' +
      "<div class=\"field-label\">Position dans l'arbre</div><div class=\"field-value mono\">" +
      'profondeur ' + p.depth + ' · ' + childrenCount + ' enfant(s) direct(s)</div>' +
      (p.id === DATA.meta.seedPostId ? '<div class="field-label">Rôle</div><div class="field-value">★ Graine retenue pour cette rumeur</div>' : '') +
      '</div>';
  }

  renderDefaultPanel();
  resizeTree();
})();
