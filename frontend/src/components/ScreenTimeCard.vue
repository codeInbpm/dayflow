<script setup>
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, TrendingUp, TrendingDown, Minus, FilterX } from 'lucide-vue-next'
import HourlyBarChart from './HourlyBarChart.vue'
import { CATEGORY_META, formatDuration } from '../api/bridge'

const props = defineProps({
  dashboard: {
    type: Object,
    default: () => ({}),
  },
  dateStr: {
    type: String,
    default: '',
  },
  totalSec: {
    type: Number,
    default: null,
  },
  yesterdayTotalSec: {
    type: Number,
    default: null,
  },
  hourlyBuckets: {
    type: Array,
    default: null,
  },
  categoryTotals: {
    type: Array,
    default: null,
  },
  categoryMeta: {
    type: Object,
    default: () => CATEGORY_META,
  },
  recentDates: {
    type: Array,
    default: null,
  },
  activeApp: {
    type: Object,
    default: null,
  },
  selectedHour: {
    type: Number,
    default: null,
  },
  selectedCategory: {
    type: String,
    default: 'all',
  },
})

const emit = defineEmits([
  'change-date',
  'select-date',
  'update:dateStr',
  'select-hour',
  'update:selectedHour',
  'select-category',
  'update:selectedCategory',
])

const resolvedDateStr = computed(() => props.dateStr || props.dashboard?.date_str || '')

const resolvedTotalSec = computed(() =>
  props.totalSec !== null ? props.totalSec : Number(props.dashboard?.total_sec || 0)
)

const resolvedYesterdaySec = computed(() =>
  props.yesterdayTotalSec !== null
    ? props.yesterdayTotalSec
    : Number(props.dashboard?.yesterday_total_sec || 0)
)

const resolvedHourlyBuckets = computed(
  () => props.hourlyBuckets || props.dashboard?.hourly_buckets || []
)

const resolvedCategoryMeta = computed(
  () => props.categoryMeta || props.dashboard?.category_meta || CATEGORY_META
)

const resolvedRecentDates = computed(
  () => props.recentDates || props.dashboard?.recent_dates || []
)

const resolvedActiveApp = computed(
  () => props.activeApp || props.dashboard?.active_app || null
)

// 当前日期在 recentDates 中的索引
const currentDateIndex = computed(() => {
  if (!resolvedRecentDates.value.length) return -1
  return resolvedRecentDates.value.findIndex((d) => d.date_str === resolvedDateStr.value)
})

const canGoPrevDate = computed(() => currentDateIndex.value > 0)
const canGoNextDate = computed(
  () =>
    currentDateIndex.value !== -1 &&
    currentDateIndex.value < resolvedRecentDates.value.length - 1
)

// 格式化顶部日期显示，如 "10月29日 今日 · 周四"
const formattedDateBanner = computed(() => {
  const raw = resolvedDateStr.value
  if (!raw) return '今日'
  const parts = raw.split('-')
  const monthDay =
    parts.length === 3 ? `${Number(parts[1])}月${Number(parts[2])}日` : raw

  const matched = resolvedRecentDates.value.find((d) => d.date_str === raw)
  if (matched) {
    const tag = matched.label === '今日' || matched.label === '昨日' ? ` ${matched.label}` : ''
    const wk = matched.weekday ? ` · ${matched.weekday}` : ''
    return `${monthDay}${tag}${wk}`
  }
  return monthDay
})

// 超大字号主时长拆分（使“小时”与“分钟”数字醒目、单位精致，贴合参考图2排版）
const totalDurationParts = computed(() => {
  const sec = Math.max(0, Math.floor(resolvedTotalSec.value))
  const hours = Math.floor(sec / 3600)
  const minutes = Math.floor((sec % 3600) / 60)
  const seconds = sec % 60
  return { hours, minutes, seconds, totalSec: sec }
})

