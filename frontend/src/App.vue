<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  Clock3,
  ArrowUpDown,
  Eye,
  EyeOff,
  Terminal,
  ShieldAlert,
  Calendar,
} from 'lucide-vue-next'
import TitleBar from './components/TitleBar.vue'
import ScreenTimeCard from './components/ScreenTimeCard.vue'
import AppUsageGrid from './components/AppUsageGrid.vue'
import AppDetailModal from './components/AppDetailModal.vue'
import {
  CATEGORY_META,
  CATEGORY_ORDER,
  fetchDashboardData,
  fetchIgnoredApps,
  updateAppSettings,
  formatDuration,
} from './api/bridge'

const activeTab = ref('dashboard')
const selectedDate = ref(null)
const selectedHour = ref(null)
const selectedCategory = ref('all')
const timelineSortDesc = ref(true)

const dashboard = ref({})
const ignoredApps = ref([])

// 软件详情抽屉状态
const isDetailOpen = ref(false)
const activeModalApp = ref(null)
const detailModalRef = ref(null)

let pollTimer = null

const categoryMeta = computed(() => dashboard.value?.category_meta || CATEGORY_META)

const categoryFilterPills = computed(() => {
  const list = [{ key: 'all', label: '全部', color: '#3B82F6' }]
  for (const key of CATEGORY_ORDER) {
    const meta = categoryMeta.value[key] || CATEGORY_META[key]
    if (meta) {
      list.push({
        key,
        label: meta.label,
        color: meta.color,
      })
    }
  }
  return list
})

// 全局时段流水列表过滤与排序
const filteredTimeline = computed(() => {
  const raw = dashboard.value?.timeline || []
  const filtered = raw.filter((item) => {
    if (selectedCategory.value !== 'all' && item.category !== selectedCategory.value) {
      return false
    }
    if (
      selectedHour.value !== null &&
      selectedHour.value !== undefined &&
      Number(item.hour_bucket) !== Number(selectedHour.value)
    ) {
      return false
    }
    return true
  })

  return [...filtered].sort((a, b) => {
    const cmp =
      a.hour_bucket - b.hour_bucket ||
      String(a.start_time).localeCompare(String(b.start_time))
    return timelineSortDesc.value ? -cmp : cmp
  })
})

function getCategoryInfo(catKey) {
  return categoryMeta.value[catKey] || CATEGORY_META[catKey] || CATEGORY_META.other
}

async function loadData(dateStr = selectedDate.value, silent = false) {
  try {
    const data = await fetchDashboardData(dateStr)
    if (data) {
      dashboard.value = data
      if (!selectedDate.value && data.date_str) {
        selectedDate.value = data.date_str
      }
    }
    ignoredApps.value = await fetchIgnoredApps()
    if (silent && isDetailOpen.value && detailModalRef.value) {
      detailModalRef.value.refresh()
    }
  } catch (err) {
    console.error('Failed to load Dayflow dashboard data:', err)
  }
}

function handleDateChange(newDate) {
  selectedDate.value = newDate
  selectedHour.value = null
  loadData(newDate)
}

function handleOpenAppDetail(appItem) {
  if (!appItem) return
  activeModalApp.value = {
    ...appItem,
    id: appItem.id ?? appItem.app_id,
  }
  isDetailOpen.value = true
}

async function handleAppUpdated() {
  await loadData(selectedDate.value, false)
}

async function handleRestoreIgnoredApp(app) {
  if (!app?.id) return
  await updateAppSettings(app.id, { is_ignored: false })
  await loadData(selectedDate.value, false)
}

