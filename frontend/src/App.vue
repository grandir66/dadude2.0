<template>
  <v-app>
    <!-- Navigation Drawer -->
    <v-navigation-drawer
      v-model="drawer"
      :rail="rail"
      permanent
    >
      <v-list-item
        prepend-avatar="https://cdn.vuetifyjs.com/images/logos/vuetify-logo-dark.png"
        title="DaDude v2.0"
        subtitle="Network Monitoring"
        nav
      >
        <template v-slot:append>
          <v-btn
            variant="text"
            :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
            @click.stop="rail = !rail"
          ></v-btn>
        </template>
      </v-list-item>

      <v-divider></v-divider>

      <v-list density="compact" nav>
        <v-list-item
          v-for="item in menuItems"
          :key="item.title"
          :prepend-icon="item.icon"
          :title="item.title"
          :to="item.to"
          :value="item.value"
        ></v-list-item>
      </v-list>

      <template v-slot:append>
        <div class="pa-2">
          <v-btn
            block
            :prepend-icon="isDark ? 'mdi-white-balance-sunny' : 'mdi-moon-waning-crescent'"
            @click="toggleTheme"
          >
            {{ isDark ? 'Light' : 'Dark' }}
          </v-btn>
        </div>
      </template>
    </v-navigation-drawer>

    <!-- App Bar -->
    <v-app-bar elevation="1">
      <v-app-bar-nav-icon @click="drawer = !drawer"></v-app-bar-nav-icon>
      <v-toolbar-title>{{ currentPageTitle }}</v-toolbar-title>

      <v-spacer></v-spacer>

      <!-- Connection Status -->
      <v-chip
        :color="connectionStatus.color"
        variant="tonal"
        class="mr-2"
      >
        <v-icon start :icon="connectionStatus.icon"></v-icon>
        {{ connectionStatus.text }}
      </v-chip>

      <!-- Notifications -->
      <v-btn icon="mdi-bell-outline" class="mr-2">
        <v-badge
          :content="notificationCount"
          :model-value="notificationCount > 0"
          color="error"
        >
          <v-icon>mdi-bell-outline</v-icon>
        </v-badge>
      </v-btn>

      <!-- User Menu -->
      <v-menu>
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-avatar color="primary" size="32">
              <span class="text-h6">A</span>
            </v-avatar>
          </v-btn>
        </template>
        <v-list>
          <v-list-item prepend-icon="mdi-account" title="Profile"></v-list-item>
          <v-list-item prepend-icon="mdi-cog" title="Settings" to="/settings"></v-list-item>
          <v-divider></v-divider>
          <v-list-item prepend-icon="mdi-logout" title="Logout"></v-list-item>
        </v-list>
      </v-menu>
    </v-app-bar>

    <!-- Main Content -->
    <v-main>
      <v-container fluid>
        <router-view></router-view>
      </v-container>
    </v-main>

    <!-- Snackbar for notifications -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="snackbar.timeout"
    >
      {{ snackbar.text }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from 'vuetify'
import { useWebSocketStore } from '@/stores/websocket'
import { useNotificationStore } from '@/stores/notifications'

const route = useRoute()
const theme = useTheme()
const wsStore = useWebSocketStore()
const notificationStore = useNotificationStore()

// State
const drawer = ref(true)
const rail = ref(false)
const snackbar = ref({
  show: false,
  text: '',
  color: 'success',
  timeout: 3000
})

// Menu items
const menuItems = [
  { title: 'Dashboard', icon: 'mdi-view-dashboard', to: '/', value: 'dashboard' },
  { title: 'Customers', icon: 'mdi-domain', to: '/customers', value: 'customers' },
  { title: 'Agents', icon: 'mdi-server-network', to: '/agents', value: 'agents' },
  { title: 'Devices', icon: 'mdi-devices', to: '/devices', value: 'devices' },
  { title: 'Discovery', icon: 'mdi-radar', to: '/discovery', value: 'discovery' },
  { title: 'Credentials', icon: 'mdi-key', to: '/credentials', value: 'credentials' },
  { title: 'Backups', icon: 'mdi-backup-restore', to: '/backups', value: 'backups' },
  { title: 'Alerts', icon: 'mdi-bell-alert', to: '/alerts', value: 'alerts' },
  { title: 'Settings', icon: 'mdi-cog', to: '/settings', value: 'settings' },
]

// Computed
const isDark = computed(() => theme.global.current.value.dark)

const currentPageTitle = computed(() => {
  const item = menuItems.find(m => m.to === route.path)
  return item?.title || 'DaDude'
})

const connectionStatus = computed(() => {
  if (wsStore.connected) {
    return { color: 'success', icon: 'mdi-check-circle', text: 'Connected' }
  }
  return { color: 'error', icon: 'mdi-alert-circle', text: 'Disconnected' }
})

const notificationCount = computed(() => notificationStore.unreadCount)

// Methods
function toggleTheme() {
  theme.global.name.value = isDark.value ? 'dadudeLightTheme' : 'dadudeDarkTheme'
}
</script>

<style>
.v-navigation-drawer {
  transition: all 0.2s ease-in-out;
}
</style>
