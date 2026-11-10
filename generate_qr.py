import os
import socket
import qrcode
from PIL import Image, ImageDraw, ImageFont

def get_local_ip() -> str:
    """Finds the local LAN IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_counter_standee(target_url: str = None, output_path: str = "static/kirana_qr_standee.png"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if not target_url:
        local_ip = get_local_ip()
        target_url = f"http://{local_ip}:8000"

    print(f"[Standee Generator] Target URL: {target_url}")
    
    # 1. Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=3,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1E3A8A", back_color="#FFFFFF").convert("RGBA")

    # 2. Create Standee Canvas (800 x 1100 px - standard vertical standee aspect)
    width, height = 750, 1000
    standee = Image.new("RGBA", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(standee)

    # Decorative header banner
    draw.rectangle([0, 0, width, 180], fill="#1E3A8A")
    draw.rectangle([0, 175, width, 185], fill="#F59E0B") # Golden accent line

    # Text rendering (using default or truetype font)
    try:
        title_font = ImageFont.truetype("arial.ttf", 38)
        subtitle_font = ImageFont.truetype("arial.ttf", 22)
        cta_font = ImageFont.truetype("arial.ttf", 32)
        instruction_font = ImageFont.truetype("arial.ttf", 20)
        footer_font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        title_font = subtitle_font = cta_font = instruction_font = footer_font = ImageFont.load_default()

    # Draw Store Title
    store_title = "SHREE GANESH KIRANA STORE"
    draw.text((width // 2, 60), store_title, fill="#FFFFFF", font=title_font, anchor="mm")
    
    tagline = "Apni Dukaan - Instant Voice Order Service"
    draw.text((width // 2, 120), tagline, fill="#FEF08A", font=subtitle_font, anchor="mm")

    # Call to action text
    cta_text = "Scan Karke Radha (AI) Ko Order Bolo!"
    draw.text((width // 2, 240), cta_text, fill="#0F172A", font=cta_font, anchor="mm")

    instruction_1 = "Camera se QR scan karein - seedha Radha se baat karein"
    draw.text((width // 2, 285), instruction_1, fill="#475569", font=instruction_font, anchor="mm")

    # Paste QR Code in center
    qr_w, qr_h = qr_img.size
    qr_x = (width - qr_w) // 2
    qr_y = 340
    
    # Rounded shadow box for QR
    box_pad = 20
    draw.rounded_rectangle(
        [qr_x - box_pad, qr_y - box_pad, qr_x + qr_w + box_pad, qr_y + qr_h + box_pad],
        radius=16,
        fill="#FFFFFF",
        outline="#E2E8F0",
        width=3
    )
    standee.paste(qr_img, (qr_x, qr_y), qr_img)

    # Features badge
    draw.rounded_rectangle([80, 810, width - 80, 890], radius=12, fill="#EEF2F6")
    badge_text = "Voice Calling • No App Download • Hindi & English"
    draw.text((width // 2, 850), badge_text, fill="#1E293B", font=instruction_font, anchor="mm")

    # Footer banner
    draw.rectangle([0, height - 70, width, height], fill="#1E3A8A")
    footer_text = f"Live Store Link: {target_url}"
    draw.text((width // 2, height - 35), footer_text, fill="#E2E8F0", font=footer_font, anchor="mm")

    # Save image
    standee.save(output_path, "PNG")
    print(f"[Standee Generator] Printable Standee saved to: {os.path.abspath(output_path)}")
    return output_path

if __name__ == "__main__":
    generate_counter_standee()
