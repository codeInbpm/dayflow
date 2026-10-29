<script setup>
import { computed, ref, watch } from 'vue'
import { Pin, Minus, X, LayoutDashboard, BarChart3, Clock3, EyeOff } from 'lucide-vue-next'
import { toggleAlwaysOnTop, minimizeWindow, hideToTray } from '../api/bridge'

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
  'minimize',
  'close',
])

const isPinned = ref(props.alwaysOnTop)

watch(
  () => props.alwaysOnTop,
  (val) => {
    isPinned.value = Boolean(val)
  }
)

const currentTab = computed(() => props.modelValue || props.activeTab || 'dashboard')

const navTabs = [
  { key: 'dashboard', label: '今日看板', icon: LayoutDashboard },
  { key: 'ranking', label: '应用排行', icon: BarChart3 },
  { key: 'timeline', label: '时段流水', icon: Clock3 },
  { key: 'ignored', label: '已屏蔽', icon: EyeOff },
]

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

async function handleMinimize() {
  await minimizeWindow()
  emit('minimize')
}

async function handleCloseToTray() {
  await hideToTray()
  emit('close')
}
</script>

<template>
  <header class="shrink-0 bg-[#141417]/95 backdrop-blur-md border-b border-white/[0.06] z-30">
    <!-- 第一行：Windows 11 无边框标题栏与窗口控制按钮 -->
    <div class="flex items-center justify-between h-10 px-3.5">
      <!-- 左侧品牌标识与拖拽区域 -->
      <div class="pywebview-drag-region flex items-center gap-2.5 flex-1 min-w-0 h-full cursor-default">
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
          <span class="text-[11px] text-zinc-500 hidden sm:inline">桌面时长管家</span>
        </div>

        <!-- 当前前台采集状态胶囊 -->
        <div
          v-if="activeApp && activeApp.display_name"
          class="ml-1 flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 max-w-[165px]"
          :title="`正在记录: ${activeApp.display_name}`"
        >
          <span class="relative flex h-1.5 w-1.5 shrink-0">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
          </span>
          <span class="text-[11px] text-emerald-300/90 truncate">
            {{ activeApp.display_name }}
          </span>
        </div>
      </div>

      <!-- 右侧：参考图1“小智桌面”同款窗口控制按钮（置顶图钉、最小化、关闭到托盘） -->
      <div class="flex items-center gap-1 shrink-0 ml-2">
        <button
          type="button"
          class="group relative flex items-center justify-center w-7 h-7 rounded-lg transition-all duration-150 border"
          :class="
            isPinned
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
              : 'bg-transparent text-zinc-400 border-transparent hover:bg-white/[0.07] hover:text-zinc-200'
          "
          :title="isPinned ? '已固定置顶 (点击取消)' : '固定在窗口最前端'"
          @click="handleTogglePin"
        >
          <Pin class="w-3.5 h-3.5 transition-transform duration-150" :class="isPinned ? '-rotate-45 fill-emerald-400/25' : ''" />
        </button>

        <button
          type="button"
          class="flex items-center justify-center w-7 h-7 rounded-lg text-zinc-400 hover:bg-white/[0.07] hover:text-zinc-200 transition-colors duration-150"
          title="最小化窗口"
          @click="handleMinimize"
        >
          <Minus class="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          class="flex items-center justify-center w-7 h-7 rounded-lg text-zinc-400 hover:bg-rose-500/20 hover:text-rose-400 transition-colors duration-150"
          title="隐藏到系统托盘"
          @click="handleCloseToTray"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- 第二行：顶部导航胶囊栏 (今日看板 / 应用排行 / 时段流水 / 已屏蔽) -->
    <div class="px-3.5 pb-2.5 pt-0.5">
      <nav class="grid grid-cols-4 gap-1 p-1 rounded-xl bg-[#1A1A21] border border-white/[0.06]">
        <button
          v-for="tab in navTabs"
          :key="tab.key"
          type="button"
          class="relative flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-[12px] font-medium transition-all duration-150"
          :class="
            currentTab === tab.key
              ? 'bg-[#272732] text-white shadow-sm border border-white/[0.08]'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] border border-transparent'
          "
          @click="selectTab(tab.key)"
        >
          <component
            :is="tab.icon"
            class="w-3.5 h-3.5 shrink-0"
            :class="currentTab === tab.key ? 'text-blue-400' : 'text-zinc-500'"
          />
          <span class="truncate">{{ tab.label }}</span>
          <span
            v-if="tab.key === 'ignored' && ignoredCount > 0"
            class="ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] leading-tight font-semibold"
            :class="
              currentTab === 'ignored'
                ? 'bg-blue-500/25 text-blue-300'
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
