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

    // Группируем узлы по этажам
    const nodesByFloor = {};
    nodes.forEach(n => {
        const f = n.floor || 0;
        if (!nodesByFloor[f]) nodesByFloor[f] = [];
        nodesByFloor[f].push(n);
    });

    // Определяем достижимые узлы
    const currentNode = nodes.find(n => n.index === currentId);
    const reachableIndices = new Set();
    if (currentNode && currentNode.next_nodes) {
        currentNode.next_nodes.forEach(id => reachableIndices.add(id));
    }

    // Создаем контейнер для этажей
    const floorsContainer = document.createElement("div");
    floorsContainer.className = "floors-container";
    floorsContainer.style.display = "flex";
    floorsContainer.style.flexDirection = "column";
    floorsContainer.style.gap = "12px";
    floorsContainer.style.padding = "10px";
    container.appendChild(floorsContainer);

    // Рендерим каждый этаж
    const sortedFloors = Object.keys(nodesByFloor).sort((a, b) => parseInt(a) - parseInt(b));

    sortedFloors.forEach(floorKey => {
        const floorNodes = nodesByFloor[floorKey];
        const f = parseInt(floorKey);

        // Строка этажа
        const floorRow = document.createElement("div");
        floorRow.className = "floor-row";
        floorRow.style.display = "flex";
        floorRow.style.justifyContent = "center";
        floorRow.style.alignItems = "center";
        floorRow.style.gap = "16px";
        floorRow.style.minHeight = "60px";

        // Сортируем узлы по lane для консистентности
        floorNodes.sort((a, b) => (a.lane || 0) - (b.lane || 0));

        floorNodes.forEach(n => {
            const style = NODE_COLORS[n.node_type] || NODE_COLORS.combat;
            const isCurrent = n.index === currentId;
            const isCompleted = n.completed;
            const isReachable = reachableIndices.has(n.index);

            // HTML кнопка вместо SVG
            const btn = document.createElement("button");
            btn.className = "map-node-btn";
            btn.style.width = "80px";
            btn.style.height = "80px";
            btn.style.borderRadius = "50%";
            btn.style.border = isCurrent ? "3px solid #fff" : (isReachable ? "2px solid #ffd700" : "2px solid #333");
            btn.style.backgroundColor = style.bg;
            btn.style.color = style.color;
            btn.style.fontSize = "11px";
            btn.style.fontWeight = "bold";
            btn.style.cursor = isReachable ? "pointer" : "default";
            btn.style.display = "flex";
            btn.style.flexDirection = "column";
            btn.style.alignItems = "center";
            btn.style.justifyContent = "center";
            btn.style.position = "relative";
            btn.style.boxShadow = isReachable ? "0 0 10px rgba(255,215,0,0.6)" : "none";
            btn.style.opacity = isCompleted ? "0.5" : "1";
            btn.style.transition = "transform 0.2s, box-shadow 0.2s";
            btn.style.touchAction = "manipulation"; // Важно для TMA
            btn.style.webkitTapHighlightColor = "transparent";

            // Номер этажа сверху
            const floorLabel = document.createElement("span");
            floorLabel.textContent = "Э" + (n.floor + 1);
            floorLabel.style.fontSize = "9px";
            floorLabel.style.position = "absolute";
            floorLabel.style.top = "4px";
            floorLabel.style.color = "#666";
            btn.appendChild(floorLabel);

            // Основной лейбл
            const label = document.createElement("span");
            label.textContent = style.label;
            btn.appendChild(label);

            // Индикатор текущего узла
            if (isCurrent) {
                const indicator = document.createElement("span");
                indicator.textContent = "●";
                indicator.style.fontSize = "8px";
                indicator.style.position = "absolute";
                indicator.style.bottom = "4px";
                indicator.style.color = "#00fff5";
                btn.appendChild(indicator);
            }

            // Обработчик клика только для достижимых
            if (isReachable) {
                btn.addEventListener("click", (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (onNodeClick) onNodeClick(n.index);
                });
            } else {
                btn.disabled = true;
                btn.style.pointerEvents = "none";
            }

            floorRow.appendChild(btn);
        });

        floorsContainer.appendChild(floorRow);
    });
}
