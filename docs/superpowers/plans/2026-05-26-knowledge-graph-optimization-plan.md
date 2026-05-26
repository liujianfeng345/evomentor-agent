# 知识图谱可视化优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 D3.js 力导向图替换 Canvas 圆形布局，增加筛选搜索和分类折叠，让 47 个节点的知识图谱清晰可用。

**Architecture:** 后端 `/api/graph` 增加 `search`/`parent`/`min_level` 查询参数，节点加 `group` 字段，响应加 `groups` 列表。前端引入 D3.js v7 CDN，用力模拟（link+charge+center+collide）自动排布节点，SVG 渲染支持 zoom/pan，hover tooltip，点击高亮关联节点，搜索/筛选控制栏联动图谱和图例。

**Tech Stack:** Python FastAPI + SQLite（后端），D3.js v7 CDN + 原生 JS（前端），零构建依赖。

---

## 文件结构

| 文件 | 职责 | 变更 |
|------|------|------|
| `src/web/routes.py:456-503` | `/api/graph` 端点，接受查询参数，返回节点/边/分类 | 修改 |
| `tests/test_api.py` | 测试 `/api/graph` 的查询参数和响应结构 | 新增测试 |
| `src/web/templates/index.html:101-107` | 图谱 Tab 的 HTML 结构（canvas→svg 容器, 控制栏） | 修改 |
| `src/web/templates/index.html:792-889` | 图谱相关的 JS 函数（drawGraph, renderGraphList, loadGraph） | 重写 |
| `src/web/static/style.css` | 图谱控制栏、图例、tooltip、折叠列表的样式 | 新增样式 |

---

### Task 1: 后端 `/api/graph` 增强

**Files:**
- Modify: `src/web/routes.py:456-503`
- Create: `tests/test_graph_api.py`（或追加到 `tests/test_api.py`）

#### Step 1: 编写后端测试

在 `tests/test_graph_api.py` 中创建测试文件：

```python
"""测试 /api/graph 端点的增强功能。"""
import pytest
from fastapi.testclient import TestClient
from src.web.routes import router
from src.db.models import init_db
from src.db.connection import get_connection

client = TestClient(router)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    conn = get_connection()
    # 清理旧数据
    conn.execute("DELETE FROM user_knowledge_graph")
    # 插入测试数据
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("Python 装饰器", 3, "Python 生态"),
    )
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("asyncio 异步", 2, "Python 生态"),
    )
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("Transformer 架构", 4, "人工智能"),
    )
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("偏好设置", 5, "preference"),
    )
    conn.commit()
    conn.close()
    yield
    # 清理
    conn = get_connection()
    conn.execute("DELETE FROM user_knowledge_graph")
    conn.commit()
    conn.close()


def test_graph_returns_groups_field():
    """响应应包含 groups 列表。"""
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert isinstance(data["groups"], list)
    assert "Python 生态" in data["groups"]
    assert "人工智能" in data["groups"]
    assert "preference" not in data["groups"]  # preference 被排除


def test_graph_nodes_have_group_field():
    """每个节点应有 group 字段。"""
    resp = client.get("/api/graph")
    data = resp.json()
    for node in data["nodes"]:
        assert "group" in node
        assert "id" in node
        assert "label" in node
        assert "proficiency" in node


def test_graph_excludes_preference():
    """parent_topic 为 preference 的行不出现在节点中。"""
    resp = client.get("/api/graph")
    data = resp.json()
    labels = [n["label"] for n in data["nodes"]]
    assert "偏好设置" not in labels


def test_graph_search_filter():
    """search 参数模糊匹配 topic。"""
    resp = client.get("/api/graph?search=装饰器")
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["label"] == "Python 装饰器"


def test_graph_parent_filter():
    """parent 参数按 parent_topic 筛选。"""
    resp = client.get("/api/graph?parent=Python 生态")
    data = resp.json()
    labels = [n["label"] for n in data["nodes"]]
    assert "Python 装饰器" in labels
    assert "asyncio 异步" in labels
    assert "Transformer 架构" not in labels


def test_graph_min_level_filter():
    """min_level 参数过滤熟练度低于阈值的节点。"""
    resp = client.get("/api/graph?min_level=3")
    data = resp.json()
    for node in data["nodes"]:
        assert node["proficiency"] >= 3


def test_graph_no_ghost_nodes_with_negative_ids():
    """不应出现负数 ID 的幽灵节点。"""
    resp = client.get("/api/graph")
    data = resp.json()
    for node in data["nodes"]:
        assert node["id"] > 0


def test_graph_combined_filters():
    """组合筛选：parent + min_level + search。"""
    resp = client.get("/api/graph?parent=Python 生态&min_level=2&search=asyncio")
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["label"] == "asyncio 异步"
```

