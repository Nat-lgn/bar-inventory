import streamlit as st
from datetime import datetime
from database import Session, engine
from models import Base, Product, InventoryRecord

# Автоматически создаем таблицы в базе данных
Base.metadata.create_all(bind=engine)

# Открываем сессию для работы с базой
session = Session()

st.title("🍹 Система инвентаризации бара")

# Создаем вкладки, чтобы интерфейс был аккуратным и разделенным
tab1, tab2 = st.tabs(["📝 Проведение переучета", "📚 Справочник товаров"])

# --- ВКЛАДКА 1: ПЕРЕУЧЕТ ---
with tab1:
    st.header("Ввод данных переучета")

    # Достаем все товары из базы для выпадающего списка
    products = session.query(Product).all()

    if not products:
        st.warning("Сначала добавьте товары во вкладке «Справочник товаров»!")
    else:
        with st.form("inventory_form"):
            # Создаем словарик для удобного выбора товара по имени
            product_options = {p.name: p for p in products}
            selected_product_name = st.selectbox("Выберите товар", list(product_options.keys()))

            # Получаем выбранный объект товара
            selected_product = product_options[selected_product_name]

            # Показываем подсказку о типе товара
            st.info(
                f"Категория товара: **{selected_product.category}** | Плотность: {selected_product.density} | Вес тары: {selected_product.tare_weight}г")

            # Динамические поля в зависимости от категории (как в нашей таблице!)
            input_value = 0.0

            if selected_product.category == "шт":
                input_value = st.number_input("Количество (шт)", min_value=0.0, step=1.0)
            else:
                # Для вина, крепкого алкоголя и сиропов просим ввести общий вес брутто
                input_value = st.number_input("Общий вес с тарой (г)", min_value=0.0, step=10.0)

            submit_inventory = st.form_submit_button("Сохранить результат переучета")

            if submit_inventory:
                # Математика расчета (наша логика из Google Таблиц):
                calculated_result = 0.0

                if selected_product.category == "шт":
                    calculated_result = input_value
                else:
                    # Формула: (Общий вес - Вес тары) / Плотность / 1000 (перевод граммов в литры)
                    net_weight = input_value - selected_product.tare_weight
                    if net_weight > 0 and selected_product.density > 0:
                        calculated_result = net_weight / selected_product.density / 1000
                    else:
                        calculated_result = 0.0

                # Сохраняем в таблицу inventory_records
                new_record = InventoryRecord(
                    product_id=selected_product.id,
                    current_weight=input_value,
                    checked_at=datetime.now()
                )
                session.add(new_record)
                session.commit()

                st.success(
                    f"Записано! Итог для '{selected_product.name}': **{calculated_result:.3f}** ({selected_product.category})")

    # Выводим историю последних переучетов
    st.subheader("📊 Последние сохраненные результаты")
    records = session.query(InventoryRecord).order_by(InventoryRecord.checked_at.desc()).limit(10).all()

    if records:
        history_data = []
        for r in records:
            prod = session.query(Product).filter_by(id=r.product_id).first()
            p_name = prod.name if prod else "Удаленный товар"
            p_cat = prod.category if prod else ""

            # Считаем итоговое значение для отображения в истории
            res = 0.0
            if prod:
                if prod.category == "шт":
                    res = r.current_weight
                else:
                    net = r.current_weight - prod.tare_weight
                    if net > 0 and prod.density > 0:
                        res = net / prod.density / 1000

            history_data.append({
                "Дата и время": r.checked_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Товар": p_name,
                "Введенное значение": r.current_weight,
                "Итог": round(res, 3),
                "Ед. изм.": p_cat
            })
        st.dataframe(history_data, use_container_width=True)
    else:
        st.info("История переучетов пока пуста.")

# --- ВКЛАДКА 2: СПРАВОЧНИК ---
with tab2:
    st.header("Добавить новый товар в справочник")

    with st.form("add_product_form"):
        prod_name = st.text_input("Название товара")
        prod_category = st.selectbox("Категория", ["шт", "вино", "крепкий алкоголь", "сироп"])
        prod_density = st.number_input("Плотность (г/мл)", value=1.0, step=0.01)
        prod_tare = st.number_input("Вес тары (г)", value=0.0, step=10.0)

        submit_product = st.form_submit_button("Сохранить товар в справочник")

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
                    st.success(f"Товар '{prod_name}' успешно добавлен!")
                    st.rerun()  # Перезагружаем страницу, чтобы товар сразу появился в списках
                except Exception as e:
                    session.rollback()
                    st.error(f"Ошибка (возможно, такой товар уже есть): {e}")
            else:
                st.warning("Название товара не может быть пустым!")

    st.header("📦 Текущий справочник товаров")
    products = session.query(Product).all()

    if products:
        data_for_table = [{
            "ID": p.id,
            "Название": p.name,
            "Категория": p.category,
            "Плотность": p.density,
            "Вес тары": p.tare_weight
        } for p in products]
        st.dataframe(data_for_table, use_container_width=True)
    else:
        st.info("В справочнике пока нет товаров.")

# Закрываем сессию базы данных
session.close()