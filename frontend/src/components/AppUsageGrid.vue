<script setup>
import { computed, ref, watch } from 'vue'
import { LayoutGrid, AlignLeft, Clock, FilterX } from 'lucide-vue-next'
import { CATEGORY_META, CATEGORY_ORDER, formatDuration } from '../api/bridge'
import {
  i18n,
  effectiveTheme,
  getCategoryLabel,
  getLocalizedAppName,
} from '../i18n'

const props = defineProps({
  apps: {
    type: Array,
    default: () => [],
  },
  timeline: {
    type: Array,
    default: () => [],
  },
  totalSec: {
    type: Number,
    default: 0,
  },
  activeApp: {
    type: Object,
    default: null,
  },
  selectedCategory: {
    type: String,
    default: 'all',
  },
  selectedHour: {
    type: Number,
    default: null,
  },
  defaultViewMode: {
    type: String,
    default: 'grid', // 'grid' (双列磁贴，对标参考图2) | 'list' (单列进度条排行)
  },
  categoryMeta: {
    type: Object,
    default: () => CATEGORY_META,
  },
})

const emit = defineEmits([
  'select-app',
  'update:selectedCategory',
  'select-category',
  'update:selectedHour',
  'clear-hour',
])

const viewMode = ref(props.defaultViewMode === 'list' ? 'list' : 'grid')
const t = computed(() => i18n.value)
const isLight = computed(() => effectiveTheme.value === 'light')

watch(
  () => props.defaultViewMode,
  (mode) => {
    if (mode === 'grid' || mode === 'list') {
      viewMode.value = mode
    }
  }
)

const categoryTabs = computed(() => {
  const list = [{ key: 'all', label: t.value.catAll, color: '#3B82F6' }]
  for (const key of CATEGORY_ORDER) {
    const meta = props.categoryMeta?.[key] || CATEGORY_META[key]
    if (meta) {
      list.push({
        key,
        label: getCategoryLabel(key),
        color: meta.color,
      })
    }
  }
  return list
})

// 若用户在 24 小时柱状图中选中了某个具体小时，则从 timeline 动态聚合并展示该小时内的软件使用时长
const baseAppsForPeriod = computed(() => {
  if (props.selectedHour === null || props.selectedHour === undefined) {
    return props.apps || []
  }

  const hour = Number(props.selectedHour)
  const map = new Map()

  for (const item of props.timeline || []) {
    if (Number(item.hour_bucket) !== hour) continue
    const id = item.app_id
    const existing = map.get(id)
    if (existing) {
      existing.total_sec += Number(item.duration_sec || 0)
      existing.session_count += 1
      if (item.last_window_title) {
        existing.last_window_title = item.last_window_title
      }
    } else {
      map.set(id, {
        id: item.app_id,
        exe_path: item.exe_path || '',
        exe_name: item.exe_name || '',
        display_name: item.display_name || item.exe_name || '未知应用',
        category: item.category || 'other',
        icon_base64: item.icon_base64 || '',
        total_sec: Number(item.duration_sec || 0),
        session_count: 1,
        last_window_title: item.last_window_title || '',
      })
    }
  }

  return Array.from(map.values()).sort((a, b) => b.total_sec - a.total_sec)
})

const filteredApps = computed(() => {
  const list = baseAppsForPeriod.value
  if (!props.selectedCategory || props.selectedCategory === 'all') {
    return list
  }
  return list.filter((app) => app.category === props.selectedCategory)
})

const periodTotalSec = computed(() => {
  const sum = filteredApps.value.reduce((acc, a) => acc + Number(a.total_sec || 0), 0)
  return sum > 0 ? sum : Math.max(1, Number(props.totalSec || 1))
})

function isAppActive(app) {
  if (!props.activeApp || !app) return false
  if (props.activeApp.app_id !== undefined && app.id !== undefined) {
    return Number(props.activeApp.app_id) === Number(app.id)
  }
  if (props.activeApp.exe_name && app.exe_name) {
    return props.activeApp.exe_name.toLowerCase() === app.exe_name.toLowerCase()
  }
  return false
}

function getCategoryInfo(catKey) {
  const base = props.categoryMeta?.[catKey] || CATEGORY_META[catKey] || CATEGORY_META.other
  return {
    ...base,
    label: getCategoryLabel(catKey),
  }
}

function getAppInitial(name) {
  const clean = String(getLocalizedAppName(name) || '?').trim()
  return clean.slice(0, 1).toUpperCase()
}

function handleCategorySelect(key) {
  emit('update:selectedCategory', key)
  emit('select-category', key)
}

function handleClearHour() {
  emit('update:selectedHour', null)
  emit('clear-hour')
}

function handleAppClick(app) {
  emit('select-app', app)
}
</script>

