import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# .envファイルから環境変数を読み込む
load_dotenv()

class Settings(BaseSettings):
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_refresh_token: str = os.getenv("GOOGLE_REFRESH_TOKEN", "")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")

    gmail_query_audio: str = os.getenv("GMAIL_QUERY_AUDIO", "本日の音声素材")
    gmail_query_script: str = os.getenv("GMAIL_QUERY_SCRIPT", "撮影分の台本について")
    drive_folder_id_step2: str = os.getenv("DRIVE_FOLDER_ID_STEP2", "")
    doc_id_for_step4: str = os.getenv("DOC_ID_FOR_STEP4", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080/")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore" # .envファイルに未定義の環境変数があってもエラーにしない

settings = Settings()

if __name__ == "__main__":
    # テスト用: 設定値が正しく読み込めているか確認
    print("GOOGLE_CLIENT_ID:", settings.google_client_id)
    print("GOOGLE_CLIENT_SECRET:", settings.google_client_secret)
    print("GOOGLE_REFRESH_TOKEN:", settings.google_refresh_token)
    print("GMAIL_QUERY_AUDIO:", settings.gmail_query_audio) 