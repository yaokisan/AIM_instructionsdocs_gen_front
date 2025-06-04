import os.path
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow # get_refresh_token.py で使用したが、ここでは直接は使わない想定
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings # .envからの設定情報を読み込む

# スコープ (get_refresh_token.pyと同じものを定義)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

# 認証情報ファイル (token.json) のパス
# get_refresh_token.py で refresh_token を .env に保存する方式にしたので、
# token.json を直接読み書きする処理は不要になる。
# 代わりに、.env から読み込んだ refresh_token を使用して認証情報を生成する。
# TOKEN_JSON_PATH = 'token.json' # 不要

def get_credentials():
    """Google APIの認証情報を取得または更新する。"""
    creds = None
    # .envファイルからリフレッシュトークンなどを読み込む
    if settings.google_refresh_token and settings.google_client_id and settings.google_client_secret:
        creds = Credentials.from_authorized_user_info(info={
            "refresh_token": settings.google_refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "token_uri": "https://oauth2.googleapis.com/token", # トークンエンドポイント
            # "scopes": SCOPES # ここでscopesを指定することも可能だが、build時に渡すので必須ではない
        }, scopes=SCOPES) # Credentialsオブジェクト作成時にscopesを渡す

    # 認証情報が存在し、かつ有効期限切れの場合はリフレッシュする
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # (オプション) リフレッシュ後の認証情報を保存する場合（今回は.envのrefresh_tokenを使うので不要）
            # with open(TOKEN_JSON_PATH, 'w') as token_file:
            #     token_file.write(creds.to_json())
        except Exception as e:
            print(f"リフレッシュトークンの更新に失敗しました: {e}")
            # ここでエラーが発生した場合、ユーザーに再度get_refresh_token.pyの実行を促すなどの対応が必要
            # 今回はNoneを返して、呼び出し元でエラー処理をする想定
            return None
    
    if not creds or not creds.valid:
        # 有効な認証情報がない場合はエラーメッセージを表示 (本来はここで再度認証フローを促す)
        print("有効な認証情報が見つかりません。get_refresh_token.py を実行して、")
        print("取得したリフレッシュトークンを backend/.env に正しく設定してください。")
        return None

    return creds

def extract_urls_from_text(text):
    """与えられたテキストからURLを抽出する。"""
    if not text:
        return []
    # 簡単なURL抽出の正規表現 (より複雑なものが必要な場合あり)
    url_pattern = r'https?://[\S]+'
    urls = re.findall(url_pattern, text)
    return list(set(urls)) # 重複を排除して返す

