<script setup>
import { computed, ref, watch } from 'vue'
import {
  Pin,
  Minus,
  X,
  Settings,
  LayoutDashboard,
  BarChart3,
  Clock3,
  EyeOff,
} from 'lucide-vue-next'
import { toggleAlwaysOnTop, minimizeWindow, quitApp } from '../api/bridge'
import { i18n, effectiveTheme, getLocalizedAppName } from '../i18n'

const props = defineProps({
  activeTab: {
    type: String,
    default: 'dashboard',
  },
  modelValue: {
    type: String,
    default: '',
  },
  alwaysOnTop: {
    type: Boolean,
    default: false,
  },
  ignoredCount: {
    type: Number,
    default: 0,
  },
  activeApp: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits([
  'update:activeTab',
  'update:modelValue',
  'tab-change',
  'change-tab',
  'toggle-pin',
  'update:alwaysOnTop',
  'open-settings',
  'minimize',
  'close',
])

const isPinned = ref(props.alwaysOnTop)
const t = computed(() => i18n.value)
const isLight = computed(() => effectiveTheme.value === 'light')

watch(
  () => props.alwaysOnTop,
  (val) => {
    isPinned.value = Boolean(val)
  }
)

const currentTab = computed(() => props.modelValue || props.activeTab || 'dashboard')

const navTabs = computed(() => [
  { key: 'dashboard', label: t.value.tabDashboard, icon: LayoutDashboard },
  { key: 'ranking', label: t.value.tabRanking, icon: BarChart3 },
  { key: 'timeline', label: t.value.tabTimeline, icon: Clock3 },
  { key: 'ignored', label: t.value.tabIgnored, icon: EyeOff },
])

function selectTab(key) {
  emit('update:activeTab', key)
  emit('update:modelValue', key)
  emit('tab-change', key)
  emit('change-tab', key)
}

async function handleTogglePin() {
  const nextState = !isPinned.value
  const res = await toggleAlwaysOnTop(nextState)
  const finalState = res?.always_on_top !== undefined ? Boolean(res.always_on_top) : nextState
  isPinned.value = finalState
  emit('update:alwaysOnTop', finalState)
  emit('toggle-pin', finalState)
}

function handleOpenSettings() {
  emit('open-settings')
}

async function handleMinimize() {
  await minimizeWindow()
  emit('minimize')
}

async function handleCloseApp() {
  await quitApp()
  emit('close')
}

function handleDragPointerDown(e) {
  if (e.button !== 0) return
  if (e.target && typeof e.target.closest === 'function' && e.target.closest('button')) {
    return
  }
  try {
    e.currentTarget?.setPointerCapture?.(e.pointerId)
  } catch (_err) {
    // ignore
  }
}

function handleDragPointerUp(e) {
  try {
    if (e.currentTarget?.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  } catch (_err) {
    // ignore
  }
}
</script>

<template>
  <header
    class="titlebar-shell pywebview-drag-region shrink-0 bg-[#141417]/95 backdrop-blur-md border-b border-white/[0.06] z-30 cursor-move"
    @pointerdown="handleDragPointerDown"
    @pointerup="handleDragPointerUp"
    @pointercancel="handleDragPointerUp"
  >
    <!-- 第一行：Windows 11 无边框标题栏与窗口控制按钮 -->
    <div class="flex items-center justify-between h-10 px-3.5">
      <!-- 左侧品牌标识与拖拽区域 -->
      <div class="flex items-center gap-2.5 flex-1 min-w-0 h-full">
        <!-- 四色 Windows 桌面风格几何品牌图标 -->
        <div class="grid grid-cols-2 gap-[2px] w-4 h-4 p-[1px] rounded-[4px] bg-white/[0.04] shrink-0">
          <span class="rounded-[1.5px] bg-[#3B82F6]"></span>
          <span class="rounded-[1.5px] bg-[#06B6D4]"></span>
          <span class="rounded-[1.5px] bg-[#10B981]"></span>
          <span class="rounded-[1.5px] bg-[#F59E0B]"></span>
        </div>

        <div class="flex items-center gap-2 min-w-0">
          <span class="text-[13px] font-semibold tracking-wide text-zinc-100 truncate">
            Dayflow
          </span>
          <span class="text-[11px] text-zinc-500 hidden sm:inline">{{ t.appSubTitle }}</span>
        </div>

        <!-- 当前前台采集状态胶囊 -->
        <div
          v-if="activeApp && activeApp.display_name"
          class="ml-1 flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 max-w-[150px]"
          :title="`${t.recording}: ${getLocalizedAppName(activeApp.display_name)}`"
        >
          <span class="relative flex h-1.5 w-1.5 shrink-0">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
          </span>
          <span class="text-[11px] text-emerald-500 font-medium truncate">
            {{ getLocalizedAppName(activeApp.display_name) }}
          </span>
        </div>
      </div>

      <!-- 右侧：设置齿轮、置顶图钉、最小化、关闭并退出 -->
      <div class="flex items-center gap-1 shrink-0 ml-2 cursor-default" @mousedown.stop @pointerdown.stop>
        <button
          type="button"
          class="flex items-center justify-center w-7 h-7 rounded-lg text-zinc-400 hover:bg-white/[0.07] hover:text-zinc-200 transition-colors duration-150 cursor-pointer"
          :title="t.openSettings"
          @mousedown.stop
          @pointerdown.stop
          @click="handleOpenSettings"
        >
          <Settings class="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          class="group relative flex items-center justify-center w-7 h-7 rounded-lg transition-all duration-150 border cursor-pointer"
          :class="
            isPinned
              ? 'bg-emerald-500/15 text-emerald-500 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
              : 'bg-transparent text-zinc-400 border-transparent hover:bg-white/[0.07] hover:text-zinc-200'
          "
          :title="isPinned ? t.pinActive : t.pinInactive"
          @mousedown.stop
          @pointerdown.stop
          @click="handleTogglePin"
        >
          <Pin class="w-3.5 h-3.5 transition-transform duration-150" :class="isPinned ? '-rotate-45 fill-emerald-400/25' : ''" />
        </button>

        <button
          type="button"
          class="flex items-center justify-center w-7 h-7 rounded-lg text-zinc-400 hover:bg-white/[0.07] hover:text-zinc-200 transition-colors duration-150 cursor-pointer"
          :title="t.minimizeWin"
          @mousedown.stop
          @pointerdown.stop
          @click="handleMinimize"
        >
          <Minus class="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          class="flex items-center justify-center w-7 h-7 rounded-lg text-zinc-400 hover:bg-rose-500/20 hover:text-rose-400 transition-colors duration-150 cursor-pointer"
          :title="t.quitApp"
          @mousedown.stop
          @pointerdown.stop
          @click="handleCloseApp"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- 第二行：顶部导航胶囊栏 (今日看板 / 应用排行 / 时段流水 / 已屏蔽) -->
    <div class="px-3.5 pb-2.5 pt-0.5 cursor-default">
      <nav class="titlebar-nav grid grid-cols-4 gap-1 p-1 rounded-xl bg-[#1A1A21] border border-white/[0.06]" @mousedown.stop @pointerdown.stop>
        <button
          v-for="tab in navTabs"
          :key="tab.key"
          type="button"
          class="relative flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-[12px] font-medium transition-all duration-150 cursor-pointer"
          :class="
            currentTab === tab.key
              ? 'titlebar-nav-active bg-[#272732] text-white shadow-sm border border-white/[0.08]'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] border border-transparent'
          "
          @mousedown.stop
          @pointerdown.stop
          @click="selectTab(tab.key)"
        >
          <component
            :is="tab.icon"
            class="w-3.5 h-3.5 shrink-0"
            :class="currentTab === tab.key ? 'text-blue-500' : 'text-zinc-500'"
          />
          <span class="truncate">{{ tab.label }}</span>
          <span
            v-if="tab.key === 'ignored' && ignoredCount > 0"
            class="ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] leading-tight font-semibold"
            :class="
              currentTab === 'ignored'
                ? 'bg-blue-500/20 text-blue-500'
                : isLight
                  ? 'bg-black/[0.07] text-zinc-600'
                  : 'bg-zinc-700/70 text-zinc-300'
            "
          >
            {{ ignoredCount }}
          </span>
        </button>
      </nav>
    </div>
  </header>
</template>
