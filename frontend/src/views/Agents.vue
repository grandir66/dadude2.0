<template>
  <div>
    <!-- Header -->
    <v-row class="mb-4">
      <v-col>
        <h1 class="text-h4">
          Agents
          <v-badge
            v-if="pendingAgents.length > 0"
            :content="pendingAgents.length"
            color="warning"
            inline
          ></v-badge>
        </h1>
      </v-col>
      <v-col cols="auto">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          @click="showCreateDialog = true"
        >
          Add Agent
        </v-btn>
      </v-col>
    </v-row>

    <!-- Pending Agents Section -->
    <v-expand-transition>
      <v-card v-if="pendingAgents.length > 0" class="mb-4" color="warning" variant="tonal">
        <v-card-title class="d-flex align-center">
          <v-icon start>mdi-alert-circle</v-icon>
          Pending Approval ({{ pendingAgents.length }})
          <v-spacer></v-spacer>
          <v-btn
            variant="text"
            size="small"
            @click="showPendingExpanded = !showPendingExpanded"
          >
            {{ showPendingExpanded ? 'Collapse' : 'Expand' }}
          </v-btn>
        </v-card-title>
        <v-expand-transition>
          <v-card-text v-if="showPendingExpanded">
            <v-row>
              <v-col
                v-for="agent in pendingAgents"
                :key="agent.id"
                cols="12"
                sm="6"
                md="4"
              >
                <v-card variant="outlined">
                  <v-card-item>
                    <template v-slot:prepend>
                      <v-avatar color="warning" size="40">
                        <v-icon :icon="agent.agent_type === 'docker' ? 'mdi-docker' : 'mdi-router-wireless'" color="white"></v-icon>
                      </v-avatar>
                    </template>
                    <v-card-title>{{ agent.name || 'Unknown Agent' }}</v-card-title>
                    <v-card-subtitle>{{ agent.address }}{{ agent.port ? ':' + agent.port : '' }}</v-card-subtitle>
                  </v-card-item>
                  <v-card-text>
                    <v-row dense>
                      <v-col cols="6">
                        <div class="text-caption text-grey">Type</div>
                        <v-chip size="x-small" variant="tonal">{{ agent.agent_type || 'docker' }}</v-chip>
                      </v-col>
                      <v-col cols="6">
                        <div class="text-caption text-grey">Version</div>
                        <span>{{ agent.version || '-' }}</span>
                      </v-col>
                      <v-col cols="12" v-if="agent.capabilities?.length">
                        <div class="text-caption text-grey">Capabilities</div>
                        <v-chip
                          v-for="cap in agent.capabilities.slice(0, 4)"
                          :key="cap"
                          size="x-small"
                          class="mr-1"
                          variant="tonal"
                        >
                          {{ cap }}
                        </v-chip>
                      </v-col>
                      <v-col cols="12">
                        <div class="text-caption text-grey">Registered</div>
                        <span>{{ formatDate(agent.created_at) }}</span>
                      </v-col>
                    </v-row>
                  </v-card-text>
                  <v-card-actions>
                    <v-btn
                      color="success"
                      variant="tonal"
                      size="small"
                      prepend-icon="mdi-check"
                      @click="openApproveDialog(agent)"
                    >
                      Approve
                    </v-btn>
                    <v-btn
                      color="error"
                      variant="text"
                      size="small"
                      prepend-icon="mdi-delete"
                      @click="deleteAgent(agent)"
                    >
                      Reject
                    </v-btn>
                  </v-card-actions>
                </v-card>
              </v-col>
            </v-row>
          </v-card-text>
        </v-expand-transition>
      </v-card>
    </v-expand-transition>

    <!-- Agent Cards Grid -->
    <v-row>
      <v-col
        v-for="agent in agents"
        :key="agent.id"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card
          :to="`/agents/${agent.id}`"
          hover
        >
          <v-card-item>
            <template v-slot:prepend>
              <v-avatar
                :color="agent.status === 'online' ? 'success' : 'error'"
                size="48"
              >
                <v-icon
                  :icon="agent.agent_type === 'docker' ? 'mdi-docker' : 'mdi-router-wireless'"
                  color="white"
                ></v-icon>
              </v-avatar>
            </template>
            <v-card-title>{{ agent.name }}</v-card-title>
            <v-card-subtitle>{{ agent.address }}:{{ agent.port }}</v-card-subtitle>
          </v-card-item>

          <v-card-text>
            <v-row dense>
              <v-col cols="6">
                <div class="text-caption text-grey">Status</div>
                <v-chip
                  :color="agent.status === 'online' ? 'success' : 'error'"
                  size="small"
                  variant="tonal"
                >
                  {{ agent.status || 'unknown' }}
                </v-chip>
              </v-col>
              <v-col cols="6">
                <div class="text-caption text-grey">Type</div>
                <v-chip size="small" variant="tonal">
                  {{ agent.agent_type || 'mikrotik' }}
                </v-chip>
              </v-col>
              <v-col cols="12" v-if="agent.version">
                <div class="text-caption text-grey">Version</div>
                <span>{{ agent.version }}</span>
              </v-col>
              <v-col cols="12" v-if="agent.last_seen">
                <div class="text-caption text-grey">Last Seen</div>
                <span>{{ formatDate(agent.last_seen) }}</span>
              </v-col>
            </v-row>
          </v-card-text>

          <v-card-actions>
            <v-btn
              variant="text"
              size="small"
              prepend-icon="mdi-connection"
              @click.prevent="testConnection(agent)"
              :loading="testingAgent === agent.id"
            >
              Test
            </v-btn>
            <v-btn
              variant="text"
              size="small"
              prepend-icon="mdi-radar"
              @click.prevent="startScan(agent)"
            >
              Scan
            </v-btn>
            <v-spacer></v-spacer>
            <v-btn
              icon="mdi-dots-vertical"
              size="small"
              variant="text"
            >
              <v-menu activator="parent">
                <v-list>
                  <v-list-item
                    prepend-icon="mdi-pencil"
                    title="Edit"
                    @click.stop="editAgent(agent)"
                  ></v-list-item>
                  <v-list-item
                    prepend-icon="mdi-delete"
                    title="Delete"
                    @click.stop="deleteAgent(agent)"
                  ></v-list-item>
                </v-list>
              </v-menu>
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Empty State -->
      <v-col v-if="!loading && agents.length === 0" cols="12">
        <v-card class="text-center pa-8">
          <v-icon icon="mdi-server-network-off" size="64" color="grey"></v-icon>
          <h3 class="text-h5 mt-4">No Agents Found</h3>
          <p class="text-grey mt-2">Add your first agent to start monitoring.</p>
          <v-btn
            color="primary"
            class="mt-4"
            @click="showCreateDialog = true"
          >
            Add Agent
          </v-btn>
        </v-card>
      </v-col>
    </v-row>

    <!-- Loading -->
    <v-row v-if="loading">
      <v-col v-for="i in 4" :key="i" cols="12" sm="6" md="4" lg="3">
        <v-skeleton-loader type="card"></v-skeleton-loader>
      </v-col>
    </v-row>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>Delete Agent</v-card-title>
        <v-card-text>
          Are you sure you want to delete agent <strong>{{ agentToDelete?.name }}</strong>?
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showDeleteDialog = false">Cancel</v-btn>
          <v-btn
            color="error"
            @click="confirmDelete"
            :loading="deleting"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Scan Dialog -->
    <v-dialog v-model="showScanDialog" max-width="500">
      <v-card>
        <v-card-title>Start Network Scan</v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Scanning networks via agent: <strong>{{ scanAgent?.name }}</strong>
          </v-alert>
          <v-text-field
            v-model="scanNetwork"
            label="Network CIDR"
            placeholder="192.168.1.0/24"
            hint="Enter network in CIDR format"
            persistent-hint
          ></v-text-field>
          <v-select
            v-model="scanType"
            :items="['ping', 'arp', 'snmp', 'full']"
            label="Scan Type"
            class="mt-4"
          ></v-select>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showScanDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="executeScan"
            :loading="scanning"
            :disabled="!scanNetwork"
          >
            Start Scan
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Approve Agent Dialog -->
    <v-dialog v-model="showApproveDialog" max-width="500">
      <v-card>
        <v-card-title>
          <v-icon start color="success">mdi-check-circle</v-icon>
          Approve Agent
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Approving agent: <strong>{{ agentToApprove?.name }}</strong>
            <br>
            <span class="text-grey">{{ agentToApprove?.address }}</span>
          </v-alert>
          <v-select
            v-model="approveCustomerId"
            :items="customers"
            item-title="name"
            item-value="id"
            label="Assign to Customer *"
            :rules="[v => !!v || 'Customer is required']"
            prepend-inner-icon="mdi-domain"
          ></v-select>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showApproveDialog = false">Cancel</v-btn>
          <v-btn
            color="success"
            @click="confirmApprove"
            :loading="approving"
            :disabled="!approveCustomerId"
          >
            Approve
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.text }}
    </v-snackbar>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="showCreateDialog" max-width="600">
      <v-card>
        <v-card-title>
          {{ editingAgent ? 'Edit Agent' : 'Add Agent' }}
        </v-card-title>
        <v-card-text>
          <v-form ref="form" v-model="formValid">
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="agentForm.name"
                  label="Name"
                  :rules="[v => !!v || 'Name is required']"
                  required
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="8">
                <v-text-field
                  v-model="agentForm.address"
                  label="Address (IP or hostname)"
                  :rules="[v => !!v || 'Address is required']"
                  required
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model.number="agentForm.port"
                  label="Port"
                  type="number"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="agentForm.agent_type"
                  :items="['mikrotik', 'docker']"
                  label="Agent Type"
                ></v-select>
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="agentForm.customer_id"
                  :items="customers"
                  item-title="name"
                  item-value="id"
                  label="Customer"
                  clearable
                ></v-select>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="agentForm.username"
                  label="Username"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="agentForm.password"
                  label="Password"
                  type="password"
                ></v-text-field>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="closeDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="saveAgent"
            :loading="saving"
            :disabled="!formValid"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { format, parseISO } from 'date-fns'
