<script setup>
import { computed, ref } from 'vue'
import { Settings, Info, X, ChevronsUpDown, Check } from 'lucide-vue-next'
import {
  appPreferences,
  FONT_SCALE_STEPS,
  i18n,
  effectiveTheme,
  applyPreferencesToDom,
} from '../i18n'
import { savePreferences, toggleAlwaysOnTop } from '../api/bridge'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  alwaysOnTop: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'change-preferences', 'update:alwaysOnTop'])

const activeSection = ref('general') // 'general' | 'about'
const langMenuOpen = ref(false)
const themeMenuOpen = ref(false)
const updateChecked = ref(false)

const t = computed(() => i18n.value)
const isLight = computed(() => effectiveTheme.value === 'light')

const languageOptions = computed(() => [
  { value: 'system', label: t.value.langSystem },
  { value: 'zh-CN', label: t.value.langZhCN },
  { value: 'en', label: t.value.langEn },
  { value: 'zh-TW', label: t.value.langZhTW },
])

const themeOptions = computed(() => [
  { value: 'system', label: t.value.themeSystem },
  { value: 'dark', label: t.value.themeDark },
  { value: 'light', label: t.value.themeLight },
])

const currentLanguageLabel = computed(() => {
  const found = languageOptions.value.find((o) => o.value === appPreferences.language)
  return found ? found.label : t.value.langSystem
})

const currentThemeLabel = computed(() => {
  const found = themeOptions.value.find((o) => o.value === appPreferences.theme)
  return found ? found.label : t.value.themeSystem
})

// 当前字体档位索引 (0 ~ 5)
const currentFontStepIndex = computed(() => {
  const scale = Number(appPreferences.font_scale || 1.0)
  let bestIdx = 1
  let minDiff = Infinity
  FONT_SCALE_STEPS.forEach((stepVal, idx) => {
    const diff = Math.abs(stepVal - scale)
    if (diff < minDiff) {
      minDiff = diff
      bestIdx = idx
    }
  })
  return bestIdx
})

const fontSliderPercent = computed(() => {
  const maxIdx = FONT_SCALE_STEPS.length - 1
  return (currentFontStepIndex.value / maxIdx) * 100
})

function closeModal() {
  langMenuOpen.value = false
  themeMenuOpen.value = false
  emit('update:modelValue', false)
}

function closeDropdowns() {
  langMenuOpen.value = false
  themeMenuOpen.value = false
}

async function updatePref(partial) {
  applyPreferencesToDom(partial)
  const saved = await savePreferences(partial)
  if (saved) {
    applyPreferencesToDom(saved)
  }
  emit('change-preferences', { ...appPreferences })
}

async function handleSelectLanguage(val) {
  langMenuOpen.value = false
  await updatePref({ language: val })
}

async function handleSelectTheme(val) {
  themeMenuOpen.value = false
  await updatePref({ theme: val })
}

async function handleFontSliderInput(e) {
  const idx = Number(e.target.value)
  const scale = FONT_SCALE_STEPS[idx] ?? 1.0
  await updatePref({ font_scale: scale })
}

async function handleSelectFontStep(idx) {
  const scale = FONT_SCALE_STEPS[idx] ?? 1.0
  await updatePref({ font_scale: scale })
}

async function handleToggleAutoStart() {
  const nextVal = !appPreferences.auto_start
  await updatePref({ auto_start: nextVal })
}

async function handleToggleTopMost() {
  const nextVal = !props.alwaysOnTop
  const res = await toggleAlwaysOnTop(nextVal)
  const finalState = res?.always_on_top !== undefined ? Boolean(res.always_on_top) : nextVal
  emit('update:alwaysOnTop', finalState)
}

function handleCheckUpdate() {
  updateChecked.value = true
}
</script>

