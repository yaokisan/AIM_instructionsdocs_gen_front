#!/usr/bin/env python3
"""
Google API認証テストスクリプト
"""

import os
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# .envファイルを読み込み
load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

def test_credentials():
    """認証情報をテストする"""
    
    print("🔑 Google API認証テスト")
    print("=" * 40)
    
    # 環境変数を確認
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET") 
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    
    print(f"CLIENT_ID: {client_id[:20]}..." if client_id else "❌ CLIENT_ID が設定されていません")
    print(f"CLIENT_SECRET: {client_secret[:10]}..." if client_secret else "❌ CLIENT_SECRET が設定されていません")
    print(f"REFRESH_TOKEN: {refresh_token[:20]}..." if refresh_token else "❌ REFRESH_TOKEN が設定されていません")
    print()
    
    if not all([client_id, client_secret, refresh_token]):
        print("❌ 必要な環境変数が不足しています")
        return False
    
    try:
        # 認証情報を作成
        print("🔄 認証情報を作成中...")
        creds = Credentials.from_authorized_user_info(
            info={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "token_uri": "https://oauth2.googleapis.com/token",
            }, 
            scopes=SCOPES
        )
        
        print(f"認証情報作成: ✅")
        print(f"有効性: {'✅' if creds.valid else '❌'}")
        print(f"期限切れ: {'✅' if creds.expired else '❌'}")
        print(f"リフレッシュトークン: {'✅' if creds.refresh_token else '❌'}")
        print()
        
        # 期限切れの場合はリフレッシュを試行
        if creds.expired and creds.refresh_token:
            print("🔄 トークンをリフレッシュ中...")
            creds.refresh(Request())
            print("✅ リフレッシュ成功!")
        
        # 最終的な有効性をチェック
        if creds.valid:
            print("🎉 認証成功! APIを使用できます")
            
            # 実際にAPIを呼び出してテスト
            from googleapiclient.discovery import build
            
            print("\n📧 Gmail API テスト中...")
            service = build('gmail', 'v1', credentials=creds)
            profile = service.users().getProfile(userId='me').execute()
            print(f"✅ Gmail API成功! メールアドレス: {profile.get('emailAddress')}")
            
            print("\n📁 Drive API テスト中...")
            drive_service = build('drive', 'v3', credentials=creds)
            results = drive_service.files().list(pageSize=1).execute()
            print(f"✅ Drive API成功!")
            
            return True
        else:
            print("❌ 認証失敗: 無効な認証情報")
            return False
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_credentials()
    if not success:
        print("\n🔧 トラブルシューティング:")
        print("1. 新しいリフレッシュトークンを再取得してください")
        print("2. Google Cloud Console でOAuth設定を確認してください")
        print("3. アプリケーションの権限を確認してください")