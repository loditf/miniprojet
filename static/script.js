(function () {
  "use strict";

  // ---------- Onglets ----------
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      tabs.forEach((t) => t.classList.toggle("active", t === tab));
      panels.forEach((p) =>
        p.classList.toggle("active", p.id === "panel-" + target)
      );
    });
  });

  // ---------- Utilitaires ----------
  function setStatus(el, message, kind) {
    el.textContent = message || "";
    el.className = "status" + (kind ? " " + kind : "");
  }

  function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function errorFromResponse(resp) {
    const data = await resp.json().catch(() => ({}));
    return data.error || "Échec de l'opération.";
  }

  /**
   * Câble une dropzone (clic, clavier, glisser-déposer) à un input fichier.
   * onFiles(FileList) est appelé à chaque sélection.
   */
  function wireDropzone(dropzone, input, onFiles) {
    const nameEl = dropzone.querySelector(".file-name");

    function show(files) {
      if (!files || !files.length) return;
      const label =
        files.length === 1
          ? files[0].name
          : files.length + " fichiers sélectionnés";
      nameEl.textContent = "✅ " + label;
      nameEl.hidden = false;
      onFiles(files);
    }

    dropzone.addEventListener("click", () => input.click());
    dropzone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        input.click();
      }
    });
    input.addEventListener("change", () => show(input.files));

    ["dragenter", "dragover"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
      })
    );
    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        show(e.dataTransfer.files);
      }
    });
  }

  // ===================================================================
  // PDF -> HTML
  // ===================================================================
  (function setupPdfToHtml() {
    const form = document.getElementById("html-form");
    const input = document.getElementById("html-file");
    const dropzone = form.querySelector(".dropzone");
    const modeSelect = document.getElementById("mode");
    const previewBtn = form.querySelector('button[type="submit"]');
    const downloadBtn = form.querySelector('[data-action="download-html"]');
    const statusEl = form.querySelector(".status");
    const previewSection = document.getElementById("preview-section");
    const previewFrame = document.getElementById("preview-frame");
    const previewMeta = document.getElementById("preview-meta");
    let file = null;

    wireDropzone(dropzone, input, (files) => {
      file = files[0];
      previewBtn.disabled = false;
      downloadBtn.disabled = false;
      setStatus(statusEl, "");
    });

    function formData() {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mode", modeSelect.value);
      return fd;
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!file) return;
      previewBtn.disabled = downloadBtn.disabled = true;
      setStatus(statusEl, "Conversion en cours…", "loading");
      try {
        const resp = await fetch("/api/convert", { method: "POST", body: formData() });
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || "Échec.");
        previewFrame.srcdoc = data.html;
        previewSection.hidden = false;
        previewMeta.textContent = data.page_count + " page(s) · mode " + data.mode;
        let msg = "Conversion réussie.";
        if (data.warnings && data.warnings.length) msg += " " + data.warnings.join(" ");
        setStatus(statusEl, msg, "ok");
        previewSection.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        setStatus(statusEl, err.message, "error");
      } finally {
        previewBtn.disabled = downloadBtn.disabled = !file;
      }
    });

    downloadBtn.addEventListener("click", async () => {
      if (!file) return;
      previewBtn.disabled = downloadBtn.disabled = true;
      setStatus(statusEl, "Préparation du téléchargement…", "loading");
      try {
        const resp = await fetch("/api/download", { method: "POST", body: formData() });
        if (!resp.ok) throw new Error(await errorFromResponse(resp));
        triggerDownload(await resp.blob(), file.name.replace(/\.pdf$/i, "") + ".html");
        setStatus(statusEl, "Fichier HTML téléchargé.", "ok");
      } catch (err) {
        setStatus(statusEl, err.message, "error");
      } finally {
        previewBtn.disabled = downloadBtn.disabled = !file;
      }
    });
  })();

  // ===================================================================
  // PNG -> PDF
  // ===================================================================
  (function setupImagesToPdf() {
    const form = document.getElementById("img-form");
    const input = document.getElementById("img-files");
    const dropzone = form.querySelector(".dropzone");
    const submitBtn = form.querySelector('button[type="submit"]');
    const statusEl = form.querySelector(".status");
    let files = null;

    wireDropzone(dropzone, input, (selected) => {
      files = selected;
      submitBtn.disabled = false;
      setStatus(statusEl, "");
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!files || !files.length) return;
      submitBtn.disabled = true;
      setStatus(statusEl, "Création du PDF…", "loading");
      try {
        const fd = new FormData();
        Array.from(files).forEach((f) => fd.append("images", f));
        const resp = await fetch("/api/images-to-pdf", { method: "POST", body: fd });
        if (!resp.ok) throw new Error(await errorFromResponse(resp));
        triggerDownload(await resp.blob(), "images.pdf");
        setStatus(statusEl, files.length + " image(s) assemblée(s) → images.pdf", "ok");
      } catch (err) {
        setStatus(statusEl, err.message, "error");
      } finally {
        submitBtn.disabled = !files;
      }
    });
  })();

  // ===================================================================
  // PDF -> PNG
  // ===================================================================
  (function setupPdfToPng() {
    const form = document.getElementById("pdfpng-form");
    const input = document.getElementById("pdfpng-file");
    const dropzone = form.querySelector(".dropzone");
    const submitBtn = form.querySelector('button[type="submit"]');
    const statusEl = form.querySelector(".status");
    const dpi = document.getElementById("dpi");
    const dpiValue = document.getElementById("dpi-value");
    let file = null;

    dpi.addEventListener("input", () => {
      dpiValue.textContent = dpi.value;
    });

    wireDropzone(dropzone, input, (files) => {
      file = files[0];
      submitBtn.disabled = false;
      setStatus(statusEl, "");
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!file) return;
      submitBtn.disabled = true;
      setStatus(statusEl, "Rendu en PNG…", "loading");
      try {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("dpi", dpi.value);
        const resp = await fetch("/api/pdf-to-images", { method: "POST", body: fd });
        if (!resp.ok) throw new Error(await errorFromResponse(resp));
        const blob = await resp.blob();
        const stem = file.name.replace(/\.pdf$/i, "");
        const isZip = blob.type.indexOf("zip") !== -1;
        triggerDownload(blob, stem + (isZip ? "-png.zip" : ".png"));
        setStatus(
          statusEl,
          isZip ? "PDF rendu → archive ZIP téléchargée." : "PDF rendu → PNG téléchargé.",
          "ok"
        );
      } catch (err) {
        setStatus(statusEl, err.message, "error");
      } finally {
        submitBtn.disabled = !file;
      }
    });
  })();

  // ===================================================================
  // ÉDITEUR PDF
  // ===================================================================
  (function setupEditor() {
    const form = document.getElementById("editor-form");
    const input = document.getElementById("editor-file");
    const dropzone = form.querySelector(".dropzone");
    const statusEl = form.querySelector(".status");
    const workspace = document.getElementById("editor-workspace");
    const grid = document.getElementById("page-grid");
    const ovPage = document.getElementById("ov-page");
    const overlayList = document.getElementById("overlay-list");
    const fieldsCard = document.getElementById("fields-card");
    const fieldsList = document.getElementById("fields-list");
    const appendInput = document.getElementById("append-files");
    const appendInfo = document.getElementById("append-info");
    const applyBtn = document.getElementById("apply-btn");
    const resultEl = document.getElementById("editor-result");

    let file = null;          // File object du PDF d'origine
    let pages = [];           // [{src, rotate, deleted}] dans l'ordre d'affichage
    let overlays = [];        // [{page, text, x, y, size, color, opacity, rotate}]

    wireDropzone(dropzone, input, (files) => {
      file = files[0];
      loadDocument();
    });

    async function loadDocument() {
      setStatus(statusEl, "Analyse du PDF…", "loading");
      workspace.hidden = true;
      try {
        const fd = new FormData();
        fd.append("file", file);
        const resp = await fetch("/api/pdf/inspect", { method: "POST", body: fd });
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || "Échec.");
        pages = data.pages.map((p) => ({ src: p.index, rotate: 0, deleted: false, info: p }));
        overlays = [];
        renderPages();
        renderOverlayPageOptions();
        renderOverlayList();
        renderFields(data.fields);
        workspace.hidden = false;
        let msg = data.page_count + " page(s) chargée(s).";
        if (data.warnings && data.warnings.length) msg += " " + data.warnings.join(" ");
        setStatus(statusEl, msg, "ok");
      } catch (err) {
        setStatus(statusEl, err.message, "error");
      }
    }

    // ---------- Pages : rendu + drag-and-drop ----------
    function renderPages() {
      grid.innerHTML = "";
      pages.forEach((page, position) => {
        const card = document.createElement("div");
        card.className = "page-card" + (page.deleted ? " deleted" : "");
        card.draggable = true;
        card.dataset.pos = position;

        const badge = page.rotate
          ? `<span class="rot-badge">${page.rotate}°</span>`
          : "";
        card.innerHTML =
          badge +
          `<img class="thumb" src="data:image/png;base64,${page.info.thumbnail}" alt="page ${page.src + 1}" style="transform:rotate(${page.rotate}deg)">` +
          `<div class="pg-label">page ${page.src + 1}</div>` +
          `<div class="pg-tools">
             <button type="button" data-act="rotate" title="Pivoter">🔄</button>
             <button type="button" data-act="delete" title="Supprimer / restaurer">${page.deleted ? "↩️" : "🗑️"}</button>
           </div>`;

        card.querySelector('[data-act="rotate"]').addEventListener("click", (e) => {
          e.stopPropagation();
          page.rotate = (page.rotate + 90) % 360;
          renderPages();
        });
        card.querySelector('[data-act="delete"]').addEventListener("click", (e) => {
          e.stopPropagation();
          page.deleted = !page.deleted;
          renderPages();
        });

        // Drag-and-drop pour réordonner.
        card.addEventListener("dragstart", (e) => {
          card.classList.add("dragging");
          e.dataTransfer.setData("text/plain", position);
        });
        card.addEventListener("dragend", () => card.classList.remove("dragging"));
        card.addEventListener("dragover", (e) => {
          e.preventDefault();
          card.classList.add("drag-over");
        });
        card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
        card.addEventListener("drop", (e) => {
          e.preventDefault();
          card.classList.remove("drag-over");
          const from = parseInt(e.dataTransfer.getData("text/plain"), 10);
          const to = position;
          if (from === to || isNaN(from)) return;
          const moved = pages.splice(from, 1)[0];
          pages.splice(to, 0, moved);
          renderPages();
        });

        grid.appendChild(card);
      });
    }

    // ---------- Surimpressions ----------
    function renderOverlayPageOptions() {
      ovPage.innerHTML = pages
        .map((p) => `<option value="${p.src}">page ${p.src + 1}</option>`)
        .join("");
    }

    function renderOverlayList() {
      overlayList.innerHTML = "";
      overlays.forEach((ov, i) => {
        const li = document.createElement("li");
        li.innerHTML =
          `<span>« ${ov.text} » — page ${ov.page + 1}, ${ov.size}px, ${Math.round(
            ov.opacity * 100
          )}%, ${ov.rotate}°</span>`;
        const del = document.createElement("button");
        del.textContent = "✕";
        del.title = "Retirer";
        del.addEventListener("click", () => {
          overlays.splice(i, 1);
          renderOverlayList();
        });
        li.appendChild(del);
        overlayList.appendChild(li);
      });
    }

    // Sliders d'aperçu des valeurs.
    const bind = (id, valId, fmt) => {
      const el = document.getElementById(id);
      const val = document.getElementById(valId);
      el.addEventListener("input", () => (val.textContent = fmt(el.value)));
    };
    bind("ov-opacity", "ov-op-val", (v) => v);
    bind("ov-x", "ov-x-val", (v) => Math.round(v * 100) + "%");
    bind("ov-y", "ov-y-val", (v) => Math.round(v * 100) + "%");

    document.getElementById("ov-add").addEventListener("click", () => {
      const text = document.getElementById("ov-text").value.trim();
      if (!text) {
        setStatus(resultEl, "Saisissez un texte à ajouter.", "error");
        return;
      }
      overlays.push({
        page: parseInt(ovPage.value, 10),
        text: text,
        x: parseFloat(document.getElementById("ov-x").value),
        y: parseFloat(document.getElementById("ov-y").value),
        size: parseInt(document.getElementById("ov-size").value, 10),
        color: document.getElementById("ov-color").value,
        opacity: parseFloat(document.getElementById("ov-opacity").value),
        rotate: parseInt(document.getElementById("ov-rotate").value, 10),
      });
      document.getElementById("ov-text").value = "";
      renderOverlayList();
      setStatus(resultEl, "");
    });

    // ---------- Champs de formulaire ----------
    function renderFields(fields) {
      fieldsList.innerHTML = "";
      if (!fields || !fields.length) {
        fieldsCard.hidden = true;
        return;
      }
      fieldsCard.hidden = false;
      fields.forEach((f) => {
        const label = document.createElement("label");
        label.textContent = f.name + " (page " + (f.page_index + 1) + ")";
        const inp = document.createElement("input");
        inp.type = "text";
        inp.value = f.value || "";
        inp.dataset.field = f.name;
        label.appendChild(inp);
        fieldsList.appendChild(label);
      });
    }

    appendInput.addEventListener("change", () => {
      const n = appendInput.files.length;
      appendInfo.textContent = n
        ? n + " PDF seront ajoutés à la fin."
        : "";
    });

    // ---------- Application ----------
    function buildSpec() {
      const kept = pages.filter((p) => !p.deleted);
      const fields = {};
      fieldsList.querySelectorAll("input[data-field]").forEach((inp) => {
        if (inp.value !== "") fields[inp.dataset.field] = inp.value;
      });
      return {
        pages: kept.map((p) => ({ src: p.src, rotate: p.rotate })),
        overlays: overlays,
        fields: fields,
      };
    }

    applyBtn.addEventListener("click", async () => {
      if (!file) return;
      if (pages.every((p) => p.deleted)) {
        setStatus(resultEl, "Au moins une page doit être conservée.", "error");
        return;
      }
      applyBtn.disabled = true;
      setStatus(resultEl, "Application des modifications…", "loading");
      try {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("spec", JSON.stringify(buildSpec()));
        Array.from(appendInput.files).forEach((f) => fd.append("append", f));
        const resp = await fetch("/api/pdf/edit", { method: "POST", body: fd });
        if (!resp.ok) throw new Error(await errorFromResponse(resp));
        triggerDownload(await resp.blob(), file.name.replace(/\.pdf$/i, "") + "-edite.pdf");
        setStatus(resultEl, "PDF édité téléchargé.", "ok");
      } catch (err) {
        setStatus(resultEl, err.message, "error");
      } finally {
        applyBtn.disabled = false;
      }
    });
  })();
})();
