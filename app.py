from flask import Flask, render_template, request, jsonify
import requests
import re
from flask_sqlalchemy import SQLAlchemy
import json
import logging

app = Flask(__name__)

DISCOGS_API_TOKEN = "GwesTfjmlWGqXOeGycdSVgqopWAncbEuhUTPUOgw"  # Replace with your actual token

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///albums.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discogs_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    artist = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(100), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    tracklist = db.Column(db.Text, nullable=True)  # Store as JSON string
    cover_image = db.Column(db.String(500), nullable=True)
    discogs_link = db.Column(db.String(500), unique=True, nullable=False)
    style = db.Column(db.String(200), nullable=True)
    label = db.Column(db.String(200), nullable=True)
    catalog_number = db.Column(db.String(100), nullable=True)
    shelf_label = db.Column(db.String(10), nullable=True)

    def to_dict(self):
        return {
            "title": self.title,
            "artist": self.artist,
            "genre": self.genre,
            "year": self.year,
            "tracklist": self.tracklist,
            "cover_image": self.cover_image,
            "discogs_link": self.discogs_link,
            "style": self.style,
            "label": self.label,
            "catalog_number": self.catalog_number,
            "shelf_label": self.shelf_label
        }

# Initialize the database
with app.app_context():
    db.create_all()  # Removed db.drop_all() to avoid data loss

def extract_id(link):
    """Extract the Discogs ID and type (release or master) from the link."""
    release_match = re.search(r'release/(\d+)', link)
    master_match = re.search(r'master/(\d+)', link)

    if release_match:
        return "release", release_match.group(1)
    elif master_match:
        return "master", master_match.group(1)
    return None, None

def fetch_album_data(link, shelf_label):
    """Fetch album data from Discogs API and save to the database."""
    id_type, album_id = extract_id(link)
    if not album_id:
        return {"error": f"Invalid Discogs link: {link}"}

    # Check if album is already in the database
    existing_album = Album.query.filter_by(discogs_id=album_id).first()
    if existing_album:
        return existing_album.to_dict()

    # If not in the database, fetch data from Discogs API
    url = f"https://api.discogs.com/{id_type}s/{album_id}"
    headers = {"Authorization": f"Discogs token={DISCOGS_API_TOKEN}"}
    response = requests.get(url, headers=headers)

    # Log the status code and response data
    logger.debug(f"Fetching data from {url}")
    logger.debug(f"Response status code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        genre = ", ".join(data.get("genres", []))

        # Filter and save specific fields
        album_data = {
            "discogs_id": album_id,
            "title": data.get("title"),
            "artist": data.get("artists", [{}])[0].get("name"),
            "genre": genre,
            "year": data.get("year"),
            "tracklist": json.dumps([{"title": track["title"], "duration": track.get("duration")} for track in data.get("tracklist", [])]),
            "cover_image": data.get("images", [{}])[0].get("uri"),
            "discogs_link": link,
            "style": ", ".join(data.get("styles", [])),
            "label": ", ".join([label.get("name") for label in data.get("labels", [])]),
            "catalog_number": data.get("catalog_number"),
            "shelf_label": shelf_label  # Ensure shelf_label is included here
        }

        # Save album to the database
        new_album = Album(**album_data)
        db.session.add(new_album)
        db.session.commit()

        return new_album.to_dict()
    else:
        return {"error": f"Failed to fetch data for {link}, Status code: {response.status_code}"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    total_albums = get_total_albums()
    return render_template('dashboard.html', total_albums=total_albums)

def get_total_albums():
    """Returns the total number of albums in the database."""
    return Album.query.count()

@app.route('/albums', methods=['GET'])
def get_albums():
    albums = fetch_albums_from_db()
    return jsonify(albums)

def fetch_albums_from_db():
    """Fetch all albums from the database."""
    return [album.to_dict() for album in Album.query.all()]

@app.route('/album', methods=['POST'])
def add_album():
    data = request.json
    # Add album to database logic here
    return jsonify({'message': 'Album added successfully'}), 201

@app.route('/album/<int:id>', methods=['PUT'])
def update_album(id):
    data = request.json
    # Update album logic here
    return jsonify({'message': 'Album updated successfully'})

@app.route('/album/<int:id>', methods=['DELETE'])
def delete_album(id):
    # Delete album logic here
    return jsonify({'message': 'Album deleted successfully'})

@app.route('/get_album_info', methods=['POST'])
def get_album_info():
    data = request.json
    links = data.get('links', [])
    shelf_label = data.get('shelf_label')
    results = []

    for link in links:
        album_data = fetch_album_data(link, shelf_label)
        results.append(album_data)

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