def step1_get_audio_material_urls():
    """
    STEP1: 「本日の音声素材」というワードでGmailを検索し、
    検索結果で一番上のものを開く。
    そのメールそのものと、スレッドに返信されたURLを、
    それぞれ送信者を明記して全て出力する。ただし、同一URLは重複して出力しない。
    出力形式:
    送信者メールアドレス
    https://example.com/url
    """
    creds = get_credentials()
    if not creds:
        return "エラー: Gmail APIの認証に失敗しました。"

    try:
        service = build('gmail', 'v1', credentials=creds)

        # 1. 「本日の音声素材」でメールを検索
        query = settings.gmail_query_audio
        print(f"Gmailを検索中: '{query}'")
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"「{query}」に一致するメールは見つかりませんでした。"

        # 2. 検索結果の一番上のメール(スレッド)を取得
        # list APIは通常、最新のものが先頭に来るが、ソート順が保証されていない場合もあるため、
        # 必要であればthreadIdでソートするか、より詳細なクエリを使う。ここでは先頭を取得。
        message_id = messages[0]['id']
        
        # スレッドIDを取得 (同じスレッド内のメールを全て取得するため)
        message_detail = service.users().messages().get(userId='me', id=message_id, format='metadata', metadataHeaders=['threadId']).execute()
        thread_id = message_detail.get('threadId')

        if not thread_id:
            return "エラー: メールのスレッドIDを取得できませんでした。"

        print(f"スレッドID {thread_id} のメールを処理中...")
        thread_messages = service.users().threads().get(userId='me', id=thread_id).execute()
        
        all_urls_with_senders = {} # {url: sender} の形式で重複を管理

        for msg_container in thread_messages.get('messages', []):
            msg_id = msg_container['id']
            msg = service.users().messages().get(userId='me', id=msg_id).execute()
            
            sender = ""
            for header in msg.get('payload', {}).get('headers', []):
                if header['name'].lower() == 'from':
                    sender = header['value']
                    # <example@example.com> のような形式からメールアドレスのみを抽出
                    match = re.search(r'<([^>]+)>', sender)
                    if match:
                        sender = match.group(1)
                    break
            
            body_text = ""
            if 'parts' in msg.get('payload', {}):
                for part in msg['payload']['parts']:
                    if part['mimeType'] == 'text/plain' and 'data' in part.get('body',{}):
                        import base64
                        body_text += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    # HTMLメールの場合の処理も追加可能
            elif 'body' in msg.get('payload', {}) and 'data' in msg['payload']['body']:
                 import base64
                 body_text = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')

            urls_in_mail = extract_urls_from_text(body_text)
            for url in urls_in_mail:
                if url not in all_urls_with_senders: # 重複チェック
                    all_urls_with_senders[url] = sender
        
        # スレッドの最初のメール本文からもURLを抽出 (もしスレッドAPIで取得した情報に含まれていなければ)
        # Gmail APIでは通常スレッドのメッセージには元のメッセージも含まれる
        # 上記のループで既に処理されているはずなので、ここの処理は冗長かもしれないが念のため。
        # main_message_body_text = "" # ... (message_idを使ってメール本文を取得する処理) ...
        # main_message_urls = extract_urls_from_text(main_message_body_text)
        # main_message_sender = "" # ... (message_idを使って送信者を取得する処理) ...
        # for url in main_message_urls:
        #    if url not in all_urls_with_senders:
        #        all_urls_with_senders[url] = main_message_sender

        if not all_urls_with_senders:
            return "メールからURLが見つかりませんでした。"

        output_lines = []
        for url, sender in all_urls_with_senders.items():
            output_lines.append(sender)
            output_lines.append(url)
        
        print("STEP1 完了: URLと送信者を抽出しました。")
        return "\n".join(output_lines)

    except HttpError as error:
        print(f"Gmail APIでエラーが発生しました: {error}")
        return f"Gmail APIエラー: {error}"
    except Exception as e:
        print(f"STEP1で予期せぬエラー: {e}")
        return f"STEP1で予期せぬエラー: {e}"

def step2_get_latest_folder_url():
    """
    STEP2: 指定されたGoogle Driveフォルダ内で、作成日が最も新しいフォルダの
    フォルダ名とURLを出力する。
    出力形式:
    "フォルダ名"
    https://drive.google.com/drive/folders/フォルダID
    """
    creds = get_credentials()
    if not creds:
        return "エラー: Google Drive APIの認証に失敗しました。"

    try:
        service = build('drive', 'v3', credentials=creds)
        folder_id = settings.drive_folder_id_step2

        if not folder_id:
            return "エラー: .envにDRIVE_FOLDER_ID_STEP2が設定されていません。"

        print(f"Google Drive フォルダID '{folder_id}' 内を検索中...")
        # フォルダ内で、フォルダタイプ(mimeType)で絞り込み、作成日で降順ソート、最初の1件を取得
        # fieldsで取得する情報を絞り込む (id, name, webViewLink, createdTime)
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(
            q=query,
            orderBy='createdTime desc',
            pageSize=1, # 最新の1件のみ取得
            fields='files(id, name, webViewLink, createdTime)'
        ).execute()
        
        items = results.get('files', [])

        if not items:
            return f"フォルダID '{folder_id}' 内にサブフォルダが見つかりませんでした。"

        latest_folder = items[0]
        folder_name = latest_folder['name']
        folder_url = latest_folder['webViewLink'] # webViewLinkがユーザーがブラウザで開くURL
        # folder_id_latest = latest_folder['id'] # こちらはAPIで使うID

        output_lines = [
            f'"{folder_name}"', # 指示通りダブルクォーテーションで囲む
            folder_url
        ]
        
        print(f"STEP2 完了: 最新フォルダ '{folder_name}' ({folder_url}) を見つけました。")
        return "\n".join(output_lines)

    except HttpError as error:
        print(f"Google Drive APIでエラーが発生しました: {error}")
        return f"Google Drive APIエラー: {error}"
    except Exception as e:
        print(f"STEP2で予期せぬエラー: {e}")
        return f"STEP2で予期せぬエラー: {e}"

