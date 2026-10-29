from __future__ import annotations

from pathlib import Path

from xianyu_bot.bot import DeliveryLedger, decide_chat_action
from xianyu_bot.config import (
    DELIVERY_MESSAGE,
    QUARK_EXTRACT_CODE,
    QUARK_SHARE_URL,
    QUARK_TOKEN,
)
from xianyu_bot.generate_cover import generate_xianyu_cover


def test_quark_config_and_cover_generation(tmp_path: Path) -> None:
    assert QUARK_SHARE_URL == "https://pan.quark.cn/s/3ad86edcaa2a"
    assert QUARK_EXTRACT_CODE == "zrSv"
    assert QUARK_TOKEN == "/~90903bswYi~:/"
    assert QUARK_SHARE_URL in DELIVERY_MESSAGE
    assert QUARK_EXTRACT_CODE in DELIVERY_MESSAGE
    assert QUARK_TOKEN in DELIVERY_MESSAGE

    # 验证首图海报生成
    cover = generate_xianyu_cover()
    assert cover.is_file()
    assert cover.stat().st_size > 10000


def test_decide_chat_action_auto_delivery_and_deduplication(tmp_path: Path) -> None:
    ledger = DeliveryLedger(tmp_path / "delivery_log.json")

    # 1. 买家售前咨询“在吗” -> 触发售前自动回复
    action1, msg1 = decide_chat_action(
        buyer_key="buyer_alice",
        full_chat_text="你好，在吗？win11能用吗",
        last_incoming_msg="你好，在吗？win11能用吗",
        ledger=ledger,
    )
    assert action1 == "pre_sale_reply"
    assert msg1 is not None and "全自动秒发" in msg1
    ledger.mark_auto_replied("buyer_alice", "你好，在吗？win11能用吗")

    # 相同消息不重复回复
    action1_dup, _ = decide_chat_action(
        buyer_key="buyer_alice",
        full_chat_text="你好，在吗？win11能用吗",
        last_incoming_msg="你好，在吗？win11能用吗",
        ledger=ledger,
    )
    assert action1_dup is None

    # 2. 买家拍下付款（聊天出现“我已拍下，请尽快发货”或“等待卖家发货”） -> 立即触发自动发夸克网盘链接
    action2, msg2 = decide_chat_action(
        buyer_key="buyer_alice",
        full_chat_text="我已拍下，请尽快发货\n等待卖家发货",
        last_incoming_msg="我已拍下，请尽快发货",
        ledger=ledger,
    )
    assert action2 == "deliver"
    assert msg2 == DELIVERY_MESSAGE
    ledger.mark_delivered("buyer_alice")

    # 3. 已发货后，常规轮询绝不重复刷屏发送
    action3, _ = decide_chat_action(
        buyer_key="buyer_alice",
        full_chat_text=f"我已拍下，请尽快发货\n{DELIVERY_MESSAGE}",
        last_incoming_msg="谢谢",
        ledger=ledger,
    )
    assert action3 is None