import { agentsApi, customersApi } from '@/services/api'
import { useWebSocketStore } from '@/stores/websocket'

const wsStore = useWebSocketStore()

// State
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const scanning = ref(false)
const approving = ref(false)
const testingAgent = ref(null)
const agents = ref([])
const pendingAgents = ref([])
const customers = ref([])
const showCreateDialog = ref(false)
const showDeleteDialog = ref(false)
const showScanDialog = ref(false)
const showApproveDialog = ref(false)
const showPendingExpanded = ref(true)
const editingAgent = ref(null)
const agentToDelete = ref(null)
const agentToApprove = ref(null)
const approveCustomerId = ref(null)
const scanAgent = ref(null)
const scanNetwork = ref('')
const scanType = ref('ping')
const formValid = ref(false)
const snackbar = ref({ show: false, text: '', color: 'success' })

const agentForm = ref({
  name: '',
  address: '',
  port: 8728,
  agent_type: 'mikrotik',
  customer_id: null,
  username: '',
  password: ''
})

// Methods
async function loadAgents() {
  try {
    loading.value = true
    const data = await agentsApi.getAll()
    agents.value = data.agents || data || []
  } catch (error) {
    console.error('Error loading agents:', error)
  } finally {
    loading.value = false
  }
}

async function loadCustomers() {
  try {
    const data = await customersApi.getAll()
    customers.value = data.customers || data || []
  } catch (error) {
    console.error('Error loading customers:', error)
  }
}

