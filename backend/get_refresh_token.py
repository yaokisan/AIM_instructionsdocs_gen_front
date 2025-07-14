#!/usr/bin/env python3
"""
Google OAuth2 リフレッシュトークン取得スクリプト
使用方法: python get_refresh_token.py
"""

import os
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv

# .envファイルから設定を読み込み
load_dotenv()

# OAuth設定（.envから読み込み）
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080/")

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

def get_refresh_token():
    """リフレッシュトークンを取得する"""
    
    # 設定値チェック
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ エラー: GOOGLE_CLIENT_ID または GOOGLE_CLIENT_SECRET が設定されていません")
        print("backend/.env ファイルを確認してください")
        return
    
    print("🔑 Google OAuth2 リフレッシュトークン取得ツール")
    print("=" * 50)
    print(f"クライアントID: {CLIENT_ID}")
    print(f"リダイレクトURI: {REDIRECT_URI}")
    print()
    
    # OAuth フローを作成
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI]
                }
            },
            scopes=SCOPES
        )
        flow.redirect_uri = REDIRECT_URI
        
        # 認証URLを生成（offline access + consent prompt）
        auth_url, _ = flow.authorization_url(
            prompt='consent', 
            access_type='offline'
        )
        
        print("📋 手順:")
        print("1. 以下のURLをブラウザでアクセスしてください")
        print("2. Googleアカウントでログインし、権限を許可してください")
        print("3. リダイレクト後のURLから認証コードをコピーしてください")
        print()
        print("🌐 認証URL:")
        print(auth_url)
        print()
        
        # 認証コードを入力
        print("📝 認証コード入力:")
        print("ブラウザでリダイレクトされたURLの 'code=' の後の部分をコピーして入力してください")
        auth_code = input("認証コード: ").strip()
        
        if not auth_code:
            print("❌ 認証コードが入力されていません")
            return
        
        # トークンを取得
        print("\n🔄 トークンを取得中...")
        flow.fetch_token(code=auth_code)
        
        # 結果を表示
        refresh_token = flow.credentials.refresh_token
        if refresh_token:
            print("\n✅ 成功! リフレッシュトークンを取得しました:")
            print("=" * 50)
            print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
            print("=" * 50)
            print("\n📝 次の手順:")
            print("1. 上記のトークンを backend/.env ファイルに設定してください")
            print("2. デプロイ先の環境変数にも同じ値を設定してください")
            print("3. アプリケーションを再起動してください")
        else:
            print("❌ エラー: リフレッシュトークンが取得できませんでした")
            print("'access_type=offline' と 'prompt=consent' が正しく設定されているか確認してください")
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        print("\n🔧 トラブルシューティング:")
        print("1. GOOGLE_CLIENT_ID と GOOGLE_CLIENT_SECRET が正しいか確認")
        print("2. Google Cloud Console で OAuth 2.0 設定を確認")
        print("3. リダイレクトURI がコンソールに登録されているか確認")

if __name__ == "__main__":
    get_refresh_token()