(function () {
  "use strict";

  const fieldsByType = {
    folder: ["parent", "order", "folder_files"],
    video: ["parent", "order", "content_files", "video_urls"],
    quiz: ["parent", "order", "exams"],
    subjective: ["parent", "order", "exams"],
    practice: ["parent", "order", "exams"],
    document: ["parent", "order", "content_files"],
    image: ["parent", "order", "content_files"],
  };

  function updateRow(select) {
    const row = select.closest(".form-row") || select.closest("tr");
    if (!row) return;

    const type = select.value;
    const visibleFields = new Set(["content_type", "title", ...(fieldsByType[type] || [])]);
    row.querySelectorAll("[name]").forEach((input) => {
      const match = input.name.match(/-(content_type|title|parent|folder_files|content_files|video_urls|exams|order)$/);
      if (!match) return;

      const cell = input.closest(".fieldBox") || input.closest("td") || input.closest(".form-row");
      if (!cell) return;
      cell.hidden = !visibleFields.has(match[1]);
    });
  }

  function initialize(root) {
    root.querySelectorAll('select[name$="-content_type"]').forEach(updateRow);
  }

  function syncFolderPaths(input) {
    const row = input.closest("tr");
    if (!row) return;
    const hidden = row.querySelector('input[name$="-folder_paths"]');
    if (!hidden) return;
    hidden.value = JSON.stringify(Array.from(input.files || []).map((file) => file.webkitRelativePath || file.name));
  }

  document.addEventListener("change", (event) => {
    if (event.target.matches('select[name$="-content_type"]')) updateRow(event.target);
    if (event.target.matches('input[name$="-folder_files"]')) syncFolderPaths(event.target);
  });

  document.addEventListener("formset:added", (event) => initialize(event.target));
  document.addEventListener("click", (event) => {
    if (event.target.closest(".add-row a")) window.setTimeout(() => initialize(document), 0);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initialize(document));
  } else {
    initialize(document);
  }
})();
