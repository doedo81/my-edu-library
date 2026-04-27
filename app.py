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

# 화면을 가장 넓게 씁니다 (이글 스타일 필수 설정)
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
# --- 🦅 이글(Eagle) 스타일 웹 화면 그리기 ---
# ==========================================

# 1. 헤더 (상단 제목)
st.title("📚 나만의 전용 교육 자료실")
passed_url = st.query_params.get("url", "")
if passed_url:
    st.success("💡 크롬 확장 프로그램에서 링크를 성공적으로 가져왔습니다!")
st.divider()

service = get_drive_service()

# 2. 🌟 대망의 3단 분할 레이아웃 (비율 = 좌 1 : 중 2 : 우 1)
col_left, col_center, col_right = st.columns([1.2, 2, 1.2], gap="large")

# ---------------------------------------------------------
# ⬅️ [왼쪽 창] 파일 트리 뷰어 (탐색기)
# ---------------------------------------------------------
with col_left:
    st.subheader("🌳 내 서랍장 (Tree)")
    if st.button("🔄 새로고침", use_container_width=True):
        get_all_folders_cached.clear()
        st.rerun()
    
    st.write("---")
    def display_tree(service, parent_id, depth=0):
        items = list_files_in_folder(service, parent_id)
        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                # st.expander가 이글의 '+' 버튼 역할을 합니다.
                with st.expander(f"📁 {item['name']}", expanded=False):
                    display_tree(service, item['id'], depth + 1)
            else:
                # 파일은 클릭하면 열리도록 링크 처리
                st.markdown(f"&nbsp;&nbsp; 📄 [{item['name']}]({item['webViewLink']})")

    if service:
        with st.spinner("트리 로딩 중..."):
            display_tree(service, TARGET_FOLDER_ID)

# ---------------------------------------------------------
# ⏺️ [가운데 창] 작업 및 업로드 공간
# ---------------------------------------------------------
with col_center:
    st.subheader("📤 자료 올리기")
    mode = st.radio("저장 위치 선택 방식", ["🔍 기존 폴더 검색해서 넣기", "🆕 새 폴더 직접 만들기 (연도/과목)"], horizontal=True)
    
    final_folder_id = None
    
    # 위치 지정 UI
    with st.container(border=True):
        if mode == "🆕 새 폴더 직접 만들기 (연도/과목)":
            c1, c2, c3 = st.columns(3)
            with c1: year = st.selectbox("연도", ["2025", "2026", "2027"], index=1)
            with c2: grade = st.selectbox("학년", ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"], index=4)
            with c3: semester = st.selectbox("학기", ["1학기", "2학기", "여름방학", "겨울방학"])

            c4, c5, c6 = st.columns(3)
            with c4: subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어", "창체", "기타"])
            with c5: unit = st.text_input("단원", placeholder="예: 3단원 우리 이웃")
            with c6: period = st.text_input("차시", placeholder="예: 2차시")
        else:
            if service:
                all_folders = get_all_folders_cached(service, TARGET_FOLDER_ID)
                folder_options = {f['name']: f['id'] for f in all_folders}
                if folder_options:
                    selected_path = st.selectbox("어느 폴더에 저장할까요?", list(folder_options.keys()))
                    final_folder_id = folder_options[selected_path] if selected_path else None
                    st.info(f"선택됨: {selected_path}")
                else:
                    st.warning("먼저 새 폴더를 만들어주세요.")

    # 파일 업로드 (가장 넓게 사용)
    uploaded_files = st.file_uploader("📂 이 곳에 수업 파일을 끌어다 놓으세요 (Drag & Drop)", accept_multiple_files=True)

# ---------------------------------------------------------
# ➡️ [오른쪽 창] 참고 링크 및 메모 (메타데이터) + 저장 버튼
# ---------------------------------------------------------
with col_right:
    st.subheader("📝 세부 정보 입력")
    
    with st.container(border=True):
        link_url = st.text_area("🔗 참고 링크 (URL)", value=passed_url, height=120, placeholder="유튜브, 인디스쿨 주소 등")
        memo = st.text_area("📝 수업 메모", height=150, placeholder="이 자료의 활용 꿀팁, 주의사항 등을 적어주세요.")
    
    st.write("") # 빈 칸 띄우기
    
    if st.button("🚀 드라이브에 저장하기", type="primary", use_container_width=True):
        if not uploaded_files and not link_url and not memo:
            st.warning("업로드할 파일이나 링크를 입력해 주세요.")
        elif mode == "🆕 새 폴더 직접 만들기 (연도/과목)" and not unit:
            st.warning("새 폴더를 만들려면 단원명을 입력해 주세요.")
        else:
            with st.spinner('구글 드라이브로 전송 중... 🚀'):
                if service:
                    try:
                        if mode == "🆕 새 폴더 직접 만들기 (연도/과목)":
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
                                content = f"🔗 링크:\n{link_url}\n\n📝 메모:\n{memo}"
                                upload_to_drive(service, final_folder_id, "참고링크_및_메모.txt", content.encode('utf-8'))
                            
                            get_all_folders_cached.clear()
                            st.success("✨ 저장 완료! 왼쪽 트리를 새로고침 해보세요.")
                    except Exception as e:
                        st.error(f"오류: {e}")
