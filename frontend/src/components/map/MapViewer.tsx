import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { GameMap, MapGraph, CytoscapeElement } from "../../types/mapTypes";

interface MapViewerProps {
  gameMap: GameMap;
  mapGraph: MapGraph;
}

const MapViewer = ({ gameMap, mapGraph }: MapViewerProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!containerRef.current || !mapGraph) return;

    // Convert map graph data to Cytoscape format
    const elements: CytoscapeElement[] = [];

    // Add nodes
    mapGraph.nodes.forEach((node) => {
      elements.push({
        data: {
          id: node.id.toString(),
          label: node.name || `Node ${node.id}`,
          x: node.x_position * 100,
          y: node.y_position * 100,
          types: node.node_type.map((nt) => nt.name),
        },
      });
    });

    // Add edges
    mapGraph.edges.forEach((edge) => {
      elements.push({
        data: {
          id: edge.id.toString(),
          source: edge.start_node.toString(),
          target: edge.end_node.toString(),
          label: edge.name || `Edge ${edge.id}`,
        },
      });
    });

    // Initialize Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: "node",
          style: {
            content: "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "#4f46e5",
            color: "#ffffff",
            width: "60px",
            height: "60px",
            "font-size": "12px",
            padding: "10px",
            "border-width": "2px",
            "border-color": "#312e81",
          },
        },
        {
          selector: "edge",
          style: {
            "line-color": "#9ca3af",
            "target-arrow-color": "#9ca3af",
            "target-arrow-shape": "triangle",
            width: "2px",
            "curve-style": "bezier",
          },
        },
        {
          selector: "node:selected",
          style: {
            "background-color": "#ec4899",
            "border-color": "#be185d",
          },
        },
        {
          selector: "edge:selected",
          style: {
            "line-color": "#ec4899",
            "target-arrow-color": "#ec4899",
            width: "3px",
          },
        },
      ] as any,
      layout: {
        name: "preset",
        positions: (node: any) => {
          const data = node.data();
          return {
            x: data.x,
            y: data.y,
          };
        },
      } as any,
      wheelSensitivity: 0.1,
      userZoomingEnabled: true,
      userPanningEnabled: true,
    });

    cyRef.current = cy;

    // Auto-fit the graph
    cy.fit();

    // Handle node/edge selection
    cy.on("tap", "node, edge", (evt) => {
      const element = evt.target;
      console.log("Selected:", element.data());
    });

    // Deselect on background click
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().unselect();
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [mapGraph]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-main dark:text-darktext mb-2">
          {gameMap.name}
        </h1>
        {gameMap.description && (
          <p className="text-muted dark:text-darkmutedtext">
            {gameMap.description}
          </p>
        )}
      </div>

      {/* Map Info */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 mb-8 border border-subtle dark:border-darksubtle">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Max Players
            </p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {gameMap.max_player}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Dimensions
            </p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {gameMap.x_dim} × {gameMap.y_dim}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">Author</p>
            <p className="text-lg font-semibold text-main dark:text-darktext">
              {gameMap.author.username}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Created
            </p>
            <p className="text-lg font-semibold text-main dark:text-darktext">
              {new Date(gameMap.created).toLocaleDateString()}
            </p>
          </div>
        </div>
      </div>

      {/* Graph Stats */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 mb-8 border border-subtle dark:border-darksubtle">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">Nodes</p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {mapGraph.node_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">Edges</p>
            <p className="text-2xl font-bold text-main dark:text-darktext">
              {mapGraph.edge_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted dark:text-darkmutedtext">
              Version
            </p>
            <p className="text-lg font-semibold text-main dark:text-darktext">
              {mapGraph.version_name}
            </p>
          </div>
        </div>
      </div>

      {/* Cytoscape Container */}
      <div className="bg-surface dark:bg-darksurface rounded-lg shadow-lg border border-subtle dark:border-darksubtle overflow-hidden mb-8">
        <div
          ref={containerRef}
          className="w-full"
          style={{ height: "600px", backgroundColor: "#f5f5f5" }}
        />
      </div>

      {/* Legend */}
      <div className="bg-subtle dark:bg-darksubtle rounded-lg p-6 border border-subtle dark:border-darksubtle">
        <h2 className="text-lg font-semibold text-main dark:text-darktext mb-4">
          Legend
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-main dark:text-darktext mb-3">
              Node Types
            </h3>
            <ul className="space-y-2 text-sm text-muted dark:text-darkmutedtext">
              <li>
                🏠 <span>Home</span>
              </li>
              <li>
                💼 <span>Workplace</span>
              </li>
              <li>
                🚏 <span>Bus Stop</span>
              </li>
              <li>
                🚉 <span>Station</span>
              </li>
              <li>
                🛣️ <span>Intersection</span>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-main dark:text-darktext mb-3">
              Edge Types
            </h3>
            <ul className="space-y-2 text-sm text-muted dark:text-darkmutedtext">
              <li>
                — <span className="inline-block w-8 h-0.5 bg-blue-500"></span>{" "}
                Street
              </li>
              <li>
                — <span className="inline-block w-8 h-0.5 bg-red-500"></span>{" "}
                Train
              </li>
              <li>
                — <span className="inline-block w-8 h-0.5 bg-green-500"></span>{" "}
                Both
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapViewer;
