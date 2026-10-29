/**
 * Dayflow 前后端桥接层 (PyWebView JS API + 浏览器高仿真 Windows 桌面软件 Mock 回退)
 */

export const CATEGORY_META = {
  social: { key: 'social', label: '社交通讯', color: '#3B82F6' },
  creative: { key: 'creative', label: '开发与创意', color: '#06B6D4' },
  entertainment: { key: 'entertainment', label: '影音娱乐', color: '#F59E0B' },
  productivity: { key: 'productivity', label: '办公与效率', color: '#10B981' },
  other: { key: 'other', label: '其他工具', color: '#71717A' },
}

export const CATEGORY_ORDER = ['social', 'creative', 'entertainment', 'productivity', 'other']

let pywebviewReady = typeof window !== 'undefined' && Boolean(window.pywebview?.api)

if (typeof window !== 'undefined') {
  window.addEventListener('pywebviewready', () => {
    pywebviewReady = Boolean(window.pywebview?.api)
  })
}

function getPyApi() {
  if (typeof window !== 'undefined' && window.pywebview?.api) {
    pywebviewReady = true
    return window.pywebview.api
  }
  return null
}

/**
 * 异步等待 PyWebView 桥接对象注入完成（解决启动首屏瞬间因 bridge 尚未注入而闪现假数据的问题）
 */
async function ensurePyApi(maxWaitMs = 2000) {
  const immediate = getPyApi()
  if (immediate) return immediate
  if (typeof window === 'undefined') return null

  return new Promise((resolve) => {
    let settled = false
    const start = Date.now()

    const finish = (apiObj) => {
      if (settled) return
      settled = true
      window.removeEventListener('pywebviewready', onReady)
      clearInterval(timer)
      resolve(apiObj)
    }

    const onReady = () => {
      const apiObj = getPyApi()
      if (apiObj) finish(apiObj)
    }

    window.addEventListener('pywebviewready', onReady)

    const timer = setInterval(() => {
      const apiObj = getPyApi()
      if (apiObj) {
        finish(apiObj)
      } else if (Date.now() - start >= maxWaitMs) {
        finish(null)
      }
    }, 15)
  })
}

function isExplicitMockMode() {
  if (typeof window === 'undefined') return false
  return window.location?.search?.includes('mock=1')
}

function buildEmptyDashboard(dateStr = null, period = 'day') {
  const todayStr = getTodayStr()
  const targetDate = dateStr || todayStr
  const hourlyBuckets = Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    total_sec: 0,
    categories: { social: 0, creative: 0, entertainment: 0, productivity: 0, other: 0 },
  }))
  return {
    period,
    date_str: targetDate,
    today_str: todayStr,
    start_date_str: targetDate,
    end_date_str: targetDate,
    prev_date_str: null,
    next_date_str: null,
    can_go_next: false,
    period_label: '今日',
    total_sec: 0,
    yesterday_total_sec: 0,
    prev_period_total_sec: 0,
    daily_avg_sec: 0,
    active_days_count: 0,
    hourly_buckets: hourlyBuckets,
    chart_buckets: hourlyBuckets,
    category_totals: CATEGORY_ORDER.map((k) => ({
      category: k,
      label: CATEGORY_META[k].label,
      total_sec: 0,
    })),
    apps: [],
    recent_dates: [],
    category_meta: CATEGORY_META,
    active_app: null,
    always_on_top: false,
    timeline: [],
  }
}

export function isDesktopBridgeActive() {
  return Boolean(getPyApi())
}

/**
 * 生成带精美渐变色与品牌字符的高清 SVG 图标 Data URL
 */
