(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("entity-data").textContent);
  var COMMUNITY_COLORS = ["#4fb3a9", "#d99a5b", "#8f8fd9", "#d98fa0", "#8fbf8a", "#6fa8d9", "#c2a15c", "#5cb0d9"];
  function communityColor(i) { return COMMUNITY_COLORS[i % COMMUNITY_COLORS.length]; }
  function hexA(hex, a) {
    var c = hex.replace("#", "");
    var r = parseInt(c.substr(0, 2), 16), g = parseInt(c.substr(2, 2), 16), b = parseInt(c.substr(4, 2), 16);
    return "rgba(" + r + "," + g + "," + b + "," + a + ")";
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }

  // -----------------------------------------------------------------------
  // ego-network : layout radial déterministe, l'entité au centre
  // -----------------------------------------------------------------------
  var canvas = document.getElementById("ego-canvas");
  var ctx = canvas.getContext("2d");
  var dpr = Math.max(1, window.devicePixelRatio || 1);
  var tooltip = document.getElementById("tooltip");

  var neighbors = DATA.neighbors.slice().sort(function (a, b) { return b.pagerank - a.pagerank; });
  var relByOther = {};
  DATA.relations.forEach(function (r) { relByOther[r.otherId] = r; });
  var maxWeight = Math.max.apply(null, DATA.relations.map(function (r) { return r.weight; }).concat([1]));

  var positions = {};  // id -> {x, y, r}
  var stage = document.getElementById("ego-stage");

  function layout() {
    var rect = stage.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + "px";
    canvas.style.height = rect.height + "px";

    var cx = rect.width / 2, cy = rect.height / 2;
    var radius = Math.min(rect.width, rect.height) / 2 - 60;
    positions["__center__"] = { x: cx, y: cy, r: 22 };

    var n = neighbors.length || 1;
    neighbors.forEach(function (nb, i) {
      var angle = (i / n) * Math.PI * 2 - Math.PI / 2;
      var rel = relByOther[nb.id];
      var w = rel ? rel.weight : 1;
      var nodeR = 6 + (w / maxWeight) * 12;
      positions[nb.id] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius, r: nodeR };
    });
    draw();
  }

  var hoverId = null;

  function draw() {
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    var center = positions["__center__"];

    neighbors.forEach(function (nb) {
      var p = positions[nb.id];
      var rel = relByOther[nb.id];
      var dim = hoverId && hoverId !== nb.id && hoverId !== "__center__";
      ctx.beginPath();
      ctx.moveTo(center.x, center.y);
      ctx.lineTo(p.x, p.y);
      ctx.lineWidth = Math.max(1, (rel ? rel.weight / maxWeight : 0.3) * 4);
      ctx.strokeStyle = hexA(rel && rel.reliability && "ABC".includes(rel.reliability) ? "#4fb3a9" : "#8996a6", dim ? 0.12 : 0.4);
      if (rel && rel.credibility >= 5) ctx.setLineDash([3, 3]); else ctx.setLineDash([]);
      ctx.stroke();
      ctx.setLineDash([]);
    });

    neighbors.forEach(function (nb) {
      var p = positions[nb.id];
      var dim = hoverId && hoverId !== nb.id;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = hexA(communityColor(nb.community), dim ? 0.25 : 1);
      ctx.fill();
      if (nb.lowConfidence) {
        ctx.setLineDash([2, 2]);
        ctx.strokeStyle = "#d99a5b";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.font = "500 11px 'IBM Plex Sans', sans-serif";
      ctx.fillStyle = hexA("#e8ecf1", dim ? 0.3 : 1);
      ctx.textAlign = p.x < center.x - 5 ? "right" : p.x > center.x + 5 ? "left" : "center";
      var labelX = p.x + (p.x < center.x - 5 ? -p.r - 6 : p.x > center.x + 5 ? p.r + 6 : 0);
      var labelY = p.x >= center.x - 5 && p.x <= center.x + 5 ? p.y - p.r - 8 : p.y + 4;
      ctx.fillText(nb.label, labelX, labelY);
    });

    ctx.beginPath();
    ctx.arc(center.x, center.y, center.r, 0, Math.PI * 2);
    ctx.fillStyle = communityColor(DATA.entity.community);
    ctx.fill();
    ctx.strokeStyle = "#e8ecf1";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.font = "600 12px 'IBM Plex Sans', sans-serif";
    ctx.fillStyle = "#0c1116";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(DATA.entity.label.slice(0, 2).toUpperCase(), center.x, center.y);
    ctx.textBaseline = "alphabetic";

    ctx.restore();
  }

  function hitTest(sx, sy) {
    for (var id in positions) {
      var p = positions[id];
      var dx = sx - p.x, dy = sy - p.y;
      if (dx * dx + dy * dy <= (p.r + 4) * (p.r + 4)) return id;
    }
    return null;
  }

  canvas.addEventListener("mousemove", function (ev) {
    var rect = canvas.getBoundingClientRect();
    var hit = hitTest(ev.clientX - rect.left, ev.clientY - rect.top);
    if (hit !== hoverId) { hoverId = hit; draw(); }
    if (hit && hit !== "__center__") {
      var nb = neighbors.find(function (n) { return n.id === hit; });
      var rel = relByOther[hit];
      tooltip.innerHTML = "<b>" + escapeHtml(nb.label) + "</b><br>" +
        (rel ? escapeHtml(rel.predicates.join(", ")) + " (×" + rel.weight + ")" : "");
      tooltip.style.left = (ev.clientX - rect.left + 12) + "px";
      tooltip.style.top = (ev.clientY - rect.top + 12) + "px";
      tooltip.style.opacity = 1;
    } else {
      tooltip.style.opacity = 0;
    }
  });
  canvas.addEventListener("mouseleave", function () { hoverId = null; tooltip.style.opacity = 0; draw(); });
  canvas.addEventListener("click", function (ev) {
    var rect = canvas.getBoundingClientRect();
    var hit = hitTest(ev.clientX - rect.left, ev.clientY - rect.top);
    if (hit && hit !== "__center__") {
      var card = document.getElementById("rel-" + hit);
      if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  window.addEventListener("resize", layout);
  layout();
})();