def step3_get_script_email_body():
    """
    STEP3: 「撮影分の台本について」というワードでメールを検索し、
    ヒットしたスレッドの一番最初のメールの本文を全て出力する。
    """
    creds = get_credentials()
    if not creds:
        return "エラー: Gmail APIの認証に失敗しました。"

    try:
        service = build('gmail', 'v1', credentials=creds)
        query = settings.gmail_query_script

        if not query:
            return "エラー: .envにGMAIL_QUERY_SCRIPTが設定されていません。"

        print(f"Gmailを検索中: '{query}' (スレッドの最初のメールを取得する処理)")
        # 1. クエリに合致するメッセージリストを取得 (最新のものが先頭に来ることが多い)
        list_results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = list_results.get('messages', [])

        if not messages:
            return f"「{query}」に一致するメールは見つかりませんでした。"

        # 2. 最初にヒットしたメッセージからスレッドIDを取得
        #    このメッセージがスレッドの最新であるとは限らないが、スレッドを特定するには十分
        first_hit_message_id = messages[0]['id']
        message_meta = service.users().messages().get(userId='me', id=first_hit_message_id, format='metadata', metadataHeaders=['threadId']).execute()
        thread_id = message_meta.get('threadId')

        if not thread_id:
            return f"エラー: メッセージID '{first_hit_message_id}' からスレッドIDを取得できませんでした。"

        print(f"スレッドID '{thread_id}' のメッセージを取得中...")
        # 3. スレッドIDを使ってスレッド全体のメッセージを取得
        thread_details = service.users().threads().get(userId='me', id=thread_id).execute()
        thread_messages = thread_details.get('messages', [])

        if not thread_messages:
            return f"エラー: スレッドID '{thread_id}' からメッセージを取得できませんでした。"

        # 4. スレッド内のメッセージをinternalDateでソート (昇順 = 古い順)
        #    internalDateは文字列のUnixタイムスタンプなので、比較のために数値に変換
        #    メッセージオブジェクトに直接internalDateがない場合があるため、各メッセージを再度取得する必要がある場合もある。
        #    threads().get()で返るメッセージリストには通常internalDateが含まれる。
        def get_internal_date(msg):
            return int(msg.get('internalDate', 0)) # internalDateがなければ0として扱う(リストの最後に)
        
        thread_messages.sort(key=get_internal_date)

        if not thread_messages: # ソート後も空なら (ありえないはずだが念のため)
            return f"エラー: スレッドID '{thread_id}' にソート可能なメッセージがありませんでした。"
        
        # 5. ソート後の最初のメールのIDを取得
        first_email_in_thread_id = thread_messages[0]['id']
        print(f"スレッドの最初のメールID: {first_email_in_thread_id}")
        
        # 6. そのメールの詳細を取得
        msg = service.users().messages().get(userId='me', id=first_email_in_thread_id).execute()

        body_text = ""
        payload = msg.get('payload', {})
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain' and 'body' in part and 'data' in part['body']:
                    import base64
                    body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
        elif 'body' in payload and 'data' in payload['body']:
            if payload.get('mimeType') == 'text/plain':
                import base64
                body_text = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        
        if not body_text:
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('mimeType') == 'text/html' and 'body' in part and 'data' in part['body']:
                        import base64
                        html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        body_text = re.sub(r'<[^>]+>', '', html_body).strip()
                        if body_text:
                             print("プレーンテキストが見つからず、HTMLからテキストを抽出しました（簡易処理）。")
                             break 
            if not body_text:
                return "スレッドの最初のメールから本文 (プレーンテキスト) が見つかりませんでした。"

        print(f"STEP3 完了: スレッドの最初のメール (ID: '{first_email_in_thread_id}') の本文を取得しました。")
        return body_text.strip()

    except HttpError as error:
        print(f"Gmail APIでエラーが発生しました: {error}")
        return f"Gmail APIエラー: {error}"
    except Exception as e:
        print(f"STEP3で予期せぬエラー: {e}")
        return f"STEP3で予期せぬエラー: {e}"