<template>
  <Transition name="settings-fade">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex flex-col select-none"
      :class="isLight ? 'bg-[#F2F2F5] text-zinc-800' : 'bg-[#18181C] text-zinc-100'"
      @click="closeDropdowns"
    >
      <!-- 顶部无边框栏与右上角关闭按钮（参考微信设置窗口右上角 ×） -->
      <div
        class="flex items-center justify-between h-9 px-3.5 shrink-0 border-b"
        :class="
          isLight
            ? 'bg-[#F7F7F9] border-black/[0.06]'
            : 'bg-[#1C1C22] border-white/[0.06]'
        "
      >
        <span
          class="text-[12px] font-semibold tracking-wide"
          :class="isLight ? 'text-zinc-600' : 'text-zinc-300'"
        >
          {{ t.settingsTitle }}
        </span>
        <button
          type="button"
          class="flex items-center justify-center w-6 h-6 rounded-md transition-colors cursor-pointer"
          :class="
            isLight
              ? 'text-zinc-500 hover:bg-black/[0.06] hover:text-zinc-800'
              : 'text-zinc-400 hover:bg-white/[0.08] hover:text-white'
          "
          @click.stop="closeModal"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- 主体：左侧导航 + 右侧卡片区（复刻微信设置图1 & 图2） -->
      <div class="flex flex-1 min-h-0 overflow-hidden">
        <!-- 左侧导航栏 -->
        <aside
          class="w-[122px] shrink-0 p-2 space-y-1 border-r"
          :class="
            isLight
              ? 'bg-[#F7F7F9] border-black/[0.06]'
              : 'bg-[#1C1C22] border-white/[0.06]'
          "
        >
          <button
            type="button"
            class="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[12.5px] font-medium transition-colors cursor-pointer text-left"
            :class="
              activeSection === 'general'
                ? isLight
                  ? 'bg-[#E2E2E6] text-zinc-900 font-semibold'
                  : 'bg-white/[0.11] text-white font-semibold'
                : isLight
                  ? 'text-zinc-600 hover:bg-black/[0.04]'
                  : 'text-zinc-400 hover:bg-white/[0.05]'
            "
            @click.stop="activeSection = 'general'"
          >
            <Settings class="w-4 h-4 shrink-0" />
            <span class="truncate">{{ t.navGeneral }}</span>
          </button>

          <button
            type="button"
            class="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[12.5px] font-medium transition-colors cursor-pointer text-left"
            :class="
              activeSection === 'about'
                ? isLight
                  ? 'bg-[#E2E2E6] text-zinc-900 font-semibold'
                  : 'bg-white/[0.11] text-white font-semibold'
                : isLight
                  ? 'text-zinc-600 hover:bg-black/[0.04]'
                  : 'text-zinc-400 hover:bg-white/[0.05]'
            "
            @click.stop="activeSection = 'about'"
          >
            <Info class="w-4 h-4 shrink-0" />
            <span class="truncate">{{ t.navAbout }}</span>
          </button>
        </aside>

        <!-- 右侧内容滚动区 -->
        <div class="flex-1 overflow-y-auto p-3.5 flex flex-col justify-between">
          <!-- Tab A: 通用设置（严格对标微信图1：语言、外观、字体大小拖动、自启开关） -->
          <div v-if="activeSection === 'general'" class="space-y-3">
            <!-- 卡片 1：语言 -->
            <div
              class="rounded-xl p-3.5 border transition-colors"
              :class="
                isLight
                  ? 'bg-white border-black/[0.05] shadow-[0_1px_3px_rgba(0,0,0,0.03)]'
                  : 'bg-[#23232B] border-white/[0.06]'
              "
            >
              <div class="flex items-center justify-between gap-2 relative">
                <span class="text-[13px] font-medium">{{ t.labelLanguage }}</span>

                <!-- 语言下拉选择器 -->
                <div class="relative" @click.stop>
                  <button
                    type="button"
                    class="inline-flex items-center justify-between gap-2 min-w-[116px] px-2.5 py-1 rounded-md border text-[12px] transition-colors cursor-pointer"
                    :class="
                      isLight
                        ? 'bg-[#F7F7F9] border-black/[0.1] text-zinc-800 hover:bg-[#EFEFF3]'
                        : 'bg-[#2C2C36] border-white/[0.1] text-zinc-100 hover:bg-[#343440]'
                    "
                    @click="
                      langMenuOpen = !langMenuOpen;
                      themeMenuOpen = false
                    "
                  >
                    <span>{{ currentLanguageLabel }}</span>
                    <span class="inline-flex items-center justify-center w-4 h-4 rounded-[4px] bg-[#07C160] text-white shrink-0">
                      <ChevronsUpDown class="w-3 h-3" />
                    </span>
                  </button>

                  <!-- 悬浮选项菜单（复刻微信图1弹出菜单） -->
                  <div
                    v-if="langMenuOpen"
                    class="absolute right-0 top-full mt-1.5 w-36 rounded-xl py-1.5 z-30 border shadow-xl"
                    :class="
                      isLight
                        ? 'bg-white border-black/[0.08] text-zinc-800'
                        : 'bg-[#2B2B35] border-white/[0.12] text-zinc-100'
                    "
                  >
                    <button
                      v-for="opt in languageOptions"
                      :key="opt.value"
                      type="button"
                      class="w-full flex items-center justify-between px-3 py-1.5 text-[12.5px] text-left transition-colors cursor-pointer"
                      :class="
                        isLight
                          ? 'hover:bg-black/[0.05]'
                          : 'hover:bg-white/[0.08]'
                      "
                      @click="handleSelectLanguage(opt.value)"
                    >
                      <span>{{ opt.label }}</span>
                      <Check
                        v-if="appPreferences.language === opt.value"
                        class="w-3.5 h-3.5 text-[#07C160]"
                      />
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 卡片 2：外观 & 字体大小（复刻微信图1中间卡片） -->
            <div
              class="rounded-xl p-3.5 border space-y-3.5 transition-colors"
              :class="
                isLight
                  ? 'bg-white border-black/[0.05] shadow-[0_1px_3px_rgba(0,0,0,0.03)]'
                  : 'bg-[#23232B] border-white/[0.06]'
              "
            >
              <!-- 外观行 -->
              <div class="flex items-center justify-between gap-2 relative">
                <span class="text-[13px] font-medium">{{ t.labelAppearance }}</span>

                <div class="relative" @click.stop>
                  <button
                    type="button"
                    class="inline-flex items-center justify-between gap-2 min-w-[116px] px-2.5 py-1 rounded-md border text-[12px] transition-colors cursor-pointer"
                    :class="
                      isLight
                        ? 'bg-[#F7F7F9] border-black/[0.1] text-zinc-800 hover:bg-[#EFEFF3]'
                        : 'bg-[#2C2C36] border-white/[0.1] text-zinc-100 hover:bg-[#343440]'
                    "
                    @click="
                      themeMenuOpen = !themeMenuOpen;
                      langMenuOpen = false
                    "
                  >
                    <span>{{ currentThemeLabel }}</span>
                    <span class="inline-flex items-center justify-center w-4 h-4 rounded-[4px] bg-[#07C160] text-white shrink-0">
                      <ChevronsUpDown class="w-3 h-3" />
                    </span>
                  </button>

                  <div
                    v-if="themeMenuOpen"
                    class="absolute right-0 top-full mt-1.5 w-36 rounded-xl py-1.5 z-30 border shadow-xl"
                    :class="
                      isLight
                        ? 'bg-white border-black/[0.08] text-zinc-800'
                        : 'bg-[#2B2B35] border-white/[0.12] text-zinc-100'
                    "
                  >
                    <button
                      v-for="opt in themeOptions"
                      :key="opt.value"
                      type="button"
                      class="w-full flex items-center justify-between px-3 py-1.5 text-[12.5px] text-left transition-colors cursor-pointer"
                      :class="
                        isLight
                          ? 'hover:bg-black/[0.05]'
                          : 'hover:bg-white/[0.08]'
                      "
                      @click="handleSelectTheme(opt.value)"
                    >
                      <span>{{ opt.label }}</span>
                      <Check
                        v-if="appPreferences.theme === opt.value"
                        class="w-3.5 h-3.5 text-[#07C160]"
                      />
                    </button>
                  </div>
                </div>
              </div>

              <!-- 分割线 -->
              <div
                class="h-px"
                :class="isLight ? 'bg-black/[0.06]' : 'bg-white/[0.06]'"
              ></div>

              <!-- 字体大小行（复刻微信图1刻度拖动条：小 / 标准 / ... / 大） -->
              <div class="flex items-center justify-between gap-3 pt-0.5">
                <span class="text-[13px] font-medium shrink-0">{{ t.labelFontSize }}</span>

                <div class="w-[165px] shrink-0">
                  <!-- 刻度轨道与滑块 -->
                  <div class="relative h-6 flex items-center">
                    <!-- 底色横轨 -->
                    <div
                      class="w-full h-[3px] rounded-full"
                      :class="isLight ? 'bg-zinc-200' : 'bg-zinc-700'"
                    ></div>

                    <!-- 微信绿高亮进度条 -->
                    <div
                      class="absolute left-0 h-[3px] rounded-full bg-[#07C160] transition-all duration-100"
                      :style="{ width: `${fontSliderPercent}%` }"
                    ></div>

                    <!-- 6 个竖向刻度点 -->
                    <div class="absolute inset-x-0 flex items-center justify-between pointer-events-none">
                      <span
                        v-for="(_, idx) in FONT_SCALE_STEPS"
                        :key="idx"
                        class="w-[2px] h-2 rounded-full transition-colors"
                        :class="
                          idx <= currentFontStepIndex
                            ? 'bg-[#07C160]'
                            : isLight
                              ? 'bg-zinc-300'
                              : 'bg-zinc-600'
                        "
                      ></span>
                    </div>

                    <!-- 白色圆形滑块展示 -->
                    <div
                      class="absolute w-3.5 h-3.5 rounded-full bg-white shadow-[0_1px_4px_rgba(0,0,0,0.35)] border border-black/10 pointer-events-none -translate-x-1/2 transition-all duration-100"
                      :style="{ left: `${fontSliderPercent}%` }"
                    ></div>

                    <!-- 原生透明 range input 支持丝滑拖拽 -->
                    <input
                      type="range"
                      min="0"
                      :max="FONT_SCALE_STEPS.length - 1"
                      step="1"
                      :value="currentFontStepIndex"
                      class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                      @input="handleFontSliderInput"
                    />
                  </div>

                  <!-- 刻度下方标签：小 (0) / 标准 (1) / 大 (5) -->
                  <div class="relative h-4 text-[10.5px] text-zinc-400">
                    <button
                      type="button"
                      class="absolute left-0 -translate-x-1/4 cursor-pointer hover:text-[#07C160]"
                      :class="currentFontStepIndex === 0 ? 'text-[#07C160] font-semibold' : ''"
                      @click="handleSelectFontStep(0)"
                    >
                      {{ t.fontSmall }}
                    </button>
                    <button
                      type="button"
                      class="absolute left-[20%] -translate-x-1/2 cursor-pointer hover:text-[#07C160]"
                      :class="currentFontStepIndex === 1 ? 'text-[#07C160] font-semibold' : ''"
                      @click="handleSelectFontStep(1)"
                    >
                      {{ t.fontStandard }}
                    </button>
                    <button
                      type="button"
                      class="absolute right-0 translate-x-1/4 cursor-pointer hover:text-[#07C160]"
                      :class="
                        currentFontStepIndex === FONT_SCALE_STEPS.length - 1
                          ? 'text-[#07C160] font-semibold'
                          : ''
                      "
                      @click="handleSelectFontStep(FONT_SCALE_STEPS.length - 1)"
                    >
                      {{ t.fontLarge }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 卡片 3：开机自启与置顶开关（复刻微信图1底部开关卡片） -->
            <div
              class="rounded-xl p-3.5 border space-y-3 transition-colors"
              :class="
                isLight
                  ? 'bg-white border-black/[0.05] shadow-[0_1px_3px_rgba(0,0,0,0.03)]'
                  : 'bg-[#23232B] border-white/[0.06]'
              "
            >
              <!-- 开机自动启动 -->
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <div class="text-[13px] font-medium">{{ t.labelAutoStart }}</div>
                  <div class="text-[11px] text-zinc-400 mt-0.5 leading-snug">
                    {{ t.descAutoStart }}
                  </div>
                </div>

                <!-- 微信同款绿色 Toggle Switch -->
                <button
                  type="button"
                  role="switch"
                  :aria-checked="appPreferences.auto_start"
                  class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
                  :class="
                    appPreferences.auto_start
                      ? 'bg-[#07C160]'
                      : isLight
                        ? 'bg-zinc-300'
                        : 'bg-zinc-600'
                  "
                  @click="handleToggleAutoStart"
                >
                  <span
                    class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
                    :class="appPreferences.auto_start ? 'translate-x-4' : 'translate-x-0'"
                  />
                </button>
              </div>

              <div
                class="h-px"
                :class="isLight ? 'bg-black/[0.06]' : 'bg-white/[0.06]'"
              ></div>

              <!-- 窗口始终置顶 -->
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <div class="text-[13px] font-medium">{{ t.labelAlwaysOnTopSetting }}</div>
                  <div class="text-[11px] text-zinc-400 mt-0.5 leading-snug">
                    {{ t.descAlwaysOnTopSetting }}
                  </div>
                </div>

                <button
                  type="button"
                  role="switch"
                  :aria-checked="alwaysOnTop"
                  class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
                  :class="
                    alwaysOnTop
                      ? 'bg-[#07C160]'
                      : isLight
                        ? 'bg-zinc-300'
                        : 'bg-zinc-600'
                  "
                  @click="handleToggleTopMost"
                >
                  <span
                    class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
                    :class="alwaysOnTop ? 'translate-x-4' : 'translate-x-0'"
                  />
                </button>
              </div>
            </div>
          </div>

          <!-- Tab B: 关于 Dayflow（严格对标微信图2：版本信息 + 版本号） -->
          <div v-else class="space-y-3">
            <!-- 版本信息卡片 -->
            <div
              class="rounded-xl p-4 border flex items-center justify-between gap-3"
              :class="
                isLight
                  ? 'bg-white border-black/[0.05] shadow-[0_1px_3px_rgba(0,0,0,0.03)]'
                  : 'bg-[#23232B] border-white/[0.06]'
              "
            >
              <div>
                <div class="text-[13.5px] font-medium">{{ t.labelVersionInfo }}</div>
                <div class="text-[12px] text-zinc-400 mt-0.5 font-mono">
                  {{ appPreferences.version || '1.0.0' }}
                </div>
              </div>

              <button
                type="button"
                class="px-3.5 py-1.5 rounded-md text-[12px] font-medium transition-colors cursor-pointer"
                :class="
                  isLight
                    ? 'bg-[#EBEBEF] hover:bg-[#E0E0E6] text-zinc-800'
                    : 'bg-white/[0.08] hover:bg-white/[0.14] text-zinc-200'
                "
                @click="handleCheckUpdate"
              >
                {{ updateChecked ? t.btnLatestVersion : t.btnCheckUpdate }}
              </button>
            </div>

            <!-- 本地数据说明卡片 -->
            <div
              class="rounded-xl p-4 border"
              :class="
                isLight
                  ? 'bg-white border-black/[0.05] shadow-[0_1px_3px_rgba(0,0,0,0.03)]'
                  : 'bg-[#23232B] border-white/[0.06]'
              "
            >
              <div class="text-[13px] font-medium">{{ t.labelDataStorage }}</div>
              <div class="text-[11.5px] text-zinc-400 mt-1 leading-relaxed">
                {{ t.descDataStorage }}
              </div>
            </div>
          </div>

          <!-- 底部版权信息（对标微信图2底部） -->
          <div class="pt-6 pb-1 text-center text-[11px] text-zinc-400 space-y-0.5">
            <div>{{ t.copyrightText }}</div>
            <div class="text-[10.5px] text-zinc-400/80">
              Copyright © 2026 Dayflow. All Rights Reserved.
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.settings-fade-enter-active,
.settings-fade-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}
.settings-fade-enter-from,
.settings-fade-leave-to {
  opacity: 0;
  transform: scale(0.985);
}
</style>
