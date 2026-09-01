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

# --- ВКЛАДКА 1: ПЕРЕУЧЕТ ПО ОТДЕЛЬНЫМ ПОЛЯМ ДЛЯ КАЖДОГО ТОВАРА ---
with tab1:
    st.header("Проведение переучета")
    st.write("Введите данные для каждого товара. Посчитанные позиции можно сохранить кнопкой внизу.")
    
    products = session.query(Product).all()
    
    if not products:
        st.warning("Сначала добавьте товары во вкладке «Справочник и Управление»!")
    else:
        with st.form("inventory_cards_form"):
            inventory_inputs = {}
            
            for p in products:
                st.markdown(f"### 🔹 {p.name} <span style='font-size:14px; color:gray;'>(Тип: {p.category})</span>", unsafe_allow_html=True)
                
                if p.category == "шт":
                    # Только одно поле для ввода результата
                    res_val = st.number_input(f"Количество штук [{p.name}]", min_value=0.0, step=1.0, key=f"val_{p.id}")
                    inventory_inputs[p.id] = {"tare_count": 0.0, "total_weight": res_val, "result": res_val}
                
                elif p.category in ["кг", "л"]:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        tare_count = st.number_input(f"Кол-во тары [{p.name}]", min_value=0.0, step=1.0, key=f"tare_{p.id}")
                    with col2:
                        total_weight = st.number_input(f"Общий вес (г) [{p.name}]", min_value=0.0, step=10.0, key=f"weight_{p.id}")
                    with col3:
                        # Автоматический расчет результата «на лету» для отображения
                        total_tare_weight = tare_count * p.tare_weight
                        net_result = 0.0
                        if p.category == "л":
                            net_weight = total_weight - total_tare_weight if total_weight > total_tare_weight else 0.0
                            net_result = net_weight / p.density / 1000 if p.density > 0 else 0.0
                        elif p.category == "кг":
                            net_weight = total_weight - total_tare_weight if total_tare_weight > 0 else total_weight
                            net_result = net_weight if net_weight > 0 else 0.0
                        
                        st.metric(label="Результат (нетто)", value=f"{net_result:.3f} {p.category}")
                    
                    inventory_inputs[p.id] = {"tare_count": tare_count, "total_weight": total_weight, "result": net_result}
                
                st.divider()
            
            submit_all = st.form_submit_button("💾 Сохранить результаты переучета смены", type="primary")
            
            if submit_all:
                try:
                    current_time = datetime.now()
                    saved_count = 0
                    
                    for p_id, data in inventory_inputs.items():
                        if data["total_weight"] > 0 or data["tare_count"] > 0:
                            new_record = InventoryRecord(
                                product_id=p_id,
                                current_weight=data["total_weight"],
                                checked_at=current_time
                            )
                            session.add(new_record)
                            saved_count += 1
                    
                    session.commit()
                    if saved_count > 0:
                        st.success(f"Успешно сохранено позиций: {saved_count}!")
                        st.rerun()
                    else:
                        st.warning("Вы не заполнили данные ни для одного товара.")
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


# --- ВКЛАДКА 3: СПРАВОЧНИК И УПРАВЛЕНИЕ (ДОБАВЛЕНИЕ, РЕДАКТИРОВАНИЕ, УДАЛЕНИЕ) ---
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
        # Интерактивное редактирование
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