def step4_duplicate_document(number_of_copies: int):
    """
    STEP4: 指定されたGoogleドキュメントを、指定された数だけ複製する。
    元のファイル名と保存場所を維持する。
    複製した各ドキュメントのタイトルとURLを出力する。
    出力形式:
    元ファイル名
    https://docs.google.com/document/d/複製されたドキュメントID1
    元ファイル名
    https://docs.google.com/document/d/複製されたドキュメントID2
    ...
    """
    creds = get_credentials()
    if not creds:
        return "エラー: Google Drive APIの認証に失敗しました。"

    if number_of_copies <= 0:
        return "複製するファイル数は1以上である必要があります。"

    try:
        drive_service = build('drive', 'v3', credentials=creds)
        original_doc_id = settings.doc_id_for_step4

        if not original_doc_id:
            return "エラー: .envにDOC_ID_FOR_STEP4が設定されていません。"

        # 1. 元のドキュメントの情報を取得 (名前と親フォルダID)
        print(f"元のドキュメントID '{original_doc_id}' の情報を取得中...")
        original_file_metadata = drive_service.files().get(
            fileId=original_doc_id,
            fields='name, parents' # 名前と親フォルダIDを取得
        ).execute()

        original_doc_name = original_file_metadata.get('name')
        original_parent_folders = original_file_metadata.get('parents')

        if not original_doc_name:
            return f"エラー: 元のドキュメントID '{original_doc_id}' の名前を取得できませんでした。"
        
        # 親フォルダIDはリストで返ってくるが、通常ドキュメントは1つのフォルダに属すると想定
        # 複数の親を持つ場合も考慮するなら、どの親に複製を置くか選択するロジックが必要
        parent_folder_id = None
        if original_parent_folders:
            parent_folder_id = original_parent_folders[0] # 最初の親フォルダを採用
        else:
            # 親フォルダ情報がない場合（例: マイドライブ直下）、マイドライブ直下に複製される
            print(f"元のドキュメントID '{original_doc_id}' に親フォルダ情報がありません。マイドライブ直下に複製されます。")

        duplicated_files_output = [] # STEP4の出力用 (名前とURLのペア)
        duplicated_doc_ids = []      # STEP5への引き渡し用 (ドキュメントIDのリスト)

        print(f"ドキュメント '{original_doc_name}' (ID: {original_doc_id}) を {number_of_copies} 回複製します...")

        for i in range(number_of_copies):
            print(f"{i+1}回目の複製処理を開始...")
            copied_file_body = {
                'name': original_doc_name
            }
            if parent_folder_id:
                copied_file_body['parents'] = [parent_folder_id]
            
            copied_file = drive_service.files().copy(
                fileId=original_doc_id,
                body=copied_file_body,
                fields='id, name, webViewLink' # 複製されたファイルのID, 名前, URLを取得
            ).execute()
            
            doc_id = copied_file.get('id')
            doc_name = copied_file.get('name')
            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit" # Docsの編集URL形式
            
            duplicated_files_output.append(doc_name)
            duplicated_files_output.append(doc_url)
            duplicated_doc_ids.append(doc_id) # IDをリストに追加
            print(f"{i+1}回目の複製完了: {doc_name} ({doc_url})")

        if not duplicated_doc_ids: # duplicated_files_outputでも良い
            return "ドキュメントの複製に失敗しました。", [] # STEP5のために空リストも返す
        
        print(f"STEP4 完了: {number_of_copies}個のドキュメントを複製しました。")
        # STEP4の出力文字列と、複製されたドキュメントIDのリストをタプルで返す
        return "\n".join(duplicated_files_output), duplicated_doc_ids

    except HttpError as error:
        print(f"Google Drive APIでエラーが発生しました: {error}")
        return f"Google Drive APIエラー: {error}", []
    except Exception as e:
        print(f"STEP4で予期せぬエラー: {e}")
        return f"STEP4で予期せぬエラー: {e}", []

