// SPDX-License-Identifier: AGPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Yi Zou <zouyi.nju@gmail.com> and GFA Editor contributors

let cy = null;
let graphState = null;
let currentLayout = "cose";
let toastTimer = null;
let pendingRename = null;
let pendingDuplicateSource = null;
let pendingSelectNodeId = null;
let pendingMergeLayout = null;
let repeatResolutionContext = null;
let serverSavePathAuto = true;
let serverSaveSourceName = null;

const alignmentPresets = {
  blastn: [
    {
      value: "repeat",
      label: "Repeat/contig",
      args: '-task megablast -evalue 1e-10 -perc_identity 80 -max_target_seqs 25 -outfmt "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore"',
      format: "blast6",
    },
    {
      value: "sensitive",
      label: "Sensitive DNA",
      args: '-task blastn -evalue 1e-5 -word_size 11 -dust no -outfmt "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore"',
      format: "blast6",
    },
  ],
  minimap2: [
    {
      value: "ont",
      label: "ONT long reads",
      args: "-x map-ont -c --secondary=yes",
      format: "paf",
    },
    {
      value: "hifi",
      label: "PacBio HiFi",
      args: "-x map-hifi -c --secondary=yes",
      format: "paf",
    },
    {
      value: "asm5",
      label: "Assembly/repeat",
      args: "-x asm5 -c --secondary=yes",
      format: "paf",
    },
  ],
};

const bandageState = {
  selected: null,
  selectedNodeIds: new Set(),
  selectedEdgeIds: new Set(),
  nodes: new Map(),
  visibleNodeIds: new Set(),
  visibleEdgeIds: new Set(),
  transform: { x: 0, y: 0, scale: 1 },
  pointer: { down: false, mode: "pan", id: null, lastX: 0, lastY: 0 },
  layoutSeed: 1,
  lengthScale: null,
};

const randomColorById = new Map();
const alignmentQuerySettings = new Map();
const randomPalette = [
  "#2fa4c8",
  "#4bcc4b",
  "#a7cf3f",
  "#665fd4",
  "#d940c9",
  "#05c986",
  "#bfca3e",
  "#8d4bd3",
  "#3347ff",
  "#7d6f55",
];
const alignmentPalette = [
  "#a51f5d",
  "#1976d2",
  "#2e7d32",
  "#f57c00",
  "#6a1b9a",
];

const SVG_NS = "http://www.w3.org/2000/svg";
const ALIGNMENT_UNHIT_NODE_COLOR = "#dbe1d4";
const ALIGNMENT_UNHIT_LINK_COLOR = "#aab5a5";
const ALIGNMENT_HIT_BACKGROUND_COLOR = "#bfd7c5";
const ALIGNMENT_HIT_NODE_COLOR = "#edbdb4";
const ALIGNMENT_HIT_LINK_COLOR = "#dda69f";
const ALIGNMENT_HIT_BORDER_COLOR = "#b96960";
const BANDAGE_LAYOUTS = new Set(["bandage_native"]);
const BANDAGE_MODE_CONFIGS = {
  bandage_native: {
    seedIdealEdgeLength: 48,
    seedNodeRepulsion: 14500,
    seedComponentSpacing: 120,
    seedScale: 0.98,
    coseIdealEdgeLength: 44,
    coseNodeRepulsion: 11000,
    coseComponentSpacing: 100,
    springStrength: 0.9,
    springTorqueStrength: 0.34,
    maxRotation: 0.12,
    centerWidthFactor: 8.2,
    centerLengthFactor: 0.32,
    centerStrength: 0.18,
    capsuleStrength: 1.55,
    capsulePadding: 42,
    linkNodeStrength: 0.12,
    linkNodePadding: 18,
    radialExpansionStrength: 0.048,
    radialExpansionRadiusFactor: 150,
    radialExpansionMinRadius: 380,
    flexibleGlyphs: true,
    segmentSpringStrength: 1.18,
    restShapeStrength: 0.1,
    flexibleGlyphStrength: 1.25,
    flexiblePointMaxMove: 22,
    pointRepulsionStrength: 0.42,
    pointRepulsionPadding: 30,
    segmentCrossingStrength: 18,
    nativeFoldAmplitudeFactor: 0.35,
    targetTurnAngleDeg: 148,
    turnAngleMinDeg: 118,
    turnAngleMaxDeg: 170,
    turnAngleStrength: 0.3,
    turnAngleConstraintPasses: 0,
    endpointRefineIterations: 85,
    endpointRefineStrength: 1.8,
    segmentConstraintPasses: 5,
    redrawCandidatesSmall: 1,
    redrawCandidatesMedium: 1,
    redrawCandidatesLarge: 1,
    redrawJitterRadius: 95,
    simulationIterationsSmall: 370,
    simulationIterationsLarge: 210,
    simulationChargeDistanceMax: 260,
    simulationCollisionRadiusFactor: 2.0,
    simulationCollisionStrength: 0.36,
    simulationInternalStrength: 0.2,
    simulationLinkStrength: 0.92,
    simulationRepulsionStrength: 3900,
    simulationSegmentCollisionStrength: 0.52,
    simulationSegmentCollisionEvery: 3,
    simulationSegmentPadding: 14,
    simulationSameNodeRepulsionFactor: 0.62,
    simulationCenterStrength: 0.0008,
    simulationMaxMove: 22,
    simulationUntanglePasses: 72,
    simulationUntangleEvery: 2,
    simulationUntangleCrossingForce: 20,
    simulationUntangleOverlapStrength: 0.3,
    simulationUntangleMaxMove: 24,
    simulationRetightenPasses: 26,
    virtualCose: false,
    virtualCoseIterationsSmall: 320,
    virtualCoseIterationsLarge: 180,
    virtualCoseNodeRepulsion: 17000,
    virtualCoseSegmentElasticity: 95,
    virtualCoseLinkElasticity: 520,
    virtualCoseGravity: 0.045,
    simulationCoordinateLimit: 5000,
    overlapResolvePasses: 0,
    overlapResolvePadding: 5,
    overlapResolveStrength: 0.12,
    crossingResolveStrength: 8,
    overlapPenalty: 1,
    intersectionPenalty: 9000,
    linkLengthPenalty: 0.32,
    areaPenalty: 0.0008,
    angleRelaxStep: 0.14,
    angleRelaxFinal: 0.74,
    maxMove: 32,
    bendMultiplier: 1.9,
    bendScale: 0.34,
    bendMax: 230,
    segmentGlyphs: true,
    glyphSegmentLength: 44,
    glyphSegmentMaxLength: 72,
    glyphSegmentMin: 2,
    glyphSegmentMax: 28,
    polylineKinkScale: 0.08,
    polylineKinkMin: 4,
    polylineKinkMax: 34,
    linkBendMin: 4,
    linkBendMax: 18,
    linkBendDistanceFactor: 0.16,
    linkBendSeedFactor: 9,
    maxGlyphSmall: 560,
    maxGlyphMedium: 420,
    maxGlyphLarge: 300,
    minGlyphSmall: 30,
    minGlyphLarge: 22,
    fallbackGlyphMin: 30,
    fallbackGlyphMax: 360,
    fallbackGlyphMultiplier: 1.15,
    linkDistanceSmall: 4,
    linkDistanceMedium: 4,
    linkDistanceLarge: 4,
    iterationsSmall: 400,
    iterationsLarge: 220,
  },
};

const dom = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  setupAlignmentPresets();
  setupCollapsiblePanels();
  bindEvents();
  setupToolbarTooltips();
  resetDetails();
  renderStats(null);
  renderHistory({});
  if (window.lucide) {
    window.lucide.createIcons();
  }
  if (!window.cytoscape || !window.d3) {
    setStatus("Cytoscape or D3 failed to load. Check local vendor files.");
  }
  loadServerFiles();
  tryLoadExistingGraph();
});

function cacheDom() {
  const ids = [
    "gfa-upload-form",
    "gfa-file",
    "gfa-file-label",
    "keep-sequences",
    "export-format",
    "export-menu-toggle",
    "export-menu-panel",
    "quick-export-button",
    "export-svg-button",
    "history-file",
    "history-file-label",
    "apply-history-button",
    "render-gfa-file",
    "render-gfa-file-label",
    "render-history-file",
    "render-history-file-label",
    "render-history-button",
    "infer-old-gfa-file",
    "infer-old-gfa-file-label",
    "infer-new-gfa-file",
    "infer-new-gfa-file-label",
    "infer-history-button",
    "blast-upload-form",
    "alignment-tool",
    "alignment-preset",
    "alignment-extra-args",
    "alignment-result-format",
    "alignment-target-role",
    "alignment-command",
    "query-fasta-file",
    "query-fasta-file-label",
    "alignment-run-button",
    "alignment-read-select",
    "alignment-show-background",
    "alignment-query-list",
    "blast-file",
    "blast-file-label",
    "blast-upload-button",
    "server-data-dir",
    "server-file-select",
    "server-refresh-button",
    "server-load-button",
    "server-save-path",
    "server-save-button",
    "sftp-host",
    "sftp-port",
    "sftp-username",
    "sftp-password",
    "sftp-remote-path",
    "sftp-download-button",
    "sftp-upload-button",
    "auto-redraw",
    "draw-scope",
    "draw-graph-button",
    "draw-graph-toolbar-button",
    "graph-drawing-toggle",
    "graph-drawing-panel",
    "graph-display-toggle",
    "graph-display-panel",
    "graph-filter-toggle",
    "graph-filter-panel",
    "server-files-toggle",
    "server-files-panel",
    "undo-button",
    "redo-button",
    "export-button",
    "export-selected-button",
    "export-history-button",
    "fit-button",
    "delete-selected-button",
    "delete-all-selected-button",
    "duplicate-node-button",
    "merge-link-button",
    "rotate-circular-button",
    "repeat-resolution-a-button",
    "repeat-resolution-b-button",
    "node-search",
    "find-node-button",
    "min-depth",
    "color-mode",
    "zoom-level",
    "node-size-scale",
    "node-width",
    "link-width-scale",
    "label-name",
    "label-length",
    "label-depth",
    "label-blast",
    "show-link-labels",
    "text-outline",
    "stats-grid",
    "depth-histogram",
    "graph",
    "cy-layer",
    "bandage-svg",
    "empty-state",
    "visible-count",
    "status-text",
    "source-name",
    "selection-kind",
    "selection-details",
    "clear-history-button",
    "history-list",
    "toast",
  ];
  ids.forEach((id) => {
    dom[toCamel(id)] = document.getElementById(id);
  });
  dom.layoutButtons = Array.from(document.querySelectorAll(".layout-button"));
}

function setupAlignmentPresets() {
  if (!dom.alignmentTool || !dom.alignmentPreset) return;
  populateAlignmentPresetOptions();
  updateAlignmentCommandPreview();
}

function populateAlignmentPresetOptions() {
  const tool = dom.alignmentTool?.value || "blastn";
  const presets = alignmentPresets[tool] || alignmentPresets.blastn;
  dom.alignmentPreset.replaceChildren(
    ...presets.map((preset) => optionEl(preset.value, preset.label)),
  );
  const active = presets[0];
  if (active) {
    dom.alignmentPreset.value = active.value;
    dom.alignmentExtraArgs.value = active.args;
    dom.alignmentResultFormat.value = active.format;
  }
}

function getAlignmentPreset() {
  const tool = dom.alignmentTool?.value || "blastn";
  const presets = alignmentPresets[tool] || alignmentPresets.blastn;
  return presets.find((preset) => preset.value === dom.alignmentPreset?.value) || presets[0];
}

function setupCollapsiblePanels() {
  document.querySelectorAll(".sidebar .panel, .inspector .panel").forEach((panel) => {
    const titleRow = panel.querySelector(":scope > .panel-title-row");
    const heading = panel.querySelector(":scope > h2") || titleRow?.querySelector("h2");
    if (!heading || panel.querySelector(":scope > .panel-body")) return;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "panel-toggle";
    const title = document.createElement("span");
    title.textContent = heading.textContent || "";
    const icon = document.createElement("i");
    icon.setAttribute("data-lucide", "chevron-down");
    toggle.append(title, icon);

    const body = document.createElement("div");
    body.className = "panel-body";
    const anchor = titleRow || heading;
    let sibling = anchor.nextSibling;
    while (sibling) {
      const next = sibling.nextSibling;
      body.appendChild(sibling);
      sibling = next;
    }

    if (titleRow) {
      heading.replaceWith(toggle);
      panel.appendChild(body);
    } else {
      heading.replaceWith(toggle);
      panel.appendChild(body);
    }

    toggle.addEventListener("click", () => {
      panel.classList.toggle("collapsed");
    });
  });
}

function setupToolbarTooltips() {
  const toolbarButtons = [
    ...document.querySelectorAll(".layout-mode-group > button"),
    ...document.querySelectorAll(".graph-toolbar-left > .display-menu > button"),
    ...document.querySelectorAll(".graph-actions > button, .graph-actions > .display-menu > button"),
    ...document.querySelectorAll(".graph-export-actions > button, .graph-export-actions > .display-menu > button"),
  ];
  toolbarButtons.forEach((button) => {
    const label = button.getAttribute("aria-label")
      || button.getAttribute("title")
      || button.textContent.trim();
    if (label) {
      button.dataset.tooltip = label;
      button.removeAttribute("title");
    }
  });
}

function bindEvents() {
  dom.gfaFile.addEventListener("change", () => {
    dom.gfaFileLabel.textContent = dom.gfaFile.files[0]?.name || "Choose GFA";
  });

  dom.historyFile.addEventListener("change", () => {
    dom.historyFileLabel.textContent = dom.historyFile.files[0]?.name || "Choose history JSON";
    updateHistoryFileButtons();
  });

  dom.renderGfaFile.addEventListener("change", () => {
    dom.renderGfaFileLabel.textContent = dom.renderGfaFile.files[0]?.name || "Input GFA";
    updateHistoryFileButtons();
  });

  dom.renderHistoryFile.addEventListener("change", () => {
    dom.renderHistoryFileLabel.textContent = dom.renderHistoryFile.files[0]?.name || "Input history JSON";
    updateHistoryFileButtons();
  });

  dom.inferOldGfaFile.addEventListener("change", () => {
    dom.inferOldGfaFileLabel.textContent = dom.inferOldGfaFile.files[0]?.name || "Old GFA";
    updateHistoryFileButtons();
  });

  dom.inferNewGfaFile.addEventListener("change", () => {
    dom.inferNewGfaFileLabel.textContent = dom.inferNewGfaFile.files[0]?.name || "New GFA";
    updateHistoryFileButtons();
  });

  dom.blastFile.addEventListener("change", () => {
    dom.blastFileLabel.textContent = dom.blastFile.files[0]?.name || "Choose alignment result";
    updateAlignmentButtons();
  });
  dom.queryFastaFile.addEventListener("change", () => {
    dom.queryFastaFileLabel.textContent = dom.queryFastaFile.files[0]?.name || "Choose query";
    updateAlignmentCommandPreview();
    updateAlignmentButtons();
  });
  dom.alignmentTool.addEventListener("change", () => {
    populateAlignmentPresetOptions();
    updateAlignmentCommandPreview();
  });
  dom.alignmentPreset.addEventListener("change", () => {
    const preset = getAlignmentPreset();
    if (preset) {
      dom.alignmentExtraArgs.value = preset.args;
      dom.alignmentResultFormat.value = preset.format;
    }
    updateAlignmentCommandPreview();
  });
  [dom.alignmentExtraArgs, dom.alignmentResultFormat, dom.alignmentTargetRole].forEach((input) => {
    input.addEventListener("input", updateAlignmentCommandPreview);
    input.addEventListener("change", updateAlignmentCommandPreview);
  });
  dom.alignmentRunButton.addEventListener("click", runAlignmentFromQueryFile);
  dom.alignmentReadSelect.addEventListener("change", selectAlignmentRead);
  dom.alignmentShowBackground.addEventListener("change", refreshVisualProperties);
  dom.alignmentQueryList.addEventListener("change", (event) => {
    const target = event.target;
    const row = target.closest?.("[data-query-id]");
    if (!row) return;
    const settings = ensureAlignmentQuerySettings(row.dataset.queryId);
    if (target.matches('input[type="checkbox"][data-role="visible"]')) {
      settings.visible = target.checked;
    }
    if (target.matches('input[type="checkbox"][data-role="background"]')) {
      settings.background = target.checked;
      settings.backgroundTouched = true;
    }
    if (target.matches('input[type="color"]')) {
      settings.color = target.value;
    }
    refreshVisualProperties();
  });
  dom.alignmentQueryList.addEventListener("input", (event) => {
    const target = event.target;
    const row = target.closest?.("[data-query-id]");
    if (!row || !target.matches('input[type="color"]')) return;
    ensureAlignmentQuerySettings(row.dataset.queryId).color = target.value;
    refreshVisualProperties();
  });

  dom.serverRefreshButton.addEventListener("click", loadServerFiles);
  dom.serverFileSelect.addEventListener("change", updateServerFileButtons);
  dom.serverLoadButton.addEventListener("click", loadSelectedServerFile);
  dom.serverSavePath.addEventListener("input", () => {
    serverSavePathAuto = false;
  });
  dom.serverSaveButton.addEventListener("click", saveGraphToServer);
  [dom.sftpHost, dom.sftpPort, dom.sftpUsername, dom.sftpPassword, dom.sftpRemotePath].forEach((input) => {
    input.addEventListener("input", updateSftpButtons);
  });
  dom.sftpDownloadButton.addEventListener("click", downloadFromSftp);
  dom.sftpUploadButton.addEventListener("click", uploadToSftp);

  dom.gfaUploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = dom.gfaFile.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("keep_sequences", dom.keepSequences.checked ? "true" : "false");
    await callAndRender("/api/upload", {
      method: "POST",
      body: formData,
      loading: "Parsing GFA...",
      success: "GFA loaded",
      relayout: true,
    });
  });

  dom.blastUploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = dom.blastFile.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("format", dom.alignmentResultFormat.value);
    formData.append("target_role", dom.alignmentTargetRole.value);
    await callAndRender("/api/upload_alignment", {
      method: "POST",
      body: formData,
      loading: "Importing alignments...",
      success: "Alignments imported",
      relayout: shouldAutoRedraw(),
    });
    showAlignmentVisualMode();
  });

  dom.undoButton.addEventListener("click", () => postUndoRedoAction("/api/undo", "Undo complete"));
  dom.redoButton.addEventListener("click", () => postUndoRedoAction("/api/redo", "Redo complete"));
  dom.clearHistoryButton.addEventListener("click", clearOperationHistory);
  dom.quickExportButton.addEventListener("click", quickDownloadExport);
  dom.exportMenuToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleExportMenuPanel();
  });
  dom.exportMenuPanel.addEventListener("click", (event) => event.stopPropagation());
  dom.exportButton.addEventListener("click", downloadExport);
  dom.exportSvgButton.addEventListener("click", () => saveSvgExport({ selectedOnly: false, quick: false }));
  dom.exportSelectedButton.addEventListener("click", downloadSelectedExport);
  dom.exportHistoryButton.addEventListener("click", downloadEditHistory);
  dom.applyHistoryButton.addEventListener("click", applyHistoryFile);
  dom.renderHistoryButton.addEventListener("click", renderHistoryFromFiles);
  dom.inferHistoryButton.addEventListener("click", inferHistoryFromFiles);
  dom.fitButton.addEventListener("click", () => {
    if (isTwinMode()) {
      if (cy) cy.fit(cy.elements(":visible"), 40);
      fitBandageToView();
    } else if (isBandageMode()) {
      fitBandageToView();
    } else if (cy) {
      cy.fit(undefined, 40);
    }
  });
  dom.drawGraphButton.addEventListener("click", drawGraphManually);
  dom.drawGraphToolbarButton.addEventListener("click", drawGraphManually);
  dom.graphDrawingToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleGraphDrawingPanel();
  });
  dom.graphDrawingPanel.addEventListener("click", (event) => event.stopPropagation());
  dom.graphDisplayToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleGraphDisplayPanel();
  });
  dom.graphDisplayPanel.addEventListener("click", (event) => event.stopPropagation());
  dom.graphFilterToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleGraphFilterPanel();
  });
  dom.graphFilterPanel.addEventListener("click", (event) => event.stopPropagation());
  dom.serverFilesToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleServerFilesPanel();
  });
  dom.serverFilesPanel.addEventListener("click", (event) => event.stopPropagation());
  document.addEventListener("click", () => {
    toggleExportMenuPanel(false);
    toggleGraphDrawingPanel(false);
    toggleGraphDisplayPanel(false);
    toggleGraphFilterPanel(false);
    toggleServerFilesPanel(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      toggleExportMenuPanel(false);
      toggleGraphDrawingPanel(false);
      toggleGraphDisplayPanel(false);
      toggleGraphFilterPanel(false);
      toggleServerFilesPanel(false);
    }
  });
  dom.deleteSelectedButton.addEventListener("click", deleteSelected);
  dom.deleteAllSelectedButton.addEventListener("click", deleteAllSelected);
  dom.duplicateNodeButton.addEventListener("click", duplicateSelectedNode);
  dom.mergeLinkButton.addEventListener("click", mergeSelectedLink);
  dom.rotateCircularButton.addEventListener("click", rotateSelectedCircularStart);
  dom.repeatResolutionAButton.addEventListener("click", () => runRepeatResolution("A"));
  dom.repeatResolutionBButton.addEventListener("click", () => runRepeatResolution("B"));

  dom.nodeSearch.addEventListener("input", applyFilters);
  dom.findNodeButton.addEventListener("click", findNodes);
  dom.minDepth.addEventListener("input", applyFilters);
  dom.colorMode.addEventListener("change", () => {
    refreshVisualProperties();
    applyFilters();
  });
  dom.exportFormat.addEventListener("change", () => {
    if (serverSavePathAuto) {
      updateServerSavePath();
    }
    updateServerFileButtons();
    updateSelectionButtons(getSelectedGraphItem());
  });
  dom.nodeWidth.addEventListener("input", refreshVisualProperties);
  dom.nodeSizeScale.addEventListener("input", refreshVisualProperties);
  dom.linkWidthScale.addEventListener("input", refreshVisualProperties);
  dom.zoomLevel.addEventListener("change", applyZoomInput);
  document.querySelectorAll('input[name="match-mode"]').forEach((input) => {
    input.addEventListener("change", applyFilters);
  });
  [dom.labelName, dom.labelLength, dom.labelDepth, dom.labelBlast, dom.showLinkLabels, dom.textOutline].forEach((input) => {
    input.addEventListener("change", refreshVisualProperties);
  });
  bindBandageSvgEvents();

  dom.layoutButtons.forEach((button) => {
    button.addEventListener("click", () => {
      currentLayout = button.dataset.layout;
      dom.layoutButtons.forEach((item) => item.classList.toggle("active", item === button));
      refreshVisualProperties();
      if (isTwinMode()) {
        activateTwinRenderer(true);
      } else if (isBandageMode()) {
        activateBandageRenderer(true);
      } else {
        activateCytoscapeRenderer();
        runLayout(true);
      }
    });
  });
}

function toggleExportMenuPanel(force) {
  const opened = toggleToolbarPanel(dom.exportMenuPanel, dom.exportMenuToggle, force);
  if (opened) {
    toggleGraphDrawingPanel(false);
    toggleGraphDisplayPanel(false);
    toggleGraphFilterPanel(false);
    toggleServerFilesPanel(false);
  }
}

function toggleGraphDrawingPanel(force) {
  const opened = toggleToolbarPanel(dom.graphDrawingPanel, dom.graphDrawingToggle, force);
  if (opened) {
    toggleExportMenuPanel(false);
    toggleGraphDisplayPanel(false);
    toggleGraphFilterPanel(false);
    toggleServerFilesPanel(false);
  }
}

function toggleGraphDisplayPanel(force) {
  const opened = toggleToolbarPanel(dom.graphDisplayPanel, dom.graphDisplayToggle, force);
  if (opened) {
    toggleExportMenuPanel(false);
    toggleGraphDrawingPanel(false);
    toggleGraphFilterPanel(false);
    toggleServerFilesPanel(false);
  }
}

function toggleGraphFilterPanel(force) {
  const opened = toggleToolbarPanel(dom.graphFilterPanel, dom.graphFilterToggle, force);
  if (opened) {
    toggleExportMenuPanel(false);
    toggleGraphDrawingPanel(false);
    toggleGraphDisplayPanel(false);
    toggleServerFilesPanel(false);
  }
}

function toggleServerFilesPanel(force) {
  const opened = toggleToolbarPanel(dom.serverFilesPanel, dom.serverFilesToggle, force);
  if (opened) {
    toggleExportMenuPanel(false);
    toggleGraphDrawingPanel(false);
    toggleGraphDisplayPanel(false);
    toggleGraphFilterPanel(false);
  }
}

function toggleToolbarPanel(panel, toggle, force) {
  if (!panel || !toggle) return;
  const nextOpen = typeof force === "boolean" ? force : panel.hidden;
  panel.hidden = !nextOpen;
  toggle.setAttribute("aria-expanded", String(nextOpen));
  return nextOpen;
}

async function postAction(path, success) {
  await callAndRender(path, {
    method: "POST",
    loading: "Updating graph...",
    success,
    relayout: shouldAutoRedraw(),
  });
}

async function postUndoRedoAction(path, success) {
  await callAndRender(path, {
    method: "POST",
    loading: "Updating graph...",
    success,
    relayout: shouldRelayoutUndoRedo,
  });
}

function shouldAutoRedraw() {
  return Boolean(dom.autoRedraw?.checked);
}

function shouldRelayoutUndoRedo(nextPayload, previousPayload) {
  return shouldAutoRedraw() || graphAddsNodes(previousPayload, nextPayload);
}

function graphAddsNodes(previousPayload, nextPayload) {
  const previousIds = new Set((previousPayload?.nodes || []).map((node) => node.data?.id).filter(Boolean));
  return (nextPayload?.nodes || []).some((node) => {
    const nodeId = node.data?.id;
    return nodeId && !previousIds.has(nodeId);
  });
}

async function downloadExport() {
  if (!graphState) return;
  const format = dom.exportFormat.value;
  if (format === "svg") {
    await saveSvgExport({ selectedOnly: false, quick: false });
    return;
  }
  try {
    setStatus(`Exporting ${format.toUpperCase()}...`);
    const response = await fetch(`/api/export?format=${encodeURIComponent(format)}`);
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const text = await response.text();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || `edited.${format === "fasta" ? "fasta" : "gfa"}`;
    const saved = await saveTextExport(text, filename, "text/plain");
    if (saved.canceled) {
      setStatus("Export canceled");
      return;
    }
    showToast(`${format.toUpperCase()} exported`);
    setStatus("Ready");
  } catch (error) {
    pendingRename = null;
    pendingDuplicateSource = null;
    setStatus(error.message);
    showToast(error.message);
  }
}