#### Step 2: 运行测试确认失败

```bash
python -m pytest tests/test_graph_api.py -v
```

预期：测试因缺少 `groups` 字段、无 `group` 字段、无筛选支持等而失败。

#### Step 3: 实现增强版 `/api/graph`

替换 `src/web/routes.py:456-503`：

```python
@router.get("/api/graph")
async def get_graph(
    search: str = "",
    parent: str = "",
    min_level: int = 0,
):
    """返回知识图谱的节点和边，支持筛选。"""
    conn = get_connection()

    where_parts = ["parent_topic != 'preference'"]
    params: list = []

    if search:
        where_parts.append("topic LIKE ?")
        params.append(f"%{search}%")
    if parent:
        where_parts.append("parent_topic = ?")
        params.append(parent)
    if min_level > 0:
        where_parts.append("proficiency >= ?")
        params.append(min_level)

    where_clause = " AND ".join(where_parts)
    sql = f"SELECT id, topic, proficiency, parent_topic FROM user_knowledge_graph WHERE {where_clause} ORDER BY proficiency DESC"

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    nodes: list[dict] = []
    edges: list[dict] = []
    topic_ids: dict[str, int] = {}

    for r in rows:
        tid = r["id"]
        topic_ids[r["topic"]] = tid
        parent = r["parent_topic"] or ""
        nodes.append({
            "id": tid,
            "label": r["topic"],
            "group": parent,
            "proficiency": r["proficiency"],
        })
        if parent and parent != "preference":
            edges.append({
                "from": parent,
                "to": r["topic"],
            })

    # 为 edges 中缺少的父级创建分类锚点节点（使用 10000+ 的 ID 避免冲突）
    virtual_id = 10000
    for edge in edges:
        if edge["from"] not in topic_ids:
            nodes.append({
                "id": virtual_id,
                "label": edge["from"],
                "group": edge["from"],
                "proficiency": 0,
                "is_category": True,
            })
            topic_ids[edge["from"]] = virtual_id
            virtual_id += 1

    # 将 edge 的 label 转为 id
    resolved_edges: list[dict] = []
    for edge in edges:
        from_id = topic_ids.get(edge["from"])
        to_id = topic_ids.get(edge["to"])
        if from_id is not None and to_id is not None:
            resolved_edges.append({"from": from_id, "to": to_id})

    # 收集所有分组（去重排序）
    groups = sorted({n["group"] for n in nodes if n["group"]})

    return {"nodes": nodes, "edges": resolved_edges, "groups": groups}
```

关键变更：
- 接受 `search`、`parent`、`min_level` 查询参数
- 每个节点增加 `group` 字段（值为 `parent_topic`）
- 幽灵节点用正数 ID（10000+）并标记 `is_category: true`
- 响应增加 `groups` 字段

#### Step 4: 运行测试确认通过

```bash
python -m pytest tests/test_graph_api.py -v
```

预期：全部 8 个测试通过。

#### Step 5: 提交

```bash
git add tests/test_graph_api.py src/web/routes.py
git commit -m "feat: /api/graph 增强 — 筛选参数 + group/groups 字段 + 去幽灵节点"
```

