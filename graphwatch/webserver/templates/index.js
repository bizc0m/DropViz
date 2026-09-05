(function () {
  "use strict";

  var dropzone = document.getElementById("dropzone");
  var fileInput = document.getElementById("file-input");
  var sourceSelect = document.getElementById("source-select");
  var urlInput = document.getElementById("url-input");
  var urlBtn = document.getElementById("url-btn");
  var pasteInput = document.getElementById("paste-input");
  var pasteBtn = document.getElementById("paste-btn");
  var logEl = document.getElementById("log");
  var overlay = document.getElementById("drop-overlay");

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }

  function addLogItem(html, cls) {
    var item = document.createElement("div");
    item.className = "log-item " + (cls || "");
    item.innerHTML = html;
    logEl.prepend(item);
    return item;
  }

  function renderResult(item, data) {
    var links = "";
    if (data.notebook_url) links += '<a href="' + data.notebook_url + '" target="_blank">notebook</a>';
    if (data.graph_url) links += '<a href="' + data.graph_url + '" target="_blank">graphe interactif ↗</a>';
    if (data.json_url) links += '<a href="' + data.json_url + '" target="_blank">json</a>';
    if (data.markdown_url) links += '<a href="' + data.markdown_url + '" target="_blank">markdown</a>';
    if (data.graphml_url) links += '<a href="' + data.graphml_url + '" target="_blank">graphml</a>';
    if (data.entity_urls) {
      data.entity_urls.forEach(function (u, i) {
        links += '<a href="' + u + '" target="_blank">fiche ' + (i + 1) + ' ↗</a>';
      });
    }
    if (data.propagation_urls) {
      data.propagation_urls.forEach(function (u, i) {
        links += '<a href="' + u + '" target="_blank">propagation ' + (i + 1) + ' ↗</a>';
      });
    }
    item.className = "log-item ok";
    item.innerHTML =
      '<div>✓ ' + escapeHtml(data.message || "traité") + '</div>' +
      (data.saved && data.saved.length ? '<div class="files">' + data.saved.map(escapeHtml).join(", ") + '</div>' : "") +
      (links ? '<div style="margin-top:8px">' + links + '</div>' : "");
  }

  function renderError(item, message) {
    item.className = "log-item err";
    item.innerHTML = '<div>✗ ' + escapeHtml(message) + '</div>';
  }

  function currentSource() {
    return sourceSelect ? sourceSelect.value : "";
  }

  function uploadFiles(fileList) {
    if (!fileList.length) return;
    var item = addLogItem('<span class="spinner"></span>envoi de ' + fileList.length + ' fichier(s)…', "");
    var form = new FormData();
    form.append("source", currentSource());
    for (var i = 0; i < fileList.length; i++) form.append("files", fileList[i]);

    fetch("/api/upload", { method: "POST", body: form })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok) { renderError(item, res.data.detail || "échec de l'envoi"); return; }
        renderResult(item, res.data);
      })
      .catch(function (e) { renderError(item, String(e)); });
  }

  function fetchUrl(url) {
    url = (url || "").trim();
    if (!url) return;
    var item = addLogItem('<span class="spinner"></span>récupération de ' + escapeHtml(url) + '…', "");
    fetch("/api/fetch-url", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, source: currentSource() }),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok) { renderError(item, res.data.detail || "échec"); return; }
        renderResult(item, res.data);
      })
      .catch(function (e) { renderError(item, String(e)); });
  }

  // extrait une URL d'un drop : un lien glissé depuis l'onglet/la barre d'adresse
  // n'arrive jamais dans dataTransfer.files (ça, c'est réservé aux vrais fichiers) --
  // il faut lire les types texte que le navigateur fournit à la place.
  function urlFromDrop(dataTransfer) {
    if (!dataTransfer) return null;
    var uriList = dataTransfer.getData("text/uri-list");
    if (uriList) return uriList.split("\n").map(function (s) { return s.trim(); }).filter(function (s) { return s && s[0] !== "#"; })[0] || null;
    var text = dataTransfer.getData("text/plain");
    if (text && /^https?:\/\//i.test(text.trim())) return text.trim();
    return null;
  }

  if (dropzone) {
    dropzone.addEventListener("click", function () { fileInput.click(); });
    fileInput.addEventListener("change", function () { uploadFiles(fileInput.files); fileInput.value = ""; });
  }

  // drag & drop global : n'importe où sur la page, pas juste la petite boîte --
  // un compteur d'entrée/sortie évite le clignotement du calque (dragenter/dragleave
  // se déclenchent aussi en survolant les enfants, pas seulement au bord de la page).
  var dragDepth = 0;

  function showOverlay() { if (overlay) overlay.classList.add("active"); }
  function hideOverlay() { if (overlay) overlay.classList.remove("active"); }

  document.addEventListener("dragenter", function (e) {
    e.preventDefault();
    dragDepth++;
    showOverlay();
  });
  document.addEventListener("dragover", function (e) { e.preventDefault(); });
  document.addEventListener("dragleave", function (e) {
    e.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) hideOverlay();
  });
  document.addEventListener("drop", function (e) {
    e.preventDefault();
    dragDepth = 0;
    hideOverlay();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      uploadFiles(e.dataTransfer.files);
      return;
    }
    var url = urlFromDrop(e.dataTransfer);
    if (url) fetchUrl(url);
  });

  if (urlBtn) {
    urlBtn.addEventListener("click", function () { fetchUrl(urlInput.value); urlInput.value = ""; });
    urlInput.addEventListener("keydown", function (e) { if (e.key === "Enter") { fetchUrl(urlInput.value); urlInput.value = ""; } });
  }

  // texte collé en vrac -> même pipeline qu'un fichier déposé : on fabrique un
  // fichier .md en mémoire et on repasse par /api/upload, aucun endpoint à part.
  if (pasteBtn) {
    pasteBtn.addEventListener("click", function () {
      var text = pasteInput.value;
      if (!text.trim()) return;
      var stamp = new Date().toISOString().replace(/[:.]/g, "-");
      var file = new File([text], "colle-" + stamp + ".md", { type: "text/markdown" });
      uploadFiles([file]);
      pasteInput.value = "";
    });
  }
})();
