import { computed, reactive } from 'vue'

export const appPreferences = reactive({
  language: 'system', // 'system' | 'zh-CN' | 'en' | 'zh-TW'
  theme: 'dark',      // 'system' | 'dark' | 'light'
  font_scale: 1.0,    // 0.92 (小) | 1.00 (标准) | 1.05 | 1.10 | 1.15 | 1.20 (大)
  auto_start: false,
  version: '1.0.0',
})

// 6 档字体大小刻度（对应微信设置图1：第1格“小”，第2格“标准”，第6格“大”）
export const FONT_SCALE_STEPS = [0.92, 1.0, 1.05, 1.1, 1.15, 1.2]

const MESSAGES = {
  'zh-CN': {
    appSubTitle: '桌面时长管家',
    recording: '正在记录',
    pinActive: '已固定置顶 (点击取消)',
    pinInactive: '固定在窗口最前端',
    openSettings: '设置',
    minimizeWin: '最小化窗口',
    quitApp: '结束并退出程序',
    tabDashboard: '今日看板',
    tabRanking: '应用排行',
    tabTimeline: '时段流水',
    tabIgnored: '已屏蔽',
    periodDay: '每日',
    periodWeek: '每周',
    periodMonth: '每月',
    statusCollecting: '实时采集中',
    statusReady: '后台就绪',
    backToToday: '回到今日',
    backToWeek: '回到本周',
    backToMonth: '回到本月',
    dailyAvg: '日均',
    screenTimeTitle: '屏幕使用时间',
    weekTotalTitle: '本周累计使用',
    monthTotalTitle: '本月累计使用',
    unitHour: '小时',
    unitMinute: '分钟',
    unitSecond: '秒',
    catAll: '全部',
    catSocial: '社交通讯',
    catCreative: '创意与开发',
    catEntertainment: '影音娱乐',
    catProductivity: '办公与效率',
    catOther: '其他',
    rankingTitleSuffix: '软件时长排行',
    totalPrefix: '总计',
    timelineTitle: '时段使用流水',
    recordsSuffix: '条记录',
    sortNewest: '最新时段在前',
    sortChrono: '00:00 顺序排列',
    emptyTimeline: '当前筛选条件下暂无时段使用流水',
    ignoredListTitle: '已屏蔽的软件名单',
    ignoredHint: '不计入屏幕使用时长',
    restoreTrack: '恢复统计',
    emptyIgnored: '当前没有被屏蔽的软件',
    emptyIgnoredSub: '可在任意软件的详情面板中点击“屏蔽此软件”将其排除统计',
    // 设置面板（对标微信桌面版设置）
    settingsTitle: '设置',
    navGeneral: '通用',
    navAbout: '关于 Dayflow',
    labelLanguage: '语言',
    langSystem: '跟随系统',
    langZhCN: '简体中文',
    langEn: 'English',
    langZhTW: '繁體中文',
    labelAppearance: '外观',
    themeSystem: '跟随系统',
    themeDark: '深色模式',
    themeLight: '浅色模式',
    labelFontSize: '字体大小',
    fontSmall: '小',
    fontStandard: '标准',
    fontLarge: '大',
    labelAutoStart: '开机自动启动 Dayflow',
    descAutoStart: '开启后，登录 Windows 系统时将自动启动并统计软件使用时长。',
    labelAlwaysOnTopSetting: '窗口始终置顶显示',
    descAlwaysOnTopSetting: '开启后，Dayflow 窗口将固定在其他桌面软件最前端。',
    labelVersionInfo: '版本信息',
    btnCheckUpdate: '检查更新',
    btnLatestVersion: '已是最新版本',
    labelDataStorage: '本地数据存储',
    descDataStorage: '所有使用记录均保存在本地 SQLite 数据库，永久留存且绝不上传云端。',
    copyrightText: 'Dayflow 桌面时长管家 · 专为 Windows 打造',
  },
  'zh-TW': {
    appSubTitle: '桌面時長管家',
    recording: '正在記錄',
    pinActive: '已固定置頂 (點擊取消)',
    pinInactive: '固定在視窗最前端',
    openSettings: '設定',
    minimizeWin: '最小化視窗',
    quitApp: '結束並退出程式',
    tabDashboard: '今日看板',
    tabRanking: '應用排行',
    tabTimeline: '時段流水',
    tabIgnored: '已封鎖',
    periodDay: '每日',
    periodWeek: '每週',
    periodMonth: '每月',
    statusCollecting: '即時採集中',
    statusReady: '背景就緒',
    backToToday: '回到今日',
    backToWeek: '回到本週',
    backToMonth: '回到本月',
    dailyAvg: '日均',
    screenTimeTitle: '螢幕使用時間',
    weekTotalTitle: '本週累計使用',
    monthTotalTitle: '本月累計使用',
    unitHour: '小時',
    unitMinute: '分鐘',
    unitSecond: '秒',
    catAll: '全部',
    catSocial: '社交通訊',
    catCreative: '創意與開發',
    catEntertainment: '影音娛樂',
    catProductivity: '辦公與效率',
    catOther: '其他',
    rankingTitleSuffix: '軟體時長排行',
    totalPrefix: '總計',
    timelineTitle: '時段使用流水',
    recordsSuffix: '筆記錄',
    sortNewest: '最新時段在前',
    sortChrono: '00:00 順序排列',
    emptyTimeline: '目前篩選條件下暫無時段使用流水',
    ignoredListTitle: '已封鎖的軟體名單',
    ignoredHint: '不計入螢幕使用時長',
    restoreTrack: '恢復統計',
    emptyIgnored: '目前沒有被封鎖的軟體',
    emptyIgnoredSub: '可在任意軟體的詳情面板中點擊「封鎖此軟體」將其排除統計',
    settingsTitle: '設定',
    navGeneral: '通用',
    navAbout: '關於 Dayflow',
    labelLanguage: '語言',
    langSystem: '跟隨系統',
    langZhCN: '简体中文',
    langEn: 'English',
    langZhTW: '繁體中文',
    labelAppearance: '外觀',
    themeSystem: '跟隨系統',
    themeDark: '深色模式',
    themeLight: '淺色模式',
    labelFontSize: '字體大小',
    fontSmall: '小',
    fontStandard: '標準',
    fontLarge: '大',
    labelAutoStart: '開機自動啟動 Dayflow',
    descAutoStart: '開啟後，登入 Windows 系統時將自動啟動並統計軟體使用時長。',
    labelAlwaysOnTopSetting: '視窗始終置頂顯示',
    descAlwaysOnTopSetting: '開啟後，Dayflow 視窗將固定在其他桌面軟體最前端。',
    labelVersionInfo: '版本資訊',
    btnCheckUpdate: '檢查更新',
    btnLatestVersion: '已是最新版本',
    labelDataStorage: '本機資料儲存',
    descDataStorage: '所有使用記錄均保存在本機 SQLite 資料庫，永久留存且絕不連網上傳。',
    copyrightText: 'Dayflow 桌面時長管家 · 專為 Windows 打造',
  },
  en: {
    appSubTitle: 'Screen Time Tracker',
    recording: 'Tracking',
    pinActive: 'Pinned on top (Click to unpin)',
    pinInactive: 'Pin window on top',
    openSettings: 'Settings',
    minimizeWin: 'Minimize',
    quitApp: 'Quit Dayflow',
    tabDashboard: 'Overview',
    tabRanking: 'Rankings',
    tabTimeline: 'Timeline',
    tabIgnored: 'Ignored',
    periodDay: 'Day',
    periodWeek: 'Week',
    periodMonth: 'Month',
    statusCollecting: 'Tracking Live',
    statusReady: 'Standing By',
    backToToday: 'Today',
    backToWeek: 'This Week',
    backToMonth: 'This Month',
    dailyAvg: 'Daily Avg',
    screenTimeTitle: 'Screen Time',
    weekTotalTitle: 'Weekly Total',
    monthTotalTitle: 'Monthly Total',
    unitHour: 'h',
    unitMinute: 'm',
    unitSecond: 's',
    catAll: 'All',
    catSocial: 'Social',
    catCreative: 'Dev & Create',
    catEntertainment: 'Media & Fun',
    catProductivity: 'Productivity',
    catOther: 'Other',
    rankingTitleSuffix: 'App Usage Ranking',
    totalPrefix: 'Total',
    timelineTitle: 'Usage Timeline',
    recordsSuffix: 'sessions',
    sortNewest: 'Newest First',
    sortChrono: '00:00 Order',
    emptyTimeline: 'No usage sessions found for current filter',
    ignoredListTitle: 'Ignored Applications',
    ignoredHint: 'Excluded from screen time',
    restoreTrack: 'Restore',
    emptyIgnored: 'No ignored applications',
    emptyIgnoredSub: 'Click any app and select "Ignore App" to exclude it from tracking',
    settingsTitle: 'Settings',
    navGeneral: 'General',
    navAbout: 'About Dayflow',
    labelLanguage: 'Language',
    langSystem: 'Follow System',
    langZhCN: '简体中文',
    langEn: 'English',
    langZhTW: '繁體中文',
    labelAppearance: 'Appearance',
    themeSystem: 'Follow System',
    themeDark: 'Dark Mode',
    themeLight: 'Light Mode',
    labelFontSize: 'Font Size',
    fontSmall: 'A-',
    fontStandard: 'Default',
    fontLarge: 'A+',
    labelAutoStart: 'Launch Dayflow at Login',
    descAutoStart: 'Automatically start Dayflow in background when signing in to Windows.',
    labelAlwaysOnTopSetting: 'Always on Top',
    descAlwaysOnTopSetting: 'Keep Dayflow window floating above other desktop windows.',
    labelVersionInfo: 'Version',
    btnCheckUpdate: 'Check Update',
    btnLatestVersion: 'Up to Date',
    labelDataStorage: 'Local Data Storage',
    descDataStorage: 'All records are stored permanently in local SQLite database with 100% privacy.',
    copyrightText: 'Dayflow Screen Time · Crafted for Windows',
  },
}

