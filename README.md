# Step3-1　宿題パッケージstarterのサンプルアプリです

## クローン
git clone https://github.com/techzerocs/LinkFastAPINext_starter.git


## backend
cd backend

python3 -m venv backend_env (backend_env という名前の仮想環境を作成)

./backend_env/Script/activate.ps1 (powershell の場合)

source backend_env/bin/activate (macOS/Linux の場合)

pip install -r requirements.txt

uvicorn app:app --reload

## frontend

cd frontend

npm install

npm run dev

## 立ち上げ
http://localhost:3000/ にアクセス
