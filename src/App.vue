<template>
  <div id="app-container">
    <AppHeader />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import AppHeader from './components/AppHeader.vue'
</script>

<style scoped>
#app-container {
  /* 使用 100% 继承根节点高度，防止子页面再叠加 100vh 造成纵向溢出。 */
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.main-content {
  /* flex:1 + min-height:0 允许实时监测页面在头部下方正确收缩。 */
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
