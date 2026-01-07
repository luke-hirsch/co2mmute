/**
 * Map Detail SVG Rendering Script
 * Handles rendering of nodes, edges, and interactive labels
 */
(() => {
  const initMapVisualization = () => {
    const svg = document.getElementById("mapSvg");
    const nodesDataEl = document.getElementById("mapNodesData");
    const edgesDataEl = document.getElementById("mapEdgesData");

    if (!svg || !nodesDataEl || !edgesDataEl) {
      console.error("Map elements not found");
      return;
    }

    const nodesDataStr = nodesDataEl.textContent;
    const edgesDataStr = edgesDataEl.textContent;

    if (!nodesDataStr || !edgesDataStr) {
      console.error("Map data not available");
      return;
    }

    let nodesData, edgesData;
    try {
      nodesData = JSON.parse(nodesDataStr);
      edgesData = JSON.parse(edgesDataStr);
    } catch (e) {
      console.error("Error parsing map data:", e);
      return;
    }

    // Calculate dimensions
    const padding = 60;
    const minX =
      Math.min(...nodesData.map((n) => n.x_position * 100)) - padding;
    const minY =
      Math.min(...nodesData.map((n) => n.y_position * 100)) - padding;
    const maxX =
      Math.max(...nodesData.map((n) => n.x_position * 100)) + padding;
    const maxY =
      Math.max(...nodesData.map((n) => n.y_position * 100)) + padding;
    const width = maxX - minX;
    const height = maxY - minY;

    svg.setAttribute("viewBox", `${minX} ${minY} ${width} ${height}`);
    svg.style.aspectRatio = `${width}/${height}`;

    // Draw grid - set position and size to cover entire viewBox
    const gridRect = document.getElementById("gridRect");
    gridRect.setAttribute("x", minX);
    gridRect.setAttribute("y", minY);
    gridRect.setAttribute("width", width);
    gridRect.setAttribute("height", height);
    gridRect.style.display = "block";

    // Helper function to get edge color and style
    const getEdgeStyle = (edge) => {
      const hasStreetEdge = edge.street_edge !== null;
      const hasTrainEdge = edge.train_edge !== null;

      if (hasTrainEdge && !hasStreetEdge) {
        return { stroke: "#ef4444", strokeDasharray: "5,5" };
      }
      if (hasStreetEdge && hasTrainEdge) {
        return { stroke: "#f97316", strokeDasharray: "0" };
      }
      if (hasStreetEdge) {
        return { stroke: "#6b7280", strokeDasharray: "0" };
      }
      if (edge.biking && !edge.walking) {
        return { stroke: "#3b82f6", strokeDasharray: "0" };
      }
      if (edge.walking && !edge.biking) {
        return { stroke: "#10b981", strokeDasharray: "0" };
      }
      return { stroke: "#8b5cf6", strokeDasharray: "0" };
    };

    // Helper function to get node color
    const getNodeColor = (nodeTypes) => {
      const typeNames = nodeTypes.map((t) => t.name);
      if (typeNames.includes("home")) return "#10b981";
      if (typeNames.includes("workplace")) return "#3b82f6";
      if (typeNames.includes("station")) return "#f59e0b";
      if (typeNames.includes("bus_stop")) return "#ef4444";
      return "#6b7280";
    };

    // Draw edges
    edgesData.forEach((edge) => {
      const startNode = nodesData.find((n) => n.id === edge.start_node);
      const endNode = nodesData.find((n) => n.id === edge.end_node);

      if (!startNode || !endNode) return;

      const x1 = startNode.x_position * 100;
      const y1 = startNode.y_position * 100;
      const x2 = endNode.x_position * 100;
      const y2 = endNode.y_position * 100;

      const style = getEdgeStyle(edge);
      const line = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "line"
      );
      line.setAttribute("x1", x1);
      line.setAttribute("y1", y1);
      line.setAttribute("x2", x2);
      line.setAttribute("y2", y2);
      line.setAttribute("stroke", style.stroke);
      line.setAttribute("stroke-width", "2");
      line.setAttribute("stroke-dasharray", style.strokeDasharray);
      line.setAttribute("opacity", "0.6");
      line.style.cursor = "pointer";
      line.title = edge.name;

      svg.appendChild(line);
    });

    // Track currently selected node for label toggle
    let selectedNodeId = null;

    // Draw nodes
    nodesData.forEach((node) => {
      const x = node.x_position * 100;
      const y = node.y_position * 100;
      const color = getNodeColor(node.node_type);

      // Create a group for node and label
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.setAttribute("data-node-id", node.id);

      const circle = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle"
      );
      circle.setAttribute("cx", x);
      circle.setAttribute("cy", y);
      circle.setAttribute("r", "10");
      circle.setAttribute("fill", color);
      circle.style.cursor = "pointer";
      circle.setAttribute("class", "node-circle");

      group.appendChild(circle);

      // Create label background (pill shape)
      const labelBg = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect"
      );
      labelBg.setAttribute("rx", "4");
      labelBg.setAttribute("ry", "4");
      labelBg.setAttribute("class", "node-label-bg");
      labelBg.style.display = "none";

      // Add label text
      const text = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "text"
      );
      text.setAttribute("x", x);
      text.setAttribute("y", y + 25);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-size", "10");
      text.setAttribute("class", "node-label");
      text.style.fontWeight = "bold";
      text.style.display = "none";
      text.textContent = node.name || `Node ${node.id}`;

      group.appendChild(labelBg);
      group.appendChild(text);

      // Click handler to toggle label
      group.addEventListener("click", () => {
        const isCurrentlySelected = selectedNodeId === node.id;

        // Hide all labels first
        document.querySelectorAll(".node-label").forEach((label) => {
          label.style.display = "none";
        });
        document.querySelectorAll(".node-label-bg").forEach((bg) => {
          bg.style.display = "none";
        });

        if (!isCurrentlySelected) {
          // Show this node's label
          text.style.display = "block";

          // Position and show background
          const bbox = text.getBBox();
          const paddingX = 6;
          const paddingY = 3;
          labelBg.setAttribute("x", bbox.x - paddingX);
          labelBg.setAttribute("y", bbox.y - paddingY);
          labelBg.setAttribute("width", bbox.width + paddingX * 2);
          labelBg.setAttribute("height", bbox.height + paddingY * 2);
          labelBg.style.display = "block";

          selectedNodeId = node.id;
        } else {
          selectedNodeId = null;
        }
      });

      // Hover effect
      circle.addEventListener("mouseenter", () => {
        circle.setAttribute("r", "12");
      });
      circle.addEventListener("mouseleave", () => {
        circle.setAttribute("r", "10");
      });

      svg.appendChild(group);
    });

    // Click on SVG background to deselect
    svg.addEventListener("click", (e) => {
      if (e.target === svg || e.target === gridRect) {
        document.querySelectorAll(".node-label").forEach((label) => {
          label.style.display = "none";
        });
        document.querySelectorAll(".node-label-bg").forEach((bg) => {
          bg.style.display = "none";
        });
        selectedNodeId = null;
      }
    });
  };

  // Initialize when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMapVisualization);
  } else {
    initMapVisualization();
  }
})();
