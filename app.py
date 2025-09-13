import pytest
from app import app as flask_app
import api_handler
import os

# --- Pytest Fixture for Flask App ---

@pytest.fixture
def app():
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

# --- Tests for api_handler.py ---

def test_google_search_images_success(mocker):
    """Test successful image search with Google Custom Search."""
    # Mock the googleapiclient.discovery.build function
    mock_service = mocker.Mock()
    mock_list_request = mocker.Mock()
    mock_list_request.execute.return_value = {
        'items': [{'link': 'http://fake.google.com/image.jpg'}]
    }
    mock_service.cse.return_value.list.return_value = mock_list_request
    mocker.patch('api_handler.build', return_value=mock_service)
    
    mocker.patch('api_handler.GOOGLE_API_KEY', 'fake_google_api_key')
    mocker.patch('api_handler.GOOGLE_CX_KEY', 'fake_google_cx')
    
    urls = api_handler.search_images("test sneaker")
    assert urls == ['http://fake.google.com/image.jpg']
    mock_service.cse().list.assert_called_once_with(
        q="test sneaker",
        cx='fake_google_cx',
        searchType='image',
        num=5,
        rights='cc_publicdomain,cc_attribute,cc_sharealike,cc_noncommercial,cc_nonderived'
    )

def test_generate_text_success(mocker):
    """Test successful text generation with OpenAI."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        'choices': [{'message': {'content': '{"greek": {"hook": "Γεια"}, "english": {"hook": "Hello"}}'}}]
    }
    mock_response.raise_for_status.return_value = None
    mocker.patch('requests.post', return_value=mock_response)
    
    mocker.patch('api_handler.OPENAI_API_KEY', 'fake_key')
    
    result = api_handler.generate_text_for_platform("test sneaker", "Instagram")
    assert result['platform'] == "Instagram"
    assert result['greek']['hook'] == "Γεια"
    
def test_create_video_success(mocker):
    """Test successful video render submission to Shotstack."""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {'response': {'id': 'render-123'}}
    mock_response.raise_for_status.return_value = None
    mocker.patch('requests.post', return_value=mock_response)
    
    mocker.patch('api_handler.SHOTSTACK_API_KEY', 'fake_key')
    
    render_id = api_handler.create_video("test sneaker", ["http://fake.url/image.jpg"])
    assert render_id == 'render-123'
    
def test_upload_to_cloudinary_success(mocker):
    """Test successful upload to Cloudinary."""
    mock_upload_result = {'secure_url': 'http://res.cloudinary.com/video.mp4'}
    mocker.patch('cloudinary.uploader.upload', return_value=mock_upload_result)
    
    mocker.patch('cloudinary.config', return_value=None)
    mocker.patch('api_handler.cloudinary.config', return_value=None)
    mocker.patch('api_handler.cloudinary.config', **{'return_value.cloud_name': 'name', 'return_value.api_key': 'key', 'return_value.api_secret': 'secret'})

    url = api_handler.upload_to_cloudinary("http://shotstack.url/video.mp4", "test_sneaker")
    assert url == 'http://res.cloudinary.com/video.mp4'

# --- Tests for app.py (Flask App) ---

def test_index_route(client):
    """Test the index route loads correctly."""
    response = client.get('/')
    assert response.status_code == 200
    assert "Δημιουργός Περιεχομένου για Sneakers" in response.data.decode('utf-8')

def test_generate_route(client, mocker):
    """Test the generate route with mocked backend calls."""
    mocker.patch('api_handler.search_images', return_value=['img1.jpg'])
    mocker.patch('api_handler.generate_all_texts', return_value=[{'platform': 'Test', 'greek': {}, 'english': {}}])
    mocker.patch('api_handler.create_video', return_value='render-123')
    
    response = client.post('/generate', data={
        'sneaker_name': 'My Test Shoe',
        'platforms': ['Instagram']
    })
    
    assert response.status_code == 200
    assert "Κείμενα για Social Media" in response.data.decode('utf-8')
    
    api_handler.search_images.assert_called_once_with('My Test Shoe')
    api_handler.generate_all_texts.assert_called_once_with('My Test Shoe', ['Instagram'])
    api_handler.create_video.assert_called_once_with('My Test Shoe', ['img1.jpg'])

def test_status_route_done(client, mocker):
    """Test the status route when rendering is done."""
    mocker.patch('api_handler.get_render_status', return_value={'status': 'done', 'url': 'http://shotstack.url/video.mp4', 'id': '123'})
    mocker.patch('api_handler.upload_to_cloudinary', return_value='http://cloudinary.url/video.mp4')
    
    response = client.get('/status/render-123')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'done'
    assert json_data['url'] == 'http://cloudinary.url/video.mp4'

def test_status_route_rendering(client, mocker):
    """Test the status route when still rendering."""
    mocker.patch('api_handler.get_render_status', return_value={'status': 'rendering'})
    
    response = client.get('/status/render-123')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'rendering'
