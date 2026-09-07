"""
ماژول پردازش گرافیکی و اعمال واترمارک کپسولی شیشه‌ای به همراه لاگ‌های فشرده
"""
import io
import os
from PIL import Image, ImageDraw, ImageFont
from signal_bot.logger import logger
from signal_bot.site.kv import kv_get


def get_configured_watermark_text() -> str:
    text = kv_get("settings:watermark_text")
    if text and text.strip():
        return text.strip()
    return "@MemeLand_Hub"


def is_watermark_enabled() -> bool:
    val = kv_get("settings:watermark_enabled")
    if val is None:
        return True
    return str(val).lower() in ("1", "true", "yes")


def apply_watermark(image_bytes: bytes, custom_text: str = None) -> bytes:
    if not is_watermark_enabled():
        return image_bytes

    watermark_text = custom_text or get_configured_watermark_text()

    try:
        base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        width, height = base_img.size

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(16, int(width * 0.035))

        font = None
        candidate_fonts = [
            os.path.join(os.path.dirname(__file__), "..", "..", "memeland_site", "static", "fonts", "Vazirmatn-Bold.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "arialbd.ttf",
            "arial.ttf"
        ]
        for fpath in candidate_fonts:
            if os.path.exists(fpath):
                try:
                    font = ImageFont.truetype(fpath, font_size)
                    break
                except Exception:
                    continue

        if not font:
            try:
                font = ImageFont.load_default()
            except Exception:
                pass

        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x = int(font_size * 0.6)
        pad_y = int(font_size * 0.35)
        pill_w = text_w + (pad_x * 2)
        pill_h = text_h + (pad_y * 2)

        margin_x = int(width * 0.025)
        margin_y = int(height * 0.025)
        pos_x = margin_x
        pos_y = height - pill_h - margin_y

        pill_box = [pos_x, pos_y, pos_x + pill_w, pos_y + pill_h]
        corner_radius = int(pill_h / 2)
        draw.rounded_rectangle(
            pill_box,
            radius=corner_radius,
            fill=(15, 23, 42, 160),
            outline=(255, 255, 255, 50),
            width=1
        )

        text_pos = (pos_x + pad_x, pos_y + pad_y - int(bbox[1]))
        draw.text(text_pos, watermark_text, font=font, fill=(255, 255, 255, 240))

        composed = Image.alpha_composite(base_img, overlay).convert("RGB")

        output = io.BytesIO()
        composed.save(output, format="JPEG", quality=90, optimize=True)
        result_bytes = output.getvalue()

        logger.info(f"WTM_OK: txt='{watermark_text}' sz={width}x{height}")
        return result_bytes

    except Exception as e:
        logger.warning(f"WTM_FAIL: err={e}")
        return image_bytes