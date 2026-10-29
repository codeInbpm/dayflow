<script setup>
import { computed } from 'vue'
import {
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Minus,
  FilterX,
  RotateCcw,
} from 'lucide-vue-next'
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
  period: {
    type: String,
    default: 'day', // 'day' | 'week' | 'month'
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
  chartBuckets: {
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
  'change-period',
  'update:period',
  'select-hour',
  'update:selectedHour',
  'select-category',
  'update:selectedCategory',
])

const PERIOD_TABS = [
  { key: 'day', label: '每日' },
  { key: 'week', label: '每周' },
  { key: 'month', label: '每月' },
]

const resolvedPeriod = computed(() => props.period || props.dashboard?.period || 'day')

const resolvedDateStr = computed(() => props.dateStr || props.dashboard?.date_str || '')

const resolvedTodayStr = computed(() => {
  if (props.dashboard?.today_str) return props.dashboard.today_str
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
})

const resolvedTotalSec = computed(() =>
  props.totalSec !== null ? props.totalSec : Number(props.dashboard?.total_sec || 0)
)

const resolvedPrevPeriodSec = computed(() => {
  if (props.yesterdayTotalSec !== null) return props.yesterdayTotalSec
  if (props.dashboard?.prev_period_total_sec !== undefined) {
    return Number(props.dashboard.prev_period_total_sec || 0)
  }
  return Number(props.dashboard?.yesterday_total_sec || 0)
})

const resolvedDailyAvgSec = computed(() => Number(props.dashboard?.daily_avg_sec || 0))

const resolvedActiveDaysCount = computed(() => Number(props.dashboard?.active_days_count || 0))

const resolvedHourlyBuckets = computed(
  () => props.hourlyBuckets || props.dashboard?.hourly_buckets || []
)