async function loadPendingAgents() {
  try {
    const data = await agentsApi.getPending()
    pendingAgents.value = data.agents || data || []
  } catch (error) {
    console.error('Error loading pending agents:', error)
    pendingAgents.value = []
  }
}

function openApproveDialog(agent) {
  agentToApprove.value = agent
  approveCustomerId.value = null
  showApproveDialog.value = true
}

async function confirmApprove() {
  if (!agentToApprove.value || !approveCustomerId.value) return

  try {
    approving.value = true
    await agentsApi.approve(agentToApprove.value.id, { customer_id: approveCustomerId.value })
    showApproveDialog.value = false
    snackbar.value = { show: true, text: `Agent "${agentToApprove.value.name}" approved successfully`, color: 'success' }
    agentToApprove.value = null
    approveCustomerId.value = null
    // Reload both lists
    loadPendingAgents()
    loadAgents()
  } catch (error) {
    console.error('Error approving agent:', error)
    snackbar.value = { show: true, text: 'Approval failed: ' + (error.response?.data?.detail || error.message), color: 'error' }
  } finally {
    approving.value = false
  }
}

async function testConnection(agent) {
  try {
    testingAgent.value = agent.id
    const result = await agentsApi.testConnection(agent.id)
    if (result.success) {
      snackbar.value = { show: true, text: result.message || 'Connection successful!', color: 'success' }
    } else {
      snackbar.value = { show: true, text: result.message || 'Connection failed', color: 'error' }
    }
  } catch (error) {
    console.error('Connection test failed:', error)
    snackbar.value = { show: true, text: 'Connection test failed: ' + (error.response?.data?.detail || error.message), color: 'error' }
  } finally {
    testingAgent.value = null
  }
}

