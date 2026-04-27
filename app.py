import streamlit as st
import io
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# =====================================================================
# 설정 및 인증
# =====================================================================
TARGET_FOLDER_ID = "1cVO7Crr0D8l95_m4rlpWNg85PQSy5pad"
SCOPES = ['https://www.googleapis.com/auth/drive']

st.set_page_config(page_title="나만의 교육 자료실", page_icon="📚", layout="wide")

# 폴더 버튼들을 탐색기처럼 깔끔하게 보이게 하는 디자인 설정
st.markdown("""
    <style>
    .stButton>button { text-align: left; width: 100%; border: none; background-color: transparent; box-shadow: none; padding-left: 0; padding-top: 2px; padding-bottom: 2px; }
    .stButton>button:hover { background-color: #f0f2f6; color: #ff4b4b; }
    .stButton>button:focus { background-color: #ffeaea; color: #ff4b4b; border: none; box-shadow: none;}
    [data-testid="stExpander"] { border: 1px solid #e6e6e6; border-radius: 5px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

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

# --- 폴더 & 파일 제어 함수 ---
@st.cache_data(ttl=300)
def get_folders_in_parent(_service, parent_id):
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = _service.files().list(q=query, fields="files(id, name)").execute()
    return sorted(results.get('files', []), key=lambda x: x['name'])

def get_or_create_folder(service, folder_name, parent_id):
    query = f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    if items: return items[0]['id']
    else:
        folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def list_files_only(service, folder_id):
    query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, mimeType, webViewLink)").execute()
    return results.get('files', [])

def upload_to_drive(service, folder_id, file_name, file_content):
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream', resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# --- 상태 저장소 초기화 ---
if 'expanded_folders' not in st.session_state:
    st.session_state.expanded_folders = {TARGET_FOLDER_ID}
if 'current_folder_id' not in st.session_state:
    st.session_state.current_folder_id = TARGET_FOLDER_ID
if 'current_folder_name' not in st.session_state:
    st.session_state.current_folder_name = "최상위 폴더"

# ==========================================
# --- 🖥️ 메인 화면 구성 ---
# ==========================================
st.title("📚 나만의 전용 교육 자료실")
st.write("---")

service = get_drive_service()

if service:
    # 3단 분할 레이아웃
    col_left, col_center, col_right = st.columns([1.2, 2.0, 1.2], gap="large")

    # ---------------------------------------------------------
    # ⬅️ [왼쪽] 폴더 체계 생성 & 파일 트리 (깔끔하게 정리됨)
    # ---------------------------------------------------------
    with col_left:
        # 1. 새 폴더 만들기 (접었다 펴기)
        with st.expander("🆕 새 폴더 만들기", expanded=False): # 공간 확보를 위해 기본은 접어둠
            year = st.selectbox("연도", ["2025", "2026", "2027"], index=1)
            grade = st.selectbox("학년", ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"], index=4)
            subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어", "창체", "기타"])
            unit = st.text_input("단원", placeholder="예: 3단원 우리 이웃")
            period = st.text_input("차시", placeholder="예: 2차시")
            
            if st.button("➕ 이 체계로 폴더 생성"):
                with st.spinner("폴더 생성 중..."):
                    f1 = get_or_create_folder(service, f"{year}학년도", TARGET_FOLDER_ID)
                    f2 = get_or_create_folder(service, grade, f1)
                    f3 = get_or_create_folder(service, subject, f2)
                    if unit: f4 = get_or_create_folder(service, unit, f3)
                    if unit and period: get_or_create_folder(service, period, f4)
                    
                    get_folders_in_parent.clear()
                    st.success("생성 완료!")
                    st.rerun()

        # 2. 폴더 탐색 트리 (안내문구 및 최상위 버튼 제거, 접기 기능 추가)
        def render_tree(parent_id, depth=0):
            folders = get_folders_in_parent(service, parent_id)
            for folder in folders:
                indent = "　" * depth 
                is_expanded = folder['id'] in st.session_state.expanded_folders
                is_selected = (st.session_state.current_folder_id == folder['id'])
                
                icon = "📂" if is_expanded else "📁"
                marker = "📍 " if is_selected else ""
                font_weight = "**" if is_selected else ""
                
                label = f"{indent}{marker}{icon} {font_weight}{folder['name']}{font_weight}"
                
                if st.button(label, key=f"tree_{folder['id']}"):
                    st.session_state.current_folder_id = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    
                    if is_expanded:
                        st.session_state.expanded_folders.remove(folder['id'])
                    else:
                        st.session_state.expanded_folders.add(folder['id'])
                    st.rerun()
                
                if is_expanded:
                    render_tree(folder['id'], depth + 1)

        with st.expander("🌳 폴더 탐색기", expanded=True):
            # 높이를 450으로 제한하여 한 화면에 깔끔하게 들어오도록 설정
            with st.container(height=450):
                render_tree(TARGET_FOLDER_ID)

    # ---------------------------------------------------------
    # ⏺️ [가운데] 현재 폴더 내용 및 미리보기 전용 창
    # ---------------------------------------------------------
    with col_center:
        st.subheader(f"📍 현재 위치: [{st.session_state.current_folder_name}]")
        st.write("---")
        
        files = list_files_only(service, st.session_state.current_folder_id)
        
        if not files:
            st.info("이 폴더는 비어있습니다. 오른쪽에서 자료를 추가해 보세요.")
        else:
            st.write("**📄 폴더 내 자료 목록**")
            for f in files:
                col_name, col_btn = st.columns([4, 1])
                col_name.markdown(f"- [{f['name']}]({f['webViewLink']})")
                if col_btn.button("미리보기", key=f"prev_{f['id']}"):
                    st.session_state.preview_url = f['webViewLink']

        if 'preview_url' in st.session_state:
            st.write("---")
            st.write("**👀 미리보기 창**")
            try:
                st.components.v1.iframe(st.session_state.preview_url, height=450, scrolling=True)
            except:
                st.warning("이 파일 형식은 보안상 직접 열어야 합니다. 위 링크를 클릭하세요.")

    # ---------------------------------------------------------
    # ➡️ [오른쪽] 입력 폼 (업로드 / 주소 붙여넣기 / 메모 / 저장)
    # ---------------------------------------------------------
    with col_right:
        st.subheader(f"💾 업로드 및 메모")
        
        with st.container(border=True):
            passed_