// 与昨日对比文案
const yesterdayDiffInfo = computed(() => {
  const today = resolvedTotalSec.value
  const yesterday = resolvedYesterdaySec.value
  if (!yesterday || yesterday <= 0) {
    return { type: 'neutral', text: '全天实时采集中' }
  }
  const diff = today - yesterday
  const absDiff = Math.abs(diff)
  if (absDiff < 60) {
    return { type: 'neutral', text: '与昨日基本持平' }
  }
  if (diff > 0) {
    return {
      type: 'up',
      text: `较昨日多 ${formatDuration(absDiff, { showSecondsWhenUnderMinute: false })}`,
    }
  }
  return {
    type: 'down',
    text: `较昨日少 ${formatDuration(absDiff, { showSecondsWhenUnderMinute: false })}`,
  }
})

// 柱状图正下方横向展示的核心分类汇总（优先展示四大主分类：社交通讯、开发与创意、影音娱乐、办公与效率）
const mainCategories = computed(() => {
  const rawList = props.categoryTotals || props.dashboard?.category_totals || []
  const totalMap = new Map()
  for (const item of rawList) {
    totalMap.set(item.category, Number(item.total_sec || 0))
  }

  const displayKeys = ['social', 'creative', 'entertainment', 'productivity']
  return displayKeys.map((key) => {
    const meta = resolvedCategoryMeta.value[key] || CATEGORY_META[key]
    return {
      key,
      label: meta.label,
      color: meta.color,
      totalSec: totalMap.get(key) || 0,
    }
  })
})

function selectDate(targetDateStr) {
  if (!targetDateStr || targetDateStr === resolvedDateStr.value) return
  emit('change-date', targetDateStr)
  emit('select-date', targetDateStr)
  emit('update:dateStr', targetDateStr)
}

function handlePrevDate() {
  if (!canGoPrevDate.value) return
  const target = resolvedRecentDates.value[currentDateIndex.value - 1]
  if (target) selectDate(target.date_str)
}

function handleNextDate() {
  if (!canGoNextDate.value) return
  const target = resolvedRecentDates.value[currentDateIndex.value + 1]
  if (target) selectDate(target.date_str)
}

function handleHourSelect(hour) {
  emit('select-hour', hour)
  emit('update:selectedHour', hour)
}

function handleCategoryClick(catKey) {
  const next = props.selectedCategory === catKey ? 'all' : catKey
  emit('select-category', next)
  emit('update:selectedCategory', next)
}
</script>

