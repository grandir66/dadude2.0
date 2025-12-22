/**
 * DaDude v2.0 - API Service
 * Centralized API client with Axios
 */
import axios from 'axios'

// Create axios instance
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  }
})

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('api_key')
    if (token) {
      config.headers['X-API-Key'] = token
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      // Handle specific error codes
      switch (error.response.status) {
        case 401:
          // Unauthorized - redirect to login
          window.location.href = '/login'
          break
        case 403:
          console.error('Forbidden:', error.response.data)
          break
        case 404:
          console.error('Not found:', error.response.data)
          break
        case 500:
          console.error('Server error:', error.response.data)
          break
      }
    }
    return Promise.reject(error)
  }
)

// ===========================================
// CUSTOMERS
// ===========================================
export const customersApi = {
  getAll: (params) => api.get('/customers', { params }),
  getById: (id) => api.get(`/customers/${id}`),
  create: (data) => api.post('/customers', data),
  update: (id, data) => api.put(`/customers/${id}`, data),
  delete: (id) => api.delete(`/customers/${id}`),
  // Networks
  getNetworks: (customerId) => api.get(`/customers/${customerId}/networks`),
  createNetwork: (customerId, data) => api.post(`/customers/${customerId}/networks`, data),
  // Credentials
  getCredentials: (customerId) => api.get(`/customers/${customerId}/credentials`),
}

// ===========================================
// AGENTS
// ===========================================
export const agentsApi = {
  getAll: (params) => api.get('/agents', { params }),
  getById: (id) => api.get(`/agents/${id}`),
  create: (data) => api.post('/agents', data),
  update: (id, data) => api.put(`/agents/${id}`, data),
  delete: (id) => api.delete(`/agents/${id}`),
  // Pending agents
  getPending: () => api.get('/agents/pending'),
  // Actions
  testConnection: (id) => api.post(`/agents/${id}/test-connection`),
  startScan: (id, data) => api.post(`/agents/${id}/scan`, data),
  getStatus: (id) => api.get(`/agents/${id}/status`),
  getConfig: (id) => api.get(`/agents/config/${id}`),
  updateConfig: (id, data) => api.put(`/agents/${id}/config`, data),
  // Commands
  exec: (id, command) => api.post(`/agents/${id}/exec`, { command }),
  restart: (id) => api.post(`/agents/${id}/restart`),
  // Updates
  checkUpdate: (id) => api.get(`/agents/${id}/check-update`),
  triggerUpdate: (id) => api.post(`/agents/${id}/trigger-update`),
  // Certificate
  getCertificate: (id) => api.get(`/agents/${id}/certificate`),
  renewCertificate: (id) => api.post(`/agents/${id}/renew`),
  // Approve pending agent
  approve: (id, data) => api.post(`/agents/${id}/approve`, data),
}

// ===========================================
// DEVICES (INVENTORY)
// ===========================================
export const devicesApi = {
  getAll: (params) => api.get('/inventory/devices', { params }),
  getById: (id) => api.get(`/inventory/devices/${id}`),
  create: (data) => api.post('/inventory/devices', data),
  update: (id, data) => api.put(`/inventory/devices/${id}`, data),
  delete: (id) => api.delete(`/inventory/devices/${id}`),
  // Actions
  probe: (id) => api.post(`/inventory/devices/${id}/probe`),
  getDetails: (id) => api.get(`/inventory/devices/${id}/details`),
}

// ===========================================
// DISCOVERY
// ===========================================
export const discoveryApi = {
  getScanResults: (params) => api.get('/discovery/scans', { params }),
  getDiscoveredDevices: (scanId) => api.get(`/discovery/scans/${scanId}/devices`),
  startScan: (data) => api.post('/discovery/scan', data),
  importDevice: (deviceId, customerId, deviceData = {}) => api.post(`/discovery/devices/${deviceId}/import`, {
    customer_id: customerId,
    device: deviceData,
    ...deviceData  // Also spread at top level for backwards compatibility
  }),
}

// ===========================================
// BACKUPS
// ===========================================
export const backupsApi = {
  getAll: (params) => api.get('/backups', { params }),
  getById: (id) => api.get(`/backups/${id}`),
  download: (id) => api.get(`/backups/${id}/download`, { responseType: 'blob' }),
  delete: (id) => api.delete(`/backups/${id}`),
  // Schedules
  getSchedules: (params) => api.get('/backups/schedules', { params }),
  createSchedule: (data) => api.post('/backups/schedules', data),
  updateSchedule: (id, data) => api.put(`/backups/schedules/${id}`, data),
  deleteSchedule: (id) => api.delete(`/backups/schedules/${id}`),
  // Jobs
  getJobs: (params) => api.get('/backups/jobs', { params }),
  startJob: (data) => api.post('/backups/jobs', data),
}

// ===========================================
// ALERTS
// ===========================================
export const alertsApi = {
  getAll: (params) => api.get('/alerts', { params }),
  getById: (id) => api.get(`/alerts/${id}`),
  acknowledge: (id) => api.post(`/alerts/${id}/acknowledge`),
  resolve: (id, notes) => api.post(`/alerts/${id}/resolve`, { notes }),
  delete: (id) => api.delete(`/alerts/${id}`),
}

// ===========================================
// CREDENTIALS
// ===========================================
export const credentialsApi = {
  getAll: (params) => api.get('/customers/credentials', { params }),
  getById: (id) => api.get(`/customers/credentials/${id}`),
  // Create: uses customer-specific endpoint if customer_id provided, otherwise global
  create: (data) => {
    if (data.customer_id) {
      return api.post(`/customers/${data.customer_id}/credentials`, data)
    }
    return api.post('/customers/credentials', data)
  },
  update: (id, data) => api.put(`/customers/credentials/${id}`, data),
  delete: (id) => api.delete(`/customers/credentials/${id}`),
  // Global credentials
  getGlobal: () => api.get('/customers/credentials', { params: { global_only: true } }),
  // Test credential
  test: (id, targetIp) => api.post(`/customers/credentials/${id}/test`, { target_ip: targetIp }),
}

// ===========================================
// NETWORKS
// ===========================================
export const networksApi = {
  getAll: (params) => api.get('/customers/networks', { params }),
  getById: (id) => api.get(`/customers/networks/${id}`),
  create: (customerId, data) => api.post(`/customers/${customerId}/networks`, data),
  update: (id, data) => api.put(`/customers/networks/${id}`, data),
  delete: (id) => api.delete(`/customers/networks/${id}`),
}

// ===========================================
// SYSTEM
// ===========================================
export const systemApi = {
  getHealth: () => api.get('/system/health'),
  getInfo: () => api.get('/system/info'),
  getStats: () => api.get('/system/stats'),
}

// ===========================================
// DASHBOARD
// ===========================================
export const dashboardApi = {
  getStats: () => api.get('/dashboard/stats'),
  getRecentAlerts: () => api.get('/dashboard/alerts'),
  getAgentStatus: () => api.get('/dashboard/agents'),
  getDeviceSummary: () => api.get('/dashboard/devices'),
}

export default api
