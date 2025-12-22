<template>
  <div>
    <!-- Loading State -->
    <div v-if="loading" class="d-flex justify-center align-center" style="min-height: 400px;">
      <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
    </div>

    <!-- Error State -->
    <v-alert v-else-if="error" type="error" class="mb-4">
      {{ error }}
      <template v-slot:append>
        <v-btn variant="text" @click="loadAgent">Retry</v-btn>
      </template>
    </v-alert>

    <!-- Agent Content -->
    <template v-else-if="agent">
      <!-- Header -->
      <v-row class="mb-4">
        <v-col>
          <div class="d-flex align-center">
            <v-avatar
              :color="agent.status === 'online' ? 'success' : 'error'"
              size="56"
              class="mr-4"
            >
              <v-icon
                :icon="agent.agent_type === 'docker' ? 'mdi-docker' : 'mdi-router-wireless'"
                color="white"
                size="32"
              ></v-icon>
            </v-avatar>
            <div>
              <h1 class="text-h4">{{ agent.name }}</h1>
              <p class="text-body-2 text-grey">{{ agent.address }}:{{ agent.port }}</p>
            </div>
            <v-spacer></v-spacer>
            <v-chip
              :color="agent.status === 'online' ? 'success' : 'error'"
              size="large"
              class="mr-2"
            >
              <v-icon start>mdi-circle</v-icon>
              {{ agent.status || 'unknown' }}
            </v-chip>
          </div>
        </v-col>
        <v-col cols="auto">
          <v-btn
            color="primary"
            prepend-icon="mdi-connection"
            @click="testConnection"
            :loading="testing"
            class="mr-2"
          >
            Test Connection
          </v-btn>
          <v-btn
            variant="outlined"
            prepend-icon="mdi-pencil"
            @click="showEditDialog = true"
          >
            Edit
          </v-btn>
        </v-col>
      </v-row>

      <!-- Tabs -->
      <v-tabs v-model="activeTab" color="primary" class="mb-4">
        <v-tab value="overview">Overview</v-tab>
        <v-tab value="scan">Network Scan</v-tab>
        <v-tab value="commands">Commands</v-tab>
        <v-tab value="certificate">Certificate</v-tab>
        <v-tab value="updates">Updates</v-tab>
      </v-tabs>

      <v-window v-model="activeTab">
        <!-- Overview Tab -->
        <v-window-item value="overview">
          <v-row>
            <v-col cols="12" md="6">
              <v-card>
                <v-card-title>
                  <v-icon start>mdi-information</v-icon>
                  Agent Information
                </v-card-title>
                <v-divider></v-divider>
                <v-list density="compact">
                  <v-list-item>
                    <v-list-item-title>ID</v-list-item-title>
                    <template v-slot:append>
                      <code>{{ agent.id }}</code>
                    </template>
                  </v-list-item>
                  <v-list-item>
                    <v-list-item-title>Type</v-list-item-title>
                    <template v-slot:append>
                      <v-chip size="small" variant="tonal">{{ agent.agent_type }}</v-chip>
                    </template>
                  </v-list-item>
                  <v-list-item>
                    <v-list-item-title>Address</v-list-item-title>
                    <template v-slot:append>
                      <code>{{ agent.address }}:{{ agent.port }}</code>
                    </template>
                  </v-list-item>
                  <v-list-item v-if="agent.version">
                    <v-list-item-title>Version</v-list-item-title>
                    <template v-slot:append>{{ agent.version }}</template>
                  </v-list-item>
                  <v-list-item v-if="agent.last_seen">
                    <v-list-item-title>Last Seen</v-list-item-title>
                    <template v-slot:append>{{ formatDate(agent.last_seen) }}</template>
                  </v-list-item>
                  <v-list-item v-if="agent.customer_id">
                    <v-list-item-title>Customer</v-list-item-title>
                    <template v-slot:append>
                      <router-link :to="`/customers/${agent.customer_id}`">
                        {{ agent.customer_name || agent.customer_id }}
                      </router-link>
                    </template>
                  </v-list-item>
                </v-list>
              </v-card>
            </v-col>

            <v-col cols="12" md="6">
              <v-card>
                <v-card-title>
                  <v-icon start>mdi-chart-line</v-icon>
                  Status
                </v-card-title>
                <v-divider></v-divider>
                <v-card-text>
                  <v-row>
                    <v-col cols="6" class="text-center">
                      <div class="text-h3" :class="agent.status === 'online' ? 'text-success' : 'text-error'">
                        <v-icon size="48">{{ agent.status === 'online' ? 'mdi-check-circle' : 'mdi-alert-circle' }}</v-icon>
                      </div>
                      <div class="text-caption mt-2">Connection Status</div>
                    </v-col>
                    <v-col cols="6" class="text-center">
                      <div class="text-h3 text-primary">{{ agent.scans_count || 0 }}</div>
                      <div class="text-caption mt-2">Total Scans</div>
                    </v-col>
                  </v-row>
                </v-card-text>
              </v-card>

              <!-- Quick Actions -->
              <v-card class="mt-4">
                <v-card-title>
                  <v-icon start>mdi-flash</v-icon>
                  Quick Actions
                </v-card-title>
                <v-divider></v-divider>
                <v-card-text>
                  <v-btn
                    block
                    color="primary"
                    prepend-icon="mdi-radar"
                    class="mb-2"
                    @click="activeTab = 'scan'"
                  >
                    Start Network Scan
                  </v-btn>
                  <v-btn
                    block
                    variant="outlined"
                    prepend-icon="mdi-restart"
                    class="mb-2"
                    @click="restartAgent"
                    :loading="restarting"
                  >
                    Restart Agent
                  </v-btn>
                  <v-btn
                    block
                    variant="outlined"
                    color="error"
                    prepend-icon="mdi-delete"
                    @click="showDeleteDialog = true"
                  >
                    Delete Agent
                  </v-btn>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>

        <!-- Scan Tab -->
        <v-window-item value="scan">
          <v-row>
            <v-col cols="12" md="4">
              <v-card>
                <v-card-title>
                  <v-icon start>mdi-radar</v-icon>
                  Network Scan
                </v-card-title>
                <v-divider></v-divider>
                <v-card-text>
                  <v-text-field
                    v-model="scanForm.network"
                    label="Network CIDR"
                    placeholder="192.168.1.0/24"
                    hint="Enter network in CIDR format or single IP"
                    persistent-hint
                    prepend-inner-icon="mdi-ip-network"
                  ></v-text-field>
                  <v-select
                    v-model="scanForm.type"
                    :items="scanTypes"
                    label="Scan Type"
                    class="mt-4"
                    prepend-inner-icon="mdi-magnify-scan"
                  ></v-select>
                  <v-checkbox
                    v-model="scanForm.include_ports"
                    label="Scan common ports"
                    color="primary"
                  ></v-checkbox>
                  <v-btn
                    block
                    color="primary"
                    size="large"
                    @click="startScan"
                    :loading="scanning"
                    :disabled="!scanForm.network"
                  >
                    <v-icon start>mdi-radar</v-icon>
                    Start Scan
                  </v-btn>
                </v-card-text>
              </v-card>
            </v-col>

            <v-col cols="12" md="8">
              <v-card>
                <v-card-title class="d-flex align-center">
                  <v-icon start>mdi-devices</v-icon>
                  Scan Results
                  <v-chip v-if="scanResults.length" class="ml-2" color="primary" size="small">
                    {{ scanResults.length }}
                  </v-chip>
                </v-card-title>
                <v-divider></v-divider>
                <v-data-table
                  :headers="scanHeaders"
                  :items="scanResults"
                  :loading="scanning"
                  density="compact"
                >
                  <template v-slot:item.address="{ item }">
                    <code>{{ item.address }}</code>
                  </template>
                  <template v-slot:item.mac_address="{ item }">
                    <code v-if="item.mac_address">{{ item.mac_address }}</code>
                    <span v-else class="text-grey">-</span>
                  </template>
                  <template v-slot:item.vendor="{ item }">
                    <span v-if="item.vendor">{{ item.vendor }}</span>
                    <span v-else class="text-grey">-</span>
                  </template>
                  <template v-slot:item.ports="{ item }">
                    <div v-if="item.open_ports && item.open_ports.length">
                      <v-chip
                        v-for="port in item.open_ports.slice(0, 5)"
                        :key="port.port"
                        size="x-small"
                        class="mr-1"
                        variant="tonal"
                        color="info"
                      >
                        {{ port.port }}
                      </v-chip>
                      <span v-if="item.open_ports.length > 5" class="text-grey">
                        +{{ item.open_ports.length - 5 }}
                      </span>
                    </div>
                    <span v-else class="text-grey">-</span>
                  </template>
                </v-data-table>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>

        <!-- Commands Tab -->
        <v-window-item value="commands">
          <v-row>
            <v-col cols="12">
              <v-card>
                <v-card-title>
                  <v-icon start>mdi-console</v-icon>
                  Execute Command
                </v-card-title>
                <v-divider></v-divider>
                <v-card-text>
                  <v-text-field
                    v-model="command"
                    label="Command"
                    placeholder="Enter command to execute on agent..."
                    prepend-inner-icon="mdi-console-line"
                    :disabled="executing"
                    @keyup.enter="executeCommand"
                  >
                    <template v-slot:append>
                      <v-btn
                        color="primary"
                        @click="executeCommand"
                        :loading="executing"
                        :disabled="!command"
                      >
                        Execute
                      </v-btn>
                    </template>
                  </v-text-field>

                  <v-card v-if="commandOutput" variant="outlined" class="mt-4">
                    <v-card-title class="text-caption">Output</v-card-title>
                    <v-card-text>
                      <pre class="command-output">{{ commandOutput }}</pre>
                    </v-card-text>
                  </v-card>

                  <v-alert v-if="commandError" type="error" class="mt-4">
                    {{ commandError }}
                  </v-alert>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>

        <!-- Certificate Tab -->
        <v-window-item value="certificate">
          <v-row>
            <v-col cols="12" md="6">
              <v-card>
                <v-card-title>
                  <v-icon start>mdi-certificate</v-icon>
                  Certificate Status
                </v-card-title>
                <v-divider></v-divider>
                <v-card-text v-if="certificate">
                  <v-list density="compact">
                    <v-list-item>
                      <v-list-item-title>Status</v-list-item-title>
                      <template v-slot:append>
                        <v-chip
                          :color="certificate.valid ? 'success' : 'error'"
                          size="small"
                        >
                          {{ certificate.valid ? 'Valid' : 'Invalid' }}
                        </v-chip>
                      </template>
                    </v-list-item>
                    <v-list-item v-if="certificate.expires_at">
                      <v-list-item-title>Expires</v-list-item-title>
                      <template v-slot:append>{{ formatDate(certificate.expires_at) }}</template>
                    </v-list-item>
                    <v-list-item v-if="certificate.fingerprint">
                      <v-list-item-title>Fingerprint</v-list-item-title>
                      <template v-slot:append>
                        <code class="text-caption">{{ certificate.fingerprint.substring(0, 20) }}...</code>
                      </template>
                    </v-list-item>
                  </v-list>
                  <v-btn
                    block
                    color="primary"
                    class="mt-4"
                    @click="renewCertificate"
                    :loading="renewingCert"
                  >
                    <v-icon start>mdi-refresh</v-icon>
                    Renew Certificate
                  </v-btn>
                </v-card-text>
                <v-card-text v-else>
                  <v-alert type="info" variant="tonal">
                    No certificate information available
                  </v-alert>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>

        <!-- Updates Tab -->
        <v-window-item value="updates">
          <v-row>
            <v-col cols="12" md="6">
              <v-card>
                <v-card-title>
                  <v-icon start>mdi-update</v-icon>
                  Agent Updates
                </v-card-title>
                <v-divider></v-divider>
                <v-card-text>
                  <v-list density="compact">
                    <v-list-item>
                      <v-list-item-title>Current Version</v-list-item-title>
                      <template v-slot:append>
                        <code>{{ agent.version || 'Unknown' }}</code>
                      </template>
                    </v-list-item>
                    <v-list-item v-if="updateInfo">
                      <v-list-item-title>Latest Version</v-list-item-title>
                      <template v-slot:append>
                        <code>{{ updateInfo.latest_version }}</code>
                      </template>
                    </v-list-item>
                    <v-list-item v-if="updateInfo">
                      <v-list-item-title>Update Available</v-list-item-title>
                      <template v-slot:append>
                        <v-chip
                          :color="updateInfo.update_available ? 'warning' : 'success'"
                          size="small"
                        >
                          {{ updateInfo.update_available ? 'Yes' : 'No' }}
                        </v-chip>
                      </template>
                    </v-list-item>
                  </v-list>
                  <v-btn
                    block
                    variant="outlined"
                    class="mt-4 mb-2"
                    @click="checkUpdate"
                    :loading="checkingUpdate"
                  >
                    <v-icon start>mdi-magnify</v-icon>
                    Check for Updates
                  </v-btn>
                  <v-btn
                    v-if="updateInfo?.update_available"
                    block
                    color="primary"
                    @click="triggerUpdate"
                    :loading="updating"
                  >
                    <v-icon start>mdi-download</v-icon>
                    Update Agent
                  </v-btn>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>
      </v-window>
    </template>

    <!-- Edit Dialog -->
    <v-dialog v-model="showEditDialog" max-width="600">
      <v-card>
        <v-card-title>Edit Agent</v-card-title>
        <v-card-text>
          <v-form ref="editForm" v-model="editFormValid">
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="editFormData.name"
                  label="Name"
                  :rules="[v => !!v || 'Name is required']"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="8">
                <v-text-field
                  v-model="editFormData.address"
                  label="Address"
                  :rules="[v => !!v || 'Address is required']"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="editFormData.port"
                  label="Port"
                  type="number"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editFormData.username"
                  label="Username"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="editFormData.password"
                  label="Password"
                  type="password"
                  placeholder="Leave empty to keep current"
                ></v-text-field>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showEditDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="saveAgent" :loading="saving" :disabled="!editFormValid">
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>Delete Agent</v-card-title>
        <v-card-text>
          Are you sure you want to delete agent <strong>{{ agent?.name }}</strong>?
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showDeleteDialog = false">Cancel</v-btn>
          <v-btn color="error" @click="deleteAgent" :loading="deleting">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="4000">
      {{ snackbar.text }}
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { format, parseISO } from 'date-fns'
import { agentsApi } from '@/services/api'

