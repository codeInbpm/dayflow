<script setup>
import { computed, ref } from 'vue'
import { CATEGORY_META, CATEGORY_ORDER, formatDuration } from '../api/bridge'
import {
  i18n,
  currentLocale,
  effectiveTheme,
  getCategoryLabel,
} from '../i18n'

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
const t = computed(() => i18n.value)
const isLight = computed(() => effectiveTheme.value === 'light')

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
    return { top: t.value.yAxis1Hour, mid: t.value.yAxis30Min, bottom: '0' }
  }
  const topHours = Math.round(yMaxSec.value / 3600)
  const midHours = topHours / 2
  const midStr = Number.isInteger(midHours) ? String(midHours) : midHours.toFixed(1)
  return {
    top: t.value.yAxisHours.replace('{h}', String(topHours)),
    mid: t.value.yAxisHours.replace('{h}', midStr),
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
        shortLabel: [0, 6, 12, 18].includes(hour)
          ? t.value.xAxisHour.replace('{h}', String(hour))
          : '',
        raw,
        maxCap: 3600,
      })
    })
  }

  return rawList.value.map((raw, idx) => {
    const index = typeof raw?.index === 'number' ? raw.index : idx
    const dateStr = raw?.date_str || null
    let shortLabel = raw?.short_label ?? ''
    let title = raw?.label || dateStr || `#${index + 1}`

    if (props.period === 'week') {
      const wkLabel = t.value.weekdays?.[idx] || shortLabel
      shortLabel = wkLabel
      if (dateStr) {
        const parts = dateStr.split('-').map(Number)
        if (parts.length === 3) {
          title =
            currentLocale.value === 'en'
              ? `${wkLabel} (${parts[1]}/${parts[2]})`
              : `${parts[1]}月${parts[2]}日 ${wkLabel}`
        }
      }
    } else if (props.period === 'month' && dateStr) {
      const parts = dateStr.split('-').map(Number)
      if (parts.length === 3) {
        const dayNum = parts[2]
        if (shortLabel) {
          shortLabel = t.value.xAxisDay.replace('{d}', String(dayNum))
        }
        title =
          currentLocale.value === 'en'
            ? `${dateStr}`
            : `${parts[1]}月${parts[2]}日`
      }
    }

    return buildBucketItem({
      index,
      hour: raw?.hour ?? null,
      dateStr,
      title,
      shortLabel,
      raw: raw || {},
      maxCap,
    })
  })
})

// 顶部留白比例：满刻度柱子高度占绘图区 85%，顶部预留 15% 呼吸空间，避免顶格
const CHART_MAX_RATIO = 0.85

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
        label: getCategoryLabel(key),
        color: meta.color,
        sec,
      })
      sumSec += sec
    }
  }

  const realTotal = Math.max(Number(raw.total_sec || 0), sumSec)
  const cappedTotal = Math.min(maxCap, realTotal)
  const scaleFactor = sumSec > maxCap ? maxCap / sumSec : 1

  // 计算整体柱子相对容器高度百分比（最高 CHART_MAX_RATIO * 100% = 85%）
  const totalBarHeightPct = (cappedTotal / maxCap) * CHART_MAX_RATIO * 100

  // 内部各段按各自所占比例分配
  const scaledSegments = segments.map((seg) => {
    const segShare = sumSec > 0 ? (seg.sec * scaleFactor) / sumSec : 0
    return {
      ...seg,
      pctOfBar: Math.max(3, segShare * 100),
      sharePct: Math.round(segShare * 100),
    }
  })

  return {
    index,
    hour,
    dateStr,
    title,
    shortLabel,
    totalSec: realTotal,
    hasData: realTotal > 0,
    totalBarHeightPct: realTotal > 0 ? Math.max(4, totalBarHeightPct) : 0,
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
      leftPct: ((b.index + 0.5) / count) * 100,
    }))
})

const gridColumnsStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(1, normalizedBuckets.value.length)}, minmax(0, 1fr))`,
}))
</script>

<template>
  <div class="relative select-none pt-1 pb-1">
    <!-- 顶部悬停/选中时段明细浮动气泡 (现代化悬浮毛玻璃卡片) -->
    <transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 translate-y-1 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 translate-y-1 scale-95"
    >
      <div
        v-if="activeTooltipBucket"
        class="pointer-events-none absolute -top-3 z-30 min-w-[188px] rounded-2xl backdrop-blur-xl border px-3.5 py-2.5 shadow-2xl transition-all duration-150"
        :class="
          isLight
            ? 'bg-white/95 border-black/[0.08] shadow-zinc-300/60 text-zinc-900'
            : 'bg-[#1e1e26]/95 border-white/[0.14] shadow-black/80 text-zinc-100'
        "
        :style="tooltipPositionStyle"
      >
        <div
          class="flex items-center justify-between gap-3 pb-1.5 mb-1.5 border-b"
          :class="isLight ? 'border-black/[0.06]' : 'border-white/[0.08]'"
        >
          <span
            class="text-[12px] font-semibold tracking-tight"
            :class="isLight ? 'text-zinc-800' : 'text-zinc-100'"
          >
            {{ activeTooltipBucket.title }}
          </span>
          <span class="text-[12px] font-bold text-blue-500 font-mono">
            {{ formatDuration(activeTooltipBucket.totalSec) }}
          </span>
        </div>

        <div v-if="activeTooltipBucket.segments.length > 0" class="space-y-1.5">
          <div
            v-for="seg in activeTooltipBucket.segments"
            :key="seg.key"
            class="flex items-center justify-between text-[11px] gap-2"
          >
            <div class="flex items-center gap-1.5 min-w-0">
              <span
                class="w-2 h-2 rounded-full shrink-0 shadow-xs"
                :style="{ backgroundColor: seg.color }"
              ></span>
              <span
                class="truncate font-medium"
                :class="isLight ? 'text-zinc-700' : 'text-zinc-300'"
              >
                {{ seg.label }}
              </span>
            </div>
            <div class="flex items-center gap-1.5 shrink-0">
              <span class="text-[10px] text-zinc-400 font-medium">
                {{ seg.sharePct }}%
              </span>
              <span
                class="font-mono font-medium"
                :class="isLight ? 'text-zinc-900' : 'text-zinc-200'"
              >
                {{ formatDuration(seg.sec) }}
              </span>
            </div>
          </div>
        </div>
        <div
          v-else
          class="text-[11px] py-0.5 text-center font-medium"
          :class="isLight ? 'text-zinc-400' : 'text-zinc-500'"
        >
          {{ t.emptySlotRecord }}
        </div>
      </div>
    </transition>

    <!-- 图表主体：左侧柱状绘图区 + 右侧自适应 Y 轴刻度 -->
    <div class="flex items-stretch gap-2.5">
      <div class="relative flex-1 h-[142px]">
        <!-- 背景水平参考线 (轻量柔和极简线条，彻底摒除纵向密集棋盘虚线) -->
        <div class="pointer-events-none absolute inset-0 flex flex-col justify-between">
          <!-- 顶部参考线（1小时 / 满刻度线，距顶 15% 呼吸空间） -->
          <div
            class="w-full border-t border-dashed"
            :class="isLight ? 'border-black/[0.06]' : 'border-white/[0.07]'"
            :style="{ marginTop: `${(1 - CHART_MAX_RATIO) * 100}%` }"
          ></div>
          <!-- 中部参考线（30分钟 / 半刻度线） -->
          <div
            class="w-full border-t border-dashed"
            :class="isLight ? 'border-black/[0.04]' : 'border-white/[0.04]'"
          ></div>
          <!-- 底部基线（0刻度线） -->
          <div
            class="w-full border-t"
            :class="isLight ? 'border-black/[0.08]' : 'border-white/[0.1]'"
          ></div>
        </div>

        <!-- 分色圆角胶囊柱子 (按日24根 / 按周7根 / 按月30根) -->
        <div
          class="relative z-10 grid items-end h-full px-1"
          :class="period === 'week' ? 'gap-3 px-2' : period === 'month' ? 'gap-[2px]' : 'gap-[3.5px]'"
          :style="gridColumnsStyle"
        >
          <button
            v-for="bucket in normalizedBuckets"
            :key="bucket.index"
            type="button"
            class="group relative flex flex-col justify-end items-center h-full w-full focus:outline-none cursor-pointer py-0"
            :title="
              period !== 'day' && bucket.dateStr
                ? t.clickToViewDate.replace('{date}', bucket.dateStr)
                : ''
            "
            @mouseenter="hoveredIndex = bucket.index"
            @mouseleave="hoveredIndex = null"
            @click="handleBarClick(bucket)"
          >
            <!-- 胶囊轨道总槽位 (Ghost Track Pillar)：无论是否有数据，全天始终呈现细腻的底轨胶囊轮廓 -->
            <div
              class="w-full h-full flex flex-col justify-end rounded-t-[5px] transition-all duration-200 relative overflow-hidden"
              :class="[
                period === 'week' ? 'max-w-[28px]' : 'max-w-[18px]',
                // 槽位底轨背景色 (浅色极淡米灰 / 深色极淡微光)
                isLight ? 'bg-black/[0.035]' : 'bg-white/[0.04]',
                // 选中或 Hover 态高亮反馈
                period === 'day' && activeSelectedHour === bucket.index
                  ? isLight
                    ? 'bg-blue-500/12 ring-1.5 ring-blue-500/60 shadow-xs'
                    : 'bg-blue-500/15 ring-1.5 ring-blue-400/70 shadow-sm'
                  : 'group-hover:bg-blue-500/8',
                hoveredIndex !== null && hoveredIndex !== bucket.index ? 'opacity-60' : 'opacity-100',
              ]"
            >
              <!-- 真实彩色数据柱 (从底部向上平滑升起，顶部拥有自然柔和圆弧) -->
              <div
                v-if="bucket.hasData"
                class="w-full flex flex-col-reverse justify-start rounded-t-[4px] overflow-hidden bar-segment-transition"
                :style="{ height: `${bucket.totalBarHeightPct}%` }"
              >
                <!-- 分类堆叠色块 (无缝贴合，纯净优雅) -->
                <div
                  v-for="seg in bucket.segments"
                  :key="seg.key"
                  class="w-full"
                  :style="{
                    height: `${seg.pctOfBar}%`,
                    backgroundColor: seg.color,
                  }"
                ></div>
              </div>

              <!-- 空柱底端极简微圆点 (当该时间段完全无使用记录时，点缀极淡小圆点避免空洞) -->
              <div
                v-else
                class="w-full flex items-center justify-center pb-1"
              >
                <div
                  class="w-1 h-1 rounded-full"
                  :class="isLight ? 'bg-black/10' : 'bg-white/10'"
                ></div>
              </div>
            </div>
          </button>
        </div>
      </div>

      <!-- 右侧 Y 轴刻度标注 (与水平参考线精确对齐) -->
      <div class="relative w-12 shrink-0 h-[142px] pointer-events-none text-right">
        <!-- 顶刻度 (1小时) -->
        <span
          class="absolute right-0 text-[10.5px] font-medium tabular-nums transition-colors -translate-y-1/2 leading-none"
          :class="isLight ? 'text-zinc-500 font-semibold' : 'text-zinc-400 font-semibold'"
          :style="{ top: `${(1 - CHART_MAX_RATIO) * 100}%` }"
        >
          {{ yAxisLabels.top }}
        </span>
        <!-- 中刻度 (30分钟) -->
        <span
          class="absolute right-0 text-[10.5px] font-medium tabular-nums transition-colors -translate-y-1/2 leading-none"
          :class="isLight ? 'text-zinc-400' : 'text-zinc-500'"
          :style="{ top: `${((1 - CHART_MAX_RATIO) * 100 + 100) / 2}%` }"
        >
          {{ yAxisLabels.mid }}
        </span>
        <!-- 底刻度 (0) -->
        <span
          class="absolute right-0 bottom-0 text-[10.5px] font-medium tabular-nums transition-colors translate-y-1/2 leading-none"
          :class="isLight ? 'text-zinc-400' : 'text-zinc-500'"
        >
          {{ yAxisLabels.bottom }}
        </span>
      </div>
    </div>

    <!-- 底部 X 轴时间刻度标注 (精准居中对齐对应时间柱) -->
    <div class="flex items-center gap-2.5 mt-2">
      <div class="relative flex-1 h-4">
        <div
          v-for="tick in xTicks"
          :key="tick.index"
          class="absolute top-0 flex flex-col items-center -translate-x-1/2 transition-colors duration-150 whitespace-nowrap"
          :style="{ left: `${tick.leftPct}%` }"
        >
          <span
            class="text-[11px] font-medium transition-colors"
            :class="[
              period === 'day' && activeSelectedHour === tick.index
                ? 'text-blue-500 font-bold'
                : isLight
                  ? 'text-zinc-500'
                  : 'text-zinc-400',
            ]"
          >
            {{ tick.label }}
          </span>
          <!-- 选中指示小蓝点 -->
          <span
            v-if="period === 'day' && activeSelectedHour === tick.index"
            class="w-1 h-1 rounded-full bg-blue-500 mt-0.5"
          ></span>
        </div>
      </div>
      <div class="w-12 shrink-0"></div>
    </div>
  </div>
</template>
