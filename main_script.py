import os
import random
import json
import requests
import cloudinary # Import Cloudinary SDK
import cloudinary.uploader
import cloudinary.api
from PIL import Image, ImageDraw, ImageFont # Kept for potential future image features, though not used for video directly

# --- CONFIGURATION (Reads from GitHub Secrets) ---
PAGE_ID = os.getenv("PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FIREBASE_KEY_JSON_STR = os.getenv("FIREBASE_KEY_JSON")

# Cloudinary Secrets
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Check if all secrets were loaded correctly
if not all([PAGE_ID, FB_ACCESS_TOKEN, FIREBASE_KEY_JSON_STR,
            CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    print("Error: One or more required secrets (PAGE_ID, FB_ACCESS_TOKEN, FIREBASE_KEY_JSON, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET) are not set.")
    exit()

# --- Cloudinary Configuration ---
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)
CLOUDINARY_FOLDER = "Movie_Clips" # Your Cloudinary folder name

# --- Other Configurations ---
# output_folder is less relevant for direct video streaming, but kept for consistency
output_folder = "./output"
HASHTAGS = "#movieexplainhindi #viral #movierecap" # Add your desired hashtags

# --- Initialize Firebase (Assuming it's still needed for quotes/metadata) ---
# Removed for brevity if not directly used for video posting, but keep if needed for other features.
# If you don't need Firestore for video posts, you can comment out or remove this section.
# try:
#     firebase_key_dict = json.loads(FIREBASE_KEY_JSON_STR)
#     cred = credentials.Certificate(firebase_key_dict)
#     if not firebase_admin._apps:
#         firebase_admin.initialize_app(cred)
#     db = firestore.client()
# except json.JSONDecodeError:
#     print("Error: FIREBASE_KEY_JSON secret is not a valid JSON string.")
#     exit()
# except Exception as e:
#     print(f"Error initializing Firebase: {e}")
#     exit()

# --- Functions ---

def get_page_access_token(fb_user_access_token, page_id):
    """
    Fetches the page-specific access token using the user access token.
    """
    print("Fetching Page Access Token...")
    accounts_url = f"https://graph.facebook.com/me/accounts"
    params = {'access_token': fb_user_access_token}
    try:
        response = requests.get(accounts_url, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors
        accounts_data = response.json()

        if 'data' in accounts_data:
            for account in accounts_data['data']:
                if account['id'] == page_id:
                    print(f"Found Page Access Token for Page ID: {page_id}")
                    return account['access_token']
            print("Error: Could not find Page Access Token for the given Page ID in your accounts.")
            return None
        else:
            print(f"Error fetching accounts: {accounts_data.get('error', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching page token: {e}")
        if response and response.text:
            print(f"Facebook API Response: {response.text}")
        return None

def get_random_video_from_cloudinary(folder_name):
    """
    Lists videos in a Cloudinary folder and returns a random video URL and its title.
    """
    try:
        # Use Cloudinary API to list resources in the specified folder
        result = cloudinary.api.resources(
            type="upload",
            resource_type="video",
            prefix=f"{folder_name}/", # To get only videos from this folder
            max_results=500 # Adjust as needed to fetch all videos if you have many
        )

        videos = result.get('resources', [])
        if not videos:
            print(f"No videos found in Cloudinary folder: {folder_name}")
            return None, None

        random_video = random.choice(videos)
        video_url = random_video['secure_url']
        # Extract title from public_id (e.g., "Movie_Clips/My_Awesome_Movie")
        video_title = os.path.splitext(os.path.basename(random_video['public_id']))[0].replace('_', ' ').strip()
        print(f"Selected video from Cloudinary: {video_title} ({video_url})")
        return video_url, video_title

    except Exception as e:
        print(f"Error fetching video from Cloudinary: {e}")
        return None, None

def post_video_to_facebook(video_url, caption, page_access_token, page_id):
    """
    Posts a video to a Facebook Page from a given URL.
    """
    print(f"Attempting to post video to Facebook Page ID: {page_id}")
    # Facebook's Graph API for video upload
    # You can either upload directly or use the `file_url` parameter for public URLs
    post_url = f"https://graph.facebook.com/v19.0/{page_id}/videos" # Use /videos endpoint

    payload = {
        'file_url': video_url, # Use file_url for publicly accessible videos
        'description': caption,
        'access_token': page_access_token,
        'og_action_type_id': 'og.likes', # Optional: for better insights
        'og_object_id': 'me', # Optional: for better insights
    }

    try:
        response = requests.post(post_url, data=payload)
        response_data = response.json()
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        if 'id' in response_data: # For video uploads, Facebook usually returns 'id'
            video_id = response_data['id']
            print(f"Successfully started video upload to Facebook! Video ID: {video_id}")
            # Facebook often processes videos asynchronously. You can check its status.
            print(f"Video might be processing. Check it on your Facebook page or use Graph API to query its status.")
        else:
            print("Error posting video to Facebook:")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
            # Check for specific error message related to permissions
            if 'error' in response_data:
                error_msg = response_data['error'].get('message', '')
                if 'requires publish_video permission' in error_msg:
                    print("CRITICAL ERROR: Your Facebook Access Token might not have 'publish_video' permission. Please check your app settings and re-generate the token.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while trying to post video to Facebook: {e}")
        if response is not None:
            try:
                error_data = response.json()
                print(f"Facebook API Error Details (JSON): {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except json.JSONDecodeError:
                print(f"Facebook API Error Details (Text): {response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


# --- Main Logic ---
def main():
    # 1. Get Page Access Token
    page_access_token = get_page_access_token(FB_ACCESS_TOKEN, PAGE_ID)
    if not page_access_token:
        print("Exiting: Could not obtain Page Access Token.")
        return

    # 2. Get a random video from Cloudinary
    video_url, video_title = get_random_video_from_cloudinary(CLOUDINARY_FOLDER)
    if not video_url:
        print("Exiting: Could not get a video from Cloudinary.")
        return

    # 3. Prepare the caption
    caption = f"{video_title}\n\n{HASHTAGS}"
    print(f"Generated Caption:\n{caption}")

    # 4. Post the video to Facebook
    post_video_to_facebook(video_url, caption, page_access_token, PAGE_ID)

if __name__ == "__main__":
    # Create output folder if it doesn't exist (useful for general script use, less so for direct video upload)
    os.makedirs(output_folder, exist_ok=True)
    main()