export function resolveLocaleCode(langPref = appPreferences.language) {
  if (langPref && langPref !== 'system' && MESSAGES[langPref]) {
    return langPref
  }
  if (typeof navigator !== 'undefined') {
    const sys = (navigator.language || '').toLowerCase()
    if (sys.includes('tw') || sys.includes('hk') || sys.includes('hant')) {
      return 'zh-TW'
    }
    if (sys.startsWith('en')) {
      return 'en'
    }
  }
  return 'zh-CN'
}

export const currentLocale = computed(() => resolveLocaleCode(appPreferences.language))

export const i18n = computed(() => MESSAGES[currentLocale.value] || MESSAGES['zh-CN'])

export function resolveEffectiveTheme(themePref = appPreferences.theme) {
  if (themePref === 'light' || themePref === 'dark') {
    return themePref
  }
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  }
  return 'dark'
}

export const effectiveTheme = computed(() => resolveEffectiveTheme(appPreferences.theme))

export function applyPreferencesToDom(prefs = appPreferences) {
  if (prefs && typeof prefs === 'object') {
    if (prefs.language !== undefined) appPreferences.language = prefs.language
    if (prefs.theme !== undefined) appPreferences.theme = prefs.theme
    if (prefs.font_scale !== undefined) appPreferences.font_scale = Number(prefs.font_scale) || 1.0
    if (prefs.auto_start !== undefined) appPreferences.auto_start = Boolean(prefs.auto_start)
    if (prefs.version !== undefined) appPreferences.version = String(prefs.version)
  }

  if (typeof document === 'undefined') return
  const htmlEl = document.documentElement
  const mode = resolveEffectiveTheme(appPreferences.theme)
  htmlEl.classList.toggle('theme-light', mode === 'light')
  htmlEl.classList.toggle('theme-dark', mode === 'dark')
  htmlEl.style.colorScheme = mode

  const scale = Math.max(0.88, Math.min(1.25, Number(appPreferences.font_scale) || 1.0))
  htmlEl.style.zoom = String(scale)
}
