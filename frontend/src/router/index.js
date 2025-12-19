/**
 * DaDude v2.0 - Vue Router Configuration
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: 'Dashboard' }
  },
  {
    path: '/customers',
    name: 'Customers',
    component: () => import('@/views/Customers.vue'),
    meta: { title: 'Customers' }
  },
  {
    path: '/customers/:id',
    name: 'CustomerDetail',
    component: () => import('@/views/CustomerDetail.vue'),
    meta: { title: 'Customer Detail' }
  },
  {
    path: '/agents',
    name: 'Agents',
    component: () => import('@/views/Agents.vue'),
    meta: { title: 'Agents' }
  },
  {
    path: '/agents/:id',
    name: 'AgentDetail',
    component: () => import('@/views/AgentDetail.vue'),
    meta: { title: 'Agent Detail' }
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('@/views/Devices.vue'),
    meta: { title: 'Devices' }
  },
  {
    path: '/devices/:id',
    name: 'DeviceDetail',
    component: () => import('@/views/DeviceDetail.vue'),
    meta: { title: 'Device Detail' }
  },
  {
    path: '/discovery',
    name: 'Discovery',
    component: () => import('@/views/Discovery.vue'),
    meta: { title: 'Network Discovery' }
  },
  {
    path: '/backups',
    name: 'Backups',
    component: () => import('@/views/Backups.vue'),
    meta: { title: 'Backups' }
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('@/views/Alerts.vue'),
    meta: { title: 'Alerts' }
  },
  {
    path: '/credentials',
    name: 'Credentials',
    component: () => import('@/views/Credentials.vue'),
    meta: { title: 'Credentials' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: 'Settings' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: 'Login', public: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: 'Not Found' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// Update page title on navigation
router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'DaDude'} - DaDude v2.0`
  next()
})

export default router
