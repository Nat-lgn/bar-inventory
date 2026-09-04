import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime
from database import Session, engine
from models import Base, Product, InventoryRecord, User

def init_default_user(session):
    existing_user = session.query(User).first()
    if not existing_user:
        default_user = User(username="admin", password="bar123")
        session.add(default_user)
        session.commit()

Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="Инвентаризация бара", page_icon="🍹", layout="wide")

# --- СИСТЕМА АВТОРИЗАЦИИ (ВХОД И РЕГИСТРАЦИЯ) ---
session = Session()
init_default_user(session)
session.close()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

if not st.session_state.authenticated:
    st.title("🔒 Доступ к системе инвентаризации")
    
    auth_tab1, auth_tab2 = st.tabs(["🔑 Вход (Log in)", "📝 Регистрация (Sign up)"])
    
    with auth_tab1:
        with st.form("login_form"):
            username_input = st.text_input("Логин", key="login_user")
            password_input = st.text_input("Пароль", type="password", key="login_pass")
            submit_login = st.form_submit_button("Войти")
            
            if submit_login:
                session = Session()
                user = session.query(User).filter_by(username=username_input.strip(), password=password_input).first()
                session.close()
                
                if user:
                    st.session_state.authenticated = True
                    st.session_state.username = user.username
                    st.success("Успешный вход!")
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль.")
                    
    with auth_tab2:
        with st.form("signup_form"):
            new_user_input = st.text_input("Придумайте логин", key="signup_user")
            new_pass_input = st.text_input("Придумайте пароль", type="password", key="signup_pass")
            confirm_pass_input = st.text_input("Подтвердите пароль", type="password", key="signup_confirm")
            submit_signup = st.form_submit_button("Зарегистрироваться")
            
            if submit_signup:
                if not new_user_input.strip() or not new_pass_input.strip():
                    st.warning("Логин и пароль не могут быть пустыми.")
                elif new_pass_input != confirm_pass_input:
                    st.warning("Пароли не совпадают.")
                else:
                    session = Session()
                    existing_user = session.query(User).filter_by(username=new_user_input.strip()).first()
                    if existing_user:
                        st.warning("Пользователь с таким логином уже существует.")
                    else:
                        new_user = User(username=new_user_input.strip(), password=new_pass_input)
                        session.add(new_user)
                        session.commit()
                        st.session_state.authenticated = True
                        st.session_state.username = new_user.username
                        st.success("Регистрация успешна! Вход выполнен.")
                        st.rerun()
                    session.close()
    st.stop()

st.sidebar.title("🍹 Меню бармена")
st.sidebar.caption(f"👤 Вы вошли как: **{st.session_state.username}**")
page = st.sidebar.radio(
    "Навигация", 
    ["📝 Переучет продукции", "📊 История и Экспорт", "📚 Справочник и Управление"]
)

if st.sidebar.button("🚪 Выйти из системы"):
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.rerun()

