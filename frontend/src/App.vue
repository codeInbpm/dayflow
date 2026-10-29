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
import SettingsModal from './components/SettingsModal.vue'
import {
  CATEGORY_META,
  CATEGORY_ORDER,
  fetchDashboardData,
  fetchIgnoredApps,
  fetchPreferences,
  updateAppSettings,
  startWindowResize,
  formatDuration,
} from './api/bridge'
import { i18n, applyPreferencesToDom } from './i18n'

const activeTab = ref('dashboard')
const selectedDate = ref(null)
const selectedPeriod = ref('day') // 'day' | 'week' | 'month'
const selectedHour = ref(null)
const selectedCategory = ref('all')
const timelineSortDesc = ref(true)

const dashboard = ref({})
const ignoredApps = ref([])

// 软件详情抽屉与设置弹窗状态
const isDetailOpen = ref(false)
const activeModalApp = ref(null)
const detailModalRef = ref(null)
const isSettingsOpen = ref(false)

let pollTimer = null
let mediaQueryList = null

const t = computed(() => i18n.value)

const categoryMeta = computed(() => dashboard.value?.category_meta || CATEGORY_META)

const categoryFilterPills = computed(() => {
  const list = [{ key: 'all', label: t.value.catAll, color: '#3B82F6' }]
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
      selectedPeriod.value === 'day' &&
      selectedHour.value !== null &&
      selectedHour.value !== undefined &&
      Number(item.hour_bucket) !== Number(selectedHour.value)
    ) {
      return false
    }
    return true
  })

  return [...filtered].sort((a, b) => {
    const dateCmp = String(a.date_str || '').localeCompare(String(b.date_str || ''))
    const cmp =
      dateCmp ||
      a.hour_bucket - b.hour_bucket ||
      String(a.start_time).localeCompare(String(b.start_time))
    return timelineSortDesc.value ? -cmp : cmp
  })
})

function getCategoryInfo(catKey) {
  return categoryMeta.value[catKey] || CATEGORY_META[catKey] || CATEGORY_META.other
}

