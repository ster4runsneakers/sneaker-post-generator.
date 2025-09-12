from flask import Flask, render_template, request, redirect, url_for, jsonify
import api_handler # Import our REAL handler
import time

app = Flask(__name__)

@app.route('/')
def index():
    """Renders the main input page."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """
    Handles the form submission, starts the content generation process,
    and renders the initial results page.
    """
    sneaker_name = request.form.get('sneaker_name')
    platforms = request.form.getlist('platforms') # Get list of selected platforms

    if not sneaker_name or not platforms:
        return redirect(url_for('index'))

    # --- This part of the flow is synchronous ---
    # 1. Get image URLs from Pexels
    image_urls = api_handler.search_images(sneaker_name)
    
    # 2. Get text content for all selected platforms from OpenAI
    all_texts = api_handler.generate_all_texts(sneaker_name, platforms)
    
    # --- This part is asynchronous ---
    # 3. Start the video render with Shotstack
    render_id = api_handler.create_video(sneaker_name, image_urls)
    
    # Render a results page that will poll for the video status
    return render_template(
        'results.html',
        sneaker_name=sneaker_name,
        image_urls=image_urls,
        all_texts=all_texts,
        render_id=render_id # Pass the render_id to the template
    )

@app.route('/status/<render_id>')
def status(render_id):
    """
    An endpoint for the frontend to poll for the video render status.
    Once the video is done, it uploads it to Cloudinary and returns the final URL.
    """
    render_info = api_handler.get_render_status(render_id)
    
    if render_info['status'] == 'done':
        # Video is ready, get its URL
        video_url = render_info['url']
        # Upload to Cloudinary for permanent storage
        cloudinary_url = api_handler.upload_to_cloudinary(video_url, render_info['id'])
        return jsonify({'status': 'done', 'url': cloudinary_url or video_url})
    
    elif render_info['status'] == 'failed':
        return jsonify({'status': 'failed'})
        
    else: # 'submitted', 'queued', 'rendering'
        return jsonify({'status': 'rendering'})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)
