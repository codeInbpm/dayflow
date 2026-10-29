<script setup>
import { computed, ref } from 'vue'
import { CATEGORY_META, CATEGORY_ORDER, formatDuration } from '../api/bridge'

const props = defineProps({
  period: {
    type: String,
    default: 'day',
  },
  hourlyBuckets: {
    type: Array,
    default: () => [],
  },
  chartBuckets: {
    type: Array,
    default: null,
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

const emit = defineEmits(['select-hour', 'update:selectedHour', 'update:modelValue', 'select-date'])

const hoveredIndex = ref(null)

const activeSelectedHour = computed(() => {
  if (props.modelValue !== null && props.modelValue !== undefined) {
    return props.modelValue
  }
  return props.selectedHour
})

const rawList = computed(() => {
  if (Array.isArray(props.chartBuckets) && props.chartBuckets.length > 0) {
    return props.chartBuckets
  }
  return props.hourlyBuckets || []
})

// 计算 Y 轴满量程秒数（按日固定 3600s=1小时；按周/按月根据单日最大值自适应为整小时刻度，最低 7200s=2小时）
const yMaxSec = computed(() => {
  if (props.period === 'day') {
    return 3600
  }
  let maxDaySec = 0
  for (const item of rawList.value) {
    const sec = Number(item?.total_sec || 0)
    if (sec > maxDaySec) maxDaySec = sec
  }
  if (maxDaySec <= 7200) return 7200 // 2小时
  if (maxDaySec <= 14400) return 14400 // 4小时
  if (maxDaySec <= 28800) return 28800 // 8小时
  if (maxDaySec <= 43200) return 43200 // 12小时
  return Math.ceil(maxDaySec / 7200) * 7200
})

const yAxisLabels = computed(() => {
  if (props.period === 'day') {
    return { top: '1小时', mid: '30分钟', bottom: '0' }
  }
  const topHours = Math.round(yMaxSec.value / 3600)
  const midHours = topHours / 2
  return {
    top: `${topHours}小时`,
    mid: Number.isInteger(midHours) ? `${midHours}小时` : `${midHours.toFixed(1)}小时`,
    bottom: '0',
  }
})

// 归一化柱状图数组（day: 24 根; week: 7 根; month: 28~31 根）
const normalizedBuckets = computed(() => {
  const maxCap = yMaxSec.value

  if (props.period === 'day') {
    const map = new Map()
    for (const item of rawList.value) {
      const h = item?.hour ?? item?.index
      if (typeof h === 'number') {
        map.set(h, item)
      }
    }

    return Array.from({ length: 24 }, (_, hour) => {
      const raw = map.get(hour) || {}
      return buildBucketItem({
        index: hour,
        hour,
        dateStr: raw.date_str || null,
        title: `${String(hour).padStart(2, '0')}:00 - ${String(hour).padStart(2, '0')}:59`,
        shortLabel: [0, 6, 12, 18].includes(hour) ? `${hour}时` : '',
        raw,
        maxCap: 3600,
      })
    })
  }

  return rawList.value.map((raw, idx) => {
    const index = typeof raw?.index === 'number' ? raw.index : idx
    return buildBucketItem({
      index,
      hour: raw?.hour ?? null,
      dateStr: raw?.date_str || null,
      title: raw?.label || raw?.date_str || `#${index + 1}`,
      shortLabel: raw?.short_label ?? '',
      raw: raw || {},
      maxCap,
    })
  })
})

function buildBucketItem({ index, hour, dateStr, title, shortLabel, raw, maxCap }) {
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

  const realTotal = Math.max(Number(raw.total_sec || 0), sumSec)
  const cappedTotal = Math.min(maxCap, realTotal)
  const scaleFactor = sumSec > maxCap ? maxCap / sumSec : 1
  const scaledSegments = segments.map((seg) => ({
    ...seg,
    heightPct: Math.max(2.5, ((seg.sec * scaleFactor) / maxCap) * 100),
  }))

  return {
    index,
    hour,
    dateStr,
    title,
    shortLabel,
    totalSec: realTotal,
    totalPct: Math.min(100, (cappedTotal / maxCap) * 100),
    segments: scaledSegments,
  }
}

const activeTooltipBucket = computed(() => {
  const targetIdx =
    hoveredIndex.value !== null
      ? hoveredIndex.value
      : props.period === 'day'
        ? activeSelectedHour.value
        : null
  if (targetIdx === null || targetIdx === undefined) return null
  return normalizedBuckets.value.find((b) => b.index === targetIdx) || null
})

const tooltipPositionStyle = computed(() => {
  if (!activeTooltipBucket.value) return {}
  const totalCount = Math.max(1, normalizedBuckets.value.length)
  const idx = activeTooltipBucket.value.index
  const pct = ((idx + 0.5) / totalCount) * 100
  if (pct <= 22) {
    return { left: '0%', transform: 'translateX(0)' }
  }
  if (pct >= 78) {
    return { right: '0%', transform: 'translateX(0)' }
  }
  return { left: `${pct}%`, transform: 'translateX(-50%)' }
})

function handleBarClick(bucket) {
  if (props.period === 'day') {
    const next = activeSelectedHour.value === bucket.index ? null : bucket.index
    emit('select-hour', next)
    emit('update:selectedHour', next)
    emit('update:modelValue', next)
  } else if (bucket.dateStr) {
    emit('select-date', bucket.dateStr)
  }
}

const xTicks = computed(() => {
  const count = normalizedBuckets.value.length
  if (count === 0) return []
  return normalizedBuckets.value
    .filter((b) => Boolean(b.shortLabel))
    .map((b) => ({
      index: b.index,
      label: b.shortLabel,
      leftPct: props.period === 'week' ? ((b.index + 0.5) / count) * 100 : (b.index / count) * 100,
      centered: props.period === 'week',
    }))
})

const gridColumnsStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(1, normalizedBuckets.value.length)}, minmax(0, 1fr))`,
}))
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
        class="pointer-events-none absolute -top-2 z-20 min-w-[172px] rounded-xl bg-[#22222B]/95 backdrop-blur-md border border-white/[0.12] px-3 py-2 shadow-floating"
        :style="tooltipPositionStyle"
      >
        <div class="flex items-center justify-between gap-3 border-b border-white/[0.07] pb-1 mb-1.5">
          <span class="text-[11px] font-semibold text-zinc-200">
            {{ activeTooltipBucket.title }}
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

    <!-- 图表主体：左侧柱状绘图区 + 右侧自适应 Y 轴刻度 -->
    <div class="flex items-stretch gap-2">
      <div class="relative flex-1 h-[132px]">
        <!-- 背景水平参考线 -->
        <div class="pointer-events-none absolute inset-0 flex flex-col justify-between">
          <div class="border-t border-dashed border-white/[0.09] w-full"></div>
          <div class="border-t border-dashed border-white/[0.07] w-full"></div>
          <div class="border-t border-white/[0.12] w-full"></div>
        </div>

        <div class="pointer-events-none absolute inset-0">
          <div
            v-for="tick in xTicks"
            :key="tick.index"
            class="absolute top-0 bottom-0 border-l border-dashed border-white/[0.05]"
            :style="{ left: `${tick.leftPct}%` }"
          ></div>
        </div>

        <!-- 分色圆角堆叠柱子 (按日24根 / 按周7根 / 按月30根) -->
        <div
          class="relative z-10 grid items-end h-full px-[2px]"
          :class="period === 'week' ? 'gap-2.5 px-2' : 'gap-[3px]'"
          :style="gridColumnsStyle"
        >
          <button
            v-for="bucket in normalizedBuckets"
            :key="bucket.index"
            type="button"
            class="group relative flex flex-col justify-end items-center h-full w-full focus:outline-none cursor-pointer"
            :title="period !== 'day' && bucket.dateStr ? `点击查看 ${bucket.dateStr} 当日明细` : ''"
            @mouseenter="hoveredIndex = bucket.index"
            @mouseleave="hoveredIndex = null"
            @click="handleBarClick(bucket)"
          >
            <div
              class="w-full h-full flex flex-col-reverse justify-start overflow-hidden transition-all duration-150"
              :class="[
                period === 'week' ? 'rounded-t-[6px] max-w-[26px]' : 'rounded-t-[4px]',
                period === 'day' && activeSelectedHour === bucket.index
                  ? 'bg-white/[0.09] ring-1 ring-blue-400/60'
                  : 'group-hover:bg-white/[0.05]',
                period === 'day' && activeSelectedHour !== null && activeSelectedHour !== bucket.index
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
                  idx === bucket.segments.length - 1
                    ? period === 'week'
                      ? 'rounded-t-[5px]'
                      : 'rounded-t-[3.5px]'
                    : '',
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

      <!-- 右侧 Y 轴刻度标注 -->
      <div class="flex flex-col justify-between text-[11px] text-zinc-500 font-medium leading-none py-0.5 shrink-0 w-11 text-right">
        <span>{{ yAxisLabels.top }}</span>
        <span>{{ yAxisLabels.mid }}</span>
        <span>{{ yAxisLabels.bottom }}</span>
      </div>
    </div>

    <!-- 底部 X 轴时间刻度标注 -->
    <div class="flex items-center gap-2 mt-1.5">
      <div class="relative flex-1 h-4">
        <span
          v-for="tick in xTicks"
          :key="tick.index"
          class="absolute top-0 text-[11px] font-medium transition-colors duration-150 whitespace-nowrap"
          :class="[
            period === 'day' && activeSelectedHour === tick.index
              ? 'text-blue-400 font-semibold'
              : 'text-zinc-500',
            tick.centered ? '-translate-x-1/2' : '',
          ]"
          :style="{ left: `${tick.leftPct}%` }"
        >
          {{ tick.label }}
        </span>
      </div>
      <div class="w-11 shrink-0"></div>
    </div>
  </div>
</template>
