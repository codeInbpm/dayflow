<script setup>
import { computed, ref, watch } from 'vue'
import { X, Clock3, Tag, EyeOff, Eye, Terminal, Activity } from 'lucide-vue-next'
import {
  CATEGORY_META,
  CATEGORY_ORDER,
  fetchAppDetail,
  updateAppSettings,
  formatDuration,
} from '../api/bridge'
import {
  i18n,
  effectiveTheme,
  getCategoryLabel,
  getLocalizedAppName,
} from '../i18n'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  visible: {
    type: Boolean,
    default: false,
  },
  appId: {
    type: Number,
    default: null,
  },
  initialApp: {
    type: Object,
    default: null,
  },
  dateStr: {
    type: String,
    default: null,
  },
  activeApp: {
    type: Object,
    default: null,
  },
  categoryMeta: {
    type: Object,
    default: () => CATEGORY_META,
  },
})

const emit = defineEmits(['update:modelValue', 'close', 'updated'])

const isOpen = computed(() => Boolean(props.modelValue || props.visible))
const detail = ref(null)
const loading = ref(false)
const saving = ref(false)
const hoveredHour = ref(null)
const pendingCategory = ref(null)
const t = computed(() => i18n.value)
const isLight = computed(() => effectiveTheme.value === 'light')

const resolvedAppId = computed(() => {
  if (props.appId !== null && props.appId !== undefined) return Number(props.appId)
  if (props.initialApp?.id !== undefined) return Number(props.initialApp.id)
  if (props.initialApp?.app_id !== undefined) return Number(props.initialApp.app_id)
  return null
})

const appData = computed(() => {
  const d = detail.value
  const init = props.initialApp || {}
  const rawName = d?.display_name || init.display_name || init.exe_name || '未知应用'
  return {
    id: d?.id ?? init.id ?? init.app_id ?? resolvedAppId.value,
    display_name: getLocalizedAppName(rawName),
    exe_name: d?.exe_name || init.exe_name || '',
    exe_path: d?.exe_path || init.exe_path || '',
    category: d?.category || init.category || 'other',
    icon_base64: d?.icon_base64 || init.icon_base64 || '',
    is_ignored: Boolean(d?.is_ignored ?? init.is_ignored ?? false),
    total_sec: Number(d?.total_sec ?? init.total_sec ?? 0),
  }
})

const sessions = computed(() => {
  const list = detail.value?.sessions || []
  // 默认按时间倒序展示（最新使用时间段在最前，也可一目了然看全天流水）
  return [...list].sort(
    (a, b) => b.hour_bucket - a.hour_bucket || String(b.start_time).localeCompare(String(a.start_time))
  )
})

const hourlyDistribution = computed(() => {
  const raw = detail.value?.hourly_sec || Array(24).fill(0)
  const maxSec = Math.max(600, ...raw.map((v) => Number(v || 0)))
  return Array.from({ length: 24 }, (_, hour) => {
    const sec = Math.max(0, Number(raw[hour] || 0))
    const pct = sec > 0 ? Math.max(8, Math.min(100, (sec / maxSec) * 100)) : 0
    return {
      hour,
      sec,
      pct,
    }
  })
})

const currentCategoryMeta = computed(() => {
  const cat = appData.value.category
  const base = props.categoryMeta?.[cat] || CATEGORY_META[cat] || CATEGORY_META.other
  return {
    ...base,
    label: getCategoryLabel(cat),
  }
})

const categoryOptions = computed(() =>
  CATEGORY_ORDER.map((key) => {
    const meta = props.categoryMeta?.[key] || CATEGORY_META[key]
    return {
      key,
      label: getCategoryLabel(key),
      color: meta.color,
    }
  })
)

const isCurrentlyActive = computed(() => {
  if (!props.activeApp || !appData.value.id) return false
  return Number(props.activeApp.app_id) === Number(appData.value.id)
})

async function loadAppDetail(silent = false) {
  if (!resolvedAppId.value || !isOpen.value) return
  if (!silent) loading.value = true
  try {
    const res = await fetchAppDetail(resolvedAppId.value, props.dateStr)
    if (res) {
      detail.value = res
    }
  } finally {
    if (!silent) loading.value = false
  }
}

watch(
  () => [isOpen.value, resolvedAppId.value, props.dateStr],
  ([open, id]) => {
    if (open && id) {
      loadAppDetail(false)
    } else if (!open) {
      detail.value = null
      hoveredHour.value = null
    }
  },
  { immediate: true }
)

function closeModal() {
  pendingCategory.value = null
  emit('update:modelValue', false)
  emit('close')
}