async function quickDownloadExport() {
  if (!graphState) return;
  const format = dom.exportFormat.value;
  if (format === "svg") {
    await saveSvgExport({ selectedOnly: false, quick: true });
    return;
  }
  try {
    setStatus(`Exporting ${format.toUpperCase()}...`);
    const response = await fetch(`/api/export?format=${encodeURIComponent(format)}`);
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const text = await response.text();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || `edited.${format === "fasta" ? "fasta" : "gfa"}`;
    const desktopApi = window.pywebview?.api;
    if (desktopApi && typeof desktopApi.save_text_file_default === "function") {
      const result = await desktopApi.save_text_file_default({
        filename,
        contents: text,
      });
      if (!result?.ok) {
        throw new Error(result?.message || "Save failed");
      }
      showToast(`${format.toUpperCase()} exported`);
      setStatus(result.path ? `Saved to ${result.path}` : "Ready");
      return;
    }
    downloadBlob(new Blob([text], { type: "text/plain" }), filename);
    showToast(`${format.toUpperCase()} exported`);
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function downloadSelectedExport() {
  if (!graphState) return;
  const selection = getSelectedGraphSelection();
  const format = dom.exportFormat.value;
  if (format === "svg") {
    if (!selection.nodeIds.length && !selection.edgeIds.length) {
      showToast("Select one or more graph items");
      return;
    }
    await saveSvgExport({ selectedOnly: true, quick: false });
    return;
  }
  const edgeIds = selection.edgeIds;
  if (!edgeIds.length) {
    showToast("Select one or more links");
    return;
  }
  try {
    setStatus(`Exporting selected links as ${format.toUpperCase()}...`);
    const response = await fetch("/api/export_selection", {
      method: "POST",
      body: JSON.stringify({ edge_ids: edgeIds, format }),
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const text = await response.text();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const extension = format === "fasta" ? "fasta" : "gfa";
    const filename = match?.[1] || `selected-links.${extension}`;
    const saved = await saveTextExport(text, filename, "text/plain");
    if (saved.canceled) {
      setStatus("Export canceled");
      return;
    }
    showToast(`Selected links exported (${edgeIds.length})`);
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function downloadEditHistory() {
  if (!graphState) return;
  try {
    setStatus("Exporting edit history...");
    const response = await fetch("/api/export_history");
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = await response.json();
    const sourceName = graphState.session?.source_name || "edited";
    const stem = fileStem(sourceName, "edited");
    const saved = await saveTextExport(
      JSON.stringify(payload, null, 2),
      `${stem}.edit-history.json`,
      "application/json",
    );
    if (saved.canceled) {
      setStatus("Export canceled");
      return;
    }
    showToast("Edit history exported");
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function applyHistoryFile() {
  if (!graphState || !dom.historyFile.files[0]) return;
  const formData = new FormData();
  formData.append("history_file", dom.historyFile.files[0]);
  await callAndRender("/api/apply_history", {
    method: "POST",
    body: formData,
    loading: "Applying edit history...",
    success: "Edit history applied",
    relayout: true,
  });
}

async function renderHistoryFromFiles() {
  const gfaFile = dom.renderGfaFile.files[0];
  const historyFile = dom.renderHistoryFile.files[0];
  if (!gfaFile || !historyFile) return;
  try {
    setStatus("Rendering GFA from history...");
    const formData = new FormData();
    formData.append("gfa_file", gfaFile);
    formData.append("history_file", historyFile);
    formData.append("keep_sequences", dom.keepSequences.checked ? "true" : "false");
    const response = await fetch("/api/render_history", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const text = await response.text();
    const saved = await saveTextExport(
      text,
      `${fileStem(gfaFile.name, "edited")}.history-rendered.gfa`,
      "text/plain",
    );
    if (saved.canceled) {
      setStatus("Export canceled");
      return;
    }
    showToast("Edited GFA rendered");
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function inferHistoryFromFiles() {
  const oldFile = dom.inferOldGfaFile.files[0];
  const newFile = dom.inferNewGfaFile.files[0];
  if (!oldFile || !newFile) return;
  try {
    setStatus("Inferring edit history...");
    const formData = new FormData();
    formData.append("old_gfa_file", oldFile);
    formData.append("new_gfa_file", newFile);
    formData.append("keep_sequences", dom.keepSequences.checked ? "true" : "false");
    const response = await fetch("/api/infer_history", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = await response.json();
    const saved = await saveTextExport(
      JSON.stringify(payload, null, 2),
      `${fileStem(oldFile.name, "old")}.inferred-history.json`,
      "application/json",
    );
    if (saved.canceled) {
      setStatus("Export canceled");
      return;
    }
    showToast("Inferred edit history generated");
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function runAlignmentFromQueryFile() {
  if (!graphState || !dom.queryFastaFile.files[0]) return;
  const tool = dom.alignmentTool.value;
  try {
    setStatus(`Running ${tool}...`);
    const formData = new FormData();
    formData.append("query_file", dom.queryFastaFile.files[0]);
    formData.append("tool", tool);
    formData.append("extra_args", dom.alignmentExtraArgs.value || "");
    formData.append("target_role", dom.alignmentTargetRole.value || "subject");
    const response = await fetch("/api/run_alignment", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    renderGraph(await response.json(), { relayout: shouldAutoRedraw() });
    showAlignmentVisualMode();
    showToast(`${tool} complete`);
    setStatus("Alignment complete");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function selectAlignmentRead() {
  if (!graphState) return;
  const readId = dom.alignmentReadSelect.value || "__all__";
  try {
    setStatus(readId === "__all__" ? "Showing all reads..." : `Showing ${readId}...`);
    const response = await fetch("/api/alignment_select_read", {
      method: "POST",
      body: JSON.stringify({ read_id: readId }),
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    renderGraph(await response.json(), { relayout: false });
    showAlignmentVisualMode();
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function restoreHistoryTraceStep(traceIndex) {
  await postJsonAction(
    "/api/history_trace_step",
    { trace_index: traceIndex },
    `Restored history step ${traceIndex}`,
  );
}

async function restoreOperationState(stateIndex, label) {
  await callAndRender("/api/operation_state", {
    method: "POST",
    body: JSON.stringify({ state_index: stateIndex }),
    headers: { "Content-Type": "application/json" },
    loading: "Restoring operation...",
    success: label,
    relayout: true,
  });
}

async function clearOperationHistory() {
  await postAction("/api/clear_operation_history", "Operation log cleared");
}

async function jumpToEditStep(targetStepCount, label) {
  await postJsonAction(
    "/api/jump_edit_step",
    { target_step_count: targetStepCount },
    label,
  );
}

async function saveTextExport(text, filename, mimeType = "text/plain") {
  const desktopApi = window.pywebview?.api;
  if (desktopApi && typeof desktopApi.save_text_file === "function") {
    const result = await desktopApi.save_text_file({
      filename,
      contents: text,
      file_types: fileTypesForFilename(filename),
    });
    if (!result?.ok) {
      throw new Error(result?.message || "Save failed");
    }
    return result;
  }
  if (typeof window.showSaveFilePicker === "function") {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: browserFileTypesForFilename(filename, mimeType),
      });
      const writable = await handle.createWritable();
      await writable.write(new Blob([text], { type: mimeType }));
      await writable.close();
      return { ok: true, canceled: false, path: handle.name };
    } catch (error) {
      if (error?.name === "AbortError") {
        return { ok: true, canceled: true };
      }
      throw new Error(error?.message || "Save failed");
    }
  }
  const fallbackName = window.prompt("Save as", filename);
  if (fallbackName == null) {
    return { ok: true, canceled: true };
  }
  downloadBlob(new Blob([text], { type: mimeType }), fallbackName.trim() || filename);
  return { ok: true, downloaded: true, canceled: false };
}

function browserFileTypesForFilename(filename, mimeType) {
  const extension = String(filename || "").toLowerCase().split(".").pop();
  if (extension === "gfa") {
    return [{ description: "GFA files", accept: { "text/plain": [".gfa"] } }];
  }
  if (extension === "fasta" || extension === "fa") {
    return [{ description: "FASTA files", accept: { "text/plain": [".fasta", ".fa"] } }];
  }
  if (extension === "svg") {
    return [{ description: "SVG images", accept: { "image/svg+xml": [".svg"] } }];
  }
  if (extension === "json") {
    return [{ description: "JSON files", accept: { "application/json": [".json"] } }];
  }
  return [{ description: "Text files", accept: { [mimeType || "text/plain"]: [".txt"] } }];
}

function fileTypesForFilename(filename) {
  const extension = String(filename || "").toLowerCase().split(".").pop();
  if (extension === "gfa") return ["GFA files (*.gfa)", "All files (*.*)"];
  if (extension === "fasta" || extension === "fa") {
    return ["FASTA files (*.fasta;*.fa)", "All files (*.*)"];
  }
  if (extension === "svg") return ["SVG images (*.svg)", "All files (*.*)"];
  if (extension === "json") return ["JSON files (*.json)", "All files (*.*)"];
  return ["Text files (*.txt)", "All files (*.*)"];
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function saveSvgExport({ selectedOnly = false, quick = false } = {}) {
  if (!graphState) return;
  try {
    setStatus("Exporting SVG...");
    const svgText = buildGraphSvgExport({ selectedOnly });
    const filename = `${fileStem(graphState.session?.source_name, "graph")}${selectedOnly ? ".selected" : ""}.svg`;
    if (quick) {
      const desktopApi = window.pywebview?.api;
      if (desktopApi && typeof desktopApi.save_text_file_default === "function") {
        const result = await desktopApi.save_text_file_default({ filename, contents: svgText });
        if (!result?.ok) throw new Error(result?.message || "Save failed");
        showToast("SVG exported");
        setStatus(result.path ? `Saved to ${result.path}` : "Ready");
        return;
      }
      downloadBlob(new Blob([svgText], { type: "image/svg+xml" }), filename);
      showToast("SVG exported");
      setStatus("Ready");
      return;
    }
    const saved = await saveTextExport(svgText, filename, "image/svg+xml");
    if (saved.canceled) {
      setStatus("Export canceled");
      return;
    }
    showToast("SVG exported");
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

function buildGraphSvgExport({ selectedOnly = false } = {}) {
  const selection = getSelectedGraphSelection();
  if (selectedOnly && !selection.nodeIds.length && !selection.edgeIds.length) {
    throw new Error("Select one or more graph items");
  }
  const margin = 34;
  const gap = 70;
  const root = svgEl("svg", { xmlns: SVG_NS, version: "1.1" });
  root.appendChild(svgEl("title", {}, `${fileStem(graphState.session?.source_name, "graph")} ${currentLayout}`));
  root.appendChild(svgEl("style", {}, exportSvgStyle()));

  if (isTwinMode()) {
    const left = buildCytoscapeSvgLayer({ selectedOnly, selection });
    const right = buildBandageSvgLayer({ selectedOnly, selection });
    if (!hasBounds(left.bounds) && !hasBounds(right.bounds)) throw new Error("Nothing visible to export");
    const leftSize = boundsSize(left.bounds);
    const rightSize = boundsSize(right.bounds);
    const width = Math.ceil(leftSize.width + rightSize.width + gap + margin * 2);
    const height = Math.ceil(Math.max(leftSize.height, rightSize.height) + margin * 2);
    root.setAttribute("width", String(width));
    root.setAttribute("height", String(height));
    root.setAttribute("viewBox", `0 0 ${width} ${height}`);
    root.appendChild(svgEl("rect", { class: "export-background", x: 0, y: 0, width, height }));
    if (hasBounds(left.bounds)) {
      const wrap = svgEl("g", {
        transform: `translate(${round(margin - left.bounds.minX)} ${round(margin - left.bounds.minY)})`,
      });
      wrap.appendChild(left.group);
      root.appendChild(wrap);
    }
    root.appendChild(svgEl("line", {
      class: "export-divider",
      x1: margin + leftSize.width + gap / 2,
      y1: margin / 2,
      x2: margin + leftSize.width + gap / 2,
      y2: height - margin / 2,
    }));
    if (hasBounds(right.bounds)) {
      const wrap = svgEl("g", {
        transform: `translate(${round(margin + leftSize.width + gap - right.bounds.minX)} ${round(margin - right.bounds.minY)})`,
      });
      wrap.appendChild(right.group);
      root.appendChild(wrap);
    }
  } else {
    const layer = isBandageMode()
      ? buildBandageSvgLayer({ selectedOnly, selection })
      : buildCytoscapeSvgLayer({ selectedOnly, selection });
    if (!hasBounds(layer.bounds)) throw new Error("Nothing visible to export");
    const size = boundsSize(layer.bounds);
    const width = Math.ceil(size.width + margin * 2);
    const height = Math.ceil(size.height + margin * 2);
    root.setAttribute("width", String(width));
    root.setAttribute("height", String(height));
    root.setAttribute("viewBox", `0 0 ${width} ${height}`);
    root.appendChild(svgEl("rect", { class: "export-background", x: 0, y: 0, width, height }));
    const wrap = svgEl("g", {
      transform: `translate(${round(margin - layer.bounds.minX)} ${round(margin - layer.bounds.minY)})`,
    });
    wrap.appendChild(layer.group);
    root.appendChild(wrap);
  }
  return `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(root)}\n`;
}

function buildCytoscapeSvgLayer({ selectedOnly = false, selection = null } = {}) {
  const group = svgEl("g", { class: "export-cose-layer" });
  const bounds = emptyBounds();
  if (!cy) return { group, bounds };
  const selectedNodeIds = new Set(selection?.nodeIds || []);
  const selectedEdgeIds = new Set(selection?.edgeIds || []);
  const nodeIds = new Set(selectedNodeIds);
  const edgeLayer = svgEl("g", { class: "export-edge-layer" });
  cy.edges().forEach((edge) => {
    if (!edge.visible()) return;
    if (selectedOnly && !selectedEdgeIds.has(edge.id())) return;
    const source = edge.source();
    const target = edge.target();
    if (!source.visible() || !target.visible()) return;
    if (selectedOnly) {
      nodeIds.add(source.id());
      nodeIds.add(target.id());
    }
    const sourcePosition = source.position();
    const targetPosition = target.position();
    addPointToBounds(bounds, sourcePosition, 28);
    addPointToBounds(bounds, targetPosition, 28);
    const data = enrichEdgeData(edge.data());
    const color = data.renderColor || chooseEdgeColor(data);
    const width = Math.max(1.2, Number(data.width || 2));
    edgeLayer.appendChild(svgEl("path", {
      class: "export-edge",
      d: `M ${round(sourcePosition.x)} ${round(sourcePosition.y)} L ${round(targetPosition.x)} ${round(targetPosition.y)}`,
      stroke: color,
      "stroke-width": width,
    }));
    edgeLayer.appendChild(svgEl("polygon", {
      class: "export-arrow",
      points: arrowPolygonPoints(sourcePosition, targetPosition, Math.max(7, width + 5)),
      fill: color,
    }));
    if (data.renderLabel) {
      appendSvgText(edgeLayer, data.renderLabel, (sourcePosition.x + targetPosition.x) / 2, (sourcePosition.y + targetPosition.y) / 2 - 7, "export-edge-label");
    }
  });
  group.appendChild(edgeLayer);
  if (!selectedOnly) {
    cy.nodes().forEach((node) => {
      if (node.visible()) nodeIds.add(node.id());
    });
  }
  const nodeLayer = svgEl("g", { class: "export-node-layer" });
  cy.nodes().forEach((node) => {
    if (!node.visible() || !nodeIds.has(node.id())) return;
    const data = enrichNodeData(node.data(), graphState.stats);
    const position = node.position();
    const width = Math.max(6, Number(data.renderWidth || data.size || 24));
    const height = Math.max(6, Number(data.renderHeight || data.size || width));
    addPointToBounds(bounds, position, Math.max(width, height) / 2 + 22);
    const color = data.renderColor || chooseNodeColor(data, graphState.stats);
    nodeLayer.appendChild(
      data.shape === "rectangle"
        ? svgEl("rect", { class: "export-node", x: position.x - width / 2, y: position.y - height / 2, width, height, rx: 2.5, fill: color })
        : svgEl("ellipse", { class: "export-node", cx: position.x, cy: position.y, rx: width / 2, ry: height / 2, fill: color }),
    );
    if (data.renderLabel) {
      appendSvgText(nodeLayer, data.renderLabel, position.x, position.y + height / 2 + 12, "export-node-label");
    }
  });
  group.appendChild(nodeLayer);
  return { group, bounds };
}

function buildBandageSvgLayer({ selectedOnly = false, selection = null } = {}) {
  const group = svgEl("g", { class: "export-bandage-layer" });
  const bounds = emptyBounds();
  const selectedNodeIds = new Set(selection?.nodeIds || []);
  const selectedEdgeIds = new Set(selection?.edgeIds || []);
  const nodeIds = new Set(selectedNodeIds);
  const linkLayer = svgEl("g", { class: "export-bandage-link-layer" });
  getClientEdges().forEach((edge) => {
    if (!bandageState.visibleEdgeIds.has(edge.id)) return;
    if (selectedOnly && !selectedEdgeIds.has(edge.id)) return;
    if (selectedOnly) {
      nodeIds.add(edge.source);
      nodeIds.add(edge.target);
    }
    const geometry = getLinkGeometry(edge);
    if (!geometry) return;
    quadraticSamplePoints(geometry.source, geometry.control, geometry.target, 8).forEach((point) => {
      addPointToBounds(bounds, point, displayEdgeWidth(edge) + 12);
    });
    const color = chooseEdgeColor(edge, "bandage");
    const edgeWidth = displayEdgeWidth(edge);
    linkLayer.appendChild(svgEl("path", {
      class: "export-bandage-link",
      d: geometry.path,
      stroke: color,
      "stroke-width": Math.max(2.3, edgeWidth * 0.78),
    }));
    linkLayer.appendChild(svgEl("polygon", {
      class: "export-arrow",
      points: geometry.arrow.map((point) => `${point.x},${point.y}`).join(" "),
      fill: color,
    }));
    if (dom.showLinkLabels?.checked && (edge.customLabel || edge.label)) {
      appendSvgText(linkLayer, edge.customLabel || edge.label, geometry.label.x, geometry.label.y - 6, "export-edge-label");
    }
  });
  group.appendChild(linkLayer);
  if (!selectedOnly) {
    getClientNodes().forEach((node) => {
      if (bandageState.visibleNodeIds.has(node.id)) nodeIds.add(node.id);
    });
  }
  const contigLayer = svgEl("g", { class: "export-bandage-contig-layer" });
  getClientNodes().forEach((node) => {
    if (!nodeIds.has(node.id) || !bandageState.visibleNodeIds.has(node.id)) return;
    const geometry = getGlyphGeometry(node.id);
    if (!geometry) return;
    (geometry.points?.length ? geometry.points : [geometry.start, geometry.end, geometry.control]).forEach((point) => {
      addPointToBounds(bounds, point, geometry.width / 2 + 20);
    });
    const contigGroup = svgEl("g", { class: "export-bandage-contig" });
    contigGroup.appendChild(svgEl("path", {
      class: "bandage-contig-path",
      d: geometry.path,
      stroke: chooseNodeColor(node, graphState.stats, "bandage"),
      "stroke-width": geometry.width,
    }));
    appendBandageAlignmentSpans(contigGroup, node, geometry);
    appendBandageEndpoint(contigGroup, geometry.start, "-");
    appendBandageEndpoint(contigGroup, geometry.end, "+");
    appendBandageNodeLabel(contigGroup, node, geometry);
    contigLayer.appendChild(contigGroup);
  });
  group.appendChild(contigLayer);
  return { group, bounds };
}

function exportSvgStyle() {
  return `
    .export-background { fill: #fbfcf8; }
    .export-divider { stroke: #d9ded2; stroke-width: 1; }
    .export-edge, .export-bandage-link, .bandage-contig-path, .bandage-query-hit-block { fill: none; stroke-linecap: round; stroke-linejoin: round; }
    .export-node { stroke: rgba(31, 37, 33, 0.45); stroke-width: 1.2; }
    .export-node-label, .export-edge-label, .bandage-node-label, .bandage-link-label {
      fill: #1f2521;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      font-size: 10px;
      text-anchor: middle;
      dominant-baseline: central;
    }
    .export-edge-label, .bandage-link-label { font-size: 9px; }
    .bandage-label-outline { paint-order: stroke; stroke: #fbfcf8; stroke-width: 4px; stroke-linejoin: round; }
    .bandage-query-hit-block { stroke-linecap: butt; }
    .bandage-endpoint { fill: rgba(31, 37, 33, 0.85); }
    .bandage-endpoint-label { fill: #ffffff; font-size: 7px; font-weight: 700; text-anchor: middle; dominant-baseline: central; }
  `;
}

function appendSvgText(parent, text, x, y, className) {
  const lines = String(text || "").split("\n").filter((line) => line.trim());
  const lineHeight = className.includes("edge") ? 10 : 11;
  const startY = y - ((lines.length - 1) * lineHeight) / 2;
  lines.forEach((line, index) => {
    parent.appendChild(svgEl("text", { class: className, x, y: startY + index * lineHeight }, line));
  });
}

function emptyBounds() {
  return { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
}

function hasBounds(bounds) {
  return Number.isFinite(bounds.minX) && Number.isFinite(bounds.minY) && Number.isFinite(bounds.maxX) && Number.isFinite(bounds.maxY);
}

function addPointToBounds(bounds, point, padding = 0) {
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return;
  bounds.minX = Math.min(bounds.minX, point.x - padding);
  bounds.minY = Math.min(bounds.minY, point.y - padding);
  bounds.maxX = Math.max(bounds.maxX, point.x + padding);
  bounds.maxY = Math.max(bounds.maxY, point.y + padding);
}

function boundsSize(bounds) {
  if (!hasBounds(bounds)) return { width: 0, height: 0 };
  return { width: Math.max(1, bounds.maxX - bounds.minX), height: Math.max(1, bounds.maxY - bounds.minY) };
}

function arrowPolygonPoints(source, target, size) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.max(Math.hypot(dx, dy), 1);
  const angle = Math.atan2(dy, dx);
  const tip = { x: target.x - (dx / distance) * Math.min(size * 0.8, distance * 0.18), y: target.y - (dy / distance) * Math.min(size * 0.8, distance * 0.18) };
  return [
    tip,
    { x: tip.x - Math.cos(angle - 0.5) * size, y: tip.y - Math.sin(angle - 0.5) * size },
    { x: tip.x - Math.cos(angle + 0.5) * size, y: tip.y - Math.sin(angle + 0.5) * size },
  ].map((point) => `${round(point.x)},${round(point.y)}`).join(" ");
}

function quadraticSamplePoints(start, control, end, steps = 8) {
  const points = [];
  for (let index = 0; index <= steps; index += 1) {
    points.push(quadraticPoint(start, control, end, index / steps));
  }
  return points;
}

function fileStem(rawName, fallback) {
  const name = String(rawName || fallback || "file").replace(/^server:/, "").split("/").pop() || fallback || "file";
  return name.replace(/\.[^.]+$/, "") || fallback || "file";
}

function isBackendExportFormat(format) {
  return ["gfa", "fasta", "fa"].includes(String(format || "").toLowerCase());
}

async function loadServerFiles() {
  try {
    const response = await fetch("/api/server_files");
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = await response.json();
    dom.serverDataDir.value = payload.data_dir || "Not connected";
    const files = payload.files || [];
    dom.serverFileSelect.replaceChildren();
    if (!files.length) {
      dom.serverFileSelect.appendChild(optionEl("", "No .gfa/.txt files"));
    } else {
      files.forEach((file) => {
        const label = `${file.path} (${formatBytes(file.size)})`;
        dom.serverFileSelect.appendChild(optionEl(file.path, label));
      });
    }
    dom.serverFileSelect.disabled = !files.length;
    updateServerFileButtons();
  } catch (error) {
    dom.serverDataDir.value = "Not connected";
    dom.serverFileSelect.replaceChildren(optionEl("", "Server files unavailable"));
    dom.serverFileSelect.disabled = true;
    updateServerFileButtons();
  }
}

async function loadSelectedServerFile() {
  const path = dom.serverFileSelect.value;
  if (!path) return;
  await callAndRender("/api/load_server_file", {
    method: "POST",
    body: JSON.stringify({
      path,
      keep_sequences: dom.keepSequences.checked,
    }),
    headers: { "Content-Type": "application/json" },
    loading: "Loading server GFA...",
    success: "Server GFA loaded",
    relayout: true,
  });
}

async function saveGraphToServer() {
  if (!graphState) return;
  const format = dom.exportFormat.value;
  if (!isBackendExportFormat(format)) {
    showToast("Use export options to save SVG views");
    return;
  }
  const path = dom.serverSavePath.value.trim();
  try {
    setStatus(`Saving ${format.toUpperCase()} to local workspace...`);
    const response = await fetch("/api/save_server_file", {
      method: "POST",
      body: JSON.stringify({ path: path || null, format }),
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = await response.json();
    dom.serverSavePath.value = payload.path;
    serverSavePathAuto = false;
    showToast(`Saved locally: ${payload.path}`);
    setStatus("Local save complete");
    await loadServerFiles();
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

function sftpPayload(extra = {}) {
  return {
    host: dom.sftpHost.value.trim(),
    port: Number(dom.sftpPort.value || 22),
    username: dom.sftpUsername.value.trim(),
    password: dom.sftpPassword.value,
    remote_path: dom.sftpRemotePath.value.trim(),
    keep_sequences: dom.keepSequences.checked,
    format: dom.exportFormat.value,
    ...extra,
  };
}

async function downloadFromSftp() {
  try {
    setStatus("Downloading GFA via SFTP...");
    const response = await fetch("/api/sftp_download", {
      method: "POST",
      body: JSON.stringify(sftpPayload()),
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    renderGraph(await response.json(), { relayout: true });
    showToast("SFTP GFA loaded");
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

async function uploadToSftp() {
  if (!graphState) return;
  if (!isBackendExportFormat(dom.exportFormat.value)) {
    showToast("SFTP upload supports GFA/FASTA");
    return;
  }
  try {
    setStatus("Uploading via SFTP...");
    const response = await fetch("/api/sftp_upload", {
      method: "POST",
      body: JSON.stringify(sftpPayload({ format: dom.exportFormat.value })),
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = await response.json();
    showToast(`Uploaded: ${payload.remote_path}`);
    setStatus("SFTP upload complete");
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
  }
}

function updateServerFileButtons() {
  const canLoad = Boolean(dom.serverFileSelect?.value);
  const canSaveTextGraph = Boolean(graphState && isBackendExportFormat(dom.exportFormat?.value));
  dom.serverLoadButton.disabled = !canLoad;
  dom.serverSaveButton.disabled = !canSaveTextGraph;
  updateSftpButtons();
}

function updateHistoryFileButtons() {
  dom.applyHistoryButton.disabled = !graphState || !dom.historyFile.files[0];
  dom.renderHistoryButton.disabled = !dom.renderGfaFile.files[0] || !dom.renderHistoryFile.files[0];
  dom.inferHistoryButton.disabled = !dom.inferOldGfaFile.files[0] || !dom.inferNewGfaFile.files[0];
}

function updateSftpButtons() {
  const hasConnection = Boolean(
    dom.sftpHost?.value.trim()
      && dom.sftpUsername?.value.trim()
      && dom.sftpRemotePath?.value.trim(),
  );
  dom.sftpDownloadButton.disabled = !hasConnection;
  dom.sftpUploadButton.disabled = !hasConnection || !graphState || !isBackendExportFormat(dom.exportFormat?.value);
}

function updateAlignmentButtons() {
  if (dom.alignmentRunButton) {
    dom.alignmentRunButton.disabled = !graphState || !dom.queryFastaFile?.files[0];
  }
  if (dom.blastUploadButton) {
    dom.blastUploadButton.disabled = !graphState || !dom.blastFile?.files[0];
  }
}

function updateAlignmentReadSelect(alignment) {
  if (!dom.alignmentReadSelect) return;
  const readIds = alignment?.read_ids || [];
  const selected = alignment?.selected_read_id || "__all__";
  dom.alignmentReadSelect.replaceChildren(optionEl("__all__", `All reads${readIds.length ? ` (${readIds.length})` : ""}`));
  readIds.forEach((readId) => {
    dom.alignmentReadSelect.appendChild(optionEl(readId, readId));
  });
  dom.alignmentReadSelect.value = readIds.includes(selected) ? selected : "__all__";
  dom.alignmentReadSelect.disabled = !readIds.length;
}

function renderAlignmentQueryControls(alignment) {
  if (!dom.alignmentQueryList) return;
  const readIds = alignment?.read_ids || [];
  if (dom.alignmentShowBackground) {
    const backgroundDisabled = !readIds.length;
    dom.alignmentShowBackground.disabled = backgroundDisabled;
    dom.alignmentShowBackground.closest("label")?.classList.toggle("is-disabled", backgroundDisabled);
  }
  dom.alignmentQueryList.replaceChildren();
  if (!readIds.length) {
    const empty = document.createElement("div");
    empty.className = "alignment-query-empty";
    empty.textContent = "No alignment queries";
    dom.alignmentQueryList.appendChild(empty);
    return;
  }
  const multiActive = hasMultipleAlignmentQueries();
  readIds.forEach((readId, index) => {
    const settings = ensureAlignmentQuerySettings(readId, index);
    if (!settings.backgroundTouched) {
      settings.background = !multiActive;
    }
    const row = document.createElement("div");
    row.className = "alignment-query-item";
    row.dataset.queryId = readId;
    const visibleWrap = document.createElement("label");
    visibleWrap.className = "alignment-query-check";
    visibleWrap.title = "Front query hit colour";
    const visible = document.createElement("input");
    visible.type = "checkbox";
    visible.dataset.role = "visible";
    visible.checked = settings.visible !== false;
    visible.setAttribute("aria-label", `Front ${readId}`);
    visibleWrap.append(visible, document.createTextNode("f"));
    const backgroundWrap = document.createElement("label");
    backgroundWrap.className = "alignment-query-check";
    backgroundWrap.title = "Light hit background";
    const background = document.createElement("input");
    background.type = "checkbox";
    background.dataset.role = "background";
    background.checked = settings.background !== false;
    background.setAttribute("aria-label", `Background ${readId}`);
    backgroundWrap.append(background, document.createTextNode("b"));
    const color = document.createElement("input");
    color.type = "color";
    color.value = settings.color;
    color.title = "Query colour";
    const name = document.createElement("span");
    name.textContent = readId;
    row.append(visibleWrap, backgroundWrap, color, name);
    dom.alignmentQueryList.appendChild(row);
  });
}

function ensureAlignmentQuerySettings(readId, fallbackIndex = null) {
  const key = String(readId || "__alignment__");
  if (!alignmentQuerySettings.has(key)) {
    const index = Number.isFinite(fallbackIndex)
      ? fallbackIndex
      : Math.floor(hashNumber(key) * alignmentPalette.length);
    alignmentQuerySettings.set(key, {
      visible: true,
      background: true,
      backgroundTouched: false,
      color: alignmentPalette[index % alignmentPalette.length],
    });
  } else {
    const settings = alignmentQuerySettings.get(key);
    if (settings.visible == null) {
      settings.visible = true;
    }
    if (settings.background == null) {
      settings.background = settings.visible !== false;
    }
    if (settings.backgroundTouched == null) {
      settings.backgroundTouched = false;
    }
  }
  return alignmentQuerySettings.get(key);
}

function activeAlignmentReadIds() {
  const alignment = graphState?.session?.alignment;
  const readIds = alignment?.read_ids || [];
  const selected = alignment?.selected_read_id || "__all__";
  if (selected && selected !== "__all__") return [selected];
  return readIds;
}

function hasMultipleAlignmentQueries() {
  return activeAlignmentReadIds().length > 1;
}

function alignmentQueryVisible(readId) {
  return ensureAlignmentQuerySettings(readId).visible !== false;
}

function alignmentQueryBackgroundVisible(readId) {
  return alignmentQueryVisible(readId) && ensureAlignmentQuerySettings(readId).background !== false;
}

function visibleAlignmentSpans(data) {
  return (Array.isArray(data?.alignmentSpans) ? data.alignmentSpans : [])
    .filter((span) => alignmentQueryVisible(span.qseqid || "__alignment__"));
}

function alignmentDataHasVisibleHit(data) {
  if (visibleAlignmentSpans(data).length) return true;
  const queryId = alignmentQueryId(data);
  return Boolean(queryId && alignmentQueryVisible(queryId) && (data?.blastBest || data?.blastHitCount));
}

function alignmentDataShowsHitBackground(data) {
  if (!alignmentDataHasVisibleHit(data)) return false;
  const spans = visibleAlignmentSpans(data);
  if (spans.length) {
    return spans.some((span) => alignmentQueryBackgroundVisible(span.qseqid || "__alignment__"));
  }
  return alignmentQueryBackgroundVisible(alignmentQueryId(data));
}

function alignmentQueryId(dataOrHit) {
  if (!dataOrHit) return "__alignment__";
  if (dataOrHit.qseqid) return String(dataOrHit.qseqid);
  if (dataOrHit.blastBest?.qseqid) return String(dataOrHit.blastBest.qseqid);
  const visibleSpan = visibleAlignmentSpans(dataOrHit)[0];
  if (visibleSpan?.qseqid) return String(visibleSpan.qseqid);
  const span = Array.isArray(dataOrHit.alignmentSpans) ? dataOrHit.alignmentSpans[0] : null;
  return span?.qseqid ? String(span.qseqid) : "__alignment__";
}

function alignmentQueryColor(readId) {
  return ensureAlignmentQuerySettings(readId).color;
}

function alignmentHitColor(dataOrHit) {
  return alignmentQueryColor(alignmentQueryId(dataOrHit));
}

function showAlignmentHitBackground() {
  const mode = dom.colorMode?.value;
  return ["alignment", "read_path"].includes(mode)
    && Boolean(dom.alignmentShowBackground?.checked);
}

function alignmentHitBackgroundColor(dataOrHit) {
  return ALIGNMENT_HIT_BACKGROUND_COLOR;
}

function mixHexColor(hex, targetHex, amount) {
  const source = hexToRgb(hex) || hexToRgb(ALIGNMENT_HIT_LINK_COLOR);
  const target = hexToRgb(targetHex) || [251, 252, 248];
  const ratio = clamp(Number(amount), 0, 1);
  const rgb = source.map((value, index) => Math.round(value + (target[index] - value) * ratio));
  return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}

function hexToRgb(hex) {
  const match = String(hex || "").trim().match(/^#([0-9a-fA-F]{6})$/);
  if (!match) return null;
  const value = match[1];
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

function showAlignmentVisualMode() {
  if (!dom.colorMode || !graphState) return;
  dom.colorMode.value = "read_path";
  refreshVisualProperties();
  applyFilters();
}

function updateServerSavePath() {
  if (!graphState || !dom.serverSavePath) return;
  if (!isBackendExportFormat(dom.exportFormat?.value)) return;
  const sourceName = graphState.session?.source_name || "edited";
  if (!serverSavePathAuto && sourceName === serverSaveSourceName) return;
  serverSaveSourceName = sourceName;
  const extension = dom.exportFormat.value === "gfa" ? "gfa" : "fasta";
  const source = sourceName.replace(/^server:/, "");
  const parts = source.split("/");
  const filename = parts.pop() || "edited";
  const stem = filename.replace(/\.[^.]+$/, "") || "edited";
  dom.serverSavePath.value = `${stem}.edited.${extension}`;
  serverSavePathAuto = true;
}

function optionEl(value, text) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = text;
  return option;
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function updateAlignmentCommandPreview() {
  if (!dom.alignmentCommand) return;
  const tool = dom.alignmentTool?.value || "blastn";
  const query = dom.queryFastaFile?.files[0]?.name || "query.fa";
  const sourceName = graphState?.session?.source_name;
  const targetFasta = sourceName ? `${fileStem(sourceName, "graph")}.graph.fa` : "graph.fa";
  const args = (dom.alignmentExtraArgs?.value || "").trim();
  if (tool === "minimap2") {
    dom.alignmentCommand.value = `minimap2 ${args} ${targetFasta} ${query} > ${fileStem(query, "query")}.paf`;
    return;
  }
  dom.alignmentCommand.value = `blastn -query ${query} -subject ${targetFasta} ${args} -out ${fileStem(query, "query")}.blast6.tsv`;
}

async function tryLoadExistingGraph() {
  try {
    const response = await fetch("/api/graph");
    if (!response.ok) return;
    renderGraph(await response.json(), { relayout: true });
    setStatus("Ready");
  } catch {
    // Empty sessions are normal on first load.
  }
}

async function deleteSelected() {
  const selected = getSelectedGraphItem();
  if (!selected) return;
  if (selected.kind === "node") {
    await postJsonAction("/api/delete_node", { node_id: selected.id }, "Node deleted");
  } else {
    await postJsonAction("/api/delete_edge", { edge_id: selected.id }, "Link deleted");
  }
}

async function deleteAllSelected() {
  const selection = getSelectedGraphSelection();
  const itemCount = selection.nodeIds.length + selection.edgeIds.length;
  if (!itemCount) return;
  await postJsonAction(
    "/api/delete_selection",
    { node_ids: selection.nodeIds, edge_ids: selection.edgeIds },
    itemCount === 1 ? "Selected item deleted" : `${itemCount} selected items deleted`,
  );
}

async function duplicateSelectedNode() {
  const selected = getSelectedGraphItem();
  if (!selected || selected.kind !== "node") return;
  pendingDuplicateSource = selected.id;
  const payload = await postJsonAction("/api/duplicate_node", { node_id: selected.id }, "Node duplicated");
  const details = latestHistoryDetails(payload, "duplicate_node");
  if (details?.source_node_id && details?.new_node_id) {
    setRepeatResolutionContext({
      sourceId: details.source_node_id,
      duplicateId: details.new_node_id,
    });
  }
}

async function mergeSelectedLink() {
  const selection = getSelectedGraphSelection();
  if (!selection.edgeIds.length && selection.nodeIds.length < 2) return;
  const path = selection.nodeIds.length >= 2 || selection.edgeIds.length !== 1
    ? "/api/merge_selection"
    : "/api/merge_link";
  const body = path === "/api/merge_link"
    ? { edge_id: selection.edgeIds[0] }
    : { node_ids: selection.nodeIds, edge_ids: selection.edgeIds };
  const layoutSnapshot = captureMergeLayoutSnapshot();
  try {
    setStatus("Updating graph...");
    const response = await fetch(path, {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      throw new Error(await readError(response));
    }
    const payload = await response.json();
    const details = latestHistoryDetails(payload, path === "/api/merge_link" ? "merge_link" : "merge_selection");
    pendingMergeLayout = details?.new_node_id ? { snapshot: layoutSnapshot, details } : null;
    renderGraph(payload, { relayout: false });
    showToast("Merge complete");
    setStatus("Merge complete");
    if (details?.new_node_id) {
      pendingSelectNodeId = details.new_node_id;
      selectGraphNode(details.new_node_id, { fit: false });
    }
  } catch (error) {
    pendingMergeLayout = null;
    setStatus(error.message);
    showToast(error.message);
  }
}

function captureMergeLayoutSnapshot() {
  const cyPositions = new Map();
  if (cy) {
    cy.nodes().forEach((node) => {
      cyPositions.set(node.id(), { ...node.position() });
    });
  }
  const bandageNodes = new Map();
  getClientNodes().forEach((node) => {
    const geometry = getGlyphGeometry(node.id);
    if (geometry?.points?.length) {
      bandageNodes.set(node.id, geometry.points.map((point) => ({ x: point.x, y: point.y })));
      return;
    }
    const state = bandageState.nodes.get(node.id);
    if (state?.minus && state?.plus) {
      bandageNodes.set(node.id, [{ ...state.minus }, { ...state.plus }]);
    }
  });
  const bandageLinks = new Map();
  getClientEdges().forEach((edge) => {
    const geometry = getLinkGeometry(edge);
    if (geometry) {
      bandageLinks.set(edge.id, quadraticSamplePoints(geometry.source, geometry.control, geometry.target, 10));
    }
  });
  return { cyPositions, bandageNodes, bandageLinks };
}

function mergePathNodeIds(details) {
  const ids = details?.path_node_ids || details?.node_ids || [details?.source_node_id, details?.target_node_id];
  return (ids || []).filter(Boolean);
}

function mergePathEdgeIds(details) {
  const ids = details?.path_edge_ids || details?.edge_ids || [details?.edge_id];
  return (ids || []).filter(Boolean);
}

function mergedCytoscapePosition(nodeId) {
  if (!pendingMergeLayout || pendingMergeLayout.details?.new_node_id !== nodeId) return null;
  const points = mergePathNodeIds(pendingMergeLayout.details)
    .map((id) => pendingMergeLayout.snapshot.cyPositions.get(id))
    .filter(Boolean);
  return points.length ? averagePoints(points) : null;
}

function mergedBandageState(node) {
  if (!pendingMergeLayout || pendingMergeLayout.details?.new_node_id !== node.id) return null;
  const pathPoints = mergedBandagePathPoints(pendingMergeLayout.details, pendingMergeLayout.snapshot);
  if (pathPoints.length < 2) return null;
  const config = getBandageModeConfig();
  const targetLength = getBandageGlyphLength(node);
  const pointCount = config.flexibleGlyphs ? getNativePolylinePointCount(targetLength, config) : 2;
  const points = resamplePolylinePoints(pathPoints, Math.max(2, pointCount));
  const state = {
    x: 0,
    y: 0,
    angle: 0,
    bend: 0,
    minus: points[0],
    plus: points[points.length - 1],
    points,
  };
  const center = averagePoints(points);
  state.x = center.x;
  state.y = center.y;
  state.angle = Math.atan2(state.plus.y - state.minus.y, state.plus.x - state.minus.x);
  return state;
}

function mergedBandagePathPoints(details, snapshot) {
  const points = [];
  const nodeIds = mergePathNodeIds(details);
  const edgeIds = mergePathEdgeIds(details);
  nodeIds.forEach((nodeId, index) => {
    appendNearestPolyline(points, snapshot.bandageNodes.get(nodeId));
    appendNearestPolyline(points, snapshot.bandageLinks.get(edgeIds[index]));
  });
  return dedupePolylinePoints(points);
}

function appendNearestPolyline(target, source) {
  if (!source?.length) return;
  const candidate = source.map((point) => ({ x: point.x, y: point.y }));
  if (!target.length) {
    target.push(...candidate);
    return;
  }
  const last = target[target.length - 1];
  if (pointDistance(last, candidate[candidate.length - 1]) < pointDistance(last, candidate[0])) {
    candidate.reverse();
  }
  target.push(...candidate);
}

function dedupePolylinePoints(points) {
  const result = [];
  points.forEach((point) => {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return;
    const previous = result[result.length - 1];
    if (!previous || pointDistance(previous, point) > 0.5) {
      result.push({ x: point.x, y: point.y });
    }
  });
  return result;
}

function resamplePolylinePoints(points, targetCount) {
  const clean = dedupePolylinePoints(points);
  if (clean.length <= 2 || targetCount <= 2) {
    return clean.length >= 2 ? [clean[0], clean[clean.length - 1]] : clean;
  }
  const distances = [0];
  for (let index = 1; index < clean.length; index += 1) {
    distances.push(distances[index - 1] + pointDistance(clean[index - 1], clean[index]));
  }
  const total = distances[distances.length - 1];
  if (total <= 0) return clean.slice(0, targetCount);
  const result = [];
  for (let index = 0; index < targetCount; index += 1) {
    const targetDistance = (total * index) / Math.max(targetCount - 1, 1);
    let segmentIndex = 1;
    while (segmentIndex < distances.length - 1 && distances[segmentIndex] < targetDistance) {
      segmentIndex += 1;
    }
    const startDistance = distances[segmentIndex - 1];
    const endDistance = distances[segmentIndex];
    const ratio = endDistance === startDistance ? 0 : (targetDistance - startDistance) / (endDistance - startDistance);
    const start = clean[segmentIndex - 1];
    const end = clean[segmentIndex];
    result.push({ x: start.x + (end.x - start.x) * ratio, y: start.y + (end.y - start.y) * ratio });
  }
  return result;
}

function pointDistance(a, b) {
  if (!a || !b) return Infinity;
  return Math.hypot(a.x - b.x, a.y - b.y);
}

async function rotateSelectedCircularStart() {
  const selected = getSelectedGraphItem();
  if (!selected || selected.kind !== "node") return;
  const rawOffset = window.prompt("New circular start offset (0-based bp)", "0");
  if (rawOffset == null) return;
  const offset = Number(rawOffset.trim());
  if (!Number.isInteger(offset) || offset < 0) {
    showToast("Offset must be a non-negative integer");
    return;
  }
  const payload = await postJsonAction(
    "/api/rotate_circular_node",
    { node_id: selected.id, offset },
    "Circular start rotated",
  );
  const details = latestHistoryDetails(payload, "rotate_circular_node");
  if (details?.node_id) {
    pendingSelectNodeId = details.node_id;
    selectGraphNode(details.node_id);
  }
}

async function postJsonAction(path, payload, success) {
  return callAndRender(path, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    loading: "Updating graph...",
    success,
    relayout: shouldAutoRedraw(),
  });
}

async function callAndRender(path, options) {
  try {
    setStatus(options.loading || "Loading...");
    const response = await fetch(path, options);
    if (!response.ok) {
      const error = await readError(response);
      throw new Error(error);
    }
    const previousPayload = graphState;
    const payload = await response.json();
    const relayout = typeof options.relayout === "function"
      ? options.relayout(payload, previousPayload)
      : options.relayout ?? true;
    renderGraph(payload, { relayout });
    showToast(options.success || "Done");
    setStatus(options.success || "Ready");
    return payload;
  } catch (error) {
    setStatus(error.message);
    showToast(error.message);
    return null;
  }
}

function latestHistoryDetails(payload, action) {
  const history = payload?.session?.history || [];
  const event = history[history.length - 1];
  return event?.action === action ? event.details || null : null;
}

async function readError(response) {
  try {
    const data = await response.json();
    return data.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

function renderGraph(payload, options = {}) {
  graphState = payload;
  dom.emptyState.style.display = "none";
  dom.sourceName.textContent = payload.session?.source_name || "loaded.gfa";
  renderStats(payload.stats);
  renderHistogram(payload.histogram || []);
  renderHistory(payload.session || {});
  updateGlobalButtons(payload.session);
  updateServerSavePath();
  updateAlignmentCommandPreview();
  updateAlignmentReadSelect(payload.session?.alignment);
  renderAlignmentQueryControls(payload.session?.alignment);

  const elements = [
    ...payload.nodes.map((node) => ({ data: enrichNodeData(node.data, payload.stats) })),
    ...payload.edges.map((edge) => ({ data: enrichEdgeData(edge.data) })),
  ];

  if (!cy) {
    cy = cytoscape({
      container: dom.cyLayer,
      elements,
      minZoom: 0.04,
      maxZoom: 4,
      style: cytoscapeStyle(),
      layout: layoutConfig(false),
    });
    cy.on("select unselect", "node, edge", () => updateSelection());
    cy.on("zoom", updateZoomDisplay);
    cy.on("tap", (event) => {
      if (event.target === cy) {
        cy.elements().unselect();
      }
    });
  } else {
    syncGraphElements(elements, Boolean(options.relayout));
  }
  applyFilters();
  updateSelection();
  if (isTwinMode()) {
    activateTwinRenderer(Boolean(options.relayout));
  } else if (isBandageMode()) {
    activateBandageRenderer(Boolean(options.relayout));
  } else {
    activateCytoscapeRenderer();
    updateZoomDisplay();
  }
  pendingRename = null;
  pendingDuplicateSource = null;
  pendingMergeLayout = null;
}

function syncGraphElements(elements, relayout) {
  if (!cy) return;
  const nextById = new Map(elements.map((element) => [element.data.id, element]));
  const previousPositions = new Map();
  cy.nodes().forEach((node) => {
    previousPositions.set(node.id(), { ...node.position() });
  });

  cy.elements().forEach((element) => {
    if (!nextById.has(element.id())) {
      element.remove();
    }
  });

  elements.forEach((element) => {
    const existing = cy.getElementById(element.data.id);
    if (existing.length) {
      existing.data(element.data);
      return;
    }
    const added = cy.add(element);
    if (added.isNode()) {
      const renamePosition =
        pendingRename && pendingRename.newId === element.data.id
          ? previousPositions.get(pendingRename.oldId)
          : null;
      const sourcePosition = pendingDuplicateSource
        ? previousPositions.get(pendingDuplicateSource)
        : null;
      const mergePosition = mergedCytoscapePosition(element.data.id);
      if (renamePosition) {
        added.position(renamePosition);
      } else if (mergePosition) {
        added.position(mergePosition);
      } else if (sourcePosition) {
        added.position({ x: sourcePosition.x + 42, y: sourcePosition.y + 42 });
      }
    }
  });

  if (relayout) {
    runLayout(true);
  }
}

function cytoscapeStyle() {
  return [
    {
      selector: "node",
      style: {
        label: "data(renderLabel)",
        width: "data(renderWidth)",
        height: "data(renderHeight)",
        shape: "data(shape)",
        "background-color": "data(renderColor)",
        "border-width": "data(blastBorderWidth)",
        "border-color": "data(blastBorderColor)",
        color: "#1f2521",
        "font-size": 10,
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 7,
        "text-outline-width": "data(textOutlineWidth)",
        "text-outline-color": "#fbfcf8",
        "overlay-padding": 8,
      },
    },
    {
      selector: "edge",
      style: {
        width: "data(width)",
        label: "data(renderLabel)",
        "font-size": 9,
        "line-color": "data(renderColor)",
        "target-arrow-shape": "triangle",
        "target-arrow-color": "data(renderColor)",
        "curve-style": "bezier",
        opacity: 0.82,
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 4,
        "border-color": "#3f67b1",
      },
    },
    {
      selector: "edge:selected",
      style: {
        "line-color": "#3f67b1",
        "target-arrow-color": "#3f67b1",
        width: 5,
      },
    },
  ];
}

function enrichNodeData(data, stats) {
  const isBandage = isBandageMode();
  const nodeWidth = displayContigWidth();
  const circleScale = displayNodeSizeScale();
  return {
    ...data,
    renderLabel: buildNodeLabel(data),
    renderColor: chooseNodeColor(data, stats, "cytoscape"),
    renderWidth: isBandage ? data.bandageWidth : data.size * circleScale,
    renderHeight: isBandage ? nodeWidth : data.size * circleScale,
    shape: isBandage ? "rectangle" : "ellipse",
    textOutlineWidth: dom.textOutline?.checked ? 2 : 0,
    blastBorderWidth: data.blastBest ? 3 : 1,
    blastBorderColor: alignmentDataHasVisibleHit(data) ? alignmentHitColor(data) : "rgba(31, 37, 33, 0.18)",
  };
}

function enrichEdgeData(data) {
  const baseWidth = Number(data.baseWidth || data.width || 2);
  const width = Math.max(0.6, baseWidth * displayLinkWidthScale());
  return {
    ...data,
    baseWidth,
    width,
    renderColor: chooseEdgeColor(data, "cytoscape"),
    renderLabel: dom.showLinkLabels?.checked ? data.customLabel || data.label || "" : "",
  };
}

function displayNodeSizeScale() {
  return clamp(Number(dom.nodeSizeScale?.value || 1), 0.45, 3);
}

function displayContigWidth() {
  return clamp(Number(dom.nodeWidth?.value || 18), 6, 56);
}

function displayLinkWidthScale() {
  return clamp(Number(dom.linkWidthScale?.value || 1), 0.4, 4);
}

function displayEdgeWidth(edge) {
  return Math.max(0.6, Number(edge?.baseWidth || edge?.width || 2) * displayLinkWidthScale());
}

function chooseNodeColor(data, stats, renderer = "cytoscape") {
  if (data.customColor) return data.customColor;
  const mode = dom.colorMode.value;
  if (mode === "random") {
    if (!randomColorById.has(data.id)) {
      randomColorById.set(data.id, randomPalette[randomColorById.size % randomPalette.length]);
    }
    return randomColorById.get(data.id);
  }
  if (mode === "alignment") {
    if (alignmentDataHasVisibleHit(data)) {
      if (renderer === "bandage") {
        return showAlignmentHitBackground() && alignmentDataShowsHitBackground(data)
          ? alignmentHitBackgroundColor(data)
          : visibleAlignmentSpans(data).length
            ? ALIGNMENT_UNHIT_NODE_COLOR
            : alignmentHitColor(data);
      }
      return alignmentHitColor(data);
    }
    return ALIGNMENT_UNHIT_NODE_COLOR;
  }
  if (mode === "read_path") {
    if (alignmentDataHasVisibleHit(data)) {
      if (renderer === "bandage") {
        return showAlignmentHitBackground() && alignmentDataShowsHitBackground(data)
          ? alignmentHitBackgroundColor(data)
          : visibleAlignmentSpans(data).length
            ? ALIGNMENT_UNHIT_NODE_COLOR
            : alignmentHitColor(data);
      }
      return alignmentHitColor(data);
    }
    return ALIGNMENT_UNHIT_NODE_COLOR;
  }
  if (mode === "degree") {
    const maxDegree = Math.max(...(graphState?.nodes || []).map((node) => node.data.degree || 0), 1);
    const ratio = (data.degree || 0) / maxDegree;
    return interpolateColor([231, 236, 224], [63, 103, 177], ratio);
  }
  return data.color || "#dbe1d4";
}

function chooseEdgeColor(data, renderer = "cytoscape") {
  if (data.customColor) return data.customColor;
  const mode = dom.colorMode.value;
  if (mode === "alignment") {
    return alignmentDataHasVisibleHit(data) ? alignmentHitColor(data) : ALIGNMENT_UNHIT_LINK_COLOR;
  }
  if (mode === "read_path") {
    return alignmentDataHasVisibleHit(data) ? alignmentHitColor(data) : ALIGNMENT_UNHIT_LINK_COLOR;
  }
  return data.customColor || "#9ba797";
}

function buildNodeLabel(data) {
  const lines = [];
  if (dom.labelName?.checked) lines.push(data.customLabel || data.id);
  if (dom.labelLength?.checked) lines.push(`${number(data.length)} bp`);
  if (dom.labelDepth?.checked && data.depth != null) lines.push(`${number(data.depth)}x`);
  if (dom.labelBlast?.checked) lines.push(`Align ${number(data.blastHitCount || 0)}`);
  return lines.join("\n");
}

function refreshVisualProperties() {
  if (!cy || !graphState) return;
  if (usesBandageRenderer()) {
    updateBandageVisibilityFromFilters();
    renderBandageSvg();
  }
  if (usesCytoscapeRenderer()) {
    cy.nodes().forEach((node) => {
      node.data(enrichNodeData(node.data(), graphState.stats));
    });
    cy.edges().forEach((edge) => {
      edge.data(enrichEdgeData(edge.data()));
    });
    cy.style().update();
  }
}

function runLayout(animate) {
  if (isTwinMode()) {
    layoutBandageGraph({ reset: true });
    renderBandageSvg();
    runCytoscapeLayout(animate);
    return;
  }
  if (isBandageMode()) {
    layoutBandageGraph({ reset: true });
    renderBandageSvg();
    return;
  }
  runCytoscapeLayout(animate);
}

function runCytoscapeLayout(animate) {
  if (!cy) return;
  cy.layout(layoutConfig(animate)).run();
}

function layoutConfig(animate) {
  if (isBandageMode()) {
    const config = getBandageModeConfig();
    return {
      name: "cose",
      animate,
      padding: 54,
      idealEdgeLength: config.coseIdealEdgeLength,
      nodeRepulsion: config.coseNodeRepulsion,
      componentSpacing: config.coseComponentSpacing,
      refresh: 20,
    };
  }
  return {
    name: "cose",
    animate,
    padding: 44,
    idealEdgeLength: 85,
    nodeRepulsion: 6800,
    componentSpacing: 80,
    refresh: 20,
  };
}

function applyFilters() {
  if (!graphState) return;
  if (usesCytoscapeRenderer()) {
    applyCytoscapeFilters();
  }
  if (usesBandageRenderer()) {
    updateBandageVisibilityFromFilters();
    renderBandageSvg();
  }
  updateVisibleCount();
}

function applyCytoscapeFilters() {
  if (!cy || !graphState) return;
  const query = dom.nodeSearch.value.trim().toLowerCase();
  const minDepth = Number(dom.minDepth.value || 0);

  cy.nodes().forEach((node) => {
    const data = node.data();
    const passSearch = !query || nodeMatches(data, query);
    const passDepth = data.depth == null || Number(data.depth) >= minDepth;
    if (passSearch && passDepth) {
      node.show();
    } else {
      node.hide();
    }
  });

  cy.edges().forEach((edge) => {
    if (edge.source().visible() && edge.target().visible()) {
      edge.show();
    } else {
      edge.hide();
    }
  });
}

function nodeMatches(data, query) {
  const matchMode = document.querySelector('input[name="match-mode"]:checked')?.value || "partial";
  const best = data.blastBest;
  const fields = [
    data.id,
    data.customLabel,
    data.renderLabel,
    best?.qseqid,
    best?.sseqid,
    best?.path,
    best?.pident,
    data.tags ? JSON.stringify(data.tags) : "",
  ]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());
  if (matchMode === "exact") {
    return fields.some((field) => field === query);
  }
  return fields.some((field) => field.includes(query));
}

function findNodes() {
  if (isBandageMode()) {
    findBandageNodes();
    return;
  }
  if (isTwinMode()) {
    findTwinNodes();
    return;
  }
  if (!cy) return;
  const query = dom.nodeSearch.value.trim().toLowerCase();
  if (!query) {
    showToast("Enter a node name");
    return;
  }
  const matches = cy.nodes().filter((node) => nodeMatches(node.data(), query));
  cy.elements().unselect();
  matches.select();
  if (matches.length) {
    cy.fit(matches, 90);
    showToast(`Found ${matches.length} node(s)`);
  } else {
    showToast("No matching nodes");
  }
}

function findTwinNodes() {
  if (!cy) return;
  const query = dom.nodeSearch.value.trim().toLowerCase();
  if (!query) {
    showToast("Enter a node name");
    return;
  }
  const matches = cy.nodes().filter((node) => nodeMatches(node.data(), query));
  cy.elements().unselect();
  matches.select();
  if (!matches.length) {
    showToast("No matching nodes");
    return;
  }
  const matchIds = matches.map((node) => node.id());
  bandageState.visibleNodeIds = new Set(matchIds);
  bandageState.visibleEdgeIds = new Set(
    getClientEdges()
      .filter((edge) => bandageState.visibleNodeIds.has(edge.source) && bandageState.visibleNodeIds.has(edge.target))
      .map((edge) => edge.id),
  );
  setSingleBandageSelection({ kind: "node", id: matchIds[0] });
  cy.fit(matches, 90);
  fitBandageToView();
  renderBandageSelection();
  updateVisibleCount();
  showToast(`Found ${matches.length} node(s)`);
}

function drawGraphManually() {
  if (isBandageMode()) {
    drawBandageGraphManually();
    return;
  }
  if (isTwinMode()) {
    drawTwinGraphManually();
    return;
  }
  if (!cy || !graphState) return;
  const scope = dom.drawScope.value;
  if (scope === "selection") {
    const selectedNode = cy.nodes(":selected")[0];
    if (!selectedNode) {
      showToast("Select a node first");
      return;
    }
    showNeighborhood(selectedNode);
  } else if (scope === "entire") {
    cy.elements().show();
    updateVisibleCount();
  } else {
    applyFilters();
  }
  refreshVisualProperties();
  runLayout(true);
  setTimeout(() => {
    if (cy) cy.fit(cy.elements(":visible"), 50);
  }, 120);
  setStatus("Draw graph complete");
}

function drawTwinGraphManually() {
  if (!cy || !graphState) return;
  const scope = dom.drawScope.value;
  if (scope === "selection") {
    const selected = getSelectedGraphItem();
    if (!selected || selected.kind !== "node") {
      showToast("Select a node first");
      return;
    }
    const cyNode = cy.getElementById(selected.id);
    if (cyNode.length) {
      showNeighborhood(cyNode);
    }
    setSingleBandageSelection({ kind: "node", id: selected.id });
    const ids = new Set([selected.id]);
    const edgeIds = new Set();
    getClientEdges().forEach((edge) => {
      if (edge.source === selected.id || edge.target === selected.id) {
        ids.add(edge.source);
        ids.add(edge.target);
        edgeIds.add(edge.id);
      }
    });
    bandageState.visibleNodeIds = ids;
    bandageState.visibleEdgeIds = edgeIds;
  } else if (scope === "entire") {
    cy.elements().show();
    bandageState.visibleNodeIds = new Set(getClientNodes().map((node) => node.id));
    bandageState.visibleEdgeIds = new Set(getClientEdges().map((edge) => edge.id));
  } else {
    applyCytoscapeFilters();
    updateBandageVisibilityFromFilters();
  }
  cy.nodes().forEach((node) => {
    node.data(enrichNodeData(node.data(), graphState.stats));
  });
  cy.edges().forEach((edge) => {
    edge.data(enrichEdgeData(edge.data()));
  });
  cy.style().update();
  layoutBandageGraph({ reset: true });
  fitBandageToView();
  renderBandageSelection();
  runCytoscapeLayout(true);
  setTimeout(() => {
    if (cy) cy.fit(cy.elements(":visible"), 50);
  }, 120);
  updateVisibleCount();
  setStatus("Draw graph complete");
}

function showNeighborhood(selectedNode) {
  const neighborhood = selectedNode.closedNeighborhood();
  cy.elements().hide();
  neighborhood.show();
  selectedNode.show();
  updateVisibleCount();
}

function updateVisibleCount() {
  if (usesBandageRenderer() && !usesCytoscapeRenderer()) {
    dom.visibleCount.textContent = `${bandageState.visibleNodeIds.size} nodes / ${bandageState.visibleEdgeIds.size} links`;
    return;
  }
  if (!cy) return;
  dom.visibleCount.textContent = `${cy.nodes(":visible").length} nodes / ${cy.edges(":visible").length} links`;
}

function updateZoomDisplay() {
  if (usesBandageRenderer() && !usesCytoscapeRenderer()) {
    dom.zoomLevel.value = Math.round(bandageState.transform.scale * 100);
    return;
  }
  if (!cy || !dom.zoomLevel) return;
  dom.zoomLevel.value = Math.round(cy.zoom() * 100);
}

function applyZoomInput() {
  if (usesBandageRenderer()) {
    const zoom = Math.max(5, Math.min(500, Number(dom.zoomLevel.value || 100))) / 100;
    bandageState.transform.scale = zoom;
    renderBandageSvg();
    if (!usesCytoscapeRenderer()) {
      updateZoomDisplay();
      return;
    }
  }
  if (!cy) return;
  const zoom = Math.max(5, Math.min(500, Number(dom.zoomLevel.value || 100))) / 100;
  cy.zoom({
    level: zoom,
    renderedPosition: { x: dom.graph.clientWidth / 2, y: dom.graph.clientHeight / 2 },
  });
  updateZoomDisplay();
}

function updateSelection() {
  if (isBandageMode()) {
    renderBandageSelection();
    return;
  }
  if (!cy) {
    resetDetails();
    return;
  }
  const selected = cy.$(":selected")[0];
  if (!selected) {
    if (isTwinMode()) {
      clearBandageSelection();
      renderBandageSvg();
    }
    resetDetails();
    updateSelectionButtons(null);
    return;
  }
  if (isTwinMode()) {
    syncBandageSelectionFromCytoscape();
    renderBandageSvg();
  }
  updateSelectionButtons(selected);
  if (selected.isNode()) {
    renderNodeDetails(selected.data());
  } else {
    renderEdgeDetails(selected.data());
  }
}

function updateSelectionButtons(selected) {
  const hasGraph = Boolean(graphState);
  const selection = getSelectedGraphSelection();
  const selectedCount = selection.nodeIds.length + selection.edgeIds.length;
  const isNode =
    selected &&
    (typeof selected.isNode === "function" ? selected.isNode() : selected.kind === "node");
  dom.deleteSelectedButton.disabled = !hasGraph || !selected;
  dom.deleteAllSelectedButton.disabled = !hasGraph || !selectedCount;
  dom.duplicateNodeButton.disabled = !hasGraph || !selected || !isNode;
  dom.mergeLinkButton.disabled = !canMergeCurrentSelection();
  dom.exportSelectedButton.disabled = !hasGraph
    || (dom.exportFormat?.value === "svg" ? !selectedCount : !selection.edgeIds.length);
  dom.rotateCircularButton.disabled = !hasGraph || !selected || !isNode;
  updateRepeatResolutionButtons();
}

function canMergeCurrentSelection() {
  if (!graphState) return false;
  const selection = getSelectedGraphSelection();
  return selection.edgeIds.length === 1 || selection.nodeIds.length >= 2;
}

function getSelectedGraphSelection() {
  if (isBandageMode()) {
    return getBandageGraphSelection();
  }
  if (cy) {
    const selected = cy.$(":selected");
    const nodeIds = [];
    const edgeIds = [];
    selected.nodes().forEach((node) => nodeIds.push(node.id()));
    selected.edges().forEach((edge) => edgeIds.push(edge.id()));
    if (nodeIds.length || edgeIds.length) {
      const primary = selected[0]
        ? { kind: selected[0].isNode() ? "node" : "edge", id: selected[0].id() }
        : null;
      return { nodeIds, edgeIds, primary };
    }
  }
  if (usesBandageRenderer() && bandageState.selected) {
    return getBandageGraphSelection();
  }
  return { nodeIds: [], edgeIds: [], primary: null };
}

function getBandageGraphSelection() {
  const nodeIds = [...bandageState.selectedNodeIds];
  const edgeIds = [...bandageState.selectedEdgeIds];
  if (nodeIds.length || edgeIds.length) {
    return { nodeIds, edgeIds, primary: bandageState.selected };
  }
  return selectionFromSingleItem(bandageState.selected);
}

function selectionFromSingleItem(item) {
  if (!item) return { nodeIds: [], edgeIds: [], primary: null };
  return {
    nodeIds: item.kind === "node" ? [item.id] : [],
    edgeIds: item.kind === "edge" ? [item.id] : [],
    primary: item,
  };
}

function getSelectedGraphItem() {
  return getSelectedGraphSelection().primary;
}

function setRepeatResolutionContext(context) {
  repeatResolutionContext = context;
  updateRepeatResolutionButtons();
}

function updateRepeatResolutionButtons() {
  const context = getRepeatResolutionContext();
  const disabled = !Boolean(context);
  if (dom.repeatResolutionAButton) dom.repeatResolutionAButton.disabled = disabled;
  if (dom.repeatResolutionBButton) dom.repeatResolutionBButton.disabled = disabled;
}

function getRepeatResolutionContext() {
  if (!graphState) return null;
  if (isValidRepeatResolutionContext(repeatResolutionContext)) {
    return repeatResolutionContext;
  }
  const selected = getSelectedGraphItem();
  const selectedContext = inferRepeatResolutionContextFromNode(selected?.kind === "node" ? selected.id : null);
  if (selectedContext) return selectedContext;
  const history = graphState.session?.history || [];
  for (let index = history.length - 1; index >= 0; index -= 1) {
    const event = history[index];
    if (event.action !== "duplicate_node") continue;
    const context = {
      sourceId: event.details?.source_node_id,
      duplicateId: event.details?.new_node_id,
    };
    if (isValidRepeatResolutionContext(context)) return context;
  }
  return null;
}

function inferRepeatResolutionContextFromNode(nodeId) {
  if (!nodeId) return null;
  const copyMatch = nodeId.match(/^(.*)_copy\d+$/);
  if (copyMatch) {
    const context = { sourceId: copyMatch[1], duplicateId: nodeId };
    if (isValidRepeatResolutionContext(context)) return context;
  }
  const copy = getClientNodes().find((node) => node.id.startsWith(`${nodeId}_copy`));
  if (!copy) return null;
  const context = { sourceId: nodeId, duplicateId: copy.id };
  return isValidRepeatResolutionContext(context) ? context : null;
}

function isValidRepeatResolutionContext(context) {
  if (!context?.sourceId || !context?.duplicateId) return false;
  if (context.sourceId === context.duplicateId) return false;
  const ids = new Set(getClientNodes().map((node) => node.id));
  if (!ids.has(context.sourceId) || !ids.has(context.duplicateId)) return false;
  return isRepeatResolutionReadyNode(context.sourceId) && isRepeatResolutionReadyNode(context.duplicateId);
}

function isRepeatResolutionReadyNode(nodeId) {
  const counts = { "-": 0, "+": 0 };
  getClientEdges().forEach((edge) => {
    if (edge.source === nodeId) {
      counts[getGfaEndpointSide(edge.sourceOrient, "source")] += 1;
    } else if (edge.target === nodeId) {
      counts[getGfaEndpointSide(edge.targetOrient, "target")] += 1;
    }
  });
  return counts["-"] === 2 && counts["+"] === 2;
}

async function runRepeatResolution(strategy) {
  const context = getRepeatResolutionContext();
  if (!context) {
    showToast("Duplicate a repeat node first");
    return;
  }
  const payload = await postJsonAction(
    "/api/repeat_resolution",
    {
      node_id: context.sourceId,
      duplicate_id: context.duplicateId,
      strategy,
    },
    `Repeat resolution ${strategy} complete`,
  );
  if (payload) {
    setRepeatResolutionContext(null);
  }
}

function selectGraphNode(nodeId, options = {}) {
  if (!nodeId || !graphState) return;
  const shouldFit = options.fit !== false;
  if (cy) {
    const node = cy.getElementById(nodeId);
    if (node.length) {
      cy.elements().unselect();
      node.select();
      if (shouldFit && !isBandageMode()) {
        cy.fit(node, 100);
      }
    }
  }
  if (usesBandageRenderer()) {
    setSingleBandageSelection({ kind: "node", id: nodeId });
    renderBandageSelection();
  }
  pendingSelectNodeId = null;
}

function updateGlobalButtons(session) {
  const hasGraph = Boolean(graphState);
  dom.undoButton.disabled = !session?.can_undo;
  dom.redoButton.disabled = !session?.can_redo;
  dom.exportButton.disabled = !hasGraph;
  dom.quickExportButton.disabled = !hasGraph;
  dom.exportSvgButton.disabled = !hasGraph;
  dom.exportSelectedButton.disabled = true;
  dom.exportHistoryButton.disabled = !hasGraph;
  dom.fitButton.disabled = !hasGraph;
  dom.deleteAllSelectedButton.disabled = true;
  dom.findNodeButton.disabled = !hasGraph;
  dom.drawGraphButton.disabled = !hasGraph;
  dom.drawGraphToolbarButton.disabled = !hasGraph;
  dom.serverSaveButton.disabled = !hasGraph || !isBackendExportFormat(dom.exportFormat?.value);
  updateServerFileButtons();
  updateHistoryFileButtons();
  updateSftpButtons();
  updateAlignmentButtons();
  updateRepeatResolutionButtons();
}

function isBandageMode() {
  return BANDAGE_LAYOUTS.has(currentLayout);
}

function isTwinMode() {
  return currentLayout === "twin";
}

function usesBandageRenderer() {
  return isBandageMode() || isTwinMode();
}

function usesCytoscapeRenderer() {
  return !isBandageMode() || isTwinMode();
}

function getBandageModeConfig() {
  return BANDAGE_MODE_CONFIGS[isTwinMode() ? "bandage_native" : currentLayout] || BANDAGE_MODE_CONFIGS.bandage_native;
}

function bindBandageSvgEvents() {
  const svg = dom.bandageSvg;
  svg.addEventListener("pointerdown", (event) => {
    if (!usesBandageRenderer() || !graphState) return;
    event.preventDefault();
    svg.setPointerCapture(event.pointerId);
    const hit = getBandageEventTarget(event.target);
    bandageState.pointer = {
      down: true,
      mode: hit?.kind === "node" ? "node" : "pan",
      id: hit?.kind === "node" ? hit.id : null,
      lastX: event.clientX,
      lastY: event.clientY,
    };
    if (hit) {
      const additive = event.shiftKey || event.metaKey || event.ctrlKey;
      updateBandageSelection(hit, additive);
      syncCytoscapeSelectionFromBandage(hit, additive, isBandageItemSelected(hit.kind, hit.id));
      if (hit.kind === "node") {
        dom.graph.classList.add("bandage-dragging");
      }
      renderBandageSelection();
    } else {
      clearBandageSelection();
      if (isTwinMode() && cy) {
        cy.elements().unselect();
      }
      resetDetails();
      updateSelectionButtons(null);
      renderBandageSvg();
    }
  });

  svg.addEventListener("pointermove", (event) => {
    if (!usesBandageRenderer() || !bandageState.pointer.down) return;
    const pointer = bandageState.pointer;
    const dx = event.clientX - pointer.lastX;
    const dy = event.clientY - pointer.lastY;
    pointer.lastX = event.clientX;
    pointer.lastY = event.clientY;
    if (pointer.mode === "node" && pointer.id) {
      const node = bandageState.nodes.get(pointer.id);
      if (node) {
        moveBandageNode(node, dx / bandageState.transform.scale, dy / bandageState.transform.scale);
        if (isTwinMode()) {
          nudgeCytoscapePosition(pointer.id, dx, dy);
        } else {
          syncCytoscapePosition(pointer.id, node);
        }
      }
    } else {
      bandageState.transform.x += dx;
      bandageState.transform.y += dy;
    }
    dom.graph.classList.add("bandage-dragging");
    renderBandageSvg();
    updateZoomDisplay();
  });

  svg.addEventListener("pointerup", (event) => {
    if (!usesBandageRenderer()) return;
    bandageState.pointer.down = false;
    dom.graph.classList.remove("bandage-dragging");
    try {
      svg.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture can already be released after browser-level interruptions.
    }
  });

  svg.addEventListener("pointercancel", () => {
    bandageState.pointer.down = false;
    dom.graph.classList.remove("bandage-dragging");
  });

  svg.addEventListener(
    "wheel",
    (event) => {
      if (!usesBandageRenderer()) return;
      event.preventDefault();
      const rect = svg.getBoundingClientRect();
      const sx = event.clientX - rect.left;
      const sy = event.clientY - rect.top;
      const before = screenPointToWorld(sx, sy);
      const factor = event.deltaY < 0 ? 1.12 : 0.88;
      const nextScale = Math.max(0.05, Math.min(5, bandageState.transform.scale * factor));
      bandageState.transform.scale = nextScale;
      bandageState.transform.x = sx - before.x * nextScale;
      bandageState.transform.y = sy - before.y * nextScale;
      renderBandageSvg();
      updateZoomDisplay();
    },
    { passive: false },
  );

  window.addEventListener("resize", () => {
    if (!usesBandageRenderer()) return;
    resizeBandageSvg();
    renderBandageSvg();
  });
}

function activateCytoscapeRenderer() {
  dom.graph.classList.remove("bandage-active", "twin-active", "bandage-dragging");
  if (cy) {
    cy.resize();
    cy.style().update();
  }
  updateSelection();
}

function activateBandageRenderer(relayout = false) {
  dom.graph.classList.remove("twin-active");
  dom.graph.classList.add("bandage-active");
  resizeBandageSvg();
  updateBandageVisibilityFromFilters();
  if (relayout || !bandageState.nodes.size) {
    layoutBandageGraph({ reset: relayout });
    fitBandageToView();
  } else {
    syncBandageNodeStore();
  }
  renderBandageSvg();
  renderBandageSelection();
  updateZoomDisplay();
  updateVisibleCount();
}

function activateTwinRenderer(relayout = false) {
  dom.graph.classList.remove("bandage-active", "bandage-dragging");
  dom.graph.classList.add("twin-active");
  if (cy) {
    cy.resize();
    cy.style().update();
  }
  resizeBandageSvg();
  updateBandageVisibilityFromFilters();
  if (relayout || !bandageState.nodes.size) {
    layoutBandageGraph({ reset: relayout });
    fitBandageToView();
  } else {
    syncBandageNodeStore();
  }
  renderBandageSvg();
  renderBandageSelection();
  if (relayout) {
    runCytoscapeLayout(true);
  }
  updateZoomDisplay();
  updateVisibleCount();
}

function getClientNodes() {
  return graphState?.nodes?.map((node) => node.data) || [];
}

function getClientEdges() {
  return graphState?.edges?.map((edge) => edge.data) || [];
}

function getNodeData(id) {
  return getClientNodes().find((node) => node.id === id) || null;
}

function getEdgeData(id) {
  return getClientEdges().find((edge) => edge.id === id) || null;
}

function updateBandageVisibilityFromFilters() {
  bandageState.lengthScale = null;
  bandageState.visibleNodeIds.clear();
  bandageState.visibleEdgeIds.clear();
  if (!graphState) return;
  const query = dom.nodeSearch.value.trim().toLowerCase();
  const minDepth = Number(dom.minDepth.value || 0);
  getClientNodes().forEach((node) => {
    const passSearch = !query || nodeMatches(node, query);
    const passDepth = node.depth == null || Number(node.depth) >= minDepth;
    if (passSearch && passDepth) {
      bandageState.visibleNodeIds.add(node.id);
    }
  });
  getClientEdges().forEach((edge) => {
    if (bandageState.visibleNodeIds.has(edge.source) && bandageState.visibleNodeIds.has(edge.target)) {
      bandageState.visibleEdgeIds.add(edge.id);
    }
  });
  pruneBandageSelectionToVisible();
}

function isBandageSelectionVisible(selection) {
  if (!selection) return false;
  if (selection.kind === "node") return bandageState.visibleNodeIds.has(selection.id);
  return bandageState.visibleEdgeIds.has(selection.id);
}

function syncBandageNodeStore() {
  const existing = new Set(getClientNodes().map((node) => node.id));
  if (pendingRename && existing.has(pendingRename.newId) && bandageState.nodes.has(pendingRename.oldId)) {
    const oldState = bandageState.nodes.get(pendingRename.oldId);
    bandageState.nodes.set(pendingRename.newId, cloneBandageState(oldState));
  }
  Array.from(bandageState.nodes.keys()).forEach((id) => {
    if (!existing.has(id)) {
      bandageState.nodes.delete(id);
    }
  });
  const seedMap = getBandageSeedMap(getClientNodes());
  getClientNodes().forEach((node, index) => {
    const existingState = bandageState.nodes.get(node.id);
    if (existingState) {
      ensureEndpointState(node, existingState);
      return;
    }
    const mergeState = mergedBandageState(node);
    if (mergeState) {
      bandageState.nodes.set(node.id, mergeState);
      syncCytoscapePosition(node.id, mergeState);
      return;
    }
    const sourceState = pendingDuplicateSource ? bandageState.nodes.get(pendingDuplicateSource) : null;
    if (sourceState) {
      const state = cloneBandageState(sourceState);
      moveBandageNode(state, 46, 46);
      state.bend = deterministicBend(node.id) * getBandageModeConfig().bendMultiplier;
      bandageState.nodes.set(node.id, state);
      return;
    }
    const center = seedMap.get(node.id) || fallbackBandageCenter(index, getClientNodes().length);
    const angle = estimateBandageAngle(node.id, seedMap, center, index);
    bandageState.nodes.set(node.id, createBandageState(node, center, angle));
  });
}

function runBandageSeedLayout() {
  if (!cy) return;
  const config = getBandageModeConfig();
  cy.resize();
  cy.layout({
    name: "cose",
    animate: false,
    fit: false,
    padding: 70,
    idealEdgeLength: config.seedIdealEdgeLength,
    nodeRepulsion: config.seedNodeRepulsion,
    componentSpacing: config.seedComponentSpacing,
    refresh: 24,
  }).run();
}

function layoutBandageGraph({ reset = false } = {}) {
  if (reset) {
    bandageState.layoutSeed += 1;
    runBandageSeedLayout();
  }
  bandageState.lengthScale = null;
  syncBandageNodeStore();
  const visibleNodes = getClientNodes().filter((node) => bandageState.visibleNodeIds.has(node.id));
  const visibleEdges = getClientEdges().filter((edge) => bandageState.visibleEdgeIds.has(edge.id));
  if (!visibleNodes.length) return;
  const config = getBandageModeConfig();
  bandageState.lengthScale = getBandageLengthScale(visibleNodes);

  if (reset) {
    const seedMap = getBandageSeedMap(visibleNodes);
    visibleNodes.forEach((node, index) => {
      const center = seedMap.get(node.id) || fallbackBandageCenter(index, visibleNodes.length);
      const angle = estimateBandageAngle(node.id, seedMap, center, index);
      bandageState.nodes.set(node.id, createBandageState(node, center, angle));
    });
  }

  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    ensureEndpointState(node, state);
  });

  const adjacency = buildBandageAdjacency(visibleNodes, visibleEdges);
  if (config.flexibleGlyphs) {
    if (reset) {
      layoutFlexibleBandageCandidates(visibleNodes, visibleEdges, adjacency, config);
    } else {
      layoutFlexibleBandageGraph(visibleNodes, visibleEdges, adjacency, config);
    }
    return;
  }

  const iterations = visibleNodes.length > 260 ? config.iterationsLarge : config.iterationsSmall;
  for (let step = 0; step < iterations; step += 1) {
    const displacements = new Map(visibleNodes.map((node) => [node.id, { x: 0, y: 0 }]));
    const rotations = new Map(visibleNodes.map((node) => [node.id, 0]));

    visibleEdges.forEach((edge) => {
      const source = getEndpointRef(edge.source, edge.sourceOrient, "source");
      const target = getEndpointRef(edge.target, edge.targetOrient, "target");
      if (!source || !target) return;
      addEndpointSpring(
        displacements,
        rotations,
        source,
        target,
        getBandageLinkTargetDistance(visibleNodes.length),
        config.springStrength,
        config.springTorqueStrength || 0,
      );
    });

    for (let i = 0; i < visibleNodes.length; i += 1) {
      const aNode = visibleNodes[i];
      const a = bandageState.nodes.get(aNode.id);
      for (let j = i + 1; j < visibleNodes.length; j += 1) {
        const bNode = visibleNodes[j];
        const b = bandageState.nodes.get(bNode.id);
        const minDistance =
          displayContigWidth() * config.centerWidthFactor +
          (getBandageGlyphLength(aNode) + getBandageGlyphLength(bNode)) * config.centerLengthFactor;
        addCenterRepulsion(displacements, aNode.id, a, bNode.id, b, minDistance, config.centerStrength);
        addCapsuleRepulsion(displacements, aNode, bNode, config.capsuleStrength, config.capsulePadding);
      }
    }

    if (config.linkNodeStrength > 0) {
      visibleEdges.forEach((edge) => {
        const geometry = getLinkGeometry(edge);
        if (!geometry) return;
        visibleNodes.forEach((node) => {
          if (node.id === edge.source || node.id === edge.target) return;
          addLinkNodeRepulsion(displacements, geometry, node, config.linkNodeStrength, config.linkNodePadding);
        });
      });
    }

    if (config.radialExpansionStrength > 0) {
      addRadialExpansion(displacements, visibleNodes, config);
    }

    if (step % 4 === 0) {
      relaxBandageAngles(visibleNodes, adjacency, config.angleRelaxStep);
    }

    const cooling = 0.95 - (step / iterations) * 0.58;
    visibleNodes.forEach((node) => {
      const state = bandageState.nodes.get(node.id);
      const displacement = displacements.get(node.id);
      const rotation = rotations.get(node.id) || 0;
      if (!state || !displacement) return;
      state.x += clamp(displacement.x * cooling, -config.maxMove, config.maxMove);
      state.y += clamp(displacement.y * cooling, -config.maxMove, config.maxMove);
      state.angle += clamp(rotation * cooling, -(config.maxRotation || 0), config.maxRotation || 0);
      syncBandageGlyphEndpoints(node, state);
    });
  }
  relaxBandageAngles(visibleNodes, adjacency, config.angleRelaxFinal);
  visibleNodes.forEach((node) => {
    syncBandageGlyphEndpoints(node, bandageState.nodes.get(node.id));
  });
}

function layoutFlexibleBandageGraph(visibleNodes, visibleEdges, adjacency, config) {
  visibleNodes.forEach((node) => {
    syncFlexibleGlyphState(node, bandageState.nodes.get(node.id), config);
  });
  runFlexibleSimulation(visibleNodes, visibleEdges, config);
  constrainFlexibleSegmentLengths(visibleNodes, config, Math.max(2, Math.floor((config.segmentConstraintPasses || 4) / 2)));
  const turnPasses = config.turnAngleConstraintPasses ?? 2;
  if (turnPasses > 0) {
    constrainFlexibleTurnAngles(visibleNodes, config, turnPasses);
  }
  resolveFlexibleSegmentOverlaps(visibleNodes, config);
  visibleNodes.forEach((node) => {
    syncFlexibleGlyphState(node, bandageState.nodes.get(node.id), config);
  });
}

function runFlexibleSimulation(visibleNodes, visibleEdges, config) {
  const startedAt = performance.now();
  const { points, links, pointByKey } = buildFlexibleSimulationGraph(visibleNodes, visibleEdges, config);
  points.forEach((point, index) => {
    point.simIndex = index;
  });
  const indexedLinks = indexFlexibleSimulationLinks(links, pointByKey);
  const linkedPairs = new Set(indexedLinks.map((link) => simulationPairKey(link.sourceIndex, link.targetIndex)));
  const gfaPairs = new Set(
    indexedLinks
      .filter((link) => link.kind === "gfa")
      .map((link) => simulationPairKey(link.sourceIndex, link.targetIndex)),
  );
  const gfaNodePairs = new Set(
    indexedLinks
      .filter((link) => link.kind === "gfa")
      .map((link) => simulationNodePairKey(link.sourcePoint.nodeId, link.targetPoint.nodeId)),
  );
  const pointIndexesByNode = groupSimulationPointsByNode(points);
  const segments = indexedLinks
    .filter((link) => link.kind === "segment")
    .map((link) => ({
      sourceIndex: link.sourceIndex,
      targetIndex: link.targetIndex,
      nodeId: link.sourcePoint.nodeId,
      localIndex: Math.min(link.sourcePoint.index, link.targetPoint.index),
      distance: link.distance,
    }));
  window.__bandageLastSimulation = {
    points: points.length,
    links: indexedLinks.length,
    internalLinks: indexedLinks.filter((link) => link.kind === "segment").length,
    gfaLinks: indexedLinks.filter((link) => link.kind === "gfa").length,
    elapsedMs: 0,
  };
  if (!points.length) return;
  const usedVirtualCose = runFlexibleVirtualCose(points, indexedLinks, visibleNodes.length, config);
  const iterations = visibleNodes.length > 260
    ? config.simulationIterationsLarge || 220
    : config.simulationIterationsSmall || 420;
  const refinementIterations = usedVirtualCose ? Math.max(90, Math.floor(iterations * 0.45)) : iterations;
  const collisionEvery = Math.max(1, config.simulationSegmentCollisionEvery || 4);
  for (let step = 0; step < refinementIterations; step += 1) {
    const alpha = 1 - step / Math.max(refinementIterations, 1);
    const displacements = makeSimulationDisplacements(points.length);
    addFlexibleSimulationSprings(points, indexedLinks, displacements, config, alpha);
    addFlexibleSimulationRepulsion(points, displacements, linkedPairs, config, alpha);
    if (step % collisionEvery === 0) {
      addFlexibleSimulationSegmentCollisions(points, segments, displacements, gfaPairs, config, alpha, step);
    }
    addFlexibleSimulationCentering(points, displacements, config);
    applyFlexibleSimulationDisplacements(points, displacements, config, alpha);
    clampFlexibleSimulationPoints(points, config);
    if (step % 18 === 0) {
      constrainFlexibleSimulationSegmentLengths(points, segments, 1, 0.42);
    }
  }
  untangleFlexibleSimulationGlyphs(
    points,
    segments,
    indexedLinks,
    pointIndexesByNode,
    gfaNodePairs,
    config,
    config.simulationUntanglePasses || 0,
  );
  retightenFlexibleSimulationLinks(points, segments, indexedLinks, config);
  untangleFlexibleSimulationGlyphs(
    points,
    segments,
    indexedLinks,
    pointIndexesByNode,
    gfaNodePairs,
    config,
    Math.min(18, Math.floor((config.simulationUntanglePasses || 0) / 3)),
  );
  constrainFlexibleSimulationSegmentLengths(points, segments, 3, 0.55);
  writeFlexibleSimulationPoints(points);
  window.__bandageLastSimulation.elapsedMs = Math.round(performance.now() - startedAt);
}

function indexFlexibleSimulationLinks(links, pointByKey) {
  return links
    .map((link) => {
      const sourcePoint = pointByKey.get(link.source);
      const targetPoint = pointByKey.get(link.target);
      if (!sourcePoint || !targetPoint) return null;
      return {
        ...link,
        sourcePoint,
        targetPoint,
        sourceIndex: sourcePoint.simIndex,
        targetIndex: targetPoint.simIndex,
      };
    })
    .filter(Boolean);
}

function runFlexibleVirtualCose(points, links, nodeCount, config) {
  if (!config.virtualCose || typeof cytoscape !== "function" || !points.length) return false;
  const elements = [
    ...points.map((point) => ({
      data: { id: point.key },
      position: { x: point.x, y: point.y },
    })),
    ...links.map((link, index) => ({
      data: {
        id: `virtual-link-${index}`,
        source: link.sourcePoint.key,
        target: link.targetPoint.key,
        kind: link.kind,
        distance: link.distance,
      },
    })),
  ];
  const virtualCy = cytoscape({
    headless: true,
    styleEnabled: false,
    elements,
  });
  const iterations = nodeCount > 260
    ? config.virtualCoseIterationsLarge || 160
    : config.virtualCoseIterationsSmall || 280;
  virtualCy.layout({
    name: "cose",
    animate: false,
    fit: false,
    randomize: false,
    componentSpacing: config.seedComponentSpacing || 100,
    nodeOverlap: Math.max(10, displayContigWidth() * 1.4),
    idealEdgeLength: (edge) => edge.data("distance"),
    edgeElasticity: (edge) => (
      edge.data("kind") === "gfa"
        ? config.virtualCoseLinkElasticity || 420
        : config.virtualCoseSegmentElasticity || 85
    ),
    nodeRepulsion: () => config.virtualCoseNodeRepulsion || 12000,
    gravity: config.virtualCoseGravity || 0.04,
    numIter: iterations,
    initialTemp: 180,
    coolingFactor: 0.96,
    minTemp: 1.0,
  }).run();
  points.forEach((point) => {
    const cyPoint = virtualCy.getElementById(point.key);
    if (!cyPoint.length) return;
    const position = cyPoint.position();
    if (Number.isFinite(position.x) && Number.isFinite(position.y)) {
      point.x = position.x;
      point.y = position.y;
    }
  });
  virtualCy.destroy();
  return true;
}

function makeSimulationDisplacements(count) {
  return {
    dx: new Float64Array(count),
    dy: new Float64Array(count),
  };
}

function groupSimulationPointsByNode(points) {
  const groups = new Map();
  points.forEach((point, index) => {
    if (!groups.has(point.nodeId)) groups.set(point.nodeId, []);
    groups.get(point.nodeId).push(index);
  });
  return groups;
}

function untangleFlexibleSimulationGlyphs(
  points,
  segments,
  links,
  pointIndexesByNode,
  gfaNodePairs,
  config,
  passes,
) {
  if (!passes || passes <= 0) return;
  const nodeIds = Array.from(pointIndexesByNode.keys());
  const segmentsByNode = groupSimulationSegmentsByNode(segments);
  const width = displayContigWidth();
  const minDistance = width + (config.simulationSegmentPadding || 10);
  const crossingForce = config.simulationUntangleCrossingForce || 16;
  const overlapStrength = config.simulationUntangleOverlapStrength || 0.24;
  const maxMove = config.simulationUntangleMaxMove || 20;
  const springEvery = Math.max(1, config.simulationUntangleEvery || 2);
  for (let pass = 0; pass < passes; pass += 1) {
    const displacements = makeSimulationDisplacements(points.length);
    let adjusted = false;
    for (let i = 0; i < nodeIds.length; i += 1) {
      const aId = nodeIds[i];
      const aSegments = segmentsByNode.get(aId) || [];
      if (!aSegments.length) continue;
      for (let j = i + 1; j < nodeIds.length; j += 1) {
        const bId = nodeIds[j];
        const bSegments = segmentsByNode.get(bId) || [];
        if (!bSegments.length) continue;
        const linked = gfaNodePairs.has(simulationNodePairKey(aId, bId));
        const score = scoreSimulationNodePair(points, aSegments, bSegments, `${aId}:${bId}:${pass}`);
        const tooClose = score.minDistance < minDistance;
        if (!score.intersections && (linked || !tooClose)) continue;
        const centerA = getSimulationNodeCenter(points, pointIndexesByNode.get(aId));
        const centerB = getSimulationNodeCenter(points, pointIndexesByNode.get(bId));
        const direction = centerDirection(centerA, centerB, `${aId}:${bId}:untangle:${pass}`, score.minDistance);
        const overlapForce = Math.max(0, minDistance - score.minDistance) * overlapStrength;
        const force = Math.min(maxMove, score.intersections * crossingForce + overlapForce);
        addSimulationNodeGroupDisplacement(displacements, pointIndexesByNode.get(aId), direction.x * force, direction.y * force);
        addSimulationNodeGroupDisplacement(displacements, pointIndexesByNode.get(bId), -direction.x * force, -direction.y * force);
        adjusted = true;
      }
    }
    if (pass % springEvery === 0) {
      addFlexibleSimulationSprings(points, links, displacements, config, 0.35);
    }
    if (!adjusted && pass > 3) break;
    applyFlexibleSimulationDisplacementsWithLimit(points, displacements, maxMove);
    constrainFlexibleSimulationSegmentLengths(points, segments, 1, 0.48);
  }
}

function groupSimulationSegmentsByNode(segments) {
  const groups = new Map();
  segments.forEach((segment) => {
    if (!groups.has(segment.nodeId)) groups.set(segment.nodeId, []);
    groups.get(segment.nodeId).push(segment);
  });
  return groups;
}

function scoreSimulationNodePair(points, aSegments, bSegments, seed) {
  let intersections = 0;
  let minDistance = Infinity;
  aSegments.forEach((aSegment) => {
    bSegments.forEach((bSegment) => {
      const vector = closestSimulationSegments(points, aSegment, bSegment, seed);
      if (!vector) return;
      if (vector.intersecting) intersections += 1;
      minDistance = Math.min(minDistance, vector.distance);
    });
  });
  return { intersections, minDistance };
}

function getSimulationNodeCenter(points, indexes) {
  if (!indexes?.length) return { x: 0, y: 0 };
  const sum = indexes.reduce((acc, index) => {
    acc.x += points[index].x;
    acc.y += points[index].y;
    return acc;
  }, { x: 0, y: 0 });
  return { x: sum.x / indexes.length, y: sum.y / indexes.length };
}

function addSimulationNodeGroupDisplacement(displacements, indexes, dx, dy) {
  if (!indexes?.length) return;
  indexes.forEach((index) => {
    displacements.dx[index] += dx;
    displacements.dy[index] += dy;
  });
}

function retightenFlexibleSimulationLinks(points, segments, links, config) {
  const passes = config.simulationRetightenPasses || 0;
  for (let pass = 0; pass < passes; pass += 1) {
    const displacements = makeSimulationDisplacements(points.length);
    addFlexibleSimulationSprings(points, links, displacements, config, 0.42);
    applyFlexibleSimulationDisplacementsWithLimit(points, displacements, Math.max(6, (config.simulationMaxMove || 18) * 0.42));
    if (pass % 2 === 0) {
      constrainFlexibleSimulationSegmentLengths(points, segments, 1, 0.5);
    }
  }
}

function applyFlexibleSimulationDisplacementsWithLimit(points, displacements, maxMove) {
  points.forEach((point, index) => {
    point.x += clamp(displacements.dx[index], -maxMove, maxMove);
    point.y += clamp(displacements.dy[index], -maxMove, maxMove);
  });
}

function addFlexibleSimulationSprings(points, links, displacements, config, alpha) {
  const cooling = 0.35 + alpha * 0.65;
  links.forEach((link) => {
    const source = points[link.sourceIndex];
    const target = points[link.targetIndex];
    const vx = target.x - source.x;
    const vy = target.y - source.y;
    const distance = Math.max(Math.hypot(vx, vy), 0.001);
    const force = (distance - link.distance) * link.strength * cooling;
    const fx = (vx / distance) * force;
    const fy = (vy / distance) * force;
    displacements.dx[link.sourceIndex] += fx;
    displacements.dy[link.sourceIndex] += fy;
    displacements.dx[link.targetIndex] -= fx;
    displacements.dy[link.targetIndex] -= fy;
  });
}

function addFlexibleSimulationRepulsion(points, displacements, linkedPairs, config, alpha) {
  const width = displayContigWidth();
  const collisionDistance = Math.max(width * (config.simulationCollisionRadiusFactor || 1.4), width + 8);
  const chargeDistance = config.simulationChargeDistanceMax || 220;
  const chargeStrength = config.simulationRepulsionStrength || 2600;
  const collisionStrength = config.simulationCollisionStrength || 0.28;
  const sameNodeFactor = config.simulationSameNodeRepulsionFactor || 0.45;
  const cooling = 0.25 + alpha * 0.75;
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    for (let j = i + 1; j < points.length; j += 1) {
      const b = points[j];
      if (linkedPairs.has(simulationPairKey(i, j))) continue;
      const sameNode = a.nodeId === b.nodeId;
      if (sameNode && Math.abs(a.index - b.index) <= 2) continue;
      let vx = a.x - b.x;
      let vy = a.y - b.y;
      let distance = Math.hypot(vx, vy);
      if (distance < 0.001) {
        const angle = Math.PI * 2 * hashNumber(`${a.key}:${b.key}:repel`);
        vx = Math.cos(angle);
        vy = Math.sin(angle);
        distance = 1;
      }
      if (distance >= chargeDistance && distance >= collisionDistance) continue;
      let force = 0;
      if (distance < collisionDistance) {
        force += (collisionDistance - distance) * collisionStrength;
      }
      if (distance < chargeDistance) {
        force += (chargeStrength / Math.max(distance * distance, 36)) * Math.pow(1 - distance / chargeDistance, 1.6);
      }
      if (sameNode) force *= sameNodeFactor;
      force *= cooling;
      const fx = (vx / distance) * force;
      const fy = (vy / distance) * force;
      displacements.dx[i] += fx;
      displacements.dy[i] += fy;
      displacements.dx[j] -= fx;
      displacements.dy[j] -= fy;
    }
  }
}

function addFlexibleSimulationSegmentCollisions(points, segments, displacements, gfaPairs, config, alpha, step) {
  const width = displayContigWidth();
  const minDistance = width + (config.simulationSegmentPadding || 8);
  const strength = config.simulationSegmentCollisionStrength || 0.34;
  const crossingBoost = config.segmentCrossingStrength || 12;
  const cooling = 0.2 + alpha * 0.8;
  for (let i = 0; i < segments.length; i += 1) {
    const a = segments[i];
    for (let j = i + 1; j < segments.length; j += 1) {
      const b = segments[j];
      if (a.nodeId === b.nodeId && Math.abs(a.localIndex - b.localIndex) <= 2) continue;
      if (segmentsShareGfaEndpoint(a, b, gfaPairs)) continue;
      const vector = closestSimulationSegments(points, a, b, `${a.nodeId}:${a.localIndex}:${b.nodeId}:${b.localIndex}:${step}`);
      if (!vector || vector.distance >= minDistance) continue;
      let force = (minDistance - vector.distance) * strength * cooling;
      if (vector.intersecting) force += crossingBoost * cooling;
      force = Math.min(force, config.simulationSegmentMaxForce || 24);
      addWeightedSimulationDisplacement(displacements, a.sourceIndex, 1 - vector.aT, vector.x * force, vector.y * force);
      addWeightedSimulationDisplacement(displacements, a.targetIndex, vector.aT, vector.x * force, vector.y * force);
      addWeightedSimulationDisplacement(displacements, b.sourceIndex, 1 - vector.bT, -vector.x * force, -vector.y * force);
      addWeightedSimulationDisplacement(displacements, b.targetIndex, vector.bT, -vector.x * force, -vector.y * force);
    }
  }
}

function closestSimulationSegments(points, aSegment, bSegment, seed) {
  const a0 = points[aSegment.sourceIndex];
  const a1 = points[aSegment.targetIndex];
  const b0 = points[bSegment.sourceIndex];
  const b1 = points[bSegment.targetIndex];
  if (segmentsIntersect(a0, a1, b0, b1)) {
    const direction = centerDirection(midpoint(a0, a1), midpoint(b0, b1), seed, 0);
    return { distance: 0, x: direction.x, y: direction.y, aT: 0.5, bT: 0.5, intersecting: true };
  }
  const candidates = [
    simulationEndpointToSegment(a0, b0, b1, 0, true),
    simulationEndpointToSegment(a1, b0, b1, 1, true),
    simulationEndpointToSegment(b0, a0, a1, 0, false),
    simulationEndpointToSegment(b1, a0, a1, 1, false),
  ];
  let best = candidates[0];
  candidates.forEach((candidate) => {
    if (candidate.distance < best.distance) best = candidate;
  });
  if (best.distance < 0.001) {
    const direction = centerDirection(midpoint(a0, a1), midpoint(b0, b1), seed, best.distance);
    return { ...best, x: direction.x, y: direction.y };
  }
  return best;
}

function simulationEndpointToSegment(point, start, end, endpointT, pointBelongsToA) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSq = dx * dx + dy * dy;
  const segmentT = lengthSq <= 0
    ? 0
    : clamp(((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSq, 0, 1);
  const closest = { x: start.x + dx * segmentT, y: start.y + dy * segmentT };
  const vx = point.x - closest.x;
  const vy = point.y - closest.y;
  const distance = Math.hypot(vx, vy);
  const x = distance < 0.001 ? 1 : vx / distance;
  const y = distance < 0.001 ? 0 : vy / distance;
  return pointBelongsToA
    ? { distance, x, y, aT: endpointT, bT: segmentT, intersecting: false }
    : { distance, x: -x, y: -y, aT: segmentT, bT: endpointT, intersecting: false };
}

function segmentsShareGfaEndpoint(a, b, gfaPairs) {
  return (
    gfaPairs.has(simulationPairKey(a.sourceIndex, b.sourceIndex)) ||
    gfaPairs.has(simulationPairKey(a.sourceIndex, b.targetIndex)) ||
    gfaPairs.has(simulationPairKey(a.targetIndex, b.sourceIndex)) ||
    gfaPairs.has(simulationPairKey(a.targetIndex, b.targetIndex))
  );
}

function addWeightedSimulationDisplacement(displacements, index, weight, dx, dy) {
  if (weight <= 0) return;
  displacements.dx[index] += dx * weight;
  displacements.dy[index] += dy * weight;
}

function addFlexibleSimulationCentering(points, displacements, config) {
  const strength = config.simulationCenterStrength || 0;
  if (!strength) return;
  points.forEach((point, index) => {
    displacements.dx[index] -= point.x * strength;
    displacements.dy[index] -= point.y * strength;
  });
}

function applyFlexibleSimulationDisplacements(points, displacements, config, alpha) {
  const maxMove = (config.simulationMaxMove || config.flexiblePointMaxMove || 18) * (0.45 + alpha * 0.55);
  points.forEach((point, index) => {
    point.x += clamp(displacements.dx[index], -maxMove, maxMove);
    point.y += clamp(displacements.dy[index], -maxMove, maxMove);
  });
}

function constrainFlexibleSimulationSegmentLengths(points, segments, passes = 1, strength = 0.45) {
  for (let pass = 0; pass < passes; pass += 1) {
    segments.forEach((segment) => {
      const source = points[segment.sourceIndex];
      const target = points[segment.targetIndex];
      const vx = target.x - source.x;
      const vy = target.y - source.y;
      const distance = Math.max(Math.hypot(vx, vy), 0.001);
      const correction = (distance - segment.distance) * 0.5 * strength;
      const cx = (vx / distance) * correction;
      const cy = (vy / distance) * correction;
      source.x += cx;
      source.y += cy;
      target.x -= cx;
      target.y -= cy;
    });
  }
}

function simulationPairKey(a, b) {
  return a < b ? `${a}:${b}` : `${b}:${a}`;
}

function simulationNodePairKey(a, b) {
  return a < b ? `${a}:${b}` : `${b}:${a}`;
}

function clampFlexibleSimulationPoints(points, config) {
  const limit = config.simulationCoordinateLimit || 5000;
  points.forEach((point) => {
    point.x = clamp(point.x, -limit, limit);
    point.y = clamp(point.y, -limit, limit);
  });
}

function buildFlexibleSimulationGraph(visibleNodes, visibleEdges, config) {
  const points = [];
  const links = [];
  const pointByKey = new Map();
  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    if (!state?.points?.length) return;
    const segmentLength = getBandageGlyphLength(node) / Math.max(state.points.length - 1, 1);
    state.points.forEach((point, index) => {
      const simPoint = {
        key: `${node.id}:${index}`,
        nodeId: node.id,
        index,
        x: point.x,
        y: point.y,
      };
      points.push(simPoint);
      pointByKey.set(simPoint.key, simPoint);
      if (index > 0) {
        links.push({
          kind: "segment",
          source: `${node.id}:${index - 1}`,
          target: simPoint.key,
          distance: segmentLength,
          strength: config.simulationInternalStrength || 0.9,
        });
      }
    });
  });
  visibleEdges.forEach((edge) => {
    const sourceKey = getFlexibleEndpointKey(edge.source, edge.sourceOrient, "source");
    const targetKey = getFlexibleEndpointKey(edge.target, edge.targetOrient, "target");
    if (!sourceKey || !targetKey || !pointByKey.has(sourceKey) || !pointByKey.has(targetKey)) return;
    links.push({
      kind: "gfa",
      source: sourceKey,
      target: targetKey,
      distance: getBandageLinkTargetDistance(visibleNodes.length),
      strength: config.simulationLinkStrength || 1.4,
    });
  });
  return { points, links, pointByKey };
}

function getFlexibleEndpointKey(nodeId, orient, role) {
  const state = bandageState.nodes.get(nodeId);
  if (!state?.points?.length) return null;
  const side = getGfaEndpointSide(orient, role);
  const index = side === "-" ? 0 : state.points.length - 1;
  return `${nodeId}:${index}`;
}

function writeFlexibleSimulationPoints(points) {
  points.forEach((simPoint) => {
    const state = bandageState.nodes.get(simPoint.nodeId);
    const point = state?.points?.[simPoint.index];
    if (!point) return;
    point.x = simPoint.x;
    point.y = simPoint.y;
  });
}

function readFlexibleSimulationPoints(points) {
  points.forEach((simPoint) => {
    const state = bandageState.nodes.get(simPoint.nodeId);
    const point = state?.points?.[simPoint.index];
    if (!point) return;
    simPoint.x = point.x;
    simPoint.y = point.y;
  });
}

function layoutFlexibleBandageCandidates(visibleNodes, visibleEdges, adjacency, config) {
  const baseStates = snapshotBandageStates(visibleNodes);
  const candidateCount = getFlexibleCandidateCount(visibleNodes.length, config);
  if (candidateCount <= 1) {
    restoreBandageStates(baseStates);
    perturbFlexibleSeedStates(visibleNodes, config, 0);
    layoutFlexibleBandageGraph(visibleNodes, visibleEdges, adjacency, config);
    return;
  }
  let bestScore = Infinity;
  let bestStates = null;
  for (let candidate = 0; candidate < candidateCount; candidate += 1) {
    restoreBandageStates(baseStates);
    perturbFlexibleSeedStates(visibleNodes, config, candidate);
    layoutFlexibleBandageGraph(visibleNodes, visibleEdges, adjacency, config);
    const score = scoreFlexibleLayout(visibleNodes, visibleEdges, config);
    if (score < bestScore) {
      bestScore = score;
      bestStates = snapshotBandageStates(visibleNodes);
    }
  }
  if (bestStates) {
    restoreBandageStates(bestStates);
  }
}

function getFlexibleCandidateCount(nodeCount, config) {
  if (nodeCount > 180) return config.redrawCandidatesLarge || 1;
  if (nodeCount > 70) return config.redrawCandidatesMedium || 2;
  return config.redrawCandidatesSmall || 3;
}

function snapshotBandageStates(nodes) {
  const snapshot = new Map();
  nodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    if (state) snapshot.set(node.id, cloneBandageState(state));
  });
  return snapshot;
}

function restoreBandageStates(snapshot) {
  snapshot.forEach((state, id) => {
    bandageState.nodes.set(id, cloneBandageState(state));
  });
}

function perturbFlexibleSeedStates(visibleNodes, config, candidate) {
  const seed = `${bandageState.layoutSeed}:${candidate}`;
  const jitterRadius = config.redrawJitterRadius || 120;
  visibleNodes.forEach((node, index) => {
    const state = bandageState.nodes.get(node.id);
    if (!state) return;
    const nodeSeed = `${seed}:${node.id}`;
    const angle = Math.PI * 2 * hashNumber(`${nodeSeed}:jitter-angle`);
    const radius = jitterRadius * (0.25 + hashNumber(`${nodeSeed}:jitter-radius`) * 0.75);
    moveBandageNode(state, Math.cos(angle) * radius, Math.sin(angle) * radius);
    reseedFlexibleGlyphShape(node, state, config, `${nodeSeed}:shape`, index);
  });
}

function reseedFlexibleGlyphShape(node, state, config, seed, index) {
  const length = getBandageGlyphLength(node);
  const center = averagePoints(state.points?.length ? state.points : [state.minus, state.plus].filter(Boolean));
  const angle =
    (Number.isFinite(state.angle) ? state.angle : 0) +
    (hashNumber(`${seed}:angle`) - 0.5) * Math.PI * 1.35 +
    (index % 2 === 0 ? 1 : -1) * 0.08;
  const half = length / 2;
  const direction = { x: Math.cos(angle), y: Math.sin(angle) };
  state.bend = seededSignedValue(`${seed}:bend`) * config.bendMultiplier;
  state.minus = { x: center.x - direction.x * half, y: center.y - direction.y * half };
  state.plus = { x: center.x + direction.x * half, y: center.y + direction.y * half };
  state.points = createNativePolylinePoints(state.minus, state.plus, state.bend, seed, config, length);
  syncFlexibleGlyphState(node, state, config);
}

function scoreFlexibleLayout(visibleNodes, visibleEdges, config) {
  let score = 0;
  let intersectionCount = 0;
  const width = displayContigWidth();
  for (let i = 0; i < visibleNodes.length; i += 1) {
    const aNode = visibleNodes[i];
    const a = getGlyphGeometry(aNode.id);
    if (!a) continue;
    for (let j = i + 1; j < visibleNodes.length; j += 1) {
      const bNode = visibleNodes[j];
      const b = getGlyphGeometry(bNode.id);
      if (!b) continue;
      const closest = closestGlyphVector(a, b, `${aNode.id}:${bNode.id}:score`);
      const minDistance = width + (config.capsulePadding || 30);
      if (closest.distance < minDistance) {
        score += Math.pow(minDistance - closest.distance, 2) * (config.overlapPenalty || 1);
      }
      const aSegments = glyphSegments(a);
      const bSegments = glyphSegments(b);
      aSegments.forEach((aSegment) => {
        bSegments.forEach((bSegment) => {
          if (segmentsIntersect(aSegment.start, aSegment.end, bSegment.start, bSegment.end)) {
            intersectionCount += 1;
          }
        });
      });
    }
  }
  score += intersectionCount * (config.intersectionPenalty || 5000);
  visibleEdges.forEach((edge) => {
    const geometry = getLinkGeometry(edge);
    if (!geometry) return;
    const linkLength = Math.hypot(geometry.target.x - geometry.source.x, geometry.target.y - geometry.source.y);
    score += linkLength * linkLength * (config.linkLengthPenalty || 0);
  });
  const bounds = getFlexibleLayoutBounds(visibleNodes);
  if (bounds) {
    score += bounds.width * bounds.height * (config.areaPenalty || 0);
  }
  return score;
}

function getFlexibleLayoutBounds(visibleNodes) {
  const points = [];
  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    if (state?.points?.length) points.push(...state.points);
  });
  if (!points.length) return null;
  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}

function makeFlexiblePointDisplacements(visibleNodes) {
  const displacements = new Map();
  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    if (!state?.points?.length) return;
    displacements.set(node.id, state.points.map(() => ({ x: 0, y: 0 })));
  });
  return displacements;
}

function addFlexibleEndpointSpring(displacements, a, b, desiredDistance, strength) {
  if (a.nodeId === b.nodeId || a.pointIndex === null || b.pointIndex === null) return;
  const dx = b.point.x - a.point.x;
  const dy = b.point.y - a.point.y;
  const distance = Math.max(Math.hypot(dx, dy), 0.001);
  const force = (distance - desiredDistance) * strength;
  const fx = (dx / distance) * force;
  const fy = (dy / distance) * force;
  addFlexiblePointDisplacement(displacements, a.nodeId, a.pointIndex, fx, fy);
  addFlexiblePointDisplacement(displacements, b.nodeId, b.pointIndex, -fx, -fy);
}

function addFlexibleSegmentSprings(displacements, node, config) {
  const state = bandageState.nodes.get(node.id);
  const points = state?.points;
  if (!points || points.length < 2) return;
  const target = getBandageGlyphLength(node) / (points.length - 1);
  for (let index = 1; index < points.length; index += 1) {
    const a = points[index - 1];
    const b = points[index];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.max(Math.hypot(dx, dy), 0.001);
    const force = (distance - target) * config.segmentSpringStrength;
    const fx = (dx / distance) * force;
    const fy = (dy / distance) * force;
    addFlexiblePointDisplacement(displacements, node.id, index - 1, fx, fy);
    addFlexiblePointDisplacement(displacements, node.id, index, -fx, -fy);
  }
}

function addFlexibleRestShape(displacements, node, config) {
  const state = bandageState.nodes.get(node.id);
  if (!state?.points || state.points.length < 3) return;
  const rest = createNativePolylinePoints(
    state.points[0],
    state.points[state.points.length - 1],
    state.bend || 0,
    node.id,
    config,
    getBandageGlyphLength(node),
    state.points.length,
  );
  for (let index = 1; index < state.points.length - 1; index += 1) {
    const point = state.points[index];
    const target = rest[index];
    addFlexiblePointDisplacement(
      displacements,
      node.id,
      index,
      (target.x - point.x) * config.restShapeStrength,
      (target.y - point.y) * config.restShapeStrength,
    );
  }
}

function addFlexibleCenterRepulsion(displacements, aNode, bNode, minDistance, strength) {
  const a = bandageState.nodes.get(aNode.id);
  const b = bandageState.nodes.get(bNode.id);
  if (!a || !b) return;
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  let distance = Math.hypot(dx, dy);
  let nx = dx;
  let ny = dy;
  if (distance < 0.001) {
    const angle = Math.PI * 2 * hashNumber(`${aNode.id}:${bNode.id}:flex-center`);
    nx = Math.cos(angle);
    ny = Math.sin(angle);
    distance = 1;
  }
  if (distance >= minDistance) return;
  const force = (minDistance - distance) * strength;
  addFlexibleGlyphDisplacement(displacements, aNode.id, (nx / distance) * force, (ny / distance) * force);
  addFlexibleGlyphDisplacement(displacements, bNode.id, (-nx / distance) * force, (-ny / distance) * force);
}

function addFlexibleGlyphRepulsion(displacements, aNode, bNode, strength, padding) {
  const a = getGlyphGeometry(aNode.id);
  const b = getGlyphGeometry(bNode.id);
  if (!a || !b) return;
  const closest = closestGlyphVector(a, b, `${aNode.id}:${bNode.id}:flex-glyph`);
  const minDistance = (a.width + b.width) / 2 + padding;
  if (closest.distance >= minDistance) return;
  const force = (minDistance - closest.distance) * strength;
  addFlexibleGlyphDisplacement(displacements, aNode.id, closest.x * force, closest.y * force);
  addFlexibleGlyphDisplacement(displacements, bNode.id, -closest.x * force, -closest.y * force);
}

function addFlexiblePointCloudRepulsion(displacements, aNode, bNode, config) {
  const a = bandageState.nodes.get(aNode.id);
  const b = bandageState.nodes.get(bNode.id);
  if (!a?.points?.length || !b?.points?.length) return;
  const minDistance = displayContigWidth() + (config.pointRepulsionPadding || 24);
  const strength = config.pointRepulsionStrength || 0.25;
  a.points.forEach((aPoint, aIndex) => {
    b.points.forEach((bPoint, bIndex) => {
      let dx = aPoint.x - bPoint.x;
      let dy = aPoint.y - bPoint.y;
      let distance = Math.hypot(dx, dy);
      if (distance < 0.001) {
        const angle = Math.PI * 2 * hashNumber(`${aNode.id}:${aIndex}:${bNode.id}:${bIndex}:point`);
        dx = Math.cos(angle);
        dy = Math.sin(angle);
        distance = 1;
      }
      if (distance >= minDistance) return;
      const force = (minDistance - distance) * strength;
      addFlexiblePointDisplacement(displacements, aNode.id, aIndex, (dx / distance) * force, (dy / distance) * force);
      addFlexiblePointDisplacement(displacements, bNode.id, bIndex, (-dx / distance) * force, (-dy / distance) * force);
    });
  });
}

function addFlexibleSegmentCrossingRepulsion(displacements, aNode, bNode, config) {
  const a = bandageState.nodes.get(aNode.id);
  const b = bandageState.nodes.get(bNode.id);
  if (!a?.points || !b?.points || a.points.length < 2 || b.points.length < 2) return;
  const force = config.segmentCrossingStrength || 12;
  for (let ai = 1; ai < a.points.length; ai += 1) {
    const aStart = a.points[ai - 1];
    const aEnd = a.points[ai];
    for (let bi = 1; bi < b.points.length; bi += 1) {
      const bStart = b.points[bi - 1];
      const bEnd = b.points[bi];
      if (!segmentsIntersect(aStart, aEnd, bStart, bEnd)) continue;
      const aMid = midpoint(aStart, aEnd);
      const bMid = midpoint(bStart, bEnd);
      const direction = centerDirection(aMid, bMid, `${aNode.id}:${ai}:${bNode.id}:${bi}:cross`, 0);
      addFlexiblePointDisplacement(displacements, aNode.id, ai - 1, direction.x * force, direction.y * force);
      addFlexiblePointDisplacement(displacements, aNode.id, ai, direction.x * force, direction.y * force);
      addFlexiblePointDisplacement(displacements, bNode.id, bi - 1, -direction.x * force, -direction.y * force);
      addFlexiblePointDisplacement(displacements, bNode.id, bi, -direction.x * force, -direction.y * force);
    }
  }
}

function addFlexibleLinkNodeRepulsion(displacements, linkGeometry, node, strength, padding) {
  const glyph = getGlyphGeometry(node.id);
  if (!glyph) return;
  const minDistance = glyph.width / 2 + padding;
  const samples = [0.18, 0.32, 0.5, 0.68, 0.82];
  let best = null;
  samples.forEach((t) => {
    const point = quadraticPoint(linkGeometry.source, linkGeometry.control, linkGeometry.target, t);
    const vector = pointToGlyphVector(point, glyph);
    if (!best || vector.distance < best.distance) {
      best = vector;
    }
  });
  if (!best || best.distance >= minDistance) return;
  const direction = best.distance < 0.001
    ? centerDirection(glyph.center, linkGeometry.label, `${node.id}:${linkGeometry.path}:flex-link`, best.distance)
    : { x: best.x / best.distance, y: best.y / best.distance };
  const force = (minDistance - best.distance) * strength;
  addFlexibleGlyphDisplacement(displacements, node.id, -direction.x * force, -direction.y * force);
}

function addFlexibleRadialExpansion(displacements, visibleNodes, config) {
  const centers = visibleNodes
    .map((node) => bandageState.nodes.get(node.id))
    .filter((state) => state && Number.isFinite(state.x) && Number.isFinite(state.y));
  if (!centers.length) return;
  const centroid = {
    x: centers.reduce((sum, state) => sum + state.x, 0) / centers.length,
    y: centers.reduce((sum, state) => sum + state.y, 0) / centers.length,
  };
  const targetRadius = Math.max(
    config.radialExpansionMinRadius || 0,
    Math.sqrt(Math.max(visibleNodes.length, 1)) * (config.radialExpansionRadiusFactor || 100),
  );
  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    if (!state?.points?.length) return;
    let dx = state.x - centroid.x;
    let dy = state.y - centroid.y;
    let distance = Math.hypot(dx, dy);
    if (distance < 0.001) {
      const angle = Math.PI * 2 * hashNumber(`${node.id}:flex-radial`);
      dx = Math.cos(angle);
      dy = Math.sin(angle);
      distance = 1;
    }
    const slack = Math.max(targetRadius - distance, 0);
    if (slack <= 0) return;
    const force = Math.min(14, slack * config.radialExpansionStrength);
    addFlexibleGlyphDisplacement(displacements, node.id, (dx / distance) * force, (dy / distance) * force);
  });
}

function applyFlexiblePointDisplacements(visibleNodes, displacements, cooling, config) {
  const maxMove = config.flexiblePointMaxMove || config.maxMove || 18;
  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    const nodeDisplacements = displacements.get(node.id);
    if (!state?.points?.length || !nodeDisplacements) return;
    state.points.forEach((point, index) => {
      const displacement = nodeDisplacements[index];
      if (!displacement) return;
      point.x += clamp(displacement.x * cooling, -maxMove, maxMove);
      point.y += clamp(displacement.y * cooling, -maxMove, maxMove);
    });
    syncFlexibleGlyphState(node, state, config);
  });
}

function refineFlexibleEndpointLinks(visibleNodes, visibleEdges, config) {
  const rounds = config.endpointRefineIterations || 0;
  for (let roundIndex = 0; roundIndex < rounds; roundIndex += 1) {
    const displacements = makeFlexiblePointDisplacements(visibleNodes);
    visibleEdges.forEach((edge) => {
      const source = getEndpointRef(edge.source, edge.sourceOrient, "source");
      const target = getEndpointRef(edge.target, edge.targetOrient, "target");
      if (!source || !target) return;
      addFlexibleEndpointSpring(
        displacements,
        source,
        target,
        getBandageLinkTargetDistance(visibleNodes.length),
        config.endpointRefineStrength || config.springStrength,
      );
    });
    visibleNodes.forEach((node) => {
      addFlexibleSegmentSprings(displacements, node, config);
      addFlexibleRestShape(displacements, node, config);
    });
    applyFlexiblePointDisplacements(visibleNodes, displacements, 0.34, config);
    constrainFlexibleSegmentLengths(visibleNodes, config, 1);
    constrainFlexibleTurnAngles(visibleNodes, config, 1);
  }
}

function constrainFlexibleSegmentLengths(visibleNodes, config, passes = 1) {
  for (let pass = 0; pass < passes; pass += 1) {
    visibleNodes.forEach((node) => {
      const state = bandageState.nodes.get(node.id);
      const points = state?.points;
      if (!points || points.length < 2) return;
      const target = getBandageGlyphLength(node) / (points.length - 1);
      for (let index = 1; index < points.length; index += 1) {
        const a = points[index - 1];
        const b = points[index];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distance = Math.max(Math.hypot(dx, dy), 0.001);
        const correction = (distance - target) * 0.5;
        const cx = (dx / distance) * correction;
        const cy = (dy / distance) * correction;
        a.x += cx;
        a.y += cy;
        b.x -= cx;
        b.y -= cy;
      }
      syncFlexibleGlyphState(node, state, config);
    });
  }
}

function constrainFlexibleTurnAngles(visibleNodes, config, passes = 1) {
  const strength = config.turnAngleStrength || 0.7;
  for (let pass = 0; pass < passes; pass += 1) {
    visibleNodes.forEach((node) => {
      const state = bandageState.nodes.get(node.id);
      const points = state?.points;
      if (!points || points.length < 3) return;
      const side = hashNumber(`${node.id}:turn-side`) > 0.5 ? 1 : -1;
      for (let index = 1; index < points.length - 1; index += 1) {
        const targetAngle = getNativeTurnAngle(node.id, index, config);
        const tangent = Math.tan(targetAngle / 2);
        if (!Number.isFinite(tangent) || Math.abs(tangent) < 0.001) continue;
        const previous = points[index - 1];
        const current = points[index];
        const next = points[index + 1];
        const dx = next.x - previous.x;
        const dy = next.y - previous.y;
        const chord = Math.hypot(dx, dy);
        if (chord < 0.001) continue;
        const midpoint = {
          x: (previous.x + next.x) / 2,
          y: (previous.y + next.y) / 2,
        };
        const normal = { x: -dy / chord, y: dx / chord };
        const offset = chord / (2 * tangent);
        const target = {
          x: midpoint.x + normal.x * offset * side,
          y: midpoint.y + normal.y * offset * side,
        };
        current.x += (target.x - current.x) * strength;
        current.y += (target.y - current.y) * strength;
      }
      syncFlexibleGlyphState(node, state, config);
    });
  }
}

function getNativeTurnAngle(nodeId, index, config) {
  const min = config.turnAngleMinDeg || config.targetTurnAngleDeg || 150;
  const max = config.turnAngleMaxDeg || config.targetTurnAngleDeg || 150;
  const degrees = min + (max - min) * hashNumber(`${nodeId}:${index}:turn-angle`);
  return (degrees * Math.PI) / 180;
}

function addFlexiblePointDisplacement(displacements, nodeId, index, dx, dy) {
  const points = displacements.get(nodeId);
  const point = points?.[index];
  if (!point) return;
  point.x += dx;
  point.y += dy;
}

function addFlexibleGlyphDisplacement(displacements, nodeId, dx, dy) {
  const points = displacements.get(nodeId);
  if (!points?.length) return;
  points.forEach((point) => {
    point.x += dx;
    point.y += dy;
  });
}

function resolveFlexibleSegmentOverlaps(visibleNodes, config) {
  const passes = config.overlapResolvePasses || 0;
  const minDistance = displayContigWidth() + (config.overlapResolvePadding || 12);
  for (let pass = 0; pass < passes; pass += 1) {
    const displacements = makeFlexiblePointDisplacements(visibleNodes);
    let adjusted = false;
    for (let i = 0; i < visibleNodes.length; i += 1) {
      const aNode = visibleNodes[i];
      const a = getGlyphGeometry(aNode.id);
      if (!a) continue;
      for (let j = i + 1; j < visibleNodes.length; j += 1) {
        const bNode = visibleNodes[j];
        const b = getGlyphGeometry(bNode.id);
        if (!b) continue;
        const vector = closestGlyphVector(a, b, `${aNode.id}:${bNode.id}:resolve`);
        if (vector.distance >= minDistance) continue;
        const extra = vector.distance < 0.001 ? (config.crossingResolveStrength || 18) : 0;
        const force = Math.min(28, (minDistance - vector.distance) * (config.overlapResolveStrength || 0.35) + extra);
        addFlexibleGlyphDisplacement(displacements, aNode.id, vector.x * force, vector.y * force);
        addFlexibleGlyphDisplacement(displacements, bNode.id, -vector.x * force, -vector.y * force);
        adjusted = true;
      }
    }
    if (!adjusted) break;
    applyFlexiblePointDisplacements(visibleNodes, displacements, 1, config);
  }
}

function resizeBandageSvg() {
  const svg = dom.bandageSvg;
  const rect = svg.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
}

function renderBandageSvg() {
  if (!graphState || !dom.bandageSvg) return;
  resizeBandageSvg();
  const svg = dom.bandageSvg;
  svg.replaceChildren();

  const viewport = svgEl("g", {
    class: "bandage-viewport",
    transform: `translate(${bandageState.transform.x} ${bandageState.transform.y}) scale(${bandageState.transform.scale})`,
  });
  const linksLayer = svgEl("g", { class: "bandage-links" });
  const contigsLayer = svgEl("g", { class: "bandage-contigs" });

  getClientEdges().forEach((edge) => {
    if (!bandageState.visibleEdgeIds.has(edge.id)) return;
    const geometry = getLinkGeometry(edge);
    if (!geometry) return;
    const color = chooseEdgeColor(edge);
    const edgeWidth = displayEdgeWidth(edge);
    const selected = isBandageItemSelected("edge", edge.id);
    const linkGroup = svgEl("g", {
      class: `bandage-link-group${selected ? " selected" : ""}`,
      "data-bandage-kind": "edge",
      "data-bandage-id": edge.id,
    });
    linkGroup.appendChild(
      svgEl("path", {
        class: "bandage-link-hit",
        d: geometry.path,
        "stroke-width": Math.max(14, edgeWidth * 4),
      }),
    );
    linkGroup.appendChild(
      svgEl("path", {
        class: "bandage-link",
        d: geometry.path,
        stroke: selected ? "#3347ff" : color,
        "stroke-width": selected ? Math.max(5, edgeWidth) : Math.max(2.3, edgeWidth * 0.78),
      }),
    );
    linkGroup.appendChild(
      svgEl("polygon", {
        points: geometry.arrow.map((point) => `${point.x},${point.y}`).join(" "),
        fill: selected ? "#3347ff" : color,
        "pointer-events": "none",
      }),
    );
    if (dom.showLinkLabels?.checked && (edge.customLabel || edge.label)) {
      linkGroup.appendChild(
        svgEl("text", {
          class: `bandage-link-label${dom.textOutline.checked ? " bandage-label-outline" : ""}`,
          x: geometry.label.x,
          y: geometry.label.y - 6,
        }, edge.customLabel || edge.label),
      );
    }
    linksLayer.appendChild(linkGroup);
  });

  getClientNodes().forEach((node) => {
    if (!bandageState.visibleNodeIds.has(node.id)) return;
    const geometry = getGlyphGeometry(node.id);
    if (!geometry) return;
    const selected = isBandageItemSelected("node", node.id);
    const contigGroup = svgEl("g", {
      class: `bandage-contig${selected ? " selected" : ""}`,
      "data-bandage-kind": "node",
      "data-bandage-id": node.id,
    });
    if (selected) {
      contigGroup.appendChild(
        svgEl("path", {
          class: "bandage-selection",
          d: geometry.path,
          "stroke-width": geometry.width + 9,
        }),
      );
    }
    contigGroup.appendChild(
      svgEl("path", {
        class: "bandage-contig-path",
        d: geometry.path,
        stroke: chooseNodeColor(node, graphState.stats, "bandage"),
        "stroke-width": geometry.width,
      }),
    );
    appendBandageAlignmentSpans(contigGroup, node, geometry);
    appendBandageEndpoint(contigGroup, geometry.start, "-");
    appendBandageEndpoint(contigGroup, geometry.end, "+");
    appendBandageNodeLabel(contigGroup, node, geometry);
    contigsLayer.appendChild(contigGroup);
  });

  viewport.append(linksLayer, contigsLayer);
  svg.appendChild(viewport);
}

function appendBandageAlignmentSpans(group, node, geometry) {
  const spans = visibleAlignmentSpans(node);
  const nodeLength = Number(node.length || 0);
  if (!spans.length || !nodeLength || !geometry.points?.length) return;
  const maxSpans = 40;
  spans.slice(0, maxSpans).forEach((span) => {
    const start = Number(span.start || 0);
    const end = Number(span.end || 0);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= 0) return;
    const startRatio = clamp((Math.min(start, end) - 1) / nodeLength, 0, 1);
    const endRatio = clamp(Math.max(start, end) / nodeLength, 0, 1);
    const spanPoints = subPolylineByRatio(geometry.points, startRatio, endRatio);
    if (spanPoints.length < 2) return;
    const path = polylinePath(spanPoints);
    const blockWidth = Math.max(5, geometry.width + 1.5);
    const color = alignmentQueryColor(span.qseqid || "__alignment__");
    group.appendChild(
      svgEl("path", {
        class: "bandage-query-hit-block",
        d: path,
        stroke: color,
        style: `stroke: ${color}`,
        "stroke-width": blockWidth,
        "data-read": span.qseqid || "",
      }),
    );
  });
}

function getGlyphGeometry(nodeId) {
  const node = getNodeData(nodeId);
  const state = bandageState.nodes.get(nodeId);
  if (!node || !state) return null;
  ensureEndpointState(node, state);
  const width = displayContigWidth();
  const start = { ...state.minus };
  const end = { ...state.plus };
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.max(Math.hypot(dx, dy), 1);
  const direction = { x: dx / length, y: dy / length };
  const normal = { x: -direction.y, y: direction.x };
  const config = getBandageModeConfig();
  const center = config.flexibleGlyphs && state.points?.length
    ? averagePoints(state.points)
    : { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
  const bend = clamp((state.bend || 0) * length * config.bendScale, -config.bendMax, config.bendMax);
  const control = { x: center.x + normal.x * bend, y: center.y + normal.y * bend };
  const points = config.flexibleGlyphs && state.points?.length > 1
    ? state.points.map((point) => ({ x: point.x, y: point.y }))
    : config.segmentGlyphs
    ? sampleNativePolyline(start, end, normal, bend, nodeId, config, getBandageGlyphLength(node))
    : [start, end];
  const path = config.segmentGlyphs || config.flexibleGlyphs ? polylinePath(points) : quadraticPath(start, control, end);
  return {
    width,
    start: points[0] || start,
    end: points[points.length - 1] || end,
    control,
    center,
    points,
    label: pointAtPolylineRatio(points, 0.5) || quadraticPoint(start, control, end, 0.5),
    path,
  };
}

function getGlyphEndpoint(nodeId, orient, role) {
  const geometry = getGlyphGeometry(nodeId);
  if (!geometry) return null;
  return getGfaEndpointSide(orient, role) === "-" ? geometry.start : geometry.end;
}

function getGfaEndpointSide(orient, role) {
  if (role === "target") {
    return orient === "-" ? "+" : "-";
  }
  return orient === "-" ? "-" : "+";
}

function getBandageGlyphLength(node) {
  const config = getBandageModeConfig();
  const sequenceLength = Number(node?.length || 0);
  if (sequenceLength > 0) {
    const scale = bandageState.lengthScale || getBandageLengthScale();
    return Math.max(scale.minGlyph, sequenceLength * scale.pixelsPerBp);
  }
  return Math.max(
    config.fallbackGlyphMin,
    Math.min(config.fallbackGlyphMax, (node.bandageWidth || 110) * config.fallbackGlyphMultiplier),
  );
}

function getBandageLengthScale(nodes = null) {
  const candidates = nodes || getClientNodes().filter((node) => bandageState.visibleNodeIds.has(node.id));
  const lengths = candidates
    .map((node) => Number(node.length || 0))
    .filter((length) => Number.isFinite(length) && length > 0);
  const maxLength = Math.max(...lengths, 1);
  const count = Math.max(candidates.length, 1);
  const config = getBandageModeConfig();
  const maxGlyph = count > 180 ? config.maxGlyphLarge : count > 70 ? config.maxGlyphMedium : config.maxGlyphSmall;
  const minGlyph = count > 180 ? config.minGlyphLarge : config.minGlyphSmall;
  return {
    maxLength,
    maxGlyph,
    minGlyph,
    pixelsPerBp: maxGlyph / maxLength,
  };
}

function getBandageLinkTargetDistance(nodeCount) {
  const config = getBandageModeConfig();
  if (nodeCount > 180) return config.linkDistanceLarge;
  if (nodeCount > 70) return config.linkDistanceMedium;
  return config.linkDistanceSmall;
}

function createBandageState(node, center, angle) {
  const config = getBandageModeConfig();
  const length = getBandageGlyphLength(node);
  const half = length / 2;
  const direction = { x: Math.cos(angle), y: Math.sin(angle) };
  const minus = { x: center.x - direction.x * half, y: center.y - direction.y * half };
  const plus = { x: center.x + direction.x * half, y: center.y + direction.y * half };
  const state = {
    x: center.x,
    y: center.y,
    angle,
    bend: deterministicBend(node.id) * config.bendMultiplier,
    minus,
    plus,
  };
  if (config.flexibleGlyphs) {
    state.points = createNativePolylinePoints(minus, plus, state.bend, node.id, config, length);
    syncFlexibleGlyphState(node, state, config);
  }
  return state;
}

function ensureEndpointState(node, state) {
  if (!state) return;
  const hasEndpoints =
    state.minus &&
    state.plus &&
    Number.isFinite(state.minus.x) &&
    Number.isFinite(state.minus.y) &&
    Number.isFinite(state.plus.x) &&
    Number.isFinite(state.plus.y);
  if (!hasEndpoints) {
    const angle = Number.isFinite(state.angle) ? state.angle : 0;
    const center = {
      x: Number.isFinite(state.x) ? state.x : 0,
      y: Number.isFinite(state.y) ? state.y : 0,
    };
    const next = createBandageState(node, center, angle);
    Object.assign(state, next);
  } else {
    updateBandageCenter(state);
  }
  if (!Number.isFinite(state.bend)) {
    state.bend = deterministicBend(node.id) * getBandageModeConfig().bendMultiplier;
  }
  syncBandageGlyphEndpoints(node, state);
}

function syncBandageGlyphEndpoints(node, state) {
  if (!node || !state) return;
  const config = getBandageModeConfig();
  if (config.flexibleGlyphs) {
    syncFlexibleGlyphState(node, state, config);
    return;
  }
  if (!Number.isFinite(state.x) || !Number.isFinite(state.y)) {
    updateBandageCenter(state);
  }
  const center = {
    x: Number.isFinite(state.x) ? state.x : 0,
    y: Number.isFinite(state.y) ? state.y : 0,
  };
  const angle = Number.isFinite(state.angle) ? state.angle : 0;
  const half = getBandageGlyphLength(node) / 2;
  const direction = { x: Math.cos(angle), y: Math.sin(angle) };
  state.x = center.x;
  state.y = center.y;
  state.angle = angle;
  state.minus = {
    x: center.x - direction.x * half,
    y: center.y - direction.y * half,
  };
  state.plus = {
    x: center.x + direction.x * half,
    y: center.y + direction.y * half,
  };
}

function updateBandageCenter(state) {
  if (!state?.minus || !state?.plus) return;
  state.x = (state.minus.x + state.plus.x) / 2;
  state.y = (state.minus.y + state.plus.y) / 2;
  state.angle = Math.atan2(state.plus.y - state.minus.y, state.plus.x - state.minus.x);
}

function syncFlexibleGlyphState(node, state, config = getBandageModeConfig()) {
  if (!node || !state) return;
  const targetLength = getBandageGlyphLength(node);
  if (!state.minus || !state.plus) {
    const angle = Number.isFinite(state.angle) ? state.angle : 0;
    const center = {
      x: Number.isFinite(state.x) ? state.x : 0,
      y: Number.isFinite(state.y) ? state.y : 0,
    };
    const half = targetLength / 2;
    const direction = { x: Math.cos(angle), y: Math.sin(angle) };
    state.minus = { x: center.x - direction.x * half, y: center.y - direction.y * half };
    state.plus = { x: center.x + direction.x * half, y: center.y + direction.y * half };
  }
  const desiredPointCount = getNativePolylinePointCount(targetLength, config);
  const invalidPoints =
    !state.points ||
    state.points.length !== desiredPointCount ||
    state.points.some((point) => !Number.isFinite(point.x) || !Number.isFinite(point.y));
  if (invalidPoints) {
    state.points = createNativePolylinePoints(state.minus, state.plus, state.bend || 0, node.id, config, targetLength);
  }
  state.minus = state.points[0];
  state.plus = state.points[state.points.length - 1];
  const center = averagePoints(state.points);
  state.x = center.x;
  state.y = center.y;
  state.angle = Math.atan2(state.plus.y - state.minus.y, state.plus.x - state.minus.x);
}

function averagePoints(points) {
  if (!points?.length) return { x: 0, y: 0 };
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
  };
}

function cloneBandageState(state) {
  return {
    x: state.x,
    y: state.y,
    angle: state.angle,
    bend: state.bend,
    minus: state.minus ? { ...state.minus } : null,
    plus: state.plus ? { ...state.plus } : null,
    points: state.points ? state.points.map((point) => ({ ...point })) : null,
  };
}

function moveBandageNode(state, dx, dy) {
  if (!state) return;
  if (state.points?.length) {
    state.points.forEach((point) => {
      point.x += dx;
      point.y += dy;
    });
    state.minus = state.points[0];
    state.plus = state.points[state.points.length - 1];
    const center = averagePoints(state.points);
    state.x = center.x;
    state.y = center.y;
    state.angle = Math.atan2(state.plus.y - state.minus.y, state.plus.x - state.minus.x);
    return;
  }
  state.x = (Number.isFinite(state.x) ? state.x : 0) + dx;
  state.y = (Number.isFinite(state.y) ? state.y : 0) + dy;
  if (state.minus && state.plus) {
    state.minus.x += dx;
    state.minus.y += dy;
    state.plus.x += dx;
    state.plus.y += dy;
  }
}

function syncCytoscapePosition(nodeId, state) {
  if (!cy || !state) return;
  const node = cy.getElementById(nodeId);
  if (node.length) {
    node.position({ x: state.x, y: state.y });
  }
}

function nudgeCytoscapePosition(nodeId, dx, dy) {
  if (!cy) return;
  const node = cy.getElementById(nodeId);
  if (!node.length) return;
  const position = node.position();
  const damp = 0.18;
  const maxStep = 8;
  node.position({
    x: position.x + clamp(dx * damp, -maxStep, maxStep),
    y: position.y + clamp(dy * damp, -maxStep, maxStep),
  });
}

function getBandageSeedMap(nodes) {
  const seedMap = new Map();
  if (!cy) return seedMap;
  const raw = [];
  nodes.forEach((node) => {
    const cyNode = cy.getElementById(node.id);
    if (!cyNode.length) return;
    const position = cyNode.position();
    if (Number.isFinite(position.x) && Number.isFinite(position.y)) {
      raw.push({ id: node.id, x: position.x, y: position.y });
    }
  });
  if (!raw.length) return seedMap;
  const mean = {
    x: raw.reduce((sum, point) => sum + point.x, 0) / raw.length,
    y: raw.reduce((sum, point) => sum + point.y, 0) / raw.length,
  };
  const spread = Math.max(
    ...raw.map((point) => Math.hypot(point.x - mean.x, point.y - mean.y)),
    0,
  );
  if (spread < 20) return seedMap;
  const scale = getBandageModeConfig().seedScale;
  raw.forEach((point) => {
    seedMap.set(point.id, {
      x: (point.x - mean.x) * scale,
      y: (point.y - mean.y) * scale,
    });
  });
  return seedMap;
}

function fallbackBandageCenter(index, count) {
  const radius = 120 + Math.sqrt(Math.max(count, 1)) * 46;
  const angle = (Math.PI * 2 * index) / Math.max(count, 1);
  const lane = 1 + (index % 4) * 0.18;
  return {
    x: Math.cos(angle) * radius * lane,
    y: Math.sin(angle) * radius * lane,
  };
}

function estimateBandageAngle(nodeId, seedMap, center, index) {
  let vx = 0;
  let vy = 0;
  getClientEdges().forEach((edge) => {
    const attachedAsSource = edge.source === nodeId;
    const attachedAsTarget = edge.target === nodeId;
    if (!attachedAsSource && !attachedAsTarget) return;
    const otherId = attachedAsSource ? edge.target : edge.source;
    const otherCenter = seedMap.get(otherId) || getStoredBandageCenter(otherId);
    if (!otherCenter) return;
    const dx = otherCenter.x - center.x;
    const dy = otherCenter.y - center.y;
    const distance = Math.max(Math.hypot(dx, dy), 1);
    const side = attachedAsSource
      ? getGfaEndpointSide(edge.sourceOrient, "source")
      : getGfaEndpointSide(edge.targetOrient, "target");
    const sign = side === "-" ? -1 : 1;
    vx += (dx / distance) * sign;
    vy += (dy / distance) * sign;
  });
  if (Math.hypot(vx, vy) > 0.08) {
    return Math.atan2(vy, vx);
  }
  return Math.PI * 2 * hashNumber(`${nodeId}:${index}`);
}

function getStoredBandageCenter(nodeId) {
  const state = bandageState.nodes.get(nodeId);
  if (!state) return null;
  if (Number.isFinite(state.x) && Number.isFinite(state.y)) {
    return { x: state.x, y: state.y };
  }
  if (state.minus && state.plus) {
    return { x: (state.minus.x + state.plus.x) / 2, y: (state.minus.y + state.plus.y) / 2 };
  }
  return null;
}

function getEndpointRef(nodeId, orient, role) {
  const node = getNodeData(nodeId);
  const state = bandageState.nodes.get(nodeId);
  if (!node || !state) return null;
  ensureEndpointState(node, state);
  const side = getGfaEndpointSide(orient, role);
  const pointIndex = state.points?.length ? (side === "-" ? 0 : state.points.length - 1) : null;
  return {
    key: `${nodeId}:${side}`,
    nodeId,
    side,
    pointIndex,
    point: pointIndex === null ? (side === "-" ? state.minus : state.plus) : state.points[pointIndex],
  };
}

function buildBandageAdjacency(visibleNodes, visibleEdges) {
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const adjacency = new Map(visibleNodes.map((node) => [node.id, []]));
  visibleEdges.forEach((edge) => {
    if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) return;
    adjacency.get(edge.source)?.push({
      otherId: edge.target,
      side: getGfaEndpointSide(edge.sourceOrient, "source"),
    });
    adjacency.get(edge.target)?.push({
      otherId: edge.source,
      side: getGfaEndpointSide(edge.targetOrient, "target"),
    });
  });
  return adjacency;
}

function relaxBandageAngles(visibleNodes, adjacency, amount) {
  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    const links = adjacency.get(node.id) || [];
    if (!state || !links.length) return;
    let vx = 0;
    let vy = 0;
    links.forEach((link) => {
      const other = bandageState.nodes.get(link.otherId);
      if (!other) return;
      const dx = other.x - state.x;
      const dy = other.y - state.y;
      const distance = Math.max(Math.hypot(dx, dy), 1);
      const sign = link.side === "-" ? -1 : 1;
      vx += (dx / distance) * sign;
      vy += (dy / distance) * sign;
    });
    if (Math.hypot(vx, vy) <= 0.06) return;
    state.angle = mixAngles(state.angle, Math.atan2(vy, vx), amount);
    syncBandageGlyphEndpoints(node, state);
  });
}

function mixAngles(current, target, amount) {
  const delta = Math.atan2(Math.sin(target - current), Math.cos(target - current));
  return current + delta * amount;
}

function addEndpointSpring(displacements, rotations, a, b, desiredDistance, strength, torqueStrength) {
  if (a.nodeId === b.nodeId) return;
  const dx = b.point.x - a.point.x;
  const dy = b.point.y - a.point.y;
  const distance = Math.max(Math.hypot(dx, dy), 0.001);
  const force = (distance - desiredDistance) * strength;
  const fx = (dx / distance) * force;
  const fy = (dy / distance) * force;
  addEndpointForce(displacements, rotations, a, fx, fy, torqueStrength);
  addEndpointForce(displacements, rotations, b, -fx, -fy, torqueStrength);
}

function addEndpointForce(displacements, rotations, endpoint, fx, fy, torqueStrength) {
  addCenterDisplacement(displacements, endpoint.nodeId, fx, fy);
  if (!torqueStrength || !rotations.has(endpoint.nodeId)) return;
  const state = bandageState.nodes.get(endpoint.nodeId);
  const node = getNodeData(endpoint.nodeId);
  if (!state || !node) return;
  const rx = endpoint.point.x - state.x;
  const ry = endpoint.point.y - state.y;
  const length = Math.max(getBandageGlyphLength(node), 1);
  const torque = ((rx * fy - ry * fx) / (length * length)) * torqueStrength;
  rotations.set(endpoint.nodeId, rotations.get(endpoint.nodeId) + torque);
}

function addCenterRepulsion(displacements, aId, a, bId, b, minDistance, strength) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  let distance = Math.hypot(dx, dy);
  let nx = dx;
  let ny = dy;
  if (distance < 0.001) {
    const angle = Math.PI * 2 * hashNumber(`${aId}:${bId}`);
    nx = Math.cos(angle);
    ny = Math.sin(angle);
    distance = 1;
  }
  if (distance >= minDistance) return;
  const force = (minDistance - distance) * strength;
  addCenterDisplacement(displacements, aId, (nx / distance) * force, (ny / distance) * force);
  addCenterDisplacement(displacements, bId, (-nx / distance) * force, (-ny / distance) * force);
}

function addRadialExpansion(displacements, visibleNodes, config) {
  if (!visibleNodes.length) return;
  const centers = visibleNodes
    .map((node) => bandageState.nodes.get(node.id))
    .filter((state) => state && Number.isFinite(state.x) && Number.isFinite(state.y));
  if (!centers.length) return;
  const centroid = {
    x: centers.reduce((sum, state) => sum + state.x, 0) / centers.length,
    y: centers.reduce((sum, state) => sum + state.y, 0) / centers.length,
  };
  const targetRadius = Math.max(
    config.radialExpansionMinRadius || 0,
    Math.sqrt(Math.max(visibleNodes.length, 1)) * (config.radialExpansionRadiusFactor || 100),
  );
  visibleNodes.forEach((node) => {
    const state = bandageState.nodes.get(node.id);
    if (!state) return;
    let dx = state.x - centroid.x;
    let dy = state.y - centroid.y;
    let distance = Math.hypot(dx, dy);
    if (distance < 0.001) {
      const angle = Math.PI * 2 * hashNumber(`${node.id}:radial`);
      dx = Math.cos(angle);
      dy = Math.sin(angle);
      distance = 1;
    }
    const slack = Math.max(targetRadius - distance, 0);
    if (slack <= 0) return;
    const force = Math.min(18, slack * config.radialExpansionStrength);
    addCenterDisplacement(displacements, node.id, (dx / distance) * force, (dy / distance) * force);
  });
}

function addCapsuleRepulsion(displacements, aNode, bNode, strength, padding) {
  const a = getGlyphGeometry(aNode.id);
  const b = getGlyphGeometry(bNode.id);
  if (!a || !b) return;
  const closest = closestGlyphVector(a, b, `${aNode.id}:${bNode.id}`);
  const minDistance = (a.width + b.width) / 2 + padding;
  if (closest.distance >= minDistance) return;
  const force = (minDistance - closest.distance) * strength;
  addCenterDisplacement(displacements, aNode.id, closest.x * force, closest.y * force);
  addCenterDisplacement(displacements, bNode.id, -closest.x * force, -closest.y * force);
}

function addLinkNodeRepulsion(displacements, linkGeometry, node, strength, padding) {
  const glyph = getGlyphGeometry(node.id);
  if (!glyph) return;
  const minDistance = glyph.width / 2 + padding;
  const samples = [0.18, 0.32, 0.5, 0.68, 0.82];
  let best = null;
  samples.forEach((t) => {
    const point = quadraticPoint(linkGeometry.source, linkGeometry.control, linkGeometry.target, t);
    const vector = pointToGlyphVector(point, glyph);
    if (!best || vector.distance < best.distance) {
      best = vector;
    }
  });
  if (!best || best.distance >= minDistance) return;
  const direction = best.distance < 0.001
    ? centerDirection(glyph.center, linkGeometry.label, `${node.id}:${linkGeometry.path}`, best.distance)
    : { x: best.x / best.distance, y: best.y / best.distance };
  const force = (minDistance - best.distance) * strength;
  addCenterDisplacement(displacements, node.id, -direction.x * force, -direction.y * force);
}

function closestGlyphVector(a, b, seed) {
  const aSegments = glyphSegments(a);
  const bSegments = glyphSegments(b);
  for (const aSegment of aSegments) {
    for (const bSegment of bSegments) {
      if (segmentsIntersect(aSegment.start, aSegment.end, bSegment.start, bSegment.end)) {
        return centerDirection(a.center, b.center, seed, 0);
      }
    }
  }
  let best = null;
  aSegments.forEach((aSegment) => {
    bSegments.forEach((bSegment) => {
      [
        pointToSegmentVector(aSegment.start, bSegment.start, bSegment.end),
        pointToSegmentVector(aSegment.end, bSegment.start, bSegment.end),
        invertVector(pointToSegmentVector(bSegment.start, aSegment.start, aSegment.end)),
        invertVector(pointToSegmentVector(bSegment.end, aSegment.start, aSegment.end)),
      ].forEach((candidate) => {
        if (!best || candidate.distance < best.distance) best = candidate;
      });
    });
  });
  if (!best) return centerDirection(a.center, b.center, seed, 0);
  if (best.distance < 0.001) {
    return centerDirection(a.center, b.center, seed, best.distance);
  }
  return {
    distance: best.distance,
    x: best.x / best.distance,
    y: best.y / best.distance,
  };
}

function glyphSegments(glyph) {
  const points = glyph.points?.length > 1 ? glyph.points : [glyph.start, glyph.end];
  const segments = [];
  for (let index = 1; index < points.length; index += 1) {
    segments.push({ start: points[index - 1], end: points[index] });
  }
  return segments.length ? segments : [{ start: glyph.start, end: glyph.end }];
}

function pointToGlyphVector(point, glyph) {
  let best = null;
  glyphSegments(glyph).forEach((segment) => {
    const vector = pointToSegmentVector(point, segment.start, segment.end);
    if (!best || vector.distance < best.distance) {
      best = vector;
    }
  });
  return best || pointToSegmentVector(point, glyph.start, glyph.end);
}

function pointToSegmentVector(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSq = dx * dx + dy * dy;
  const t = lengthSq <= 0 ? 0 : clamp(((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSq, 0, 1);
  const closest = { x: start.x + dx * t, y: start.y + dy * t };
  const vx = point.x - closest.x;
  const vy = point.y - closest.y;
  return { distance: Math.hypot(vx, vy), x: vx, y: vy };
}

function invertVector(vector) {
  return { distance: vector.distance, x: -vector.x, y: -vector.y };
}

function centerDirection(a, b, seed, distance) {
  let dx = a.x - b.x;
  let dy = a.y - b.y;
  let length = Math.hypot(dx, dy);
  if (length < 0.001) {
    const angle = Math.PI * 2 * hashNumber(seed);
    dx = Math.cos(angle);
    dy = Math.sin(angle);
    length = 1;
  }
  return { distance, x: dx / length, y: dy / length };
}

function segmentsIntersect(a, b, c, d) {
  const ab1 = orientation(a, b, c);
  const ab2 = orientation(a, b, d);
  const cd1 = orientation(c, d, a);
  const cd2 = orientation(c, d, b);
  return ab1 * ab2 < 0 && cd1 * cd2 < 0;
}

function orientation(a, b, c) {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

function addCenterDisplacement(displacements, nodeId, dx, dy) {
  const current = displacements.get(nodeId);
  if (!current) return;
  current.x += dx;
  current.y += dy;
}

function getLinkGeometry(edge) {
  const source = getGlyphEndpoint(edge.source, edge.sourceOrient, "source");
  const target = getGlyphEndpoint(edge.target, edge.targetOrient, "target");
  if (!source || !target) return null;
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.max(Math.hypot(dx, dy), 1);
  const normal = { x: -dy / distance, y: dx / distance };
  const bendSeed = hashNumber(`${edge.id}:bend`);
  const config = getBandageModeConfig();
  const bend =
    Math.min(
      config.linkBendMax,
      Math.max(config.linkBendMin, distance * config.linkBendDistanceFactor + bendSeed * config.linkBendSeedFactor),
    ) *
    (hashNumber(`${edge.id}:side`) > 0.5 ? 1 : -1);
  const control = {
    x: (source.x + target.x) / 2 + normal.x * bend,
    y: (source.y + target.y) / 2 + normal.y * bend,
  };
  const nearTarget = quadraticPoint(source, control, target, 0.9);
  const angle = Math.atan2(target.y - nearTarget.y, target.x - nearTarget.x);
  const arrowSize = Math.max(7, Math.min(16, 7 + displayEdgeWidth(edge)));
  return {
    source,
    target,
    control,
    path: quadraticPath(source, control, target),
    label: quadraticPoint(source, control, target, 0.5),
    arrow: [
      target,
      {
        x: target.x - Math.cos(angle - 0.45) * arrowSize,
        y: target.y - Math.sin(angle - 0.45) * arrowSize,
      },
      {
        x: target.x - Math.cos(angle + 0.45) * arrowSize,
        y: target.y - Math.sin(angle + 0.45) * arrowSize,
      },
    ],
  };
}

function appendBandageEndpoint(group, point, label) {
  group.appendChild(svgEl("circle", {
    class: "bandage-endpoint",
    cx: point.x,
    cy: point.y,
    r: 3.9,
  }));
  if (bandageState.transform.scale > 0.55) {
    group.appendChild(svgEl("text", {
      class: "bandage-endpoint-label",
      x: point.x,
      y: point.y + 0.2,
    }, label));
  }
}

function appendBandageNodeLabel(group, node, geometry) {
  const label = buildNodeLabel(node);
  if (!label || bandageState.transform.scale < 0.24) return;
  const center = geometry.label || quadraticPoint(geometry.start, geometry.control, geometry.end, 0.5);
  label.split("\n").forEach((line, index) => {
    group.appendChild(svgEl("text", {
      class: `bandage-node-label${dom.textOutline.checked ? " bandage-label-outline" : ""}`,
      x: center.x,
      y: center.y + geometry.width * 0.88 + index * 11,
    }, line));
  });
}

function svgEl(tag, attrs = {}, text = null) {
  const element = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value != null) {
      element.setAttribute(key, String(value));
    }
  });
  if (text != null) {
    element.textContent = text;
  }
  return element;
}

function quadraticPath(start, control, end) {
  return `M ${round(start.x)} ${round(start.y)} Q ${round(control.x)} ${round(control.y)} ${round(end.x)} ${round(end.y)}`;
}

function polylinePath(points) {
  if (!points.length) return "";
  const roundedPoints = [];
  points.forEach((point) => {
    const roundedPoint = { x: round(point.x), y: round(point.y) };
    const previous = roundedPoints[roundedPoints.length - 1];
    if (!previous || previous.x !== roundedPoint.x || previous.y !== roundedPoint.y) {
      roundedPoints.push(roundedPoint);
    }
  });
  return roundedPoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${round(point.x)} ${round(point.y)}`)
    .join(" ");
}

function getBandageEventTarget(target) {
  const element = target?.closest?.("[data-bandage-kind]");
  if (!element || !dom.bandageSvg.contains(element)) return null;
  return {
    kind: element.dataset.bandageKind,
    id: element.dataset.bandageId,
  };
}

function syncCytoscapeSelectionFromBandage(selection, additive = false, selectedNow = true) {
  if (!isTwinMode() || !cy || !selection) return;
  const element = cy.getElementById(selection.id);
  if (!additive) {
    cy.elements().unselect();
  }
  if (element.length && selectedNow) {
    element.select();
  } else if (element.length) {
    element.unselect();
  }
}

function syncBandageSelectionFromCytoscape() {
  if (!cy) return;
  clearBandageSelection();
  const selected = cy.$(":selected");
  selected.nodes().forEach((node) => bandageState.selectedNodeIds.add(node.id()));
  selected.edges().forEach((edge) => bandageState.selectedEdgeIds.add(edge.id()));
  if (selected[0]) {
    bandageState.selected = {
      kind: selected[0].isNode() ? "node" : "edge",
      id: selected[0].id(),
    };
  }
}

function setSingleBandageSelection(item) {
  clearBandageSelection();
  if (!item) return;
  updateBandageSelection(item, false);
}

function updateBandageSelection(item, additive = false) {
  if (!item) {
    clearBandageSelection();
    return;
  }
  if (!additive) {
    clearBandageSelection();
  }
  const selectedIds = item.kind === "node" ? bandageState.selectedNodeIds : bandageState.selectedEdgeIds;
  if (additive && selectedIds.has(item.id)) {
    selectedIds.delete(item.id);
    if (bandageState.selected?.kind === item.kind && bandageState.selected.id === item.id) {
      bandageState.selected = firstBandageSelection();
    }
    return;
  }
  selectedIds.add(item.id);
  bandageState.selected = item;
}

function clearBandageSelection() {
  bandageState.selected = null;
  bandageState.selectedNodeIds.clear();
  bandageState.selectedEdgeIds.clear();
}

function firstBandageSelection() {
  const nodeId = bandageState.selectedNodeIds.values().next().value;
  if (nodeId) return { kind: "node", id: nodeId };
  const edgeId = bandageState.selectedEdgeIds.values().next().value;
  if (edgeId) return { kind: "edge", id: edgeId };
  return null;
}

function isBandageItemSelected(kind, id) {
  const selectedIds = kind === "node" ? bandageState.selectedNodeIds : bandageState.selectedEdgeIds;
  if (selectedIds.size) return selectedIds.has(id);
  return bandageState.selected?.kind === kind && bandageState.selected.id === id;
}

function pruneBandageSelectionToVisible() {
  [...bandageState.selectedNodeIds].forEach((nodeId) => {
    if (!bandageState.visibleNodeIds.has(nodeId)) {
      bandageState.selectedNodeIds.delete(nodeId);
    }
  });
  [...bandageState.selectedEdgeIds].forEach((edgeId) => {
    if (!bandageState.visibleEdgeIds.has(edgeId)) {
      bandageState.selectedEdgeIds.delete(edgeId);
    }
  });
  if (bandageState.selected && !isBandageSelectionVisible(bandageState.selected)) {
    bandageState.selected = firstBandageSelection();
  }
  if (!bandageState.selectedNodeIds.size && !bandageState.selectedEdgeIds.size) {
    bandageState.selected = null;
  }
}

function quadraticPoint(start, control, end, t) {
  const mt = 1 - t;
  return {
    x: mt * mt * start.x + 2 * mt * t * control.x + t * t * end.x,
    y: mt * mt * start.y + 2 * mt * t * control.y + t * t * end.y,
  };
}

function midpoint(a, b) {
  return {
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
  };
}

function getNativePolylinePointCount(targetLength, config) {
  const segmentCount = Math.max(
    config.glyphSegmentMin || 1,
    Math.min(
      config.glyphSegmentMax || 24,
      Math.ceil(Math.max(targetLength, 1) / Math.max(config.glyphSegmentLength || 56, 12)),
    ),
  );
  return segmentCount + 1;
}

function createNativePolylinePoints(start, end, bend, seed, config, targetLength, pointCount = null) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const chord = Math.max(Math.hypot(dx, dy), 1);
  const direction = { x: dx / chord, y: dy / chord };
  const normal = { x: -direction.y, y: direction.x };
  const segmentCount = Math.max(1, (pointCount || getNativePolylinePointCount(targetLength || chord, config)) - 1);
  const desiredSegment = Math.max((targetLength || chord) / segmentCount, 1);
  const chordStep = chord / segmentCount;
  const targetAngle = ((config.targetTurnAngleDeg || 150) * Math.PI) / 180;
  const targetOffset = chordStep / Math.max(Math.tan(targetAngle / 2), 0.001);
  const foldedAmplitude = Math.sqrt(Math.max(desiredSegment * desiredSegment - chordStep * chordStep, 0)) * 0.18;
  const kinkDirection = hashNumber(`${seed}:kink-side`) > 0.5 ? 1 : -1;
  const kinkAmplitude = Math.max(
    config.polylineKinkMin || 0,
    Math.min(
      config.polylineKinkMax || 0,
      Math.max(
        targetOffset,
        Math.min((targetLength || chord) * (config.polylineKinkScale || 0), foldedAmplitude * (config.nativeFoldAmplitudeFactor || 0)),
      ),
    ),
  );
  const phase = hashNumber(`${seed}:kink-phase`) > 0.5 ? 1 : 0;
  const points = [];
  for (let index = 0; index <= segmentCount; index += 1) {
    const t = index / segmentCount;
    const envelope = Math.sin(Math.PI * t);
    const arcOffset = bend * 0.16 * envelope;
    const nativeArc = index === 0 || index === segmentCount ? 0 : kinkDirection * kinkAmplitude * envelope;
    const smallFacet = Math.sin(Math.PI * 2 * t + phase * Math.PI) * kinkAmplitude * 0.04 * envelope;
    const offset = arcOffset + nativeArc + smallFacet;
    points.push({
      x: start.x + direction.x * chord * t + normal.x * offset,
      y: start.y + direction.y * chord * t + normal.y * offset,
    });
  }
  return points;
}

function sampleNativePolyline(start, end, normal, bend, seed, config, targetLength = null) {
  return createNativePolylinePoints(start, end, bend, seed, config, targetLength || Math.hypot(end.x - start.x, end.y - start.y));
}

function splitLongPolylineSegments(points, maxSegmentLength) {
  if (points.length < 2) return points;
  const limited = [points[0]];
  for (let index = 1; index < points.length; index += 1) {
    const start = limited[limited.length - 1];
    const end = points[index];
    const distance = Math.hypot(end.x - start.x, end.y - start.y);
    const splits = Math.max(1, Math.ceil(distance / Math.max(maxSegmentLength, 12)));
    for (let step = 1; step <= splits; step += 1) {
      const t = step / splits;
      limited.push({
        x: start.x + (end.x - start.x) * t,
        y: start.y + (end.y - start.y) * t,
      });
    }
  }
  return limited;
}

function pointAtPolylineRatio(points, ratio) {
  if (!points.length) return null;
  if (points.length === 1) return points[0];
  const lengths = [];
  let total = 0;
  for (let index = 1; index < points.length; index += 1) {
    total += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y);
    lengths.push(total);
  }
  const target = total * clamp(ratio, 0, 1);
  const segmentIndex = lengths.findIndex((length) => length >= target);
  if (segmentIndex < 0) return points[points.length - 1];
  const startDistance = segmentIndex === 0 ? 0 : lengths[segmentIndex - 1];
  const endDistance = lengths[segmentIndex];
  const span = Math.max(endDistance - startDistance, 0.001);
  const t = (target - startDistance) / span;
  const start = points[segmentIndex];
  const end = points[segmentIndex + 1];
  return {
    x: start.x + (end.x - start.x) * t,
    y: start.y + (end.y - start.y) * t,
  };
}

function subPolylineByRatio(points, startRatio, endRatio) {
  if (!points.length) return [];
  if (points.length === 1) return [points[0]];
  const start = clamp(Math.min(startRatio, endRatio), 0, 1);
  const end = clamp(Math.max(startRatio, endRatio), 0, 1);
  if (end <= start) return [];
  const cumulative = [0];
  let total = 0;
  for (let index = 1; index < points.length; index += 1) {
    total += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y);
    cumulative.push(total);
  }
  if (total <= 0) return [];
  const startDistance = start * total;
  const endDistance = end * total;
  const result = [pointAtPolylineRatio(points, start)];
  for (let index = 1; index < points.length - 1; index += 1) {
    const distance = cumulative[index];
    if (distance > startDistance && distance < endDistance) {
      result.push(points[index]);
    }
  }
  result.push(pointAtPolylineRatio(points, end));
  return result;
}

function screenPointToWorld(x, y) {
  return {
    x: (x - bandageState.transform.x) / bandageState.transform.scale,
    y: (y - bandageState.transform.y) / bandageState.transform.scale,
  };
}

function fitBandageToView() {
  if (!graphState || !bandageState.visibleNodeIds.size) return;
  const boxes = [];
  getClientNodes().forEach((node) => {
    if (!bandageState.visibleNodeIds.has(node.id)) return;
    const geometry = getGlyphGeometry(node.id);
    if (!geometry) return;
    if (geometry.points?.length > 2) {
      boxes.push(...geometry.points);
    } else {
      boxes.push(geometry.start, geometry.end, geometry.control);
    }
  });
  if (!boxes.length) return;
  const minX = Math.min(...boxes.map((point) => point.x));
  const maxX = Math.max(...boxes.map((point) => point.x));
  const minY = Math.min(...boxes.map((point) => point.y));
  const maxY = Math.max(...boxes.map((point) => point.y));
  const rect = dom.bandageSvg.getBoundingClientRect();
  const padding = 70;
  const width = Math.max(maxX - minX, 1);
  const height = Math.max(maxY - minY, 1);
  const scale = Math.max(0.08, Math.min(3.2, Math.min((rect.width - padding) / width, (rect.height - padding) / height)));
  bandageState.transform.scale = scale;
  bandageState.transform.x = rect.width / 2 - ((minX + maxX) / 2) * scale;
  bandageState.transform.y = rect.height / 2 - ((minY + maxY) / 2) * scale;
  renderBandageSvg();
  updateZoomDisplay();
}

function renderBandageSelection() {
  const selected = bandageState.selected;
  updateSelectionButtons(selected);
  if (!selected) {
    resetDetails();
    return;
  }
  if (selected.kind === "node") {
    const node = getNodeData(selected.id);
    if (node) renderNodeDetails(enrichNodeData(node, graphState.stats));
  } else {
    const edge = getEdgeData(selected.id);
    if (edge) renderEdgeDetails(enrichEdgeData(edge));
  }
  renderBandageSvg();
}

function findBandageNodes() {
  const query = dom.nodeSearch.value.trim().toLowerCase();
  if (!query) {
    showToast("Enter a node name");
    return;
  }
  const matches = getClientNodes().filter((node) => nodeMatches(node, query));
  if (!matches.length) {
    showToast("No matching nodes");
    return;
  }
  bandageState.visibleNodeIds = new Set(matches.map((node) => node.id));
  bandageState.visibleEdgeIds = new Set(
    getClientEdges()
      .filter((edge) => bandageState.visibleNodeIds.has(edge.source) && bandageState.visibleNodeIds.has(edge.target))
      .map((edge) => edge.id),
  );
  setSingleBandageSelection({ kind: "node", id: matches[0].id });
  fitBandageToView();
  renderBandageSelection();
  updateVisibleCount();
  showToast(`Found ${matches.length} node(s)`);
}

function drawBandageGraphManually() {
  if (!graphState) return;
  const scope = dom.drawScope.value;
  if (scope === "selection") {
    const selected = bandageState.selected;
    if (!selected || selected.kind !== "node") {
      showToast("Select a node first");
      return;
    }
    const ids = new Set([selected.id]);
    const edgeIds = new Set();
    getClientEdges().forEach((edge) => {
      if (edge.source === selected.id || edge.target === selected.id) {
        ids.add(edge.source);
        ids.add(edge.target);
        edgeIds.add(edge.id);
      }
    });
    bandageState.visibleNodeIds = ids;
    bandageState.visibleEdgeIds = edgeIds;
  } else if (scope === "visible") {
    updateBandageVisibilityFromFilters();
  } else {
    bandageState.visibleNodeIds = new Set(getClientNodes().map((node) => node.id));
    bandageState.visibleEdgeIds = new Set(getClientEdges().map((edge) => edge.id));
  }
  layoutBandageGraph({ reset: true });
  fitBandageToView();
  renderBandageSelection();
  updateVisibleCount();
  setStatus("Draw graph complete");
}

function hashNumber(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) % 10000) / 10000;
}

function deterministicBend(value) {
  return seededSignedValue(value);
}

function seededSignedValue(value) {
  return (hashNumber(value) - 0.5) * 2;
}

function resetDetails() {
  dom.selectionKind.textContent = "none";
  dom.selectionDetails.innerHTML = "";
  dom.selectionDetails.appendChild(emptyDetails("No selection"));
}

function renderNodeDetails(data) {
  dom.selectionKind.textContent = "contig";
  const rows = [
    ["ID", data.id],
    ["Label", data.customLabel || "-"],
    ["Length", number(data.length)],
    ["Depth", number(data.depth)],
    ["Degree", number(data.degree)],
    ["Alignment hits", number(data.blastHitCount)],
    ["Tags", formatTags(data.tags)],
  ];
  dom.selectionDetails.replaceChildren(...rows.map(([key, value]) => detailRow(key, value)));
  dom.selectionDetails.appendChild(nodeEditForm(data));
  if (data.blastBest) {
    const title = document.createElement("h2");
    title.textContent = "Best Alignment";
    title.style.marginTop = "12px";
    const hit = hitCard(data.blastBest);
    dom.selectionDetails.append(title, hit);
  }
}

function renderEdgeDetails(data) {
  dom.selectionKind.textContent = "link";
  const rows = [
    ["ID", data.id],
    ["Label", data.customLabel || data.label || "-"],
    ["Source", `${data.source} ${data.sourceOrient}`],
    ["Target", `${data.target} ${data.targetOrient}`],
    ["CIGAR", data.cigar],
    ["Support", number(data.support)],
    ["Read paths", number(data.blastHitCount)],
    ["Tags", formatTags(data.tags)],
  ];
  dom.selectionDetails.replaceChildren(...rows.map(([key, value]) => detailRow(key, value)));
  dom.selectionDetails.appendChild(edgeEditForm(data));
  if (data.blastBest) {
    const title = document.createElement("h2");
    title.textContent = "Best Path";
    title.style.marginTop = "12px";
    const hit = hitCard(data.blastBest);
    dom.selectionDetails.append(title, hit);
  }
}

function nodeEditForm(data) {
  const form = document.createElement("form");
  form.className = "edit-form";
  form.appendChild(editTitle("Edit contig"));
  const grid = document.createElement("div");
  grid.className = "edit-grid";
  const nameInput = appendField(grid, "Name", "text", data.id);
  const labelInput = appendField(grid, "Label", "text", data.customLabel || "");
  const colorInput = appendField(grid, "Colour", "color", data.customColor || rgbToHex(data.renderColor));
  const depthInput = appendField(grid, "Depth", "number", data.depth ?? "");
  depthInput.step = "0.01";
  depthInput.min = "0";
  form.appendChild(grid);
  form.appendChild(formNote("Name rewrites the GFA S record and updates related L records. Colour/Label are saved as CL:Z and LB:Z tags."));
  form.appendChild(saveButton("Save contig"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const newId = nameInput.value.trim();
    if (newId && newId !== data.id) {
      pendingRename = { oldId: data.id, newId };
    }
    await postJsonAction(
      "/api/update_node",
      {
        node_id: data.id,
        name: newId,
        label: labelInput.value.trim(),
        color: colorInput.value,
        depth: parseNullableNumber(depthInput.value),
      },
      "Contig saved",
    );
  });
  return form;
}

function edgeEditForm(data) {
  const form = document.createElement("form");
  form.className = "edit-form";
  form.appendChild(editTitle("Edit link"));
  const grid = document.createElement("div");
  grid.className = "edit-grid";
  const labelInput = appendField(grid, "Label", "text", data.customLabel || "");
  const colorInput = appendField(grid, "Colour", "color", data.customColor || rgbToHex(data.renderColor));
  const supportInput = appendField(grid, "Support RC", "number", data.support ?? "");
  supportInput.step = "0.01";
  supportInput.min = "0";
  const cigarInput = appendField(grid, "CIGAR", "text", data.cigar || "0M");
  form.appendChild(grid);
  form.appendChild(formNote("Links do not have independent GFA names. Label/Colour are saved as LB:Z and CL:Z tags on the L record."));
  form.appendChild(saveButton("Save link"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await postJsonAction(
      "/api/update_edge",
      {
        edge_id: data.id,
        label: labelInput.value.trim(),
        color: colorInput.value,
        support: parseNullableNumber(supportInput.value),
        cigar: cigarInput.value.trim(),
      },
      "Link saved",
    );
  });
  return form;
}

function editTitle(text) {
  const title = document.createElement("h3");
  title.textContent = text;
  return title;
}

function appendField(container, labelText, type, value, className = "") {
  const label = document.createElement("label");
  label.className = `field ${className}`.trim();
  const span = document.createElement("span");
  span.textContent = labelText;
  const input = document.createElement("input");
  input.type = type;
  input.value = value == null ? "" : String(value);
  label.append(span, input);
  container.appendChild(label);
  return input;
}

function formNote(text) {
  const note = document.createElement("div");
  note.className = "form-note";
  note.textContent = text;
  return note;
}

function saveButton(text) {
  const button = document.createElement("button");
  button.className = "primary-button full";
  button.type = "submit";
  const span = document.createElement("span");
  span.textContent = text;
  button.appendChild(span);
  return button;
}

function parseNullableNumber(value) {
  if (value == null || String(value).trim() === "") return undefined;
  return Number(value);
}

function rgbToHex(value) {
  if (!value) return "#2f7d76";
  if (value.startsWith("#")) return value;
  const match = value.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (!match) return "#2f7d76";
  return (
    "#" +
    match
      .slice(1)
      .map((part) => Number(part).toString(16).padStart(2, "0"))
      .join("")
  );
}

function detailRow(key, value) {
  const row = document.createElement("div");
  row.className = "detail-row";
  const label = document.createElement("span");
  label.textContent = key;
  const body = document.createElement("span");
  body.textContent = value == null || value === "" ? "-" : String(value);
  row.append(label, body);
  return row;
}

function hitCard(hit) {
  const item = document.createElement("div");
  item.className = "hit";
  const title = document.createElement("strong");
  title.textContent = hit.qseqid && hit.sseqid ? `${hit.qseqid} -> ${hit.sseqid}` : hit.sseqid || hit.qseqid || "alignment";
  const meta = document.createElement("span");
  const score = hit.bitscore != null ? `, bitscore ${number(hit.bitscore)}` : hit.mapq != null ? `, MAPQ ${number(hit.mapq)}` : "";
  meta.textContent = `${number(hit.pident)}% identity, ${number(hit.length)} bp${score}`;
  item.append(title, meta);
  return item;
}

function emptyDetails(text) {
  const div = document.createElement("div");
  div.className = "detail-row";
  const label = document.createElement("span");
  label.textContent = "State";
  const body = document.createElement("span");
  body.textContent = text;
  div.append(label, body);
  return div;
}

function renderStats(stats) {
  const rows = stats
    ? [
        ["Nodes", stats.node_count],
        ["Links", stats.edge_count],
        ["Total bp", stats.total_bp],
        ["Median depth", stats.median_depth],
      ]
    : [
        ["Nodes", 0],
        ["Links", 0],
        ["Total bp", 0],
        ["Median depth", "-"],
      ];
  dom.statsGrid.replaceChildren(
    ...rows.map(([label, value]) => {
      const item = document.createElement("div");
      item.className = "stat";
      const numberEl = document.createElement("b");
      numberEl.textContent = number(value);
      const labelEl = document.createElement("span");
      labelEl.textContent = label;
      item.append(numberEl, labelEl);
      return item;
    }),
  );
}

function renderHistogram(histogram) {
  if (!window.d3) return;
  const svg = d3.select(dom.depthHistogram);
  svg.selectAll("*").remove();
  const width = dom.depthHistogram.clientWidth || 260;
  const height = dom.depthHistogram.clientHeight || 76;
  const margin = { top: 6, right: 6, bottom: 18, left: 26 };
  svg.attr("viewBox", `0 0 ${width} ${height}`);

  if (!histogram.length) {
    svg
      .append("text")
      .attr("x", width / 2)
      .attr("y", height / 2)
      .attr("text-anchor", "middle")
      .attr("fill", "#8c9488")
      .attr("font-size", 11)
      .text("No depth");
    return;
  }

  const x = d3
    .scaleLinear()
    .domain([d3.min(histogram, (d) => d.x0), d3.max(histogram, (d) => d.x1)])
    .nice()
    .range([margin.left, width - margin.right]);
  const y = d3
    .scaleLinear()
    .domain([0, d3.max(histogram, (d) => d.count)])
    .nice()
    .range([height - margin.bottom, margin.top]);

  svg
    .append("g")
    .selectAll("rect")
    .data(histogram)
    .join("rect")
    .attr("x", (d) => x(d.x0) + 1)
    .attr("y", (d) => y(d.count))
    .attr("width", (d) => Math.max(1, x(d.x1) - x(d.x0) - 2))
    .attr("height", (d) => y(0) - y(d.count))
    .attr("rx", 2)
    .attr("fill", "#2f7d76");

  svg
    .append("g")
    .attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(4))
    .call((g) => g.select(".domain").attr("stroke", "#cfd7c8"))
    .call((g) => g.selectAll("line").attr("stroke", "#cfd7c8"))
    .call((g) => g.selectAll("text").attr("fill", "#667064").attr("font-size", 10));

  svg
    .append("g")
    .attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(3))
    .call((g) => g.select(".domain").attr("stroke", "#cfd7c8"))
    .call((g) => g.selectAll("line").attr("stroke", "#cfd7c8"))
    .call((g) => g.selectAll("text").attr("fill", "#667064").attr("font-size", 10));
}

function renderHistory(session) {
  const traceItems = session.history_trace || [];
  const activeTraceIndex = session.history_trace_index;
  const activeStepCount = Number(session.edit_step_count || 0);
  const activeOperationStateIndex = Number.isInteger(session.operation_state_index)
    ? session.operation_state_index
    : null;
  const items = traceItems.length
    ? traceItems.map((item, index) => ({ ...item, displayIndex: index })).reverse()
    : (session.history || []).map((item, index) => ({ ...item, displayIndex: index })).reverse().slice(0, 12);
  if (dom.clearHistoryButton) {
    dom.clearHistoryButton.disabled = !items.length;
  }
  if (!items.length) {
    dom.historyList.replaceChildren(emptyText("No operations"));
    return;
  }
  dom.historyList.replaceChildren(
    ...items.map((item) => {
      const canRestore = Number.isInteger(item.trace_index);
      const canRestoreOperation = !canRestore && Number.isInteger(item.state_index);
      const editStepCount = item.details?.edit_step_count;
      const stepNumber = item.displayIndex + 1;
      const traceStepNumber = Number.isInteger(item.details?.step) ? item.details.step : item.trace_index;
      const isFuture = !canRestore && Number.isInteger(editStepCount) && editStepCount > activeStepCount;
      const row = document.createElement("div");
      row.className = "history-item";
      row.classList.toggle("future", isFuture);
      row.classList.toggle(
        "active",
        canRestore
          ? item.trace_index === activeTraceIndex
          : canRestoreOperation
            ? item.state_index === activeOperationStateIndex
            : Number.isInteger(editStepCount) && editStepCount === activeStepCount && activeStepCount > 0,
      );
      row.addEventListener("click", () => row.classList.toggle("expanded"));

      const header = document.createElement("div");
      header.className = "history-item-header";
      if (canRestore) {
        row.classList.add("history-step-button");
        header.addEventListener("click", (event) => {
          event.stopPropagation();
          restoreHistoryTraceStep(item.trace_index);
        });
      }

      if (canRestoreOperation) {
        const nav = document.createElement("div");
        nav.className = "history-nav";
        const before = document.createElement("button");
        before.type = "button";
        before.textContent = "before";
        before.disabled = item.state_index <= 0;
        before.addEventListener("click", (event) => {
          event.stopPropagation();
          restoreOperationState(Math.max(0, item.state_index - 1), `Moved before ${item.action}`);
        });
        const after = document.createElement("button");
        after.type = "button";
        after.textContent = "after";
        after.addEventListener("click", (event) => {
          event.stopPropagation();
          restoreOperationState(item.state_index, `Moved after ${item.action}`);
        });
        nav.append(before, after);
        header.appendChild(nav);
      } else if (!canRestore && Number.isInteger(editStepCount) && editStepCount > 0) {
        const nav = document.createElement("div");
        nav.className = "history-nav";
        const before = document.createElement("button");
        before.type = "button";
        before.textContent = "before";
        before.disabled = editStepCount <= 0;
        before.addEventListener("click", (event) => {
          event.stopPropagation();
          jumpToEditStep(Math.max(0, editStepCount - 1), `Moved before step ${editStepCount}`);
        });
        const after = document.createElement("button");
        after.type = "button";
        after.textContent = "after";
        after.addEventListener("click", (event) => {
          event.stopPropagation();
          jumpToEditStep(editStepCount, `Moved after step ${editStepCount}`);
        });
        nav.append(before, after);
        header.appendChild(nav);
      }

      const action = document.createElement("strong");
      action.textContent = canRestore ? `${traceStepNumber}. ${item.action}` : `${stepNumber}. ${item.action}`;
      header.appendChild(action);

      const details = document.createElement("span");
      details.className = "history-detail";
      details.textContent = formatHistoryDetails(item.details || {});
      details.title = details.textContent;
      row.append(header, details);
      return row;
    }),
  );
}

function formatHistoryDetails(details) {
  return Object.entries(details)
    .map(([key, value]) => `${key}: ${formatHistoryValue(value)}`)
    .join(" · ");
}

function formatHistoryValue(value) {
  if (Array.isArray(value)) {
    const preview = value.slice(0, 4).map((item) => formatHistoryValue(item)).join(", ");
    return value.length > 4 ? `[${preview}, ...]` : `[${preview}]`;
  }
  if (value && typeof value === "object") {
    const text = JSON.stringify(value);
    return text.length > 90 ? `${text.slice(0, 87)}...` : text;
  }
  return String(value);
}

function emptyText(text) {
  const item = document.createElement("span");
  item.textContent = text;
  return item;
}

function formatTags(tags) {
  if (!tags || Object.keys(tags).length === 0) return "-";
  return Object.entries(tags)
    .slice(0, 10)
    .map(([key, value]) => `${key}:${value}`)
    .join(", ");
}

function number(value) {
  if (value == null || value === "") return "-";
  if (typeof value === "string") return value;
  if (!Number.isFinite(Number(value))) return String(value);
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function round(value) {
  return Math.round(value * 100) / 100;
}

function interpolateColor(a, b, ratio) {
  const t = Math.max(0, Math.min(1, ratio));
  const rgb = a.map((start, index) => Math.round(start + (b[index] - start) * t));
  return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}

function setStatus(text) {
  dom.statusText.textContent = text;
}

function showToast(text) {
  dom.toast.textContent = text;
  dom.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    dom.toast.hidden = true;
  }, 2600);
}

function toCamel(id) {
  return id.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}