onMounted(() => {
  loadData()
  pollTimer = setInterval(() => {
    loadData(selectedDate.value, true)
  }, 2000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="flex flex-col h-screen w-screen bg-[#141417] text-zinc-100 overflow-hidden select-none">
    <!-- 顶部无边框窗口控制栏与四合一胶囊导航 -->
    <TitleBar
      v-model:activeTab="activeTab"
      :always-on-top="Boolean(dashboard.always_on_top)"
      :ignored-count="ignoredApps.length"
      :active-app="dashboard.active_app"
    />

    <!-- 主内容滚动视图 -->
    <main class="flex-1 overflow-y-auto px-3.5 py-3 space-y-3">
      <!-- Tab 1: 今日看板 (复刻参考图2上部分24h分色柱状图 + 下部分双列软件图标网格) -->
      <template v-if="activeTab === 'dashboard' || activeTab === 'overview'">
        <ScreenTimeCard
          :dashboard="dashboard"
          :date-str="selectedDate"
          v-model:selectedHour="selectedHour"
          v-model:selectedCategory="selectedCategory"
          @change-date="handleDateChange"
        />

        <AppUsageGrid
          :apps="dashboard.apps || []"
          :timeline="dashboard.timeline || []"
          :total-sec="Number(dashboard.total_sec || 0)"
          :active-app="dashboard.active_app"
          :category-meta="categoryMeta"
          v-model:selectedCategory="selectedCategory"
          v-model:selectedHour="selectedHour"
          default-view-mode="grid"
          @select-app="handleOpenAppDetail"
        />
      </template>

      <!-- Tab 2: 应用排行 (单列进度条详细排行视图) -->
      <template v-else-if="activeTab === 'ranking'">
        <div class="win-surface-card rounded-2xl px-4 py-3 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Calendar class="w-4 h-4 text-blue-400" />
            <span class="text-[12px] font-semibold text-zinc-200">
              {{ selectedDate || dashboard.date_str || '今日' }} 软件时长排行
            </span>
          </div>
          <div class="text-[12px] font-semibold text-blue-400">
            总计 {{ formatDuration(dashboard.total_sec || 0) }}
          </div>
        </div>

        <AppUsageGrid
          :apps="dashboard.apps || []"
          :timeline="dashboard.timeline || []"
          :total-sec="Number(dashboard.total_sec || 0)"
          :active-app="dashboard.active_app"
          :category-meta="categoryMeta"
          v-model:selectedCategory="selectedCategory"
          v-model:selectedHour="selectedHour"
          default-view-mode="list"
          @select-app="handleOpenAppDetail"
        />
      </template>

      <!-- Tab 3: 时段流水 (全天所有软件按时间段顺序排列的使用明细流水) -->
      <template v-else-if="activeTab === 'timeline'">
        <section class="win-surface-card rounded-2xl p-3.5 space-y-3">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <Clock3 class="w-4 h-4 text-blue-400" />
              <h2 class="text-[13px] font-semibold text-zinc-100">
                全天时段使用流水
              </h2>
              <span class="px-1.5 py-0.5 rounded-md bg-white/[0.05] text-[11px] text-zinc-400">
                {{ filteredTimeline.length }} 条记录
              </span>
            </div>

            <button
              type="button"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] text-[11px] font-medium text-zinc-300 transition-colors"
              @click="timelineSortDesc = !timelineSortDesc"
            >
              <ArrowUpDown class="w-3 h-3 text-blue-400" />
              <span>{{ timelineSortDesc ? '最新时段在前' : '00:00 顺序排列' }}</span>
            </button>
          </div>

          <!-- 分类过滤胶囊 -->
          <div class="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            <button
              v-for="pill in categoryFilterPills"
              :key="pill.key"
              type="button"
              class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium whitespace-nowrap transition-all border shrink-0"
              :class="
                selectedCategory === pill.key
                  ? 'bg-white/[0.1] text-white border-white/[0.18]'
                  : 'bg-white/[0.02] text-zinc-400 border-white/[0.04] hover:bg-white/[0.05] hover:text-zinc-200'
              "
              @click="selectedCategory = pill.key"
            >
              <span
                v-if="pill.key !== 'all'"
                class="w-1.5 h-1.5 rounded-full"
                :style="{ backgroundColor: pill.color }"
              ></span>
              <span>{{ pill.label }}</span>
            </button>
          </div>

          <!-- 时间轴流水卡片列表 -->
          <div v-if="filteredTimeline.length > 0" class="space-y-2">
            <button
              v-for="record in filteredTimeline"
              :key="record.id"
              type="button"
              class="win-tile-card w-full flex items-center gap-3 p-2.5 rounded-xl text-left cursor-pointer focus:outline-none"
              @click="handleOpenAppDetail(record)"
            >
              <!-- 软件图标 -->
              <img
                v-if="record.icon_base64"
                :src="record.icon_base64"
                :alt="record.display_name"
                class="w-9 h-9 rounded-[9px] object-contain bg-white/[0.04] p-0.5 border border-white/[0.06] shrink-0"
              />
              <div
                v-else
                class="w-9 h-9 rounded-[9px] flex items-center justify-center text-[13px] font-bold text-white shrink-0"
                :style="{ backgroundColor: getCategoryInfo(record.category).color }"
              >
                {{ String(record.display_name || '?').slice(0, 1).toUpperCase() }}
              </div>

              <!-- 中间：时间区间 + 软件名称 + 窗口标题 -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="px-1.5 py-0.5 rounded bg-white/[0.06] text-[11px] font-mono font-semibold text-zinc-200">
                    {{ record.start_time }} - {{ record.end_time }}
                  </span>
                  <span class="text-[12px] font-semibold text-white truncate">
                    {{ record.display_name }}
                  </span>
                </div>
                <div class="flex items-center gap-1.5 mt-1 text-[11px] text-zinc-400 truncate">
                  <Terminal class="w-3 h-3 text-zinc-500 shrink-0" />
                  <span class="truncate">
                    {{ record.last_window_title || record.exe_name }}
                  </span>
                </div>
              </div>

              <!-- 右侧：单次时长与分类点 -->
              <div class="text-right shrink-0">
                <span
                  class="inline-block px-2 py-0.5 rounded-lg text-[11px] font-semibold"
                  :style="{
                    backgroundColor: `${getCategoryInfo(record.category).color}20`,
                    color: getCategoryInfo(record.category).color,
                  }"
                >
                  {{ formatDuration(record.duration_sec) }}
                </span>
                <div class="text-[10px] text-zinc-500 mt-0.5">
                  {{ getCategoryInfo(record.category).label }}
                </div>
              </div>
            </button>
          </div>

          <div
            v-else
            class="py-10 text-center rounded-xl bg-white/[0.02] border border-dashed border-white/[0.06] text-[12px] text-zinc-500"
          >
            当前筛选条件下暂无时段使用流水
          </div>
        </section>
      </template>

      <!-- Tab 4: 已屏蔽软件管理 -->
      <template v-else-if="activeTab === 'ignored'">
        <section class="win-surface-card rounded-2xl p-3.5 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <EyeOff class="w-4 h-4 text-zinc-400" />
              <h2 class="text-[13px] font-semibold text-zinc-100">
                已屏蔽的软件名单
              </h2>
            </div>
            <span class="text-[11px] text-zinc-500">
              不计入屏幕使用时长
            </span>
          </div>

          <div v-if="ignoredApps.length > 0" class="space-y-2">
            <div
              v-for="app in ignoredApps"
              :key="app.id"
              class="win-tile-card flex items-center justify-between gap-3 p-2.5 rounded-xl"
            >
              <div class="flex items-center gap-3 min-w-0">
                <img
                  v-if="app.icon_base64"
                  :src="app.icon_base64"
                  :alt="app.display_name"
                  class="w-9 h-9 rounded-[9px] object-contain bg-white/[0.04] p-0.5 border border-white/[0.06] shrink-0"
                />
                <div
                  v-else
                  class="w-9 h-9 rounded-[9px] flex items-center justify-center text-[13px] font-bold text-white bg-zinc-700 shrink-0"
                >
                  {{ String(app.display_name || '?').slice(0, 1).toUpperCase() }}
                </div>

                <div class="min-w-0">
                  <div class="text-[13px] font-semibold text-zinc-100 truncate">
                    {{ app.display_name }}
                  </div>
                  <div class="text-[11px] text-zinc-500 font-mono truncate">
                    {{ app.exe_name || app.exe_path }}
                  </div>
                </div>
              </div>

              <button
                type="button"
                class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-[11px] font-medium text-emerald-300 transition-colors shrink-0"
                @click="handleRestoreIgnoredApp(app)"
              >
                <Eye class="w-3.5 h-3.5" />
                <span>恢复统计</span>
              </button>
            </div>
          </div>

          <div
            v-else
            class="flex flex-col items-center justify-center py-10 text-center rounded-xl bg-white/[0.02] border border-dashed border-white/[0.06]"
          >
            <ShieldAlert class="w-6 h-6 text-zinc-500 mb-2" />
            <p class="text-[12px] text-zinc-400">当前没有被屏蔽的软件</p>
            <p class="text-[11px] text-zinc-500 mt-1">
              可在任意软件的详情面板中点击“屏蔽此软件”将其排除统计
            </p>
          </div>
        </section>
      </template>
    </main>

    <!-- 软件使用时间段流水与设置详情面板 -->
    <AppDetailModal
      ref="detailModalRef"
      v-model="isDetailOpen"
      :app-id="activeModalApp?.id ?? null"
      :initial-app="activeModalApp"
      :date-str="selectedDate || dashboard.date_str"
      :active-app="dashboard.active_app"
      :category-meta="categoryMeta"
      @updated="handleAppUpdated"
    />
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
