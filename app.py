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

tab1, tab2 = st.tabs(["📝 Проведение переучета", "📚 Справочник и Управление"])

# --- ВКЛАДКА 1: МАССОВЫЙ ПЕРЕУЧЕТ В ВИДЕ ТАБЛИЦЫ ---
with tab1:
    st.header("Массовый переучет продукции")
    st.write("Заполните количество тары и общий вес прямо в таблице, затем нажмите кнопку сохранения внизу.")
    
    products = session.query(Product).all()
    
    if not products:
        st.warning("Сначала добавьте товары во вкладке «Справочник и Управление»!")
    else:
        # Подготавливаем данные для интерактивной таблицы
        inventory_table_data = []
        for p in products:
            inventory_table_data.append({
                "id": p.id,
                "Наименование": p.name,
                "Тип": p.category,
                "Кол-во тары": 0.0,
                "Общий вес": 0.0,
                "Результат": 0.0
            })
        
        df_inventory = pd.DataFrame(inventory_table_data)
        
        # Интерактивная таблица для ввода данных
        edited_inventory = st.data_editor(
            df_inventory,
            column_config={
                "id": None, # Скрываем ID от пользователя
                "Наименование": st.column_config.TextColumn("Наименование", disabled=True),
                "Тип": st.column_config.TextColumn("Тип", disabled=True),
                "Кол-во тары": st.column_config.NumberColumn("Кол-во тары", min_value=0.0, step=1.0),
                "Общий вес": st.column_config.NumberColumn("Общий вес / Кол-во", min_value=0.0, step=0.1),
                "Результат": st.column_config.NumberColumn("Результат (нетто)", disabled=True),
            },
            hide_index=True,
            key="mass_inventory_editor"
        )
        
        if st.button("💾 Сохранить результаты переучета смены", type="primary"):
            try:
                current_time = datetime.now()
                saved_count = 0
                
                for index, row in edited_inventory.iterrows():
                    # Сохраняем только те позиции, где ввели вес или количество больше 0
                    if row["Общий вес"] > 0 or row["Кол-во тары"] > 0:
                        prod = session.query(Product).filter_by(id=row["id"]).first()
                        if prod:
                            # Математика расчета
                            net_result = 0.0
                            total_tare_weight = row["Кол-во тары"] * prod.tare_weight
                            
                            if prod.category == "шт":
                                net_result = row["Общий вес"]
                            elif prod.category == "л":
                                net_weight = row["Общий вес"] - total_tare_weight
                                net_result = net_weight / prod.density / 1000 if net_weight > 0 and prod.density > 0 else 0.0
                            elif prod.category == "кг":
                                net_weight = row["Общий вес"] - total_tare_weight
                                net_result = net_weight / 1000 if net_weight > 0 else 0.0

                            # Записываем в историю
                            new_record = InventoryRecord(
                                product_id=prod.id,
                                current_weight=row["Общий вес"],
                                checked_at=current_time
                            )
                            session.add(new_record)
                            saved_count += 1
                
                session.commit()
                if saved_count > 0:
                    st.success(f"Успешно сохранено позиций: {saved_count}!")
                else:
                    st.warning("Вы не заполнили данные ни для одного товара.")
            except Exception as e:
                session.rollback()
                st.error(f"Ошибка при сохранении: {e}")

    st.subheader("📊 История переучетов и Экспорт")
    records = session.query(InventoryRecord).order_by(InventoryRecord.checked_at.desc()).all()
    
    if records:
        history_data = []
        for r in records:
            prod = session.query(Product).filter_by(id=r.product_id).first()
            p_name = prod.name if prod else "Удаленный товар"
            p_cat = prod.category if prod else ""
            
            res = 0.0
            if prod:
                if prod.category == "шт":
                    res = r.current_weight
                elif prod.category == "л":
                    net = r.current_weight - r.current_weight # упрощенно для истории
                    res = net / prod.density / 1000 if net > 0 and prod.density > 0 else r.current_weight
                elif prod.category == "кг":
                    res = r.current_weight / 1000

            history_data.append({
                "Дата и время": r.checked_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Товар": p_name,
                "Введенное значение": r.current_weight,
                "Ед. изм.": p_cat
            })
        
        df_history = pd.DataFrame(history_data)
        st.dataframe(df_history, use_container_width=True)
        
        csv_data = df_history.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Скачать отчет в формате CSV (Excel)",
            data=csv_data,
            file_name=f"inventory_report_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("История переучетов пока пуста.")


# --- ВКЛАДКА 2: СПРАВОЧНИК И УПРАВЛЕНИЕ ---
with tab2:
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

    st.header("✏️ Редактирование справочника")
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
    else:
        st.info("Справочник пуст.")

session.close()
