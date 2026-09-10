# 消防指挥系统 - 设计尺寸规范报告

> 版本：v1.0 | 生成日期：2026-05-31 | 基准分辨率：1920 × 1080

---

## 目录

1. [整体布局框架](#1-整体布局框架)
2. [各页面标准尺寸参数](#2-各页面标准尺寸参数)
3. [UI 组件尺寸规范](#3-ui-组件尺寸规范)
4. [响应式设计尺寸变化规则](#4-响应式设计尺寸变化规则)
5. [尺寸一致性原则与例外说明](#5-尺寸一致性原则与例外说明)

---

## 1. 整体布局框架

### 1.1 根容器（所有页面统一）

| 属性 | 值 | 说明 |
|------|-----|------|
| `width` | `100vw` | 占满视口宽度 |
| `height` | `100vh` | 占满视口高度 |
| `overflow` | `hidden` | **禁止任何方向滚动条** |
| `display` | `flex` | 纵向弹性布局 |
| `flex-direction` | `column` | 从上到下排列 |
| `background` | `linear-gradient(180deg, #0A0F1A 0%, #162035 100%)` | 深色渐变背景 |
| `font-family` | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif` | 系统无衬线字体栈 |

### 1.2 五区域固定布局模型

本项目采用统一的全屏 Bento 网格布局，所有页面（除 AppHeader 外）严格遵循以下五区域模型：

```
┌─────────────────────────────────────────────────────────────┐
│                     顶部状态条 (Top Bar)                      │  64px
├──────────┬───────────────────────────────────┬──────────────┤
│          │                                   │              │
│ 左侧面板  │          中央主区域                 │  右侧面板     │  flex:1
│ 320px    │          (Center Area)            │  320px       │
│          │                                   │              │
├──────────┴───────────────────────────────────┴──────────────┤
│                     底部操作条 (Bottom Bar)                   │  60-80px
└─────────────────────────────────────────────────────────────┘
```

### 1.3 各区域基础尺寸

| 区域 | 宽度 | 高度 | 折叠宽度 | 备注 |
|------|------|------|----------|------|
| **顶部状态条** | `100%` (横跨全屏) | `64px` | — | 固定高度，不可折叠 |
| **左侧面板** | `320px` | `flex: 1` (自适应) | `60px` | 可折叠，0.2s 过渡 |
| **中央主区域** | `flex: 1` (自适应) | `flex: 1` (自适应) | — | 禁止滚动 |
| **右侧面板** | `320px` | `flex: 1` (自适应) | `60px` | 可折叠，0.2s 过渡 |
| **底部操作条** | `100%` (横跨全屏) | `60px` | — | 固定高度 |
| **底部操作条 (时间轴)** | `100%` | `80px` | — | 仅 RealtimeMonitor |

---

## 2. 各页面标准尺寸参数

### 2.1 页面总览对比

| 页面 | 文件 | 顶部条 | 底部条 | 左侧面板 | 右侧面板 | 特殊说明 |
|------|------|--------|--------|----------|----------|----------|
| 指挥调度中心 | CommandCenter.vue | 64px | 60px | 320px/60px | 320px/60px | 中央：Mapbox 地图 |
| 灾情评估分析 | DisasterAssess.vue | 64px | 60px | 320px/60px | 320px/60px | 中央：ECharts 并排图表 |
| 应急路径规划 | EmergencyRoute.vue | 64px | — | 320px/60px | 320px/60px | 无底部条 |
| 物资人员调度 | ResourceDispatch.vue | 64px | — | 320px/60px | 320px/60px | 无底部条 |
| 实时火情监测 | RealtimeMonitor.vue | 64px | **80px** | 320px/60px | 320px/60px | 底部含时间轴 |
| 无人机调度 | UAVDispatch.vue | 64px | 60px | 320px/60px | 320px/60px | 中央：Mapbox + 视频 |
| 多源融合 | MultiSourceFusion.vue | 64px | — | 320px/60px | 320px/60px | 无底部条 |
| 火情预测 | FirePredict.vue | 64px | 60px | 320px/60px | 320px/60px | 底部含控制条 |

### 2.2 各页面顶部条间距

| 页面 | `gap` | `padding` | 胶囊 `padding` |
|------|-------|-----------|-----------------|
| CommandCenter | `14px` | `0 32px` | `8px 16px` |
| DisasterAssess | `14px` | `0 32px` | `8px 18px` |
| EmergencyRoute | `20px` | `0 32px` | `8px 20px` |
| ResourceDispatch | `20px` | `0 32px` | `8px 20px` |
| RealtimeMonitor | `14px` | `0 32px` | `8px 16px` |
| MultiSourceFusion | `20px` | `0 32px` | — |

### 2.3 各页面侧边面板间距

| 页面 | 面板 `padding` | 面板 `gap` | 卡片 `padding` |
|------|---------------|-----------|----------------|
| CommandCenter | `12px` | `10px` | `14px` |
| DisasterAssess | `12px` | `12px` | `16px` |
| EmergencyRoute | `12px` | `12px` | `16px` |
| ResourceDispatch | `12px` | `12px` | `16px` |
| RealtimeMonitor | `10px` | `10px` | `12px` |

---

## 3. UI 组件尺寸规范

### 3.1 顶部胶囊 (Capsule)

应用于所有页面的顶部状态条，展示核心指标。

#### 标准尺寸

| 属性 | 标准值 | 变体说明 |
|------|--------|----------|
| `padding` | `8px 16px` 或 `8px 18px` | 页面级差异（见 2.2） |
| `border-radius` | `40px` | **全圆角胶囊** |
| `gap` | `8px` | 图标与数字间距 |
| `border` | `1px solid rgba(255,255,255,0.12)` | 半透白边框 |
| `background` | `rgba(255,255,255,0.08)` | 半透毛玻璃 |
| `backdrop-filter` | `blur(10px)` | 毛玻璃模糊 |

#### 胶囊内部文字尺寸

| 元素 | 字号 | 字重 | 颜色 |
|------|------|------|------|
| `.cap-val` (大数字) | `22px` | `700` | 渐变（各胶囊颜色不同） |
| `.cap-val-sm` (小数字) | `16px` | `700` | `#e2e8f0` |
| `.cap-unit` (单位) | `12px` | `400` | `#94a3b8` |
| `.cap-label` (标签) | `10px` | `400` | `#64748b` |
| `.cap-sub` (副文字) | `10px` - `11px` | `400` | `#64748b` |
| `.cap-icon` (图标) | `16px` - `18px` | — | — |

#### 胶囊脉动动画

```css
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.5); }
}
```

#### 胶囊交互

| 交互 | 效果 |
|------|------|
| `:hover` | `border-color: rgba(255,255,255,0.25)` |
| `:active` | `transform: scale(0.97)` |

---

### 3.2 玻璃卡片 (Glass Card)

应用于所有页面侧边面板内部，是最基础的容器组件。

#### 标准尺寸

| 属性 | 标准值 | 紧凑模式 |
|------|--------|----------|
| `padding` | `14px` - `16px` | `8px` - `10px` |
| `border-radius` | `20px` | `14px` |
| `border` | `1px solid rgba(255,255,255,0.08)` | — |
| `background` | `rgba(20,28,40,0.7)` | — |
| `backdrop-filter` | `blur(16px)` | — |
| `box-shadow` | `0 8px 32px rgba(0,0,0,0.3)` | — |

#### 卡片标题

| 属性 | 标准值 | 紧凑模式 |
|------|--------|----------|
| `font-size` | `12px` - `13px` | `10px` - `11px` |
| `font-weight` | `600` | — |
| `margin-bottom` | `10px` - `12px` | `6px` - `8px` |

---

### 3.3 折叠按钮 (Collapse Button)

#### 标准尺寸

| 属性 | 值 |
|------|-----|
| `width` | `24px` |
| `height` | `48px` |
| `position` | `absolute`; `top: 50%`; `transform: translateY(-50%)` |
| `border-radius` (左侧面板) | `0 8px 8px 0` |
| `border-radius` (右侧面板) | `8px 0 0 8px` |

---

### 3.4 标签页 (Tabs)

#### 标签容器

| 属性 | 值 |
|------|-----|
| `display` | `flex` |
| `gap` | `4px` |
| `padding` | `4px` |
| `border-radius` | `12px` |
| `background` | `rgba(255,255,255,0.04)` |

#### 标签项

| 属性 | 值 |
|------|-----|
| `padding` | `8px 6px` |
| `border-radius` | `10px` |
| `font-size` | `12px` |
| `active background` | `rgba(96,165,250,0.2)` |
| `active color` | `#60a5fa` |

#### 标签内容区

| 属性 | 标准值 | 紧凑模式 |
|------|--------|----------|
| `padding` | `14px` - `16px` | `10px` |
| `border-radius` | `20px` | `14px` |
| `overflow` | `hidden` | — |

---

### 3.5 底部按钮 (Bottom Bar Button)

#### 标准尺寸

| 属性 | 值 |
|------|-----|
| `padding` | `8px 16px` |
| `border-radius` | `10px` |
| `border` | `1px solid rgba(255,255,255,0.1)` |
| `font-size` | `12px` |
| `gap` | `6px` |

#### 交互

| 交互 | 效果 |
|------|------|
| `:hover` | `background: rgba(96,165,250,0.15)` |
| `:active` | `transform: scale(0.96)` |

#### 紧急按钮变体

| 属性 | 值 |
|------|-----|
| `background` | `rgba(239,68,68,0.15)` |
| `border-color` | `rgba(239,68,68,0.3)` |
| `color` | `#f87171` |

---

### 3.6 悬浮抽屉 (Drawer)

#### 抽屉遮罩

| 属性 | 值 |
|------|-----|
| `position` | `fixed`; `inset: 0` |
| `background` | `rgba(0,0,0,0.4)` |
| `z-index` | `100` |

#### 抽屉内容

| 属性 | 值 |
|------|-----|
| `width` | `380px` |
| `height` | `100%` |
| `background` | `rgba(20,28,40,0.95)` |
| `border-left` | `1px solid rgba(255,255,255,0.08)` |
| `backdrop-filter` | `blur(12px)` |
| `transition` | `transform 0.25s ease` |

#### 抽屉进入/离开动画

| 状态 | 效果 |
|------|------|
| `drawer-enter-from` | `opacity: 0` |
| `drawer-leave-to` | `opacity: 0` |
| `drawer-enter-from .drawer-content` | `transform: translateX(100%)` |
| `drawer-leave-to .drawer-content` | `transform: translateX(100%)` |

#### 抽屉头部

| 属性 | 值 |
|------|-----|
| `padding` | `16px` |
| `border-bottom` | `1px solid rgba(255,255,255,0.06)` |

#### 关闭按钮

| 属性 | 值 |
|------|-----|
| `width` | `28px` |
| `height` | `28px` |
| `border-radius` | `8px` |

#### 抽屉内容区

| 属性 | 值 |
|------|-----|
| `padding` | `16px` |
| `overflow-y` | `auto` (抽屉内部可滚动) |

---

### 3.7 Toast 通知

#### 标准尺寸

| 属性 | 值 |
|------|-----|
| `position` | `fixed`; `top: 80px`; `right: 32px` |
| `padding` | `12px 20px` |
| `border-radius` | `14px` |
| `z-index` | `300` |

#### 动画

| 状态 | 效果 |
|------|------|
| `enter-from` | `opacity: 0; transform: translateX(40px)` |
| `leave-to` | `opacity: 0; transform: translateX(40px)` |
| `duration` | `0.3s ease` |

---

### 3.8 时间轴控制条 (Timeline) — 仅 RealtimeMonitor

#### 底部条

| 属性 | 值 |
|------|-----|
| `height` | `80px` |
| `padding` | `0 32px` |
| `gap` | `16px` |

#### 播放按钮

| 属性 | 值 |
|------|-----|
| `width` | `40px` |
| `height` | `40px` |
| `border-radius` | `50%` |
| `font-size` | `16px` |
| `:active` | `transform: scale(0.92)` |

#### 时间轴滑块

| 属性 | 值 |
|------|-----|
| `height` | `4px` |
| `background` | `rgba(255,255,255,0.08)` |
| `border-radius` | `2px` |

#### 滑块拖拽头

| 属性 | 值 |
|------|-----|
| `width` | `16px` |
| `height` | `16px` |
| `border-radius` | `50%` |
| `background` | `#60a5fa` |
| `box-shadow` | `0 0 12px rgba(96,165,250,0.5)` |

#### 时间气泡

| 属性 | 值 |
|------|-----|
| `padding` | `3px 10px` |
| `border-radius` | `8px` |
| `font-size` | `10px` |

---

### 3.9 更新标签 (Update Tag)

| 属性 | 值 |
|------|-----|
| `font-size` | `11px` |
| `color` | `#64748b` |

#### 刷新按钮

| 属性 | 值 |
|------|-----|
| `width` | `24px` |
| `height` | `24px` |
| `border-radius` | `6px` |
| `font-size` | `12px` |

---

### 3.10 详情链接 (Detail Link)

| 属性 | 值 |
|------|-----|
| `font-size` | `11px` - `12px` |
| `color` | `#60a5fa` |
| `padding` | `4px 0` |

---

### 3.11 折叠图标 (Collapsed Icons)

| 属性 | 值 |
|------|-----|
| `width` | `40px` |
| `height` | `40px` |
| `border-radius` | `12px` |
| `gap` | `16px` |
| `font-size` | `18px` |

---

### 3.12 操作按钮 (Action Button)

| 属性 | 值 |
|------|-----|
| `padding` | `10px` |
| `border-radius` | `14px` |
| `font-size` | `13px` (主) / `12px` (副) |
| `gap` | `8px` |
| `:active` | `transform: scale(0.97)` |

---

### 3.13 弹窗表单 (Form)

| 元素 | 属性 | 值 |
|------|------|-----|
| `.form-group` | `margin-bottom` | `14px` |
| `.fg-label` | `font-size` | `12px` |
| `.fg-input` / `.fg-select` | `padding` | `10px 12px` |
| | `border-radius` | `10px` |
| | `font-size` | `13px` |
| | `border` | `1px solid rgba(255,255,255,0.1)` |
| `.fg-submit` | `padding` | `12px` |
| | `border-radius` | `12px` |
| | `font-size` | `14px` |
| | `:hover` | `transform: scale(0.98)` |
| | `:active` | `transform: scale(0.95)` |

---

### 3.14 地图图层控制 (Map Layer Controls)

| 属性 | 值 |
|------|-----|
| `padding` | `7px 12px` - `8px 14px` |
| `border-radius` | `10px` |
| `font-size` | `11px` |
| `gap` | `4px` |

---

### 3.15 地图图例 (Map Legend)

| 属性 | 值 |
|------|-----|
| `padding` | `10px 14px` |
| `border-radius` | `12px` |
| `font-size` | `11px` |
| `gap` | `4px` |

---

### 3.16 KPI 四宫格 (KPI Grid)

| 属性 | 值 |
|------|-----|
| `grid-template-columns` | `1fr 1fr` |
| `gap` | `10px` |
| 单元格 `padding` | `10px` |
| 单元格 `border-radius` | `14px` |
| 数值 `font-size` | `20px` |
| 数值 `font-weight` | `700` |
| 标签 `font-size` | `10px` |

---

### 3.17 任务卡片 (Task Card)

| 属性 | 值 |
|------|-----|
| `padding` | `10px` |
| `border-radius` | `14px` |
| `gap` | `10px` |

#### 任务进度条

| 属性 | 值 |
|------|-----|
| `height` | `4px` |
| `border-radius` | `2px` |

#### 任务按钮

| 属性 | 值 |
|------|-----|
| `width` | `28px` |
| `height` | `28px` |
| `border-radius` | `8px` |
| `font-size` | `12px` |

---

### 3.18 视频监控缩略图 (Video Thumb)

| 属性 | 值 |
|------|-----|
| 预览区 `aspect-ratio` | `16 / 9` |
| 预览区 `height` (CommandCenter) | `100px` |
| 信息区 `padding` | `5px 6px` - `8px` |
| 名称 `font-size` | `9px` - `11px` |
| 状态 `font-size` | `8px` - `10px` |

---

### 3.19 人员部署列表 (Personnel List)

| 属性 | 值 |
|------|-----|
| `gap` | `6px` |
| 行 `padding` | `8px 10px` |
| 行 `border-radius` | `10px` |
| 状态圆点 `width/height` | `8px` |
| 通讯按钮 `width/height` | `24px` |
| 通讯按钮 `border-radius` | `6px` |

---

### 3.20 告警流 (Alert Stream)

| 属性 | 值 |
|------|-----|
| 容器 `height` | `120px` |
| `overflow` | `hidden` |
| 条目 `padding` | `5px 8px` |
| 条目 `border-radius` | `6px` |
| 条目 `font-size` | `10px` |
| 条目 `margin-bottom` | `3px` |
| 高优先级左边框 | `2px solid #ef4444` |
| 滚动动画时长 | `15s linear infinite` |

#### 告警角标

| 属性 | 值 |
|------|-----|
| `width` | `18px` |
| `height` | `18px` |
| `border-radius` | `50%` |
| `font-size` | `10px` |

---

### 3.21 AppHeader 导航栏

| 属性 | 值 |
|------|-----|
| `width` | `100%` |
| `height` | `56px` |
| `padding` | `0 20px` |
| 左侧 `min-width` | `220px` |
| 右侧 `min-width` | `220px` |
| 导航项 `padding` | `8px 14px` |
| 导航项 `gap` | `2px` - `10px` |
| 全屏按钮 `width/height` | `36px` |
| 状态圆点 `width/height` | `8px` |
| 时间 `font-size` | `12px` |

#### AppHeader 响应式变化

| 属性 | 标准值 | 小屏幕 |
|------|--------|--------|
| 导航项 `padding` | `8px 14px` | `8px 10px` |
| 导航项 `font-size` | — | `12px` |
| 导航项 `gap` | `10px` | `2px` |
| Logo 字号 | — | `16px` |
| 文字元素 | 显示 | `display: none` |

---

### 3.22 全局样式 (style.css)

| 选择器 | 属性 | 值 |
|--------|------|-----|
| `*` | `margin` | `0` |
| `*` | `padding` | `0` |
| `*` | `box-sizing` | `border-box` |
| `body` | `font-family` | `-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif` |
| `body` | `margin` | `0` |
| `body` | `padding` | `0` |
| `#app` | `width` | `100%` |
| `#app` | `height` | `100vh` |
| `#app` | `overflow` | `hidden` |
| `.app-layout` | `height` | `100vh` |
| `.app-layout` | `overflow` | `hidden` |
| `.app-layout` | `padding-top` | `56px` |
| `.page-container` | `height` | `calc(100vh - 56px)` |
| `.page-container` | `overflow` | `hidden` |
| `.full-page` | `width` | `100vw` |
| `.full-page` | `height` | `calc(100vh - 56px)` |
| `.full-page` | `overflow` | `hidden` |

---

## 4. 响应式设计尺寸变化规则

### 4.1 紧凑模式 (Compact Mode)

所有重设计的页面（CommandCenter、DisasterAssess、RealtimeMonitor）均内置紧凑模式，通过底部栏的"⊞ 紧凑"按钮激活。

#### 统一规则

| 组件 | 标准尺寸 | 紧凑尺寸 | 缩放比例 |
|------|----------|----------|----------|
| 顶部条高度 | `64px` | `52px` | ~81% |
| 底部条高度 | `60px` | `48px` | 80% |
| 底部条(时间轴) | `80px` | `64px` | 80% |
| 顶部条 `padding` | `0 32px` | `0 16px` | 50% |
| 顶部条 `gap` | `14px` | `8px` | ~57% |
| 底部条 `padding` | `0 32px` | `0 16px` | 50% |
| 侧边面板宽度 | `320px` | `260px` | ~81% |
| 侧边面板折叠宽度 | `60px` | `48px` | 80% |
| 侧边面板 `padding` | `10px`-`12px` | `6px`-`8px` | ~67% |
| 侧边面板 `gap` | `10px`-`12px` | `6px`-`8px` | ~67% |
| 玻璃卡片 `padding` | `14px`-`16px` | `8px`-`10px` | ~63% |
| 玻璃卡片 `border-radius` | `20px` | `14px` | 70% |
| 卡片标题 `font-size` | `12px`-`13px` | `10px`-`11px` | ~85% |
| 胶囊 `padding` | `8px 16px`-`8px 18px` | `6px 10px`-`6px 12px` | ~67% |
| 胶囊大数字 `font-size` | `22px` | `18px` | ~82% |
| 标签内容 `padding` | `14px`-`16px` | `10px` | ~71% |
| 页签内容 `border-radius` | `20px` | `14px` | 70% |

#### 页面特有紧凑规则

**CommandCenter**:
- `.kc-val` (KPI 数值): `20px` → `16px` (80%)
- `.kpi-cell` (KPI 单元格) `padding`: `10px` → `6px` (60%)
- `.vc-preview` (视频预览) `height`: `100px` → `70px` (70%)

**DisasterAssess**:
- `.grade-badge` `padding`: 默认 → `6px 14px`
- `.grade-badge` `font-size`: 默认 → `13px`
- `.gs-val` `font-size`: 默认 → `24px`
- `.mini-chart` `height`: `80px` → `60px` (75%)
- `.center-area` `flex-direction`: `row` → `column` (图表从并排变为堆叠)

**RealtimeMonitor**:
- `.wg-val` (气象数值) `font-size`: `18px` → `14px` (~78%)
- `.cap-val-sm` (小数字) `font-size`: `16px` → `13px` (~81%)
- `.tl-btn` (时间轴按钮) `width/height`: `40px` → `32px` (80%)
- `.tl-slider-track` `padding-top`: `20px` → `16px` (80%)

---

### 4.2 布局方向变化

| 页面 | 标准布局 | 紧凑模式 |
|------|----------|----------|
| DisasterAssess 中央图表 | 左右并排 (`flex-direction: row`) | 上下堆叠 (`flex-direction: column`) |
| 其他页面中央区域 | 无变化 (地图占满) | 无变化 |

---

### 4.3 过渡动画

所有尺寸变化均使用平滑过渡：

| 属性 | 时长 | 缓动函数 |
|------|------|----------|
| 面板宽度 | `0.2s` | `ease` |
| 抽屉滑入 | `0.25s` | `ease` |
| 抽屉透明度 | `0.2s` | `ease` |
| 标签页切换 | `0.15s` / `0.1s` | `ease` |
| Toast 通知 | `0.3s` | `ease` |

---

## 5. 尺寸一致性原则与例外说明

### 5.1 一致性原则

#### ✅ 严格一致（所有页面完全统一）

| 规则 | 说明 |
|------|------|
| 根容器 `100vw × 100vh` + `overflow: hidden` | 全屏无滚动是最核心约束 |
| `background: linear-gradient(180deg, #0A0F1A 0%, #162035 100%)` | 全局统一背景 |
| 顶部条高度 `64px` | 所有带顶部条的页面 |
| 侧边面板展开宽度 `320px` | 所有页面 |
| 侧边面板折叠宽度 `60px` (± 个别页面 `48px`) | 基本一致 |
| 胶囊 `border-radius: 40px` | 所有页面 |
| 玻璃卡片 `border-radius: 20px` | 所有页面 |
| 抽屉宽度 `380px` | 所有页面 |
| Toast 位置 `top: 80px; right: 32px` | 所有页面 |
| 折叠按钮 `24px × 48px` | 所有页面 |
| 面板过渡 `0.2s ease` | 所有页面 |

#### ⚠️ 页面级差异（允许在一定范围内变化）

| 规则 | 范围 | 差异原因 |
|------|------|----------|
| 底部条高度 | `60px` (标准) / `80px` (时间轴) | RealtimeMonitor 需要时间轴滑块空间 |
| 胶囊 `padding` | `8px 16px` ~ `8px 20px` | 适配不同数量和内容的胶囊 |
| 顶部条 `gap` | `14px` ~ `20px` | 页面胶囊数量不同：5个(14px) / 4个(20px) |
| 卡片 `padding` | `12px` ~ `16px` | 面板信息密度不同 |
| 面板 `padding` | `10px` ~ `12px` | 适配不同卡片数量 |
| 面板 `gap` | `10px` ~ `12px` | 同上 |

#### 🔧 无底部条页面

以下页面不包含底部条区域，中央区域直接延伸至底部：
- EmergencyRoute.vue（应急路径规划）
- ResourceDispatch.vue（物资人员调度）
- MultiSourceFusion.vue（多源融合）

### 5.2 例外情况说明

| 例外 | 涉及页面 | 原因 |
|------|----------|------|
| 底部条 80px | RealtimeMonitor | 时间轴播放器需要更大的垂直空间容纳滑块+气泡+标记 |
| 紧凑模式折叠宽度 48px | RealtimeMonitor、CommandCenter、DisasterAssess | 紧凑模式下 60px 过大，进一步压缩至 48px |
| 紧凑模式面板宽度 260px | 所有做过紧凑适配的页面 | 320px → 260px 保持信息可读性同时缩小 |
| DisasterAssess 中央图表方向切换 | DisasterAssess | 紧凑模式下并排图表宽度不足，自动切换为上下堆叠 |
| RealtimeMonitor 面板 `padding` 略小 (10px) | RealtimeMonitor | 右侧面板内容较多（火情列表+告警流+视频），需要更紧凑的间距 |
| EmergencyRoute/ResourceDispatch 无底部条 | 旧版页面 | 这些页面在较早的设计中未包含底部全局操作条 |

### 5.3 设计令牌（Design Tokens）建议

基于以上分析，建议提取以下设计令牌供全局统一管理：

```css
:root {
  /* 布局 */
  --layout-topbar-height: 64px;
  --layout-bottombar-height: 60px;
  --layout-bottombar-timeline-height: 80px;
  --layout-panel-width: 320px;
  --layout-panel-collapsed-width: 60px;
  --layout-compact-panel-width: 260px;
  --layout-compact-panel-collapsed-width: 48px;
  --layout-drawer-width: 380px;

  /* 间距 */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 12px;
  --spacing-lg: 16px;
  --spacing-xl: 20px;
  --spacing-2xl: 24px;
  --spacing-3xl: 32px;

  /* 圆角 */
  --radius-capsule: 40px;
  --radius-card: 20px;
  --radius-compact-card: 14px;
  --radius-button: 10px;
  --radius-tab: 10px;
  --radius-tag: 8px;
  --radius-dot: 50%;

  /* 字号 */
  --font-xs: 9px;
  --font-sm: 10px;
  --font-md: 12px;
  --font-lg: 14px;
  --font-xl: 16px;
  --font-2xl: 18px;
  --font-3xl: 22px;
  --font-4xl: 24px;

  /* 过渡 */
  --transition-panel: 0.2s ease;
  --transition-drawer: 0.25s ease;
  --transition-fade: 0.15s ease;
  --transition-toast: 0.3s ease;

  /* 玻璃效果 */
  --glass-blur: blur(16px);
  --glass-blur-light: blur(10px);
  --glass-blur-heavy: blur(12px);
  --glass-border: 1px solid rgba(255,255,255,0.08);
  --glass-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
```

---

## 附录 A：页面文件清单

| 文件 | 路径 | 设计状态 |
|------|------|----------|
| App.vue | `src/App.vue` | 全局布局 |
| style.css | `src/style.css` | 全局样式 |
| AppHeader.vue | `src/components/AppHeader.vue` | 导航栏组件 |
| CommandCenter.vue | `src/views/CommandCenter.vue` | ✅ 已重设计 |
| DisasterAssess.vue | `src/views/DisasterAssess.vue` | ✅ 已重设计 |
| EmergencyRoute.vue | `src/views/EmergencyRoute.vue` | ✅ 已重设计 |
| ResourceDispatch.vue | `src/views/ResourceDispatch.vue` | ✅ 已重设计 |
| RealtimeMonitor.vue | `src/views/RealtimeMonitor.vue` | ✅ 已重设计 |
| UAVDispatch.vue | `src/views/UAVDispatch.vue` | 部分重设计 |
| MultiSourceFusion.vue | `src/views/MultiSourceFusion.vue` | 部分重设计 |
| FirePredict.vue | `src/views/FirePredict.vue` | 部分重设计 |

---

## 附录 B：垂直空间分配计算

以 1920×1080 分辨率为例，主内容区可用高度：

```
视口高度:            1080px
- AppHeader:         -56px
- 页面顶部条:         -64px
- 页面底部条:         -60px (或 -80px 时间轴)
─────────────────────────────
主内容区可用高度:      900px (标准) / 880px (时间轴)
```

面板内部卡片高度约束（以 CommandCenter 为例，视口高度 900px）：

```
左侧面板:
  关键指标卡片:     ~140px (KPI 四宫格 2×2)
  任务调度卡片:     ~160px (2个任务)
  快速操作卡片:     ~120px (3个按钮)
  间距 (gap×2):     ~20px
  面板 padding:     ~24px
  ─────────────────────────
  总计:            ~464px  < 900px ✅ 安全

右侧面板:
  标签栏:           ~42px
  标签内容:         自适应 (flex: 1)
  总计:            填充剩余空间 ✅ 安全
```

---

# 第六章：界面坐标系统与组件位置详解

> 本章以分页形式详细阐述界面各组成部分的精确位置、坐标参数、相对布局关系及间距规范。所有数据均从源代码 CSS 中提取，与实现保持一致。

---

## 6.1 全局坐标系统

### 6.1.1 视口基准

系统采用浏览器视口作为绝对定位的参考坐标系。根容器 `#app-container` 占据整个视口。

```
┌──────────────────────────────────────────────── 1920px ────────────────────────────────────────────────┐
│                                                                                                        │
│  ┌────────────────────────────────────────── AppHeader ──────────────────────────────────────────────┐  │
│  │  height: 56px  │  z-index: 1000  │  position: relative  │  padding: 0 20px  │  width: 100%       │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                        │
│  ┌────────────────────────────────────── main-content (calc(100vh - 56px)) ──────────────────────────┐  │
│  │                                                                                                  │  │
│  │  ┌─────────────────── 页面区域 ───────────────────────────────────────────────────────────────┐  │  │
│  │  │  width: 100vw  │  height: 100vh  │  display: flex  │  flex-direction: column               │  │  │
│  │  │                                                                                            │  │  │
│  │  │  ┌─── Top Bar ───────────────────────────────────────────────────────────────────────┐    │  │  │
│  │  │  │  height: 64px  │  padding: 0 32px  │  gap: 14~20px  │  justify-content: center     │    │  │  │
│  │  │  └───────────────────────────────────────────────────────────────────────────────────┘    │  │  │
│  │  │                                                                                            │  │  │
│  │  │  ┌─── Main Content Area (flex: 1) ───────────────────────────────────────────────────┐    │  │  │
│  │  │  │                                                                                    │    │  │  │
│  │  │  │  ┌─ Left Panel ─┐   ┌────────── Center Map ──────────┐   ┌─ Right Panel ─┐       │    │  │  │
│  │  │  │  │  width: 320px │   │  flex: 1  │  margin: 10~12px 0 │   │  width: 320px  │       │    │  │  │
│  │  │  │  │  padding: 12px│   │  border-radius: 20px           │   │  padding: 12px │       │    │  │  │
│  │  │  │  │  gap: 10~12px │   │  position: relative            │   │  gap: 10~12px  │       │    │  │  │
│  │  │  │  │               │   │  overflow: hidden              │   │                │       │    │  │  │
│  │  │  │  └───────────────┘   └────────────────────────────────┘   └────────────────┘       │    │  │  │
│  │  │  │                                                                                    │    │  │  │
│  │  │  └────────────────────────────────────────────────────────────────────────────────────┘    │  │  │
│  │  │                                                                                            │  │  │
│  │  │  ┌─── Bottom Bar ────────────────────────────────────────────────────────────────────┐    │  │  │
│  │  │  │  height: 60px (Command) / 80px (Monitor) / 64px (Assess) / 60px (Route/Dispatch)  │    │  │  │
│  │  │  │  padding: 0 32px  │  justify-content: space-between                                │    │  │  │
│  │  │  └───────────────────────────────────────────────────────────────────────────────────┘    │  │  │
│  │  └────────────────────────────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.1.2 坐标原点与层级体系

| 层级 | 组件 | position | z-index | 坐标参考 |
|------|------|----------|---------|----------|
| 底层 | 地图容器 `.map-container` | `static`（默认） | auto | 父容器 `.center-area` |
| 第 1 层 | 面板折叠按钮 `.collapse-btn` | `absolute` | **10** | 父面板 `.side-panel` |
| 第 1 层 | 地图图层控制 `.map-layer-controls` | `absolute` | **10** | 父容器 `.center-area` |
| 第 1 层 | 地图图例 `.map-legend` | `absolute` | **10** | 父容器 `.center-area` |
| 第 1 层 | 地图控制按钮 `.map-controls-left/right` | `absolute` | **10** | 父容器 `.map-section` |
| 第 1 层 | 拾取提示 `.picking-hint` | `absolute` | **10** | 父容器 `.map-section` |
| 第 2 层 | 抽屉遮罩层 `.drawer-overlay` | `fixed` | **100** | 视口 (inset: 0) |
| 第 3 层 | 模态框 `.modal-overlay` | `fixed` | **200** | 视口 (inset: 0) |
| 第 4 层 | Toast 通知 `.toast-notification` | `fixed` | **300** | 视口 |
| 第 5 层 | 全屏提示 `.fullscreen-toast` | `fixed` | **9999** | 视口 |
| 顶层 | AppHeader | `relative` | **1000** | 文档流 |

---

## 6.2 全局导航栏 — AppHeader 位置详解

<div style="page-break-after: always;"></div>

### 6.2.1 整体位置

| 属性 | 值 | 说明 |
|------|-----|------|
| `position` | `relative` | 相对于文档流定位 |
| `z-index` | **1000** | 全局最高层级，确保始终可见 |
| `width` | `100%` | 占据视口全宽 |
| `height` | **56px** | 固定高度 |
| `padding` | `0 20px` | 左右各 20px 内边距 |
| `display` | `flex` | 弹性布局 |
| `justify-content` | `space-between` | 两端对齐（左/中/右三段） |
| `align-items` | `center` | 垂直居中 |

### 6.2.2 内部三段式布局

```
┌─────────────────────── AppHeader (100% × 56px) ───────────────────────────┐
│                                                                           │
│  ┌── header-left ──┐  ┌──── header-nav ──────┐  ┌── header-right ────┐  │
│  │  min-width: 220px│  │  flex: 1             │  │  min-width: 220px  │  │
│  │                  │  │  justify-content:    │  │  justify-content:  │  │
│  │  ┌── logo ─────┐ │  │     center           │  │     flex-end       │  │
│  │  │ gap: 10px    │ │  │                      │  │                    │  │
│  │  │ 🛡 消防指挥  │ │  │  ┌ nav-item ──────┐  │  │  gap: 16px        │  │
│  │  └─────────────┘ │  │  │ padding: 8px 14px│  │  │                    │  │
│  │                  │  │  │ gap: 6px         │  │  │  ▣ fullscreen     │  │
│  │                  │  │  │ gap(nav): 4px    │  │  │    36×36px       │  │
│  │                  │  │  └─────────────────┘  │  │  ● status-dot     │  │
│  │                  │  │  ...共 7 个导航项...  │  │    8×8px         │  │
│  └──────────────────┘  └──────────────────────┘  └────────────────────┘  │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

| 子区域 | 尺寸 | 间距 | 对齐方式 |
|--------|------|------|----------|
| `.header-left` | min-width: 220px | — | 靠左 |
| `.header-nav` | flex: 1（自动填充） | gap: 4px | 居中 |
| `.header-right` | min-width: 220px | gap: 16px | 靠右（flex-end） |

### 6.2.3 导航项激活指示器

```
┌── nav-item (active) ──┐
│  padding: 8px 14px    │  ← 点击区域
│  ██ 指挥中心           │
│  ════════════════════  │  ← ::after 伪元素
│    height: 2px         │     position: absolute
│    left: 14px          │     bottom: -1px（贴底）
│    right: 14px         │
└────────────────────────┘
```

---

## 6.3 页面顶部栏 — Top Bar 位置详解

<div style="page-break-after: always;"></div>

### 6.3.1 通用参数

所有页面共享的顶部栏基础结构：

| 属性 | 值 | 说明 |
|------|-----|------|
| `height` | **64px** | 固定高度 |
| `padding` | `0 32px` | 左右 32px |
| `display` | `flex` | 弹性布局 |
| `justify-content` | `center` | 水平居中 |
| `align-items` | `center` | 垂直居中 |
| `gap` | 14~20px（因页面而异） | 胶囊间距 |
| `background` | `rgba(20,28,40,0.9)` | 半透明深色背景 |
| `border-bottom` | `1px solid rgba(255,255,255,0.06)` | 底部分割线 |
| `backdrop-filter` | `blur(16px)` | 玻璃效果 |

### 6.3.2 各页面 Top Bar 间距差异

| 页面 | gap | 说明 |
|------|-----|------|
| CommandCenter | **14px** | 5 个胶囊 + 更新区域 |
| RealtimeMonitor | **14px** | 4 个胶囊 + 更新区域 |
| DisasterAssess | **16px** | 胶囊 + 更新区域 |
| EmergencyRoute | **20px** | 胶囊 + 重置按钮 |
| ResourceDispatch | **20px** | 胶囊 + 更新区域 |

### 6.3.3 胶囊组件（Capsule）位置与间距

```
┌────────────────── Capsule ──────────────────┐
│  padding: 8px 16px (Command/Monitor)        │
│          8px 18px (Assess)                  │
│          8px 20px (Route/Dispatch)          │
│  border-radius: 40px  ← 完全圆角胶囊形       │
│  gap: 8~10px  ← 内部元素间距                │
│  position: relative  ← 为脉冲点提供定位参考   │
│                                              │
│  ┌─ cap-icon ─┐ ┌─ cap-data ──┐ ┌─ cap-sub ─┐
│  │  font: 16px │ │  gap: 3px   │ │ font: 10px │
│  │  🔥         │ │  687  ℃     │ │ 火线温度   │
│  └─────────────┘ └─────────────┘ └───────────┘
│                                              │
│  ★ cap-pulse (position: absolute)            │
│    top: 6px  │  right: 10px                  │
│    width: 8px  │  height: 8px                │
│    border-radius: 50%                        │
└──────────────────────────────────────────────┘
```

| 子元素 | 定位方式 | 尺寸 | 间距 |
|--------|----------|------|------|
| `.cap-icon` | 普通流 | font-size: 16px | — |
| `.cap-data` | flex（内含 `.cap-val` + `.cap-unit`） | gap: 3px, align-items: baseline | — |
| `.cap-val` | 普通流 | font-size: 22px (Command) / 24px (Monitor) | — |
| `.cap-unit` | 普通流 | font-size: 12px | — |
| `.cap-sub` / `.cap-label` | 普通流 | font-size: 10px | — |
| `.cap-pulse` | **absolute** | 8×8px | top: 6px, right: 10px |

### 6.3.4 右上角更新区域

```
┌── top-right ────────────────────────────────┐
│  margin-left: auto  ← 自动推到最右侧         │
│  gap: 10px                                   │
│                                              │
│  ⚠️ alert-dot    ┌─ update-tag ───────────┐ │
│  (条件显示)      │ gap: 6px               │ │
│                  │ 数据更新：14:38   [↻]   │ │
│                  │           └─ ut-refresh  │ │
│                  │              24×24px     │ │
│                  └─────────────────────────┘ │
└──────────────────────────────────────────────┘
```

| 元素 | 定位方式 | 尺寸 | 间距 |
|------|----------|------|------|
| `.top-right` | flex, margin-left: auto | — | gap: 10px |
| `.alert-dot` | 普通流 | font-size: 16px | — |
| `.update-tag` | flex | — | gap: 6px |
| `.ut-refresh` | flex 居中 | 24×24px, border-radius: 6px | — |

---

## 6.4 主内容区 — Main Content 布局详解

<div style="page-break-after: always;"></div>

### 6.4.1 通用结构

```
┌────────────────────── main-content (flex: 1, min-height: 0) ──────────────────────┐
│                                                                                    │
│  ┌─ Left Panel ────┐  ┌──────────── Center Area ────────────┐  ┌─ Right Panel ───┐│
│  │                  │  │                                     │  │                 ││
│  │ width: 320px     │  │ flex: 1                             │  │ width: 320px    ││
│  │ position:        │  │ position: relative                  │  │ position:       ││
│  │   relative       │  │ margin: 10~12px 0                   │  │   relative      ││
│  │ padding: 10~12px │  │ border-radius: 20px                 │  │ padding: 10~12px││
│  │ gap: 10~12px     │  │ overflow: hidden                    │  │ gap: 10~12px    ││
│  │ flex-direction:  │  │ border: 1px solid                   │  │ flex-direction: ││
│  │   column         │  │   rgba(255,255,255,0.08)            │  │   column        ││
│  │ overflow: hidden │  │                                     │  │ overflow: hidden││
│  │                  │  │ ┌ map-container ──────────────────┐ │  │                 ││
│  │                  │  │ │ width: 100%, height: 100%       │ │  │                 ││
│  │                  │  │ └─────────────────────────────────┘ │  │                 ││
│  │                  │  │                                     │  │                 ││
│  │                  │  │ ┌ map-layer-controls ────────────┐  │  │                 ││
│  │                  │  │ │ position: absolute              │  │  │                 ││
│  │                  │  │ │ top: 12px, left: 12px           │  │  │                 ││
│  │                  │  │ │ z-index: 10                     │  │  │                 ││
│  │                  │  │ └─────────────────────────────────┘  │  │                 ││
│  │                  │  │                                     │  │                 ││
│  │                  │  │ ┌ map-legend ────────────────────┐  │  │                 ││
│  │                  │  │ │ position: absolute              │  │  │                 ││
│  │                  │  │ │ bottom: 12px, right: 12px       │  │  │                 ││
│  │                  │  │ │ z-index: 10                     │  │  │                 ││
│  │                  │  │ └─────────────────────────────────┘  │  │                 ││
│  └──────────────────┘  └─────────────────────────────────────┘  └─────────────────┘│
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.4.2 各页面主内容区间距差异

| 页面 | 面板 padding | 面板 gap | 中心区 margin | 面板宽度 |
|------|-------------|----------|--------------|----------|
| CommandCenter | 12px | 10px | 12px 0 | 320px |
| RealtimeMonitor | 10px | 10px | 10px 0 | 320px |
| DisasterAssess | 12px | 12px | 12px 0（独立 gap: 12px） | 320px |
| EmergencyRoute | 12px | 12px | — | 320px |
| ResourceDispatch | 12px | 12px | — | 320px |

---

## 6.5 侧边面板 — Side Panel 位置详解

<div style="page-break-after: always;"></div>

### 6.5.1 面板折叠按钮

折叠按钮是面板中唯一的绝对定位元素，垂直居中于面板边缘。

```
┌─ Left Panel (展开) ───────────────┐  ┌─ Left Panel (折叠) ─┐
│                                   │  │                      │
│  ┌─ glass-card ────────────────┐  │  │      ┌─ ico ─┐      │
│  │ ...                         │  │  │      │  40×40 │      │
│  └─────────────────────────────┘  │  │      └────────┘      │
│                                   │  │                      │
│  ┌─ glass-card ────────────────┐  │  │      ┌─ ico ─┐      │
│  │ ...                         │  │  │      │  40×40 │      │
│  └─────────────────────────────┘  │  │      └────────┘      │
│                             ┌──┐  │  │                      │
│                             │◀─│  │  │   gap: 16px          │
│                             └──┘  │  │   padding-top: 24px  │
│  width: 320px                    │  │   width: 60px         │
│  padding: 12px                   │  │   padding: 12px 8px   │
└───────────────────────────────────┘  └──────────────────────┘
```

| 属性 | 左侧面板 | 右侧面板 |
|------|---------|----------|
| 按钮位置 | `right: 0`（贴右边缘） | `left: 0`（贴左边缘） |
| 垂直居中 | `top: 50%` + `transform: translateY(-50%)` | 同左 |
| 按钮尺寸 | 24×48px | 24×48px |
| 圆角 | `border-radius: 0 8px 8px 0`（右侧圆角） | `border-radius: 8px 0 0 8px`（左侧圆角） |
| 层级 | `z-index: 10` | `z-index: 10` |

### 6.5.2 折叠状态图标

| 属性 | 值 |
|------|-----|
| `.collapsed-icons` | `display: flex; flex-direction: column; gap: 16px; align-items: center; padding-top: 24px` |
| `.ico-item` | `width: 40px; height: 40px; border-radius: 12px` |
| 折叠面板宽度 | `60px`（Command/Monitor）/ `48px`（compact 模式） |

### 6.5.3 玻璃卡片（Glass Card）内部间距

```
┌────────── glass-card ─────────────────┐
│  padding: 12~16px                     │
│  border-radius: 20px                  │
│  border: 1px solid rgba(255,255,255,  │
│          0.08)                        │
│                                       │
│  ┌─ card-title ────────────────────┐  │
│  │  font-size: 12~13px             │  │
│  │  margin-bottom: 10~14px         │  │
│  └─────────────────────────────────┘  │
│                                       │
│  ┌─ 卡片内容区 ────────────────────┐  │
│  │  (KPI Grid / 任务列表 / 表格等)  │  │
│  │  gap: 8~10px                    │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

| 页面 | 卡片 padding | 标题 margin-bottom | 内容 gap |
|------|-------------|-------------------|----------|
| CommandCenter | 14px | 12px | 10px |
| RealtimeMonitor | 12px | 10px | 8px |
| DisasterAssess | 16px | 14px | 12px |
| EmergencyRoute | 16px | 14px | 8~12px |
| ResourceDispatch | 16px | 14px | 10~12px |

---

## 6.6 中心区域 — 地图叠加层位置详解

<div style="page-break-after: always;"></div>

### 6.6.1 图层控制按钮（Map Layer Controls）

位于地图左上角，绝对定位叠加在地图上方。

```
┌─── Center Area ──────────────────────────────────────────────┐
│                                                               │
│  ┌─ map-layer-controls ──┐                                   │
│  │ position: absolute     │                                   │
│  │ top: 12px              │                                   │
│  │ left: 12px             │                                   │
│  │ z-index: 10            │                                   │
│  │ flex-direction: column │                                   │
│  │ gap: 4px               │                                   │
│  │                         │                                  │
│  │  ┌─ ml-btn ──────────┐ │                                  │
│  │  │ padding: 7~8px    │ │      ┌─── 地图容器 ───────────┐  │
│  │  │  12~14px          │ │      │  width: 100%           │  │
│  │  │ border-radius:    │ │      │  height: 100%          │  │
│  │  │  10px             │ │      │                         │  │
│  │  │ font-size: 11px   │ │      └────────────────────────┘  │
│  │  └───────────────────┘ │                                   │
│  │  ┌─ ml-btn ──────────┐ │                                   │
│  │  │ ...                │ │              ┌─ map-legend ────┐ │
│  │  └───────────────────┘ │              │ position:        │ │
│  │  ┌─ ml-btn ──────────┐ │              │   absolute       │ │
│  │  │ ...                │ │              │ bottom: 12px     │ │
│  │  └───────────────────┘ │              │ right: 12px      │ │
│  └────────────────────────┘              │ z-index: 10      │ │
│                                          │ padding: 10px    │ │
│                                          │   14px           │ │
│                                          │ gap: 4px         │ │
│                                          └──────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

| 元素 | 定位 | 坐标 | 层级 | 间距 |
|------|------|------|------|------|
| `.map-layer-controls` | absolute | top: 12px, left: 12px | z-index: 10 | 内部 gap: 4px |
| `.map-legend` | absolute | bottom: 12px, right: 12px | z-index: 10 | padding: 10px 14px, gap: 4px |
| `.ml-btn` | 普通流 | — | — | padding: 7~8px 12~14px |
| `.ml-dot` | 普通流 | — | — | 8×8px, border-radius: 50% |

### 6.6.2 图例项（Legend Item）

| 属性 | 值 |
|------|-----|
| `.ml-item` | `display: flex; align-items: center; gap: 6px` |
| `.ml-dot` | `width: 8px; height: 8px; border-radius: 50%` |
| `.ml-area` (CommandCenter) | `width: 12px; height: 8px; border-radius: 2px` |
| `.ml-line` (RealtimeMonitor) | `width: 12px; height: 2px; border-radius: 1px` |

### 6.6.3 地图控制按钮（EmergencyRoute / ResourceDispatch）

这两个页面使用 `.map-section` 作为地图容器，控制按钮位于独立区域。

```
┌─── map-section (flex: 7~8, position: relative) ─────────────────────────────┐
│                                                                              │
│  ┌─ map-controls-left ──┐                    ┌─ map-controls-right ───────┐ │
│  │ position: absolute    │                    │ position: absolute          │ │
│  │ top: 16px, left: 16px │                    │ top: 16px, right: 16px      │ │
│  │ z-index: 10           │                    │ z-index: 10                 │ │
│  │ flex-direction: column│                    │ flex-direction: column      │ │
│  │ gap: 6px              │                    │ gap: 6px                    │ │
│  │                        │                    │                             │ │
│  │ ┌ map-ctrl-btn ─────┐ │                    │ ┌ map-ctrl-btn ───────────┐ │ │
│  │ │ padding: 8px 14px │ │                    │ │ padding: 8px 14px       │ │ │
│  │ └───────────────────┘ │                    │ └─────────────────────────┘ │ │
│  └───────────────────────┘                    └─────────────────────────────┘ │
│                                                                              │
│  ┌─ picking-hint (条件显示) ───────────────────────────────────────────────┐ │
│  │ position: absolute  │  bottom: 16px  │  left: 50%                       │ │
│  │ transform: translateX(-50%)  │  z-index: 10                             │ │
│  │ padding: 10px 20px  │  gap: 12px                                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

| 元素 | 定位 | 坐标 | 层级 | 说明 |
|------|------|------|------|------|
| `.map-controls-left` | absolute | top: 16px, left: 16px | z-index: 10 | EmergencyRoute / ResourceDispatch |
| `.map-controls-right` | absolute | top: 16px, right: 16px | z-index: 10 | EmergencyRoute / ResourceDispatch |
| `.picking-hint` | absolute | bottom: 16px, left: 50% | z-index: 10 | 仅 EmergencyRoute，水平居中 |

---

## 6.7 底部栏 — Bottom Bar 位置详解

<div style="page-break-after: always;"></div>

### 6.7.1 各页面底部栏参数对比

| 页面 | 高度 | 布局模式 | 关键元素 |
|------|------|----------|----------|
| **CommandCenter** | **60px** | `space-between` 三段式 | 紧急按钮 / 同步状态 / 操作按钮 |
| **RealtimeMonitor** | **80px** | `flex` + 时间轴 | 播放控制 / 时间轴滑块 / 摘要 |
| **DisasterAssess** | **64px** | `space-between` 三段式 | 时间选择 / 同步状态 / 操作按钮 |
| **EmergencyRoute** | **60px** | `space-between` 三段式 | 操作按钮 / 同步状态 / 操作按钮 |
| **ResourceDispatch** | **60px** | `space-between` 三段式 | 操作按钮 / 同步状态 / 操作按钮 |

### 6.7.2 CommandCenter 底部栏结构

```
┌────────────────────── bottom-bar (60px) ──────────────────────────────────────┐
│  padding: 0 32px  │  justify-content: space-between                           │
│                                                                               │
│  ┌─ bb-left ──────────┐  ┌─ bb-center ───┐  ┌─ bb-right ───────────────────┐ │
│  │ gap: 12px           │  │                │  │ gap: 12px                    │ │
│  │                     │  │  数据同步：14:38│  │                              │ │
│  │ [🚨 紧急呼叫]       │  │                │  │ [⊞ 紧凑] [🔄 刷新] [📥 导出] │ │
│  │ [📢 广播通知]       │  │                │  │                              │ │
│  └─────────────────────┘  └────────────────┘  └──────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┘
```

| 按钮元素 | 尺寸 | 间距 |
|----------|------|------|
| `.bb-btn` | padding: 8px 16px; border-radius: 10px | gap: 6px（内部图标与文字） |
| `.bb-icon` | font-size: 12px | — |
| `.bb-left / .bb-center / .bb-right` | — | gap: 12px |

### 6.7.3 RealtimeMonitor 底部栏（时间轴）结构

```
┌──────────────────────── bottom-bar (80px) ────────────────────────────────────────┐
│  padding: 0 32px  │  gap: 16px                                                   │
│                                                                                   │
│  ┌─ tl-controls ─┐  ┌─────────────── tl-slider-track ──────────────────────┐     │
│  │ gap: 8px      │  │ flex: 1  │  position: relative  │  padding-top: 20px │     │
│  │               │  │                                                       │     │
│  │  ┌─ tl-btn ─┐ │  │  ┌── tl-time-bubble ──────────────┐                  │     │
│  │  │ 40×40px  │ │  │  │ position: absolute; top: 0     │                  │     │
│  │  │ 圆形     │ │  │  │ transform: translateX(-50%)     │                  │     │
│  │  └──────────┘ │  │  │ padding: 3px 10px              │                  │     │
│  │               │  │  │ 16:00                          │                  │     │
│  │  ┌─ tl-btn ─┐ │  │  └────────────────────────────────┘                  │     │
│  │  │ 40×40px  │ │  │                                                       │     │
│  │  │ 圆形     │ │  │  ═══════════●══════════════════════  tl-slider (4px)  │     │
│  │  └──────────┘ │  │  12:00    14:00    16:00    18:00   tl-marks         │     │
│  └───────────────┘  └───────────────────────────────────────────────────────┘     │
│                                                                     ┌─ tl-summary ┐│
│                                                                     │ gap: 8px     ││
│                                                                     │ 过火面积...  ││
│                                                                     └──────────────┘│
└───────────────────────────────────────────────────────────────────────────────────┘
```

| 时间轴元素 | 定位 | 尺寸 | 间距 |
|------------|------|------|------|
| `.tl-controls` | flex | gap: 8px | — |
| `.tl-btn` | flex 居中 | 40×40px, border-radius: 50% | — |
| `.tl-slider-track` | flex: 1, position: relative | padding-top: 20px | — |
| `.tl-time-bubble` | **absolute**, top: 0 | padding: 3px 10px, font-size: 10px | — |
| `.tl-slider` | 普通流 | height: 4px, width: 100% | — |
| `.tl-slider::-webkit-slider-thumb` | — | 16×16px, border-radius: 50% | — |
| `.tl-marks` | flex, position: relative | margin-top: 4px, padding: 0 8px | — |
| `.tl-mark` | **absolute** | font-size: 9px | transform: translateX(-50%) |
| `.tl-summary` | flex | gap: 8px, font-size: 12px | — |

---

## 6.8 浮动层 — Toast / Drawer / Modal 位置详解

<div style="page-break-after: always;"></div>

### 6.8.1 Toast 通知

所有页面共享相同的 Toast 定位规范。

```
┌─────────────────────────────────────────── 视口 ───────────────────────────────────────────┐
│                                                                                            │
│                                                                                            │
│  ┌── AppHeader (56px) ─────────────────────────────────────────────────────────────────┐  │
│  └──────────────────────────────────────────────────────────────────────────────────────┘  │
│                                        ┌── toast-notification ──────────────────────┐      │
│  80px ← top                            │ position: fixed                            │      │
│                                        │ top: 80px, right: 32px                     │      │
│                                        │ z-index: 300                               │      │
│                                        │ padding: 12px 20px                         │      │
│                                        │ border-radius: 14px                        │      │
│                                        │ gap: 10px                                   │      │
│                                        │                                             │      │
│                                        │ ✓  数据已刷新                                │      │
│                                        └─────────────────────────────────────────────┘      │
│                                                                                            │
│                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

| 属性 | 值 | 说明 |
|------|-----|------|
| `position` | **fixed** | 相对于视口固定 |
| `top` | **80px** | AppHeader(56px) + 24px 间距 |
| `right` | **32px** | 与页面 padding 对齐 |
| `z-index` | **300** | 高于 Drawer(100) 和 Modal(200) |
| 动画 | `translateX(40px)` → 0 | 从右侧滑入 |

### 6.8.2 抽屉面板（Drawer）

所有页面共享相同的 Drawer 定位规范。

```
┌─────────────────────────────────────────── 视口 ───────────────────────────────────────────┐
│                                                                                            │
│  ┌── drawer-overlay ───────────────────────────────────────────────────────────────────┐  │
│  │  position: fixed  │  inset: 0  │  z-index: 100                                        │  │
│  │  background: rgba(0,0,0,0.4)  ← 半透明遮罩                                           │  │
│  │  justify-content: flex-end  ← 内容靠右                                               │  │
│  │                                                                                       │  │
│  │                                        ┌── drawer-content ────────────────────────┐   │  │
│  │                                        │  width: 380px                            │   │  │
│  │                                        │  height: 100%                            │   │  │
│  │                                        │  border-left: 1px solid                  │   │  │
│  │                                        │    rgba(255,255,255,0.08)                │   │  │
│  │                                        │                                          │   │  │
│  │                                        │  ┌─ drawer-header ───────────────────┐  │   │  │
│  │                                        │  │ padding: 16px                     │  │   │  │
│  │                                        │  │ justify-content: space-between    │  │   │  │
│  │                                        │  │ 全部任务调度           [✕] 28×28 │  │   │  │
│  │                                        │  └──────────────────────────────────┘  │   │  │
│  │                                        │                                          │   │  │
│  │                                        │  ┌─ drawer-body ────────────────────┐  │   │  │
│  │                                        │  │ flex: 1                          │  │   │  │
│  │                                        │  │ padding: 16px                    │  │   │  │
│  │                                        │  │ overflow-y: auto                 │  │   │  │
│  │                                        │  └──────────────────────────────────┘  │   │  │
│  │                                        └──────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

| 属性 | 值 | 说明 |
|------|-----|------|
| `.drawer-overlay` | `position: fixed; inset: 0; z-index: 100` | 全屏遮罩 |
| `.drawer-content` | `width: 380px; height: 100%` | 右侧面板 |
| `.drawer-header` | `padding: 16px` | 标题栏 |
| `.close-drawer` | `28×28px; border-radius: 8px` | 关闭按钮 |
| `.drawer-body` | `flex: 1; padding: 16px; overflow-y: auto` | 可滚动内容区 |
| 动画 | `translateX(100%)` → 0 | 从右侧滑入 |

### 6.8.3 模态框（Modal — 仅 EmergencyRoute）

```
┌─────────────────────────────────── 视口 ───────────────────────────────────┐
│                                                                            │
│  ┌── modal-overlay ────────────────────────────────────────────────────┐  │
│  │  position: fixed  │  inset: 0  │  z-index: 200                       │  │
│  │  align-items: center  │  justify-content: center                     │  │
│  │                                                                      │  │
│  │              ┌── modal-content ──────────────────┐                   │  │
│  │              │  width: 480px                     │                   │  │
│  │              │  max-height: 70vh                 │                   │  │
│  │              │  border-radius: 20px              │                   │  │
│  │              │                                   │                   │  │
│  │              │  ┌─ modal-header ──────────────┐ │                   │  │
│  │              │  │ padding: 16px 20px           │ │                   │  │
│  │              │  └──────────────────────────────┘ │                   │  │
│  │              │                                   │                   │  │
│  │              │  ┌─ modal-body ────────────────┐ │                   │  │
│  │              │  │ padding: 20px                │ │                   │  │
│  │              │  └──────────────────────────────┘ │                   │  │
│  │              │                                   │                   │  │
│  │              │  ┌─ confirm-actions ───────────┐ │                   │  │
│  │              │  │ gap: 10px                    │ │                   │  │
│  │              │  │ flex: 1 (each .ca-btn)       │ │                   │  │
│  │              │  └──────────────────────────────┘ │                   │  │
│  │              └───────────────────────────────────┘                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

| 属性 | 值 |
|------|-----|
| `.modal-overlay` | `position: fixed; inset: 0; z-index: 200` |
| `.modal-content` | `width: 480px; max-height: 70vh; border-radius: 20px` |
| `.modal-header` | `padding: 16px 20px` |
| `.modal-body` | `padding: 20px` |
| `.confirm-actions` | `display: flex; gap: 10px` |

---

## 6.9 各页面特殊布局差异

<div style="page-break-after: always;"></div>

### 6.9.1 CommandCenter 页面布局总览

```
┌─── CommandCenter ──────────────────────────────────────────────────────────────────────────┐
│  ┌─ top-bar (64px, gap: 14px) ──────────────────────────────────────────────────────────┐  │
│  │  [🔥 3起火点] [🛸 8架在线] [📦 12个] [👥 320人] [☀️ 26℃晴]  ⚠️ 数据更新：14:38 [↻] │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ main-content ────────────────────────────────────────────────────────────────────────┐  │
│  │ ┌─ left (320px) ───┐  ┌─ center (flex:1) ────────────┐  ┌─ right (320px) ──────────┐ │  │
│  │ │ glass-card       │  │ ┌ map-layer-controls ──────┐  │  │ tabs (gap: 4px)         │ │  │
│  │ │  关键指标 (2×2)  │  │ │ top:12px left:12px       │  │  │  [📹监控][👥部署][🌡️环境]│ │  │
│  │ │ glass-card       │  │ │ z-index:10               │  │  │                          │ │  │
│  │ │  当前任务调度     │  │ └──────────────────────────┘  │  │ tab-content              │ │  │
│  │ │ glass-card       │  │ ┌ map-legend ─────────────┐  │  │  padding: 14px           │ │  │
│  │ │  快速操作         │  │ │ bottom:12px right:12px  │  │  │  video-grid (2×2)       │ │  │
│  │ └──────────────────┘  │ │ z-index:10              │  │  └──────────────────────────┘ │  │
│  │                       │ └──────────────────────────┘  │                                │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ bottom-bar (60px) ───────────────────────────────────────────────────────────────────┐  │
│  │  [🚨紧急呼叫][📢广播通知]        数据同步：14:38        [⊞紧凑][🔄刷新][📥导出态势]     │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.9.2 RealtimeMonitor 页面布局总览

```
┌─── RealtimeMonitor ───────────────────────────────────────────────────────────────────────┐
│  ┌─ top-bar (64px, gap: 14px) ──────────────────────────────────────────────────────────┐  │
│  │  [🌡️ 687℃火线温度] [📐 12.3km²过火面积] [⚠️ 中风险] [🕐 15:23:08]  ⚠️ 更新：14:38  │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ main-content ────────────────────────────────────────────────────────────────────────┐  │
│  │ ┌─ left (320px) ────┐  ┌─ center (flex:1) ───────────────┐  ┌─ right (320px) ───────┐ │  │
│  │ │ weather-card      │  │ ┌ map-overlay-top ───────────┐  │  │ 高危火情列表           │ │  │
│  │ │  实时气象观测(3列) │  │ │ top:12px left:12px         │  │  │ 实时告警(滚动)         │ │  │
│  │ │ tabbed-card       │  │ │ z-index:10                 │  │  │   alert-stream: 120px  │ │  │
│  │ │  [火线][热力][环境]│  │ └────────────────────────────┘  │  │ 视频监控(3列)          │ │  │
│  │ │ 资源部署摘要(2×2) │  │ ┌ map-legend ────────────────┐  │  └────────────────────────┘ │  │
│  │ └───────────────────┘  │ │ bottom:12px right:12px     │  │                              │  │
│  │                        │ │ z-index:10                 │  │                              │  │
│  │                        │ └────────────────────────────┘  │                              │  │
│  └────────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ bottom-bar (80px) ───────────────────────────────────────────────────────────────────┐  │
│  │  [⏸][⟲]  ┌─────────── 16:00 ───────────┐  ═════●══════════════  过火面积：12.3km²  │  │
│  │           │ 12:00   14:00   16:00   18:00 │                      | 活跃火点：7处      │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.9.3 DisasterAssess 页面布局总览

```
┌─── DisasterAssess ────────────────────────────────────────────────────────────────────────┐
│  ┌─ top-bar (64px, gap: 16px) ──────────────────────────────────────────────────────────┐  │
│  │  [📊 灾害等级] [📐 影响范围] [⚠️ 风险指标] [📋 评估状态]     数据更新：14:38 [↻]    │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ main-content ────────────────────────────────────────────────────────────────────────┐  │
│  │ ┌─ left (320px) ────┐  ┌─ center (flex:1, gap: 12px) ────┐  ┌─ right (320px) ───────┐ │  │
│  │ │ 灾害等级评定       │  │ ┌ chart-panel (flex:1) ───────┐  │  │ tabs                  │ │  │
│  │ │ 影响范围分析       │  │ │ chart-header               │  │  │  [损失评估][应对措施]  │ │  │
│  │ │ 趋势变化           │  │ │ chart-body (flex:1)        │  │  │                       │ │  │
│  │ └───────────────────┘  │ └─────────────────────────────┘  │  │ tab-content            │ │  │
│  │                        │ ┌ chart-panel (flex:1) ───────┐  │  │  loss-items /          │ │  │
│  │                        │ │ chart-header               │  │  │  measure-list          │ │  │
│  │                        │ │ chart-body (flex:1)        │  │  └───────────────────────┘ │  │
│  │                        │ └─────────────────────────────┘  │                              │  │
│  └────────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ bottom-bar (64px) ───────────────────────────────────────────────────────────────────┐  │
│  │  [📅 时间选择]        数据同步：14:38        [📥 导出报告][🔄 刷新][📋 生成评估]       │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.9.4 EmergencyRoute 页面布局总览

```
┌─── EmergencyRoute ────────────────────────────────────────────────────────────────────────┐
│  ┌─ top-bar (64px, gap: 20px) ──────────────────────────────────────────────────────────┐  │
│  │  [🛣️ 路径规划] [🌡️ 26℃ 晴] [💨 3.4m/s] [⚠️ 风险等级] [💡 建议]    [🔄 重置]       │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ main-content ────────────────────────────────────────────────────────────────────────┐  │
│  │ ┌─ left (320px) ────┐  ┌─ center (flex:1) ───────────────────────┐  ┌─ right (320px) ┐ │  │
│  │ │ 路径类型选择       │  │ ┌ map-section (flex:7) ─────────────┐  │  │ tabs           │ │  │
│  │ │ 起终点输入         │  │ │ ┌ map-controls-left ───────────┐  │  │  路径方案       │ │  │
│  │ │ 高程预览           │  │ │ │ top:16px left:16px z:10     │  │  │  气象路段       │ │  │
│  │ └───────────────────┘  │ │ └──────────────────────────────┘  │  │  设施标注       │ │  │
│  │                        │ │ ┌ map-controls-right ──────────┐  │  │  风险评估       │ │  │
│  │                        │ │ │ top:16px right:16px z:10    │  │  └────────────────┘ │  │
│  │                        │ │ └──────────────────────────────┘  │                       │  │
│  │                        │ │ ┌ picking-hint ────────────────┐  │                       │  │
│  │                        │ │ │ bottom:16px left:50% z:10    │  │                       │  │
│  │                        │ │ └──────────────────────────────┘  │                       │  │
│  │                        │ └───────────────────────────────────┘  │                       │  │
│  │                        │ ┌ elevation-section (flex:3) ──────┐  │                       │  │
│  │                        │ │ elev-header + elev-chart(flex:1) │  │                       │  │
│  │                        │ └───────────────────────────────────┘  │                       │  │
│  └────────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ bottom-bar (60px) ───────────────────────────────────────────────────────────────────┐  │
│  │  [📋 方案对比][📥 导出]          数据同步：14:38          [✓ 确认路径][🔄 重新规划]    │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.9.5 ResourceDispatch 页面布局总览

```
┌─── ResourceDispatch ──────────────────────────────────────────────────────────────────────┐
│  ┌─ top-bar (64px, gap: 20px) ──────────────────────────────────────────────────────────┐  │
│  │  [🌡️ 26℃ 晴] [💨 风速] [📦 物资 12类] [⚠️ 告警 3条]     数据更新：14:38 [↻]      │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ main-content ────────────────────────────────────────────────────────────────────────┐  │
│  │ ┌─ left (320px) ────┐  ┌─ center (flex:1) ───────────────────┐  ┌─ right (320px) ───┐ │  │
│  │ │ 概览指标(2×2)     │  │ ┌ map-section (flex:8) ──────────┐  │  │ tabs              │ │  │
│  │ │ 物资清单          │  │ │ ┌ map-controls-left ────────┐  │  │  人员调度          │ │  │
│  │ │ 调度表单          │  │ │ │ top:16px left:16px z:10  │  │  │  任务进度          │ │  │
│  │ └───────────────────┘  │ │ └───────────────────────────┘  │  │  告警中心          │ │  │
│  │                        │ │ ┌ map-controls-right ───────┐  │  │  智能建议          │ │  │
│  │                        │ │ │ top:16px right:16px z:10 │  │  └───────────────────┘ │  │
│  │                        │ │ └───────────────────────────┘  │                          │  │
│  │                        │ └────────────────────────────────┘  │                          │  │
│  │                        │ ┌ trend-section (flex:2) ───────┐  │                          │  │
│  │                        │ │ trend-header + trend-chart    │  │                          │  │
│  │                        │ └────────────────────────────────┘  │                          │  │
│  └────────────────────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ bottom-bar (60px) ───────────────────────────────────────────────────────────────────┐  │
│  │  [📋 调度清单][📥 导出]          数据同步：14:38          [✓ 确认调度][🔄 重置]        │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6.10 紧凑模式位置变化

### 6.10.1 紧凑模式触发条件

通过 `.compact` 类在 `.command-container` / `.monitor-container` / `.assess-container` / `.route-container` / `.dispatch-container` 上切换。

### 6.10.2 紧凑模式尺寸变化表

| 组件 | 标准模式 | 紧凑模式 | 变化量 |
|------|---------|----------|--------|
| `.top-bar` height | 64px | **52px** | -12px |
| `.top-bar` padding | 0 32px | **0 16px** | -16px |
| `.top-bar` gap | 14~20px | **8px** | -6~12px |
| `.side-panel` width | 320px | **260px** | -60px |
| `.side-panel.collapsed` width | 60px | **48px** | -12px |
| `.side-panel` padding | 10~12px | **6~8px** | -4px |
| `.side-panel` gap | 10~12px | **6px** | -4~6px |
| `.glass-card` padding | 12~16px | **8~10px** | -4~6px |
| `.glass-card` border-radius | 20px | **14px** | -6px |
| `.card-title` font-size | 12~13px | **10~11px** | -2px |
| `.card-title` margin-bottom | 10~14px | **6~8px** | -4~6px |
| `.bottom-bar` height（Command） | 60px | **48px** | -12px |
| `.bottom-bar` height（Monitor） | 80px | **64px** | -16px |
| `.bottom-bar` padding | 0 32px | **0 16px** | -16px |
| `.capsule` padding | 8px 16~20px | **6px 10~12px** | -2~8px |
| `.cap-val` font-size | 22~24px | **18px** | -4~6px |
| `.vc-preview` height | 100px | **70px** | -30px |
| `.tab-content` padding | 14~16px | **10px** | -4~6px |
| `.tl-btn` size | 40×40px | **32×32px** | -8px |
| `.tl-slider-track` padding-top | 20px | **16px** | -4px |
| `.center-area`（DisasterAssess） | flex-direction: row | **flex-direction: column** | 布局方向改变 |

---

## 6.11 Z-Index 层级完整堆叠顺序

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Z-Index 层级堆叠（从低到高）                                                │
│                                                                             │
│  9999  ── .fullscreen-toast ───────────────── 全屏提示（仅 AppHeader）      │
│  1000  ── .app-header ──────────────────────── 全局导航栏                   │
│   300  ── .toast-notification ──────────────── Toast 通知                   │
│   200  ── .modal-overlay ───────────────────── 模态框（仅 EmergencyRoute）   │
│   100  ── .drawer-overlay ──────────────────── 抽屉面板遮罩                  │
│    10  ── .collapse-btn ────────────────────── 面板折叠按钮                  │
│    10  ── .map-layer-controls ──────────────── 地图图层控制                  │
│    10  ── .map-legend ──────────────────────── 地图图例                      │
│    10  ── .map-controls-left/right ─────────── 地图控制按钮                  │
│    10  ── .picking-hint ────────────────────── 拾取提示                      │
│     2  ── .tl-time-bubble ──────────────────── 时间轴气泡                    │
│   auto ── 所有普通流元素 ───────────────────── 默认层级                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6.12 间距规范速查表

### 6.12.1 面板内元素垂直间距

| 应用场景 | 间距值 | 来源 |
|----------|--------|------|
| 面板内卡片之间的 gap | 10~12px | `.side-panel` gap |
| 卡片内部 padding | 12~16px | `.glass-card` padding |
| 卡片标题与内容 | 10~14px | `.card-title` margin-bottom |
| 折叠图标间距 | 16px | `.collapsed-icons` gap |
| 折叠图标顶部偏移 | 24px | `.collapsed-icons` padding-top |

### 6.12.2 标签页（Tabs）内部间距

| 应用场景 | 间距值 | 说明 |
|----------|--------|------|
| `.tabs` 容器 padding | 4px | 内缩以容纳激活态背景 |
| `.tabs` 容器 margin-bottom | 10~12px | 与下方内容间距 |
| `.tab-item` 之间 gap | 4px | 标签项之间 |
| `.tab-item` 内部 gap | 6px | 图标与文字 |
| `.tab-item` padding | 8px 6px | 点击区域 |

### 6.12.3 底部栏按钮间距

| 应用场景 | 间距值 |
|----------|--------|
| `.bb-btn` 内部 gap（图标与文字） | 6px |
| `.bb-left / .bb-center / .bb-right` 之间 gap | 12px |
| `.bb-btn` padding | 8px 16px |

---

> **报告结束** — 本报告基于项目所有文件的实际 CSS 分析生成，所有数值均来自源代码。