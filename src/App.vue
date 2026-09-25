<template>
  <div id="app-container">
    <AppHeader />
    <div class="workspace" :class="{ 'dock-collapsed': dockCollapsed }">
      <AppSidebar />
      <main class="main-content"><router-view /></main>
      <button class="mobile-dock-toggle" type="button" @click="mobileOpen=!mobileOpen">{{ mobileOpen ? '关闭侧栏' : '详情 / 对话' }}</button>
      <aside class="workspace-dock" :class="{ open: mobileOpen, collapsed: dockCollapsed }" aria-label="业务信息与智能体对话">
        <div class="dock-header">
          <div class="dock-tabs" :class="{ single: isVerification }" role="tablist">
            <button v-if="!isVerification" role="tab" type="button" :aria-selected="activeTab==='business'" :class="{ active: activeTab==='business' }" @click="activeTab='business'">业务面板</button>
            <button role="tab" type="button" :aria-selected="activeTab==='chat'" :class="{ active: activeTab==='chat' }" @click="activeTab='chat'">智能体对话</button>
          </div>
          <button class="dock-collapse" type="button" :aria-label="dockCollapsed ? '展开右侧栏' : '收起右侧栏'" :title="dockCollapsed ? '展开右侧栏' : '收起右侧栏'" @click="dockCollapsed=!dockCollapsed">
            <span aria-hidden="true">{{ dockCollapsed ? '‹' : '›' }}</span>
          </button>
        </div>
        <div v-show="activeTab==='business' && !isVerification" id="business-panel" class="dock-body" role="tabpanel"><p class="dock-empty">当前页面没有额外的业务详情。</p></div>
        <div v-show="activeTab==='chat'" class="dock-body" role="tabpanel"><AgentChat /></div>
      </aside>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import AppSidebar from './components/AppSidebar.vue'
import AgentChat from './components/AgentChat.vue'
const activeTab=ref<'business'|'chat'>('chat')
const mobileOpen=ref(false)
const dockCollapsed=ref(false)
const route=useRoute()
const isVerification=computed(() => route.path === '/visual-verification')

watch(() => route.path, (path) => {
  if (path === '/visual-verification') activeTab.value = 'chat'
}, { immediate: true })
</script>
<style scoped>
#app-container {width:100%;height:100%;overflow:hidden;display:flex;flex-direction:column}
.workspace {flex:1;min-height:0;display:grid;grid-template-columns:72px minmax(0,1fr) clamp(420px,29vw,520px);transition:grid-template-columns .2s ease}
.workspace.dock-collapsed {grid-template-columns:72px minmax(0,1fr) 42px}
.main-content {min-width:0;min-height:0;overflow:hidden}
.workspace-dock {min-width:0;min-height:0;display:flex;flex-direction:column;border-left:1px solid #29404d;background:#081521}
.dock-header {flex:0 0 44px;display:flex;align-items:stretch;border-bottom:1px solid #29404d}
.dock-tabs {min-width:0;flex:1;display:grid;grid-template-columns:1fr 1fr;gap:5px;padding:5px}
.dock-tabs.single {grid-template-columns:1fr}
.dock-tabs button {border:0;border-radius:5px;background:transparent;color:#9fb3c7;font-size:12px;font-weight:700;cursor:pointer}
.dock-tabs button.active {background:#145367;color:#e6fbff}
.dock-collapse {flex:0 0 40px;border:0;border-left:1px solid #29404d;background:#0d2331;color:#b9d5df;cursor:pointer}
.dock-collapse span {display:block;font-size:25px;line-height:1;transform:translateY(-1px)}
.dock-collapse:hover {background:#145367;color:#fff}
.workspace-dock.collapsed .dock-tabs,.workspace-dock.collapsed .dock-body {display:none}
.workspace-dock.collapsed .dock-collapse {flex:1;border-left:0}
.dock-body {flex:1;min-height:0;overflow:auto}
.dock-body :deep(> aside) {width:100%;height:100%;border:0}
.dock-empty {padding:16px;color:#8fa7bb;font-size:13px}
.dock-body:has(> aside) .dock-empty {display:none}
.mobile-dock-toggle {display:none}
@media (max-width:850px) {
 .workspace {display:grid;grid-template-columns:54px minmax(0,1fr);position:relative}
 .workspace.dock-collapsed {grid-template-columns:54px minmax(0,1fr)}
 .main-content {height:100%}
 .workspace-dock {position:absolute;right:0;top:0;bottom:0;width:min(92vw,390px);z-index:30;transform:translateX(102%);transition:transform .2s ease;box-shadow:-12px 0 30px #0008}
 .workspace-dock.open {transform:translateX(0)}
 .workspace-dock.collapsed .dock-tabs {display:grid}
 .workspace-dock.collapsed .dock-body {display:block}
 .workspace-dock.collapsed .dock-collapse {flex:0 0 40px;border-left:1px solid #29404d}
 .dock-collapse {display:none}
 .mobile-dock-toggle {display:block;position:absolute;right:10px;bottom:10px;z-index:31;min-height:36px;padding:0 10px;border:1px solid #2dd4bf;border-radius:20px;background:#0f766e;color:#fff}
}
</style>
