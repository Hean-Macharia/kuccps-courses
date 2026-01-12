from PIL import Image, ImageDraw, ImageFont
import os

# Base directory of your project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "static", "icons")

def generate_pwa_icons():
    # Ensure the icons directory exists
    os.makedirs(ICON_DIR, exist_ok=True)

    # Standard PWA icon sizes
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]

    for size in sizes:
        # White background
        img = Image.new("RGB", (size, size), color="white")
        draw = ImageDraw.Draw(img)

        # Try to load a bold font (Arial Bold), fallback to default if not available
        try:
            font = ImageFont.truetype("arialbd.ttf", size // 2)
        except:
            font = ImageFont.load_default()

        text = "K"

        # ✅ Use textbbox instead of textsize (works in Pillow ≥10)
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Center the "K" in the icon
        x = (size - w) / 2
        y = (size - h) / 2

        # Draw the red "K"
        draw.text((x, y), text, fill="#C62828", font=font)

        # Save the icon
        file_path = os.path.join(ICON_DIR, f"icon-{size}x{size}.png")
        img.save(file_path)
        print(f"Saved {file_path}")

    print("KUCCPS 'K' icons generated successfully!")

if __name__ == "__main__":
    generate_pwa_icons()
