import { computed, reactive } from 'vue'

export const appPreferences = reactive({
  language: 'system', // 'system' | 'zh-CN' | 'en' | 'zh-TW'
  theme: 'dark',      // 'system' | 'dark' | 'light'
  font_scale: 1.0,    // 0.92 (小) | 1.00 (标准) | 1.05 | 1.10 | 1.15 | 1.20 (大)
  auto_start: false,
  health_remind_enabled: true,
  rest_remind_interval_sec: 1800, // 默认 30 分钟 (1800秒)
  health_remind_sound: true,
  health_remind_dnd_game: true,
  idle_detection_enabled: true,
  idle_threshold_sec: 180,
  global_hotkey_enabled: true,
  global_hotkey: 'Ctrl+Shift+D',
  version: '1.0.1',
})

// 6 档字体大小刻度（对应微信设置图1：第1格“小”，第2格“标准”，第6格“大”）
export const FONT_SCALE_STEPS = [0.92, 1.0, 1.05, 1.1, 1.15, 1.2]

// 常见中文软件名在英文/繁体模式下的本地化映射
const APP_NAME_EN_MAP = {
  文件资源管理器: 'File Explorer',
  任务管理器: 'Task Manager',
  微信: 'WeChat',
  企业微信: 'WeCom',
  钉钉: 'DingTalk',
  飞书: 'Feishu / Lark',
  抖音: 'Douyin',
  哔哩哔哩: 'Bilibili',
  网易云音乐: 'NetEase Music',
  QQ音乐: 'QQ Music',
  酷狗音乐: 'Kugou Music',
  百度网盘: 'Baidu Netdisk',
  阿里云盘: 'Alipan',
  迅雷: 'Thunder',
  剪映专业版: 'CapCut Pro',
  有道词典: 'Youdao Dict',
  有道云笔记: 'Youdao Note',
  印象笔记: 'Evernote',
  小智桌面: 'Xiaozhi Desktop',
  'Windows 终端': 'Windows Terminal',
  命令提示符: 'Command Prompt',
  画图: 'Paint',
  记事本: 'Notepad',
  计算器: 'Calculator',
  截图工具: 'Snipping Tool',
  设置: 'Windows Settings',
  未知应用: 'Unknown App',
}

