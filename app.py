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

# 폴더 버튼들을 좀 더 글씨(링크)처럼 보이게 하고 여백을 줄이는 CSS
st.markdown("""
    <style>
    .stButton>button { text-align: left; width: 100%; border: none; background-color: transparent; box-shadow: none; padding-left: 0; }
    .stButton>button:hover { background-color: #f0f2f6; color: #ff4b4b; }
    .stButton>button:focus { background-color: #ffeaea; color: #ff4b4b; border: none; box-shadow: none;}
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

# --- 폴더 & 파일 제어 함수 (캐싱 적용으로 속도 향상) ---
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
    col_left, col_center, col_right = st.columns([1.2, 2.0, 1.2], gap="large")

    # ---------------------------------------------------------
    # ⬅️ [왼쪽] 폴더 체계 생성 & 윈도우 스타일 파일 트리
    # ---------------------------------------------------------
    with col_left:
        # 1. 새 폴더(체계) 만들기
        with st.expander("🆕 새 폴더 만들기 (펼치기/접기)", expanded=True):
            year = st.selectbox("연도", ["2025", "2026", "2027"], index=1)
            grade = st.selectbox("학년", ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"], index=4)
            subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어", "창체", "기타"])
            unit = st.text_input("단원", placeholder="예: 3단원 우리 이웃")
            period = st.text_input("차시", placeholder="예: 2차시") # 차시 부활!
            
            if st.button("➕ 이 체계로 폴더 생성"):
                with st.spinner("폴더 생성 중..."):
                    f1 = get_or_create_folder(service, f"{year}학년도", TARGET_FOLDER_ID)
                    f2 = get_or_create_folder(service, grade, f1)
                    f3 = get_or_create_folder(service, subject, f2)
                    if unit: f4 = get_or_create_folder(service, unit, f3)
                    if unit and period: get_or_create_folder(service, period, f4)
                    
                    get_folders_in_parent.clear() # 캐시 초기화
                    st.success("생성 완료!")
                    st.rerun()

        st.write("")
        
        # 2. 윈도우 탐색기(이글) 스타일 트리 구조
        st.subheader("🌳 내 서랍장")
        st.info("💡 글자를 누르면 선택과 동시에 폴더가 열립니다.")
        
        # 최상위 폴더 홈 버튼
        if st.button("🏠 최상위 (5학년 자료실)", key="btn_root"):
            st.session_state.current_folder_id = TARGET_FOLDER_ID
            st.session_state.current_folder_name = "최상위 폴더"
            st.rerun()
            
        st.write("---")

        def render_tree(parent_id, depth=0):
            folders = get_folders_in_parent(service, parent_id)
            for folder in folders:
                indent = "　" * depth # 들여쓰기
                is_expanded = folder['id'] in st.session_state.expanded_folders
                is_selected = (st.session_state.current_folder_id == folder['id'])
                
                # 아이콘과 강조 표시
                icon = "📂" if is_expanded else "📁"
                marker = "📍 " if is_selected else ""
                font_weight = "**" if is_selected else ""
                
                label = f"{indent}{marker}{icon} {font_weight}{folder['name']}{font_weight}"
                
                # 버튼(글자)을 누르면 -> 선택됨과 동시에 하위 폴더 열림(Toggle)
                if st.button(label, key=f"tree_{folder['id']}"):
                    st.session_state.current_folder_id = folder['id']
                    st.session_state.current_folder_name = folder['name']
                    
                    if is_expanded:
                        st.session_state.expanded_folders.remove(folder['id']) # 닫기
                    else:
                        st.session_state.expanded_folders.add(folder['id']) # 열기
                    st.rerun()
                
                if is_expanded:
                    render_tree(folder['id'], depth + 1)
        
        # 트리 그리기 시작
        with st.container(height=500):
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

        # 미리보기 아이프레임
        if 'preview_url' in st.session_state:
            st.write("---")
            st.write("**👀 미리보기 창 (웹 문서 전용)**")
            try:
                st.components.v1.iframe(st.session_state.preview_url, height=500, scrolling=True)
            except:
                st.warning("이 파일 형식은 보안상 구글 드라이브에서 직접 열어야 합니다. 위의 링크를 클릭하세요.")

    # ---------------------------------------------------------
    # ➡️ [오른쪽] 입력 폼 (업로드 / 주소 붙여넣기 / 메모 / 저장)
    # ---------------------------------------------------------
    with col_right:
        st.subheader(f"💾 [{st.session_state.current_folder_name}]에 자료 넣기")
        
        with st.container(border=True):
            # 주소 넣기 (Ctrl+V)
            passed_url = st.query_params.get("url", "")
            url_input = st.text_input("🔗 참고 주소 (Ctrl+V로 붙여넣기)", value=passed_url)
            
            # 파일 넣기 (드래그앤드롭)
            up_files = st.file_uploader("📂 파일 끌어다 놓기 (Drag & Drop)", accept_multiple_files=True)
            
            # 수업 메모
            memo = st.text_area("📝 수업 메모", height=120)
            
        st.write("")
        
        if st.button("🚀 선택한 폴더에 최종 전송", type="primary", use_container_width=True):
            if not up_files and not url_input and not memo:
                st.warning("업로드할 자료나 링크를 입력해 주세요.")
            else:
                with st.spinner(f"[{st.session_state.current_folder_name}] 폴더에 저장 중..."):
                    try:
                        if up_files:
                            for f in up_files:
                                upload_to_drive(service, st.session_state.current_folder_id, f.name, f.getvalue())
                        if url_input or memo:
                            note_text = f"🔗 링크: {url_input}\n\n📝 메모:\n{memo}"
                            upload_to_drive(service, st.session_state.current_folder_id, "학습자료_및_메모.txt", note_text.encode('utf-8'))
                        
                        st.success("✨ 업로드 완료!")
                        st.rerun() # 화면 새로고침해서 가운데 창에 바로 뜨게 함
                    except Exception as e:
                        st.error(f"오류: {e}")