<template>
  <section class="win-surface-card rounded-2xl p-4 transition-all duration-200">
    <!-- 顶部栏：近 7 天日期切换器 (< 10月29日 今日 >) 与实时状态指示 -->
    <div class="flex items-center justify-between gap-2 mb-3">
      <div class="inline-flex items-center gap-1 rounded-xl bg-white/[0.04] border border-white/[0.06] p-0.5">
        <button
          type="button"
          class="flex items-center justify-center w-6 h-6 rounded-lg transition-colors"
          :class="
            canGoPrevDate
              ? 'text-zinc-300 hover:bg-white/[0.08] hover:text-white cursor-pointer'
              : 'text-zinc-600 cursor-not-allowed'
          "
          :disabled="!canGoPrevDate"
          title="前一天"
          @click="handlePrevDate"
        >
          <ChevronLeft class="w-3.5 h-3.5" />
        </button>

        <span class="px-2 text-[12px] font-medium text-zinc-200 tracking-wide">
          {{ formattedDateBanner }}
        </span>

        <button
          type="button"
          class="flex items-center justify-center w-6 h-6 rounded-lg transition-colors"
          :class="
            canGoNextDate
              ? 'text-zinc-300 hover:bg-white/[0.08] hover:text-white cursor-pointer'
              : 'text-zinc-600 cursor-not-allowed'
          "
          :disabled="!canGoNextDate"
          title="后一天"
          @click="handleNextDate"
        >
          <ChevronRight class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- 右上角：若选中了某小时则显示清除过滤按钮，否则显示实时采集状态点 -->
      <button
        v-if="selectedHour !== null && selectedHour !== undefined"
        type="button"
        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-500/15 border border-blue-500/30 text-[11px] font-medium text-blue-300 hover:bg-blue-500/25 transition-colors"
        @click="handleHourSelect(null)"
      >
        <FilterX class="w-3 h-3" />
        <span>{{ selectedHour }}:00 时段 · 点击还原</span>
      </button>

      <div
        v-else
        class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.03] border border-white/[0.05] text-[11px] text-zinc-400"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
        <span>{{ resolvedActiveApp ? '实时采集中' : '后台就绪' }}</span>
      </div>
    </div>

    <!-- 当天累计使用总时长 (超大字号，对标参考图2顶部视觉焦点) -->
    <div class="flex items-baseline justify-between gap-2 mb-3">
      <div class="flex items-baseline flex-wrap gap-x-1.5">
        <template v-if="totalDurationParts.hours > 0">
          <span class="text-[34px] leading-none font-bold tracking-tight text-white">
            {{ totalDurationParts.hours }}
          </span>
          <span class="text-[18px] font-semibold text-zinc-300 mr-1">小时</span>
        </template>

        <template v-if="totalDurationParts.minutes > 0 || totalDurationParts.hours > 0">
          <span class="text-[34px] leading-none font-bold tracking-tight text-white">
            {{ totalDurationParts.minutes }}
          </span>
          <span class="text-[18px] font-semibold text-zinc-300">分钟</span>
        </template>

        <template v-if="totalDurationParts.hours === 0 && totalDurationParts.minutes === 0">
          <span class="text-[32px] leading-none font-bold tracking-tight text-white">
            {{ totalDurationParts.seconds }}
          </span>
          <span class="text-[16px] font-semibold text-zinc-300">秒</span>
        </template>
      </div>

      <!-- 与昨日对比提示 -->
      <div class="flex items-center gap-1 text-[11px] font-medium shrink-0">
        <TrendingUp
          v-if="yesterdayDiffInfo.type === 'up'"
          class="w-3.5 h-3.5 text-amber-400"
        />
        <TrendingDown
          v-else-if="yesterdayDiffInfo.type === 'down'"
          class="w-3.5 h-3.5 text-emerald-400"
        />
        <Minus v-else class="w-3.5 h-3.5 text-zinc-500" />
        <span
          :class="{
            'text-amber-300/90': yesterdayDiffInfo.type === 'up',
            'text-emerald-300/90': yesterdayDiffInfo.type === 'down',
            'text-zinc-500': yesterdayDiffInfo.type === 'neutral',
          }"
        >
          {{ yesterdayDiffInfo.text }}
        </span>
      </div>
    </div>

    <!-- 24小时分色堆叠柱状图 -->
    <HourlyBarChart
      :hourly-buckets="resolvedHourlyBuckets"
      :category-meta="resolvedCategoryMeta"
      :selected-hour="selectedHour"
      @select-hour="handleHourSelect"
    />

    <!-- 柱状图正下方：各大分类彩色标题与累计时长汇总行 (对标参考图2) -->
    <div class="grid grid-cols-4 gap-2 mt-3.5 pt-3 border-t border-white/[0.06]">
      <button
        v-for="cat in mainCategories"
        :key="cat.key"
        type="button"
        class="group flex flex-col items-start rounded-xl px-2.5 py-1.5 text-left transition-all duration-150 border"
        :class="
          selectedCategory === cat.key
            ? 'bg-white/[0.08] border-white/[0.15] shadow-sm'
            : 'bg-transparent border-transparent hover:bg-white/[0.04]'
        "
        @click="handleCategoryClick(cat.key)"
      >
        <div class="flex items-center gap-1.5 w-full">
          <span
            class="w-1.5 h-1.5 rounded-full shrink-0"
            :style="{ backgroundColor: cat.color }"
          ></span>
          <span
            class="text-[12px] font-semibold truncate"
            :style="{ color: cat.color }"
          >
            {{ cat.label }}
          </span>
        </div>
        <span class="text-[12px] font-medium text-zinc-300 mt-0.5 pl-3 truncate w-full">
          {{ formatDuration(cat.totalSec, { showSecondsWhenUnderMinute: false }) }}
        </span>
      </button>
    </div>
  </section>
</template>