---

### Task 2: 前端 HTML 结构 + 控制栏

**Files:**
- Modify: `src/web/templates/index.html:101-107`

#### Step 1: 添加 D3.js CDN

在 `index.html` 的 `<head>` 中，在其他 CDN 脚本之后添加：

```html
<script src="https://d3js.org/d3.v7.min.js"></script>
```

插入位置：`index.html` 第 15 行之后（`highlight.js` 脚本加载之后）。

#### Step 2: 替换图谱 Tab 的 HTML 结构

替换 `index.html:101-107` 的图谱面板 HTML：

```html
<!-- 知识图谱 Tab -->
<div class="tab-panel" id="panel-graph">
    <div class="graph-toolbar">
        <input type="text" id="graph-search" placeholder="搜索知识点...">
        <select id="graph-category">
            <option value="">全部分类</option>
        </select>
        <label class="slider-label">
            熟练度 ≥ <span id="level-val">0</span>
            <input type="range" id="graph-level" min="0" max="5" value="0">
        </label>
        <button class="secondary" id="graph-reset">重置</button>
    </div>
    <div id="graph-svg-container"></div>
    <div id="graph-legend"></div>
    <div id="graph-tooltip" style="display:none; position:absolute; pointer-events:none; background:#1a1a2e; color:#e0e0e0; padding:8px 12px; border-radius:6px; font-size:12px; border:1px solid #333; z-index:100;"></div>
    <div id="graph-list"></div>
</div>
```

#### Step 3: 添加 CSS 样式

在 `src/web/static/style.css` 末尾追加：

```css
/* 图谱控制栏 */
.graph-toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 12px;
    padding: 10px;
    background: #161b22;
    border-radius: 8px;
    border: 1px solid #30363d;
}
.graph-toolbar input[type="text"] {
    flex: 1;
    min-width: 140px;
    padding: 6px 10px;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 13px;
}
.graph-toolbar select {
    min-width: 100px;
    padding: 6px 10px;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 13px;
}
.slider-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #888;
    white-space: nowrap;
}

/* 图谱 SVG 容器 */
#graph-svg-container {
    width: 100%;
    height: 500px;
    border: 1px solid #30363d;
    border-radius: 8px;
    background: #0d1117;
    overflow: hidden;
    position: relative;
}

/* 图例 */
#graph-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 8px 0;
    font-size: 12px;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    user-select: none;
}
.legend-item.hidden {
    opacity: 0.35;
}
.legend-color {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

/* 图谱 tooltip */
#graph-tooltip {
    position: absolute;
    pointer-events: none;
    background: #1a1a2e;
    color: #e0e0e0;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    border: 1px solid #333;
    z-index: 100;
    white-space: nowrap;
}

/* 折叠列表 */
.collapse-group {
    margin-bottom: 8px;
}
.collapse-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    cursor: pointer;
    user-select: none;
    font-weight: 600;
    font-size: 14px;
}
.collapse-header:hover {
    background: #1c2333;
}
.collapse-header .arrow {
    transition: transform 0.2s;
    font-size: 10px;
}
.collapse-header .count {
    font-weight: 400;
    font-size: 12px;
    color: #888;
    margin-left: auto;
}
.collapse-body {
    padding: 4px 0 4px 8px;
}
.collapse-body.collapsed {
    display: none;
}
.collapse-group.collapsed .arrow {
    transform: rotate(-90deg);
}
```

#### Step 4: 提交

```bash
git add src/web/templates/index.html src/web/static/style.css
git commit -m "feat: 图谱控制栏 HTML 结构 + D3.js CDN + CSS 样式"
```

---

### Task 3: 前端 D3.js 力导向图 + 交互

**Files:**
- Modify: `src/web/templates/index.html:792-889`

#### Step 1: 重写 `loadGraph()` 和 `drawGraph()`

替换 `index.html` 中第 792-866 行的 `loadGraph` 和 `drawGraph` 函数：

