import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageFilter
import textwrap
from io import BytesIO
import random
import facebook  # <-- Facebook SDK import

# ====== CONFIGURATION ======
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
FONT_PATH = "SpecialElite.ttf"  # GitHub Actions me relative path use karein
OUTPUT_PATH = "output.jpg"

# Facebook config
user_access_token = os.getenv("FB_ACCESS_TOKEN")
page_id = os.getenv("PAGE_ID")

def get_random_quote():
    try:
        response = requests.get("https://api.quotable.io/random")
        if response.status_code == 200:
            data = response.json()
            return f'"{data["content"]}"\n- {data["author"]}'
        else:
            return "कोट फ़ेच नहीं हो पाया। कृपया बाद में कोशिश करें।"
    except Exception as e:
        return f"Error: {e}"

def invert_color(rgb):
    return tuple(255 - x for x in rgb)

def fetch_dark_image_from_pexels():
    headers = {
        "Authorization": PEXELS_API_KEY
    }
    params = {
        "query": "plain dark wallpaper",
        "per_page": 10,
        "orientation": "landscape"
    }
    response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params)
    data = response.json()
    if data.get("photos"):
        photo = random.choice(data["photos"])
        img_url = photo["src"]["large2x"]
        img_data = requests.get(img_url).content
        img = Image.open(BytesIO(img_data)).convert("RGB")
        img = img.resize((1920, 1080), Image.LANCZOS)
        return img
    else:
        raise Exception("No dark images found on Pexels.")

def draw_quote_on_image(quote, img, output_path, font_path):
    img = img.convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=30))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, 60)
    except OSError:
        print(f"Font '{font_path}' nahi mila, default font use ho raha hai.")
        font = ImageFont.load_default()
    stat = ImageStat.Stat(img)
    avg_bg_color = tuple(int(x) for x in stat.mean)
    text_color = invert_color(avg_bg_color)
    margin = 300
    max_width = img.width - 2 * margin
    lines = []
    for line in quote.split('\n'):
        temp_line = ""
        for word in line.split():
            test_line = temp_line + (" " if temp_line else "") + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                temp_line = test_line
            else:
                if temp_line:
                    lines.append(temp_line)
                temp_line = word
        if temp_line:
            lines.append(temp_line)
    line_height = (draw.textbbox((0, 0), 'hg', font=font)[3] - draw.textbbox((0, 0), 'hg', font=font)[1]) + 30
    total_text_height = line_height * len(lines)
    y = (img.height - total_text_height) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (img.width - w) // 2
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height
    img.save(output_path)
    print(f"Image saved: {output_path}")

def post_image_to_facebook_page(image_path, caption=""):
    graph = facebook.GraphAPI(user_access_token)
    accounts = graph.get_connections('me', 'accounts')
    page_access_token = None
    for account in accounts['data']:
        if account['id'] == page_id:
            page_access_token = account['access_token']
            break
    if not page_access_token:
        raise Exception("Page Token नहीं मिला – App को Page Admin होना चाहिए")
    page_graph = facebook.GraphAPI(page_access_token)
    with open(image_path, "rb") as image_file:
        post = page_graph.put_photo(image=image_file, message=caption)
    print("Image post ho gayi! Post ID:", post['post_id'])

if __name__ == "__main__":
    quote = get_random_quote()
    img = fetch_dark_image_from_pexels()
    draw_quote_on_image(quote, img, OUTPUT_PATH, FONT_PATH)
    post_image_to_facebook_page(OUTPUT_PATH, caption=quote)
