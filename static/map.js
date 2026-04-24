const NODE_COLORS = {
    hub: { bg: "#00fff5", color: "#000", label: "ХАБ" },
    combat: { bg: "#e94560", color: "#fff", label: "БОЙ" },
    elite: { bg: "#ff4444", color: "#fff", label: "ЭЛИТА" },
    boss: { bg: "#ff00e4", color: "#fff", label: "БОСС" },
    rest: { bg: "#2ecc71", color: "#000", label: "ОТДЫХ" },
    shop: { bg: "#ffd700", color: "#000", label: "МАГАЗ" },
    event: { bg: "#b44aff", color: "#fff", label: "СОБЫТ" },
    ambush: { bg: "#ffff00", color: "#000", label: "ЗАСАДА" },
};

function renderDAGMap(run, containerId, onNodeClick) {
    const container = document.getElementById(containerId);
    if (!container || !run || !run.map_nodes) return;

    container.innerHTML = "";

    const nodes = run.map_nodes;
    const currentId = run.current_node_index;

    const nodesByFloor = {};
    nodes.forEach(n => {
        const f = n.floor || 0;
        if (!nodesByFloor[f]) nodesByFloor[f] = [];
        nodesByFloor[f].push(n);
    });

    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "600");
    svg.style.display = "block";
    container.appendChild(svg);

    const floorHeight = 55;
    const startY = 30;
    const centerX = 300;

    const nodePositions = {};

    Object.keys(nodesByFloor).sort((a, b) => parseInt(a) - parseInt(b)).forEach(floorKey => {
        const floorNodes = nodesByFloor[floorKey];
        const f = parseInt(floorKey);
        const y = startY + f * floorHeight;

        const count = floorNodes.length;
        const spacing = count > 1 ? 140 : 0;
        const startX = centerX - (spacing * (count - 1)) / 2;

        floorNodes.forEach((node, i) => {
            const x = startX + i * spacing;
            nodePositions[node.index] = { x, y, node };
        });
    });

    nodes.forEach(n => {
        if (n.next_nodes) {
            n.next_nodes.forEach(nextId => {
                const target = nodePositions[nextId];
                const source = nodePositions[n.index];
                if (target && source) {
                    const line = document.createElementNS(svgNS, "line");
                    line.setAttribute("x1", source.x);
                    line.setAttribute("y1", source.y + 18);
                    line.setAttribute("x2", target.x);
                    line.setAttribute("y2", target.y - 18);
                    line.setAttribute("stroke", "#333");
                    line.setAttribute("stroke-width", "2");
                    svg.appendChild(line);
                }
            });
        }
    });

    const currentNode = nodes.find(n => n.index === currentId);
    const reachableIndices = new Set();
    if (currentNode && currentNode.next_nodes) {
        currentNode.next_nodes.forEach(id => reachableIndices.add(id));
    }

    nodes.forEach(n => {
        const pos = nodePositions[n.index];
        if (!pos) return;

        const style = NODE_COLORS[n.node_type] || NODE_COLORS.combat;
        const isCurrent = n.index === currentId;
        const isCompleted = n.completed;
        const isReachable = reachableIndices.has(n.index);

        const g = document.createElementNS(svgNS, "g");
        g.style.cursor = isReachable ? "pointer" : "default";

        const circle = document.createElementNS(svgNS, "circle");
        circle.setAttribute("cx", pos.x);
        circle.setAttribute("cy", pos.y);
        circle.setAttribute("r", "18");
        circle.setAttribute("fill", style.bg);
        circle.setAttribute("stroke", isCurrent ? "#fff" : (isReachable ? "#ffd700" : "#333"));
        circle.setAttribute("stroke-width", isCurrent ? "3" : (isReachable ? "2" : "1"));

        if (isReachable) {
            circle.setAttribute("filter", "drop-shadow(0 0 6px rgba(255,215,0,0.6))");
        }

        if (isCompleted) {
            circle.setAttribute("opacity", "0.5");
        }

        g.appendChild(circle);

        const text = document.createElementNS(svgNS, "text");
        text.setAttribute("x", pos.x);
        text.setAttribute("y", pos.y + 4);
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("fill", style.color);
        text.setAttribute("font-size", "9");
        text.setAttribute("font-weight", "bold");
        text.textContent = style.label;
        g.appendChild(text);

        const floorText = document.createElementNS(svgNS, "text");
        floorText.setAttribute("x", pos.x);
        floorText.setAttribute("y", pos.y - 26);
        floorText.setAttribute("text-anchor", "middle");
        floorText.setAttribute("fill", "#666");
        floorText.setAttribute("font-size", "10");
        floorText.textContent = "Э" + (n.floor + 1);
        g.appendChild(floorText);

        if (isReachable) {
            g.addEventListener("click", () => {
                if (onNodeClick) onNodeClick(n.index);
            });
        }

        svg.appendChild(g);
    });
}