```javascript
// ═══ 知识图谱 Tab ═══
let graphData = { nodes: [], edges: [], groups: [] };
let graphSimulation = null;
let graphColor = null;

async function loadGraph() {
    const search = $('#graph-search').value || '';
    const parent = $('#graph-category').value || '';
    const minLevel = parseInt($('#graph-level').value) || 0;
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (parent) params.set('parent', parent);
    if (minLevel > 0) params.set('min_level', minLevel);

    const url = '/api/graph' + (params.toString() ? '?' + params.toString() : '');
    const data = await api(url);
    graphData = data;
    updateCategorySelect(data.groups);
    drawGraph(data);
    renderLegend(data.groups);
    renderGraphList(data.nodes);
}

function updateCategorySelect(groups) {
    const sel = $('#graph-category');
    const current = sel.value;
    sel.innerHTML = '<option value="">全部分类</option>';
    groups.forEach(g => {
        const opt = document.createElement('option');
        opt.value = g;
        opt.textContent = g;
        sel.appendChild(opt);
    });
    sel.value = current;
}

function drawGraph(data) {
    const container = $('#graph-svg-container');
    container.innerHTML = '';

    if (data.nodes.length === 0) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#888;">暂无匹配的知识图谱数据</div>';
        return;
    }

    const rect = container.getBoundingClientRect();
    const w = rect.width;
    const h = 500;

    const svg = d3.select('#graph-svg-container')
        .append('svg')
        .attr('width', w)
        .attr('height', h);

    const g = svg.append('g');

    // 缩放平移
    const zoom = d3.zoom()
        .scaleExtent([0.15, 5])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    svg.call(zoom);

    // 颜色映射
    graphColor = d3.scaleOrdinal(d3.schemeCategory10).domain(data.groups);

    // 力模拟
    const simulation = d3.forceSimulation(data.nodes)
        .force('link', d3.forceLink(data.edges).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-350))
        .force('center', d3.forceCenter(w / 2, h / 2))
        .force('collide', d3.forceCollide().radius(d => (d.proficiency || 0) * 5 + 18));

    graphSimulation = simulation;

    // 绘制边
    const link = g.append('g')
        .attr('stroke', '#444')
        .attr('stroke-opacity', 0.5)
        .attr('stroke-width', 1.2)
        .selectAll('line')
        .data(data.edges)
        .join('line');

    // 绘制节点
    const node = g.append('g')
        .selectAll('circle')
        .data(data.nodes)
        .join('circle')
        .attr('r', d => d.is_category ? 6 : 8 + (d.proficiency || 0) * 5)
        .attr('fill', d => d.is_category ? '#555' : graphColor(d.group))
        .attr('stroke', d => d.is_category ? '#666' : '#fff')
        .attr('stroke-width', d => d.is_category ? 1 : 1.5)
        .attr('stroke-dasharray', d => d.is_category ? '4 2' : 'none')
        .attr('cursor', 'pointer')
        .call(drag(simulation));

    // 标签（默认隐藏，hover 显示）
    const label = g.append('g')
        .selectAll('text')
        .data(data.nodes)
        .join('text')
        .text(d => d.label)
        .attr('font-size', 10)
        .attr('fill', '#aaa')
        .attr('text-anchor', 'middle')
        .attr('dy', d => d.is_category ? -10 : -(d.proficiency || 0) * 5 - 14)
        .style('display', 'none')
        .style('pointer-events', 'none');

    // Tooltip
    const tooltip = d3.select('#graph-tooltip');

    node.on('mouseenter', (event, d) => {
        label.filter(l => l.id === d.id).style('display', 'block');
        tooltip.style('display', 'block')
            .html(`<strong>${d.label}</strong><br>熟练度: ${d.proficiency || '-'}/5<br>分类: ${d.group || '未分类'}`)
            .style('left', (event.pageX + 12) + 'px')
            .style('top', (event.pageY - 12) + 'px');
    });
    node.on('mousemove', (event) => {
        tooltip.style('left', (event.pageX + 12) + 'px')
            .style('top', (event.pageY - 12) + 'px');
    });
    node.on('mouseleave', (event, d) => {
        label.filter(l => l.id === d.id).style('display', 'none');
        tooltip.style('display', 'none');
    });

    // 点击节点: 高亮关联节点
    node.on('click', (event, d) => {
        const connectedIds = new Set();
        connectedIds.add(d.id);
        data.edges.forEach(e => {
            if (e.from === d.id) connectedIds.add(e.to);
            if (e.to === d.id) connectedIds.add(e.from);
        });
        node.attr('opacity', n => connectedIds.has(n.id) ? 1 : 0.15);
        link.attr('opacity', e => (e.from === d.id || e.to === d.id) ? 1 : 0.05);
        label.style('display', n => connectedIds.has(n.id) ? 'block' : 'none');

        // 点击空白处恢复
        svg.on('click', (evt) => {
            if (evt.target === svg.node()) {
                node.attr('opacity', 1);
                link.attr('opacity', 0.5);
                label.style('display', 'none');
                svg.on('click', null);
            }
        });
    });

    // Tick 更新位置
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        node
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);
        label
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    });

    // 拖拽函数
    function drag(sim) {
        function dragstarted(event) {
            if (!event.active) sim.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        function dragended(event) {
            if (!event.active) sim.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        return d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended);
    }
}
```