const APP_NAME_TW_MAP = {
  文件资源管理器: '檔案總管',
  任务管理器: '工作管理員',
  企业微信: '企業微信',
  钉钉: '釘釘',
  飞书: '飛書',
  哔哩哔哩: '嗶哩嗶哩',
  网易云音乐: '網易雲音樂',
  QQ音乐: 'QQ音樂',
  酷狗音乐: '酷狗音樂',
  百度网盘: '百度網盤',
  阿里云盘: '阿里雲盤',
  迅雷: '迅雷',
  剪映专业版: '剪映專業版',
  有道词典: '有道詞典',
  有道云笔记: '有道雲筆記',
  印象笔记: 'Evernote',
  'Windows 终端': 'Windows 終端機',
  命令提示符: '命令提示字元',
  画图: '小畫家',
  记事本: '記事本',
  计算器: '小算盤',
  截图工具: '剪取工具',
  设置: '設定',
  未知应用: '未知應用',
}

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
    prevDayTitle: '前一天',
    nextDayTitle: '后一天',
    prevWeekTitle: '上一周',
    nextWeekTitle: '下一周',
    prevMonthTitle: '上一月',
    nextMonthTitle: '下一月',
    todayTag: '今日',
    yesterdayTag: '昨日',
    thisWeekTag: '本周',
    thisMonthTag: '本月',
    weekdays: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
    statusCollecting: '实时采集中',
    statusReady: '后台就绪',
    statusAllDayCollecting: '全天实时采集中',
    activeDaysPrefix: '活跃',
    activeDaysSuffix: '天',
    compareYesterday: '昨日',
    compareLastWeek: '上周',
    compareLastMonth: '上月',
    compareSameAs: '与{noun}基本持平',
    compareMoreThan: '较{noun}多 {dur}',
    compareLessThan: '较{noun}少 {dur}',
    hourFilterBadge: '{hour}:00 时段 · 点击还原',
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
    catCreative: '开发与创意',
    catEntertainment: '影音娱乐',
    catProductivity: '办公与效率',
    catOther: '其他工具',
    // 图表
    yAxis1Hour: '1小时',
    yAxis30Min: '30分钟',
    yAxisHours: '{h}小时',
    xAxisHour: '{h}时',
    xAxisDay: '{d}日',
    emptySlotRecord: '该时段暂无软件使用记录',
    clickToViewDate: '点击查看 {date} 当日明细',
    // 软件使用明细网格 (AppUsageGrid)
    appGridTitle: '软件使用明细',
    appGridHourTitle: '{hour}:00 时段使用明细',
    appCountSuffix: '款',
    btnAllDay: '全天',
    viewGrid: '双列',
    viewGridTip: '双列磁贴视图',
    viewList: '排行',
    viewListTip: '单列进度条排行视图',
    activeInForeground: '当前正在前台使用',
    emptyHourApps: '该时段暂无符合筛选条件的软件记录',
    emptyApps: '暂无符合条件的软件使用记录',
    resetFilter: '重置筛选条件',
    // 排行与流水
    rankingTitleSuffix: '软件时长排行',
    totalPrefix: '总计',
    timelineTitle: '时段使用流水',
    recordsSuffix: '条记录',
    sortNewest: '最新时段在前',
    sortChrono: '00:00 顺序排列',
    emptyTimeline: '当前筛选条件下暂无时段使用流水',
    ganttTitle: '24 小时全景时光彩带 (甘特全貌)',
    ganttSliceCount: '共 {count} 个时间切片',
    ganttEmpty: '该时段暂无活跃流水记录',
    exportReportBtn: '导出明细报表 (CSV)',
    exportReportSuccess: '报表导出成功',
    labelGlobalHotkey: '全局快捷键唤出 / 隐藏',
    descGlobalHotkey: '按下快捷键可在任意软件界面快速唤出或收起 Dayflow 窗口。',
    hotkeyPresetTip: '推荐预设：',
    btnApplyHotkey: '保存快捷键',
    hotkeySavedSuccess: '已保存并生效',
    labelDataExport: '数据报表一键导出',
    descDataExport: '支持导出含有一级、二级分类与起止时间的标准化 CSV 表格，方便 Excel 与归档。',
    exportingReport: '正在生成报表...',
    exportSuccess: '报表已保存到本地',
    exportFailed: '导出失败，请重试',
    // 已屏蔽
    ignoredListTitle: '已屏蔽的软件名单',
    ignoredHint: '不计入屏幕使用时长',
    restoreTrack: '恢复统计',
    emptyIgnored: '当前没有被屏蔽的软件',
    emptyIgnoredSub: '可在任意软件的详情面板中点击“屏蔽此软件”将其排除统计',
    // 软件详情抽屉 (AppDetailModal)
    runningForeground: '前台运行中',
    todayTotalPrefix: '今日累计',
    sessionsCountText: '共 {n} 个时间段',
    closeDetail: '关闭详情',
    dist24hTitle: '24小时使用分布',
    hoverToViewHour: '悬停查看各小时时长',
    appCategoryTitle: '软件分类归属',
    btnIgnoreApp: '屏蔽此软件',
    btnRestoreApp: '恢复计入统计',
    sessionListTitle: '使用时间段流水明细',
    orderByTime: '按时间排列',
    emptyAppSessions: '当日暂无该软件的分段会话流水记录',
    resizeTip: '按住拖动可调整窗口大小',
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
    labelHealthGuard: '专注久坐健康关怀',
    descHealthGuard: '连续专注操作电脑达设定时间时，自动触发关怀横幅与 Windows 系统通知。',
    labelRemindInterval: '提醒间隔时长',
    labelDndGame: '游戏与全屏免打扰',
    descDndGame: '运行全屏游戏或演示时不弹窗打扰，切回桌面后再提醒。',
    labelRemindSound: '系统通知柔和提示音',
    descRemindSound: '发送 Windows 原生通知时伴随轻柔微光水滴音。',
    min20: '20分钟',
    min30Default: '30分钟 (默认)',
    min45: '45分钟',
    min60: '60分钟',
    min90: '90分钟',
    labelVersionInfo: '版本信息',
    btnCheckUpdate: '检查更新',
    btnLatestVersion: '已是最新版本',
    labelDataStorage: '本地数据存储',
    descDataStorage: '所有使用记录均保存在本地 SQLite 数据库，永久留存且绝不上传云端。',
    copyrightText: 'Dayflow 桌面时长管家 · 专为 Windows 打造',
    confirmQuitTitle: '确认退出 Dayflow？',
    confirmQuitDesc: '退出后将暂停记录桌面应用使用时长。',
    btnCancel: '取消',
    btnConfirmQuit: '确认退出',
    pressShortcut: '按下快捷键',
    resetDefaultShortcut: '恢复默认设置',
    customIntervalTip: '自定义时长 (5~240分钟)：',
    exportModalTitle: '导出明细数据报表 (CSV)',
    exportSelectPeriod: '选择导出统计周期：',
    exportSelectedDate: '当前统计日期：',
    btnConfirmExport: '立即导出 CSV 报表',
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
    prevDayTitle: '前一天',
    nextDayTitle: '後一天',
    prevWeekTitle: '上一週',
    nextWeekTitle: '下一週',
    prevMonthTitle: '上一月',
    nextMonthTitle: '下一月',
    todayTag: '今日',
    yesterdayTag: '昨日',
    thisWeekTag: '本週',
    thisMonthTag: '本月',
    weekdays: ['週一', '週二', '週三', '週四', '週五', '週六', '週日'],
    statusCollecting: '即時採集中',
    statusReady: '背景就緒',
    statusAllDayCollecting: '全天即時採集中',
    activeDaysPrefix: '活躍',
    activeDaysSuffix: '天',
    compareYesterday: '昨日',
    compareLastWeek: '上週',
    compareLastMonth: '上月',
    compareSameAs: '與{noun}基本持平',
    compareMoreThan: '較{noun}多 {dur}',
    compareLessThan: '較{noun}少 {dur}',
    hourFilterBadge: '{hour}:00 時段 · 點擊還原',
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
    catCreative: '開發與創意',
    catEntertainment: '影音娛樂',
    catProductivity: '辦公與效率',
    catOther: '其他工具',
    yAxis1Hour: '1小時',
    yAxis30Min: '30分鐘',
    yAxisHours: '{h}小時',
    xAxisHour: '{h}時',
    xAxisDay: '{d}日',
    emptySlotRecord: '該時段暫無軟體使用記錄',
    clickToViewDate: '點擊查看 {date} 當日明細',
    appGridTitle: '軟體使用明細',
    appGridHourTitle: '{hour}:00 時段使用明細',
    appCountSuffix: '款',
    btnAllDay: '全天',
    viewGrid: '雙列',
    viewGridTip: '雙列磁貼視圖',
    viewList: '排行',
    viewListTip: '單列進度條排行視圖',
    activeInForeground: '目前正在前景使用',
    emptyHourApps: '該時段暫無符合篩選條件的軟體記錄',
    emptyApps: '暫無符合條件的軟體使用記錄',
    resetFilter: '重設篩選條件',
    rankingTitleSuffix: '軟體時長排行',
    totalPrefix: '總計',
    timelineTitle: '時段使用流水',
    recordsSuffix: '筆記錄',
    sortNewest: '最新時段在前',
    sortChrono: '00:00 順序排列',
    emptyTimeline: '目前篩選條件下暫無時段使用流水',
    ganttTitle: '24 小時全景時光彩帶 (甘特全貌)',
    ganttSliceCount: '共 {count} 個時間切片',
    ganttEmpty: '該時段暫無活躍流水記錄',
    exportReportBtn: '匯出明細報表 (CSV)',
    exportReportSuccess: '報表匯出成功',
    labelGlobalHotkey: '全域快捷鍵喚出 / 隱藏',
    descGlobalHotkey: '按下快捷鍵可在任意軟體介面快速喚出或收起 Dayflow 視窗。',
    hotkeyPresetTip: '推薦預設：',
    btnApplyHotkey: '儲存快捷鍵',
    hotkeySavedSuccess: '已儲存並生效',
    labelDataExport: '數據報表一鍵匯出',
    descDataExport: '支援匯出含有一級、二級分類與起訖時間的標準化 CSV 報表，方便 Excel 與存檔。',
    exportingReport: '正在生成報表...',
    exportSuccess: '報表已儲存至本地',
    exportFailed: '匯出失敗，請重試',
    ignoredListTitle: '已封鎖的軟體名單',
    ignoredHint: '不計入螢幕使用時長',
    restoreTrack: '恢復統計',
    emptyIgnored: '目前沒有被封鎖的軟體',
    emptyIgnoredSub: '可在任意軟體的詳情面板中點擊「封鎖此軟體」將其排除統計',
    runningForeground: '前景執行中',
    todayTotalPrefix: '今日累計',
    sessionsCountText: '共 {n} 個時間段',
    closeDetail: '關閉詳情',
    dist24hTitle: '24小時使用分佈',
    hoverToViewHour: '懸停查看各小時時長',
    appCategoryTitle: '軟體分類歸屬',
    btnIgnoreApp: '封鎖此軟體',
    btnRestoreApp: '恢復計入統計',
    sessionListTitle: '使用時間段流水明細',
    orderByTime: '按時間排列',
    emptyAppSessions: '當日暫無該軟體的分段會話流水記錄',
    resizeTip: '按住拖曳可調整視窗大小',
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
    labelHealthGuard: '專注久坐健康關懷',
    descHealthGuard: '連續專注操作電腦達設定時間時，自動觸發關懷橫幅與 Windows 系統通知。',
    labelRemindInterval: '提醒間隔時長',
    labelDndGame: '遊戲與全螢幕免打擾',
    descDndGame: '運行全螢幕遊戲或演示時不彈窗打擾，切回桌面後再提醒。',
    labelRemindSound: '系統通知柔和提示音',
    descRemindSound: '發送 Windows 原生通知時伴隨輕柔微光水滴音。',
    min20: '20分鐘',
    min30Default: '30分鐘 (預設)',
    min45: '45分鐘',
    min60: '60分鐘',
    min90: '90分鐘',
    labelVersionInfo: '版本資訊',
    btnCheckUpdate: '檢查更新',
    btnLatestVersion: '已是最新版本',
    labelDataStorage: '本機資料儲存',
    descDataStorage: '所有使用記錄均保存在本機 SQLite 資料庫，永久留存且絕不連網上傳。',
    copyrightText: 'Dayflow 桌面時長管家 · 專為 Windows 打造',
    confirmQuitTitle: '確認退出 Dayflow？',
    confirmQuitDesc: '退出後將暫停記錄桌面應用使用時長。',
    btnCancel: '取消',
    btnConfirmQuit: '確認退出',
    pressShortcut: '按下快捷鍵',
    resetDefaultShortcut: '恢復預設設定',
    customIntervalTip: '自訂時長 (5~240分鐘)：',
    exportModalTitle: '匯出明細數據報表 (CSV)',
    exportSelectPeriod: '選擇匯出統計週期：',
    exportSelectedDate: '目前統計日期：',
    btnConfirmExport: '立即匯出 CSV 報表',
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
    prevDayTitle: 'Previous Day',
    nextDayTitle: 'Next Day',
    prevWeekTitle: 'Previous Week',
    nextWeekTitle: 'Next Week',
    prevMonthTitle: 'Previous Month',
    nextMonthTitle: 'Next Month',
    todayTag: 'Today',
    yesterdayTag: 'Yesterday',
    thisWeekTag: 'This Week',
    thisMonthTag: 'This Month',
    weekdays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    statusCollecting: 'Tracking Live',
    statusReady: 'Standing By',
    statusAllDayCollecting: 'Live tracking all day',
    activeDaysPrefix: 'Active',
    activeDaysSuffix: 'days',
    compareYesterday: 'yesterday',
    compareLastWeek: 'last week',
    compareLastMonth: 'last month',
    compareSameAs: 'About the same as {noun}',
    compareMoreThan: '{dur} more than {noun}',
    compareLessThan: '{dur} less than {noun}',
    hourFilterBadge: '{hour}:00 Slot · Reset',
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
    yAxis1Hour: '1h',
    yAxis30Min: '30m',
    yAxisHours: '{h}h',
    xAxisHour: '{h}:00',
    xAxisDay: '{d}',
    emptySlotRecord: 'No usage recorded in this slot',
    clickToViewDate: 'Click to view details for {date}',
    appGridTitle: 'App Usage Details',
    appGridHourTitle: 'Usage at {hour}:00',
    appCountSuffix: 'apps',
    btnAllDay: 'All Day',
    viewGrid: 'Grid',
    viewGridTip: '2-Column Grid View',
    viewList: 'List',
    viewListTip: 'Ranked Progress View',
    activeInForeground: 'Currently active in foreground',
    emptyHourApps: 'No apps recorded in this hour slot',
    emptyApps: 'No app usage records match current filter',
    resetFilter: 'Reset Filter',
    rankingTitleSuffix: 'App Usage Ranking',
    totalPrefix: 'Total',
    timelineTitle: 'Usage Timeline',
    recordsSuffix: 'sessions',
    sortNewest: 'Newest First',
    sortChrono: '00:00 Order',
    emptyTimeline: 'No usage sessions found for current filter',
    ganttTitle: '24-Hour Panoramic Gantt Ribbon',
    ganttSliceCount: '{count} time slices',
    ganttEmpty: 'No active usage records in this period',
    exportReportBtn: 'Export Report (CSV)',
    exportReportSuccess: 'Report exported successfully',
    labelGlobalHotkey: 'Global Shortcut Toggle',
    descGlobalHotkey: 'Press shortcut anywhere to quickly summon or hide Dayflow window.',
    hotkeyPresetTip: 'Presets:',
    btnApplyHotkey: 'Save Shortcut',
    hotkeySavedSuccess: 'Saved & Active',
    labelDataExport: 'Export Usage Report',
    descDataExport: 'Export clean CSV reports with Primary & Secondary categories, durations and timestamps for Excel.',
    exportingReport: 'Generating report...',
    exportSuccess: 'Report saved to desktop',
    exportFailed: 'Export failed, please retry',
    ignoredListTitle: 'Ignored Applications',
    ignoredHint: 'Excluded from screen time',
    restoreTrack: 'Restore',
    emptyIgnored: 'No ignored applications',
    emptyIgnoredSub: 'Click any app and select "Ignore App" to exclude it from tracking',
    runningForeground: 'Active Now',
    todayTotalPrefix: 'Total',
    sessionsCountText: '{n} sessions',
    closeDetail: 'Close',
    dist24hTitle: '24-Hour Activity',
    hoverToViewHour: 'Hover to inspect hourly usage',
    appCategoryTitle: 'Category',
    btnIgnoreApp: 'Ignore App',
    btnRestoreApp: 'Restore Tracking',
    sessionListTitle: 'Session Timeline',
    orderByTime: 'Chronological',
    emptyAppSessions: 'No usage sessions recorded for this app today',
    resizeTip: 'Drag to resize window',
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
    fontSmall: 'Small',
    fontStandard: 'Default',
    fontLarge: 'Large',
    labelAutoStart: 'Launch Dayflow at Login',
    descAutoStart: 'Automatically start Dayflow in background when signing in to Windows.',
    labelAlwaysOnTopSetting: 'Always on Top',
    descAlwaysOnTopSetting: 'Keep Dayflow window floating above other desktop windows.',
    labelHealthGuard: 'Focus & Sedentary Health Guard',
    descHealthGuard: 'Show care banner and Windows notifications when continuous focus reaches threshold.',
    labelRemindInterval: 'Reminder Interval',
    labelDndGame: 'Game & Fullscreen DND',
    descDndGame: 'Pause notifications during fullscreen games or presentations.',
    labelRemindSound: 'Gentle Notification Chime',
    descRemindSound: 'Play a subtle chime when sending Windows notifications.',
    min20: '20 min',
    min30Default: '30 min (Default)',
    min45: '45 min',
    min60: '60 min',
    min90: '90 min',
    labelVersionInfo: 'Version',
    btnCheckUpdate: 'Check Update',
    btnLatestVersion: 'Up to Date',
    labelDataStorage: 'Local Data Storage',
    descDataStorage: 'All records are stored permanently in local SQLite database with 100% privacy.',
    copyrightText: 'Dayflow Screen Time · Crafted for Windows',
    confirmQuitTitle: 'Exit Dayflow?',
    confirmQuitDesc: 'Screen time tracking will be paused after exiting.',
    btnCancel: 'Cancel',
    btnConfirmQuit: 'Exit App',
    pressShortcut: 'Press shortcut',
    resetDefaultShortcut: 'Restore Defaults',
    customIntervalTip: 'Custom interval (5~240 min):',
    exportModalTitle: 'Export Usage Report (CSV)',
    exportSelectPeriod: 'Select export period:',
    exportSelectedDate: 'Target date:',
    btnConfirmExport: 'Export CSV Report',
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

