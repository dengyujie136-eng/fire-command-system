<template>
  <nav class="app-sidebar" aria-label="主要工作流程">
    <router-link v-for="(item,index) in items" :key="item.path" :to="item.path" class="page-link" active-class="active" :title="item.label">
      <span class="step">{{ String(index+1).padStart(2,'0') }}</span>
      <i :class="item.icon" aria-hidden="true"></i>
      <strong>{{ item.label }}</strong>
    </router-link>
  </nav>
</template>
<script setup lang="ts">
const items=[
 {path:'/realtime-monitor',label:'监测',icon:'fa-solid fa-satellite-dish'},
 {path:'/visual-verification',label:'核验',icon:'fa-solid fa-crosshairs'},
 {path:'/command-center',label:'推演',icon:'fa-solid fa-fire'},
 {path:'/planning',label:'规划',icon:'fa-solid fa-route'},
 {path:'/disaster-assess',label:'评估',icon:'fa-solid fa-chart-line'}
]
</script>
<style scoped>
.app-sidebar {min-width:0;min-height:0;display:flex;flex-direction:column;gap:5px;padding:10px 5px;border-right:1px solid #29404d;background:linear-gradient(180deg,#0d2331,#081521);color:#9cb4c3}
.nav-caption {margin:2px 5px 12px;color:#668796;font-size:10px;font-weight:800;letter-spacing:.12em}
.page-link {position:relative;min-height:61px;display:grid;grid-template-columns:18px 1fr;grid-template-rows:20px 20px;align-content:center;align-items:center;column-gap:4px;padding:5px;border:1px solid transparent;border-radius:7px;color:#9eb6c4;text-decoration:none}
.page-link i {grid-column:1;grid-row:1/3;justify-self:center;font-size:16px}
.page-link .step {grid-column:2;grid-row:1;color:#5f8496;font-size:9px;font-weight:800}
.page-link strong {grid-column:2;grid-row:2;color:inherit;font-size:11px}
.page-link:hover {background:#153041;color:#e7f4fa}
.page-link.active {border-color:#247e88;background:#134a59;color:#efffff;box-shadow:inset 3px 0 #2dd4bf}
.page-link.active .step {color:#73e6d8}
.sidebar-footer {margin-top:auto;padding:10px 3px;color:#4d7180;font-size:9px;line-height:1.55;letter-spacing:.08em}
@media(max-width:950px){.nav-caption,.sidebar-footer,.page-link .step,.page-link strong{display:none}.app-sidebar{padding:8px 5px}.page-link{display:grid;place-items:center;min-height:48px;padding:0}.page-link i{grid-column:auto;grid-row:auto}}
</style>
