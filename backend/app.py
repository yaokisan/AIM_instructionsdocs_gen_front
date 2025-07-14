from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import random
import string

# google_servicesから関数をインポート
from google_services import (
    step1_get_audio_material_urls,
    step2_get_latest_folder_url,
    step3_get_script_email_body,
    step4_duplicate_document,
    step5_write_info_to_documents,
    get_credentials # 認証情報取得関数も念のため（直接は使わないかも）
)

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://aim-instructionsdocs-gen-lwqr.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データのスキーマを定義するためのクラス
class EchoMessage(BaseModel):
    message: str | None = None

# 短縮URL用のデータ保存（本来はデータベースを使用）
url_database = {}

@app.get("/")
def hello():
    return {"message": "FastAPI hello!"}

@app.get("/api/hello")
def hello_world():
    return {"message": "Hello! やおき"}

@app.get("/api/multiply/{id}")
def multiply(id: int):
    print("multiply")
    doubled_value = id * 2
    return {"doubled_value": doubled_value}

@app.get("/api/divide/{id}")
def divide(id: int):
    print("divide")
    halved_value = id // 2  # 整数として扱う
    return {"halved_value": halved_value}

@app.post("/api/echo")
def echo(message: EchoMessage):
    print("echo")
    if not message:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    echo_message = message.message if message.message else "No message provided"
    return {"message": f"echo: {echo_message}"}

class CountMessage(BaseModel):
    message: str | None = None

# 短縮URL用のデータモデル
class URLRequest(BaseModel):
    url: str

class URLResponse(BaseModel):
    short_id: str
    short_url: str
    original_url: str

# 短縮ID生成関数（6文字のランダム文字列）
def generate_short_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

@app.post("/api/count")
def count_characters(message: CountMessage):
    print("count")
    if not message:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    text = message.message if message.message else ""
    return {"count": len(text)}

# 短縮URL作成API
@app.post("/api/shorten", response_model=URLResponse)
def create_short_url(url_request: URLRequest):
    print("shorten")
    original_url = url_request.url
    
    if not original_url.startswith(('http://', 'https://')):
        original_url = 'https://' + original_url
    
    short_id = generate_short_id()
    while short_id in url_database:
        short_id = generate_short_id()
    
    url_database[short_id] = original_url
    short_url = f"http://localhost:8000/s/{short_id}" # FastAPIサーバーのポートに注意
    
    return URLResponse(
        short_id=short_id,
        short_url=short_url,
        original_url=original_url
    )

@app.get("/s/{short_id}")
def redirect_to_original(short_id: str):
    print(f"redirect: {short_id}")
    if short_id not in url_database:
        raise HTTPException(status_code=404, detail="Short URL not found")
    original_url = url_database[short_id]
    return RedirectResponse(url=original_url)

@app.get("/api/urls")
def get_all_urls():
    return {"urls": url_database}

# --- デバッグ用エンドポイント ---
@app.get("/api/test_auth")
def test_auth():
    """Google API認証をテストするエンドポイント"""
    try:
        from config import settings
        import os
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        
        # 環境変数の確認
        client_id = settings.google_client_id or os.getenv("GOOGLE_CLIENT_ID")
        client_secret = settings.google_client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
        refresh_token = settings.google_refresh_token or os.getenv("GOOGLE_REFRESH_TOKEN")
        
        debug_info = {
            "client_id_set": bool(client_id),
            "client_secret_set": bool(client_secret),
            "refresh_token_set": bool(refresh_token),
            "client_id_prefix": client_id[:20] + "..." if client_id else None,
            "refresh_token_prefix": refresh_token[:20] + "..." if refresh_token else None,
        }
        
        if not all([client_id, client_secret, refresh_token]):
            return {
                "status": "error",
                "message": "環境変数が不足しています",
                "debug": debug_info
            }
        
        # 認証テスト
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/documents'
        ]
        
        creds = Credentials.from_authorized_user_info(
            info={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "token_uri": "https://oauth2.googleapis.com/token",
            }, 
            scopes=SCOPES
        )
        
        debug_info["credentials_created"] = True
        debug_info["credentials_valid"] = creds.valid
        debug_info["credentials_expired"] = creds.expired
        debug_info["has_refresh_token"] = bool(creds.refresh_token)
        
        # リフレッシュが必要な場合
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            debug_info["refreshed"] = True
        
        if creds.valid:
            # 実際にAPIテスト
            from googleapiclient.discovery import build
            service = build('gmail', 'v1', credentials=creds)
            profile = service.users().getProfile(userId='me').execute()
            
            return {
                "status": "success",
                "message": "認証成功",
                "email": profile.get('emailAddress'),
                "debug": debug_info
            }
        else:
            return {
                "status": "error", 
                "message": "認証失敗: 無効な認証情報",
                "debug": debug_info
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"認証テスト中にエラー: {str(e)}",
            "error_type": type(e).__name__,
            "debug": debug_info if 'debug_info' in locals() else {}
        }

