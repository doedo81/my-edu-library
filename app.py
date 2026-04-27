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

# CSS로 화면 레이아웃 미세 조정 (가운데 창 강조)
st.markdown("""
    <style>
    [data-testid="stExpander"] { border: 1px solid #f0f2f6; border-radius: 5px; margin-bottom: 5px; }
    .stButton>button { width: 100%; }
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

# 폴더/파일 관리 함수들
def get_or_create_folder(service, folder_name, parent_id):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    if items: return items[0]['id']
    else:
        folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def list_items(service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, mimeType, webViewLink, thumbnailLink)").execute()
    return results.get('files', [])

def upload_to_drive(service, folder_id, file_name, file_content):
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream', resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# ==========================================
# --- 메인 화면 구성 ---
# ==========================================
st.title("📚 나만의 전용 교육 자료실")
st.write("---")

service = get_drive_service()

if service:
    # 3단 분할 레이아웃
    col_left, col_center, col_right = st.columns([1.2, 2, 1.2], gap="medium")

    # ---------------------------------------------------------
    # ⬅️ [왼쪽 창] 위: 폴더 생성 / 아래: 트리 구조
    # ---------------------------------------------------------
    with col_left:
        # (위) 폴더 생성기
        with st.container(border=True):
            st.subheader("🆕 새 폴더 만들기")
            year = st.selectbox("연도", ["2025", "2026", "2027"], index=1)
            grade = st.selectbox("학년", ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"], index=4)
            subject = st.selectbox("과목", ["국어", "수학", "사회", "과학", "영어", "창체", "기타"])
            unit = st.text_input("단원명", placeholder="예: 3단원 우리 이웃")
            if st.button("➕ 폴더 체계 생성"):
                f1 = get_or_create_folder(service, f"{year}학년도", TARGET_FOLDER_ID)
                f2 = get_or_create_folder(service, grade, f1)
                f3 = get_or_create_folder(service, subject, f2)
                get_or_create_folder(service, unit, f3)
                st.success("폴더가 생성되었습니다!")
                st.rerun()

        st.write("")
        
        # (아래) 파일 트리 탐색
        st.subheader("🌳 자료실 탐색")
        def render_tree(parent_id, depth=0):
            items = list_items(service, parent_id)
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    with st.expander(f"{'　'*depth}📁 {item['name']}", expanded=False):
                        if st.button("이 폴더 선택", key=f"btn_{item['id']}"):
                            st.session_state.current_folder_id = item['id']
                            st.session_state.current_folder_name = item['name']
                            st.rerun()
                        render_tree(item['id'], depth + 1)
        
        with st.container(height=400):
            render_tree(TARGET_FOLDER_ID)

    # ---------------------------------------------------------
    # ⏺️ [가운데 창] 미리보기 & 주소 붙여넣기
    # ---------------------------------------------------------
    with col_center:
        target_name = st.session_state.get('current_folder_name', '🏠 최상위')
        target_id = st.session_state.get('current_folder_id', TARGET_FOLDER_ID)
        
        st.subheader(f"📍 현재 위치: {target_name}")
        
        # 1. 주소 붙여넣기 (Ctrl+V) 전용 칸
        url_input = st.text_input("🔗 여기에 주소를 붙여넣으세요 (Ctrl+V)", 
                                 value=st.query_params.get("url", ""), 
                                 placeholder="인디스쿨 주소 등을 붙여넣으면 자동 저장됩니다.")
        
        st.write("---")
        
        # 2. 파일 목록 및 미리보기
        st.write("**📄 폴더 내 파일 목록**")
        files = list_items(service, target_id)
        if not files:
            st.info("이 폴더에 저장된 파일이 없습니다.")
        else:
            for f in files:
                if f['mimeType'] != 'application/vnd.google-apps.folder':
                    col_f1, col_f2 = st.columns([4, 1])
                    col_f1.markdown(f"[{f['name']}]({f['webViewLink']})")
                    if col_f2.button("미리보기", key=f"pre_{f['id']}"):
                        st.session_state.preview_url = f['webViewLink']
        
        # 미리보기 영역 (간이 iframe)
        if 'preview_url' in st.session_state:
            st.write("---")
            st.write("**👀 미리보기 (새 창 열기 권장)**")
            st.components.v1.iframe(st.session_state.preview_url, height=400, scrolling=True)

    # ---------------------------------------------------------
    # ➡️ [오른쪽 창] 파일 업로드 & 메모 & 저장
    # ---------------------------------------------------------
    with col_right:
        st.subheader("💾 저장하기")
        
        with st.container(border=True):
            up_files = st.file_uploader("📂 파일 드래그 앤 드롭", accept_multiple_files=True)
            memo = st.text_area("📝 수업 메모", height=150)
        
        if st.button("🚀 드라이브로 최종 전송", type="primary"):
            if not up_files and not url_input and not memo:
                st.warning("저장할 내용이 없습니다.")
            else:
                with st.spinner("드라이브에 저장 중..."):
                    if up_files:
                        for f in up_files:
                            upload_to_drive(service, target_id, f.name, f.getvalue())
                    if url_input or memo:
                        note_text = f"🔗 링크: {url_input}\n\n📝 메모: {memo}"
                        upload_to_drive(service, target_id, "학습정보_및_링크.txt", note_text.encode('utf-8'))
                    st.success("성공적으로 저장되었습니다!")
                    st.rerun()