function handleSelectCategory(newCat) {
  if (!appData.value.id || saving.value || appData.value.category === newCat) return
  pendingCategory.value = newCat
}

function cancelCategoryChange() {
  pendingCategory.value = null
}

async function confirmCategoryChange() {
  if (!appData.value.id || saving.value || !pendingCategory.value) return
  const newCat = pendingCategory.value
  saving.value = true
  try {
    const updated = await updateAppSettings(appData.value.id, { category: newCat })
    if (detail.value) {
      detail.value = {
        ...detail.value,
        category: updated.category || newCat,
      }
    }
    emit('updated', updated)
    pendingCategory.value = null
  } finally {
    saving.value = false
  }
}

function formatConfirmMsg() {
  if (!pendingCategory.value) return ''
  const oldLabel = getCategoryLabel(appData.value.category)
  const newLabel = getCategoryLabel(pendingCategory.value)
  return (t.value.confirmChangeCategoryMsg || '是否将「{name}」的所属分类，由“{oldCat}”调整为“{newCat}”？')
    .replace('{name}', appData.value.display_name)
    .replace('{oldCat}', oldLabel)
    .replace('{newCat}', newLabel)
}

async function handleToggleIgnore() {
  if (!appData.value.id || saving.value) return
  saving.value = true
  const nextIgnored = !appData.value.is_ignored
  try {
    const updated = await updateAppSettings(appData.value.id, { is_ignored: nextIgnored })
    if (detail.value) {
      detail.value = {
        ...detail.value,
        is_ignored: Boolean(updated.is_ignored ?? nextIgnored),
      }
    }
    emit('updated', updated)
    if (nextIgnored) {
      closeModal()
    }
  } finally {
    saving.value = false
  }
}

defineExpose({
  refresh: () => loadAppDetail(true),
})
</script>