#### Step 2: 添加图例渲染函数

在 `drawGraph` 函数之后添加：

```javascript
function renderLegend(groups) {
    const container = $('#graph-legend');
    if (!groups || groups.length === 0) {
        container.innerHTML = '';
        return;
    }
    let html = '';
    groups.forEach(g => {
        const color = graphColor(g);
        html += `<div class="legend-item" data-group="${escapeHtml(g)}" onclick="toggleLegendGroup(this)" title="点击切换显隐">
            <span class="legend-color" style="background:${color}"></span>
            ${escapeHtml(g)}
        </div>`;
    });
    container.innerHTML = html;
}

function toggleLegendGroup(el) {
    el.classList.toggle('hidden');
    const group = el.dataset.group;
    const hidden = el.classList.contains('hidden');
    if (graphSimulation) {
        d3.selectAll('#graph-svg-container circle')
            .filter(d => d.group === group && !d.is_category)
            .attr('opacity', hidden ? 0.15 : 1);
    }
}
```

#### Step 3: 绑定控制栏事件

在 `loadGraph` 函数之后添加控制栏事件绑定（放在 `initTabEvents` 或页面初始化中）：

```javascript
// 图谱控制栏事件
$('#graph-search').addEventListener('input', debounce(loadGraph, 300));
$('#graph-category').addEventListener('change', loadGraph);
$('#graph-level').addEventListener('input', function() {
    $('#level-val').textContent = this.value;
    loadGraph();
});
$('#graph-reset').addEventListener('click', function() {
    $('#graph-search').value = '';
    $('#graph-category').value = '';
    $('#graph-level').value = 0;
    $('#level-val').textContent = '0';
    loadGraph();
});
```

#### Step 4: 检查 `debounce` 是否已存在

在 `index.html` 中搜索 `function debounce`，若不存在，在通用工具函数区域添加：

```javascript
function debounce(fn, ms) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms);
    };
}
```

#### Step 5: 更新 resize 事件

替换原有的 resize 监听（第 887-889 行）：

```javascript
window.addEventListener('resize', () => {
    if (STATE.currentTab === 'graph') loadGraph();
});
```

保持不变，逻辑一致。

#### Step 6: 提交

```bash
git add src/web/templates/index.html
git commit -m "feat: D3.js 力导向图谱 — 布局/zoom/hover/点击高亮/图例"
```

---

### Task 4: 前端列表按分类折叠

**Files:**
- Modify: `src/web/templates/index.html:868-885`

#### Step 1: 重写 `renderGraphList()`