/**
 * 根据当前语言返回分类名称
 */
export function getCategoryLabel(catKey) {
  const t = i18n.value
  const map = {
    all: t.catAll,
    social: t.catSocial,
    creative: t.catCreative,
    entertainment: t.catEntertainment,
    productivity: t.catProductivity,
    other: t.catOther,
  }
  return map[catKey] || map.other
}

/**
 * 根据当前语言返回软件本地化显示名
 */
export function getLocalizedAppName(rawName) {
  if (!rawName) return i18n.value.catOther
  const str = String(rawName).trim()
  const loc = currentLocale.value
  if (loc === 'en' && APP_NAME_EN_MAP[str]) {
    return APP_NAME_EN_MAP[str]
  }
  if (loc === 'zh-TW' && APP_NAME_TW_MAP[str]) {
    return APP_NAME_TW_MAP[str]
  }
  return str
}

/**
 * 多语言时长格式化（zh-CN: "2小时 15分钟" / en: "2h 15m" / zh-TW: "2小時 15分鐘"）
 */
export function formatDurationI18n(seconds, { showSecondsWhenUnderMinute = true } = {}) {
  const loc = currentLocale.value
  const sec = Math.max(0, Math.floor(Number(seconds) || 0))
  const hours = Math.floor(sec / 3600)
  const minutes = Math.floor((sec % 3600) / 60)

  if (loc === 'en') {
    if (sec === 0) return '0m'
    if (hours > 0 && minutes > 0) return `${hours}h ${minutes}m`
    if (hours > 0) return `${hours}h`
    if (minutes > 0) return `${minutes}m`
    return showSecondsWhenUnderMinute ? `${sec}s` : '<1m'
  }

  const hUnit = loc === 'zh-TW' ? '小時' : '小时'
  const mUnit = loc === 'zh-TW' ? '分鐘' : '分钟'
  const sUnit = '秒'

  if (sec === 0) return `0${mUnit}`
  if (hours > 0 && minutes > 0) {
    return `${hours}${hUnit} ${minutes}${mUnit}`
  }
  if (hours > 0) {
    return `${hours}${hUnit}`
  }
  if (minutes > 0) {
    return `${minutes}${mUnit}`
  }
  return showSecondsWhenUnderMinute ? `${sec}${sUnit}` : loc === 'zh-TW' ? '不足1分鐘' : '不足1分钟'
}