const resolvedChartBuckets = computed(
  () => props.chartBuckets || props.dashboard?.chart_buckets || []
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

// 日历加减辅助函数（当后端字段缺省时兜底计算）
function shiftDateStr(baseStr, deltaDays) {
  if (!baseStr) return ''
  const parts = baseStr.split('-').map(Number)
  if (parts.length !== 3) return ''
  const dt = new Date(parts[0], parts[1] - 1, parts[2])
  dt.setDate(dt.getDate() + deltaDays)
  const y = dt.getFullYear()
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const d = String(dt.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const prevTargetDateStr = computed(() => {
  if (props.dashboard?.prev_date_str) {
    return props.dashboard.prev_date_str
  }
  const step = resolvedPeriod.value === 'week' ? -7 : resolvedPeriod.value === 'month' ? -30 : -1
  return shiftDateStr(resolvedDateStr.value, step)
})

const nextTargetDateStr = computed(() => {
  if (props.dashboard?.next_date_str !== undefined) {
    return props.dashboard.next_date_str
  }
  const step = resolvedPeriod.value === 'week' ? 7 : resolvedPeriod.value === 'month' ? 30 : 1
  const next = shiftDateStr(resolvedDateStr.value, step)
  if (!next || next > resolvedTodayStr.value) return null
  return next
})

const canGoPrevDate = computed(() => Boolean(prevTargetDateStr.value))
const canGoNextDate = computed(() => {
  if (props.dashboard?.can_go_next !== undefined) {
    return Boolean(props.dashboard.can_go_next)
  }
  return Boolean(nextTargetDateStr.value)
})

// 格式化顶部日期/周期显示
const formattedDateBanner = computed(() => {
  if (props.dashboard?.period_label) {
    return props.dashboard.period_label
  }
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

// 超大字号主时长拆分
const totalDurationParts = computed(() => {
  const sec = Math.max(0, Math.floor(resolvedTotalSec.value))
  const hours = Math.floor(sec / 3600)
  const minutes = Math.floor((sec % 3600) / 60)
  const seconds = sec % 60
  return { hours, minutes, seconds, totalSec: sec }
})

const periodCompareNoun = computed(() => {
  if (resolvedPeriod.value === 'week') return '上周'
  if (resolvedPeriod.value === 'month') return '上月'
  return '昨日'
})

// 与上一周期（昨日/上周/上月）对比文案
const periodDiffInfo = computed(() => {
  const current = resolvedTotalSec.value
  const prev = resolvedPrevPeriodSec.value
  const noun = periodCompareNoun.value
  if (!prev || prev <= 0) {
    if (resolvedPeriod.value === 'day') {
      return { type: 'neutral', text: '全天实时采集中' }
    }
    return {
      type: 'neutral',
      text: `活跃 ${resolvedActiveDaysCount.value || 1} 天`,
    }
  }
  const diff = current - prev
  const absDiff = Math.abs(diff)
  if (absDiff < 60) {
    return { type: 'neutral', text: `与${noun}基本持平` }
  }
  if (diff > 0) {
    return {
      type: 'up',
      text: `较${noun}多 ${formatDuration(absDiff, { showSecondsWhenUnderMinute: false })}`,
    }
  }
  return {
    type: 'down',
    text: `较${noun}少 ${formatDuration(absDiff, { showSecondsWhenUnderMinute: false })}`,
  }
})

// 柱状图正下方横向展示的核心分类汇总（四大主分类：社交通讯、开发与创意、影音娱乐、办公与效率）
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
  if (!canGoPrevDate.value || !prevTargetDateStr.value) return
  selectDate(prevTargetDateStr.value)
}

function handleNextDate() {
  if (!canGoNextDate.value || !nextTargetDateStr.value) return
  selectDate(nextTargetDateStr.value)
}

function handleBackToToday() {
  const today = resolvedTodayStr.value
  if (today) {
    selectDate(today)
  }
}

function selectPeriod(nextPeriod) {
  if (!nextPeriod || nextPeriod === resolvedPeriod.value) return
  emit('update:period', nextPeriod)
  emit('change-period', nextPeriod)
}

function handleHourSelect(hour) {
  emit('select-hour', hour)
  emit('update:selectedHour', hour)
}

function handleChartDateSelect(clickedDateStr) {
  if (!clickedDateStr) return
  // 在周/月视图点击某一天柱子时，下钻切换到该日期的“每日”视图
  emit('update:period', 'day')
  emit('change-period', 'day')
  selectDate(clickedDateStr)
}

function handleCategoryClick(catKey) {
  const next = props.selectedCategory === catKey ? 'all' : catKey
  emit('select-category', next)
  emit('update:selectedCategory', next)
}
</script>

<template>
  <section class="win-surface-card rounded-2xl p-4 transition-all duration-200">
    <!-- 顶部第1行：每日 / 每周 / 每月 汇总维度切换 + 实时状态指示 -->
    <div class="flex items-center justify-between gap-2 mb-2.5">
      <!-- 每日 / 每周 / 每月 胶囊切换 -->
      <div class="inline-flex items-center rounded-xl bg-white/[0.04] border border-white/[0.06] p-0.5">
        <button
          v-for="tab in PERIOD_TABS"
          :key="tab.key"
          type="button"
          class="px-3 py-1 rounded-[9px] text-[11.5px] font-semibold transition-all duration-150 cursor-pointer"
          :class="
            resolvedPeriod === tab.key
              ? 'bg-blue-500 text-white shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]'
          "
          @click="selectPeriod(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 右上角：若选中了某小时则显示清除过滤按钮，否则显示实时采集状态点 -->
      <button
        v-if="resolvedPeriod === 'day' && selectedHour !== null && selectedHour !== undefined"
        type="button"
        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-500/15 border border-blue-500/30 text-[11px] font-medium text-blue-300 hover:bg-blue-500/25 transition-colors cursor-pointer"
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

    <!-- 顶部第2行：日期 / 周 / 月 前后切换器 (< 10月29日 今日 >) -->
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
          :title="resolvedPeriod === 'week' ? '上一周' : resolvedPeriod === 'month' ? '上一月' : '前一天'"
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
          :title="resolvedPeriod === 'week' ? '下一周' : resolvedPeriod === 'month' ? '下一月' : '后一天'"
          @click="handleNextDate"
        >
          <ChevronRight class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- 当正在浏览历史日期/周/月时，提供一键回到今天/本周/本月 -->
      <button
        v-if="canGoNextDate"
        type="button"
        class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-blue-500/15 hover:bg-blue-500/25 border border-blue-500/30 text-[11px] font-medium text-blue-300 transition-colors cursor-pointer"
        @click="handleBackToToday"
      >
        <RotateCcw class="w-3 h-3" />
        <span>{{ resolvedPeriod === 'week' ? '回到本周' : resolvedPeriod === 'month' ? '回到本月' : '回到今日' }}</span>
      </button>

      <!-- 周/月模式下展示日均使用时长 -->
      <span
        v-else-if="resolvedPeriod !== 'day'"
        class="text-[11px] font-medium text-zinc-400"
      >
        日均 {{ formatDuration(resolvedDailyAvgSec) }}
      </span>
    </div>

    <!-- 累计使用总时长 (超大字号) + 环比对比 -->
    <div class="flex items-baseline justify-between gap-2 mb-3">
      <div>
        <div class="text-[11px] text-zinc-400 mb-0.5 font-medium">
          <template v-if="resolvedPeriod === 'week'">
            本周累计使用
            <span v-if="canGoNextDate" class="text-zinc-500">· 日均 {{ formatDuration(resolvedDailyAvgSec) }}</span>
          </template>
          <template v-else-if="resolvedPeriod === 'month'">
            本月累计使用
            <span v-if="canGoNextDate" class="text-zinc-500">· 日均 {{ formatDuration(resolvedDailyAvgSec) }}</span>
          </template>
          <template v-else>
            屏幕使用时间
          </template>
        </div>

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
      </div>

      <!-- 与昨日/上周/上月对比提示 -->
      <div class="flex items-center gap-1 text-[11px] font-medium shrink-0">
        <TrendingUp
          v-if="periodDiffInfo.type === 'up'"
          class="w-3.5 h-3.5 text-amber-400"
        />
        <TrendingDown
          v-else-if="periodDiffInfo.type === 'down'"
          class="w-3.5 h-3.5 text-emerald-400"
        />
        <Minus v-else class="w-3.5 h-3.5 text-zinc-500" />
        <span
          :class="{
            'text-amber-300/90': periodDiffInfo.type === 'up',
            'text-emerald-300/90': periodDiffInfo.type === 'down',
            'text-zinc-500': periodDiffInfo.type === 'neutral',
          }"
        >
          {{ periodDiffInfo.text }}
        </span>
      </div>
    </div>

    <!-- 分色堆叠柱状图（按日 24 小时 / 按周 7 天 / 按月 28~31 天） -->
    <HourlyBarChart
      :period="resolvedPeriod"
      :hourly-buckets="resolvedHourlyBuckets"
      :chart-buckets="resolvedChartBuckets"
      :category-meta="resolvedCategoryMeta"
      :selected-hour="selectedHour"
      @select-hour="handleHourSelect"
      @select-date="handleChartDateSelect"
    />

    <!-- 柱状图正下方：各大分类彩色标题与累计时长汇总行 -->
    <div class="grid grid-cols-4 gap-1.5 mt-3.5 pt-3 border-t border-white/[0.06]">
      <button
        v-for="cat in mainCategories"
        :key="cat.key"
        type="button"
        class="group flex flex-col items-start rounded-xl px-2 py-1.5 text-left transition-all duration-150 border cursor-pointer"
        :class="
          selectedCategory === cat.key
            ? 'bg-white/[0.08] border-white/[0.15] shadow-sm'
            : 'bg-transparent border-transparent hover:bg-white/[0.04]'
        "
        @click="handleCategoryClick(cat.key)"
      >
        <div class="flex items-center gap-1 w-full">
          <span
            class="w-1.5 h-1.5 rounded-full shrink-0"
            :style="{ backgroundColor: cat.color }"
          ></span>
          <span
            class="text-[11.5px] font-semibold whitespace-nowrap"
            :style="{ color: cat.color }"
          >
            {{ cat.label }}
          </span>
        </div>
        <span class="text-[12px] font-medium text-zinc-300 mt-0.5 pl-2.5 whitespace-nowrap">
          {{ formatDuration(cat.totalSec) }}
        </span>
      </button>
    </div>
  </section>
</template>
