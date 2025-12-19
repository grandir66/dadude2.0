<template>
  <div>
    <!-- Loading State -->
    <v-skeleton-loader v-if="loading" type="card, article, table"></v-skeleton-loader>

    <!-- Customer Content -->
    <template v-else-if="customer">
      <!-- Header -->
      <v-row class="mb-4">
        <v-col>
          <div class="d-flex align-center">
            <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()"></v-btn>
            <div class="ml-2">
              <h1 class="text-h4">{{ customer.name }}</h1>
              <p class="text-body-2 text-grey">
                <v-chip size="small" variant="tonal" class="mr-2">{{ customer.code }}</v-chip>
                <v-chip size="small" :color="customer.active ? 'success' : 'error'" variant="tonal">
                  {{ customer.active ? 'Active' : 'Inactive' }}
                </v-chip>
              </p>
            </div>
          </div>
        </v-col>
        <v-col cols="auto">
          <v-btn color="primary" prepend-icon="mdi-pencil" @click="editCustomer">
            Edit Customer
          </v-btn>
        </v-col>
      </v-row>

      <!-- Info Cards -->
      <v-row class="mb-4">
        <v-col cols="12" md="3">
          <v-card color="primary" variant="tonal">
            <v-card-text class="text-center">
              <v-icon size="32" class="mb-2">mdi-network</v-icon>
              <div class="text-h4">{{ networks.length }}</div>
              <div class="text-caption">Networks</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card color="success" variant="tonal">
            <v-card-text class="text-center">
              <v-icon size="32" class="mb-2">mdi-devices</v-icon>
              <div class="text-h4">{{ devices.length }}</div>
              <div class="text-caption">Devices</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card color="info" variant="tonal">
            <v-card-text class="text-center">
              <v-icon size="32" class="mb-2">mdi-server-network</v-icon>
              <div class="text-h4">{{ agents.length }}</div>
              <div class="text-caption">Agents</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card color="warning" variant="tonal">
            <v-card-text class="text-center">
              <v-icon size="32" class="mb-2">mdi-key</v-icon>
              <div class="text-h4">{{ credentials.length }}</div>
              <div class="text-caption">Credentials</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Tabs -->
      <v-card>
        <v-tabs v-model="activeTab" color="primary">
          <v-tab value="overview">
            <v-icon start>mdi-information</v-icon>
            Overview
          </v-tab>
          <v-tab value="networks">
            <v-icon start>mdi-network</v-icon>
            Networks ({{ networks.length }})
          </v-tab>
          <v-tab value="devices">
            <v-icon start>mdi-devices</v-icon>
            Devices ({{ devices.length }})
          </v-tab>
          <v-tab value="agents">
            <v-icon start>mdi-server-network</v-icon>
            Agents ({{ agents.length }})
          </v-tab>
          <v-tab value="credentials">
            <v-icon start>mdi-key</v-icon>
            Credentials ({{ credentials.length }})
          </v-tab>
        </v-tabs>

        <v-divider></v-divider>

        <v-window v-model="activeTab">
          <!-- Overview Tab -->
          <v-window-item value="overview">
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-list density="compact">
                    <v-list-subheader>Contact Information</v-list-subheader>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon>mdi-account</v-icon>
                      </template>
                      <v-list-item-title>Contact Name</v-list-item-title>
                      <v-list-item-subtitle>{{ customer.contact_name || '-' }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon>mdi-email</v-icon>
                      </template>
                      <v-list-item-title>Email</v-list-item-title>
                      <v-list-item-subtitle>{{ customer.contact_email || '-' }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon>mdi-phone</v-icon>
                      </template>
                      <v-list-item-title>Phone</v-list-item-title>
                      <v-list-item-subtitle>{{ customer.contact_phone || '-' }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon>mdi-map-marker</v-icon>
                      </template>
                      <v-list-item-title>Address</v-list-item-title>
                      <v-list-item-subtitle>{{ customer.address || '-' }}</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>
                <v-col cols="12" md="6">
                  <v-list density="compact">
                    <v-list-subheader>Additional Info</v-list-subheader>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon>mdi-text</v-icon>
                      </template>
                      <v-list-item-title>Description</v-list-item-title>
                      <v-list-item-subtitle>{{ customer.description || '-' }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon>mdi-note</v-icon>
                      </template>
                      <v-list-item-title>Notes</v-list-item-title>
                      <v-list-item-subtitle>{{ customer.notes || '-' }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon>mdi-calendar</v-icon>
                      </template>
                      <v-list-item-title>Created</v-list-item-title>
                      <v-list-item-subtitle>{{ formatDate(customer.created_at) }}</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>
              </v-row>
            </v-card-text>
          </v-window-item>

          <!-- Networks Tab -->
          <v-window-item value="networks">
            <v-card-text>
              <div class="d-flex justify-end mb-4">
                <v-btn color="primary" prepend-icon="mdi-plus" @click="showNetworkDialog = true">
                  Add Network
                </v-btn>
              </div>
              <v-data-table
                :headers="networkHeaders"
                :items="networks"
                :loading="loadingNetworks"
                hover
              >
                <template v-slot:item.ip_network="{ item }">
                  <code>{{ item.ip_network }}</code>
                </template>
                <template v-slot:item.vlan_id="{ item }">
                  <v-chip v-if="item.vlan_id" size="small" variant="tonal">
                    VLAN {{ item.vlan_id }}
                  </v-chip>
                  <span v-else>-</span>
                </template>
                <template v-slot:item.active="{ item }">
                  <v-icon :color="item.active ? 'success' : 'grey'">
                    {{ item.active ? 'mdi-check-circle' : 'mdi-close-circle' }}
                  </v-icon>
                </template>
                <template v-slot:item.actions="{ item }">
                  <v-btn icon="mdi-pencil" size="small" variant="text" @click="editNetwork(item)"></v-btn>
                  <v-btn icon="mdi-delete" size="small" variant="text" color="error" @click="deleteNetwork(item)"></v-btn>
                </template>
              </v-data-table>
            </v-card-text>
          </v-window-item>

          <!-- Devices Tab -->
          <v-window-item value="devices">
            <v-card-text>
              <v-data-table
                :headers="deviceHeaders"
                :items="devices"
                :loading="loadingDevices"
                hover
                @click:row="(event, { item }) => $router.push(`/devices/${item.id}`)"
              >
                <template v-slot:item.management_ip="{ item }">
                  <code>{{ item.management_ip || item.address || '-' }}</code>
                </template>
                <template v-slot:item.role="{ item }">
                  <v-chip size="small" variant="tonal">{{ item.role || 'unknown' }}</v-chip>
                </template>
                <template v-slot:item.monitored="{ item }">
                  <v-icon :color="item.monitored ? 'success' : 'grey'">
                    {{ item.monitored ? 'mdi-eye' : 'mdi-eye-off' }}
                  </v-icon>
                </template>
              </v-data-table>
            </v-card-text>
          </v-window-item>

          <!-- Agents Tab -->
          <v-window-item value="agents">
            <v-card-text>
              <div class="d-flex justify-end mb-4">
                <v-btn color="primary" prepend-icon="mdi-plus" @click="showAgentDialog = true">
                  Assign Agent
                </v-btn>
              </div>
              <v-data-table
                :headers="agentHeaders"
                :items="agents"
                :loading="loadingAgents"
                hover
                @click:row="(event, { item }) => $router.push(`/agents/${item.id}`)"
              >
                <template v-slot:item.address="{ item }">
                  <code>{{ item.address }}</code>
                </template>
                <template v-slot:item.status="{ item }">
                  <v-chip
                    :color="item.status === 'online' ? 'success' : 'error'"
                    size="small"
                    variant="tonal"
                  >
                    {{ item.status }}
                  </v-chip>
                </template>
                <template v-slot:item.agent_type="{ item }">
                  <v-chip size="small" variant="tonal">{{ item.agent_type }}</v-chip>
                </template>
              </v-data-table>
            </v-card-text>
          </v-window-item>

          <!-- Credentials Tab -->
          <v-window-item value="credentials">
            <v-card-text>
              <div class="d-flex justify-end mb-4">
                <v-btn color="primary" prepend-icon="mdi-plus" to="/credentials">
                  Manage Credentials
                </v-btn>
              </div>
              <v-data-table
                :headers="credentialHeaders"
                :items="credentials"
                :loading="loadingCredentials"
                hover
              >
                <template v-slot:item.credential_type="{ item }">
                  <v-chip size="small" variant="tonal">{{ item.credential_type }}</v-chip>
                </template>
                <template v-slot:item.username="{ item }">
                  <code>{{ item.username || '-' }}</code>
                </template>
                <template v-slot:item.is_default="{ item }">
                  <v-icon v-if="item.is_default" color="success">mdi-star</v-icon>
                </template>
              </v-data-table>
            </v-card-text>
          </v-window-item>
        </v-window>
      </v-card>
    </template>

    <!-- Not Found -->
    <v-alert v-else type="error" title="Customer not found" class="mt-4">
      The requested customer could not be found.
      <template v-slot:append>
        <v-btn variant="outlined" to="/customers">Back to Customers</v-btn>
      </template>
    </v-alert>

    <!-- Network Dialog -->
    <v-dialog v-model="showNetworkDialog" max-width="600">
      <v-card>
        <v-card-title>{{ editingNetwork ? 'Edit Network' : 'Add Network' }}</v-card-title>
        <v-card-text>
          <v-form ref="networkForm" v-model="networkFormValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="networkFormData.name"
                  label="Name *"
                  :rules="[v => !!v || 'Required']"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="networkFormData.network_type"
                  :items="['lan', 'wan', 'dmz', 'guest', 'management', 'voip']"
                  label="Type"
                ></v-select>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="networkFormData.ip_network"
                  label="Network CIDR *"
                  placeholder="192.168.1.0/24"
                  :rules="[v => !!v || 'Required']"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="networkFormData.gateway"
                  label="Gateway"
                  placeholder="192.168.1.1"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="networkFormData.vlan_id"
                  label="VLAN ID"
                  type="number"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="networkFormData.vlan_name"
                  label="VLAN Name"
                ></v-text-field>
              </v-col>
              <v-col cols="12">
                <v-textarea
                  v-model="networkFormData.description"
                  label="Description"
                  rows="2"
                ></v-textarea>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="closeNetworkDialog">Cancel</v-btn>
          <v-btn color="primary" @click="saveNetwork" :loading="savingNetwork" :disabled="!networkFormValid">
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Edit Customer Dialog -->
    <v-dialog v-model="showEditDialog" max-width="600">
      <v-card>
        <v-card-title>Edit Customer</v-card-title>
        <v-card-text>
          <v-form ref="editForm" v-model="editFormValid">
            <v-row>
              <v-col cols="12" md="4">
                <v-text-field v-model="editFormData.code" label="Code" disabled></v-text-field>
              </v-col>
              <v-col cols="12" md="8">
                <v-text-field
                  v-model="editFormData.name"
                  label="Name *"
                  :rules="[v => !!v || 'Required']"
                ></v-text-field>
              </v-col>
              <v-col cols="12">
                <v-textarea v-model="editFormData.description" label="Description" rows="2"></v-textarea>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="editFormData.contact_name" label="Contact Name"></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="editFormData.contact_email" label="Email" type="email"></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="editFormData.contact_phone" label="Phone"></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-switch v-model="editFormData.active" label="Active" color="success"></v-switch>
              </v-col>
              <v-col cols="12">
                <v-textarea v-model="editFormData.address" label="Address" rows="2"></v-textarea>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showEditDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="saveCustomer" :loading="savingCustomer" :disabled="!editFormValid">
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { customersApi, networksApi, devicesApi, agentsApi, credentialsApi } from '@/services/api'

const route = useRoute()
const router = useRouter()

// State
const loading = ref(true)
const customer = ref(null)
const activeTab = ref('overview')

// Related data
const networks = ref([])
const devices = ref([])
const agents = ref([])
const credentials = ref([])
const loadingNetworks = ref(false)
const loadingDevices = ref(false)
const loadingAgents = ref(false)
const loadingCredentials = ref(false)

// Dialogs
const showNetworkDialog = ref(false)
const showAgentDialog = ref(false)
const showEditDialog = ref(false)

// Form states
const networkForm = ref(null)
const networkFormValid = ref(false)
const editForm = ref(null)
const editFormValid = ref(false)
const editingNetwork = ref(null)
const savingNetwork = ref(false)
const savingCustomer = ref(false)

const networkFormData = ref({
  name: '',
  network_type: 'lan',
  ip_network: '',
  gateway: '',
  vlan_id: null,
  vlan_name: '',
  description: ''
})

const editFormData = ref({
  code: '',
  name: '',
  description: '',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  address: '',
  active: true
})

// Table headers
const networkHeaders = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Type', key: 'network_type', sortable: true },
  { title: 'Network', key: 'ip_network', sortable: true },
  { title: 'Gateway', key: 'gateway', sortable: true },
  { title: 'VLAN', key: 'vlan_id', sortable: true },
  { title: 'Active', key: 'active', sortable: true, align: 'center' },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' }
]

const deviceHeaders = [
  { title: 'Name', key: 'local_name', sortable: true },
  { title: 'IP', key: 'management_ip', sortable: true },
  { title: 'Role', key: 'role', sortable: true },
  { title: 'Location', key: 'location', sortable: true },
  { title: 'Monitored', key: 'monitored', sortable: true, align: 'center' }
]

const agentHeaders = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Address', key: 'address', sortable: true },
  { title: 'Type', key: 'agent_type', sortable: true },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Location', key: 'location', sortable: true }
]

const credentialHeaders = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Type', key: 'credential_type', sortable: true },
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Default', key: 'is_default', sortable: true, align: 'center' }
]

// Methods
function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

async function loadCustomer() {
  try {
    loading.value = true
    const id = route.params.id
    customer.value = await customersApi.getById(id)

    // Load related data
    loadNetworks()
    loadDevices()
    loadAgents()
    loadCredentials()
  } catch (error) {
    console.error('Error loading customer:', error)
    customer.value = null
  } finally {
    loading.value = false
  }
}

async function loadNetworks() {
  try {
    loadingNetworks.value = true
    const data = await customersApi.getNetworks(route.params.id)
    networks.value = data.networks || data.items || data || []
  } catch (error) {
    console.error('Error loading networks:', error)
    networks.value = []
  } finally {
    loadingNetworks.value = false
  }
}

async function loadDevices() {
  try {
    loadingDevices.value = true
    const data = await devicesApi.getAll({ customer_id: route.params.id })
    devices.value = data.devices || data.items || data || []
  } catch (error) {
    console.error('Error loading devices:', error)
    devices.value = []
  } finally {
    loadingDevices.value = false
  }
}

async function loadAgents() {
  try {
    loadingAgents.value = true
    const data = await agentsApi.getAll({ customer_id: route.params.id })
    agents.value = data.agents || data.items || data || []
  } catch (error) {
    console.error('Error loading agents:', error)
    agents.value = []
  } finally {
    loadingAgents.value = false
  }
}

async function loadCredentials() {
  try {
    loadingCredentials.value = true
    const data = await customersApi.getCredentials(route.params.id)
    credentials.value = data.credentials || data.items || data || []
  } catch (error) {
    console.error('Error loading credentials:', error)
    credentials.value = []
  } finally {
    loadingCredentials.value = false
  }
}

function editCustomer() {
  editFormData.value = { ...customer.value }
  showEditDialog.value = true
}

async function saveCustomer() {
  if (!editFormValid.value) return
  try {
    savingCustomer.value = true
    await customersApi.update(customer.value.id, editFormData.value)
    showEditDialog.value = false
    loadCustomer()
  } catch (error) {
    console.error('Error saving customer:', error)
  } finally {
    savingCustomer.value = false
  }
}

function editNetwork(network) {
  editingNetwork.value = network
  networkFormData.value = { ...network }
  showNetworkDialog.value = true
}

function closeNetworkDialog() {
  showNetworkDialog.value = false
  editingNetwork.value = null
  networkFormData.value = {
    name: '',
    network_type: 'lan',
    ip_network: '',
    gateway: '',
    vlan_id: null,
    vlan_name: '',
    description: ''
  }
}

async function saveNetwork() {
  if (!networkFormValid.value) return
  try {
    savingNetwork.value = true
    if (editingNetwork.value) {
      await networksApi.update(editingNetwork.value.id, networkFormData.value)
    } else {
      await networksApi.create(route.params.id, networkFormData.value)
    }
    closeNetworkDialog()
    loadNetworks()
  } catch (error) {
    console.error('Error saving network:', error)
  } finally {
    savingNetwork.value = false
  }
}

async function deleteNetwork(network) {
  if (!confirm(`Delete network "${network.name}"?`)) return
  try {
    await networksApi.delete(network.id)
    loadNetworks()
  } catch (error) {
    console.error('Error deleting network:', error)
  }
}

onMounted(() => {
  loadCustomer()
})
</script>
