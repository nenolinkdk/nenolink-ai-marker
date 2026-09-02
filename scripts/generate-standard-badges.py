"""Generate the versioned Nenolink standard badge PNG assets."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "badges"
BADGES = {
    "ai-assisted.png": "AI Assisted",
    "ai-generated.png": "AI Generated",
    "ai-modified.png": "AI Modified",
    "human-reviewed.png": "Human Reviewed",
    "ai-image.png": "AI Image",
    "ai-video.png": "AI Video",
    "ai-audio.png": "AI Audio",
    "ai-software.png": "AI Software",
    "ai-translation.png": "AI Translation",
    "ai-localization.png": "AI Localization",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT.glob("*.png"):
        old.unlink()
    for filename, label in BADGES.items():
        image = Image.new("RGBA", (1200, 360), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 1192, 352), radius=86, fill=(184, 20, 36, 255), outline=(255, 255, 255, 255), width=12)
        draw.rounded_rectangle((54, 54, 306, 306), radius=58, fill=(255, 255, 255, 255))
        ai_font = font(116, True)
        label_font = font(104, True)
        ai_box = draw.textbbox((0, 0), "AI", font=ai_font)
        draw.text((180 - (ai_box[2] - ai_box[0]) / 2, 180 - (ai_box[3] - ai_box[1]) / 2 - ai_box[1]), "AI", font=ai_font, fill=(184, 20, 36, 255))
        box = draw.textbbox((0, 0), label, font=label_font)
        max_width = 820
        if box[2] - box[0] > max_width:
            label_font = font(round(104 * max_width / (box[2] - box[0])), True)
            box = draw.textbbox((0, 0), label, font=label_font)
        draw.text((342, 180 - (box[3] - box[1]) / 2 - box[1]), label, font=label_font, fill="white")
        image.save(OUTPUT / filename, optimize=True)


if __name__ == "__main__":
    main()