def step5_write_info_to_documents(document_ids: list, step1_data: str, step2_data: str, step3_data: str):
    """
    STEP5: STEP1〜3で出力した内容を、STEP4で複製した全てのファイルに記入する。
    その後、特定のメッセージを出力する。
    """
    creds = get_credentials()
    if not creds:
        return "エラー: Google Docs APIの認証に失敗しました。"

    if not document_ids:
        return "書き込み対象のドキュメントがありません。"

    try:
        docs_service = build('docs', 'v1', credentials=creds)
        
        content_to_write = f"""【自動追記情報】

--- STEP1: 本日の音声素材関連情報 ---
{step1_data}

--- STEP2: 最新動画素材フォルダ情報 ---
{step2_data}

--- STEP3: 撮影分の台本メール本文 ---
{step3_data}

--- 自動追記終了 ---

"""
        num_docs = len(document_ids)
        print(f"合計 {num_docs} 個のドキュメントに情報を書き込みます...")

        for i, doc_id in enumerate(document_ids):
            print(f"{i+1}/{num_docs} 番目のドキュメント (ID: {doc_id}) に書き込み中...")
            
            # ドキュメントの末尾に追記するためのリクエストを作成
            # まずドキュメントの現在の内容の長さを取得 (あるいは末尾を指定する他の方法)
            # 簡単な方法として、新しい段落を末尾に挿入する。
            # Google Docs APIでは、テキストの挿入は通常、特定のインデックスに対して行う。
            # ドキュメントの末尾に追記するには、まずドキュメントの現在のコンテンツの長さを取得するか、
            # endOfSegmentLocation を利用できる。
            # ここでは、まずドキュメントの末尾を示すための空のセグメントIDを指定するアプローチを試みる。
            # より堅牢なのは、ドキュメントを読み取り、末尾のインデックスを計算すること。
            # しかし、単純な追記であれば、insertTextで末尾を指定できればよい。
            # Google Docs APIのinsertTextは通常、location.indexを指定する。
            # ドキュメントの最後に挿入する場合、ドキュメントの現在の長さを知る必要がある。
            # Document.body.content の末尾の endIndex を使うのが一般的。

            # ドキュメントの現在の内容を取得して末尾のインデックスを特定
            document = docs_service.documents().get(documentId=doc_id, fields='body').execute()
            body_content = document.get('body', {}).get('content', [])
            end_index = 1 # デフォルトはドキュメントの先頭 (1-based index)
            if body_content:
                # ボディの最後の要素のendIndexを取得
                # ただし、タイトルやヘッダーフッターを含まないメインボディの末尾を意図
                # Google Docs APIの構造はネストされることがあるので注意
                # 簡単にするため、最後の構造要素のendIndexを探す
                # Documentのbody.contentはList of StructuralElement
                # StructuralElementはparagraph, table, sectionBreak, tableOfContentsを持つ
                # ここでは最後のStructuralElementのendIndexを単純に取得するが、ドキュメントが空の場合などを考慮
                # もしドキュメントが完全に空なら、最初の位置(1)に挿入される
                last_element = body_content[-1]
                if 'endIndex' in last_element:
                    end_index = last_element['endIndex']
                # もしドキュメントの最後に空行を追加してから書き込みたい場合は、
                # 先に改行を挿入するリクエストを送ることもできる。
                # 今回は取得したend_indexの直前（つまりコンテンツの本当の末尾）に挿入する。
                # insertTextのindexは、そのindexの「前」にテキストを挿入する。
                # なので、end_index -1 が適切。ただし、ドキュメントが空(end_index=1)の場合は1になる。
                # Google Docs APIでは、endOfSegmentLocation を使った方がより簡単で確実かもしれない。
                # requests = [
                #     {
                #         'insertText': {
                #             'location': {
                #                 'index': end_index -1 if end_index > 1 else 1
                #             },
                #             'text': content_to_write
                #         }
                #     }
                # ]
            # endOfSegmentLocation を使用した追記 (推奨)
            requests = [
                {
                    'insertText': {
                        'endOfSegmentLocation': {
                            'segmentId': '' # 空文字列はデフォルトのボディセグメントを示す
                        },
                        'text': content_to_write
                    }
                }
            ]

            # ドキュメントが空でない場合、追記内容の前に2行改行を入れる
            if end_index > 1: # つまりドキュメントに既に何かしらコンテンツがある
                 requests.insert(0, {
                    'insertText': {
                        'endOfSegmentLocation': {
                            'segmentId': ''
                        },
                        'text': '\n\n' # 2行改行
                    }
                })

            docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
            print(f"ドキュメントID: {doc_id} への書き込み完了。")

        final_message = "全てのファイルに情報を記入しました。"
        print(f"STEP5 完了: {final_message}")
        return final_message

    except HttpError as error:
        print(f"Google Docs APIでエラーが発生しました: {error}")
        return f"Google Docs APIエラー: {error}"
    except Exception as e:
        print(f"STEP5で予期せぬエラー: {e}")
        return f"STEP5で予期せぬエラー: {e}"

