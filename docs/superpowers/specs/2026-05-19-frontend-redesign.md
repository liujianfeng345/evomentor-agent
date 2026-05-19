# 前端界面美化 — 设计文档

日期：2026-05-19

## 需求概述

在现有单文件 HTML 架构基础上，通过 CSS 重构美化前端界面。不动 JS 逻辑，只改样式和配色。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 改造方式 | CSS 美化现有界面 | 改动最小、不引入新依赖、风险可控 |
| 视觉风格 | 极简白色风 | 清爽专业、阅读体验好 |
| 布局结构 | 保持侧边栏 + 内容区 | 熟悉感保留、改动范围可控 |
| 主色调 | `#6366f1` 紫蓝 | 辨识度高、与白底搭配柔和 |

## 配色系统

| 角色 | 颜色值 | 用途 |
|------|--------|------|
| 页面背景 | `#ffffff` / `#f8fafc` | 主背景 |
| 侧边栏背景 | `#f8fafc` | 侧边栏底色 |
| 主色调 | `#6366f1` | 按钮、链接、激活态 |
| 主色调 hover | `#4f46e5` | 按钮悬停 |
| 用户消息气泡 | `#6366f1`（背景）/ `#ffffff`（文字） | 发送消息 |
| 助手消息气泡 | `#f8fafc`（背景）/ `#334155`（文字） | 接收消息 |
| 边框色 | `#e2e8f0` | 分割线、卡片边框 |
| 卡片背景 | `#ffffff` | 卡片底色 |
| 输入区背景 | `#f8fafc` | 输入框/搜索栏 |
| 标题文字 | `#1e293b` | 主标题 |
| 正文文字 | `#334155` | 正文内容 |
| 辅助文字 | `#94a3b8` | 时间戳、元信息 |
| 弱化文字 | `#cbd5e1` | placeholder |
| 成功 | `#10b981` | 成功状态 |
| 警告 | `#f59e0b` | 待处理/运行中 |
| 错误 | `#ef4444` | 失败状态 |

## 字体系统

- 系统字体栈：`-apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif`
- 代码字体：`'JetBrains Mono', 'Fira Code', 'Consolas', monospace`（CDN 引入 JetBrains Mono）

## 圆角规范

| 元素 | 圆角 |
|------|------|
| 按钮 / 输入框 / Badge | `8px` |
| 卡片 / 面板 | `12px` |
| 消息气泡（用户） | `16px 16px 4px 16px` |
| 消息气泡（助手） | `4px 16px 16px 16px` |
| 输入框容器 | `24px`（胶囊形） |

## 组件设计

### 1. 全局

- body 背景 `#ffffff`
- 全局字体大小 14px，行高 1.6
- 移除所有原有暗色背景

### 2. Header（顶部栏）

- 背景 `#ffffff`，底部 1px `#e2e8f0` 边框
- 标题 "Evomentor" 字号 18px，粗体 `#1e293b`
- 当前 Tab 标签用 `#6366f1` 小字
- 侧边栏切换按钮：图标按钮，hover 变灰

### 3. 侧边栏

**折叠态（56px 宽）：**
- 背景 `#f8fafc`，右侧 1px `#e2e8f0` 边框
- 图标居中排列，上下间距 4px
- 激活项：`#eef2ff` 背景 + `#6366f1` 图标色 + 8px 圆角
- 非激活项：`#94a3b8` 图标色，hover 变 `#64748b`
- 展开按钮在顶部

**展开态（190px 宽）：**
- 顶部显示 "Evomentor" 标题
- 每项：16px 图标 + 14px 文字标签
- 激活项：`#eef2ff` 背景 + `#6366f1` 文字 + 粗体
- 非激活项：`#64748b` 文字，hover 背景 `#f1f5f9`
- 圆角 8px，左右各留 6px margin

### 4. 聊天区

**消息气泡：**
- 用户消息：`#6366f1` 背景、`#ffffff` 文字、右对齐、圆角偏右下
- 助手消息：带圆形头像（28px，`#6366f1` 渐变，显示 "E"）、`#f8fafc` 背景、`#1e293b` 文字、`#f1f5f9` 边框
- Markdown 内容样式：保留现有 h1-h4/code/pre/table/blockquote 样式，调整为白色主题配色
  - 标题：`#1e293b`
  - 行内代码：`#f1f5f9` 背景、`#e11d48` 文字色
  - 代码块：`#1e293b` 背景、`#e2e8f0` 文字
  - 引用块：`#6366f1` 左边框、`#f8fafc` 背景
  - 链接：`#6366f1`
  - 表格：`#e2e8f0` 边框、`#f8fafc` 表头

