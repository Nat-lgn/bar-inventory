import streamlit as st
from database import Session, engine
from models import Base, User
from locales import TEXTS

# Импорт разделов из папки views
from views import inventory, history, catalog, tools, cabinet

def init_default_user(session):
    existing_user = session.query(User).first()
    if not existing_user:
        default_user = User(username="admin", password="bar123")
        session.add(default_user)
        session.commit()

def evaluate_expression(expr_str):
    if expr_str is None:
        return 0.0
    str_val = str(expr_str).strip().replace(',', '.')
    if not str_val:
        return 0.0
    try:
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in str_val):
            return float(str_val)
        result = eval(str_val, {"__builtins__": {}}, {})
        return float(result)
    except Exception:
        try:
            return float(str_val)
        except ValueError:
            return 0.0

Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="Инвентаризация бара / Облік бару", page_icon="🍹", layout="wide")

session = Session()
init_default_user(session)
session.close()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "lang" not in st.session_state:
    st.session_state.lang = "ru"
if "keep_completed_in_place" not in st.session_state:
    st.session_state.keep_completed_in_place = False

# Выбор языка
selected_lang_label = st.sidebar.selectbox("🌍 Язык / Мова", ["Русский", "Українська"], index=0 if st.session_state.lang == "ru" else 1)
st.session_state.lang = "ru" if selected_lang_label == "Русский" else "uk"
t = TEXTS[st.session_state.lang]

# Экран авторизации
if not st.session_state.authenticated:
    st.title(t["login_title"])
    auth_tab1, auth_tab2 = st.tabs([t["tab_login"], t["tab_signup"]])
    
    with auth_tab1:
        with st.form("login_form"):
            username_input = st.text_input("Логин / Логін", key="login_user")
            password_input = st.text_input("Пароль", type="password", key="login_pass")
            submit_login = st.form_submit_button(t["login_btn"])
            if submit_login:
                session = Session()
                user = session.query(User).filter_by(username=username_input.strip(), password=password_input).first()
                session.close()
                if user:
                    st.session_state.authenticated = True
                    st.session_state.username = user.username
                    st.success(t["success_login"])
                    st.rerun()
                else:
                    st.error(t["error_login"])
                    
    with auth_tab2:
        with st.form("signup_form"):
            new_user_input = st.text_input("Логин / Логін", key="signup_user")
            new_pass_input = st.text_input("Пароль", type="password", key="signup_pass")
            confirm_pass_input = st.text_input("Подтвердите пароль / Підтвердьте пароль", type="password", key="signup_confirm")
            submit_signup = st.form_submit_button(t["signup_btn"])
            if submit_signup:
                if not new_user_input.strip() or not new_pass_input.strip():
                    st.warning(t["empty_creds"])
                elif new_pass_input != confirm_pass_input:
                    st.warning(t["pass_mismatch"])
                else:
                    session = Session()
                    existing_user = session.query(User).filter_by(username=new_user_input.strip()).first()
                    if existing_user:
                        st.warning(t["user_exists"])
                    else:
                        new_user = User(username=new_user_input.strip(), password=new_pass_input)
                        session.add(new_user)
                        session.commit()
                        st.session_state.authenticated = True
                        st.session_state.username = new_user.username
                        st.success(t["signup_success"])
                        st.rerun()
                    session.close()
    st.stop()

# Сайдбар и навигация
st.sidebar.title(t["menu_title"])
st.sidebar.caption(f"{t['logged_in']}: **{st.session_state.username}**")
st.sidebar.divider()

if "current_page" not in st.session_state:
    st.session_state.current_page = t["p1"]

st.sidebar.markdown(f"**{t['nav']}**")
nav_items = [t["p1"], t["p2"], t["p3"], t["p5"], t["p4"]]

for item in nav_items:
    is_active = (st.session_state.current_page == item)
    if st.sidebar.button(item, key=f"nav_btn_{item}", use_container_width=True, type="primary" if is_active else "secondary"):
        if st.session_state.current_page != item:
            st.session_state.current_page = item
            st.rerun()

page = st.session_state.current_page

st.sidebar.divider()
if st.sidebar.button(t["logout"], key="logout_button_sidebar", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.rerun()

# Роутинг страниц
if page == t["p1"]:
    inventory.render(t, evaluate_expression)
elif page == t["p2"]:
    history.render(t)
elif page == t["p3"]:
    catalog.render(t)
elif page == t["p5"]:
    tools.render(t)
elif page == t["p4"]:
    cabinet.render(t)
