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

def get_or_create_folder(service, folder_name, parent_id):
    if not folder_name: return parent_id
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    if items: return items[0]['id']
    else:
        folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

# 캐시를 사용해서 폴더 목록을 빠르게 불러옵니다.
@st.cache_data(ttl=300)
def get_all_folders_cached(_service, parent_id, path=""):
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = _service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    path_list = []
    for f in folders:
        current_path = f"{path} > {f['name']}" if path else f['name']
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

# ==========================================
# --- 웹 화면 그리기 ---
# ==========================================
st.set_page_config(page_title="나만의 교육 자료실", page_icon="📚", layout="wide")
st.title("나만의 전용 교육 자료실 ☁️")

passed_url = st.query_params.get("url", "")
if passed_url:
    st.success("💡 크롬 앱에서 링크를 가져왔습니다!")

tab1, tab2 = st.tabs(["📤 자료 올리기 (업로드)", "🌳 내 자료 트리 보기 (갤러리)"])

with tab1:
    mode = st.radio("폴더 지정 방식 선택", ["🆕 신규 폴더 생성 (연도/과목 직접 입력)", "🔍 기존 폴더 찾아넣기 (드라이브 검색)"], horizontal=True)
    st.divider()

    service = get_drive_service()
    final_folder_id = None

    if mode == "🆕 신규 폴더 생성 (연도/과목 직접 입력)":
        c1, c2, c3 = st.columns(3)
        with c1: year = st.selectbox("연도", ["2025", "2026", "2027"], index=1)
        with c2: grade = st.selectbox("학년", ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"], index=4)
        with c3: semester = st.selectbox("학기", ["1학기", "2학기", "여름방학", "겨울방학"])

        c4, c5, c6 = st.columns(3)
        with c4: subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어", "음악", "미술", "체육", "실과", "도덕", "창체", "기타"])
        with c5: unit = st.text_input("단원", placeholder="예: 3단원 우리 이웃")
        with c6: period = st.text_input("차시", placeholder="예: 2차시")
    else:
        with st.spinner("구글 드라이브에서 폴더 목록을 쫙 불러오는 중입니다... 🔍"):
            if service:
                all_folders = get_all_folders_cached(service, TARGET_FOLDER_ID)
                folder_options = {f['name']: f['id'] for f in all_folders}
                if folder_options:
                    selected_path = st.selectbox("저장할 폴더를 선택하세요", list(folder_options.keys()))
                    final_folder_id = folder_options[selected_path] if selected_path else None
                    st.info(f"📂 선택된 경로: {selected_path}")
                else:
                    st.warning("아직 드라이브에 만들어진 폴더가 없습니다. 신규 폴더 생성 모드를 먼저 이용해 주세요!")

    st.write("---")
    uploaded_files = st.file_uploader("📂 수업 파일 업로드 (드래그 앤 드롭!)", accept_multiple_files=True)
    link_url = st.text_area("🔗 참고 링크", value=passed_url, height=70)
    memo = st.text_area("📝 수업 메모", height=70)

    if st.button("🚀 구글 드라이브에 완벽하게 정리하기", type="primary", use_container_width=True):
        if not uploaded_files and not link_url and not memo:
            st.warning("저장할 내용을 입력해 주세요!")
        elif mode == "🆕 신규 폴더 생성 (연도/과목 직접 입력)" and not unit:
            st.warning("단원명을 최소한 입력해 주세요!")
        else:
            with st.spinner('드라이브에 자료를 쏙쏙 넣는 중... 🚀'):
                if service:
                    try:
                        if mode == "🆕 신규 폴더 생성 (연도/과목 직접 입력)":
                            f1 = get_or_create_folder(service, f"{year}학년도", TARGET_FOLDER_ID)
                            f2 = get_or_create_folder(service, grade, f1)
                            f3 = get_or_create_folder(service, semester, f2)
                            f4 = get_or_create_folder(service, subject, f3)
                            f5 = get_or_create_folder(service, unit, f4)
                            final_folder_id = get_or_create_folder(service, period, f5)
                        
                        if final_folder_id:
                            if uploaded_files:
                                for file in uploaded_files:
                                    upload_to_drive(service, final_folder_id, file.name, file.getvalue())
                            if link_url or memo:
                                content = f"🔗 참고 링크:\n{link_url}\n\n📝 수업 메모:\n{memo}"
                                upload_to_drive(service, final_folder_id, "참고링크_및_메모.txt", content.encode('utf-8'))
                            
                            # 새로 저장했으니 캐시를 비워줍니다.
                            get_all_folders_cached.clear()
                            st.success("✨ 저장 완료! 웹앱에서 드라이브로 성공적으로 전송되었습니다.")
                    except Exception as e:
                        st.error(f"저장 오류 발생: {e}")

with tab2:
    st.subheader("📂 내 교육 자료 보관함 (Tree View)")
    if st.button("🔄 드라이브 구조 새로고침", help="최신 폴더 구조를 다시 불러옵니다."):
        get_all_folders_cached.clear()
        st.rerun()

    def display_tree(service, parent_id, depth=0):
        items = list_files_in_folder(service, parent_id)
        for item in items:
            indent = "&nbsp;" * (depth * 8)
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                with st.expander(f"{'　' * depth} 📁 **{item['name']}**"):
                    display_tree(service, item['id'], depth + 1)
            else:
                st.markdown(f"{indent} 📄 [{item['name']}]({item['webViewLink']})")

    if service:
        with st.spinner("드라이브 트리를 구성하는 중입니다... 🌳"):
            display_tree(service, TARGET_FOLDER_ID)