# --- СТРАНИЦА 1: ПЕРЕУЧЕТ ПРОДУКЦИИ ---
if page == "📝 Переучет продукции":
    st.title("📝 Массовый переучет продукции")
    st.write("Посчитанные товары уходят под шлагбаум. Шкала прогресса показывает, сколько позиций уже обработано.")
    
    session = Session()
    products = session.query(Product).order_by(Product.name.asc()).all()
    session.close()
    
    if not products:
        st.warning("Сначала добавьте товары во вкладке «Справочник и Управление»!")
    else:
        if "inv_data" not in st.session_state:
            st.session_state.inv_data = {}
        if "edit_mode" not in st.session_state:
            st.session_state.edit_mode = set()

        def is_completed(p):
            if p.id in st.session_state.edit_mode:
                return False
            d = st.session_state.inv_data.get(p.id, {})
            if p.category == "шт":
                val = d.get("val")
                return val is not None and val > 0
            else:
                w = d.get("weight")
                return w is not None and w > 0

        total_count = len(products)
        completed_products = [p for p in products if is_completed(p)]
        completed_count = len(completed_products)
        progress_val = completed_count / total_count if total_count > 0 else 0.0

        # --- ШКАЛА ПРОГРЕССА ---
        st.subheader(f"Прогресс смены: {completed_count} из {total_count} позиций")
        st.progress(progress_val)
        st.divider()

        uncompleted_products = [p for p in products if not is_completed(p)]

        # --- ВВЕРХУ: НЕПОСЧИТАННЫЕ ТОВАРЫ В ВИДЕ АККУРАТНЫХ КАРТОЧЕК ---
        for p in uncompleted_products:
            with st.container(border=True):
                st.markdown(f"#### {p.name} <span style='font-size:14px; color:gray;'>({p.category})</span>", unsafe_allow_html=True)
                
                p_data = st.session_state.inv_data.get(p.id, {})
                
                if p.category == "шт":
                    val = st.number_input(
                        "Количество", 
                        min_value=0.0, 
                        step=1.0, 
                        value=p_data.get("val", None), 
                        key=f"val_{p.id}"
                    )
                    if val != p_data.get("val"):
                        st.session_state.inv_data[p.id] = {"val": val}
                        if p.id in st.session_state.edit_mode:
                            st.session_state.edit_mode.remove(p.id)
                        st.rerun()
                
                elif p.category in ["кг", "л"]:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        tare_count = st.number_input(
                            "Кол-во тары", 
                            min_value=0.0, 
                            step=1.0, 
                            value=p_data.get("tare", None), 
                            key=f"tare_{p.id}"
                        )
                    with col2:
                        total_weight = st.number_input(
                            "Общий вес (г)", 
                            min_value=0.0, 
                            step=10.0, 
                            value=p_data.get("weight", None), 
                            key=f"weight_{p.id}"
                        )
                    with col3:
                        t_val = tare_count if tare_count is not None else 0.0
                        w_val = total_weight if total_weight is not None else 0.0
                        total_tare_weight = t_val * p.tare_weight
                        net_result = 0.0
                        if p.category == "л":
                            net_weight = w_val - total_tare_weight if w_val > total_tare_weight else 0.0
                            net_result = net_weight / p.density / 1000 if p.density > 0 else 0.0
                        elif p.category == "кг":
                            net_weight = w_val - total_tare_weight if total_tare_weight > 0 else w_val
                            net_result = net_weight if net_weight > 0 else 0.0
                        
                        st.metric(label="Результат", value=f"{net_result:.3f} {p.category}")
                    
                    if tare_count != p_data.get("tare") or total_weight != p_data.get("weight"):
                        st.session_state.inv_data[p.id] = {"tare": tare_count, "weight": total_weight}
                        if p.id in st.session_state.edit_mode:
                            st.session_state.edit_mode.remove(p.id)
                        st.rerun()

        # --- ШЛАГБАУМ ---
        if completed_products:
            st.markdown(
                """
                <div style="display: flex; align-items: center; text-align: center; margin: 30px 0 20px 0;">
                    <hr style="flex: 1; border: none; border-top: 2px dashed #ff4b4b;">
                    <span style="padding: 0 15px; color: #ff4b4b; font-weight: bold; font-size: 15px;">🛑 Шлагбаум: Посчитанная продукция (нажмите для редактирования)</span>
                    <hr style="flex: 1; border: none; border-top: 2px dashed #ff4b4b;">
                </div>
                """, 
                unsafe_allow_html=True
            )

            for p in completed_products:
                d = st.session_state.inv_data.get(p.id, {})
                res_str = ""
                if p.category == "шт":
                    res_str = f"{d.get('val', 0)} шт"
                else:
                    t_val = d.get("tare", 0.0) or 0.0
                    w_val = d.get("weight", 0.0) or 0.0
                    total_tare_weight = t_val * p.tare_weight
                    if p.category == "л":
                        net = (w_val - total_tare_weight) / p.density / 1000 if (w_val - total_tare_weight) > 0 and p.density > 0 else 0.0
                    else:
                        net = (w_val - total_tare_weight) if total_tare_weight > 0 else w_val
                    res_str = f"{net:.3f} {p.category}"

                if st.button(f"✅ {p.name} — Результат: {res_str} (кликните для изменения)", key=f"edit_btn_{p.id}"):
                    st.session_state.edit_mode.add(p.id)
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Сохранить результаты переучета смены", type="primary"):
            try:
                current_time = datetime.now()
                saved_count = 0
                session = Session()
                
                for p in products:
                    data = st.session_state.inv_data.get(p.id, {})
                    if p.category == "шт":
                        val = data.get("val")
                        if val is not None and val > 0:
                            session.add(InventoryRecord(product_id=p.id, current_weight=val, checked_at=current_time))
                            saved_count += 1
                    else:
                        w = data.get("weight")
                        if w is not None and w > 0:
                            session.add(InventoryRecord(product_id=p.id, current_weight=w, checked_at=current_time))
                            saved_count += 1
                
                session.commit()
                session.close()
                if saved_count > 0:
                    st.success(f"Успешно сохранено позиций: {saved_count}!")
                    st.session_state.inv_data = {}
                    st.session_state.edit_mode = set()
                    st.rerun()
                else:
                    st.warning("Нет заполненных данных для сохранения.")
            except Exception as e:
                session.rollback()
                session.close()
                st.error(f"Ошибка при сохранении: {e}")


