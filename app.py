import streamlit as st
import os
import io
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# =====================================================================
# 선생님 전용 설정
# =====================================================================
TARGET_FOLDER_ID = "1cVO7Crr0D8l95_m4rlpWNg85PQSy5pad" # 선생님 폴더 고정
SCOPES = ['https://www.googleapis.com/auth/drive']
SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(settings, f, ensure_ascii=False)

def get_drive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token: token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

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
st.title("나만의 전용 교육 자료실 📚")

# 크롬 확장 프로그램에서 보낸 주소 받아오기
passed_url = st.query_params.get("url", "")
if passed_url:
    st.success("💡 크롬 앱에서 인디스쿨(또는 다른) 링크를 성공적으로 가져왔습니다!")

saved = load_settings()
years_list = ["2025", "2026", "2027"]
grades_list = ["1학년", "2학년", "3학년", "4학년", "5학년", "6학년"]
semesters_list = ["1학기", "2학기", "여름방학", "겨울방학"]
subjects_list = ["국어", "수학", "사회", "과학", "영어", "음악", "미술", "체육", "실과", "도덕", "창체", "기타"]

def get_idx(lst, val, default_idx=0): return lst.index(val) if val in lst else default_idx

tab1, tab2 = st.tabs(["📤 자료 올리기 (업로드)", "🦅 내 자료 모아보기 (갤러리)"])

# ---------------------------------------------------------
# 탭 1: 자료 올리기
# ---------------------------------------------------------
with tab1:
    col_year, col_grade, col_semester = st.columns(3)
    with col_year: year = st.selectbox("연도", years_list, index=get_idx(years_list, saved.get("year", "2026")))
    with col_grade: grade = st.selectbox("학년", grades_list, index=get_idx(grades_list, saved.get("grade", "5학년")))
    with col_semester: semester = st.selectbox("학기", semesters_list, index=get_idx(semesters_list, saved.get("semester", "1학기")))

    col_sub, col_unit, col_period = st.columns(3)
    with col_sub: subject = st.selectbox("과목", subjects_list, index=get_idx(subjects_list, saved.get("subject", "국어")))
    with col_unit: unit = st.text_input("단원", placeholder="예: 3단원 우리 이웃")
    with col_period: period = st.text_input("차시", placeholder="예: 2차시")

    # 설정 자동 저장
    current_settings = {"year": year, "grade": grade, "semester": semester, "subject": subject}
    if current_settings != saved: save_settings(current_settings)

    st.write("---")
    uploaded_files = st.file_uploader("📂 수업 파일 업로드 (인디스쿨에서 받은 파일을 드래그 앤 드롭!)", accept_multiple_files=True)
    link_url = st.text_area("🔗 참고 링크 (크롬 앱 사용 시 자동 입력됨)", value=passed_url, height=100)
    memo = st.text_area("📝 수업 메모 (필요시 작성)", height=100)

    if st.button("🚀 구글 드라이브에 완벽하게 정리하기", type="primary", use_container_width=True):
        if not unit: st.warning("단원명을 최소한 입력해 주세요!")
        elif not uploaded_files and not link_url and not memo: st.warning("저장할 내용을 입력해 주세요!")
        else:
            with st.spinner('드라이브에 폴더를 만들고 자료를 쏙쏙 넣는 중... 🚀'):
                try:
                    service = get_drive_service()
                    f1 = get_or_create_folder(service, f"{year}학년도", TARGET_FOLDER_ID)
                    f2 = get_or_create_folder(service, grade, f1)
                    f3 = get_or_create_folder(service, semester, f2)
                    f4 = get_or_create_folder(service, subject, f3)
                    f5 = get_or_create_folder(service, unit, f4)
                    final_folder_id = get_or_create_folder(service, period, f5)

                    if uploaded_files:
                        for file in uploaded_files:
                            new_file_name = f"[{subject}_{unit}_{period}] {file.name}"
                            upload_to_drive(service, final_folder_id, new_file_name, file.getvalue())

                    if link_url or memo:
                        # 텍스트 파일(메모장) 내용물 만들기
                        memo_content = f"🔗 참고 링크:\n{link_url}\n\n📝 수업 메모:\n{memo}"
                        memo_file_name = f"[{subject}_{unit}_{period}] 링크_및_설명.txt"
                        upload_to_drive(service, final_folder_id, memo_file_name, memo_content.encode('utf-8'))

                    st.success("✨ 저장 완료! 메모장 파일까지 완벽하게 생성되었습니다.")
                except Exception as e: st.error(f"오류 발생: {e}")

# ---------------------------------------------------------
# 탭 2: 갤러리 (이글 모드)
# ---------------------------------------------------------
with tab2:
    st.subheader("🔎 내 서랍장 뒤져보기")
    st.info("💡 왼쪽 탭에서 선택한 과목의 자료를 바로 확인합니다.")
    
    if st.button("🔄 현재 과목 폴더 열어보기", icon="📂"):
        with st.spinner("구글 드라이브에서 파일을 가져오는 중입니다..."):
            try:
                service = get_drive_service()
                f1 = get_or_create_folder(service, f"{year}학년도", TARGET_FOLDER_ID)
                f2 = get_or_create_folder(service, grade, f1)
                f3 = get_or_create_folder(service, semester, f2)
                f4 = get_or_create_folder(service, subject, f3)
                
                units = list_files_in_folder(service, f4)
                if not units: st.warning("아직 저장된 자료가 없습니다.")
                else:
                    for u in units:
                        if u['mimeType'] == 'application/vnd.google-apps.folder':
                            with st.expander(f"📁 {u['name']}"):
                                periods = list_files_in_folder(service, u['id'])
                                for p in periods:
                                    if p['mimeType'] == 'application/vnd.google-apps.folder':
                                        st.markdown(f"**📂 {p['name']}**")
                                        files = list_files_in_folder(service, p['id'])
                                        for f in files:
                                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp; 📄 [{f['name']}]({f['webViewLink']})")
                                    else:
                                        st.markdown(f"📄 [{p['name']}]({p['webViewLink']})")
            except Exception as e: st.error(f"오류 발생: {e}")