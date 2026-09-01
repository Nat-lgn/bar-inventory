import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Проверяем, где мы запущены. В Streamlit Cloud папка /mount/src/ существует.
# Если мы в облаке, сохраняем базу в безопасное место, иначе — локально в папку проекта.
if os.path.exists("/mount/src"):
    DB_PATH = "sqlite:////mount/src/bar-inventory/database.db"
else:
    DB_PATH = "sqlite:///database.db"

engine = create_engine(DB_PATH, echo=True)
Base = declarative_base()
Session = sessionmaker(bind=engine)