const route = useRoute()
const router = useRouter()

// State
const loading = ref(true)
const error = ref(null)
const agent = ref(null)
const activeTab = ref('overview')

// Actions state
const testing = ref(false)
const scanning = ref(false)
const restarting = ref(false)
const executing = ref(false)
const saving = ref(false)
const deleting = ref(false)
const checkingUpdate = ref(false)
const updating = ref(false)
const renewingCert = ref(false)

// Data
const scanResults = ref([])
const certificate = ref(null)
const updateInfo = ref(null)
const command = ref('')
const commandOutput = ref('')
const commandError = ref('')

// Dialogs
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const editForm = ref(null)
const editFormValid = ref(false)
const editFormData = ref({
  name: '',
  address: '',
  port: 8728,
  username: '',
  password: ''
})

// Scan form
const scanForm = ref({
  network: '',
  type: 'arp',
  include_ports: false
})

const scanTypes = [
  { title: 'ARP Scan (fast)', value: 'arp' },
  { title: 'Ping Scan', value: 'ping' },
  { title: 'SNMP Discovery', value: 'snmp' },
  { title: 'Full Scan', value: 'full' }
]

const scanHeaders = [
  { title: 'IP Address', key: 'address' },
  { title: 'MAC', key: 'mac_address' },
  { title: 'Hostname', key: 'hostname' },
  { title: 'Vendor', key: 'vendor' },
  { title: 'Ports', key: 'ports' }
]