async function loadData(
  dateStr = selectedDate.value,
  silent = false,
  period = selectedPeriod.value
) {
  try {
    const data = await fetchDashboardData(dateStr, period)
    if (data) {
      dashboard.value = data
      if (!selectedDate.value && data.date_str) {
        selectedDate.value = data.date_str
      }
      if (!silent && data.preferences) {
        applyPreferencesToDom(data.preferences)
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
  loadData(newDate, false, selectedPeriod.value)
}

function handlePeriodChange(newPeriod) {
  selectedPeriod.value = newPeriod
  selectedHour.value = null
  loadData(selectedDate.value, false, newPeriod)
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
  await loadData(selectedDate.value, false, selectedPeriod.value)
}

async function handleRestoreIgnoredApp(app) {
  if (!app?.id) return
  await updateAppSettings(app.id, { is_ignored: false })
  await loadData(selectedDate.value, false, selectedPeriod.value)
}

function handleAlwaysOnTopSync(val) {
  dashboard.value = {
    ...dashboard.value,
    always_on_top: Boolean(val),
  }
}

function handleSystemThemeChange() {
  applyPreferencesToDom()
}

function handleResizeMouseDown(edge, event) {
  if (event && event.button !== 0) return
  event?.preventDefault?.()
  event?.stopPropagation?.()
  startWindowResize(edge)
}

onMounted(async () => {
  try {
    const prefs = await fetchPreferences()
    if (prefs) {
      applyPreferencesToDom(prefs)
    }
  } catch (_e) {
    // ignore
  }
  loadData()
  pollTimer = setInterval(() => {
    loadData(selectedDate.value, true, selectedPeriod.value)
  }, 2000)

  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    mediaQueryList = window.matchMedia('(prefers-color-scheme: light)')
    mediaQueryList.addEventListener?.('change', handleSystemThemeChange)
  }
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (mediaQueryList) {
    mediaQueryList.removeEventListener?.('change', handleSystemThemeChange)
  }
})
</script>

<template>
  <div class="app-root-shell flex flex-col h-screen w-screen bg-[#141417] text-zinc-100 overflow-hidden select-none">
    <!-- 顶部无边框窗口控制栏与四合一胶囊导航 -->
    <TitleBar
      v-model:activeTab="activeTab"
      :always-on-top="Boolean(dashboard.always_on_top)"
      :ignored-count="ignoredApps.length"
      :active-app="dashboard.active_app"
      @open-settings="isSettingsOpen = true"
      @update:always-on-top="handleAlwaysOnTopSync"
    />

    <!-- 主内容滚动视图 -->
    <main class="flex-1 overflow-y-auto px-3.5 py-3 space-y-3">
      <!-- Tab 1: 今日看板 (支持每日/每周/每月汇总切换 + 分色柱状图 + 双列软件图标网格) -->
      <template v-if="activeTab === 'dashboard' || activeTab === 'overview'">
        <ScreenTimeCard
          :dashboard="dashboard"
          :date-str="selectedDate"
          v-model:period="selectedPeriod"
          v-model:selectedHour="selectedHour"
          v-model:selectedCategory="selectedCategory"
          @change-date="handleDateChange"
          @change-period="handlePeriodChange"
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
              {{ dashboard.period_label || selectedDate || dashboard.date_str || '今日' }} · {{ t.rankingTitleSuffix }}
            </span>
          </div>
          <div class="text-[12px] font-semibold text-blue-500">
            {{ t.totalPrefix }} {{ formatDuration(dashboard.total_sec || 0) }}
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

      <!-- Tab 3: 时段流水 (所有软件按时间段顺序排列的使用明细流水) -->
      <template v-else-if="activeTab === 'timeline'">
        <section class="win-surface-card rounded-2xl p-3.5 space-y-3">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <Clock3 class="w-4 h-4 text-blue-400" />
              <h2 class="text-[13px] font-semibold text-zinc-100">
                {{ t.timelineTitle }} ({{ dashboard.period_label || '今日' }})
              </h2>
              <span class="px-1.5 py-0.5 rounded-md bg-white/[0.05] text-[11px] text-zinc-400">
                {{ filteredTimeline.length }} {{ t.recordsSuffix }}
              </span>
            </div>

            <button
              type="button"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] text-[11px] font-medium text-zinc-300 transition-colors cursor-pointer"
              @click="timelineSortDesc = !timelineSortDesc"
            >
              <ArrowUpDown class="w-3 h-3 text-blue-400" />
              <span>{{ timelineSortDesc ? t.sortNewest : t.sortChrono }}</span>
            </button>
          </div>

          <!-- 分类过滤胶囊 -->
          <div class="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            <button
              v-for="pill in categoryFilterPills"
              :key="pill.key"
              type="button"
              class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium whitespace-nowrap transition-all border shrink-0 cursor-pointer"
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
                  <span
                    v-if="selectedPeriod !== 'day' && record.date_str"
                    class="px-1.5 py-0.5 rounded bg-blue-500/15 text-[10.5px] font-mono text-blue-400 shrink-0"
                  >
                    {{ record.date_str.slice(5) }}
                  </span>
                  <span class="px-1.5 py-0.5 rounded bg-white/[0.06] text-[11px] font-mono font-semibold text-zinc-200 shrink-0">
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
            {{ t.emptyTimeline }}
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
                {{ t.ignoredListTitle }}
              </h2>
            </div>
            <span class="text-[11px] text-zinc-500">
              {{ t.ignoredHint }}
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
                class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-[11px] font-medium text-emerald-500 transition-colors shrink-0 cursor-pointer"
                @click="handleRestoreIgnoredApp(app)"
              >
                <Eye class="w-3.5 h-3.5" />
                <span>{{ t.restoreTrack }}</span>
              </button>
            </div>
          </div>

          <div
            v-else
            class="flex flex-col items-center justify-center py-10 text-center rounded-xl bg-white/[0.02] border border-dashed border-white/[0.06]"
          >
            <ShieldAlert class="w-6 h-6 text-zinc-500 mb-2" />
            <p class="text-[12px] text-zinc-400">{{ t.emptyIgnored }}</p>
            <p class="text-[11px] text-zinc-500 mt-1">
              {{ t.emptyIgnoredSub }}
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

    <!-- 微信桌面版风格设置面板（通用：语言/外观/字体大小滑块/开机自启 + 关于 Dayflow：版本号） -->
    <SettingsModal
      v-model="isSettingsOpen"
      :always-on-top="Boolean(dashboard.always_on_top)"
      @update:always-on-top="handleAlwaysOnTopSync"
    />

    <!-- 无边框窗口八向拖拽缩放热区（四边 + 四角 + 右下角斜纹缩放手柄） -->
    <!-- 上边 (n) -->
    <div
      class="fixed top-0 left-3 right-3 h-1.5 z-[60] cursor-ns-resize"
      @mousedown="handleResizeMouseDown('n', $event)"
    ></div>
    <!-- 下边 (s) -->
    <div
      class="fixed bottom-0 left-3 right-3 h-1.5 z-[60] cursor-ns-resize"
      @mousedown="handleResizeMouseDown('s', $event)"
    ></div>
    <!-- 左边 (w) -->
    <div
      class="fixed left-0 top-3 bottom-3 w-1.5 z-[60] cursor-ew-resize"
      @mousedown="handleResizeMouseDown('w', $event)"
    ></div>
    <!-- 右边 (e) -->
    <div
      class="fixed right-0 top-3 bottom-3 w-1.5 z-[60] cursor-ew-resize"
      @mousedown="handleResizeMouseDown('e', $event)"
    ></div>
    <!-- 左上角 (nw) -->
    <div
      class="fixed top-0 left-0 w-3 h-3 z-[61] cursor-nwse-resize"
      @mousedown="handleResizeMouseDown('nw', $event)"
    ></div>
    <!-- 右上角 (ne) -->
    <div
      class="fixed top-0 right-0 w-3 h-3 z-[61] cursor-nesw-resize"
      @mousedown="handleResizeMouseDown('ne', $event)"
    ></div>
    <!-- 左下角 (sw) -->
    <div
      class="fixed bottom-0 left-0 w-3 h-3 z-[61] cursor-nesw-resize"
      @mousedown="handleResizeMouseDown('sw', $event)"
    ></div>
    <!-- 右下角 (se) 带精致斜纹角标提示 -->
    <div
      class="fixed bottom-0 right-0 w-4 h-4 z-[61] cursor-nwse-resize flex items-end justify-end p-0.5 opacity-40 hover:opacity-90 transition-opacity"
      title="按住拖动可调整窗口大小"
      @mousedown="handleResizeMouseDown('se', $event)"
    >
      <svg class="w-2.5 h-2.5 text-zinc-400 pointer-events-none" viewBox="0 0 10 10" fill="none">
        <path d="M9 1L1 9M9 5L5 9M9 8.5L8.5 9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
      </svg>
    </div>
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
