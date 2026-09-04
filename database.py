import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Считываем строку подключения из секретов Streamlit
DATABASE_URL = st.secrets["database"]["url"]

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
