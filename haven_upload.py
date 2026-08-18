#!/usr/bin/env python3
"""
Haven YouTube Uploader
Uploads videos to YouTube with proper metadata and AI disclosure.

Setup:
    1. Go to https://console.cloud.google.com
    2. Create a new project
    3. Enable "YouTube Data API v3"
    4. Go to Credentials → Create Credentials → OAuth 2.0 Client ID
    5. Download the JSON file, rename to client_secret.json
    6. Place it in the credentials/ folder
    7. Run this script once to authenticate

Usage:
    python3 haven_upload.py
    python3 haven_upload.py --video output/haven_2026-08-16.mp4 --thumb thumbs/haven_2026-08-16.jpg
"""

import argparse
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from config import load_config
from haven_control import load_record, record_upload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
CLIENT_SECRET_FILE = 'credentials/client_secret.json'
TOKEN_FILE = 'credentials/token.pickle'


def get_authenticated_service():
    """Authenticate with YouTube API"""
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                print("❌ client_secret.json not found!")
                print()
                print("   Setup required:")
                print("   1. Go to https://console.cloud.google.com")
                print("   2. Create a new project")
                print("   3. Enable 'YouTube Data API v3'")
                print("   4. Go to APIs & Services → Credentials")
                print("   5. Click 'Create Credentials' → 'OAuth 2.0 Client ID'")
                print("   6. Application type: 'Desktop app'")
                print("   7. Download the JSON file")
                print("   8. Rename it to client_secret.json")
                print("   9. Place it in the credentials/ folder")
                print()
                return None
            
            print("🔐 Starting OAuth authentication...")
            print("   A browser window will open. Sign in and grant permission.")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        os.makedirs('credentials', exist_ok=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        print("✅ Token saved for future uploads")
    
    return build('youtube', 'v3', credentials=creds)


def build_video_body(config, privacy_status="private"):
    """Build explicit, policy-aware metadata for a YouTube upload."""
    title = config.get('title', 'Ambient Music')
    description = config.get('description', '')
    tags = config.get('tags', [])
    
    # Ensure AI disclosure is in description
    if 'AI' not in description:
        description += "\n\n⚠️ This music was created with AI assistance."
    
    return {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': '10',  # Music
            'defaultLanguage': 'en',
        },
        'status': {
            # Private-first prevents an unreviewed render from becoming public.
            'privacyStatus': privacy_status,
            'selfDeclaredMadeForKids': False,
            'madeForKids': False,
            'containsSyntheticMedia': True,
        },
        'contentDetails': {
            'licensedContent': False,
        }
    }


def upload_video(video_path, thumbnail_path, config, privacy_status="private"):
    """Upload video to YouTube. Uploads are private unless explicitly overridden."""
    youtube = get_authenticated_service()
    if not youtube:
        return None

    body = build_video_body(config, privacy_status)
    title = body["snippet"]["title"]
    tags = body["snippet"]["tags"]
    
    print(f"⏫ Uploading: {title}")
    print(f"   Video: {video_path}")
    print(f"   Tags: {', '.join(tags[:5])}...")
    
    try:
        # Upload video
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part='snippet,status,contentDetails',
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   {int(status.progress() * 100)}%")
        
        video_id = response['id']
        print(f"✅ Upload complete!")
        print(f"   Video ID: {video_id}")
        print(f"   URL: https://youtube.com/watch?v={video_id}")
        
        # Upload thumbnail
        if thumbnail_path and os.path.exists(thumbnail_path):
            print("🖼️  Uploading thumbnail...")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            print("   ✅ Thumbnail uploaded")
        
        return video_id
        
    except HttpError as e:
        print(f"❌ Upload failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Haven YouTube Uploader')
    parser.add_argument('--video', default=None, help='Path to video file')
    parser.add_argument('--thumb', default=None, help='Path to thumbnail')
    parser.add_argument('--title', default=None, help='Override title')
    parser.add_argument('--private', action='store_true', help='Deprecated: private is already the default')
    parser.add_argument('--publish', action='store_true', help='Make public immediately (requires an explicit opt-in)')
    args = parser.parse_args()
    
    print("=" * 65)
    print("📤 HAVEN YOUTUBE UPLOADER")
    print("=" * 65)
    print()
    
    config = load_config()

    content_id = config.get("content_id")
    if content_id:
        record = load_record(content_id)
        if record["status"] not in {"approved_for_upload", "uploaded_private", "published"}:
            print("❌ Publication package is not approved for upload.")
            print("   Review the render in Haven, then choose 'Approve publication package'.")
            return 1
    
    # Find video file
    video_path = args.video
    if not video_path:
        from datetime import datetime
        date = config.get('date', datetime.now().strftime('%Y-%m-%d'))
        default_path = f"output/haven_{date}.mp4"
        if os.path.exists(default_path):
            video_path = default_path
        else:
            # Find any recent video
            import glob
            videos = glob.glob('output/*.mp4')
            if videos:
                videos.sort(key=os.path.getmtime, reverse=True)
                video_path = videos[0]
    
    if not video_path or not os.path.exists(video_path):
        print("❌ No video file found!")
        print("   Specify with: --video output/your_video.mp4")
        return 1
    
    # Find thumbnail
    thumb_path = args.thumb
    if not thumb_path:
        date = config.get('date', '')
        default_thumb = f"thumbs/haven_{date}.jpg"
        if os.path.exists(default_thumb):
            thumb_path = default_thumb
        else:
            import glob
            thumbs = glob.glob('thumbs/*.jpg')
            if thumbs:
                thumbs.sort(key=os.path.getmtime, reverse=True)
                thumb_path = thumbs[0]
    
    if args.title:
        config['title'] = args.title
    
    privacy_status = 'public' if args.publish else 'private'
    
    print(f"📹 Video: {video_path}")
    print(f"🖼️  Thumbnail: {thumb_path if thumb_path and os.path.exists(thumb_path) else 'None'}")
    print(f"📝 Title: {config.get('title', 'N/A')}")
    print()
    
    video_id = upload_video(video_path, thumb_path, config, privacy_status=privacy_status)
    
    if video_id:
        print()
        print("=" * 65)
        print("🎉 UPLOAD SUCCESSFUL")
        print("=" * 65)
        print(f"🔗 https://youtube.com/watch?v={video_id}")
        if content_id:
            record_upload(content_id, video_id, f"https://youtube.com/watch?v={video_id}", privacy_status)
        print("=" * 65)


if __name__ == "__main__":
    raise SystemExit(main() or 0)
