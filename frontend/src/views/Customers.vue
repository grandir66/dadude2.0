<template>
  <div>
    <!-- Header -->
    <v-row class="mb-4">
      <v-col>
        <h1 class="text-h4">Customers</h1>
      </v-col>
      <v-col cols="auto">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          @click="showCreateDialog = true"
        >
          Add Customer
        </v-btn>
      </v-col>
    </v-row>

    <!-- Search and Filters -->
    <v-card class="mb-4">
      <v-card-text>
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="search"
              prepend-inner-icon="mdi-magnify"
              label="Search customers..."
              variant="outlined"
              density="compact"
              hide-details
              clearable
            ></v-text-field>
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="statusFilter"
              :items="['All', 'Active', 'Inactive']"
              label="Status"
              variant="outlined"
              density="compact"
              hide-details
            ></v-select>
          </v-col>
          <v-col cols="12" md="3">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-refresh"
              @click="loadCustomers"
              :loading="loading"
            >
              Refresh
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Customers Table -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="filteredCustomers"
        :loading="loading"
        :search="search"
        item-value="id"
        hover
        @click:row="(event, { item }) => goToCustomer(item)"
      >
        <template v-slot:item.active="{ item }">
          <v-chip
            :color="item.active ? 'success' : 'error'"
            size="small"
            variant="tonal"
          >
            {{ item.active ? 'Active' : 'Inactive' }}
          </v-chip>
        </template>

        <template v-slot:item.networks_count="{ item }">
          <v-chip size="small" variant="tonal">
            {{ item.networks_count || 0 }}
          </v-chip>
        </template>

        <template v-slot:item.devices_count="{ item }">
          <v-chip size="small" variant="tonal">
            {{ item.devices_count || 0 }}
          </v-chip>
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn
            icon="mdi-pencil"
            size="small"
            variant="text"
            @click.stop="editCustomer(item)"
          ></v-btn>
          <v-btn
            icon="mdi-delete"
            size="small"
            variant="text"
            color="error"
            @click.stop="deleteCustomer(item)"
          ></v-btn>
        </template>
      </v-data-table>
    </v-card>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="showCreateDialog" max-width="600">
      <v-card>
        <v-card-title>
          {{ editingCustomer ? 'Edit Customer' : 'Add Customer' }}
        </v-card-title>
        <v-card-text>
          <v-form ref="form" v-model="formValid">
            <v-row>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="customerForm.code"
                  label="Code"
                  :rules="[v => !!v || 'Code is required']"
                  required
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="8">
                <v-text-field
                  v-model="customerForm.name"
                  label="Name"
                  :rules="[v => !!v || 'Name is required']"
                  required
                ></v-text-field>
              </v-col>
              <v-col cols="12">
                <v-textarea
                  v-model="customerForm.description"
                  label="Description"
                  rows="2"
                ></v-textarea>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="customerForm.contact_name"
                  label="Contact Name"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="customerForm.contact_email"
                  label="Contact Email"
                  type="email"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="customerForm.contact_phone"
                  label="Contact Phone"
                ></v-text-field>
              </v-col>
              <v-col cols="12" md="6">
                <v-switch
                  v-model="customerForm.active"
                  label="Active"
                  color="success"
                ></v-switch>
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="closeDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            @click="saveCustomer"
            :loading="saving"
            :disabled="!formValid"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>Delete Customer</v-card-title>
        <v-card-text>
          Are you sure you want to delete <strong>{{ customerToDelete?.name }}</strong>?
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { customersApi } from '@/services/api'

const router = useRouter()

// State
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const customers = ref([])
const search = ref('')
const statusFilter = ref('All')
const showCreateDialog = ref(false)
const showDeleteDialog = ref(false)
const editingCustomer = ref(null)
const customerToDelete = ref(null)
const formValid = ref(false)
const form = ref(null)

const customerForm = ref({
  code: '',
  name: '',
  description: '',
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  active: true
})

// Table headers
const headers = [
  { title: 'Code', key: 'code', sortable: true },
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Contact', key: 'contact_name', sortable: true },
  { title: 'Networks', key: 'networks_count', sortable: true, align: 'center' },
  { title: 'Devices', key: 'devices_count', sortable: true, align: 'center' },
  { title: 'Status', key: 'active', sortable: true, align: 'center' },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' }
]

// Computed
const filteredCustomers = computed(() => {
  let result = customers.value

  if (statusFilter.value === 'Active') {
    result = result.filter(c => c.active)
  } else if (statusFilter.value === 'Inactive') {
    result = result.filter(c => !c.active)
  }

  return result
})

// Methods
async function loadCustomers() {
  try {
    loading.value = true
    const data = await customersApi.getAll({ active_only: false })
    customers.value = data.customers || data || []
  } catch (error) {
    console.error('Error loading customers:', error)
  } finally {
    loading.value = false
  }
}

function goToCustomer(customer) {
  router.push(`/customers/${customer.id}`)
}

function editCustomer(customer) {
  editingCustomer.value = customer
  customerForm.value = { ...customer }
  showCreateDialog.value = true
}

function deleteCustomer(customer) {
  customerToDelete.value = customer
  showDeleteDialog.value = true
}

async function saveCustomer() {
  if (!formValid.value) return

  try {
    saving.value = true

    if (editingCustomer.value) {
      await customersApi.update(editingCustomer.value.id, customerForm.value)
    } else {
      await customersApi.create(customerForm.value)
    }

    closeDialog()
    loadCustomers()
  } catch (error) {
    console.error('Error saving customer:', error)
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!customerToDelete.value) return

  try {
    deleting.value = true
    await customersApi.delete(customerToDelete.value.id)
    showDeleteDialog.value = false
    customerToDelete.value = null
    loadCustomers()
  } catch (error) {
    console.error('Error deleting customer:', error)
  } finally {
    deleting.value = false
  }
}

function closeDialog() {
  showCreateDialog.value = false
  editingCustomer.value = null
  customerForm.value = {
    code: '',
    name: '',
    description: '',
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    active: true
  }
}

onMounted(() => {
  loadCustomers()
})
</script>