if __name__ == '__main__':
    # テスト実行
    print("Google Services モジュールのテスト実行開始...")
    
    # 認証テスト
    print("\n--- 認証テスト ---")
    creds_test = get_credentials()
    if creds_test and creds_test.valid:
        print("認証成功！")
    else:
        print("認証失敗。")

    # STEP1 テスト
    if creds_test and creds_test.valid:
        print("\n--- STEP1 テスト ---")
        step1_result = step1_get_audio_material_urls()
        print("\nSTEP1 実行結果:")
        print(step1_result)

        # STEP2 テスト (STEP1が成功した場合のみ実行)
        print("\n--- STEP2 テスト ---")
        step2_result = step2_get_latest_folder_url()
        print("\nSTEP2 実行結果:")
        print(step2_result)

        # STEP3 テスト (STEP1, STEP2が成功 or 認証が成功していれば実行)
        print("\n--- STEP3 テスト ---")
        step3_result = step3_get_script_email_body()
        print("\nSTEP3 実行結果:")
        print(step3_result)

        # STEP4 テスト (認証が成功していれば実行)
        print("\n--- STEP4 テスト (2部複製) ---")
        number_to_copy_test = 2 
        step4_output_str, duplicated_ids_for_step5 = step4_duplicate_document(number_to_copy_test)
        print("\nSTEP4 実行結果 (出力文字列):")
        print(step4_output_str)
        print("\nSTEP4 実行結果 (複製されたドキュメントIDリスト):")
        print(duplicated_ids_for_step5)

        # STEP5 テスト (STEP4が成功し、複製IDリストが取得できた場合)
        if duplicated_ids_for_step5:
            print("\n--- STEP5 テスト ---")
            # STEP1,2,3のテスト結果をSTEP5に渡す (実際はエラーでない場合のみ)
            # ここではテストなので、エラー文字列でないことを簡易的に確認
            s1_data = step1_result if "エラー" not in str(step1_result) else "(STEP1データなし)"
            s2_data = step2_result if "エラー" not in str(step2_result) else "(STEP2データなし)"
            s3_data = step3_result if "エラー" not in str(step3_result) else "(STEP3データなし)"
            
            step5_result = step5_write_info_to_documents(duplicated_ids_for_step5, s1_data, s2_data, s3_data)
            print("\nSTEP5 実行結果:")
            print(step5_result)
        else:
            print("\nSTEP5 テストスキップ (STEP4で複製IDが取得できなかったため)")

    else:
        print("\nSTEP1 テストスキップ (認証失敗のため)")
        print("STEP2 テストスキップ (認証失敗のため)")
        print("STEP3 テストスキップ (認証失敗のため)")
        print("STEP4 テストスキップ (認証失敗のため)")

    print("\nGoogle Services モジュールのテスト実行終了。") 