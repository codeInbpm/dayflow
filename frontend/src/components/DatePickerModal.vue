<script setup>
import { computed, ref, watch } from 'vue'
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Calendar as CalendarIcon,
  X,
} from 'lucide-vue-next'
import { i18n, effectiveTheme } from '../i18n'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  currentDate: {
    type: String,
    default: '',
  },
  todayStr: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'close', 'select'])

const t = computed(() => i18n.value)
const isLight = computed(() => effectiveTheme.value === 'light')

const viewYear = ref(2026)
const viewMonth = ref(10) // 1-12

// 当弹窗打开或传入日期变化时，初始化 viewYear 与 viewMonth
watch(
  () => [props.modelValue, props.currentDate],
  ([open, dateStr]) => {
    if (open) {
      const target = dateStr || props.todayStr || new Date().toISOString().slice(0, 10)
      const parts = target.split('-').map(Number)
      if (parts.length === 3 && parts[0] > 2000) {
        viewYear.value = parts[0]
        viewMonth.value = parts[1]
      }
    }
  },
  { immediate: true }
)

const resolvedTodayStr = computed(() => {
  if (props.todayStr) return props.todayStr
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
})

const WEEK_HEADERS = ['日', '一', '二', '三', '四', '五', '六']

// 生成当前视图月的 42 个格子（6 周 × 7 天）
const calendarDays = computed(() => {
  const y = viewYear.value
  const m = viewMonth.value

  // 当前月第一天是星期几 (0: 周日, 1: 周一, ...)
  const firstDayOfWeek = new Date(y, m - 1, 1).getDay()
  // 当前月天数
  const daysInCurrentMonth = new Date(y, m, 0).getDate()
  // 上个月天数
  const daysInPrevMonth = new Date(y, m - 1, 0).getDate()

  const days = []

  // 1. 上月末尾补齐天数
  const prevMonthYear = m === 1 ? y - 1 : y
  const prevMonthNum = m === 1 ? 12 : m - 1
  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i
    const mm = String(prevMonthNum).padStart(2, '0')
    const dd = String(d).padStart(2, '0')
    const dateStr = `${prevMonthYear}-${mm}-${dd}`
    days.push({
      year: prevMonthYear,
      month: prevMonthNum,
      day: d,
      dateStr,
      isCurrentMonth: false,
      isSelected: dateStr === props.currentDate,
      isToday: dateStr === resolvedTodayStr.value,
      isFuture: dateStr > resolvedTodayStr.value,
    })
  }

  // 2. 当月全部天数
  for (let d = 1; d <= daysInCurrentMonth; d++) {
    const mm = String(m).padStart(2, '0')
    const dd = String(d).padStart(2, '0')
    const dateStr = `${y}-${mm}-${dd}`
    days.push({
      year: y,
      month: m,
      day: d,
      dateStr,
      isCurrentMonth: true,
      isSelected: dateStr === props.currentDate,
      isToday: dateStr === resolvedTodayStr.value,
      isFuture: dateStr > resolvedTodayStr.value,
    })
  }

  // 3. 下月开头补齐天数（凑齐 42 格）
  const nextMonthYear = m === 12 ? y + 1 : y
  const nextMonthNum = m === 12 ? 1 : m + 1
  let nextDay = 1
  while (days.length < 42) {
    const mm = String(nextMonthNum).padStart(2, '0')
    const dd = String(nextDay).padStart(2, '0')
    const dateStr = `${nextMonthYear}-${mm}-${dd}`
    days.push({
      year: nextMonthYear,
      month: nextMonthNum,
      day: nextDay,
      dateStr,
      isCurrentMonth: false,
      isSelected: dateStr === props.currentDate,
      isToday: dateStr === resolvedTodayStr.value,
      isFuture: dateStr > resolvedTodayStr.value,
    })
    nextDay++
  }

  return days
})

function prevYear() {
  viewYear.value -= 1
}

function nextYear() {
  viewYear.value += 1
}

function prevMonth() {
  if (viewMonth.value === 1) {
    viewYear.value -= 1
    viewMonth.value = 12
  } else {
    viewMonth.value -= 1
  }
}

function nextMonth() {
  if (viewMonth.value === 12) {
    viewYear.value += 1
    viewMonth.value = 1
  } else {
    viewMonth.value += 1
  }
}

function handleSelectDay(item) {
  emit('select', item.dateStr)
  emit('update:modelValue', false)
  emit('close')
}

function handleSelectToday() {
  emit('select', resolvedTodayStr.value)
  emit('update:modelValue', false)
  emit('close')
}

function handleClose() {
  emit('update:modelValue', false)
  emit('close')
}
</script>

