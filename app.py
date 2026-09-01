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

# --- ВКЛАДКА 1: МАССОВЫЙ ПЕРЕУЧЕТ ---
with tab1:
    st.header("Массовый переучет продукции")
    st.write("Заполните данные по позициям. Посчитанные товары автоматически переместятся в низ таблицы.")
    
    products = session.query(Product).all()
    
    if not products:
        st.warning("Сначала добавьте товары во вкладке «Справочник и Управление»!")
    else:
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
        
        # Смещение заполненных позиций вниз
        df_inventory["_is_counted"] = (df_inventory["Общий вес"] > 0) | (df_inventory["Кол-во тары"] > 0)
        df_inventory = df_inventory.sort_values(by="_is_counted", ascending=True).drop(columns=["_is_counted"])

        edited_inventory = st.data_editor(
            df_inventory,
            column_config={
                "id": None,
                "Наименование": st.column_config.TextColumn("Наименование", disabled=True),
                "Тип": st.column_config.TextColumn("Тип", disabled=True),
                "Кол-во тары": st.column_config.NumberColumn("Кол-во тары", min_value=0.0, step=1.0),
                "Общий вес": st.column_config.NumberColumn("Общий вес / Кол-во", min_value=0.0, step=0.1),
                "Результат": st.column_config.NumberColumn("Результат (нетто)", disabled=True),
            },
            hide_index=True,
            key="mass_inventory_editor",
            num_rows="fixed"
        )
        
        if st.button("💾 Сохранить результаты переучета смены", type="primary"):
            try:
                current_time = datetime.now()
                saved_count = 0
                
                for index, row in edited_inventory.iterrows():
                    if row["Общий вес"] > 0 or row["Кол-во тары"] > 0:
                        prod = session.query(Product).filter_by(id=row["id"]).first()
                        if prod:
                            net_result = 0.0
                            total_tare_weight = row["Кол-во тары"] * prod.tare_weight
                            
                            if prod.category == "шт":
                                net_result = row["Общий вес"]
                            elif prod.category == "л":
                                net_weight = row["Общий вес"] - total_tare_weight
                                net_result = net_weight / prod.density / 1000 if net_weight > 0 and prod.density > 0 else 0.0
                            elif prod.category == "кг":
                                # Если вес тары не задан или равен 0, тара не отнимается
                                net_weight = row["Общий вес"] - total_tare_weight if total_tare_weight > 0 else row["Общий вес"]
                                net_result = net_weight if net_weight > 0 else 0.0

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
        # Группируем записи по датам (YYYY-MM-DD)
        dates_dict = {}
        for r in records:
            date_str = r.checked_at.strftime("%Y-%m-%d %H:%M") # с точностью до минут смены
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
                    "Введенный вес/кол-во": r.current_weight
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
    
    # Условия отображения параметров в зависимости от категории
    if prod_category == "л":
        prod_density = st.number_input("Плотность (г/мл)", value=1.0, step=0.01)
        prod_tare = st.number_input("Вес одной единицы тары (г)", value=0.0, step=10.0)
    elif prod_category == "кг":
        # Для кг плотность скрыта, оставляем только вес тары
        prod_tare = st.number_input("Вес одной единицы тары (г)", value=0.0, step=10.0)
    # Для категории "шт" и плотность, и вес тары автоматически скрыты и равны 0

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
