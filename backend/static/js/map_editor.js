/**
 * Map Editor - Cytoscape.js based graph editor
 * Requires: cytoscape.js, mapEditorData (global) with nodesData, edgesData
 */

document.addEventListener("DOMContentLoaded", function () {
  // Get data from global variable set by Django template
  const nodesData = window.mapEditorData?.nodesData || [];
  const edgesData = window.mapEditorData?.edgesData || [];

  // Scale factor for positioning (maps use small coordinates, cytoscape needs pixels)
  const SCALE = 100;

  // Track changes
  let hasChanges = false;
  let selectedElement = null;
  let edgeMode = false;
  let edgeSourceNode = null;

  // Get max IDs for new elements
  const nodeIds = nodesData.map((n) => parseInt(n.data.id) || 0);
  const edgeIds = edgesData.map((e) => parseInt(e.data.id) || 0);
  let nextNodeId = Math.max(0, ...nodeIds) + 1;
  let nextEdgeId = Math.max(0, ...edgeIds) + 1;

  // Node type lookup (from DOM checkboxes)
  const nodeTypesLookup = {};
  document.querySelectorAll(".nodeTypeCheckbox").forEach((cb) => {
    nodeTypesLookup[cb.value] = {
      id: parseInt(cb.value),
      name: cb.dataset.name,
    };
  });

  // Helper: Get node color based on type IDs
  function getNodeColorByTypeIds(typeIds) {
    const types = (typeIds || []).map((id) => nodeTypesLookup[id]?.name || "");
    if (types.includes("home")) return "#10b981";
    if (types.includes("workplace")) return "#3b82f6";
    if (types.includes("station")) return "#f59e0b";
    if (types.includes("bus_stop")) return "#ef4444";
    return "#6b7280";
  }

  // Helper: Get edge color and style based on edgeType
  function getEdgeStyleByType(edgeType, biking, walking) {
    if (edgeType === "train") {
      return { color: "#ef4444", style: "dashed" };
    }
    if (edgeType === "both") {
      return { color: "#f97316", style: "solid" };
    }
    if (edgeType === "street") {
      return { color: "#6b7280", style: "solid" };
    }
    // Plain path
    if (biking && walking) {
      return { color: "#8b5cf6", style: "solid" };
    }
    if (biking) {
      return { color: "#3b82f6", style: "solid" };
    }
    if (walking) {
      return { color: "#10b981", style: "solid" };
    }
    return { color: "#9ca3af", style: "solid" };
  }

  // Convert data to Cytoscape format with proper IDs and scaling
  const cyNodes = nodesData.map((node) => {
    return {
      data: {
        id: "n" + node.data.id,
        label: node.data.name || "Node " + node.data.id,
        originalId: node.data.id,
        name: node.data.name,
        nodeTypes: node.data.nodeTypes || [],
      },
      position: {
        x: (node.position?.x || 0) * SCALE,
        y: (node.position?.y || 0) * SCALE,
      },
    };
  });

  const cyEdges = edgesData.map((edge) => {
    const edgeType = edge.data.edgeType || "path";
    const style = getEdgeStyleByType(
      edgeType,
      edge.data.biking,
      edge.data.walking
    );
    return {
      data: {
        id: "e" + edge.data.id,
        source: "n" + edge.data.source,
        target: "n" + edge.data.target,
        label: edge.data.name || "",
        originalId: edge.data.id,
        name: edge.data.name,
        biking: edge.data.biking,
        walking: edge.data.walking,
        maxLanes: edge.data.maxLanes || 2,
        edgeType: edgeType,
        speedLimit: edge.data.speedLimit,
        lanes: edge.data.lanes,
        dedicatedBusLane: edge.data.dedicatedBusLane,
        edgeColor: style.color,
        edgeStyle: style.style,
      },
    };
  });

  console.log(
    "Initializing Cytoscape with",
    cyNodes.length,
    "nodes and",
    cyEdges.length,
    "edges"
  );

  // Initialize Cytoscape
  const cy = cytoscape({
    container: document.getElementById("cy"),
    elements: [...cyNodes, ...cyEdges],
    style: [
      {
        selector: "node",
        style: {
          "background-color": function (ele) {
            return getNodeColorByTypeIds(ele.data("nodeTypes"));
          },
          label: "data(label)",
          "text-valign": "bottom",
          "text-halign": "center",
          "font-size": "10px",
          "text-margin-y": "5px",
          color: "#374151",
          width: "20px",
          height: "20px",
          "border-width": "0px",
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-width": "3px",
          "border-color": "#3b82f6",
          width: "26px",
          height: "26px",
        },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "data(edgeColor)",
          "line-style": "data(edgeStyle)",
          "curve-style": "bezier",
          "target-arrow-shape": "triangle",
          "target-arrow-color": "data(edgeColor)",
          "arrow-scale": 0.8,
          opacity: 0.7,
        },
      },
      {
        selector: "edge:selected",
        style: {
          width: 4,
          opacity: 1,
        },
      },
      {
        selector: ".edge-source",
        style: {
          "border-width": "3px",
          "border-color": "#3b82f6",
          "border-style": "dashed",
        },
      },
    ],
    layout: { name: "preset" },
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
  });

  // Fit to content with padding
  if (cyNodes.length > 0) {
    cy.fit(50);
  }

  // UI Elements
  const noSelectionDiv = document.getElementById("noSelection");
  const nodePropertiesDiv = document.getElementById("nodeProperties");
  const edgePropertiesDiv = document.getElementById("edgeProperties");
  const deleteBtn = document.getElementById("deleteBtn");
  const addNodeBtn = document.getElementById("addNodeBtn");
  const addEdgeBtn = document.getElementById("addEdgeBtn");
  const edgeModeIndicator = document.getElementById("edgeModeIndicator");

  // Show/hide property panels
  function showNoSelection() {
    noSelectionDiv.classList.remove("hidden");
    nodePropertiesDiv.classList.add("hidden");
    edgePropertiesDiv.classList.add("hidden");
    deleteBtn.disabled = true;
  }

  function showNodeProperties(node) {
    noSelectionDiv.classList.add("hidden");
    nodePropertiesDiv.classList.remove("hidden");
    edgePropertiesDiv.classList.add("hidden");
    deleteBtn.disabled = false;

    document.getElementById("nodeName").value = node.data("name") || "";
    document.getElementById("nodeX").value = (
      node.position("x") / SCALE
    ).toFixed(1);
    document.getElementById("nodeY").value = (
      node.position("y") / SCALE
    ).toFixed(1);

    // Set checkboxes for node types
    const typeIds = node.data("nodeTypes") || [];
    document.querySelectorAll(".nodeTypeCheckbox").forEach((cb) => {
      cb.checked = typeIds.includes(parseInt(cb.value));
    });
  }

  function showEdgeProperties(edge) {
    noSelectionDiv.classList.add("hidden");
    nodePropertiesDiv.classList.add("hidden");
    edgePropertiesDiv.classList.remove("hidden");
    deleteBtn.disabled = false;

    document.getElementById("edgeName").value = edge.data("name") || "";
    document.getElementById("edgeConnection").textContent = `${edge
      .source()
      .data("label")} → ${edge.target().data("label")}`;
    document.getElementById("edgeBiking").checked =
      edge.data("biking") || false;
    document.getElementById("edgeWalking").checked =
      edge.data("walking") || false;
    document.getElementById("edgeMaxLanes").value = edge.data("maxLanes") || 2;

    // Street edge
    const edgeType = edge.data("edgeType") || "path";
    const hasStreet = edgeType === "street" || edgeType === "both";
    const hasTrain = edgeType === "train" || edgeType === "both";

    document.getElementById("hasStreetEdge").checked = hasStreet;
    document
      .getElementById("streetEdgeFields")
      .classList.toggle("hidden", !hasStreet);
    if (hasStreet) {
      document.getElementById("streetSpeedLimit").value =
        edge.data("speedLimit") || 50;
      document.getElementById("streetLanes").value = edge.data("lanes") || 1;
      document.getElementById("streetBusLane").checked =
        edge.data("dedicatedBusLane") || false;
    }

    // Train edge
    document.getElementById("hasTrainEdge").checked = hasTrain;
  }

  // Selection handling
  cy.on("select", "node", function (evt) {
    if (edgeMode) {
      handleEdgeModeClick(evt.target);
      return;
    }
    selectedElement = evt.target;
    showNodeProperties(evt.target);
  });

  cy.on("select", "edge", function (evt) {
    if (edgeMode) return;
    selectedElement = evt.target;
    showEdgeProperties(evt.target);
  });

  cy.on("unselect", function () {
    if (!edgeMode) {
      selectedElement = null;
      showNoSelection();
    }
  });

  // Track node movement
  cy.on("dragfree", "node", function (evt) {
    hasChanges = true;
    const node = evt.target;

    // Update position fields if this node is selected
    if (selectedElement && selectedElement.id() === node.id()) {
      document.getElementById("nodeX").value = (
        node.position("x") / SCALE
      ).toFixed(1);
      document.getElementById("nodeY").value = (
        node.position("y") / SCALE
      ).toFixed(1);
    }
  });

  // Add Node
  addNodeBtn.addEventListener("click", function () {
    const extent = cy.extent();
    const x = (extent.x1 + extent.x2) / 2;
    const y = (extent.y1 + extent.y2) / 2;

    const newNode = cy.add({
      data: {
        id: "n_new_" + nextNodeId,
        label: "New Node",
        originalId: null,
        name: "New Node",
        nodeTypes: [],
        isNew: true,
      },
      position: { x, y },
    });

    nextNodeId++;
    hasChanges = true;
    cy.nodes().unselect();
    newNode.select();
  });

  // Edge Mode
  addEdgeBtn.addEventListener("click", function () {
    edgeMode = !edgeMode;
    edgeModeIndicator.classList.toggle("hidden", !edgeMode);
    addEdgeBtn.classList.toggle("ring-2", edgeMode);
    addEdgeBtn.classList.toggle("ring-white", edgeMode);

    if (!edgeMode) {
      cy.nodes().removeClass("edge-source");
      edgeSourceNode = null;
    }
  });

  function handleEdgeModeClick(node) {
    if (!edgeSourceNode) {
      edgeSourceNode = node;
      node.addClass("edge-source");
    } else if (edgeSourceNode.id() !== node.id()) {
      // Create edge
      const sourceName = edgeSourceNode.data("name") || "Source";
      const targetName = node.data("name") || "Target";

      const newEdge = cy.add({
        data: {
          id: "e_new_" + nextEdgeId,
          source: edgeSourceNode.id(),
          target: node.id(),
          label: `${sourceName} → ${targetName}`,
          originalId: null,
          name: `${sourceName} → ${targetName}`,
          biking: true,
          walking: true,
          maxLanes: 2,
          edgeType: "path",
          speedLimit: null,
          lanes: null,
          dedicatedBusLane: false,
          edgeColor: "#8b5cf6",
          edgeStyle: "solid",
          isNew: true,
        },
      });

      nextEdgeId++;
      hasChanges = true;

      // Reset edge mode
      edgeSourceNode.removeClass("edge-source");
      edgeSourceNode = null;

      // Select the new edge
      cy.elements().unselect();
      newEdge.select();
    }
  }

  // Delete selected
  deleteBtn.addEventListener("click", function () {
    if (selectedElement) {
      selectedElement.remove();
      selectedElement = null;
      hasChanges = true;
      showNoSelection();
    }
  });

  // Apply node changes
  document
    .getElementById("applyNodeBtn")
    .addEventListener("click", function () {
      if (!selectedElement || !selectedElement.isNode()) return;

      const name = document.getElementById("nodeName").value;
      const x = parseFloat(document.getElementById("nodeX").value) * SCALE;
      const y = parseFloat(document.getElementById("nodeY").value) * SCALE;

      // Collect selected types
      const nodeTypes = [];
      document.querySelectorAll(".nodeTypeCheckbox:checked").forEach((cb) => {
        nodeTypes.push(parseInt(cb.value));
      });

      selectedElement.data("name", name);
      selectedElement.data("label", name);
      selectedElement.data("nodeTypes", nodeTypes);
      selectedElement.position({ x, y });

      // Update color
      selectedElement.style(
        "background-color",
        getNodeColorByTypeIds(nodeTypes)
      );

      hasChanges = true;
    });

  // Toggle street edge fields
  document
    .getElementById("hasStreetEdge")
    .addEventListener("change", function () {
      document
        .getElementById("streetEdgeFields")
        .classList.toggle("hidden", !this.checked);
    });

  // Apply edge changes
  document
    .getElementById("applyEdgeBtn")
    .addEventListener("click", function () {
      if (!selectedElement || !selectedElement.isEdge()) return;

      const name = document.getElementById("edgeName").value;
      const biking = document.getElementById("edgeBiking").checked;
      const walking = document.getElementById("edgeWalking").checked;
      const maxLanes = parseInt(document.getElementById("edgeMaxLanes").value);
      const hasStreet = document.getElementById("hasStreetEdge").checked;
      const hasTrain = document.getElementById("hasTrainEdge").checked;

      // Determine edge type
      let edgeType = "path";
      if (hasStreet && hasTrain) {
        edgeType = "both";
      } else if (hasStreet) {
        edgeType = "street";
      } else if (hasTrain) {
        edgeType = "train";
      }

      selectedElement.data("name", name);
      selectedElement.data("label", name);
      selectedElement.data("biking", biking);
      selectedElement.data("walking", walking);
      selectedElement.data("maxLanes", maxLanes);
      selectedElement.data("edgeType", edgeType);

      // Street properties
      if (hasStreet) {
        selectedElement.data(
          "speedLimit",
          parseInt(document.getElementById("streetSpeedLimit").value)
        );
        selectedElement.data(
          "lanes",
          parseInt(document.getElementById("streetLanes").value)
        );
        selectedElement.data(
          "dedicatedBusLane",
          document.getElementById("streetBusLane").checked
        );
      } else {
        selectedElement.data("speedLimit", null);
        selectedElement.data("lanes", null);
        selectedElement.data("dedicatedBusLane", false);
      }

      // Update style
      const style = getEdgeStyleByType(edgeType, biking, walking);
      selectedElement.data("edgeColor", style.color);
      selectedElement.data("edgeStyle", style.style);

      hasChanges = true;
    });

  // Reset
  document.getElementById("resetBtn").addEventListener("click", function () {
    if (confirm("Reset all changes? This will reload the page.")) {
      window.location.reload();
    }
  });

  // Save form
  document.getElementById("saveForm").addEventListener("submit", function (e) {
    // Collect all graph data
    const graphData = {
      nodes: [],
      edges: [],
    };

    cy.nodes().forEach((node) => {
      graphData.nodes.push({
        id: node.data("originalId"),
        name: node.data("name"),
        x_position: node.position("x") / SCALE,
        y_position: node.position("y") / SCALE,
        node_types: node.data("nodeTypes"),
        isNew: node.data("isNew") || false,
        cyId: node.id(),
      });
    });

    cy.edges().forEach((edge) => {
      graphData.edges.push({
        id: edge.data("originalId"),
        name: edge.data("name"),
        source_cyId: edge.source().id(),
        target_cyId: edge.target().id(),
        biking: edge.data("biking"),
        walking: edge.data("walking"),
        max_lanes: edge.data("maxLanes"),
        edge_type: edge.data("edgeType"),
        speed_limit: edge.data("speedLimit"),
        lanes: edge.data("lanes"),
        dedicated_bus_lane: edge.data("dedicatedBusLane"),
        isNew: edge.data("isNew") || false,
      });
    });

    document.getElementById("graphDataInput").value = JSON.stringify(graphData);
  });

  // Warn before leaving with unsaved changes
  window.addEventListener("beforeunload", function (e) {
    if (hasChanges) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
});
