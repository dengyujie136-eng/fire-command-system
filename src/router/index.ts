import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'HomePage',
    redirect: '/realtime-monitor'
  },
  {
    path: '/multi-source-fusion',
    name: 'MultiSourceFusion',
    redirect: '/visual-verification'
  },
  {
    path: '/realtime-monitor',
    name: 'RealtimeMonitor',
    component: () => import('../views/RealtimeMonitor.vue')
  },
  {
    path: '/visual-verification',
    name: 'VisualVerification',
    component: () => import('../views/VerificationWorkspace.vue')
  },
  {
    path: '/emergency-route',
    name: 'EmergencyRoute',
    redirect: '/planning'
  },
  {
    path: '/command-center',
    name: 'CommandCenter',
    component: () => import('../views/FirePredict.vue')
  },
  {
    path: '/planning',
    name: 'Planning',
    component: () => import('../views/Planning.vue')
  },
  {
    path: '/uav-dispatch',
    name: 'UAVDispatch',
    redirect: '/planning'
  },
  {
    path: '/fire-predict',
    name: 'FirePredict',
    redirect: '/command-center'
  },
  {
    path: '/disaster-assess',
    name: 'DisasterAssess',
    component: () => import('../views/AssessmentWorkspace.vue')
  },
  {
    path: '/resource-dispatch',
    name: 'ResourceDispatch',
    redirect: '/planning'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
