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
})();
