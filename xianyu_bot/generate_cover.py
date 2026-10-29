from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """加载 Windows 微软雅黑字体，不可用时回退默认字体。"""
    candidates = (
        ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"]
        if bold
        else ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc"]
    )
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_xianyu_cover(root_dir: Path | None = None) -> Path:
    """使用 Pillow 将 Dayflow 三张实机运行截图合成为 1200x1200 高转化率闲鱼商品首图海报。"""
    if root_dir is None:
        root_dir = Path(__file__).resolve().parent.parent

    screenshots_dir = root_dir / "assets" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    out_path = screenshots_dir / "xianyu_cover.png"

    W, H = 1200, 1200
    canvas = Image.new("RGBA", (W, H), (18, 18, 24, 255))
    draw = ImageDraw.Draw(canvas)

    # 顶部与底部装饰渐变色块条
    draw.rounded_rectangle([36, 36, W - 36, H - 36], radius=36, fill=(24, 24, 32, 255), outline=(63, 63, 78, 255), width=3)

    # 顶部角标胶囊：24小时全自动秒发货
    draw.rounded_rectangle(
        [72, 68, 430, 124],
        radius=28,
        fill=(16, 185, 129, 255),
    )
    font_badge = _load_font(24, bold=True)
    draw.text((98, 80), "● 24h 自动发货 · 夸克网盘秒发", fill=(255, 255, 255, 255), font=font_badge)

    # 右上角系统支持胶囊
    draw.rounded_rectangle(
        [830, 68, 1128, 124],
        radius=28,
        fill=(59, 130, 246, 255),
    )
    draw.text((858, 80), "● 支持 Win10 / Win11", fill=(255, 255, 255, 255), font=font_badge)

    # 主标题与副标题
    font_title = _load_font(56, bold=True)
    font_sub = _load_font(28, bold=False)
    draw.text((72, 148), "Dayflow 桌面屏幕时长管家", fill=(255, 255, 255, 255), font=font_title)
    draw.text(
        (74, 224),
        "每日/周/月统计 · 真实图标 · QQ同款贴顶隐藏 · 绿色免安装即开即用",
        fill=(161, 161, 170, 255),
        font=font_sub,
    )

    # 拼接三张实机截图
    img_files = [
        screenshots_dir / "dashboard.png",
        screenshots_dir / "ranking.png",
        screenshots_dir / "settings.png",
    ]
    loaded_imgs: list[Image.Image] = []
    for p in img_files:
        if p.is_file():
            try:
                loaded_imgs.append(Image.open(p).convert("RGBA"))
            except Exception:
                pass

    if loaded_imgs:
        card_w = 336
        card_h = 650
        gap = 32
        start_x = (W - (card_w * len(loaded_imgs) + gap * (len(loaded_imgs) - 1))) // 2
        top_y = 295

        for idx, im in enumerate(loaded_imgs):
            x = start_x + idx * (card_w + gap)
            y = top_y + (20 if idx != 1 else 0)  # 中间一张略微凸出更有层次感
            resized = im.resize((card_w, card_h), Image.Resampling.LANCZOS)
            # 卡片外发光边框
            draw.rounded_rectangle(
                [x - 4, y - 4, x + card_w + 4, y + card_h + 4],
                radius=18,
                fill=(39, 39, 50, 255),
                outline=(59, 130, 246, 180) if idx == 1 else (82, 82, 95, 160),
                width=3,
            )
            canvas.paste(resized, (x, y), resized)

    # 底部四大卖点横幅
    banner_y = 1015
    draw.rounded_rectangle(
        [68, banner_y, W - 68, banner_y + 115],
        radius=24,
        fill=(32, 32, 43, 255),
        outline=(75, 85, 99, 180),
        width=2,
    )
    font_feat = _load_font(25, bold=True)
    features = [
        ("● 日/周/月汇总图表", (96, 165, 250, 255)),
        ("● 深浅主题 & 多语言", (34, 211, 238, 255)),
        ("● 拖到屏幕顶部隐藏", (52, 211, 153, 255)),
        ("● 100%本地隐私存储", (251, 191, 36, 255)),
    ]
    col_w = (W - 140) // 4
    for i, (text, color) in enumerate(features):
        fx = 88 + i * col_w
        draw.text((fx, banner_y + 42), text, fill=color, font=font_feat)

    canvas.convert("RGB").save(out_path, format="PNG", optimize=True)
    return out_path


if __name__ == "__main__":
    p = generate_xianyu_cover()
    print(f"[Dayflow Xianyu] Cover image generated: {p}")
