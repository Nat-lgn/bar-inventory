import os
import streamlit as st
import pandas as pd
from datetime import datetime
from database import Session, engine
from models import Base, Product, InventoryRecord

Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="Инвентаризация бара", page_icon="🍹")

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

# --- ВКЛАДКА 1: ПЕРЕУЧЕТ И ЭКСПОРТ ---
with tab1:
    st.header("Ввод данных переучета")
    
    products = session.query(Product).all()
    
    if not products:
        st.warning("Сначала добавьте товары во вкладке «Справочник и Управление»!")
    else:
        with st.form("inventory_form"):
            product_options = {p.name: p for p in products}
            selected_product_name = st.selectbox("Выберите товар", list(product_options.keys()))
            selected_product = product_options[selected_product_name]
            
            st.info(f"Категория: **{selected_product.category}** | Плотность: {selected_product.density} | Вес тары: {selected_product.tare_weight}г")
            
            input_value = 0.0
            if selected_product.category == "шт":
                input_value = st.number_input("Количество (шт)", min_value=0.0, step=1.0)
            else:
                input_value = st.number_input("Общий вес с тарой (г)", min_value=0.0, step=10.0)
            
            submit_inventory = st.form_submit_button("Сохранить результат")
            
            if submit_inventory:
                net_weight = input_value - selected_product.tare_weight
                if selected_product.category == "шт":
                    calculated_result = input_value
                else:
                    calculated_result = net_weight / selected_product.density / 1000 if net_weight > 0 and selected_product.density > 0 else 0.0

                new_record = InventoryRecord(
                    product_id=selected_product.id,
                    current_weight=input_value,
                    checked_at=datetime.now()
                )
                session.add(new_record)
                session.commit()
                st.success(f"Сохранено! Итог для '{selected_product.name}': **{calculated_result:.3f}** ({selected_product.category})")

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
                else:
                    net = r.current_weight - prod.tare_weight
                    res = net / prod.density / 1000 if net > 0 and prod.density > 0 else 0.0

            history_data.append({
                "Дата и время": r.checked_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Товар": p_name,
                "Введенное значение": r.current_weight,
                "Итог": round(res, 3),
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


# --- ВКЛАДКА 2: СПРАВОЧНИК И ИТЕРАТИВНОЕ РЕДАКТИРОВАНИЕ ---
with tab2:
    st.header("Добавить новый товар")
    with st.form("add_product_form"):
        prod_name = st.text_input("Название товара")
        prod_category = st.selectbox("Категория", ["шт", "вино", "крепкий алкоголь", "сироп"])
        prod_density = st.number_input("Плотность (г/мл)", value=1.0, step=0.01)
        prod_tare = st.number_input("Вес тары (г)", value=0.0, step=10.0)
        
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
    st.write("Вы можете менять данные прямо в таблице ниже, а затем нажать кнопку сохранения.")
    
    products = session.query(Product).all()
    
    if products:
        # Превращаем данные из базы в Pandas DataFrame для редактора
        df_products = pd.DataFrame([{
            "id": p.id,
            "Название": p.name,
            "Категория": p.category,
            "Плотность": p.density,
            "Вес тары": p.tare_weight
        } for p in products])
        
        # Создаем интерактивный редактор таблиц
        edited_df = st.data_editor(df_products, key="product_editor", hide_index=True)
        
        if st.button("💾 Сохранить изменения в таблице"):
            try:
                # Проходим по каждой строчке измененной таблицы и обновляем базу данных
                for index, row in edited_df.iterrows():
                    db_prod = session.query(Product).filter_by(id=row["id"]).first()
                    if db_prod:
                        db_prod.name = row["Название"]
                        db_prod.category = row["Категория"]
                        db_prod.density = row["Плотность"]
                        db_prod.tare_weight = row["Вес тары"]
                session.commit()
                st.success("Все изменения успешно сохранены в базе данных!")
                st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"Ошибка при сохранении: {e}")
    else:
        st.info("Справочник пуст.")

session.close()
