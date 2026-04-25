const NODE_COLORS = {
    hub: { bg: "#00fff5", color: "#000", label: "СТАРТ" },
    combat: { bg: "#e94560", color: "#fff", label: "БОЙ" },
    elite: { bg: "#ff4444", color: "#fff", label: "ЭЛИТА" },
    boss: { bg: "#ff00e4", color: "#fff", label: "БОСС" },
    rest: { bg: "#2ecc71", color: "#000", label: "ОТДЫХ" },
    shop: { bg: "#ffd700", color: "#000", label: "МАГАЗ" },
    event: { bg: "#b44aff", color: "#fff", label: "?" },
    ambush: { bg: "#ffff00", color: "#000", label: "ЗАСАДА" },
};

function renderDAGMap(run, containerId, onNodeClick) {
    const container = document.getElementById(containerId);
    if (!container || !run || !run.map_nodes) return;

    container.innerHTML = "";

    const nodes = run.map_nodes;
    const currentId = run.current_node_index;
    const currentNode = nodes.find(n => n.index === currentId);

    // Контейнер с column-reverse (карта растет снизу вверх как в STS)
    const mapWrapper = document.createElement("div");
    mapWrapper.className = "map-sts-wrapper";
    mapWrapper.style.display = "flex";
    mapWrapper.style.flexDirection = "column-reverse"; // STS: снизу вверх
    mapWrapper.style.gap = "60px"; // Пространство для линий
    mapWrapper.style.padding = "20px 10px";
    mapWrapper.style.minHeight = "100%";
    mapWrapper.style.position = "relative";
    container.appendChild(mapWrapper);

    // SVG слой для линий (за HTML узлами)
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.className = "map-svg-lines";
    svg.style.position = "absolute";
    svg.style.top = "0";
    svg.style.left = "0";
    svg.style.width = "100%";
    svg.style.height = "100%";
    svg.style.pointerEvents = "none";
    svg.style.zIndex = "1";
    mapWrapper.appendChild(svg);

    // Группируем узлы по этажам
    const nodesByFloor = {};
    nodes.forEach(n => {
        const f = n.floor || 0;
        if (!nodesByFloor[f]) nodesByFloor[f] = [];
        nodesByFloor[f].push(n);
    });

    // Сортируем этажи (0 снизу, 9 сверху из-за column-reverse)
    const sortedFloors = Object.keys(nodesByFloor)
        .map(f => parseInt(f))
        .sort((a, b) => a - b);

    // Позиции узлов для рисования линий
    const nodePositions = {};
    const floorRows = {};

    // Рендерим каждый этаж (от 0 к 9, но column-reverse покажет 9 сверху)
    sortedFloors.forEach(floorNum => {
        const floorNodes = nodesByFloor[floorNum];

        // Строка этажа
        const floorRow = document.createElement("div");
        floorRow.className = "floor-row";
        floorRow.style.display = "flex";
        floorRow.style.justifyContent = "center";
        floorRow.style.alignItems = "center";
        floorRow.style.gap = "40px";
        floorRow.style.position = "relative";
        floorRow.style.zIndex = "2";

        // Сортируем по lane
        floorNodes.sort((a, b) => (a.lane || 0) - (b.lane || 0));

        // Создаем узлы
        floorNodes.forEach((n, idx) => {
            const style = NODE_COLORS[n.node_type] || NODE_COLORS.combat;
            const isCurrent = n.index === currentId;
            const isCompleted = n.completed;

            // Проверка is_reachable: узел должен быть в next_nodes текущего узла
            const isReachable = currentNode &&
                currentNode.next_nodes &&
                currentNode.next_nodes.includes(n.index);

            // HTML кнопка для узла
            const btn = document.createElement("button");
            btn.className = "map-node-btn" + (isCurrent ? " current" : "") + (isReachable ? " reachable" : "");
            btn.dataset.nodeId = n.index;
            btn.dataset.floor = n.floor;
            btn.dataset.lane = n.lane;

            // Стили для круглого узла
            btn.style.width = "56px";
            btn.style.height = "56px";
            btn.style.borderRadius = "50%";
            btn.style.border = isCurrent ? "3px solid #fff" : (isReachable ? "2px solid #ffd700" : "2px solid #444");
            btn.style.backgroundColor = style.bg;
            btn.style.color = style.color;
            btn.style.fontSize = "10px";
            btn.style.fontWeight = "bold";
            btn.style.cursor = isReachable ? "pointer" : "default";
            btn.style.display = "flex";
            btn.style.alignItems = "center";
            btn.style.justifyContent = "center";
            btn.style.position = "relative";
            btn.style.boxShadow = isReachable ? "0 0 12px rgba(255,215,0,0.7)" : (isCurrent ? "0 0 8px rgba(0,255,245,0.5)" : "none");
            btn.style.opacity = isCompleted ? "0.4" : "1";
            btn.style.transition = "transform 0.15s";
            btn.style.touchAction = "manipulation";
            btn.style.webkitTapHighlightColor = "transparent";
            btn.style.zIndex = "3";

            // Лейбл типа узла
            btn.textContent = style.label;

            // Обработчик клика с дебаг логом
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();

                // Дебаг: логируем клик и валидные next_nodes
                const validNextNodes = currentNode ? currentNode.next_nodes : [];
                console.log("[MAP CLICK] clickedNodeId:", n.index, "validNextNodes:", validNextNodes, "isReachable:", isReachable);

                if (isReachable && onNodeClick) {
                    onNodeClick(n.index);
                }
            });

            floorRow.appendChild(btn);

            // Сохраняем позицию для линий (обновим после рендера)
            nodePositions[n.index] = { node: n, element: btn, floor: floorNum, lane: n.lane };
        });

        mapWrapper.appendChild(floorRow);
        floorRows[floorNum] = floorRow;
    });

    // Рисуем линии после того как DOM готов
    setTimeout(() => drawConnections(svg, nodePositions, nodes, svgNS), 0);
}

function drawConnections(svg, nodePositions, allNodes, svgNS) {
    // Очищаем старые линии
    svg.innerHTML = "";

    // Для каждого узла рисуем линии к его next_nodes
    allNodes.forEach(node => {
        if (!node.next_nodes || node.next_nodes.length === 0) return;

        const fromPos = nodePositions[node.index];
        if (!fromPos) return;

        const fromRect = fromPos.element.getBoundingClientRect();
        const svgRect = svg.getBoundingClientRect();

        // Центр исходного узла (относительно SVG)
        const x1 = fromRect.left + fromRect.width / 2 - svgRect.left;
        const y1 = fromRect.top + fromRect.height / 2 - svgRect.top;

        node.next_nodes.forEach(targetId => {
            const toPos = nodePositions[targetId];
            if (!toPos) return;

            const toRect = toPos.element.getBoundingClientRect();
            const x2 = toRect.left + toRect.width / 2 - svgRect.left;
            const y2 = toRect.top + toRect.height / 2 - svgRect.top;

            // Создаем линию
            const line = document.createElementNS(svgNS, "line");
            line.setAttribute("x1", x1);
            line.setAttribute("y1", y1);
            line.setAttribute("x2", x2);
            line.setAttribute("y2", y2);
            line.setAttribute("stroke", "#444");
            line.setAttribute("stroke-width", "2");
            line.setAttribute("stroke-dasharray", "4,4");

            svg.appendChild(line);
        });
    });
}
