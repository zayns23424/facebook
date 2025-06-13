import os
import random
import json # <-- NEW: JSON string ko handle karne ke liye
from PIL import Image, ImageDraw, ImageFont
import firebase_admin
from firebase_admin import credentials, firestore
import requests

# --- CONFIGURATION (Ab GitHub Secrets se aayega) ---
PAGE_ID = os.getenv("PAGE_ID")
ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FIREBASE_KEY_JSON_STR = os.getenv("FIREBASE_KEY_JSON")

# Check agar secrets load hue hain
if not all([PAGE_ID, ACCESS_TOKEN, FIREBASE_KEY_JSON_STR]):
    print("Error: One or more secrets are not set in the environment.")
    exit()

input_folder = r"./wallpaper"  # <-- CHANGED: Relative path for GitHub Actions
output_folder = r"./output" # <-- CHANGED: Relative path

# Fonts, Text, Sizes, Colors (Yeh sab waise hi hai)
font_path = r"./fonnt/MerriweatherSans-MediumItalic.ttf" # <-- CHANGED
font_path_secondary = r"./fonnt/SplineSans-Bold.ttf" # <-- CHANGED
font_path_hashtag = r"./fonnt/nunitoblackitalic.ttf" # <-- CHANGED
text_secondary = "Sigma Cat"
TARGET_WIDTH, TARGET_HEIGHT = 1040, 2050
font_size, font_size_secondary, font_size_hashtag = 60, 25, 30
font_colors = ["#3A0000", "#41340A", "#360C2D", "#151057", "#0F3F0C"]
font_color_secondary = "#2E2E2E"

# --- Firebase and Dynamic Counter Logic ---
# Initialize Firebase from the JSON string secret
try:
    firebase_key_dict = json.loads(FIREBASE_KEY_JSON_STR)
    cred = credentials.Certificate(firebase_key_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except json.JSONDecodeError:
    print("Error: FIREBASE_KEY_JSON is not a valid JSON string.")
    exit()

# ... (Baaki ka logic bilkul same hai)
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

# ... (Functions bhi bilkul same hain)
def post_to_facebook(image_path, caption):
    post_url = f"https://graph.facebook.com/{PAGE_ID}/photos"
    payload = {'message': caption, 'access_token': ACCESS_TOKEN}
    files = {'source': open(image_path, 'rb')}
    try:
        print("Posting to Facebook Page...")
        response = requests.post(post_url, data=payload, files=files)
        response_data = response.json()
        if response.status_code == 200:
            print(f"Successfully posted to Facebook! Post ID: {response_data.get('post_id')}")
        else:
            print("Error posting to Facebook:", response_data)
    except Exception as e:
        print(f"An error occurred: {e}")

# ... (Image processing loop aur baaki sab kuch same hai)
# Make sure the necessary directories exist in the runner
os.makedirs(output_folder, exist_ok=True)
os.makedirs(os.path.dirname(font_path), exist_ok=True)

# Main Logic
all_images = [f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
if not all_images:
    print("No images found in the input folder. Exiting.")
    exit()
# ... (rest of the script is the same as before) ...
