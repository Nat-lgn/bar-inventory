import streamlit as st
from database import Session
from models import User

def render(t):
    st.title(t["cabinet_title"])
    st.write(t["cabinet_desc"])

    st.subheader(t["settings_title"])
    st.session_state.keep_completed_in_place = st.checkbox(
        t["keep_in_place_label"],
        value=st.session_state.keep_completed_in_place
    )

    st.divider()
    
    with st.expander("📖 Гайд / Посібник", expanded=False):
        st.markdown(t["guide_text"])
    
    st.divider()
    
    session = Session()
    
    with st.form("change_password_form"):
        st.subheader(t["change_pass_title"])
        new_password = st.text_input(t["new_pass_label"], type="password")
        confirm_password = st.text_input(t["confirm_pass_label"], type="password")
        submit_pass = st.form_submit_button(t["update_pass_btn"])
        
        if submit_pass:
            if new_password and new_password == confirm_password:
                current_user = session.query(User).filter_by(username=st.session_state.username).first()
                if current_user:
                    current_user.password = new_password
                    session.commit()
                    st.success(t["pass_success"])
                else:
                    st.warning("User not found.")
            else:
                st.warning("Passwords do not match or empty.")

    st.divider()

    with st.form("add_user_form"):
        st.subheader(t["add_emp_title"])
        new_username = st.text_input(t["emp_login"])
        new_user_password = st.text_input(t["emp_pass"], type="password")
        submit_user = st.form_submit_button(t["create_emp_btn"])
        
        if submit_user:
            if new_username.strip() and new_user_password.strip():
                try:
                    user_exists = session.query(User).filter_by(username=new_username.strip()).first()
                    if user_exists:
                        st.warning("User already exists.")
                    else:
                        add_user = User(username=new_username.strip(), password=new_user_password.strip())
                        session.add(add_user)
                        session.commit()
                        st.success(t["emp_success"])
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Fill all fields.")

    session.close()
