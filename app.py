import os
import streamlit as st
import pandas as pd
from datetime import datetime
from database import Session, engine
from models import Base, Product, InventoryRecord

Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="Инвентаризация бара", page_icon="🍹", layout="wide")

# --- СИСТЕМА АВТОРИЗАЦИИ ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Доступ ограничен")
    st.write("Пожалуйста, введите пароль для доступа к системе инвентаризации.")
    
    with st.form("login_form"):
        password_input = st.text_input("Пароль", type="password")
        submit_login = st.form_submit_button("Войти")
        
        if submit_login:
            if password_input == "bar123":
                st.session_state.authenticated = True
                st.success("Успешный вход!")
                st.rerun()
            else:
                st.error("Неверный пароль. Попробуйте еще раз.")
    st.stop()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---
session = Session()

st.title("🍹 Система инвентаризации бара")

if st.sidebar.button("🚪 Выйти из системы"):
    st.session_state.authenticated = False
    st.rerun()

tab1, tab2, tab3 = st.tabs(["📝 Переучет продукции", "📊 История и Экспорт", "📚 Справочник и Управление"])

# --- ВКЛАДКА 1: ПЕРЕУЧЕТ С ДИНАМИЧЕСКИМ СМЕЩЕНИЕМ И ПУСТЫМИ ПОЛЯМИ ---
with tab1:
    st.header("Проведение переучета")
    st.write("Поля ввода изначально пусты. Заполненные позиции автоматически перемещаются в конец списка.")
    
    products = session.query(Product).all()
    
    if not products:
        st.warning("Сначала добавьте товары во вкладке «Справочник и Управление»!")
    else:
        if "inv_data" not in st.session_state:
            st.session_state.inv_data = {}

        def is_completed(p):
            d = st.session_state.inv_data.get(p.id, {})
            if p.category == "шт":
                return d.get("val") is not None and d.get("val") > 0
            else:
                return (d.get("weight") is not None and d.get("weight") > 0) or (d.get("tare") is not None and d.get("tare") > 0)

        # Сортировка: незаполненные сверху, заполненные снизу
        sorted_products = sorted(products, key=lambda p: (1 if is_completed(p) else 0, p.name))

        for p in sorted_products:
            st.markdown(f"### 🔹 {p.name} <span style='font-size:14px; color:gray;'>(Тип: {p.category})</span>", unsafe_allow_html=True)
            
            p_data = st.session_state.inv_data.get(p.id, {})
            
            if p.category == "шт":
                val = st.number_input(
                    f"Количество штук [{p.name}]", 
                    min_value=0.0, 
                    step=1.0, 
                    value=p_data.get("val", None), 
                    key=f"val_{p.id}"
                )
                if val != p_data.get("val"):
                    st.session_state.inv_data[p.id] = {"val": val}
                    st.rerun()
            
            elif p.category in ["кг", "л"]:
                col1, col2, col3 = st.columns(3)
                with col1:
                    tare_count = st.number_input(
                        f"Кол-во тары [{p.name}]", 
                        min_value=0.0, 
                        step=1.0, 
                        value=p_data.get("tare", None), 
                        key=f"tare_{p.id}"
                    )
                with col2:
                    total_weight = st.number_input(
                        f"Общий вес (г) [{p.name}]", 
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
                    
                    st.metric(label="Результат (нетто)", value=f"{net_result:.3f} {p.category}")
                
                if tare_count != p_data.get("tare") or total_weight != p_data.get("weight"):
                    st.session_state.inv_data[p.id] = {"tare": tare_count, "weight": total_weight}
                    st.rerun()
            
            st.divider()

        if st.button("💾 Сохранить результаты переучета смены", type="primary"):
            try:
                current_time = datetime.now()
                saved_count = 0
                
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
                if saved_count > 0:
                    st.success(f"Успешно сохранено позиций: {saved_count}!")
                    st.session_state.inv_data = {}
                    st.rerun()
                else:
                    st.warning("Нет заполненных данных для сохранения.")
            except Exception as e:
                session.rollback()
                st.error(f"Ошибка при сохранении: {e}")


# --- ВКЛАДКА 2: ИСТОРИЯ ПО ДАТАМ И ЭКСПОРТ ---
with tab2:
    st.header("📊 История переучетов по датам")
    
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
            
            csv_data = df_history.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Скачать отчет за {selected_session_date} в CSV (Excel)",
                data=csv_data,
                file_name=f"inventory_report_{selected_session_date.replace(':', '-')}.csv",
                mime="text/csv"
            )
    else:
        st.info("История переучетов пока пуста.")


# --- ВКЛАДКА 3: СПРАВОЧНИК И УПРАВЛЕНИЕ ---
with tab3:
    st.header("Добавить новый товар")
    
    prod_category = st.selectbox("Категория", ["шт", "л", "кг"])
    
    prod_density = 1.0
    prod_tare = 0.0
    
    if prod_category == "л":
        prod_density = st.number_input("Плотность (г/мл)", value=1.0, step=0.01)
        prod_tare = st.number_input("Вес одной единицы тары (г)", value=0.0, step=10.0)
    elif prod_category == "кг":
        prod_tare = st.number_input("Вес одной единицы тары (г)", value=0.0, step=10.0)

    with st.form("add_product_form"):
        prod_name = st.text_input("Название товара")
        submit_product = st.form_submit_button("Сохранить в справочник")
        
        if submit_product:
            if prod_name.strip():
                try:
                    new_product = Product(
                        name=prod_name,
                        category=prod_category,
                        density=prod_density,
                        tare_weight=prod_tare
                    )
                    session.add(new_product)
                    session.commit()
                    st.success(f"Товар '{prod_name}' добавлен!")
                    st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"Ошибка (возможно, такой товар уже есть): {e}")
            else:
                st.warning("Название не может быть пустым!")

    st.header("✏️ Редактирование и удаление справочника")
    products = session.query(Product).all()
    
    if products:
        df_products = pd.DataFrame([{
            "id": p.id,
            "Название": p.name,
            "Категория": p.category,
            "Плотность": p.density,
            "Вес тары": p.tare_weight
        } for p in products])
        
        edited_df = st.data_editor(df_products, key="product_editor", hide_index=True)
        
        if st.button("💾 Сохранить изменения в таблице"):
            try:
                for index, row in edited_df.iterrows():
                    db_prod = session.query(Product).filter_by(id=row["id"]).first()
                    if db_prod:
                        db_prod.name = row["Название"]
                        db_prod.category = row["Категория"]
                        db_prod.density = row["Плотность"]
                        db_prod.tare_weight = row["Вес тары"]
                session.commit()
                st.success("Все изменения успешно сохранены!")
                st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"Ошибка при сохранении: {e}")
        
        st.divider()
        st.subheader("🗑️ Удаление товара")
        prod_to_delete = st.selectbox("Выберите товар для удаления", [p.name for p in products], key="del_select")
        if st.button("Удалить выбранный товар", type="secondary"):
            target = session.query(Product).filter_by(name=prod_to_delete).first()
            if target:
                session.delete(target)
                session.commit()
                st.success(f"Товар '{prod_to_delete}' удален из справочника!")
                st.rerun()
    else:
        st.info("Справочник пуст.")

session.close()
