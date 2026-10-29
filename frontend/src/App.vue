<script setup>
import { onMounted, ref } from 'vue'
import TitleBar from './components/TitleBar.vue'
import ScreenTimeCard from './components/ScreenTimeCard.vue'
import { fetchDashboardData, fetchIgnoredApps } from './api/bridge'

const activeTab = ref('dashboard')
const selectedDate = ref(null)
const selectedHour = ref(null)
const selectedCategory = ref('all')
const dashboard = ref({})
const ignoredApps = ref([])

async function loadData(dateStr = selectedDate.value) {
  const data = await fetchDashboardData(dateStr)
  dashboard.value = data
  if (!selectedDate.value && data?.date_str) {
    selectedDate.value = data.date_str
  }
  ignoredApps.value = await fetchIgnoredApps()
}

function handleDateChange(newDate) {
  selectedDate.value = newDate
  selectedHour.value = null
  loadData(newDate)
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="flex flex-col h-screen w-screen bg-[#141417] text-zinc-100 overflow-hidden select-none">
    <TitleBar
      v-model:activeTab="activeTab"
      :always-on-top="Boolean(dashboard.always_on_top)"
      :ignored-count="ignoredApps.length"
      :active-app="dashboard.active_app"
    />

    <main class="flex-1 overflow-y-auto px-3.5 py-3 space-y-3">
      <ScreenTimeCard
        :dashboard="dashboard"
        :date-str="selectedDate"
        v-model:selectedHour="selectedHour"
        v-model:selectedCategory="selectedCategory"
        @change-date="handleDateChange"
      />
    </main>
  </div>
</template>
