<template>
  <div>
    <!-- Header -->
    <v-row class="mb-4">
      <v-col>
        <h1 class="text-h4">Credentials</h1>
        <p class="text-body-2 text-grey">Manage credentials for device access (SSH, SNMP, MikroTik API, etc.)</p>
      </v-col>
      <v-col cols="auto">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          @click="openCreateDialog"
        >
          Add Credential
        </v-btn>
      </v-col>
    </v-row>

    <!-- Filters -->
    <v-card class="mb-4">
      <v-card-text>
        <v-row>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="search"
              prepend-inner-icon="mdi-magnify"
              label="Search credentials..."
              variant="outlined"
              density="compact"
              hide-details
              clearable
            ></v-text-field>
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="typeFilter"
              :items="credentialTypes"
              label="Type"
              variant="outlined"
              density="compact"
              hide-details
              clearable
            ></v-select>
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="customerFilter"
              :items="customerOptions"
              item-title="name"
              item-value="id"
              label="Customer"
              variant="outlined"
              density="compact"
              hide-details
              clearable
            ></v-select>
          </v-col>
          <v-col cols="12" md="2">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-refresh"
              @click="loadCredentials"
              :loading="loading"
              block
            >
              Refresh
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Stats Cards -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card color="primary" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.total }}</div>
            <div class="text-caption">Total</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="success" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.global }}</div>
            <div class="text-caption">Global</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="info" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.ssh }}</div>
            <div class="text-caption">SSH</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="warning" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.snmp }}</div>
            <div class="text-caption">SNMP</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Credentials Table -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="filteredCredentials"
        :loading="loading"
        :search="search"
        item-value="id"
        hover
      >
        <template v-slot:item.credential_type="{ item }">
          <v-chip
            :color="getTypeColor(item.credential_type)"
            size="small"
            variant="tonal"
          >
            <v-icon start size="small">{{ getTypeIcon(item.credential_type) }}</v-icon>
            {{ item.credential_type }}
          </v-chip>
        </template>

        <template v-slot:item.customer="{ item }">
          <v-chip
            v-if="item.is_global"
            color="success"
            size="small"
            variant="tonal"
          >
            <v-icon start size="small">mdi-earth</v-icon>
            Global
          </v-chip>
          <span v-else>{{ item.customer_name || item.customer_id || '-' }}</span>
        </template>

        <template v-slot:item.username="{ item }">
          <code v-if="item.username">{{ item.username }}</code>
          <span v-else class="text-grey">-</span>
        </template>

        <template v-slot:item.active="{ item }">
          <v-icon
            :color="item.active ? 'success' : 'grey'"
            size="small"
          >
            {{ item.active ? 'mdi-check-circle' : 'mdi-close-circle' }}
          </v-icon>
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn
            icon="mdi-eye"
            size="small"
            variant="text"
            @click="viewCredential(item)"
            title="View details"
          ></v-btn>
          <v-btn
            icon="mdi-pencil"
            size="small"
            variant="text"
            @click="editCredential(item)"
            title="Edit"
          ></v-btn>
          <v-btn
            icon="mdi-connection"
            size="small"
            variant="text"
            color="info"
            @click="testCredential(item)"
            title="Test connection"
          ></v-btn>
          <v-btn
            icon="mdi-delete"
            size="small"
            variant="text"
            color="error"
            @click="deleteCredential(item)"
            title="Delete"
          ></v-btn>
        </template>
      </v-data-table>
    </v-card>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="showDialog" max-width="800" persistent>
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center">
          <span>{{ isEditing ? 'Edit Credential' : 'Add Credential' }}</span>
          <v-btn icon="mdi-close" variant="text" @click="closeDialog"></v-btn>
        </v-card-title>

        <v-divider></v-divider>

        <v-card-text>
          <v-form ref="form" v-model="formValid">
            <v-row>
              <!-- Basic Info -->
              <v-col cols="12">
                <div class="text-subtitle-2 mb-2">Basic Information</div>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="credentialForm.name"
                  label="Name *"
                  :rules="[v => !!v || 'Name is required']"
                  placeholder="e.g., Router Admin, Switch Default"
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-select
                  v-model="credentialForm.credential_type"
                  :items="credentialTypeOptions"
                  label="Type *"
                  :rules="[v => !!v || 'Type is required']"
                ></v-select>
              </v-col>

              <v-col cols="12" md="6">
                <v-select
                  v-model="credentialForm.customer_id"
                  :items="customerOptions"
                  item-title="name"
                  item-value="id"
                  label="Customer"
                  clearable
                  hint="Leave empty for global credential"
                  persistent-hint
                ></v-select>
              </v-col>

              <v-col cols="12" md="6">
                <v-switch
                  v-model="credentialForm.is_global"
                  label="Global (available to all customers)"
                  color="success"
                  :disabled="!!credentialForm.customer_id"
                ></v-switch>
              </v-col>

              <!-- Authentication -->
              <v-col cols="12">
                <v-divider class="my-2"></v-divider>
                <div class="text-subtitle-2 mb-2">Authentication</div>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="credentialForm.username"
                  label="Username"
                  autocomplete="off"
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="credentialForm.password"
                  label="Password"
                  :type="showPassword ? 'text' : 'password'"
                  :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                  @click:append-inner="showPassword = !showPassword"
                  autocomplete="new-password"
                ></v-text-field>
              </v-col>

              <!-- SSH Settings (conditional) -->
              <template v-if="credentialForm.credential_type === 'ssh'">
                <v-col cols="12">
                  <v-divider class="my-2"></v-divider>
                  <div class="text-subtitle-2 mb-2">SSH Settings</div>
                </v-col>

                <v-col cols="12" md="4">
                  <v-text-field
                    v-model.number="credentialForm.ssh_port"
                    label="SSH Port"
                    type="number"
                    placeholder="22"
                  ></v-text-field>
                </v-col>

                <v-col cols="12" md="4">
                  <v-select
                    v-model="credentialForm.ssh_key_type"
                    :items="['rsa', 'ed25519', 'ecdsa']"
                    label="Key Type"
                    clearable
                  ></v-select>
                </v-col>

                <v-col cols="12">
                  <v-textarea
                    v-model="credentialForm.ssh_private_key"
                    label="Private Key (PEM format)"
                    rows="4"
                    placeholder="-----BEGIN RSA PRIVATE KEY-----"
                  ></v-textarea>
                </v-col>
              </template>

              <!-- SNMP Settings (conditional) -->
              <template v-if="credentialForm.credential_type === 'snmp'">
                <v-col cols="12">
                  <v-divider class="my-2"></v-divider>
                  <div class="text-subtitle-2 mb-2">SNMP Settings</div>
                </v-col>

                <v-col cols="12" md="4">
                  <v-select
                    v-model="credentialForm.snmp_version"
                    :items="['1', '2c', '3']"
                    label="SNMP Version"
                  ></v-select>
                </v-col>

                <v-col cols="12" md="4">
                  <v-text-field
                    v-model="credentialForm.snmp_community"
                    label="Community String"
                    placeholder="public"
                  ></v-text-field>
                </v-col>

                <v-col cols="12" md="4">
                  <v-text-field
                    v-model.number="credentialForm.snmp_port"
                    label="SNMP Port"
                    type="number"
                    placeholder="161"
                  ></v-text-field>
                </v-col>

                <!-- SNMPv3 specific -->
                <template v-if="credentialForm.snmp_version === '3'">
                  <v-col cols="12" md="4">
                    <v-select
                      v-model="credentialForm.snmp_security_level"
                      :items="['noAuthNoPriv', 'authNoPriv', 'authPriv']"
                      label="Security Level"
                    ></v-select>
                  </v-col>

                  <v-col cols="12" md="4">
                    <v-select
                      v-model="credentialForm.snmp_auth_protocol"
                      :items="['MD5', 'SHA', 'SHA256', 'SHA512']"
                      label="Auth Protocol"
                    ></v-select>
                  </v-col>

                  <v-col cols="12" md="4">
                    <v-select
                      v-model="credentialForm.snmp_priv_protocol"
                      :items="['DES', 'AES', 'AES256']"
                      label="Privacy Protocol"
                    ></v-select>
                  </v-col>
                </template>
              </template>

              <!-- MikroTik API Settings (conditional) -->
              <template v-if="credentialForm.credential_type === 'mikrotik'">
                <v-col cols="12">
                  <v-divider class="my-2"></v-divider>
                  <div class="text-subtitle-2 mb-2">MikroTik API Settings</div>
                </v-col>

                <v-col cols="12" md="6">
                  <v-text-field
                    v-model.number="credentialForm.mikrotik_api_port"
                    label="API Port"
                    type="number"
                    placeholder="8728"
                  ></v-text-field>
                </v-col>

                <v-col cols="12" md="6">
                  <v-switch
                    v-model="credentialForm.mikrotik_api_ssl"
                    label="Use SSL (port 8729)"
                    color="primary"
                  ></v-switch>
                </v-col>
              </template>

              <!-- Description -->
              <v-col cols="12">
                <v-divider class="my-2"></v-divider>
              </v-col>

              <v-col cols="12">
                <v-textarea
                  v-model="credentialForm.description"
                  label="Description"
                  rows="2"
                ></v-textarea>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="credentialForm.device_filter"
                  label="Device Filter Pattern"
                  placeholder="e.g., router-*, sw-*"
                  hint="Regex pattern to match device names"
                  persistent-hint
                ></v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-row>
                  <v-col>
                    <v-switch
                      v-model="credentialForm.is_default"
                      label="Default for customer"
                      color="primary"
                    ></v-switch>
                  </v-col>
                  <v-col>
                    <v-switch
                      v-model="credentialForm.active"
                      label="Active"
                      color="success"
                    ></v-switch>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>

        <v-divider></v-divider>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="closeDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="saveCredential"
            :loading="saving"
            :disabled="!formValid"
          >
            {{ isEditing ? 'Update' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- View Detail Dialog -->
    <v-dialog v-model="showViewDialog" max-width="600">
      <v-card v-if="selectedCredential">
        <v-card-title>
          <v-icon start>{{ getTypeIcon(selectedCredential.credential_type) }}</v-icon>
          {{ selectedCredential.name }}
        </v-card-title>

        <v-card-text>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title>Type</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip :color="getTypeColor(selectedCredential.credential_type)" size="small">
                  {{ selectedCredential.credential_type }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-title>Username</v-list-item-title>
              <v-list-item-subtitle>
                <code>{{ selectedCredential.username || '-' }}</code>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-title>Password</v-list-item-title>
              <v-list-item-subtitle>
                <code>{{ showViewPassword ? selectedCredential.password : '********' }}</code>
                <v-btn
                  :icon="showViewPassword ? 'mdi-eye-off' : 'mdi-eye'"
                  size="x-small"
                  variant="text"
                  @click="showViewPassword = !showViewPassword"
                ></v-btn>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="selectedCredential.is_global">
              <v-list-item-title>Scope</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip color="success" size="small">Global</v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="selectedCredential.description">
              <v-list-item-title>Description</v-list-item-title>
              <v-list-item-subtitle>{{ selectedCredential.description }}</v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-title>Created</v-list-item-title>
              <v-list-item-subtitle>{{ formatDate(selectedCredential.created_at) }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showViewDialog = false">Close</v-btn>
          <v-btn color="primary" @click="editCredential(selectedCredential); showViewDialog = false">
            Edit
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Test Dialog -->
    <v-dialog v-model="showTestDialog" max-width="500">
      <v-card>
        <v-card-title>Test Credential</v-card-title>
        <v-card-text>
          <p class="mb-4">Test connection with credential: <strong>{{ credentialToTest?.name }}</strong></p>
          <v-text-field
            v-model="testTargetIp"
            label="Target IP Address"
            placeholder="192.168.1.1"
            :rules="[v => !!v || 'IP is required']"
          ></v-text-field>
          <v-alert v-if="testResult" :type="testResult.success ? 'success' : 'error'" class="mt-4">
            {{ testResult.message }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showTestDialog = false">Close</v-btn>
          <v-btn color="primary" @click="runTest" :loading="testing" :disabled="!testTargetIp">
            Test
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">Delete Credential</v-card-title>
        <v-card-text>
          Are you sure you want to delete <strong>{{ credentialToDelete?.name }}</strong>?
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showDeleteDialog = false">Cancel</v-btn>
          <v-btn color="error" @click="confirmDelete" :loading="deleting">
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { credentialsApi, customersApi } from '@/services/api'

// State
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const testing = ref(false)
const credentials = ref([])
const customers = ref([])
const search = ref('')
const typeFilter = ref(null)
const customerFilter = ref(null)

// Dialogs
const showDialog = ref(false)
const showViewDialog = ref(false)
const showTestDialog = ref(false)
const showDeleteDialog = ref(false)
const showPassword = ref(false)
const showViewPassword = ref(false)

// Form
const form = ref(null)
const formValid = ref(false)
const isEditing = ref(false)
const selectedCredential = ref(null)
const credentialToDelete = ref(null)
const credentialToTest = ref(null)
const testTargetIp = ref('')
const testResult = ref(null)

const emptyForm = {
  name: '',
  credential_type: 'ssh',
  customer_id: null,
  is_global: false,
  username: '',
  password: '',
  ssh_port: 22,
  ssh_key_type: null,
  ssh_private_key: '',
  snmp_version: '2c',
  snmp_community: 'public',
  snmp_port: 161,
  snmp_security_level: null,
  snmp_auth_protocol: null,
  snmp_priv_protocol: null,
  mikrotik_api_port: 8728,
  mikrotik_api_ssl: false,
  description: '',
  device_filter: '',
  is_default: false,
  active: true
}

const credentialForm = ref({ ...emptyForm })

// Options
const credentialTypes = ['All', 'ssh', 'snmp', 'mikrotik', 'wmi', 'api', 'device']
const credentialTypeOptions = [
  { title: 'SSH', value: 'ssh' },
  { title: 'SNMP', value: 'snmp' },
  { title: 'MikroTik API', value: 'mikrotik' },
  { title: 'WMI (Windows)', value: 'wmi' },
  { title: 'Generic API', value: 'api' },
  { title: 'Device (generic)', value: 'device' }
]

// Table headers
const headers = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Type', key: 'credential_type', sortable: true },
  { title: 'Customer', key: 'customer', sortable: true },
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Active', key: 'active', sortable: true, align: 'center' },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center', width: '180px' }
]

// Computed
const customerOptions = computed(() => [
  { name: '-- Global --', id: null },
  ...customers.value
])

const filteredCredentials = computed(() => {
  let result = credentials.value

  if (typeFilter.value && typeFilter.value !== 'All') {
    result = result.filter(c => c.credential_type === typeFilter.value)
  }

  if (customerFilter.value) {
    result = result.filter(c => c.customer_id === customerFilter.value)
  }

  return result
})

const stats = computed(() => ({
  total: credentials.value.length,
  global: credentials.value.filter(c => c.is_global).length,
  ssh: credentials.value.filter(c => c.credential_type === 'ssh').length,
  snmp: credentials.value.filter(c => c.credential_type === 'snmp').length
}))

// Methods
function getTypeColor(type) {
  const colors = {
    ssh: 'blue',
    snmp: 'orange',
    mikrotik: 'purple',
    wmi: 'cyan',
    api: 'green',
    device: 'grey'
  }
  return colors[type] || 'grey'
}

function getTypeIcon(type) {
  const icons = {
    ssh: 'mdi-console',
    snmp: 'mdi-network',
    mikrotik: 'mdi-router-wireless',
    wmi: 'mdi-microsoft-windows',
    api: 'mdi-api',
    device: 'mdi-devices'
  }
  return icons[type] || 'mdi-key'
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

async function loadCredentials() {
  try {
    loading.value = true
    const data = await credentialsApi.getAll()
    credentials.value = data.credentials || data.items || data || []
  } catch (error) {
    console.error('Error loading credentials:', error)
    credentials.value = []
  } finally {
    loading.value = false
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

function openCreateDialog() {
  isEditing.value = false
  credentialForm.value = { ...emptyForm }
  showPassword.value = false
  showDialog.value = true
}

function editCredential(credential) {
  isEditing.value = true
  selectedCredential.value = credential
  credentialForm.value = { ...credential }
  showPassword.value = false
  showDialog.value = true
}

function viewCredential(credential) {
  selectedCredential.value = credential
  showViewPassword.value = false
  showViewDialog.value = true
}

function deleteCredential(credential) {
  credentialToDelete.value = credential
  showDeleteDialog.value = true
}

function testCredential(credential) {
  credentialToTest.value = credential
  testTargetIp.value = ''
  testResult.value = null
  showTestDialog.value = true
}

function closeDialog() {
  showDialog.value = false
  isEditing.value = false
  credentialForm.value = { ...emptyForm }
}

async function saveCredential() {
  if (!formValid.value) return

  try {
    saving.value = true

    // Clean up form data
    const data = { ...credentialForm.value }
    if (!data.customer_id) {
      data.customer_id = null
    }

    if (isEditing.value && selectedCredential.value) {
      await credentialsApi.update(selectedCredential.value.id, data)
    } else {
      await credentialsApi.create(data)
    }

    closeDialog()
    loadCredentials()
  } catch (error) {
    console.error('Error saving credential:', error)
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!credentialToDelete.value) return

  try {
    deleting.value = true
    await credentialsApi.delete(credentialToDelete.value.id)
    showDeleteDialog.value = false
    credentialToDelete.value = null
    loadCredentials()
  } catch (error) {
    console.error('Error deleting credential:', error)
  } finally {
    deleting.value = false
  }
}

async function runTest() {
  if (!credentialToTest.value || !testTargetIp.value) return

  try {
    testing.value = true
    testResult.value = null
    const result = await credentialsApi.test(credentialToTest.value.id, testTargetIp.value)
    testResult.value = {
      success: result.success,
      message: result.message || (result.success ? 'Connection successful!' : 'Connection failed')
    }
  } catch (error) {
    testResult.value = {
      success: false,
      message: error.response?.data?.detail || error.message || 'Test failed'
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadCredentials()
  loadCustomers()
})
</script>