**输入区：**
- 胶囊形容器：`#f8fafc` 背景、`#e2e8f0` 边框、`border-radius: 24px`
- 输入框：无边框、`#334155` 文字、placeholder `#cbd5e1`
- 发送按钮：`#6366f1` 背景、白色文字、`border-radius: 20px`、hover `#4f46e5`
- 发送中：opacity 0.6、cursor not-allowed

**工具调用折叠面板：**
- `#f8fafc` 背景、`#e2e8f0` 边框、8px 圆角
- 摘要文字 `#64748b`
- 运行中步骤：`#f59e0b` 色
- 完成步骤：`#10b981` 色
- 失败步骤：`#ef4444` 色

### 5. 卡片（报告/邮件/记忆/Skills）

- 白底 `#ffffff`、`#e2e8f0` 边框、12px 圆角
- padding: 14px 16px、间距 8px
- hover：边框变 `#6366f1`、微阴影 `0 2px 8px rgba(0,0,0,0.04)`
- 展开后详情区有顶部分割线

### 6. 工具栏

- 搜索框：`#f8fafc` 背景、`#e2e8f0` 边框、10px 圆角、左侧搜索图标
- 下拉框：同上样式
- 主按钮：`#6366f1` 背景、白色文字、10px 圆角
- 次要按钮：`#f1f5f9` 背景、`#334155` 文字

### 7. Badge

- GitHub：`#eef2ff` 背景、`#6366f1` 文字
- Research：`#ecfdf5` 背景、`#10b981` 文字
- 对话：`#f8fafc` 背景、`#64748b` 文字
- 经验：`#fef3c7` 背景、`#d97706` 文字
- 决策：`#ede9fe` 背景、`#7c3aed` 文字

### 8. Toast / Modal

- Toast：`#1e293b` 背景、白色文字、12px 圆角、顶部居中
- 成功 Toast：`#10b981` 背景
- Modal overlay：`rgba(0,0,0,0.4)` 半透明黑
- Modal 盒子：白底、16px 圆角、`#e2e8f0` 边框

### 9. 知识图谱

- Canvas：白底、`#e2e8f0` 边框、12px 圆角
- 节点颜色按掌握度：`#6366f1`（5）、`#a5b4fc`（3-4）、`#e2e8f0`（1-2）

### 10. 状态指示

- 已发送：`#10b981` 圆点
- 待发：`#f59e0b` 圆点
- 失败：`#ef4444` 圆点

## 实现要点

### CSS 组织

将 CSS 从内联 `<style>` 提取为独立文件 `src/web/static/style.css`：

```
src/web/static/
  style.css          # 全部 CSS
```

在 HTML 中通过 `<link>` 引用：
```html
<link rel="stylesheet" href="/static/style.css">
```

同时引入 JetBrains Mono 字体 CDN：
```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap">
```

### CSS 结构

```css
/* 1. Reset & Base */
/* 2. Layout (body, #main-wrap, header, #sidebar, #content) */
/* 3. Sidebar */
/* 4. Tab Panels */
/* 5. Chat (messages, bubbles, input, markdown, tool-steps) */
/* 6. Cards & Lists */
/* 7. Toolbar & Forms */
/* 8. Badges & Status */
/* 9. Knowledge Graph */
/* 10. Toast & Modal */
```

### 改造范围

- **改动**：`src/web/templates/index.html`（提取 CSS → 独立文件、加字体 CDN）
- **新增**：`src/web/static/style.css`（全部 CSS 约 350 行）
- **不改**：所有 JS 逻辑、HTML 结构（保持 DOM 结构不变，只改 class 样式）

### FastAPI 静态文件挂载

在 `src/web/app.py` 中确认已有 `app.mount("/static", StaticFiles(...))`，若没有则添加。

## 不变部分

- 全部 JavaScript 逻辑
- HTML DOM 结构
- 所有 API 端点
- 后端代码
- CDN 库引用（marked.js、highlight.js）位置不变

## 测试要点

1. 所有 6 个 Tab 切换正常
2. 聊天发送/接收/流式/工具面板正常
3. 报告/邮件/记忆/图谱/Skills 列表和交互正常
4. Toast 和 Modal 显示正常
5. 移动端响应式（min-width 兼容）
6. CDN 加载失败时降级到系统字体
