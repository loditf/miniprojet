(function () {
  "use strict";

  const form = document.getElementById("convert-form");
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const fileNameEl = document.getElementById("file-name");
  const modeSelect = document.getElementById("mode");
  const previewBtn = document.getElementById("preview-btn");
  const downloadBtn = document.getElementById("download-btn");
  const statusEl = document.getElementById("status");
  const previewSection = document.getElementById("preview-section");
  const previewFrame = document.getElementById("preview-frame");
  const previewMeta = document.getElementById("preview-meta");

  let selectedFile = null;

  function setStatus(message, kind) {
    statusEl.textContent = message || "";
    statusEl.className = "status" + (kind ? " " + kind : "");
  }

  function setFile(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("Veuillez sélectionner un fichier PDF.", "error");
      return;
    }
    selectedFile = file;
    fileNameEl.textContent = "✅ " + file.name;
    fileNameEl.hidden = false;
    previewBtn.disabled = false;
    downloadBtn.disabled = false;
    setStatus("");
  }

  // --- Sélection de fichier ---
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener("change", () => setFile(fileInput.files[0]));

  // --- Glisser-déposer ---
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
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    setFile(file);
  });

  function buildFormData() {
    const fd = new FormData();
    fd.append("file", selectedFile);
    fd.append("mode", modeSelect.value);
    return fd;
  }

  function busy(isBusy) {
    previewBtn.disabled = isBusy || !selectedFile;
    downloadBtn.disabled = isBusy || !selectedFile;
  }

  // --- Prévisualisation ---
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setStatus("Aucun fichier sélectionné.", "error");
      return;
    }
    busy(true);
    setStatus("Conversion en cours…", "loading");
    try {
      const resp = await fetch("/api/convert", {
        method: "POST",
        body: buildFormData(),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        throw new Error(data.error || "Échec de la conversion.");
      }
      // Affiche le HTML dans l'iframe en bac à sable.
      previewFrame.srcdoc = data.html;
      previewSection.hidden = false;
      previewMeta.textContent =
        data.page_count + " page(s) · mode " + data.mode;
      let msg = "Conversion réussie.";
      if (data.warnings && data.warnings.length) {
        msg += " " + data.warnings.join(" ");
      }
      setStatus(msg, "ok");
      previewSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setStatus(err.message, "error");
    } finally {
      busy(false);
    }
  });

  // --- Téléchargement ---
  downloadBtn.addEventListener("click", async () => {
    if (!selectedFile) {
      setStatus("Aucun fichier sélectionné.", "error");
      return;
    }
    busy(true);
    setStatus("Préparation du téléchargement…", "loading");
    try {
      const resp = await fetch("/api/download", {
        method: "POST",
        body: buildFormData(),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.error || "Échec du téléchargement.");
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = selectedFile.name.replace(/\.pdf$/i, "") + ".html";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setStatus("Fichier HTML téléchargé.", "ok");
    } catch (err) {
      setStatus(err.message, "error");
    } finally {
      busy(false);
    }
  });
})();
