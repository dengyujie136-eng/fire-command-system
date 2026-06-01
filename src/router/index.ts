import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/realtime-monitor'
  },
  {
    path: '/multi-source-fusion',
    name: 'MultiSourceFusion',
    component: () => import('../views/MultiSourceFusion.vue')
  },
  {
    path: '/realtime-monitor',
    name: 'RealtimeMonitor',
    component: () => import('../views/RealtimeMonitor.vue')
  },
  {
    path: '/emergency-route',
    name: 'EmergencyRoute',
    component: () => import('../views/EmergencyRoute.vue')
  },
  {
    path: '/command-center',
    name: 'CommandCenter',
    component: () => import('../views/CommandCenter.vue')
  },
  {
    path: '/uav-dispatch',
    name: 'UAVDispatch',
    component: () => import('../views/UAVDispatch.vue')
  },
  {
    path: '/fire-predict',
    name: 'FirePredict',
    component: () => import('../views/FirePredict.vue')
  },
  {
    path: '/disaster-assess',
    name: 'DisasterAssess',
    component: () => import('../views/DisasterAssess.vue')
  },
  {
    path: '/resource-dispatch',
    name: 'ResourceDispatch',
    component: () => import('../views/ResourceDispatch.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
