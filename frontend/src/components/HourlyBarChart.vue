<script setup>
import { computed, ref } from 'vue'
import { CATEGORY_META, CATEGORY_ORDER, formatDuration } from '../api/bridge'

const props = defineProps({
  hourlyBuckets: {
    type: Array,
    default: () => [],
  },
  categoryMeta: {
    type: Object,
    default: () => CATEGORY_META,
  },
  selectedHour: {
    type: Number,
    default: null,
  },
  modelValue: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['select-hour', 'update:selectedHour', 'update:modelValue'])

const hoveredHour = ref(null)

const activeSelectedHour = computed(() => {
  if (props.modelValue !== null && props.modelValue !== undefined) {
    return props.modelValue
  }
  return props.selectedHour
})

// 归一化 0~23 小时数组，确保始终渲染完整 24 根柱子
const normalizedBuckets = computed(() => {
  const map = new Map()
  for (const item of props.hourlyBuckets || []) {
    if (item && typeof item.hour === 'number') {
      map.set(item.hour, item)
    }
  }

  return Array.from({ length: 24 }, (_, hour) => {
    const raw = map.get(hour) || {}
    const cats = raw.categories || {}
    const segments = []
    let sumSec = 0

    for (const key of CATEGORY_ORDER) {
      const sec = Math.max(0, Number(cats[key] || 0))
      if (sec > 0) {
        const meta = props.categoryMeta?.[key] || CATEGORY_META[key] || CATEGORY_META.other
        segments.push({
          key,
          label: meta.label,
          color: meta.color,
          sec,
        })
        sumSec += sec
      }
    }

    const cappedTotal = Math.min(3600, Math.max(Number(raw.total_sec || 0), sumSec))
    // 计算每段占 3600 秒（1小时满量程）的高度百分比
    const scaleFactor = sumSec > 3600 ? 3600 / sumSec : 1
    const scaledSegments = segments.map((seg) => ({
      ...seg,
      heightPct: Math.max(2.5, (seg.sec * scaleFactor / 3600) * 100),
    }))

    return {
      hour,
      totalSec: cappedTotal,
      totalPct: Math.min(100, (cappedTotal / 3600) * 100),
      segments: scaledSegments,
    }
  })
})

const activeTooltipBucket = computed(() => {
  const targetHour =
    hoveredHour.value !== null ? hoveredHour.value : activeSelectedHour.value
  if (targetHour === null || targetHour === undefined) return null
  return normalizedBuckets.value[targetHour] || null
})

const tooltipPositionStyle = computed(() => {
  if (!activeTooltipBucket.value) return {}
  const h = activeTooltipBucket.value.hour
  const pct = ((h + 0.5) / 24) * 100
  if (h <= 4) {
    return { left: '0%', transform: 'translateX(0)' }
  }
  if (h >= 19) {
    return { right: '0%', transform: 'translateX(0)' }
  }
  return { left: `${pct}%`, transform: 'translateX(-50%)' }
})

function handleBarClick(hour) {
  const next = activeSelectedHour.value === hour ? null : hour
  emit('select-hour', next)
  emit('update:selectedHour', next)
  emit('update:modelValue', next)
}

const xTicks = [
  { hour: 0, label: '0时', leftPct: (0 / 24) * 100 },
  { hour: 6, label: '6时', leftPct: (6 / 24) * 100 },
  { hour: 12, label: '12时', leftPct: (12 / 24) * 100 },
  { hour: 18, label: '18时', leftPct: (18 / 24) * 100 },
]
</script>

<template>
  <div class="relative select-none pt-2 pb-1">
    <!-- 顶部悬停/选中时段明细浮动气泡 -->
    <transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-1"
    >
      <div
        v-if="activeTooltipBucket"
        class="pointer-events-none absolute -top-2 z-20 min-w-[168px] rounded-xl bg-[#22222B]/95 backdrop-blur-md border border-white/[0.12] px-3 py-2 shadow-floating"
        :style="tooltipPositionStyle"
      >
        <div class="flex items-center justify-between gap-3 border-b border-white/[0.07] pb-1 mb-1.5">
          <span class="text-[11px] font-semibold text-zinc-200">
            {{ String(activeTooltipBucket.hour).padStart(2, '0') }}:00 - {{ String(activeTooltipBucket.hour).padStart(2, '0') }}:59
          </span>
          <span class="text-[11px] font-medium text-blue-400">
            {{ formatDuration(activeTooltipBucket.totalSec) }}
          </span>
        </div>

        <div v-if="activeTooltipBucket.segments.length > 0" class="space-y-1">
          <div
            v-for="seg in activeTooltipBucket.segments"
            :key="seg.key"
            class="flex items-center justify-between text-[11px]"
          >
            <div class="flex items-center gap-1.5">
              <span
                class="w-2 h-2 rounded-full shrink-0"
                :style="{ backgroundColor: seg.color }"
              ></span>
              <span class="text-zinc-300">{{ seg.label }}</span>
            </div>
            <span class="text-zinc-400 font-mono">
              {{ formatDuration(seg.sec) }}
            </span>
          </div>
        </div>
        <div v-else class="text-[11px] text-zinc-500 py-0.5">
          该时段暂无软件使用记录
        </div>
      </div>
    </transition>

    <!-- 图表主体：左侧 24 小时柱状绘图区 + 右侧 Y 轴刻度 (1小时 / 30分钟 / 0) -->
    <div class="flex items-stretch gap-2">
      <!-- 24小时柱状图绘图容器 -->
      <div class="relative flex-1 h-[132px]">
        <!-- 背景水平参考线与竖向分时虚线 (0时/6时/12时/18时) -->
        <div class="pointer-events-none absolute inset-0 flex flex-col justify-between">
          <div class="border-t border-dashed border-white/[0.09] w-full"></div>
          <div class="border-t border-dashed border-white/[0.07] w-full"></div>
          <div class="border-t border-white/[0.12] w-full"></div>
        </div>

        <div class="pointer-events-none absolute inset-0">
          <div
            v-for="tick in xTicks"
            :key="tick.hour"
            class="absolute top-0 bottom-0 border-l border-dashed border-white/[0.06]"
            :style="{ left: `${tick.leftPct}%` }"
          ></div>
        </div>

        <!-- 24 根分色圆角堆叠柱子 -->
        <div class="relative z-10 grid grid-cols-24 items-end h-full gap-[3px] px-[2px]">
          <button
            v-for="bucket in normalizedBuckets"
            :key="bucket.hour"
            type="button"
            class="group relative flex flex-col justify-end items-center h-full w-full focus:outline-none cursor-pointer"
            :aria-label="`${bucket.hour}时 使用 ${formatDuration(bucket.totalSec)}`"
            @mouseenter="hoveredHour = bucket.hour"
            @mouseleave="hoveredHour = null"
            @click="handleBarClick(bucket.hour)"
          >
            <!-- 悬停或选中高亮底柱槽 -->
            <div
              class="w-full h-full rounded-t-[4px] flex flex-col-reverse justify-start overflow-hidden transition-all duration-150"
              :class="[
                activeSelectedHour === bucket.hour
                  ? 'bg-white/[0.09] ring-1 ring-blue-400/60'
                  : 'group-hover:bg-white/[0.05]',
                activeSelectedHour !== null && activeSelectedHour !== bucket.hour
                  ? 'opacity-45 group-hover:opacity-85'
                  : 'opacity-100',
              ]"
            >
              <!-- 堆叠分类色块 -->
              <div
                v-for="(seg, idx) in bucket.segments"
                :key="seg.key"
                class="w-full bar-segment-transition"
                :class="[
                  idx === bucket.segments.length - 1 ? 'rounded-t-[3.5px]' : '',
                  idx > 0 ? 'mb-[1px]' : '',
                ]"
                :style="{
                  height: `${seg.heightPct}%`,
                  backgroundColor: seg.color,
                }"
              ></div>

              <!-- 空柱底线占位点 -->
              <div
                v-if="bucket.segments.length === 0"
                class="w-full h-[2px] rounded-full bg-white/[0.05]"
              ></div>
            </div>
          </button>
        </div>
      </div>

      <!-- 右侧 Y 轴刻度标注 (对标参考图2: 1小时 / 30分钟 / 0) -->
      <div class="flex flex-col justify-between text-[11px] text-zinc-500 font-medium leading-none py-0.5 shrink-0 w-10 text-right">
        <span>1小时</span>
        <span>30分钟</span>
        <span>0</span>
      </div>
    </div>

    <!-- 底部 X 轴时间刻度标注 (0时 / 6时 / 12时 / 18时) -->
    <div class="flex items-center gap-2 mt-1.5">
      <div class="relative flex-1 h-4">
        <span
          v-for="tick in xTicks"
          :key="tick.hour"
          class="absolute top-0 text-[11px] font-medium transition-colors duration-150"
          :class="
            activeSelectedHour === tick.hour
              ? 'text-blue-400 font-semibold'
              : 'text-zinc-500'
          "
          :style="{ left: `${tick.leftPct}%` }"
        >
          {{ tick.label }}
        </span>
      </div>
      <div class="w-10 shrink-0"></div>
    </div>
  </div>
</template>

<style scoped>
.grid-cols-24 {
  grid-template-columns: repeat(24, minmax(0, 1fr));
}
</style>