# --- 新しいワークフロー用のコード --- 
class WorkflowRequest(BaseModel):
    number_of_copies: int # STEP4で複製するドキュメントの数

@app.post("/api/execute_workflow")
async def execute_workflow(request: WorkflowRequest):
    print("ワークフロー実行リクエスト受信")
    all_step_results = {}

    try:
        # 認証情報を事前にチェック (オプション)
        # creds = get_credentials()
        # if not creds or not creds.valid:
        #     raise HTTPException(status_code=503, detail="Google API認証に失敗しました。リフレッシュトークンを確認してください。")

        # STEP1
        print("STEP1 実行中...")
        step1_data = step1_get_audio_material_urls()
        if "エラー:" in step1_data or "見つかりませんでした" in step1_data: # エラー判定を強化
            print(f"STEP1エラー: {step1_data}")
            raise HTTPException(status_code=500, detail=f"STEP1処理エラー: {step1_data}")
        all_step_results["step1_output"] = step1_data
        print("STEP1 完了")

        # STEP2
        print("STEP2 実行中...")
        step2_data = step2_get_latest_folder_url()
        if "エラー:" in step2_data or "見つかりませんでした" in step2_data:
            print(f"STEP2エラー: {step2_data}")
            raise HTTPException(status_code=500, detail=f"STEP2処理エラー: {step2_data}")
        all_step_results["step2_output"] = step2_data
        print("STEP2 完了")

        # STEP3
        print("STEP3 実行中...")
        step3_data = step3_get_script_email_body()
        if "エラー:" in step3_data or "見つかりませんでした" in step3_data:
            print(f"STEP3エラー: {step3_data}")
            raise HTTPException(status_code=500, detail=f"STEP3処理エラー: {step3_data}")
        all_step_results["step3_output"] = step3_data
        print("STEP3 完了")

        # STEP4
        print(f"STEP4 実行中 (複製数: {request.number_of_copies})...")
        step4_output_str, duplicated_doc_ids = step4_duplicate_document(request.number_of_copies)
        if "エラー:" in step4_output_str or "失敗しました" in step4_output_str:
            print(f"STEP4エラー: {step4_output_str}")
            raise HTTPException(status_code=500, detail=f"STEP4処理エラー: {step4_output_str}")
        if not duplicated_doc_ids: # IDリストが空の場合もエラーと見なす
             print(f"STEP4エラー: 複製されたドキュメントIDが取得できませんでした。出力: {step4_output_str}")
             raise HTTPException(status_code=500, detail=f"STEP4処理エラー: 複製されたドキュメントIDが取得できませんでした。出力: {step4_output_str}")
        all_step_results["step4_output"] = step4_output_str
        all_step_results["step4_duplicated_ids"] = duplicated_doc_ids # デバッグ用にIDも返す
        print("STEP4 完了")

        # STEP5
        print("STEP5 実行中...")
        step5_message = step5_write_info_to_documents(duplicated_doc_ids, step1_data, step2_data, step3_data)
        if "エラー:" in step5_message:
            print(f"STEP5エラー: {step5_message}")
            raise HTTPException(status_code=500, detail=f"STEP5処理エラー: {step5_message}")
        all_step_results["step5_final_message"] = step5_message
        print("STEP5 完了")

        return {
            "message": "ワークフローが正常に完了しました。",
            "details": all_step_results
        }

    except HTTPException as http_exc: # FastAPIのHTTPExceptionを再raise
        raise http_exc 
    except Exception as e:
        print(f"ワークフロー実行中に予期せぬエラー: {e}")
        # スタックトレースもログに出力するとデバッグに役立つ
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ワークフロー実行中に予期せぬサーバーエラーが発生しました: {str(e)}")

# uvicorn app:app --reload --port 8000 で起動する場合の参考