<template>
  <section class="win-surface-card rounded-2xl p-3.5 transition-all duration-200">
    <!-- 顶部栏：标题、时段过滤提示与双列/单列视图切换按钮 -->
    <div class="flex items-center justify-between gap-2 mb-2.5">
      <div class="flex items-center gap-2 min-w-0">
        <h2 class="text-[13px] font-semibold text-zinc-100 tracking-wide truncate">
          {{
            selectedHour !== null
              ? t.appGridHourTitle.replace('{hour}', String(selectedHour).padStart(2, '0'))
              : t.appGridTitle
          }}
        </h2>
        <span class="px-1.5 py-0.5 rounded-md bg-white/[0.05] text-[11px] font-medium text-zinc-400">
          {{ filteredApps.length }} {{ t.appCountSuffix }}
        </span>

        <button
          v-if="selectedHour !== null"
          type="button"
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-500/15 border border-blue-500/30 text-[11px] hover:bg-blue-500/25 transition-colors"
          :class="isLight ? 'text-blue-600' : 'text-blue-300'"
          @click="handleClearHour"
        >
          <FilterX class="w-3 h-3" />
          <span>{{ t.btnAllDay }}</span>
        </button>
      </div>

      <!-- 双列磁贴 / 单列进度条视图切换器 (修复浅色模式下黑底黑字问题) -->
      <div
        class="inline-flex items-center p-0.5 rounded-lg border shrink-0 transition-colors"
        :class="
          isLight
            ? 'bg-[#EBEBEF] border-black/[0.06]'
            : 'bg-[#15151B] border-white/[0.06]'
        "
      >
        <button
          type="button"
          class="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-all duration-150 cursor-pointer"
          :class="
            viewMode === 'grid'
              ? isLight
                ? 'bg-white text-zinc-900 shadow-sm font-semibold'
                : 'bg-[#272733] text-white shadow-sm'
              : isLight
                ? 'text-zinc-500 hover:text-zinc-800'
                : 'text-zinc-400 hover:text-zinc-200'
          "
          :title="t.viewGridTip"
          @click="viewMode = 'grid'"
        >
          <LayoutGrid class="w-3.5 h-3.5" />
          <span>{{ t.viewGrid }}</span>
        </button>

        <button
          type="button"
          class="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-all duration-150 cursor-pointer"
          :class="
            viewMode === 'list'
              ? isLight
                ? 'bg-white text-zinc-900 shadow-sm font-semibold'
                : 'bg-[#272733] text-white shadow-sm'
              : isLight
                ? 'text-zinc-500 hover:text-zinc-800'
                : 'text-zinc-400 hover:text-zinc-200'
          "
          :title="t.viewListTip"
          @click="viewMode = 'list'"
        >
          <AlignLeft class="w-3.5 h-3.5" />
          <span>{{ t.viewList }}</span>
        </button>
      </div>
    </div>

    <!-- 分类筛选胶囊栏 -->
    <div class="flex items-center gap-1.5 overflow-x-auto pb-2 mb-2 no-scrollbar">
      <button
        v-for="tab in categoryTabs"
        :key="tab.key"
        type="button"
        class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium whitespace-nowrap transition-all duration-150 border shrink-0 cursor-pointer"
        :class="
          selectedCategory === tab.key
            ? isLight
              ? 'bg-blue-500/12 text-blue-600 border-blue-500/30 font-semibold shadow-sm'
              : 'bg-white/[0.1] text-white border-white/[0.18] shadow-sm'
            : 'bg-white/[0.02] text-zinc-400 border-white/[0.04] hover:bg-white/[0.05] hover:text-zinc-200'
        "
        @click="handleCategorySelect(tab.key)"
      >
        <span
          v-if="tab.key !== 'all'"
          class="w-1.5 h-1.5 rounded-full"
          :style="{ backgroundColor: tab.color }"
        ></span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- 视图模式 1：软件图标磁贴视图 (默认双列，窗口拉宽时自动扩展为3~4列) -->
    <div
      v-if="viewMode === 'grid' && filteredApps.length > 0"
      class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5"
    >
      <button
        v-for="app in filteredApps"
        :key="app.id"
        type="button"
        class="win-tile-card group relative flex items-center gap-3 p-2.5 rounded-xl text-left cursor-pointer focus:outline-none"
        @click="handleAppClick(app)"
      >
        <!-- 左侧 38x38 软件真实圆角图标 + 活跃呼吸绿点 -->
        <div class="relative w-[38px] h-[38px] shrink-0">
          <img
            v-if="app.icon_base64"
            :src="app.icon_base64"
            :alt="getLocalizedAppName(app.display_name)"
            class="w-[38px] h-[38px] rounded-[10px] object-contain bg-white/[0.04] p-0.5 border border-white/[0.06] group-hover:scale-[1.03] transition-transform duration-150"
          />
          <div
            v-else
            class="w-[38px] h-[38px] rounded-[10px] flex items-center justify-center text-[15px] font-bold text-white border border-white/[0.1]"
            :style="{ backgroundColor: getCategoryInfo(app.category).color }"
          >
            {{ getAppInitial(app.display_name) }}
          </div>

          <!-- 当前前台活跃软件绿色呼吸指示点 -->
          <span
            v-if="isAppActive(app)"
            class="absolute -bottom-0.5 -right-0.5 flex h-3 w-3 items-center justify-center rounded-full p-0.5"
            :class="isLight ? 'bg-white' : 'bg-[#18181F]'"
            :title="t.activeInForeground"
          >
            <span class="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
        </div>

        <!-- 右侧：上方软件名 + 下方累计时长 -->
        <div class="flex flex-col min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <span class="text-[13px] font-semibold text-zinc-100 truncate">
              {{ getLocalizedAppName(app.display_name) }}
            </span>
          </div>
          <div class="flex items-center gap-1.5 mt-0.5">
            <span class="text-[12px] font-medium text-zinc-400 truncate">
              {{ formatDuration(app.total_sec) }}
            </span>
            <span
              class="w-1.5 h-1.5 rounded-full shrink-0 opacity-75"
              :style="{ backgroundColor: getCategoryInfo(app.category).color }"
              :title="getCategoryInfo(app.category).label"
            ></span>
          </div>
        </div>
      </button>
    </div>

    <!-- 视图模式 2：单列进度条详细排行视图 -->
    <div
      v-else-if="viewMode === 'list' && filteredApps.length > 0"
      class="space-y-2"
    >
      <button
        v-for="(app, index) in filteredApps"
        :key="app.id"
        type="button"
        class="win-tile-card group w-full flex flex-col gap-2 p-2.5 rounded-xl text-left cursor-pointer focus:outline-none"
        @click="handleAppClick(app)"
      >
        <div class="flex items-center gap-2.5 w-full">
          <!-- 排名序号 -->
          <span
            class="w-5 text-center text-[12px] font-bold shrink-0"
            :class="
              index === 0
                ? 'text-amber-500'
                : index === 1
                  ? 'text-zinc-400'
                  : index === 2
                    ? 'text-amber-600'
                    : 'text-zinc-500'
            "
          >
            {{ index + 1 }}
          </span>

          <!-- 38x38 软件图标 -->
          <div class="relative w-[36px] h-[36px] shrink-0">
            <img
              v-if="app.icon_base64"
              :src="app.icon_base64"
              :alt="getLocalizedAppName(app.display_name)"
              class="w-[36px] h-[36px] rounded-[9px] object-contain bg-white/[0.04] p-0.5 border border-white/[0.06]"
            />
            <div
              v-else
              class="w-[36px] h-[36px] rounded-[9px] flex items-center justify-center text-[14px] font-bold text-white"
              :style="{ backgroundColor: getCategoryInfo(app.category).color }"
            >
              {{ getAppInitial(app.display_name) }}
            </div>

            <span
              v-if="isAppActive(app)"
              class="absolute -bottom-0.5 -right-0.5 flex h-2.5 w-2.5 items-center justify-center rounded-full"
              :class="isLight ? 'bg-white' : 'bg-[#18181F]'"
            >
              <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </div>

          <!-- 软件名、分类胶囊与最近窗口标题 -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1.5">
              <span class="text-[13px] font-semibold text-zinc-100 truncate">
                {{ getLocalizedAppName(app.display_name) }}
              </span>
              <span
                class="px-1.5 py-0.2 rounded text-[10px] font-medium shrink-0"
                :style="{
                  backgroundColor: `${getCategoryInfo(app.category).color}22`,
                  color: getCategoryInfo(app.category).color,
                }"
              >
                {{ getCategoryInfo(app.category).label }}
              </span>
            </div>
            <p class="text-[11px] text-zinc-500 truncate mt-0.5">
              {{ app.last_window_title || app.exe_name }}
            </p>
          </div>

          <!-- 右侧时长与占比 -->
          <div class="text-right shrink-0">
            <div class="text-[13px] font-semibold text-zinc-200">
              {{ formatDuration(app.total_sec) }}
            </div>
            <div class="text-[11px] text-zinc-500 font-mono">
              {{ Math.min(100, Math.round((app.total_sec / periodTotalSec) * 100)) }}%
            </div>
          </div>
        </div>

        <!-- 底部彩色进度条 -->
        <div class="w-full h-1.5 rounded-full bg-white/[0.05] overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-300"
            :style="{
              width: `${Math.max(3, Math.min(100, (app.total_sec / periodTotalSec) * 100))}%`,
              backgroundColor: getCategoryInfo(app.category).color,
            }"
          ></div>
        </div>
      </button>
    </div>

    <!-- 空状态占位 -->
    <div
      v-else
      class="flex flex-col items-center justify-center py-8 text-center rounded-xl bg-white/[0.02] border border-dashed border-white/[0.06]"
    >
      <Clock class="w-6 h-6 text-zinc-500 mb-2" />
      <p class="text-[12px] text-zinc-400 font-medium">
        {{ selectedHour !== null ? t.emptyHourApps : t.emptyApps }}
      </p>
      <button
        v-if="selectedCategory !== 'all' || selectedHour !== null"
        type="button"
        class="mt-2 px-3 py-1 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-[11px] text-zinc-300 transition-colors cursor-pointer"
        @click="
          handleCategorySelect('all');
          handleClearHour();
        "
      >
        {{ t.resetFilter }}
      </button>
    </div>
  </section>
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