function startScan(agent) {
  scanAgent.value = agent
  scanNetwork.value = ''
  scanType.value = 'ping'
  showScanDialog.value = true
}

async function executeScan() {
  if (!scanAgent.value || !scanNetwork.value) return

  try {
    scanning.value = true
    await agentsApi.startScan(scanAgent.value.id, {
      network: scanNetwork.value,
      scan_type: scanType.value
    })
    showScanDialog.value = false
    snackbar.value = { show: true, text: 'Scan started successfully', color: 'success' }
  } catch (error) {
    console.error('Scan failed:', error)
    snackbar.value = { show: true, text: 'Scan failed: ' + (error.response?.data?.detail || error.message), color: 'error' }
  } finally {
    scanning.value = false
  }
}

function editAgent(agent) {
  editingAgent.value = agent
  agentForm.value = { ...agent }
  showCreateDialog.value = true
}

function deleteAgent(agent) {
  agentToDelete.value = agent
  showDeleteDialog.value = true
}

async function confirmDelete() {
  if (!agentToDelete.value) return

  try {
    deleting.value = true
    await agentsApi.delete(agentToDelete.value.id)
    showDeleteDialog.value = false
    agentToDelete.value = null
    snackbar.value = { show: true, text: 'Agent deleted successfully', color: 'success' }
    loadAgents()
  } catch (error) {
    console.error('Error deleting agent:', error)
    snackbar.value = { show: true, text: 'Delete failed: ' + (error.response?.data?.detail || error.message), color: 'error' }
  } finally {
    deleting.value = false
  }
}

async function saveAgent() {
  if (!formValid.value) return

  try {
    saving.value = true

    if (editingAgent.value) {
      await agentsApi.update(editingAgent.value.id, agentForm.value)
      snackbar.value = { show: true, text: `Agent "${agentForm.value.name}" updated successfully`, color: 'success' }
    } else {
      await agentsApi.create(agentForm.value)
      snackbar.value = { show: true, text: `Agent "${agentForm.value.name}" created successfully`, color: 'success' }
    }

    closeDialog()
    loadAgents()
  } catch (error) {
    console.error('Error saving agent:', error)
    snackbar.value = { show: true, text: 'Save failed: ' + (error.response?.data?.detail || error.message), color: 'error' }
  } finally {
    saving.value = false
  }
}

function closeDialog() {
  showCreateDialog.value = false
  editingAgent.value = null
  agentForm.value = {
    name: '',
    address: '',
    port: 8728,
    agent_type: 'mikrotik',
    customer_id: null,
    username: '',
    password: ''
  }
}

function formatDate(date) {
  if (!date) return ''
  try {
    return format(parseISO(date), 'dd/MM/yyyy HH:mm')
  } catch {
    return date
  }
}

onMounted(() => {
  loadAgents()
  loadCustomers()
  loadPendingAgents()

  // Subscribe to agent status updates
  wsStore.subscribe('agent_connected', (data) => {
    const agent = agents.value.find(a => a.id === data.agent_id)
    if (agent) agent.status = 'online'
  })

  wsStore.subscribe('agent_disconnected', (data) => {
    const agent = agents.value.find(a => a.id === data.agent_id)
    if (agent) agent.status = 'offline'
  })

  // Subscribe to new agent registrations
  wsStore.subscribe('agent_registered', () => {
    loadPendingAgents()
  })
})
</script>