// Snackbar
const snackbar = ref({ show: false, text: '', color: 'success' })

// Methods
function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    return format(parseISO(dateStr), 'dd/MM/yyyy HH:mm')
  } catch {
    return dateStr
  }
}

function showMessage(text, color = 'success') {
  snackbar.value = { show: true, text, color }
}

async function loadAgent() {
  const agentId = route.params.id
  if (!agentId) {
    error.value = 'Agent ID not provided'
    loading.value = false
    return
  }

  try {
    loading.value = true
    error.value = null
    const data = await agentsApi.getById(agentId)
    agent.value = data.agent || data

    // Pre-fill edit form
    editFormData.value = {
      name: agent.value.name,
      address: agent.value.address,
      port: agent.value.port,
      username: agent.value.username || '',
      password: ''
    }
  } catch (e) {
    console.error('Error loading agent:', e)
    error.value = e.response?.data?.detail || 'Failed to load agent'
  } finally {
    loading.value = false
  }
}

async function testConnection() {
  try {
    testing.value = true
    const result = await agentsApi.testConnection(agent.value.id)
    if (result.success) {
      showMessage('Connection successful')
      agent.value.status = 'online'
    } else {
      showMessage(result.error || 'Connection failed', 'error')
    }
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Connection test failed', 'error')
  } finally {
    testing.value = false
  }
}

