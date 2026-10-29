from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from xianyu_bot.config import (
    BUYER_REQUEST_DELIVERY_KEYWORDS,
    DELIVERY_MESSAGE,
    ORDER_PAID_KEYWORDS,
    PRE_SALE_AUTO_REPLIES,
    QUARK_EXTRACT_CODE,
    QUARK_SHARE_URL,
    QUARK_TOKEN,
    XIANYU_ITEM_DESCRIPTION,
    XIANYU_ITEM_TITLE,
    XIANYU_ORIGINAL_PRICE,
    XIANYU_SUGGESTED_PRICE,
)
from xianyu_bot.generate_cover import generate_xianyu_cover

GOOFISH_HOME_URL = "https://www.goofish.com"
GOOFISH_IM_URL = "https://www.goofish.com/im"

BOT_DIR = Path(__file__).resolve().parent
ROOT_DIR = BOT_DIR.parent
PROFILE_DIR = BOT_DIR / "browser_profile"
DATA_DIR = BOT_DIR / "data"
DELIVERY_LOG_PATH = DATA_DIR / "delivery_log.json"


def copy_to_windows_clipboard(text: str) -> bool:
    """将文本复制到 Windows 系统剪贴板，方便一键粘贴商品文案或发货内容。"""
    if sys.platform != "win32":
        return False
    try:
        proc = subprocess.Popen(
            ["clip.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        proc.communicate(input=text.encode("utf-16-le"), timeout=3)
        return proc.returncode == 0
    except Exception:
        return False


class DeliveryLedger:
    """本地发货与自动回复防重账本，避免对同一位买家死循环重复刷屏。"""

    def __init__(self, log_path: Path = DELIVERY_LOG_PATH) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.log_path.is_file():
            return {}
        try:
            data = json.loads(self.log_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def save(self) -> None:
        try:
            self.log_path.write_text(
                json.dumps(self._records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def can_deliver(self, buyer_key: str, force_resend: bool = False, cooldown_sec: float = 60.0) -> bool:
        """判断是否应该向该买家发送网盘链接（首次付款立发；买家主动索要时冷却 60s 后可补发）。"""
        rec = self._records.get(buyer_key)
        if not rec or not rec.get("delivered_at_ts"):
            return True
        if force_resend:
            elapsed = time.time() - float(rec.get("delivered_at_ts", 0))
            return elapsed >= cooldown_sec
        return False

    def mark_delivered(self, buyer_key: str, reason: str = "order_paid") -> None:
        rec = self._records.setdefault(buyer_key, {})
        rec["delivered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rec["delivered_at_ts"] = time.time()
        rec["delivery_count"] = int(rec.get("delivery_count", 0)) + 1
        rec["last_reason"] = reason
        self.save()

    def can_auto_reply(self, buyer_key: str, msg_fingerprint: str, cooldown_sec: float = 120.0) -> bool:
        rec = self._records.get(buyer_key)
        if not rec:
            return True
        if rec.get("last_reply_fp") == msg_fingerprint:
            return False
        elapsed = time.time() - float(rec.get("replied_at_ts", 0))
        return elapsed >= cooldown_sec

    def mark_auto_replied(self, buyer_key: str, msg_fingerprint: str) -> None:
        rec = self._records.setdefault(buyer_key, {})
        rec["last_reply_fp"] = msg_fingerprint
        rec["replied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rec["replied_at_ts"] = time.time()
        self.save()


def decide_chat_action(
    buyer_key: str,
    full_chat_text: str,
    last_incoming_msg: str,
    ledger: DeliveryLedger,
) -> tuple[str | None, str | None]:
    """根据当前会话文本与买家最新消息判定动作：
    返回 (action_type, message_to_send)
    action_type: 'deliver' | 'pre_sale_reply' | None
    """
    norm_chat = (full_chat_text or "").strip()
    norm_last = (last_incoming_msg or "").strip()
    norm_last_lower = norm_last.lower()

    # 1. 如果聊天记录中已经包含我们发出的夸克提取码 zrSv，除非买家明确要求“重发/补发/没收到”，否则不再重复发
    already_has_link_in_dom = (QUARK_EXTRACT_CODE in norm_chat) or (QUARK_SHARE_URL in norm_chat)

    # 检查买家最新一句话是否在主动索要/要求补发链接
    buyer_asking_link = any(kw in norm_last for kw in BUYER_REQUEST_DELIVERY_KEYWORDS)

    # 检查当前会话中是否出现了订单已拍下/已付款系统卡片提示
    has_paid_signal = any(kw in norm_chat for kw in ORDER_PAID_KEYWORDS)

    if has_paid_signal:
        if not already_has_link_in_dom and ledger.can_deliver(buyer_key, force_resend=False):
            return "deliver", DELIVERY_MESSAGE
        if buyer_asking_link and ledger.can_deliver(buyer_key, force_resend=True, cooldown_sec=45.0):
            return "deliver", DELIVERY_MESSAGE

    # 即使未识别到系统卡片 DOM，若买家已付款并直接发“已拍，发一下链接”
    if buyer_asking_link and ("已拍" in norm_last or "付了" in norm_last or "拍了" in norm_last):
        if ledger.can_deliver(buyer_key, force_resend=True, cooldown_sec=45.0):
            return "deliver", DELIVERY_MESSAGE

    # 2. 售前咨询自动回复（仅当买家有最新发言且该发言不是我们自己的话术时）
    if norm_last and QUARK_EXTRACT_CODE not in norm_last and "全自动秒发" not in norm_last:
        for keywords, reply_text in PRE_SALE_AUTO_REPLIES:
            if any(k.lower() in norm_last_lower for k in keywords):
                if ledger.can_auto_reply(buyer_key, norm_last):
                    return "pre_sale_reply", reply_text

    return None, None


def _launch_browser_context(playwright: Any, headless: bool = False):
    """启动带持久化登录态的浏览器（优先使用系统已安装的 Chrome 或 Microsoft Edge，无需额外下载内核）。"""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    common_args = [
        "--disable-blink-features=AutomationControlled",
        "--start-maximized",
    ]

    for channel in ("msedge", "chrome", None):
        try:
            kwargs: dict[str, Any] = {
                "user_data_dir": str(PROFILE_DIR),
                "headless": headless,
                "no_viewport": True,
                "args": common_args,
            }
            if channel:
                kwargs["channel"] = channel
            ctx = playwright.chromium.launch_persistent_context(**kwargs)
            print(f"[闲鱼机器人] 已成功启动浏览器 (channel={channel or 'chromium'})")
            return ctx
        except Exception:
            continue

    raise RuntimeError(
        "无法启动浏览器，请确保系统已安装 Microsoft Edge / Google Chrome，或运行 `playwright install chromium`。"
    )


def _send_message_in_chat_box(page: Any, text: str) -> bool:
    """在闲鱼网页版 (/im) 右侧聊天输入框中填入多行文本并点击发送。"""
    input_selectors = [
        "textarea",
        "[contenteditable='true']",
        "div[role='textbox']",
        ".ant-input",
    ]

    target_box = None
    for sel in input_selectors:
        loc = page.locator(sel)
        count = loc.count()
        if count > 0:
            # 取页面最后一个可见输入框（通常在右下角聊天发送区）
            for idx in range(count - 1, -1, -1):
                candidate = loc.nth(idx)
                try:
                    if candidate.is_visible():
                        target_box = candidate
                        break
                except Exception:
                    continue
        if target_box is not None:
            break

    if target_box is None:
        return False

    try:
        target_box.click(timeout=2000)
        target_box.fill(text, timeout=3000)
        time.sleep(0.25)

        # 优先寻找“发送”按钮点击
        send_btn_selectors = [
            "button:has-text('发送')",
            "div[role='button']:has-text('发送')",
            "span:has-text('发送')",
        ]
        for btn_sel in send_btn_selectors:
            btn = page.locator(btn_sel).last
            try:
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=1500)
                    return True
            except Exception:
                continue

        # 回退为直接按 Enter 发送
        target_box.press("Enter")
        return True
    except Exception as exc:
        print(f"[闲鱼机器人] 填写或发送消息时出现异常: {exc}")
        return False


def _try_click_ship_without_logistics(page: Any) -> bool:
    """如果当前聊天窗口顶部订单卡片存在『去发货』/『无需物流』按钮，自动点击完成平台发货状态流转。"""
    ship_triggers = [
        "button:has-text('去发货')",
        "a:has-text('去发货')",
        "div:has-text('去发货')",
    ]
    for sel in ship_triggers:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=1500)
                time.sleep(0.8)
                # 若弹出“无需物流/虚拟发货/确认发货”二次确认弹窗，自动点击确认
                for confirm_sel in (
                    "text=无需物流",
                    "button:has-text('确认发货')",
                    "button:has-text('确定')",
                    "button:has-text('立即发货')",
                ):
                    c_loc = page.locator(confirm_sel).first
                    if c_loc.count() > 0 and c_loc.is_visible():
                        c_loc.click(timeout=1500)
                        time.sleep(0.4)
                return True
        except Exception:
            continue
    return False


def run_publish_Flow(headless: bool = False) -> int:
    """模式 1：生成闲鱼首图海报、将爆款文案复制到剪贴板，并打开闲鱼网页版辅助自动上架商品。"""
    cover_path = generate_xianyu_cover(ROOT_DIR)
    screenshots_dir = ROOT_DIR / "assets" / "screenshots"
    all_images = [
        str(cover_path),
        str(screenshots_dir / "dashboard.png"),
        str(screenshots_dir / "ranking.png"),
        str(screenshots_dir / "settings.png"),
    ]
    existing_images = [p for p in all_images if Path(p).is_file()]

    full_copy_text = f"{XIANYU_ITEM_TITLE}\n\n{XIANYU_ITEM_DESCRIPTION}"
    copied = copy_to_windows_clipboard(full_copy_text)

    print("=" * 72)
    print("🚀 【Dayflow 闲鱼商品上架助手】准备就绪！")
    print("=" * 72)
    print(f"📌 推荐商品标题：\n   {XIANYU_ITEM_TITLE}\n")
    print(f"💰 推荐售卖价格：¥{XIANYU_SUGGESTED_PRICE}  (原价可填 ¥{XIANYU_ORIGINAL_PRICE}，发货方式选：无需寄件/自动发货)")
    print(f"🖼️ 已为您自动合成高清商品首图与详情图 ({len(existing_images)} 张)：")
    for idx, img_p in enumerate(existing_images, 1):
        print(f"   [{idx}] {img_p}")
    if copied:
        print("\n✅ 商品【标题 + 详情文案】已自动复制到您的 Windows 剪贴板（可直接 Ctrl+V 粘贴）！")
    print("=" * 72)

    # 在资源管理器中打开图片目录方便拖拽上传
    if sys.platform == "win32":
        try:
            subprocess.Popen(["explorer.exe", str(screenshots_dir)])
        except Exception:
            pass

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = _launch_browser_context(p, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(GOOFISH_HOME_URL, wait_until="domcontentloaded")
        print("\n👉 正在打开闲鱼网页版 (https://www.goofish.com)...")
        print("   1. 若尚未登录，请使用手机闲鱼 APP 扫码登录（登录状态将永久保存）；")
        print("   2. 点击页面上的【发闲置】按钮，脚本将自动为您检测并填入商品图片、描述与价格！")

        filled_once = False
        try:
            while len(ctx.pages) > 0:
                for cur_page in list(ctx.pages):
                    try:
                        # 检测页面是否出现了文件上传 input[type='file'] 与描述框
                        file_input = cur_page.locator("input[type='file']")
                        if not filled_once and file_input.count() > 0:
                            try:
                                file_input.first.set_input_files(existing_images)
                                print("[闲鱼上架助手] ✅ 已自动上传 4 张商品图片！")
                            except Exception:
                                pass

                            # 尝试自动填入商品文案
                            for desc_sel in (
                                "textarea[placeholder*='描述']",
                                "textarea[placeholder*='介绍']",
                                "textarea",
                                "[contenteditable='true']",
                            ):
                                desc_box = cur_page.locator(desc_sel).first
                                if desc_box.count() > 0 and desc_box.is_visible():
                                    desc_box.fill(f"{XIANYU_ITEM_TITLE}\n\n{XIANYU_ITEM_DESCRIPTION}")
                                    print("[闲鱼上架助手] ✅ 已自动填入商品标题与详情文案！")
                                    break

                            # 尝试自动填入价格
                            for price_sel in (
                                "input[placeholder*='价格']",
                                "input[placeholder*='0.00']",
                            ):
                                price_box = cur_page.locator(price_sel).first
                                if price_box.count() > 0 and price_box.is_visible():
                                    price_box.fill(XIANYU_SUGGESTED_PRICE)
                                    print(f"[闲鱼上架助手] ✅ 已自动填入价格 ¥{XIANYU_SUGGESTED_PRICE}！")
                                    break

                            filled_once = True
                            print("\n🎉 自动填表已完成！请核对后点击【发布】按钮完成上架。")
                            print("💡 上架完成后，可直接运行自动发货监控模式，24 小时自动为买家发送夸克网盘链接！")
                    except Exception:
                        pass
                time.sleep(2.0)
        except KeyboardInterrupt:
            print("\n[闲鱼上架助手] 已退出。")
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    return 0


def run_auto_delivery_watch(poll_interval: float = 3.0, headless: bool = False) -> int:
    """模式 2：7×24 小时闲鱼自动发货与售前智能回复值守循环。"""
    ledger = DeliveryLedger()

    print("=" * 72)
    print("🤖 【Dayflow 闲鱼 7×24h 自动发货机器人】已启动！")
    print("=" * 72)
    print(f"📦 绑定发货网盘：{QUARK_SHARE_URL} (提取码: {QUARK_EXTRACT_CODE} | 口令: {QUARK_TOKEN})")
    print(f"📒 发货防重账本：{DELIVERY_LOG_PATH}")
    print("💡 请保持打开的浏览器窗口不要关闭，收到买家付款或咨询时将自动秒发夸克网盘链接！")
    print("=" * 72)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = _launch_browser_context(p, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(GOOFISH_IM_URL, wait_until="domcontentloaded")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已打开闲鱼消息中心 ({GOOFISH_IM_URL})，等待扫码登录或加载会话列表...")

        try:
            while len(ctx.pages) > 0:
                try:
                    # 1. 查找左侧会话列表中带未读红点或含订单关键词的会话项
                    conv_candidates = page.locator(
                        "li, div[class*='conversation-item'], div[class*='session-item'], div[class*='chat-item']"
                    )
                    total_items = min(conv_candidates.count(), 25)
                    for idx in range(total_items):
                        item = conv_candidates.nth(idx)
                        try:
                            if not item.is_visible():
                                continue
                            preview_text = (item.inner_text(timeout=500) or "").strip()
                        except Exception:
                            continue

                        if not preview_text:
                            continue

                        # 如果左侧某会话预览包含已付款/待发货/索要链接关键词，点击打开该会话
                        needs_attention = any(
                            kw in preview_text
                            for kw in (ORDER_PAID_KEYWORDS + BUYER_REQUEST_DELIVERY_KEYWORDS)
                        )
                        if needs_attention:
                            try:
                                item.click(timeout=1000)
                                time.sleep(0.6)
                            except Exception:
                                pass

                    # 2. 读取当前激活的右侧聊天窗口内容
                    body_text = ""
                    try:
                        body_text = page.locator("body").inner_text(timeout=1500) or ""
                    except Exception:
                        pass

                    if not body_text:
                        time.sleep(poll_interval)
                        continue

                    # 提取当前聊天对象标识（若未取到具体昵称则以当前会话首行文本兜底）
                    buyer_key = "active_buyer"
                    for header_sel in (
                        "div[class*='chat-header']",
                        "div[class*='title']",
                        "header",
                    ):
                        try:
                            loc = page.locator(header_sel).first
                            if loc.count() > 0 and loc.is_visible():
                                h_txt = (loc.inner_text(timeout=500) or "").strip().splitlines()
                                if h_txt and len(h_txt[0].strip()) >= 1:
                                    buyer_key = h_txt[0].strip()[:40]
                                    break
                        except Exception:
                            continue

                    # 提取最后几行消息作为买家最新消息参考
                    lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
                    last_msg = "\n".join(lines[-6:]) if lines else ""

                    action, reply_msg = decide_chat_action(
                        buyer_key=buyer_key,
                        full_chat_text=body_text,
                        last_incoming_msg=last_msg,
                        ledger=ledger,
                    )

                    if action == "deliver" and reply_msg:
                        print(
                            f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔔 检测到买家【{buyer_key}】已拍下/请求发货，正在执行自动发货..."
                        )
                        # 先尝试点击“去发货/无需物流”按钮
                        if _try_click_ship_without_logistics(page):
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 已自动点击【去发货/无需物流】按钮！")

                        # 在聊天框发送夸克网盘永久链接与使用说明
                        if _send_message_in_chat_box(page, reply_msg):
                            ledger.mark_delivered(buyer_key, reason="auto_delivery")
                            print(
                                f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 已成功向【{buyer_key}】发送夸克网盘链接 ({QUARK_SHARE_URL})！"
                            )

                    elif action == "pre_sale_reply" and reply_msg:
                        print(
                            f"\n[{datetime.now().strftime('%H:%M:%S')}] 💬 检测到买家【{buyer_key}】售前咨询，正在自动回复..."
                        )
                        if _send_message_in_chat_box(page, reply_msg):
                            ledger.mark_auto_replied(buyer_key, last_msg)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 已完成售前自动回复！")

                except Exception:
                    pass

                time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\n[闲鱼机器人] 收到退出指令，正在安全关闭...")
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    return 0


def print_dry_run_summary() -> int:
    """模式 3：生成宣传首图、复制上架文案到剪贴板，并在终端打印完整上架文案与自动发货消息预览。"""
    cover_path = generate_xianyu_cover(ROOT_DIR)
    copy_to_windows_clipboard(f"{XIANYU_ITEM_TITLE}\n\n{XIANYU_ITEM_DESCRIPTION}")
    print("=" * 72)
    print("✅ [1/3] 闲鱼商品首图海报已生成：")
    print(f"   -> {cover_path}")
    print("\n✅ [2/3] 闲鱼上架商品标题与详情文案（已自动复制到剪贴板）：")
    print("-" * 72)
    print(f"标题：{XIANYU_ITEM_TITLE}")
    print(f"建议售价：¥{XIANYU_SUGGESTED_PRICE} (原价 ¥{XIANYU_ORIGINAL_PRICE})")
    print("-" * 72)
    print(XIANYU_ITEM_DESCRIPTION)
    print("\n✅ [3/3] 自动发货机器人将发送的夸克网盘发货消息预览：")
    print("-" * 72)
    print(DELIVERY_MESSAGE)
    print("=" * 72)
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Dayflow 闲鱼商品上架与 24 小时自动发货机器人")
    parser.add_argument(
        "--mode",
        choices=["menu", "watch", "publish", "preview"],
        default="menu",
        help="运行模式：menu=交互式菜单 (默认)，watch=24h自动发货值守，publish=上架商品到闲鱼，preview=生成宣传图并预览文案",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="自动发货轮询间隔秒数 (默认 3.0 秒)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="无头浏览器模式 (首次扫码登录请勿开启)",
    )
    args = parser.parse_args(argv)

    mode = args.mode
    if mode == "menu":
        print("=" * 72)
        print("   Dayflow - 闲鱼 (Goofish) 自动上架与 24h 夸克网盘自动发货助手")
        print("=" * 72)
        print(f"   绑定夸克网盘: {QUARK_SHARE_URL}")
        print(f"   提取码: {QUARK_EXTRACT_CODE}   |   口令: {QUARK_TOKEN}")
        print("=" * 72)
        print("   [1] 启动 24 小时自动发货机器人 (监控闲鱼消息并自动发送夸克网盘链接)")
        print("   [2] 一键发布/上架 Dayflow 到闲鱼 (生成首图 + 自动复制文案 + 打开闲鱼)")
        print("   [3] 仅生成宣传首图并预览上架文案与发货话术")
        print("-" * 72)
        try:
            choice = input("👉 请输入数字 [1/2/3] 并回车 (直接回车默认选 1): ").strip()
        except EOFError:
            choice = "1"
        if choice == "2":
            mode = "publish"
        elif choice == "3":
            mode = "preview"
        else:
            mode = "watch"

    if mode == "preview":
        return print_dry_run_summary()
    if mode == "publish":
        return run_publish_Flow(headless=args.headless)
    return run_auto_delivery_watch(poll_interval=args.interval, headless=args.headless)


if __name__ == "__main__":
    raise SystemExit(main())
