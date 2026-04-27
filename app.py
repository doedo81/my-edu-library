import streamlit as st
import io
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# =====================================================================
# 설정
# =====================================================================
TARGET_FOLDER_ID = "1cVO7Crr0D8l95_m4rlpWNg85PQSy5pad"
SCOPES = ['https://www.googleapis.com/auth/drive']

st.set_page_config(page_title="나만의 교육 자료실", page_icon="📚", layout="wide")

def get_drive_service():
    try:
        token_info = json.loads(st.secrets["GOOGLE_TOKEN"])
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"구글 인증 실패: {e}")
        return None

# 드라이브 폴더 목록 캐싱 (속도 향상)
@st.cache_data(ttl=300)
def get_all_folders_cached(_service, parent_id, path=""):
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = _service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    path_list = [{"name": "🏠 최상위 폴더 (5학년 자료실)", "id": TARGET_FOLDER_ID}] if not path else []
    
    for f in folders:
        current_path = f"{path} 📂 {f['name']}" if path else f"📂 {f['name']}"
        path_list.append({"name": current_path, "id": f['id']})
        path_list.extend(get_all_folders_cached(_service, f['id'], current_path))
    return path_list

def upload_to_drive(service, folder_id, file_name, file_content):
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream', resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def list_files_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, mimeType, webViewLink)").execute()
    return results.get('files', [])

def create_new_folder(service, folder_name, parent_id):
    folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')

# ==========================================
# --- 🦅 진짜 이글(Eagle) 스타일 화면 구성 ---
# ==========================================

st.title("📚 나만의 전용 교육 자료실")
passed_url = st.query_params.get("url", "")
st.divider()

service = get_drive_service()

if service:
    # 3단 분할
    col_left, col_center, col_right = st.columns([1.5, 2.5, 1], gap="large")

    # ---------------------------------------------------------
    # ⬅️ [왼쪽 창] 내 서랍장 (폴더 선택기)
    # ---------------------------------------------------------
    with col_left:
        st.subheader("🌳 내 서랍장")
        st.info("👇 아래에서 작업할 폴더를 클릭하세요!")
        
        # 1. 폴더 목록 가져오기
        all_folders = get_all_folders_cached(service, TARGET_FOLDER_ID)
        folder_options = {f['name']: f['id'] for f in all_folders}
        
        # 2. 폴더를 클릭하는 UI (라디오 버튼을 활용해 클릭 즉시 가운데 창이 바뀌게 함)
        selected_path = st.radio("목록", list(folder_options.keys()), label_visibility="collapsed")
        current_folder_id = folder_options[selected_path]
        current_folder_name = selected_path.split('📂')[-1].strip() if '📂' in selected_path else "최상위 폴더"

        st.write("---")
        # (+) 새 하위 폴더 만들기 버튼
        new_folder_name = st.text_input(f"'{current_folder_name}' 안에 새 폴더 만들기", placeholder="새 폴더 이름 입력")
        if st.button("➕ 폴더 생성", use_container_width=True):
            if new_folder_name:
                with st.spinner("폴더 생성 중..."):
                    create_new_folder(service, new_folder_name, current_folder_id)
                    get_all_folders_cached.clear() # 캐시 초기화
                    st.rerun() # 화면 새로고침

    # ---------------------------------------------------------
    # ⏺️ [가운데 창] 선택된 폴더 내용 보기 & 업로드
    # ---------------------------------------------------------
    with col_center:
        st.subheader(f"📂 [{current_folder_name}] 폴더")
        
        with st.container(border=True):
            # 1. 현재 폴더 안의 파일들 보여주기
            files_in_current = list_files_in_folder(service, current_folder_id)
            if not files_in_current:
                st.write("텅~ 비어있습니다. 자료를 채워주세요!")
            else:
                for item in files_in_current:
                    if item['mimeType'] != 'application/vnd.google-apps.folder': # 폴더 제외하고 파일만
                        st.markdown(f"📄 [{item['name']}]({item['webViewLink']})")
        
        st.write("---")
        # 2. 직관적인 드래그 앤 드롭 업로드 창 (이곳에 놓으면 현재 폴더로 직행!)
        st.markdown(f"**📥 이 폴더('{current_folder_name}')에 자료 넣기**")
        uploaded_files = st.file_uploader("파일을 여기로 끌어다 놓으세요 (Drag & Drop)", accept_multiple_files=True, label_visibility="collapsed")

    # ---------------------------------------------------------
    # ➡️ [오른쪽 창] 참고 링크 및 메모 + 최종 저장 버튼
    # ---------------------------------------------------------
    with col_right:
        st.subheader("📝 설명 추가")
        
        link_url = st.text_area("🔗 참고 링크", value=passed_url, height=100)
        memo = st.text_area("📝 수업 메모", height=100)
        
        st.write("") 
        
        # 저장 버튼
        if st.button("🚀 이곳에 최종 저장하기", type="primary", use_container_width=True):
            if not uploaded_files and not link_url and not memo:
                st.warning("업로드할 자료나 메모를 입력해 주세요.")
            else:
                with st.spinner(f"'{current_folder_name}' 폴더에 저장 중... 🚀"):
                    try:
                        # 파일 업로드
                        if uploaded_files:
                            for file in uploaded_files:
                                upload_to_drive(service, current_folder_id, file.name, file.getvalue())
                        
                        # 링크/메모 업로드 (텍스트 파일로)
                        if link_url or memo:
                            content = f"🔗 링크:\n{link_url}\n\n📝 메모:\n{memo}"
                            upload_to_drive(service, current_folder_id, "참고링크_및_메모.txt", content.encode('utf-8'))
                        
                        st.success("✨ 저장 완료!")
                        st.rerun() # 화면 새로고침해서 방금 올린 파일이 가운데 창에 바로 뜨게 함
                    except Exception as e:
                        st.error(f"오류: {e}")