async function startScan() {
  try {
    scanning.value = true
    scanResults.value = []
    const result = await agentsApi.startScan(agent.value.id, {
      network: scanForm.value.network,
      scan_type: scanForm.value.type,
      include_ports: scanForm.value.include_ports
    })
    scanResults.value = result.devices || result.results || []
    showMessage(`Scan completed: ${scanResults.value.length} devices found`)
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Scan failed', 'error')
  } finally {
    scanning.value = false
  }
}

async function executeCommand() {
  if (!command.value) return

  try {
    executing.value = true
    commandOutput.value = ''
    commandError.value = ''
    const result = await agentsApi.exec(agent.value.id, command.value)
    commandOutput.value = result.output || result.result || JSON.stringify(result, null, 2)
  } catch (e) {
    commandError.value = e.response?.data?.detail || 'Command execution failed'
  } finally {
    executing.value = false
  }
}

async function restartAgent() {
  try {
    restarting.value = true
    await agentsApi.restart(agent.value.id)
    showMessage('Agent restart initiated')
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Failed to restart agent', 'error')
  } finally {
    restarting.value = false
  }
}

async function checkUpdate() {
  try {
    checkingUpdate.value = true
    const result = await agentsApi.checkUpdate(agent.value.id)
    updateInfo.value = result
    if (result.update_available) {
      showMessage('Update available!')
    } else {
      showMessage('Agent is up to date')
    }
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Failed to check updates', 'error')
  } finally {
    checkingUpdate.value = false
  }
}