<template>
  <transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="isOpen"
      class="fixed inset-0 z-50 flex items-end sm:items-center justify-center backdrop-blur-sm p-2.5"
      :class="isLight ? 'bg-black/35' : 'bg-black/65'"
      @click.self="closeModal"
    >
      <div
        class="w-full max-w-[412px] max-h-[88vh] flex flex-col rounded-2xl border shadow-2xl overflow-hidden transition-colors"
        :class="
          isLight
            ? 'bg-white border-black/[0.08] text-zinc-800'
            : 'bg-[#1A1A22] border-white/[0.1] text-zinc-100'
        "
      >
        <!-- 顶部：软件图标、名称、总时长与关闭按钮 -->
        <div
          class="flex items-start justify-between gap-3 p-4 border-b transition-colors"
          :class="
            isLight
              ? 'bg-[#F7F7FA] border-black/[0.06]'
              : 'bg-[#20202A] border-white/[0.07]'
          "
        >
          <div class="flex items-center gap-3 min-w-0">
            <div class="relative w-11 h-11 shrink-0">
              <img
                v-if="appData.icon_base64"
                :src="appData.icon_base64"
                :alt="appData.display_name"
                class="w-11 h-11 rounded-xl object-contain bg-white/[0.05] p-1 border border-white/[0.08]"
              />
              <div
                v-else
                class="w-11 h-11 rounded-xl flex items-center justify-center text-[18px] font-bold text-white"
                :style="{ backgroundColor: currentCategoryMeta.color }"
              >
                {{ String(appData.display_name || '?').slice(0, 1).toUpperCase() }}
              </div>

              <span
                v-if="isCurrentlyActive"
                class="absolute -bottom-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full"
                :class="isLight ? 'bg-[#F7F7FA]' : 'bg-[#20202A]'"
              >
                <span class="animate-ping absolute inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
            </div>

            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <h3 class="text-[15px] font-bold text-zinc-100 truncate">
                  {{ appData.display_name }}
                </h3>
                <span
                  v-if="isCurrentlyActive"
                  class="px-1.5 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-[10px] font-medium shrink-0"
                  :class="isLight ? 'text-emerald-600' : 'text-emerald-300'"
                >
                  {{ t.runningForeground }}
                </span>
              </div>
              <p class="text-[11px] text-zinc-400 font-mono truncate mt-0.5">
                {{ appData.exe_name || appData.exe_path }}
              </p>
              <div class="flex items-center gap-2 mt-1 text-[12px]">
                <span class="font-semibold text-zinc-100">
                  {{ t.todayTotalPrefix }} {{ formatDuration(appData.total_sec) }}
                </span>
                <span class="text-zinc-500">·</span>
                <span class="text-zinc-400">
                  {{ t.sessionsCountText.replace('{n}', String(sessions.length)) }}
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            class="flex items-center justify-center w-7 h-7 rounded-lg text-zinc-400 hover:bg-white/[0.08] hover:text-zinc-100 transition-colors shrink-0 cursor-pointer"
            :title="t.closeDetail"
            @click="closeModal"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- 主体滚动区 -->
        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- 1. 该软件专属 24 小时使用分布迷你柱状图 -->
          <div
            class="rounded-xl border p-3 transition-colors"
            :class="
              isLight
                ? 'bg-[#F5F5F9] border-black/[0.06]'
                : 'bg-[#15151B] border-white/[0.06]'
            "
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-1.5 text-[12px] font-semibold text-zinc-200">
                <Activity class="w-3.5 h-3.5" :style="{ color: currentCategoryMeta.color }" />
                <span>{{ t.dist24hTitle }}</span>
              </div>
              <span class="text-[11px] text-zinc-400 font-mono">
                <template v-if="hoveredHour !== null">
                  {{ String(hoveredHour).padStart(2, '0') }}:00 · {{ formatDuration(hourlyDistribution[hoveredHour]?.sec || 0) }}
                </template>
                <template v-else>
                  {{ t.hoverToViewHour }}
                </template>
              </span>
            </div>

            <div class="grid grid-cols-24 items-end h-14 gap-[2.5px] pt-1">
              <div
                v-for="item in hourlyDistribution"
                :key="item.hour"
                class="group relative flex flex-col justify-end h-full w-full cursor-pointer"
                @mouseenter="hoveredHour = item.hour"
                @mouseleave="hoveredHour = null"
              >
                <div class="w-full h-full rounded-t-[3px] bg-white/[0.03] flex items-end overflow-hidden">
                  <div
                    v-if="item.sec > 0"
                    class="w-full rounded-t-[3px] transition-all duration-300"
                    :style="{
                      height: `${item.pct}%`,
                      backgroundColor: currentCategoryMeta.color,
                    }"
                  ></div>
                </div>
              </div>
            </div>

            <div class="flex justify-between text-[10px] text-zinc-500 mt-1 font-mono">
              <span>00:00</span>
              <span>06:00</span>
              <span>12:00</span>
              <span>18:00</span>
              <span>23:00</span>
            </div>
          </div>

          <!-- 2. 软件分类归属与屏蔽设置 -->
          <div
            class="rounded-xl border p-3 space-y-2.5 transition-colors"
            :class="
              isLight
                ? 'bg-[#F5F5F9] border-black/[0.06]'
                : 'bg-[#15151B] border-white/[0.06]'
            "
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1.5 text-[12px] font-semibold text-zinc-200">
                <Tag class="w-3.5 h-3.5 text-zinc-400" />
                <span>{{ t.appCategoryTitle }}</span>
              </div>

              <!-- 屏蔽此软件开关 -->
              <button
                type="button"
                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-colors border cursor-pointer"
                :class="
                  appData.is_ignored
                    ? isLight
                      ? 'bg-emerald-500/15 text-emerald-700 border-emerald-500/30 hover:bg-emerald-500/25'
                      : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/25'
                    : isLight
                      ? 'bg-rose-500/10 text-rose-600 border-rose-500/25 hover:bg-rose-500/20'
                      : 'bg-rose-500/10 text-rose-300 border-rose-500/25 hover:bg-rose-500/20'
                "
                :disabled="saving"
                @click="handleToggleIgnore"
              >
                <Eye v-if="appData.is_ignored" class="w-3 h-3" />
                <EyeOff v-else class="w-3 h-3" />
                <span>{{ appData.is_ignored ? t.btnRestoreApp : t.btnIgnoreApp }}</span>
              </button>
            </div>

            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="cat in categoryOptions"
                :key="cat.key"
                type="button"
                class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all duration-150 border cursor-pointer"
                :class="
                  (pendingCategory ? pendingCategory === cat.key : appData.category === cat.key)
                    ? isLight
                      ? 'bg-white text-zinc-900 border-blue-500/40 font-semibold shadow-sm ring-1 ring-blue-500/30'
                      : 'bg-white/[0.12] text-white border-white/[0.25] shadow-sm ring-1 ring-white/20'
                    : isLight
                      ? 'bg-white/70 text-zinc-600 border-black/[0.06] hover:bg-white hover:text-zinc-900'
                      : 'bg-white/[0.03] text-zinc-400 border-white/[0.05] hover:bg-white/[0.07] hover:text-zinc-200'
                "
                :disabled="saving"
                @click="handleSelectCategory(cat.key)"
              >
                <span
                  class="w-2 h-2 rounded-full"
                  :style="{ backgroundColor: cat.color }"
                ></span>
                <span>{{ cat.label }}</span>
              </button>
            </div>

            <!-- 分类变更确认提示条 -->
            <transition
              enter-active-class="transition duration-150 ease-out"
              enter-from-class="opacity-0 -translate-y-1"
              enter-to-class="opacity-100 translate-y-0"
              leave-active-class="transition duration-100 ease-in"
              leave-from-class="opacity-100 translate-y-0"
              leave-to-class="opacity-0 -translate-y-1"
            >
              <div
                v-if="pendingCategory"
                class="rounded-xl border p-3 mt-2.5 transition-colors"
                :class="
                  isLight
                    ? 'bg-amber-500/10 border-amber-500/25 text-amber-950'
                    : 'bg-amber-500/10 border-amber-500/25 text-amber-200'
                "
              >
                <div class="flex items-start gap-2">
                  <div class="text-[12px] leading-relaxed flex-1">
                    {{ formatConfirmMsg() }}
                  </div>
                </div>
                <div class="flex items-center justify-end gap-2 mt-2.5 pt-2 border-t border-amber-500/20">
                  <button
                    type="button"
                    class="px-2.5 py-1 rounded-lg text-[11px] font-medium border cursor-pointer transition-colors"
                    :class="
                      isLight
                        ? 'bg-white/80 border-black/10 text-zinc-700 hover:bg-white'
                        : 'bg-white/10 border-white/10 text-zinc-300 hover:bg-white/15'
                    "
                    @click="cancelCategoryChange"
                  >
                    {{ t.btnCancel }}
                  </button>
                  <button
                    type="button"
                    class="px-3 py-1 rounded-lg text-[11px] font-medium bg-emerald-500 text-white hover:bg-emerald-600 shadow cursor-pointer transition-colors"
                    :disabled="saving"
                    @click="confirmCategoryChange"
                  >
                    {{ saving ? '...' : t.btnConfirmChange }}
                  </button>
                </div>
              </div>
            </transition>
          </div>

          <!-- 3. 具体使用时间段流水列表 (精确回答“哪个时间段使用了该软件”) -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-1.5 text-[12px] font-semibold text-zinc-200">
                <Clock3 class="w-3.5 h-3.5 text-blue-500" />
                <span>{{ t.sessionListTitle }}</span>
              </div>
              <span class="text-[11px] text-zinc-500">
                {{ t.orderByTime }}
              </span>
            </div>

            <div v-if="sessions.length > 0" class="space-y-1.5">
              <div
                v-for="s in sessions"
                :key="s.id"
                class="flex items-center justify-between gap-2.5 p-2.5 rounded-xl border transition-colors"
                :class="
                  isLight
                    ? 'bg-[#F5F5F9] border-black/[0.06] hover:border-black/[0.12]'
                    : 'bg-[#15151B] border-white/[0.05] hover:border-white/[0.1]'
                "
              >
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span
                      class="px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold text-zinc-200 bg-white/[0.06]"
                    >
                      {{ s.start_time }} - {{ s.end_time }}
                    </span>
                    <span class="text-[11px] text-zinc-500">
                      {{ t.xAxisHour.replace('{h}', String(s.hour_bucket)) }}
                    </span>
                  </div>
                  <div class="flex items-center gap-1.5 mt-1 text-[11px] text-zinc-400 truncate">
                    <Terminal class="w-3 h-3 text-zinc-500 shrink-0" />
                    <span class="truncate" :title="s.last_window_title || appData.display_name">
                      {{ s.last_window_title || appData.display_name }}
                    </span>
                  </div>
                </div>

                <div class="text-right shrink-0">
                  <span
                    class="inline-block px-2 py-0.5 rounded-lg text-[11px] font-semibold"
                    :style="{
                      backgroundColor: `${currentCategoryMeta.color}1F`,
                      color: currentCategoryMeta.color,
                    }"
                  >
                    {{ formatDuration(s.duration_sec) }}
                  </span>
                </div>
              </div>
            </div>

            <div
              v-else
              class="py-6 text-center rounded-xl border border-dashed text-[12px] text-zinc-500"
              :class="
                isLight
                  ? 'bg-[#F5F5F9] border-black/[0.08]'
                  : 'bg-[#15151B] border-white/[0.06]'
              "
            >
              {{ t.emptyAppSessions }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.grid-cols-24 {
  grid-template-columns: repeat(24, minmax(0, 1fr));
}
</style>
