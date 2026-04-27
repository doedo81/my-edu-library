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

st.markdown("""
    <style>
    .stButton>button { 
        text-align: left !important; 
        width: 100% !important; 
        border: none !important; 
        background-color: transparent !important; 
        box-shadow: none !important; 
        padding: 2px 0px !important; 
        color: inherit !important;
    }
    .stButton>button:hover { 
        color: #ff4b4b !important; 
        background-color: transparent !important;
    }
    .stButton>button:focus:not(:active) { 
        border: none !important; 
        box-shadow: none !important; 
        background-color: transparent !important;
        color: #ff4b4b !important;
    }
    [data-testid="stExpander"] { border: 1px solid #444; border-radius: 5px; margin-bottom: 10px; }
    [data-testid="stVerticalBlock"] > div { padding-bottom: 0px; }
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
    col_left, col_center, col_right = st.columns([1.3, 2.0, 1.2], gap="large")

    # ---------------------------------------------------------
    # ⬅️ [왼쪽] 새 폴더 생성 & 파일 트리
    # ---------------------------------------------------------
    with col_left:
        with st.expander("🆕 새 폴더 만들기", expanded=False):
            row1_col1, row1_col2 = st.columns(2)
            with row1_col1: year = st.selectbox("연도", ["2025", "2026", "2027"], index=1)
            with row1_col2: grade = st.selectbox("학년", ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"], index=4)
            
            row2_col1, row2_col2 = st.columns(2)
            with row2_col1: subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어", "창체", "기타"])
            with row2_col2: unit = st.text_input("단원", placeholder="예: 3단원")
            
            row3_col1, row3_col2 = st.columns(2)
            with row3_col1: period = st.text_input("차시", placeholder="예: 2차시")
            with row3_col2: st.write(""); st.write("") 
            
            if st.button("➕ 폴더 생성"):
                with st.spinner("생성 중..."):
                    f1 = get_or_create_folder(service, f"{year}학년도", TARGET_FOLDER_ID)
                    f2 = get_or_create_folder(service, grade, f1)
                    f3 = get_or_create_folder(service, subject, f2)
                    target_id, target_name = f3, subject
                    
                    if unit: 
                        f4 = get_or_create_folder(service, unit, f3)
                        target_id, target_name = f4, unit
                    if unit and period: 
                        f5 = get_or_create_folder(service, period, f4)
                        target_id, target_name = f5, period
                    
                    st.session_state.current_folder_id = target_id
                    st.session_state.current_folder_name = target_name
                    
                    st.session_state.expanded_folders.update([TARGET_FOLDER_ID, f1, f2, f3])
                    if unit: st.session_state.expanded_folders.add(f4)
                    if unit and period: st.session_state.expanded_folders.add(f5)
                    
                    get_folders_in_parent.clear()
                    st.rerun()

        def render_tree(parent_id, depth=0):
            folders = get_folders_in_parent(service, parent_id)
            for folder in folders:
                indent = "&nbsp;" * (depth * 5) 
                is_expanded = folder['id'] in st.session_state.expanded_folders
                is_selected = (st.session_state.current_folder_id == folder['id'])
                
                # [+] 와 [-] 기호 적용
                pm_icon = "➖" if is_expanded else "➕"
                folder_icon = "📂" if is_expanded else "📁"
                marker = "📍" if is_selected else ""
                
                if is_selected:
                    label = f"{indent}{pm_icon} {folder_icon} **{folder['name']}** {marker}"
                else:
                    label = f"{indent}{pm_icon} {folder_icon} {folder['name']}"
                
                if st.button(label, key=f"tree_{folder['id']}"):
                    st.session_state.current_folder_id = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    if is_expanded: st.session_state.expanded_folders.remove(folder['id'])
                    else: st.session_state.expanded_folders.add(folder['id'])
                    st.rerun()
                
                if is_expanded:
                    render_tree(folder['id'], depth + 1)

        with st.expander("🌳 폴더 탐색기", expanded=True):
            # border=False 로 설정하여 빨간 윤곽선 상자를 완전히 제거함!
            with st.container(height=500, border=False):
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
                c_name, c_btn = st.columns([4, 1.2])
                c_name.markdown(f"- [{f['name']}]({f['webViewLink']})")
                if c_btn.button("미리보기", key=f"prev_{f['id']}"):
                    st.session_state.preview_url = f['webViewLink']

        if 'preview_url' in st.session_state:
            st.write("---")
            st.write("**👀 미리보기 창**")
            st.components.v1.iframe(st.session_state.preview_url, height=500, scrolling=True)

    # ---------------------------------------------------------
    # ➡️ [오른쪽] 입력 폼 (업로드 / 주소 / 메모)
    # ---------------------------------------------------------
    with col_right:
        st.subheader(f"💾 업로드 및 메모")
        
        # 윤곽선 없앰 (깔끔한 이글 스타일)
        with st.container(border=False):
            passed_url = st.query_params.get("url", "")
            url_input = st.text_input("🔗 참고 주소 (Ctrl+V)", value=passed_url)
            up_files = st.file_uploader("📂 파일 끌어다 놓기", accept_multiple_files=True)
            memo = st.text_area("📝 수업 메모", height=150)
            
        st.write("")
        
        if st.button("🚀 현재 폴더에 전송하기", type="primary", use_container_width=True):
            if not up_files and not url_input and not memo:
                st.warning("자료나 링크를 넣어주세요.")
            else:
                with st.spinner("저장 중..."):
                    try:
                        if up_files:
                            for f in up_files:
                                upload_to_drive(service, st.session_state.current_folder_id, f.name, f.getvalue())
                        if url_input or memo:
                            note_text = f"🔗 링크: {url_input}\n\n📝 메모:\n{memo}"
                            upload_to_drive(service, st.session_state.current_folder_id, "학습자료_및_메모.txt", note_text.encode('utf-8'))
                        st.success("✨ 완료!")
                        st.rerun() 
                    except Exception as e:
                        st.error(f"오류: {e}")
