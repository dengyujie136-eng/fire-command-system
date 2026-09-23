<template>
  <div id="app-container">
    <AppHeader />
    <div class="workspace">
      <AppSidebar />
      <main class="main-content"><router-view /></main>
      <button class="mobile-dock-toggle" type="button" @click="mobileOpen=!mobileOpen">{{ mobileOpen ? '关闭侧栏' : '详情 / 对话' }}</button>
      <aside class="workspace-dock" :class="{ open: mobileOpen }" aria-label="业务信息与智能体对话">
        <div class="dock-tabs" role="tablist">
          <button role="tab" type="button" :aria-selected="activeTab==='business'" :class="{ active: activeTab==='business' }" @click="activeTab='business'">业务面板</button>
          <button role="tab" type="button" :aria-selected="activeTab==='chat'" :class="{ active: activeTab==='chat' }" @click="activeTab='chat'">智能体对话</button>
        </div>
        <div v-show="activeTab==='business'" id="business-panel" class="dock-body" role="tabpanel"><p class="dock-empty">当前页面没有额外的业务详情。</p></div>
        <div v-show="activeTab==='chat'" class="dock-body" role="tabpanel"><AgentChat /></div>
      </aside>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import AppHeader from './components/AppHeader.vue'
import AppSidebar from './components/AppSidebar.vue'
import AgentChat from './components/AgentChat.vue'
const activeTab=ref<'business'|'chat'>('business')
const mobileOpen=ref(false)
</script>
<style scoped>
#app-container {width:100%;height:100%;overflow:hidden;display:flex;flex-direction:column}
.workspace {flex:1;min-height:0;display:grid;grid-template-columns:72px minmax(0,1fr) clamp(280px,20vw,330px)}
.main-content {min-width:0;min-height:0;overflow:hidden}
.workspace-dock {min-width:0;min-height:0;display:flex;flex-direction:column;border-left:1px solid #29404d;background:#081521}
.dock-tabs {flex:0 0 40px;display:grid;grid-template-columns:1fr 1fr;gap:5px;padding:5px;border-bottom:1px solid #29404d}
.dock-tabs button {border:0;border-radius:5px;background:transparent;color:#9fb3c7;font-size:11px;font-weight:700;cursor:pointer}
.dock-tabs button.active {background:#145367;color:#e6fbff}
.dock-body {flex:1;min-height:0;overflow:auto}
.dock-body :deep(> aside) {width:100%;height:100%;border:0}
.dock-empty {padding:15px;color:#8fa7bb;font-size:11px}
.dock-body:has(> aside) .dock-empty {display:none}
.mobile-dock-toggle {display:none}
@media (max-width:850px) {
 .workspace {display:grid;grid-template-columns:54px minmax(0,1fr);position:relative}
 .main-content {height:100%}
 .workspace-dock {position:absolute;right:0;top:0;bottom:0;width:min(88vw,330px);z-index:30;transform:translateX(102%);transition:transform .2s ease;box-shadow:-12px 0 30px #0008}
 .workspace-dock.open {transform:translateX(0)}
 .mobile-dock-toggle {display:block;position:absolute;right:10px;bottom:10px;z-index:31;min-height:36px;padding:0 10px;border:1px solid #2dd4bf;border-radius:20px;background:#0f766e;color:#fff}
}
</style>
