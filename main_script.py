import os
import random
import json
from PIL import Image, ImageDraw, ImageFont
import firebase_admin
from firebase_admin import credentials, firestore
import requests

# --- CONFIGURATION (Reads from GitHub Secrets) ---
PAGE_ID = os.getenv("PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FIREBASE_KEY_JSON_STR = os.getenv("FIREBASE_KEY_JSON")

# Check if secrets were loaded correctly
if not all([PAGE_ID, FB_ACCESS_TOKEN, FIREBASE_KEY_JSON_STR]):
    print("Error: One or more secrets (PAGE_ID, FB_ACCESS_TOKEN, FIREBASE_KEY_JSON) are not set.")
    exit()

# --- Use relative paths for GitHub Actions ---
input_folder = "./wallpaper"
output_folder = "./output"
font_path = "./fonnt/MerriweatherSans-MediumItalic.ttf"
font_path_secondary = "./fonnt/SplineSans-Bold.ttf"
font_path_hashtag = "./fonnt/nunitoblackitalic.ttf"

# --- Other Configurations ---
text_secondary = "Sigma Cat"
TARGET_WIDTH, TARGET_HEIGHT = 1040, 2050
font_size, font_size_secondary, font_size_hashtag = 60, 25, 30
font_colors = ["#3A0000", "#41340A", "#360C2D", "#151057", "#0F3F0C"]
font_color_secondary = "#2E2E2E"

# --- Initialize Firebase ---
try:
    firebase_key_dict = json.loads(FIREBASE_KEY_JSON_STR)
    cred = credentials.Certificate(firebase_key_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except json.JSONDecodeError:
    print("Error: FIREBASE_KEY_JSON secret is not a valid JSON string.")
    exit()

# --- Functions and Main Logic ---

counter_ref = db.collection('metadata').document('post_counter')
try:
    doc = counter_ref.get()
    current_count = doc.to_dict().get('count', 0) if doc.exists else 0
except Exception as e:
    current_count = 0
new_count = current_count + 1
text_hashtag = f"#{new_count}"
counter_ref.set({'count': new_count})
print(f"Using Post Number: {text_hashtag}")

docs = list(db.collection("quotes").stream())
if not docs:
    print("No quotes found in Firestore. Exiting script.")
    exit()
doc = random.choice(docs)
data = doc.to_dict()
text_to_add = data.get("daily", "")
print("Random quote:", text_to_add)
try:
    doc.reference.delete()
    print(f"Quote '{doc.id}' has been deleted from Firestore.")
except Exception as e:
    print(f"Error deleting quote {doc.id}: {e}")

def crop_and_resize_image(image, target_width, target_height):
    original_width, original_height = image.size
    target_aspect = target_width / target_height
    original_aspect = original_width / original_height
    if original_aspect > target_aspect:
        new_height = original_height
        new_width = int(new_height * target_aspect)
        left = (original_width - new_width) // 2
        top, right, bottom = 0, left + new_width, new_height
    else:
        new_width = original_width
        new_height = int(new_width / target_aspect)
        left, top = 0, (original_height - new_height) // 2
        right, bottom = new_width, top + new_height
    cropped_img = image.crop((left, top, right, bottom))
    return cropped_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

def wrap_text(text, font, max_width):
    lines = []
    words = text.split(' ')
    current_line = ""
    for word in words:
        if font.getlength(current_line + " " + word) <= max_width:
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word
    lines.append(current_line.strip())
    return lines

def post_to_facebook(image_path, caption):
    page_access_token = None
    print("Fetching Page Access Token...")
    accounts_url = f"https://graph.facebook.com/me/accounts"
    params = {'access_token': FB_ACCESS_TOKEN}
    try:
        response = requests.get(accounts_url, params=params)
        accounts_data = response.json()
        if 'data' in accounts_data:
            for account in accounts_data['data']:
                if account['id'] == PAGE_ID:
                    page_access_token = account['access_token']
                    break
        if not page_access_token:
            print("Error: Could not find Page Access Token for the given Page ID.")
            return
    except Exception as e:
        print(f"An error occurred while fetching page token: {e}")
        return
        
    print("Page Access Token found! Now posting photo...")
    post_url = f"https://graph.facebook.com/{PAGE_ID}/photos"
    payload = {'message': caption, 'access_token': page_access_token}
    files = {'source': open(image_path, 'rb')}
    try:
        response = requests.post(post_url, data=payload, files=files)
        response_data = response.json()
        if 'post_id' in response_data or 'id' in response_data:
            post_id = response_data.get('id') or response_data.get('post_id')
            print(f"Successfully posted to Facebook! Post ID: {post_id}")
        else:
            print("Error posting to Facebook:", response_data)
    except Exception as e:
        print(f"An error occurred while trying to post to Facebook: {e}")

# Load fonts
try:
    font_main = ImageFont.truetype(font_path, font_size)
    font_secondary = ImageFont.truetype(font_path_secondary, font_size_secondary)
    font_hashtag = ImageFont.truetype(font_path_hashtag, font_size_hashtag)
except FileNotFoundError as e:
    print(f"Error: Font file not found! Please make sure the 'fonnt' folder and fonts are in the repository.")
    exit()

# --- Main Processing Loop ---
os.makedirs(output_folder, exist_ok=True)
all_images = [f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
if not all_images:
    print("No images found in the input folder. Exiting.")
    exit()

filename = random.choice(all_images)
try:
    img_path = os.path.join(input_folder, filename)
    img = Image.open(img_path).convert("RGB")
    processed_img = crop_and_resize_image(img, TARGET_WIDTH, TARGET_HEIGHT)
    draw = ImageDraw.Draw(processed_img)

    current_font_color = random.choice(font_colors)
    margin = int(TARGET_WIDTH * 0.1)
    max_text_width = TARGET_WIDTH - (2 * margin)
    wrapped_lines = wrap_text(text_to_add, font_main, max_text_width)
    line_spacing = 20
    total_text_height = sum([font_main.getbbox(line)[3] for line in wrapped_lines]) + (len(wrapped_lines) - 1) * line_spacing
    current_y = (TARGET_HEIGHT - total_text_height) // 2

    hashtag_text_width = font_hashtag.getlength(text_hashtag)
    x_pos_hashtag = (TARGET_WIDTH - hashtag_text_width) // 2
    y_pos_hashtag = current_y - 120
    draw.text((x_pos_hashtag, y_pos_hashtag), text_hashtag, font=font_hashtag, fill=font_color_secondary)
    for line in wrapped_lines:
        line_width = font_main.getlength(line)
        x_pos = (TARGET_WIDTH - line_width) // 2
        draw.text((x_pos, current_y), line, font=font_main, fill=current_font_color)
        current_y += font_main.getbbox(line)[3] + line_spacing
    current_y += 150
    secondary_text_width = font_secondary.getlength(text_secondary)
    draw.text(((TARGET_WIDTH - secondary_text_width) // 2, current_y), text_secondary, font=font_secondary, fill=font_color_secondary)

    output_path = os.path.join(output_folder, f"final_post_{new_count}.jpg")
    processed_img.save(output_path)
    print(f"Processed and saved: {output_path}")

    # --- CHANGED HERE ---
    # Caption/Title ko khaali bhejein taaki sirf image post ho
    post_to_facebook(image_path=output_path, caption="")

except Exception as e: 
    print(f"An error occurred during image processing: {e}")