<template>
  <transition
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-100 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center p-3 backdrop-blur-sm"
      :class="isLight ? 'bg-black/25' : 'bg-black/55'"
      @click.self="handleClose"
    >
      <div
        class="w-full max-w-[320px] rounded-2xl border shadow-2xl p-4 flex flex-col gap-3 select-none transition-colors"
        :class="
          isLight
            ? 'bg-white border-black/[0.1] text-zinc-800'
            : 'bg-[#1C1C24] border-white/[0.12] text-zinc-100'
        "
      >
        <!-- 顶部表头导航：<< < 2026年 10月 > >> 与 关闭按钮 -->
        <div class="flex items-center justify-between pb-2 border-b" :class="isLight ? 'border-black/[0.06]' : 'border-white/[0.08]'">
          <div class="flex items-center gap-1">
            <button
              type="button"
              title="上一年"
              class="w-6 h-6 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
              :class="isLight ? 'hover:bg-zinc-100 text-zinc-500' : 'hover:bg-white/[0.08] text-zinc-400'"
              @click="prevYear"
            >
              <ChevronsLeft class="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="上一月"
              class="w-6 h-6 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
              :class="isLight ? 'hover:bg-zinc-100 text-zinc-500' : 'hover:bg-white/[0.08] text-zinc-400'"
              @click="prevMonth"
            >
              <ChevronLeft class="w-3.5 h-3.5" />
            </button>
          </div>

          <div class="text-[13px] font-bold tracking-wide flex items-center gap-1">
            <span>{{ viewYear }} 年</span>
            <span class="text-blue-500 font-extrabold">{{ viewMonth }} 月</span>
          </div>

          <div class="flex items-center gap-1">
            <button
              type="button"
              title="下一月"
              class="w-6 h-6 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
              :class="isLight ? 'hover:bg-zinc-100 text-zinc-500' : 'hover:bg-white/[0.08] text-zinc-400'"
              @click="nextMonth"
            >
              <ChevronRight class="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="下一年"
              class="w-6 h-6 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
              :class="isLight ? 'hover:bg-zinc-100 text-zinc-500' : 'hover:bg-white/[0.08] text-zinc-400'"
              @click="nextYear"
            >
              <ChevronsRight class="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="关闭"
              class="w-6 h-6 ml-1 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
              :class="isLight ? 'hover:bg-rose-50 text-zinc-400 hover:text-rose-500' : 'hover:bg-white/[0.08] text-zinc-400 hover:text-zinc-200'"
              @click="handleClose"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- 星期表头：日 一 二 三 四 五 六 -->
        <div class="grid grid-cols-7 text-center text-[11px] font-semibold text-zinc-400 py-1">
          <span v-for="w in WEEK_HEADERS" :key="w" class="py-0.5">
            {{ w }}
          </span>
        </div>

        <!-- 42 格日历主体表格 -->
        <div class="grid grid-cols-7 gap-1 text-center">
          <button
            v-for="item in calendarDays"
            :key="item.dateStr"
            type="button"
            class="h-8 rounded-xl flex items-center justify-center text-[12px] font-medium transition-all relative cursor-pointer"
            :class="[
              item.isSelected
                ? 'bg-blue-500 text-white font-bold shadow-md shadow-blue-500/25'
                : item.isCurrentMonth
                  ? isLight
                    ? 'text-zinc-800 hover:bg-blue-50 hover:text-blue-600'
                    : 'text-zinc-200 hover:bg-white/[0.08] hover:text-white'
                  : isLight
                    ? 'text-zinc-400/60 hover:bg-zinc-100 hover:text-zinc-600'
                    : 'text-zinc-500/40 hover:bg-white/[0.04] hover:text-zinc-400',
              item.isToday && !item.isSelected
                ? isLight
                  ? 'border border-blue-500/40 text-blue-600 font-bold'
                  : 'border border-blue-400/50 text-blue-400 font-bold'
                : '',
            ]"
            @click="handleSelectDay(item)"
          >
            <span>{{ item.day }}</span>
            <span
              v-if="item.isToday && !item.isSelected"
              class="absolute bottom-1 w-1 h-1 rounded-full bg-blue-500"
            ></span>
          </button>
        </div>

        <!-- 底部快捷栏：回到今天 & 关闭 -->
        <div class="flex items-center justify-between pt-2 border-t text-[11px]" :class="isLight ? 'border-black/[0.06]' : 'border-white/[0.08]'">
          <span class="text-zinc-400 font-mono text-[10.5px]">
            当前: {{ currentDate || resolvedTodayStr }}
          </span>
          <div class="flex items-center gap-1.5">
            <button
              type="button"
              class="px-2.5 py-1 rounded-lg text-blue-500 hover:bg-blue-500/10 font-medium transition-colors cursor-pointer"
              @click="handleSelectToday"
            >
              回到今天
            </button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>