/**
 * 多语言格式化日期/周/月顶部横幅
 */
export function formatPeriodBannerI18n(dashboard, fallbackDateStr = '') {
  const loc = currentLocale.value
  const t = i18n.value
  const period = dashboard?.period || 'day'
  const rawDate = dashboard?.date_str || fallbackDateStr || ''
  const todayStr = dashboard?.today_str || ''

  if (!rawDate) return t.todayTag

  const parseYMD = (s) => {
    const p = String(s || '').split('-').map(Number)
    if (p.length !== 3) return null
    return { y: p[0], m: p[1], d: p[2], dt: new Date(p[0], p[1] - 1, p[2]) }
  }

  const cur = parseYMD(rawDate)
  if (!cur) return rawDate

  const monthNamesEn = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  if (period === 'week') {
    const s = parseYMD(dashboard?.start_date_str) || cur
    const e = parseYMD(dashboard?.end_date_str) || cur
    const isThisWeek = todayStr && dashboard?.start_date_str <= todayStr && todayStr <= dashboard?.end_date_str
    if (loc === 'en') {
      const rangeStr = `${monthNamesEn[s.m - 1]} ${s.d} - ${monthNamesEn[e.m - 1]} ${e.d}`
      return isThisWeek ? `${rangeStr} · ${t.thisWeekTag}` : rangeStr
    }
    const rangeStr = `${s.m}月${s.d}日 - ${e.m}月${e.d}日`
    return isThisWeek ? `${rangeStr} · ${t.thisWeekTag}` : rangeStr
  }

  if (period === 'month') {
    const isThisMonth = todayStr && todayStr.slice(0, 7) === rawDate.slice(0, 7)
    if (loc === 'en') {
      const mStr = `${monthNamesEn[cur.m - 1]} ${cur.y}`
      return isThisMonth ? `${mStr} · ${t.thisMonthTag}` : mStr
    }
    const mStr = `${cur.y}年${cur.m}月`
    return isThisMonth ? `${mStr} · ${t.thisMonthTag}` : mStr
  }

  // period === 'day'
  const jsDay = cur.dt.getDay() // 0=Sun..6=Sat
  const wkIdx = (jsDay + 6) % 7 // 0=Mon..6=Sun
  const wkName = t.weekdays[wkIdx] || ''

  let dayTag = ''
  if (todayStr && rawDate === todayStr) {
    dayTag = t.todayTag
  } else if (todayStr) {
    const td = parseYMD(todayStr)
    if (td) {
      const diffDays = Math.round((td.dt - cur.dt) / 86400000)
      if (diffDays === 1) dayTag = t.yesterdayTag
    }
  }

  if (loc === 'en') {
    const md = `${monthNamesEn[cur.m - 1]} ${cur.d}`
    return dayTag ? `${md} · ${dayTag} (${wkName})` : `${md} · ${wkName}`
  }

  const md = `${cur.m}月${cur.d}日`
  return dayTag ? `${md} ${dayTag} · ${wkName}` : `${md} · ${wkName}`
}

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
    if (prefs.health_remind_enabled !== undefined) appPreferences.health_remind_enabled = Boolean(prefs.health_remind_enabled)
    if (prefs.rest_remind_interval_sec !== undefined) appPreferences.rest_remind_interval_sec = Number(prefs.rest_remind_interval_sec) || 1800
    if (prefs.health_remind_sound !== undefined) appPreferences.health_remind_sound = Boolean(prefs.health_remind_sound)
    if (prefs.health_remind_dnd_game !== undefined) appPreferences.health_remind_dnd_game = Boolean(prefs.health_remind_dnd_game)
    if (prefs.idle_detection_enabled !== undefined) appPreferences.idle_detection_enabled = Boolean(prefs.idle_detection_enabled)
    if (prefs.idle_threshold_sec !== undefined) appPreferences.idle_threshold_sec = Number(prefs.idle_threshold_sec) || 180
    if (prefs.global_hotkey_enabled !== undefined) appPreferences.global_hotkey_enabled = Boolean(prefs.global_hotkey_enabled)
    if (prefs.global_hotkey !== undefined) appPreferences.global_hotkey = String(prefs.global_hotkey)
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