function makeBrandSvgIcon(glyph, bgStart, bgEnd, textColor = '#FFFFFF') {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
    <defs>
      <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="${bgStart}" />
        <stop offset="100%" stop-color="${bgEnd}" />
      </linearGradient>
    </defs>
    <rect width="64" height="64" rx="16" fill="url(#g)" />
    <rect x="1" y="1" width="62" height="62" rx="15" fill="none" stroke="#FFFFFF" stroke-opacity="0.16" stroke-width="1.5" />
    <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" fill="${textColor}" font-family="Segoe UI, Microsoft YaHei UI, sans-serif" font-size="25" font-weight="700">${glyph}</text>
  </svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

function getTodayStr() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function shiftDateStr(baseDateStr, deltaDays) {
  const [y, m, d] = baseDateStr.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  dt.setDate(dt.getDate() + deltaDays)
  const ny = dt.getFullYear()
  const nm = String(dt.getMonth() + 1).padStart(2, '0')
  const nd = String(dt.getDate()).padStart(2, '0')
  return `${ny}-${nm}-${nd}`
}

const WEEKDAY_NAMES = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

// 内存态 Mock 数据仓库，支持修改分类、屏蔽与恢复实时联动
const mockState = {
  alwaysOnTop: false,
  apps: [
    {
      id: 1,
      exe_path: 'C:\\Program Files\\Tencent\\WeChat\\WeChat.exe',
      exe_name: 'WeChat.exe',
      display_name: '微信',
      category: 'social',
      icon_base64: makeBrandSvgIcon('微', '#10B981', '#059669'),
      is_ignored: false,
      last_window_title: '产品研发交流群 (99+) - 微信',
      sessions: [
        { id: 101, hour_bucket: 0, start_time: '00:05:10', end_time: '00:38:10', duration_sec: 1980, last_window_title: '微信文件传输助手' },
        { id: 102, hour_bucket: 8, start_time: '08:20:00', end_time: '08:52:00', duration_sec: 1920, last_window_title: '晨会同步群 - 微信' },
        { id: 103, hour_bucket: 9, start_time: '09:15:00', end_time: '09:50:00', duration_sec: 2100, last_window_title: '产品研发交流群 - 微信' },
        { id: 104, hour_bucket: 11, start_time: '11:10:00', end_time: '11:45:00', duration_sec: 2100, last_window_title: '设计评审群 - 微信' },
        { id: 105, hour_bucket: 14, start_time: '14:00:00', end_time: '14:35:00', duration_sec: 2100, last_window_title: '客户对接群 - 微信' },
        { id: 106, hour_bucket: 16, start_time: '16:10:00', end_time: '16:50:00', duration_sec: 2400, last_window_title: '架构讨论组 - 微信' },
        { id: 107, hour_bucket: 20, start_time: '20:15:00', end_time: '20:45:00', duration_sec: 1800, last_window_title: '家人群 - 微信' },
      ],
    },
    {
      id: 2,
      exe_path: 'C:\\Users\\Admin\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe',
      exe_name: 'Code.exe',
      display_name: 'Visual Studio Code',
      category: 'creative',
      icon_base64: makeBrandSvgIcon('VS', '#0EA5E9', '#2563EB'),
      is_ignored: false,
      last_window_title: 'ScreenTimeCard.vue - dayflow - Visual Studio Code',
      sessions: [
        { id: 201, hour_bucket: 9, start_time: '09:50:10', end_time: '10:00:00', duration_sec: 590, last_window_title: 'bridge.py - dayflow - Visual Studio Code' },
        { id: 202, hour_bucket: 10, start_time: '10:00:00', end_time: '10:52:00', duration_sec: 3120, last_window_title: 'database.py - dayflow - Visual Studio Code' },
        { id: 203, hour_bucket: 13, start_time: '13:10:00', end_time: '13:58:00', duration_sec: 2880, last_window_title: 'HourlyBarChart.vue - dayflow - Visual Studio Code' },
        { id: 204, hour_bucket: 15, start_time: '15:00:00', end_time: '15:54:00', duration_sec: 3240, last_window_title: 'ScreenTimeCard.vue - dayflow - Visual Studio Code' },
        { id: 205, hour_bucket: 17, start_time: '17:05:00', end_time: '17:50:00', duration_sec: 2700, last_window_title: 'App.vue - dayflow - Visual Studio Code' },
        { id: 206, hour_bucket: 21, start_time: '21:10:00', end_time: '21:48:00', duration_sec: 2280, last_window_title: 'main.py - dayflow - Visual Studio Code' },
      ],
    },
    {
      id: 3,
      exe_path: 'C:\\Program Files\\ByteDance\\Douyin\\Douyin.exe',
      exe_name: 'Douyin.exe',
      display_name: '抖音',
      category: 'entertainment',
      icon_base64: makeBrandSvgIcon('抖', '#18181B', '#EC4899'),
      is_ignored: false,
      last_window_title: '抖音 - 记录美好生活',
      sessions: [
        { id: 301, hour_bucket: 1, start_time: '01:02:00', end_time: '01:48:00', duration_sec: 2760, last_window_title: '抖音精选视频' },
        { id: 302, hour_bucket: 7, start_time: '07:25:00', end_time: '07:55:00', duration_sec: 1800, last_window_title: '早间新闻直播 - 抖音' },
        { id: 303, hour_bucket: 12, start_time: '12:15:00', end_time: '12:55:00', duration_sec: 2400, last_window_title: '美食探店合集 - 抖音' },
        { id: 304, hour_bucket: 19, start_time: '19:10:00', end_time: '19:52:00', duration_sec: 2520, last_window_title: '数码科技评测 - 抖音' },
        { id: 305, hour_bucket: 22, start_time: '22:05:00', end_time: '22:50:00', duration_sec: 2700, last_window_title: '抖音 - 记录美好生活' },
      ],
    },
    {
      id: 4,
      exe_path: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      exe_name: 'chrome.exe',
      display_name: 'Google Chrome',
      category: 'productivity',
      icon_base64: makeBrandSvgIcon('Ch', '#2563EB', '#10B981'),
      is_ignored: false,
      last_window_title: 'Vue 3 + Tailwind CSS 桌面端性能优化指南 - Google Chrome',
      sessions: [
        { id: 401, hour_bucket: 8, start_time: '08:52:00', end_time: '09:00:00', duration_sec: 480, last_window_title: 'GitHub Pull Requests - Google Chrome' },
        { id: 402, hour_bucket: 11, start_time: '11:45:00', end_time: '12:00:00', duration_sec: 900, last_window_title: 'PyWebView Documentation - Google Chrome' },
        { id: 403, hour_bucket: 14, start_time: '14:35:00', end_time: '15:00:00', duration_sec: 1500, last_window_title: 'Figma 设计稿评审 - Google Chrome' },
        { id: 404, hour_bucket: 16, start_time: '16:50:00', end_time: '17:00:00', duration_sec: 600, last_window_title: 'Tailwind CSS 调色板 - Google Chrome' },
        { id: 405, hour_bucket: 18, start_time: '18:10:00', end_time: '18:52:00', duration_sec: 2520, last_window_title: '技术周刊与架构文档 - Google Chrome' },
      ],
    },
    {
      id: 5,
      exe_path: 'C:\\Program Files\\Hongguo\\Hongguo.exe',
      exe_name: 'Hongguo.exe',
      display_name: '红果短剧',
      category: 'entertainment',
      icon_base64: makeBrandSvgIcon('红', '#EF4444', '#F97316'),
      is_ignored: false,
      last_window_title: '红果免费短剧 - 剧场热播中',
      sessions: [
        { id: 501, hour_bucket: 2, start_time: '02:00:00', end_time: '02:50:00', duration_sec: 3000, last_window_title: '热播短剧第 12 集 - 红果短剧' },
        { id: 502, hour_bucket: 3, start_time: '03:00:00', end_time: '03:45:00', duration_sec: 2700, last_window_title: '热播短剧大结局 - 红果短剧' },
        { id: 503, hour_bucket: 23, start_time: '23:05:00', end_time: '23:49:00', duration_sec: 2640, last_window_title: '红果免费短剧 - 剧场热播中' },
      ],
    },
    {
      id: 6,
      exe_path: 'C:\\Program Files\\JetBrains\\IntelliJ IDEA\\bin\\idea64.exe',
      exe_name: 'idea64.exe',
      display_name: 'IntelliJ IDEA',
      category: 'creative',
      icon_base64: makeBrandSvgIcon('IJ', '#6366F1', '#EC4899'),
      is_ignored: false,
      last_window_title: 'dayflow-core – UsageDatabase.kt',
      sessions: [
        { id: 601, hour_bucket: 4, start_time: '04:05:00', end_time: '04:42:00', duration_sec: 2220, last_window_title: 'dayflow-service – TaskScheduler.kt' },
        { id: 602, hour_bucket: 5, start_time: '05:10:00', end_time: '05:45:00', duration_sec: 2100, last_window_title: 'dayflow-core – UsageDatabase.kt' },
      ],
    },
    {
      id: 7,
      exe_path: 'C:\\Program Files\\Feishu\\Feishu.exe',
      exe_name: 'Feishu.exe',
      display_name: '飞书',
      category: 'social',
      icon_base64: makeBrandSvgIcon('飞', '#3B82F6', '#06B6D4'),
      is_ignored: false,
      last_window_title: '飞书云文档 - 2026 桌面端产品规划',
      sessions: [
        { id: 701, hour_bucket: 6, start_time: '06:15:00', end_time: '06:50:00', duration_sec: 2100, last_window_title: '飞书日历与待办事项' },
        { id: 702, hour_bucket: 20, start_time: '20:45:00', end_time: '21:00:00', duration_sec: 900, last_window_title: '飞书云文档 - 2026 桌面端产品规划' },
      ],
    },
    {
      id: 8,
      exe_path: 'C:\\Program Files\\Bilibili\\哔哩哔哩.exe',
      exe_name: '哔哩哔哩.exe',
      display_name: '哔哩哔哩',
      category: 'entertainment',
      icon_base64: makeBrandSvgIcon('B', '#FB7185', '#EC4899'),
      is_ignored: false,
      last_window_title: '2026 桌面级硬件装机与效率工具横评 - 哔哩哔哩',
      sessions: [
        { id: 801, hour_bucket: 12, start_time: '12:00:00', end_time: '12:15:00', duration_sec: 900, last_window_title: '午休番剧连载 - 哔哩哔哩' },
        { id: 802, hour_bucket: 19, start_time: '19:52:00', end_time: '20:00:00', duration_sec: 480, last_window_title: '2026 桌面级硬件装机与效率工具横评 - 哔哩哔哩' },
      ],
    },
    {
      id: 9,
      exe_path: 'C:\\Program Files\\Kingsoft\\WPS Office\\wps.exe',
      exe_name: 'wps.exe',
      display_name: 'WPS Office',
      category: 'productivity',
      icon_base64: makeBrandSvgIcon('W', '#F97316', '#EF4444'),
      is_ignored: false,
      last_window_title: '季度研发效能统计报表.xlsx - WPS 表格',
      sessions: [
        { id: 901, hour_bucket: 10, start_time: '10:52:00', end_time: '11:00:00', duration_sec: 480, last_window_title: '产品迭代周报.docx - WPS 文字' },
        { id: 902, hour_bucket: 17, start_time: '17:50:00', end_time: '18:00:00', duration_sec: 600, last_window_title: '季度研发效能统计报表.xlsx - WPS 表格' },
      ],
    },
    {
      id: 10,
      exe_path: 'C:\\Windows\\System32\\Taskmgr.exe',
      exe_name: 'Taskmgr.exe',
      display_name: '任务管理器',
      category: 'other',
      icon_base64: makeBrandSvgIcon('任', '#52525B', '#3F3F46'),
      is_ignored: true,
      last_window_title: '任务管理器',
      sessions: [
        { id: 1001, hour_bucket: 15, start_time: '15:54:00', end_time: '15:58:00', duration_sec: 240, last_window_title: '任务管理器' },
      ],
    },
  ],
}

function buildMockDashboard(dateStr) {
  const todayStr = getTodayStr()
  const targetDate = dateStr || todayStr

  // 根据日期偏移生成稳定的比例系数，方便演示切换近 7 天日期
  const daySeed = targetDate.split('-').reduce((acc, v) => acc + Number(v || 0), 0)
  const scale = targetDate === todayStr ? 1.0 : 0.68 + ((daySeed % 5) * 0.08)

  const hourlyBuckets = Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    total_sec: 0,
    categories: {
      social: 0,
      creative: 0,
      entertainment: 0,
      productivity: 0,
      other: 0,
    },
  }))

  const catTotalsMap = {
    social: 0,
    creative: 0,
    entertainment: 0,
    productivity: 0,
    other: 0,
  }

  const appsList = []
  const timeline = []
  let totalSec = 0

  for (const app of mockState.apps) {
    if (app.is_ignored) continue
    let appTotalSec = 0
    for (const s of app.sessions) {
      const dur = Math.max(60, Math.min(3600, Math.round(s.duration_sec * scale)))
      const h = s.hour_bucket
      const cat = CATEGORY_META[app.category] ? app.category : 'other'

      hourlyBuckets[h].categories[cat] += dur
      hourlyBuckets[h].total_sec = Math.min(3600, hourlyBuckets[h].total_sec + dur)
      catTotalsMap[cat] += dur
      appTotalSec += dur
      totalSec += dur

      timeline.push({
        id: s.id,
        app_id: app.id,
        date_str: targetDate,
        hour_bucket: h,
        start_time: s.start_time,
        end_time: s.end_time,
        duration_sec: dur,
        last_window_title: s.last_window_title,
        exe_path: app.exe_path,
        exe_name: app.exe_name,
        display_name: app.display_name,
        category: cat,
        icon_base64: app.icon_base64,
      })
    }

    if (appTotalSec > 0) {
      appsList.push({
        id: app.id,
        exe_path: app.exe_path,
        exe_name: app.exe_name,
        display_name: app.display_name,
        category: app.category,
        icon_base64: app.icon_base64,
        total_sec: appTotalSec,
        session_count: app.sessions.length,
        last_window_title: app.last_window_title,
      })
    }
  }

  appsList.sort((a, b) => b.total_sec - a.total_sec)
  timeline.sort((a, b) => a.hour_bucket - b.hour_bucket || a.start_time.localeCompare(b.start_time))

  const categoryTotals = CATEGORY_ORDER.map((cat) => ({
    category: cat,
    label: CATEGORY_META[cat].label,
    total_sec: catTotalsMap[cat] || 0,
  }))

  const recentDates = []
  for (let i = 6; i >= 0; i--) {
    const dStr = shiftDateStr(todayStr, -i)
    const [y, m, d] = dStr.split('-').map(Number)
    const dt = new Date(y, m - 1, d)
    const label = i === 0 ? '今日' : i === 1 ? '昨日' : `${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    recentDates.push({
      date_str: dStr,
      label,
      weekday: WEEKDAY_NAMES[dt.getDay()],
      total_sec: dStr === targetDate ? totalSec : Math.round(totalSec * (0.72 + ((i * 3) % 5) * 0.07)),
    })
  }

  const activeCandidate = appsList.find((a) => a.exe_name === 'Code.exe') || appsList[0] || null
  const prevDateStr = shiftDateStr(targetDate, -1)
  const nextDateStr = targetDate < todayStr ? shiftDateStr(targetDate, 1) : null

  return {
    period: 'day',
    today_str: todayStr,
    date_str: targetDate,
    start_date_str: targetDate,
    end_date_str: targetDate,
    prev_date_str: prevDateStr,
    next_date_str: nextDateStr,
    can_go_next: nextDateStr !== null,
    period_label: targetDate === todayStr ? '今日' : targetDate,
    total_sec: totalSec,
    avg_daily_sec: totalSec,
    yesterday_total_sec: Math.round(totalSec * 0.86),
    hourly_buckets: hourlyBuckets,
    chart_buckets: hourlyBuckets.map((b) => ({
      index: b.hour,
      hour: b.hour,
      label: `${b.hour}时`,
      short_label: [0, 6, 12, 18].includes(b.hour) ? `${b.hour}时` : '',
      total_sec: b.total_sec,
      max_sec: 3600,
      categories: b.categories,
    })),
    category_totals: categoryTotals,
    apps: appsList,
    recent_dates: recentDates,
    category_meta: CATEGORY_META,
    active_app: activeCandidate
      ? {
          app_id: activeCandidate.id,
          exe_path: activeCandidate.exe_path,
          exe_name: activeCandidate.exe_name,
          display_name: activeCandidate.display_name,
          category: activeCandidate.category,
          icon_base64: activeCandidate.icon_base64,
          window_title: activeCandidate.last_window_title,
          started_at: '14:20:00',
          active_sec: 420,
        }
      : null,
    always_on_top: mockState.alwaysOnTop,
    timeline,
  }
}

/**
 * 获取看板聚合数据（支持按日 day / 按周 week / 按月 month）
 * @param {string|null} dateStr YYYY-MM-DD
 * @param {'day'|'week'|'month'} period
 */
export async function fetchDashboardData(dateStr = null, period = 'day') {
  const api = await ensurePyApi(2000)
  if (api && typeof api.get_dashboard_data === 'function') {
    return await api.get_dashboard_data(dateStr, period)
  }
  if (isExplicitMockMode()) {
    return buildMockDashboard(dateStr, period)
  }
  return buildEmptyDashboard(dateStr, period)
}

/**
 * 获取单个软件在指定日期的 24 小时分布与时间段会话列表
 * @param {number} appId
 * @param {string|null} dateStr
 */
export async function fetchAppDetail(appId, dateStr = null) {
  const api = await ensurePyApi(1500)
  if (api && typeof api.get_app_detail === 'function') {
    return await api.get_app_detail(Number(appId), dateStr)
  }

  const targetDate = dateStr || getTodayStr()
  const app = mockState.apps.find((a) => a.id === Number(appId))
  if (!app) {
    const emptyInfo = {
      id: Number(appId),
      exe_path: '',
      exe_name: '',
      display_name: '未知应用',
      category: 'other',
      icon_base64: makeBrandSvgIcon('?', '#52525B', '#3F3F46'),
      is_ignored: false,
    }
    return {
      ...emptyInfo,
      app: emptyInfo,
      date_str: targetDate,
      total_sec: 0,
      hourly_sec: Array(24).fill(0),
      sessions: [],
    }
  }

  const hourlySec = Array(24).fill(0)
  let totalSec = 0
  const sessions = app.sessions.map((s) => {
    hourlySec[s.hour_bucket] = Math.min(3600, hourlySec[s.hour_bucket] + s.duration_sec)
    totalSec += s.duration_sec
    return { ...s }
  })

  const appInfo = {
    id: app.id,
    exe_path: app.exe_path,
    exe_name: app.exe_name,
    display_name: app.display_name,
    category: app.category,
    icon_base64: app.icon_base64,
    is_ignored: app.is_ignored,
  }

  return {
    ...appInfo,
    app: appInfo,
    date_str: targetDate,
    total_sec: totalSec,
    hourly_sec: hourlySec,
    sessions,
  }
}

/**
 * 更新软件分类、显示名称或屏蔽状态
 * @param {number} appId
 * @param {{ category?: string, display_name?: string, is_ignored?: boolean }} payload
 */
export async function updateAppSettings(appId, payload = {}) {
  const api = getPyApi()
  if (api && typeof api.update_app === 'function') {
    return await api.update_app(Number(appId), payload)
  }

  const app = mockState.apps.find((a) => a.id === Number(appId))
  if (app) {
    if (payload.category !== undefined) app.category = payload.category
    if (payload.display_name !== undefined) app.display_name = payload.display_name
    if (payload.is_ignored !== undefined) app.is_ignored = Boolean(payload.is_ignored)
    return {
      id: app.id,
      exe_path: app.exe_path,
      exe_name: app.exe_name,
      display_name: app.display_name,
      category: app.category,
      icon_base64: app.icon_base64,
      is_ignored: app.is_ignored,
    }
  }
  return { id: Number(appId), ...payload }
}

/**
 * 获取已屏蔽的软件列表
 */
export async function fetchIgnoredApps() {
  const api = await ensurePyApi(1500)
  if (api && typeof api.get_ignored_apps === 'function') {
    return await api.get_ignored_apps()
  }
  if (!isExplicitMockMode()) {
    return []
  }
  return mockState.apps
    .filter((a) => a.is_ignored)
    .map((a) => ({
      id: a.id,
      exe_path: a.exe_path,
      exe_name: a.exe_name,
      display_name: a.display_name,
      category: a.category,
      icon_base64: a.icon_base64,
      is_ignored: true,
    }))
}

/**
 * 切换窗口置顶状态
 * @param {boolean|null} state
 */
export async function toggleAlwaysOnTop(state = null) {
  const api = getPyApi()
  if (api && typeof api.toggle_always_on_top === 'function') {
    return await api.toggle_always_on_top(state)
  }
  mockState.alwaysOnTop = state === null ? !mockState.alwaysOnTop : Boolean(state)
  return { ok: true, always_on_top: mockState.alwaysOnTop }
}

/**
 * 最小化窗口
 */
export async function minimizeWindow() {
  const api = getPyApi()
  if (api && typeof api.minimize_window === 'function') {
    return await api.minimize_window()
  }
  return { ok: true }
}

/**
 * 隐藏窗口至系统托盘
 */
export async function hideToTray() {
  const api = getPyApi()
  if (api && typeof api.hide_to_tray === 'function') {
    return await api.hide_to_tray()
  }
  return { ok: true, hidden: true }
}

/**
 * 保存当前计时数据并直接退出结束整个程序
 */
export async function quitApp() {
  const api = getPyApi()
  if (api && typeof api.quit_app === 'function') {
    return await api.quit_app()
  }
  if (typeof window !== 'undefined' && typeof window.close === 'function') {
    window.close()
  }
  return { ok: true, quitting: true }
}

const mockPreferences = {
  language: 'system',
  theme: 'dark',
  font_scale: 1.0,
  auto_start: false,
  version: '1.0.0',
}

/**
 * 获取通用偏好设置与版本信息
 */
export async function fetchPreferences() {
  const api = await ensurePyApi(1500)
  if (api && typeof api.get_preferences === 'function') {
    return await api.get_preferences()
  }
  return { ...mockPreferences }
}

/**
 * 更新通用偏好设置（语言、外观、字体大小、开机自启）
 * @param {Object} updates
 */
export async function savePreferences(updates = {}) {
  const api = getPyApi()
  if (api && typeof api.update_preferences === 'function') {
    return await api.update_preferences(updates)
  }
  Object.assign(mockPreferences, updates)
  return { ...mockPreferences }
}

/**
 * 启动无边框窗口四周/四角拖拽调整大小
 * @param {'n'|'s'|'e'|'w'|'nw'|'ne'|'sw'|'se'} edge
 */
export async function startWindowResize(edge = 'se') {
  const api = getPyApi()
  if (api && typeof api.start_window_resize === 'function') {
    return await api.start_window_resize(edge)
  }
  return { ok: true, edge }
}

/**
 * 将秒数格式化为中文人类可读时长（如 "12小时 28分钟"、"45分钟"、"32秒"）
 */
export function formatDuration(seconds, { showSecondsWhenUnderMinute = true } = {}) {
  const sec = Math.max(0, Math.floor(Number(seconds) || 0))
  if (sec === 0) return '0分钟'
  const hours = Math.floor(sec / 3600)
  const minutes = Math.floor((sec % 3600) / 60)
  if (hours > 0 && minutes > 0) {
    return `${hours}小时 ${minutes}分钟`
  }
  if (hours > 0) {
    return `${hours}小时`
  }
  if (minutes > 0) {
    return `${minutes}分钟`
  }
  return showSecondsWhenUnderMinute ? `${sec}秒` : '不足1分钟'
}
