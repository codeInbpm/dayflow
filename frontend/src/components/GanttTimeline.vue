<script setup>
import { computed, ref } from 'vue'
import { Clock, Sparkles } from 'lucide-vue-next'
import { CATEGORY_META, formatDuration } from '../api/bridge'
import { effectiveTheme, getCategoryLabel, getLocalizedAppName, i18n } from '../i18n'

const props = defineProps({
  records: {
    type: Array,
    default: () => [],
  },
  selectedRecordId: {
    type: [Number, String],
    default: null,
  },
  isToday: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['select-record'])

const hoveredRecord = ref(null)
const t = computed(() => i18n.value)
const isLight = computed(() => effectiveTheme.value === 'light')

// 将 "HH:MM:SS" 转为全天秒数 (0 ~ 86400)
function timeStrToSeconds(str) {
  if (!str) return 0
  const parts = str.split(':').map(Number)
  if (parts.length < 2) return 0
  const h = parts[0] || 0
  const m = parts[1] || 0
  const s = parts[2] || 0
  return h * 3600 + m * 60 + s
}

// 当前时刻在全天的百分比位置 (仅今天有效)
const nowPointerPct = computed(() => {
  if (!props.isToday) return null
  const now = new Date()
  const sec = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()
  return (sec / 86400) * 100
})

// 将传入的流水记录映射为 24 小时甘特色块
const ganttBlocks = computed(() => {
  const list = props.records || []
  return list.map((item) => {
    const startSec = timeStrToSeconds(item.start_time)
    const durSec = Math.max(15, Number(item.duration_sec || 0))
    const leftPct = (startSec / 86400) * 100
    // 保证最小可见宽度 0.4%
    const widthPct = Math.max(0.4, (durSec / 86400) * 100)
    const cat = item.category || 'other'
    const color = CATEGORY_META[cat]?.color || '#94A3B8'

    return {
      ...item,
      leftPct: Math.min(99.6, leftPct),
      widthPct: Math.min(100 - leftPct, widthPct),
      color,
    }
  })
})

// 悬浮气泡定位
const tooltipPositionStyle = computed(() => {
  if (!hoveredRecord.value) return {}
  const left = hoveredRecord.value.leftPct + hoveredRecord.value.widthPct / 2
  if (left <= 22) {
    return { left: '0%', transform: 'translateX(0)' }
  }
  if (left >= 78) {
    return { right: '0%', transform: 'translateX(0)' }
  }
  return { left: `${left}%`, transform: 'translateX(-50%)' }
})

// 时间刻度标尺 (0, 3, 6, 9, 12, 15, 18, 21, 24)
const RULER_TICKS = [
  { hour: 0, label: '00:00', pct: 0 },
  { hour: 4, label: '04:00', pct: (4 / 24) * 100 },
  { hour: 8, label: '08:00', pct: (8 / 24) * 100 },
  { hour: 12, label: '12:00', pct: (12 / 24) * 100 },
  { hour: 16, label: '16:00', pct: (16 / 24) * 100 },
  { hour: 20, label: '20:00', pct: (20 / 24) * 100 },
  { hour: 24, label: '24:00', pct: 100 },
]

function handleBlockClick(record) {
  emit('select-record', record)
}
</script>

<template>
  <div class="rounded-xl p-3 select-none relative transition-colors border"
    :class="isLight ? 'bg-black/[0.02] border-black/[0.06]' : 'bg-white/[0.025] border-white/[0.06]'"
  >
    <!-- 甘特图标题栏 -->
    <div class="flex items-center justify-between mb-2.5">
      <div class="flex items-center gap-1.5 text-[11.5px] font-semibold"
        :class="isLight ? 'text-zinc-700' : 'text-zinc-200'"
      >
        <Sparkles class="w-3.5 h-3.5 text-blue-500" />
        <span>{{ t.ganttTitle }}</span>
      </div>
      <div class="text-[10.5px] text-zinc-400 font-mono">
        {{ t.ganttSliceCount.replace('{count}', String(records.length)) }}
      </div>
    </div>

    <!-- 悬停明细 Tooltip -->
    <transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-1"
    >
      <div
        v-if="hoveredRecord"
        class="pointer-events-none absolute -top-11 z-30 min-w-[170px] rounded-xl backdrop-blur-md border px-2.5 py-1.5 shadow-xl text-left"
        :class="isLight ? 'bg-white/95 border-black/[0.1] text-zinc-900 shadow-zinc-300' : 'bg-[#1e1e24]/95 border-white/[0.15] text-zinc-100 shadow-black'"
        :style="tooltipPositionStyle"
      >
        <div class="flex items-center gap-1.5">
          <span
            class="w-2 h-2 rounded-full shrink-0"
            :style="{ backgroundColor: hoveredRecord.color }"
          ></span>
          <span class="text-[11.5px] font-bold truncate">
            {{ getLocalizedAppName(hoveredRecord.display_name) }}
          </span>
          <span class="text-[10px] text-blue-500 font-mono ml-auto">
            {{ formatDuration(hoveredRecord.duration_sec) }}
          </span>
        </div>
        <div class="text-[10px] text-zinc-400 font-mono mt-0.5 truncate">
          {{ hoveredRecord.start_time }} ~ {{ hoveredRecord.end_time }}
          <span v-if="hoveredRecord.last_window_title">· {{ hoveredRecord.last_window_title }}</span>
        </div>
      </div>
    </transition>

    <!-- 24小时甘特彩带容器 -->
    <div class="relative w-full h-8 rounded-lg overflow-hidden border transition-colors"
      :class="isLight ? 'bg-black/[0.04] border-black/[0.08]' : 'bg-white/[0.04] border-white/[0.08]'"
    >
      <!-- 背景时间网格竖线 -->
      <div
        v-for="tick in RULER_TICKS"
        :key="tick.hour"
        class="absolute top-0 bottom-0 border-l border-dashed pointer-events-none"
        :class="isLight ? 'border-black/[0.06]' : 'border-white/[0.06]'"
        :style="{ left: `${tick.pct}%` }"
      ></div>

      <!-- 甘特使用记录色块 -->
      <div
        v-for="block in ganttBlocks"
        :key="block.id"
        class="absolute top-0.5 bottom-0.5 rounded-[4px] cursor-pointer transition-all duration-150 hover:brightness-125 hover:z-20 hover:scale-y-110 shadow-xs"
        :class="selectedRecordId === block.id ? 'ring-2 ring-white z-20 shadow-md' : 'opacity-90'"
        :style="{
          left: `${block.leftPct}%`,
          width: `${block.widthPct}%`,
          backgroundColor: block.color,
        }"
        @mouseenter="hoveredRecord = block"
        @mouseleave="hoveredRecord = null"
        @click="handleBlockClick(block)"
      ></div>

      <!-- 当前时刻指示红线 (仅今天) -->
      <div
        v-if="nowPointerPct !== null && nowPointerPct >= 0 && nowPointerPct <= 100"
        class="absolute top-0 bottom-0 w-[2px] bg-red-500 z-30 pointer-events-none shadow-sm"
        :style="{ left: `${nowPointerPct}%` }"
        title="当前时间"
      >
        <div class="w-2 h-2 rounded-full bg-red-500 -ml-[3px] -mt-[1px] shadow-xs"></div>
      </div>
    </div>

    <!-- 底部时间刻度标尺 -->
    <div class="relative w-full h-3.5 mt-1.5">
      <span
        v-for="tick in RULER_TICKS"
        :key="tick.hour"
        class="absolute top-0 text-[9.5px] font-mono font-medium transition-colors -translate-x-1/2 whitespace-nowrap"
        :class="isLight ? 'text-zinc-500' : 'text-zinc-400'"
        :style="{ left: `${tick.pct}%` }"
      >
        {{ tick.label }}
      </span>
    </div>
  </div>
</template>
