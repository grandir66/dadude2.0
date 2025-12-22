<template>
  <div>
    <!-- Header -->
    <v-row class="mb-4">
      <v-col>
        <h1 class="text-h4">Network Discovery</h1>
        <p class="text-body-2 text-grey">Scan networks and discover devices using agents</p>
      </v-col>
      <v-col cols="auto">
        <v-btn
          color="primary"
          prepend-icon="mdi-radar"
          @click="showScanDialog = true"
          :loading="scanning"
        >
          New Scan
        </v-btn>
      </v-col>
    </v-row>

    <!-- Stats Cards -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card color="primary" variant="tonal">
          <v-card-text class="text-center">
            <v-icon size="32" class="mb-2">mdi-history</v-icon>
            <div class="text-h4">{{ scans.length }}</div>
            <div class="text-caption">Total Scans</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="success" variant="tonal">
          <v-card-text class="text-center">
            <v-icon size="32" class="mb-2">mdi-devices</v-icon>
            <div class="text-h4">{{ totalDevicesFound }}</div>
            <div class="text-caption">Devices Found</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="info" variant="tonal">
          <v-card-text class="text-center">
            <v-icon size="32" class="mb-2">mdi-server-network</v-icon>
            <div class="text-h4">{{ agents.length }}</div>
            <div class="text-caption">Available Agents</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="warning" variant="tonal">
          <v-card-text class="text-center">
            <v-icon size="32" class="mb-2">mdi-import</v-icon>
            <div class="text-h4">{{ importedCount }}</div>
            <div class="text-caption">Imported</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Discovered Devices -->
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-devices</v-icon>
        Discovered Devices
        <v-chip v-if="discoveredDevices.length > 0" class="ml-2" color="primary" size="small">
          {{ discoveredDevices.length }}
        </v-chip>
      </v-card-title>

      <v-divider></v-divider>
          <v-card-text>
            <!-- Filters -->
            <v-row class="mb-4">
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="deviceSearch"
                  prepend-inner-icon="mdi-magnify"
                  label="Search devices..."
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="3">
                <v-select
                  v-model="platformFilter"
                  :items="platformOptions"
                  label="Platform"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                ></v-select>
              </v-col>
              <v-col cols="12" md="3">
                <v-select
                  v-model="importedFilter"
                  :items="[{title: 'All', value: null}, {title: 'Imported', value: true}, {title: 'Not Imported', value: false}]"
                  label="Import Status"
                  variant="outlined"
                  density="compact"
                  hide-details
                ></v-select>
              </v-col>
              <v-col cols="12" md="2">
                <v-btn
                  color="primary"
                  prepend-icon="mdi-import"
                  :disabled="selectedDevices.length === 0"
                  @click="showImportDialog = true"
                  block
                >
                  Import ({{ selectedDevices.length }})
                </v-btn>
              </v-col>
            </v-row>

            <v-data-table
              v-model="selectedDevices"
              :headers="deviceHeaders"
              :items="filteredDevices"
              :loading="loadingDevices"
              :search="deviceSearch"
              show-select
              item-value="id"
              hover
            >
              <template v-slot:item.address="{ item }">
                <code>{{ item.address }}</code>
              </template>
              <template v-slot:item.mac_address="{ item }">
                <code v-if="item.mac_address">{{ item.mac_address }}</code>
                <span v-else class="text-grey">-</span>
              </template>
              <template v-slot:item.vendor="{ item }">
                <span v-if="item.vendor" class="font-weight-medium">{{ item.vendor }}</span>
                <span v-else class="text-grey">-</span>
              </template>
              <template v-slot:item.open_ports="{ item }">
                <div v-if="item.open_ports && item.open_ports.length > 0">
                  <v-chip
                    v-for="port in item.open_ports.slice(0, 4)"
                    :key="port.port"
                    size="x-small"
                    class="mr-1 mb-1"
                    variant="tonal"
                    color="info"
                    :title="port.service"
                  >
                    {{ port.port }}
                  </v-chip>
                  <v-chip
                    v-if="item.open_ports.length > 4"
                    size="x-small"
                    variant="text"
                    @click="viewDeviceDetail(item)"
                  >
                    +{{ item.open_ports.length - 4 }}
                  </v-chip>
                </div>
                <span v-else class="text-grey">-</span>
              </template>
              <template v-slot:item.platform="{ item }">
                <v-chip v-if="item.platform" size="small" variant="tonal">
                  {{ item.platform }}
                </v-chip>
                <span v-else class="text-grey">Unknown</span>
              </template>
              <template v-slot:item.source="{ item }">
                <v-chip size="small" :color="item.source === 'neighbor' ? 'info' : 'warning'" variant="tonal">
                  {{ item.source || 'scan' }}
                </v-chip>
              </template>
              <template v-slot:item.imported="{ item }">
                <v-icon :color="item.imported ? 'success' : 'grey'">
                  {{ item.imported ? 'mdi-check-circle' : 'mdi-circle-outline' }}
                </v-icon>
              </template>
              <template v-slot:item.actions="{ item }">
                <v-btn
                  v-if="!item.imported"
                  icon="mdi-import"
                  size="small"
                  variant="text"
                  color="primary"
                  @click="importSingleDevice(item)"
                  title="Import device"
                ></v-btn>
                <v-btn
                  icon="mdi-information"
                  size="small"
                  variant="text"
                  @click="viewDeviceDetail(item)"
                  title="View details"
                ></v-btn>
              </template>
            </v-data-table>
          </v-card-text>
    </v-card>

    <!-- New Scan Dialog -->
    <v-dialog v-model="showScanDialog" max-width="600">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-radar</v-icon>
          New Network Scan
        </v-card-title>
        <v-card-text>
          <v-form ref="scanForm" v-model="scanFormValid">
            <v-row>
              <v-col cols="12">
                <v-select
                  v-model="scanFormData.customer_id"
                  :items="customers"
                  item-title="name"
                  item-value="id"
                  label="Customer *"
                  :rules="[v => !!v || 'Customer is required']"
                  prepend-inner-icon="mdi-domain"
                ></v-select>
              </v-col>
              <v-col cols="12">
                <v-select
                  v-model="scanFormData.agent_id"
                  :items="availableAgents"
                  item-title="name"
                  item-value="id"
                  label="Agent *"
                  :rules="[v => !!v || 'Agent is required']"
                  prepend-inner-icon="mdi-server-network"
                  :hint="selectedAgentHint"
                  persistent-hint
                ></v-select>
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="scanFormData.scan_type"
                  :items="scanTypes"
                  label="Scan Type"
                  prepend-inner-icon="mdi-magnify-scan"
                ></v-select>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="scanFormData.network_cidr"
                  label="Network CIDR (optional)"
                  placeholder="192.168.1.0/24"
                  prepend-inner-icon="mdi-ip-network"
                  hint="Leave empty to scan all assigned networks"
                  persistent-hint
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-checkbox
                  v-model="scanFormData.include_neighbors"
                  label="Include MikroTik neighbor discovery"
                  color="primary"
                  hide-details
                ></v-checkbox>
              </v-col>
              <v-col cols="12" md="6">
                <v-checkbox
                  v-model="scanFormData.scan_ports"
                  label="Scan common ports (slower)"
                  color="primary"
                  hide-details
                ></v-checkbox>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showScanDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="startScan"
            :loading="scanning"
            :disabled="!scanFormValid"
          >
            Start Scan
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Import Dialog -->
    <v-dialog v-model="showImportDialog" max-width="500">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-import</v-icon>
          Import Devices
        </v-card-title>
        <v-card-text>
          <p class="mb-4">Import {{ selectedDevices.length }} device(s) to inventory:</p>
          <v-select
            v-model="importCustomerId"
            :items="customers"
            item-title="name"
            item-value="id"
            label="Target Customer *"
            :rules="[v => !!v || 'Customer is required']"
          ></v-select>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showImportDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="importDevices"
            :loading="importing"
            :disabled="!importCustomerId"
          >
            Import
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Device Detail Dialog -->
    <v-dialog v-model="showDeviceDialog" max-width="600">
      <v-card v-if="selectedDevice">
        <v-card-title>
          <v-icon start>mdi-devices</v-icon>
          Device Details
        </v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title>IP Address</v-list-item-title>
              <v-list-item-subtitle><code>{{ selectedDevice.address }}</code></v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>MAC Address</v-list-item-title>
              <v-list-item-subtitle><code>{{ selectedDevice.mac_address || '-' }}</code></v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Vendor</v-list-item-title>
              <v-list-item-subtitle>{{ selectedDevice.vendor || 'Unknown' }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Hostname</v-list-item-title>
              <v-list-item-subtitle>{{ selectedDevice.hostname || selectedDevice.identity || '-' }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Platform</v-list-item-title>
              <v-list-item-subtitle>{{ selectedDevice.platform || 'Unknown' }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Board/Model</v-list-item-title>
              <v-list-item-subtitle>{{ selectedDevice.board || selectedDevice.model || '-' }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>OS Version</v-list-item-title>
              <v-list-item-subtitle>{{ selectedDevice.os_version || '-' }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Discovery Source</v-list-item-title>
              <v-list-item-subtitle>{{ selectedDevice.source || 'scan' }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedDevice.open_ports?.length">
              <v-list-item-title>Open Ports ({{ selectedDevice.open_ports.length }})</v-list-item-title>
              <v-list-item-subtitle>
                <v-table density="compact" class="mt-2">
                  <thead>
                    <tr>
                      <th class="text-left">Port</th>
                      <th class="text-left">Protocol</th>
                      <th class="text-left">Service</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="port in selectedDevice.open_ports" :key="port.port">
                      <td><code>{{ port.port }}</code></td>
                      <td>{{ port.protocol || 'tcp' }}</td>
                      <td>
                        <v-chip size="x-small" variant="tonal" color="success">
                          {{ port.service || 'unknown' }}
                        </v-chip>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showDeviceDialog = false">Close</v-btn>
          <v-btn
            v-if="!selectedDevice.imported"
            color="primary"
            @click="importSingleDevice(selectedDevice); showDeviceDialog = false"
          >
            Import
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar for notifications -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="4000"
      location="top"
    >
      {{ snackbar.text }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">Close</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { discoveryApi, customersApi, agentsApi } from '@/services/api'

// State
const activeTab = ref('scans')
const loadingScans = ref(false)
const loadingDevices = ref(false)
const scanning = ref(false)
const importing = ref(false)

const scans = ref([])
const discoveredDevices = ref([])
const customers = ref([])
const agents = ref([])
const selectedDevices = ref([])

// Filters
const deviceSearch = ref('')
const platformFilter = ref(null)
const importedFilter = ref(null)

// Dialogs
const showScanDialog = ref(false)
const showImportDialog = ref(false)
const showDeviceDialog = ref(false)
const selectedDevice = ref(null)
const importCustomerId = ref(null)
const snackbar = ref({ show: false, text: '', color: 'success' })

// Scan form
const scanForm = ref(null)
const scanFormValid = ref(false)
const scanFormData = ref({
  customer_id: null,
  agent_id: null,
  scan_type: 'arp',
  network_cidr: '',
  include_neighbors: true,
  scan_ports: false
})

const scanTypes = [
  { title: 'ARP Scan (fast)', value: 'arp' },
  { title: 'Ping Scan', value: 'ping' },
  { title: 'Nmap Scan (accurate)', value: 'nmap' },
  { title: 'SNMP Discovery', value: 'snmp' },
  { title: 'Full Scan (all methods)', value: 'all' }
]

// Table headers
const scanHeaders = [
  { title: 'Date', key: 'created_at', sortable: true },
  { title: 'Network', key: 'network_cidr', sortable: true },
  { title: 'Type', key: 'scan_type', sortable: true },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Devices', key: 'devices_found', sortable: true, align: 'center' },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' }
]

const deviceHeaders = [
  { title: 'IP Address', key: 'address', sortable: true },
  { title: 'MAC', key: 'mac_address', sortable: true },
  { title: 'Hostname', key: 'hostname', sortable: true },
  { title: 'Vendor', key: 'vendor', sortable: true },
  { title: 'Ports', key: 'open_ports', sortable: false },
  { title: 'Platform', key: 'platform', sortable: true },
  { title: 'Source', key: 'source', sortable: true },
  { title: 'Imported', key: 'imported', sortable: true, align: 'center' },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' }
]

// Computed
const totalDevicesFound = computed(() => {
  return discoveredDevices.value.length
})

const importedCount = computed(() => {
  return discoveredDevices.value.filter(d => d.imported).length
})

const platformOptions = computed(() => {
  const platforms = [...new Set(discoveredDevices.value.map(d => d.platform).filter(Boolean))]
  return ['All', ...platforms]
})

const filteredDevices = computed(() => {
  let result = discoveredDevices.value

  if (platformFilter.value && platformFilter.value !== 'All') {
    result = result.filter(d => d.platform === platformFilter.value)
  }

  if (importedFilter.value !== null) {
    result = result.filter(d => d.imported === importedFilter.value)
  }

  return result
})

const availableAgents = computed(() => {
  if (!scanFormData.value.customer_id) return agents.value
  return agents.value.filter(a =>
    !a.customer_id || a.customer_id === scanFormData.value.customer_id
  )
})

const selectedAgentHint = computed(() => {
  const agent = agents.value.find(a => a.id === scanFormData.value.agent_id)
  return agent ? `${agent.address} - ${agent.status}` : ''
})

// Methods
function getStatusColor(status) {
  const colors = {
    running: 'info',
    completed: 'success',
    failed: 'error',
    pending: 'warning'
  }
  return colors[status] || 'grey'
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

async function loadScans() {
  try {
    loadingScans.value = true
    const data = await discoveryApi.getScanResults()
    scans.value = data.scans || data.items || data || []
  } catch (error) {
    console.error('Error loading scans:', error)
    scans.value = []
  } finally {
    loadingScans.value = false
  }
}

async function loadDiscoveredDevices() {
  try {
    loadingDevices.value = true
    // Load all discovered devices from recent scans
    const allDevices = []
    for (const scan of scans.value.slice(0, 10)) {
      try {
        const data = await discoveryApi.getDiscoveredDevices(scan.id)
        const devices = data.devices || data.items || data || []
        allDevices.push(...devices)
      } catch (e) {
        // Skip failed scans
      }
    }
    // Remove duplicates by address
    const unique = new Map()
    allDevices.forEach(d => {
      if (!unique.has(d.address) || !unique.get(d.address).imported) {
        unique.set(d.address, d)
      }
    })
    discoveredDevices.value = Array.from(unique.values())
  } catch (error) {
    console.error('Error loading discovered devices:', error)
    discoveredDevices.value = []
  } finally {
    loadingDevices.value = false
  }
}

async function loadCustomers() {
  try {
    const data = await customersApi.getAll({ active_only: true })
    customers.value = data.customers || data.items || data || []
  } catch (error) {
    console.error('Error loading customers:', error)
  }
}

async function loadAgents() {
  try {
    const data = await agentsApi.getAll({ status: 'online' })
    agents.value = data.agents || data.items || data || []
  } catch (error) {
    console.error('Error loading agents:', error)
  }
}

async function startScan() {
  if (!scanFormValid.value) return

  try {
    scanning.value = true
    const result = await discoveryApi.startScan({
      customer_id: scanFormData.value.customer_id,
      agent_id: scanFormData.value.agent_id,
      scan_type: scanFormData.value.scan_type,
      network_cidr: scanFormData.value.network_cidr || undefined,
      include_neighbors: scanFormData.value.include_neighbors,
      scan_ports: scanFormData.value.scan_ports
    })
    showScanDialog.value = false

    // Mostra i dispositivi trovati direttamente dalla risposta
    if (result.devices && result.devices.length > 0) {
      discoveredDevices.value = result.devices
      activeTab.value = 'discovered'
    }

    snackbar.value = {
      show: true,
      text: result.message || `Scan completed: ${result.devices_found || 0} devices found`,
      color: result.success !== false ? 'success' : 'warning'
    }
  } catch (error) {
    console.error('Error starting scan:', error)
    const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
    snackbar.value = { show: true, text: `Scan failed: ${errorMsg}`, color: 'error' }
  } finally {
    scanning.value = false
  }
}

async function viewScanDevices(scan) {
  try {
    loadingDevices.value = true
    const data = await discoveryApi.getDiscoveredDevices(scan.id)
    discoveredDevices.value = data.devices || data.items || data || []
    activeTab.value = 'discovered'
  } catch (error) {
    console.error('Error loading scan devices:', error)
  } finally {
    loadingDevices.value = false
  }
}

function repeatScan(scan) {
  scanFormData.value = {
    customer_id: scan.customer_id,
    agent_id: scan.agent_id,
    scan_type: scan.scan_type,
    network_cidr: scan.network_cidr || '',
    include_neighbors: true,
    scan_ports: false
  }
  showScanDialog.value = true
}

function viewDeviceDetail(device) {
  selectedDevice.value = device
  showDeviceDialog.value = true
}

async function importSingleDevice(device) {
  importCustomerId.value = device.customer_id
  selectedDevices.value = [device.id]
  showImportDialog.value = true
}

async function importDevices() {
  if (!importCustomerId.value || selectedDevices.value.length === 0) return

  try {
    importing.value = true
    let successCount = 0
    let failCount = 0

    for (const deviceId of selectedDevices.value) {
      try {
        // Find the device data from discoveredDevices
        const device = discoveredDevices.value.find(d => d.id === deviceId)
        if (device) {
          await discoveryApi.importDevice(deviceId, importCustomerId.value, {
            address: device.address,
            hostname: device.hostname,
            mac_address: device.mac_address,
            platform: device.platform,
            vendor: device.vendor,
            device_type: device.device_type
          })
          // Mark as imported in local state
          device.imported = true
          successCount++
        }
      } catch (e) {
        console.error('Import error:', e)
        failCount++
      }
    }

    showImportDialog.value = false
    selectedDevices.value = []

    if (failCount === 0) {
      snackbar.value = { show: true, text: `Successfully imported ${successCount} device(s)`, color: 'success' }
    } else {
      snackbar.value = { show: true, text: `Imported ${successCount}, failed ${failCount}`, color: 'warning' }
    }
  } catch (error) {
    console.error('Error importing devices:', error)
    const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
    snackbar.value = { show: true, text: `Import failed: ${errorMsg}`, color: 'error' }
  } finally {
    importing.value = false
  }
}

onMounted(async () => {
  await loadCustomers()
  await loadAgents()
  await loadScans()
  loadDiscoveredDevices()
})
</script>

<style scoped>
.rotating {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
