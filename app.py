import os
from dotenv import load_dotenv
import google.generativeai as genai
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import requests
import json
import cloudinary
import cloudinary.uploader

# --- Αρχικοποίηση ---
UPLOAD_FOLDER = 'uploads'
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
load_dotenv()

# --- Ρύθμιση για το Gemini AI ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# --- Ρύθμιση για το Cloudinary ---
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

# --- Συναρτήσεις ---
def call_ai(sneaker_name, language, tone):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Create a complete social media post for the "{sneaker_name}" sneaker.
    The tone of the post should be **{tone}**. Please provide the following in the {language} language, using these exact headers:
    HOOKS: [List of 3 hooks here]
    CAPTION: [The caption text here]
    HASHTAGS: [List of 5 hashtags here]
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini AI: {e}")
        return "Error"

def parse_ai_response(text):
    if "Error" in text: return {"hooks": text, "caption": "", "hashtags": ""}
    try:
        hooks = text.split("HOOKS:")[1].split("CAPTION:")[0].strip()
        caption = text.split("CAPTION:")[1].split("HASHTAGS:")[0].strip()
        hashtags = text.split("HASHTAGS:")[1].strip()
        return {"hooks": hooks, "caption": caption, "hashtags": hashtags}
    except IndexError:
        return {"hooks": text, "caption": "Could not parse response.", "hashtags": "Could not parse response."}

def create_video(image_urls, text_parts):
    shotstack_key = os.getenv("SHOTSTACK_API_KEY")
    url = "https://api.shotstack.io/v1/render"
    clips = []
    start_time = 0
    clip_length = 3
    for image_url in image_urls:
        clip = { "asset": { "type": "image", "src": image_url }, "start": start_time, "length": clip_length }
        clips.append(clip)
        start_time += clip_length
    
    title_clip = { "asset": { "type": "title", "text": text_parts['caption'], "style": "minimal", "size": "small" }, "start": 1, "length": start_time - 2 }
    clips.append(title_clip)
    payload = { "timeline": { "soundtrack": { "src": "https://shotstack-assets.s3.ap-southeast-2.amazonaws.com/music/unmm/world.mp3", "effect": "fadeInFadeOut" }, "tracks": [{ "clips": clips }] }, "output": { "format": "mp4", "resolution": "1080" } }
    headers = { "Content-Type": "application/json", "x-api-key": shotstack_key }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()['response']['id']
    except requests.exceptions.RequestException as e:
        print(f"An error occurred with Shotstack request: {e}")
        print(f"Response body: {e.response.text if e.response else 'No response'}")
        return None

# --- Κεντρική Λογική (Route) ---
@app.route('/', methods=['GET', 'POST'])
def home():
    ai_result_parts = None
    video_render_id = None
    if request.method == 'POST':
        sneaker_name_from_form = request.form['sneaker_name']
        language_from_form = request.form['language']
        tone_from_form = request.form['tone']
        
        raw_text_result = call_ai(sneaker_name_from_form, language_from_form, tone_from_form)
        ai_result_parts = parse_ai_response(raw_text_result)
        
        uploaded_files = request.files.getlist('images')
        image_urls_for_video = []
        if uploaded_files and uploaded_files[0].filename != '':
            for file in uploaded_files:
                if file:
                    try:
                        upload_result = cloudinary.uploader.upload(file)
                        image_urls_for_video.append(upload_result['secure_url'])
                    except Exception as e:
                        print(f"Cloudinary upload failed: {e}")
                        pass
            
            if ai_result_parts and image_urls_for_video:
                 video_render_id = create_video(image_urls_for_video, ai_result_parts)

    return render_template('index.html', result=ai_result_parts, video_id=video_render_id)

if __name__ == '__main__':
    app.run(debug=True)
