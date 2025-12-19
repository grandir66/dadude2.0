<template>
  <div>
    <!-- Header -->
    <v-row class="mb-4">
      <v-col>
        <h1 class="text-h4">Agents</h1>
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
const testingAgent = ref(null)
const agents = ref([])
const customers = ref([])
const showCreateDialog = ref(false)
const editingAgent = ref(null)
const formValid = ref(false)

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

async function testConnection(agent) {
  try {
    testingAgent.value = agent.id
    await agentsApi.testConnection(agent.id)
  } catch (error) {
    console.error('Connection test failed:', error)
  } finally {
    testingAgent.value = null
  }
}

function startScan(agent) {
  // Emit to start scan
  wsStore.send('start_scan', { agent_id: agent.id })
}

function editAgent(agent) {
  editingAgent.value = agent
  agentForm.value = { ...agent }
  showCreateDialog.value = true
}

function deleteAgent(agent) {
  // TODO: Implement delete confirmation
  console.log('Delete agent:', agent)
}

async function saveAgent() {
  if (!formValid.value) return

  try {
    saving.value = true

    if (editingAgent.value) {
      await agentsApi.update(editingAgent.value.id, agentForm.value)
    } else {
      await agentsApi.create(agentForm.value)
    }

    closeDialog()
    loadAgents()
  } catch (error) {
    console.error('Error saving agent:', error)
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

  // Subscribe to agent status updates
  wsStore.subscribe('agent_connected', (data) => {
    const agent = agents.value.find(a => a.id === data.agent_id)
    if (agent) agent.status = 'online'
  })

  wsStore.subscribe('agent_disconnected', (data) => {
    const agent = agents.value.find(a => a.id === data.agent_id)
    if (agent) agent.status = 'offline'
  })
})
</script>