替换 `index.html` 中第 868-885 行：

```javascript
function renderGraphList(nodes) {
    const container = $('#graph-list');
    if (nodes.length === 0) {
        container.innerHTML = '';
        return;
    }

    // 按 group 分组
    const groups = {};
    const ungrouped = [];
    nodes.forEach(node => {
        const g = node.group || '未分类';
        if (!groups[g]) groups[g] = [];
        groups[g].push(node);
    });

    let html = '<h3 style="margin:16px 0 10px;">知识点列表</h3>';
    const sortedGroups = Object.keys(groups).sort();

    sortedGroups.forEach(groupName => {
        const items = groups[groupName];
        html += `<div class="collapse-group">`;
        html += `<div class="collapse-header" onclick="toggleCollapse(this)">
            <span class="arrow">▼</span>
            ${escapeHtml(groupName)}
            <span class="count">${items.length} 项</span>
        </div>`;
        html += `<div class="collapse-body">`;
        items.forEach(node => {
            const levelText = node.proficiency >= 5 ? '掌握' : node.proficiency >= 3 ? '熟练' : '了解';
            const levelClass = node.proficiency >= 5 ? 'high' : node.proficiency >= 3 ? 'mid' : 'low';
            html += `<div class="card">
                <div class="card-header">
                    <span class="card-title">${escapeHtml(node.label)}</span>
                    <span style="font-size:12px;color:#888;">${levelText} (${node.proficiency}/5)</span>
                </div>
                <div class="prog-bar"><div class="prog-fill ${levelClass}" style="width:${node.proficiency * 20}%"></div></div>
            </div>`;
        });
        html += `</div></div>`;
    });

    container.innerHTML = html;
}

function toggleCollapse(header) {
    const group = header.parentElement;
    group.classList.toggle('collapsed');
    const body = group.querySelector('.collapse-body');
    body.classList.toggle('collapsed');
}
```

#### Step 2: 提交

```bash
git add src/web/templates/index.html
git commit -m "feat: 图谱列表按分类折叠显示"
```

---

### Task 5: 端到端验证

#### Step 1: 启动开发服务器

```bash
python run.py
```

#### Step 2: 手动验证清单

在浏览器中打开应用，切换到「图谱」Tab：

- [ ] 节点由 D3 力导向布局渲染，自动扩散排列，不重叠
- [ ] 滚轮缩放图谱，鼠标拖拽平移画布
- [ ] 节点可拖拽移动
- [ ] Hover 节点显示 tooltip（知识点名、熟练度、分类）
- [ ] 点击节点高亮其关联节点和边，其余半透明
- [ ] 点击空白处取消高亮
- [ ] 图例显示分类颜色，点击图例项切换该分类显隐
- [ ] 输入搜索关键词，图谱和列表同步过滤
- [ ] 分类下拉筛选，熟练度滑块过滤
- [ ] 重置按钮恢复全量展示
- [ ] 列表按分类折叠，点击组头展开/收起

#### Step 3: 运行后端测试

```bash
python -m pytest tests/test_graph_api.py -v
```

预期：全部 8 个测试通过。

#### Step 4: 运行全部测试确保无回归

```bash
python -m pytest tests/ -v
```

预期：所有已有测试仍通过，无回归。

#### Step 5: 提交

```bash
git add -A
git commit -m "test: 知识图谱 API 测试 + 端到端验证通过"
```

---

## 自检清单

- [x] **Spec 覆盖**：后端筛选参数（Task 1）、D3 力导向图（Task 3）、缩放平移（Task 3）、hover tooltip（Task 3）、点击高亮（Task 3）、图例（Task 3）、控制栏（Task 2）、折叠列表（Task 4）
- [x] **无占位符**：所有步骤包含完整代码，无 TBD/TODO
- [x] **类型一致性**：`graphColor`、`graphSimulation`、`graphData` 变量在 Task 3 定义，Task 3 Step 2/3 引用，一致