# --- СТРАНИЦА 2: ИСТОРИЯ ПО ДАТАМ И ЭКСПОРТ В EXCEL ---
elif page == "📊 История и Экспорт":
    st.title("📊 История переучетов по датам")
    
    session = Session()
    records = session.query(InventoryRecord).order_by(InventoryRecord.checked_at.desc()).all()
    
    if records:
        dates_dict = {}
        for r in records:
            date_str = r.checked_at.strftime("%Y-%m-%d %H:%M")
            if date_str not in dates_dict:
                dates_dict[date_str] = []
            dates_dict[date_str].append(r)
            
        selected_session_date = st.selectbox("Выберите дату и время переучета смены", list(dates_dict.keys()))
        
        if selected_session_date:
            session_records = dates_dict[selected_session_date]
            history_data = []
            for r in session_records:
                prod = session.query(Product).filter_by(id=r.product_id).first()
                p_name = prod.name if prod else "Удаленный товар"
                p_cat = prod.category if prod else ""
                
                history_data.append({
                    "Товар": p_name,
                    "Тип": p_cat,
                    "Введенное значение": r.current_weight
                })
            
            df_history = pd.DataFrame(history_data)
            st.dataframe(df_history, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_history.to_excel(writer, index=False, sheet_name='Переучет смены')
            excel_data = output.getvalue()
            
            st.download_button(
                label=f"📥 Скачать отчет за {selected_session_date} в формате Excel (.xlsx)",
                data=excel_data,
                file_name=f"inventory_report_{selected_session_date.replace(':', '-')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("История переучетов пока пуста.")
    session.close()


# --- СТРАНИЦА 3: СПРАВОЧНИК И УПРАВЛЕНИЕ ---
elif page == "📚 Справочник и Управление":
    st.title("📚 Справочник и Управление товарами")
    
    session = Session()
    
    # --- 1. МАССОВАЯ ЗАГРУЗКА ИЗ ФАЙЛА ---
    st.header("📥 Загрузка справочника из таблицы")
    st.write("Загрузите Excel-файл (`.xlsx`) или CSV со списком продукции. Сайт автоматически считает названия, категории и параметры тары.")
    
    uploaded_file = st.file_uploader("Выберите файл с товарами", type=["xlsx", "csv"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)
            
            st.write("Обнаруженные колонки в файле:", list(df_upload.columns))
            st.write("Полный предпросмотр данных:")
            st.dataframe(df_upload, use_container_width=True)
            
            if st.button("🚀 Импортировать данные в базу", type="primary"):
                added_count = 0
                updated_count = 0
                skipped_count = 0
                
                for _, row in df_upload.iterrows():
                    name = str(row.get("Название", "")).strip()
                    category = str(row.get("Категория", "шт")).strip()
                    
                    if not name or name == "nan" or name == "":
                        skipped_count += 1
                        continue
                        
                    density = float(row.get("Плотность", 1.0)) if pd.notna(row.get("Плотность")) else 1.0
                    tare_weight = float(row.get("Вес тары", 0.0)) if pd.notna(row.get("Вес тары")) else 0.0
                    
                    existing_product = session.query(Product).filter_by(name=name).first()
                    
                    if existing_product:
                        existing_product.category = category
                        existing_product.density = density
                        existing_product.tare_weight = tare_weight
                        updated_count += 1
                    else:
                        new_product = Product(
                            name=name,
                            category=category,
                            density=density,
                            tare_weight=tare_weight
                        )
                        session.add(new_product)
                        added_count += 1
                
                session.commit()
                
                if added_count > 0 or updated_count > 0:
                    st.success(f"Импорт завершен! Добавлено новых: {added_count}, обновлено: {updated_count}. (Пропущено пустых строк: {skipped_count})")
                    session.close()
                    st.rerun()
                else:
                    st.warning(f"Ни одна строка не была импортирована. Проверьте заголовки колонок. Пропущено строк: {skipped_count}")
                
        except Exception as e:
            st.error(f"Ошибка при чтении файла: {e}")

    st.divider()

    # --- 2. ИНТЕРАКТИВНЫЙ РЕДАКТОР ТАБЛИЦЫ ---
    st.header("✏️ Редактирование справочника на сайте")
    st.write("Вы можете менять ячейки кликом, добавлять новые строки внизу или удалять ненужные товары прямо в таблице.")
    
    products = session.query(Product).order_by(Product.name.asc()).all()
    
    df_products = pd.DataFrame([{
        "id": p.id,
        "Название": p.name,
        "Категория": p.category,
        "Плотность": p.density,
        "Вес тары": p.tare_weight
    } for p in products]) if products else pd.DataFrame(columns=["id", "Название", "Категория", "Плотность", "Вес тары"])
    
    edited_df = st.data_editor(
        df_products, 
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "Категория": st.column_config.SelectboxColumn("Категория", options=["шт", "л", "кг"], required=True)
        }
    )
    
    if st.button("💾 Сохранить изменения в базе данных", type="primary"):
        try:
            existing_ids = {p.id for p in products}
            current_ui_ids = set()
            
            for index, row in edited_df.iterrows():
                row_id = row.get("id")
                name = str(row.get("Название", "")).strip()
                category = str(row.get("Категория", "шт")).strip()
                
                if not name or name == "nan":
                    continue
                
                density = float(row.get("Плотность", 1.0)) if pd.notna(row.get("Плотность")) else 1.0
                tare_weight = float(row.get("Вес тары", 0.0)) if pd.notna(row.get("Вес тары")) else 0.0
                
                if pd.notna(row_id) and int(row_id) in existing_ids:
                    db_prod = session.query(Product).filter_by(id=int(row_id)).first()
                    if db_prod:
                        db_prod.name = name
                        db_prod.category = category
                        db_prod.density = density
                        db_prod.tare_weight = tare_weight
                        current_ui_ids.add(db_prod.id)
                else:
                    new_prod = Product(
                        name=name,
                        category=category,
                        density=density,
                        tare_weight=tare_weight
                    )
                    session.add(new_prod)
                    session.flush()
                    current_ui_ids.add(new_prod.id)
            
            for p in products:
                if p.id not in current_ui_ids:
                    session.delete(p)
                    
            session.commit()
            st.success("Все изменения успешно сохранены в базе данных!")
            session.close()
            st.rerun()
            
        except Exception as e:
            session.rollback()
            session.close()
            st.error(f"Ошибка при сохранении: {e}")

    st.divider()
    st.header("👤 Управление учетными записями")
    
    with st.form("change_password_form"):
        st.subheader("Изменить пароль текущего аккаунта")
        new_password = st.text_input("Новый пароль", type="password")
        confirm_password = st.text_input("Подтвердите новый пароль", type="password")
        submit_pass = st.form_submit_button("Обновить пароль")
        
        if submit_pass:
            if new_password and new_password == confirm_password:
                current_user = session.query(User).filter_by(username=st.session_state.username).first()
                if current_user:
                    current_user.password = new_password
                    session.commit()
                    st.success("Пароль успешно изменен!")
                else:
                    st.warning("Пользователь не найден.")
            else:
                st.warning("Пароли не совпадают или пусты.")

    with st.form("add_user_form"):
        st.subheader("Добавить нового сотрудника")
        new_username = st.text_input("Логин нового пользователя")
        new_user_password = st.text_input("Пароль нового пользователя", type="password")
        submit_user = st.form_submit_button("Создать пользователя")
        
        if submit_user:
            if new_username.strip() and new_user_password.strip():
                try:
                    user_exists = session.query(User).filter_by(username=new_username.strip()).first()
                    if user_exists:
                        st.warning("Пользователь с таким логином уже существует.")
                    else:
                        add_user = User(username=new_username.strip(), password=new_user_password.strip())
                        session.add(add_user)
                        session.commit()
                        st.success(f"Пользователь '{new_username}' успешно создан!")
                except Exception as e:
                    st.error(f"Ошибка создания пользователя: {e}")
            else:
                st.warning("Заполните логин и пароль.")

    session.close()