async function triggerUpdate() {
  try {
    updating.value = true
    await agentsApi.triggerUpdate(agent.value.id)
    showMessage('Update started')
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Failed to start update', 'error')
  } finally {
    updating.value = false
  }
}

async function renewCertificate() {
  try {
    renewingCert.value = true
    await agentsApi.renewCertificate(agent.value.id)
    showMessage('Certificate renewed')
    // Reload certificate info
    loadCertificate()
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Failed to renew certificate', 'error')
  } finally {
    renewingCert.value = false
  }
}

async function loadCertificate() {
  try {
    const result = await agentsApi.getCertificate(agent.value.id)
    certificate.value = result
  } catch (e) {
    // Certificate might not exist
    certificate.value = null
  }
}

async function saveAgent() {
  try {
    saving.value = true
    const updateData = { ...editFormData.value }
    if (!updateData.password) delete updateData.password

    await agentsApi.update(agent.value.id, updateData)
    showMessage('Agent updated')
    showEditDialog.value = false
    loadAgent()
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Failed to save agent', 'error')
  } finally {
    saving.value = false
  }
}

async function deleteAgent() {
  try {
    deleting.value = true
    await agentsApi.delete(agent.value.id)
    showMessage('Agent deleted')
    router.push('/agents')
  } catch (e) {
    showMessage(e.response?.data?.detail || 'Failed to delete agent', 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadAgent()
})
</script>

<style scoped>
.command-output {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 4px;
  overflow-x: auto;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
