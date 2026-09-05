import streamlit as st
import pandas as pd
from database import Session
from models import Product

def render(t):
    st.title(t["catalog_title"])
    
    session = Session()

    with st.expander(t["density_expander"], expanded=False):
        st.write(t["density_desc"])
        with st.form("density_calc_form"):
            drink_name = st.text_input(t["drink_name_label"])
            total_weight = st.number_input(t["total_weight_label"], min_value=0.0, step=0.01)
            volume_ml = st.number_input(t["volume_label"], min_value=0.0, step=10.0, value=750.0)
            submit_calc = st.form_submit_button(t["calc_density_btn"])
            
            if submit_calc:
                if not drink_name.strip():
                    st.warning("Введите название.")
                elif total_weight <= 0 or volume_ml <= 0:
                    st.warning("Введите корректные значения.")
                else:
                    st.session_state["temp_drink_name"] = drink_name.strip()
                    st.session_state["temp_total_weight"] = total_weight
                    st.session_state["temp_volume_ml"] = volume_ml
                    st.session_state["density_manual_needed"] = True

        if st.session_state.get("density_manual_needed", False):
            st.divider()
            st.subheader(t["manual_tare_title"])
            with st.form("manual_bottle_form"):
                manual_tare = st.number_input(t["manual_tare_label"], min_value=0.0, step=0.001)
                submit_manual = st.form_submit_button(t["confirm_tare_btn"])
                
                if submit_manual:
                    d_name = st.session_state["temp_drink_name"]
                    t_weight = st.session_state["temp_total_weight"]
                    vol = st.session_state["temp_volume_ml"]
                    
                    net_weight = t_weight - manual_tare
                    volume_l = vol / 1000.0
                    density = net_weight / volume_l if volume_l > 0 else 1.0
                    
                    try:
                        existing = session.query(Product).filter_by(name=d_name).first()
                        if existing:
                            existing.density = density
                            existing.tare_weight = manual_tare
                            existing.is_active = True
                        else:
                            new_p = Product(
                                name=d_name,
                                category="л",
                                density=density,
                                tare_weight=manual_tare,
                                is_active=True
                            )
                            session.add(new_p)
                        session.commit()
                        st.success(f"✅ {d_name} saved! Density: {density:.3f}, Tare: {manual_tare}")
                        st.session_state["density_manual_needed"] = False
                        session.close()
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Error: {e}")

    st.divider()

    st.header(t["import_header"])
    st.write(t["import_desc"])
    
    uploaded_file = st.file_uploader(t["file_picker"], type=["xlsx", "csv"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)
            
            st.dataframe(df_upload, use_container_width=True)
            
            if st.button(t["import_btn"], type="primary"):
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
                        existing_product.is_active = True
                        updated_count += 1
                    else:
                        new_product = Product(
                            name=name,
                            category=category,
                            density=density,
                            tare_weight=tare_weight,
                            is_active=True
                        )
                        session.add(new_product)
                        added_count += 1
                
                session.commit()
                st.success(f"Imported: {added_count}, Updated: {updated_count}")
                session.close()
                st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()

    st.header(t["editor_header"])
    st.write(t["editor_desc"])

    with st.expander(t["add_new_product_expander"], expanded=False):
        with st.form("add_single_product_form"):
            new_p_name = st.text_input(t["new_prod_name"])
            new_p_cat = st.selectbox(t["new_prod_cat"], options=["л", "кг", "шт"])
            col_nc1, col_nc2 = st.columns(2)
            with col_nc1:
                new_p_density = st.number_input(t["new_prod_density"], min_value=0.01, value=1.0, step=0.01)
            with col_nc2:
                new_p_tare = st.number_input(t["new_prod_tare"], min_value=0.0, value=0.0, step=0.001)
            
            submit_new_p = st.form_submit_button(t["add_prod_btn"], type="primary")
            if submit_new_p:
                if not new_p_name.strip():
                    st.warning("Введите название товара.")
                else:
                    try:
                        exist_p = session.query(Product).filter_by(name=new_p_name.strip()).first()
                        if exist_p:
                            exist_p.is_active = True
                            exist_p.category = new_p_cat
                            exist_p.density = new_p_density
                            exist_p.tare_weight = new_p_tare
                        else:
                            prod_item = Product(
                                name=new_p_name.strip(),
                                category=new_p_cat,
                                density=new_p_density,
                                tare_weight=new_p_tare,
                                is_active=True
                            )
                            session.add(prod_item)
                        session.commit()
                        st.success(f"✅ Товар '{new_p_name}' успешно добавлен!")
                        session.close()
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка: {e}")
    
    catalog_search = st.text_input(t["search_catalog"], value="", placeholder="...").strip().lower()
    
    all_products_query = session.query(Product).order_by(Product.is_active.desc(), Product.name.asc()).all()
    
    if catalog_search:
        filtered_products = [p for p in all_products_query if catalog_search in p.name.lower()]
    else:
        filtered_products = all_products_query

    if not filtered_products:
        st.info("В справочнике пока нет товаров.")
    else:
        if "catalog_form_data" not in st.session_state:
            st.session_state.catalog_form_data = {}

        col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([2.5, 1, 1, 1, 0.8], vertical_alignment="center")
        with col_h1:
            st.markdown(f"<p style='font-size: 13px; color: gray; margin-bottom: -5px;'><b>{t['lbl_name']}</b></p>", unsafe_allow_html=True)
        with col_h2:
            st.markdown(f"<p style='font-size: 13px; color: gray; margin-bottom: -5px;'><b>{t['lbl_cat']}</b></p>", unsafe_allow_html=True)
        with col_h3:
            st.markdown(f"<p style='font-size: 13px; color: gray; margin-bottom: -5px;'><b>{t['lbl_density']}</b></p>", unsafe_allow_html=True)
        with col_h4:
            st.markdown(f"<p style='font-size: 13px; color: gray; margin-bottom: -5px;'><b>{t['lbl_tare']}</b></p>", unsafe_allow_html=True)
        with col_h5:
            st.markdown(f"<p style='font-size: 13px; color: gray; margin-bottom: -5px;'><b>{t['lbl_active']}</b></p>", unsafe_allow_html=True)

        for p in filtered_products:
            with st.container(border=True):
                col_name, col_cat, col_density, col_tare, col_active = st.columns([2.5, 1, 1, 1, 0.8], vertical_alignment="center")
                
                with col_name:
                    new_name = st.text_input(f"Название #{p.id}", value=p.name, key=f"c_name_{p.id}", label_visibility="collapsed")
                
                with col_cat:
                    cat_index = ["л", "кг", "шт"].index(p.category) if p.category in ["л", "кг", "шт"] else 0
                    new_cat = st.selectbox(f"Категория #{p.id}", options=["л", "кг", "шт"], index=cat_index, key=f"c_cat_{p.id}", label_visibility="collapsed")
                
                with col_density:
                    if new_cat == "л":
                        new_density = st.number_input(f"Плотность #{p.id}", value=float(p.density or 1.0), step=0.01, key=f"c_density_{p.id}", label_visibility="collapsed")
                    else:
                        st.markdown("<p style='text-align: center; color: gray; margin-top: 8px;'>—</p>", unsafe_allow_html=True)
                        new_density = 1.0
                
                with col_tare:
                    if new_cat in ["л", "кг"]:
                        new_tare = st.number_input(f"Тара #{p.id}", value=float(p.tare_weight or 0.0), step=0.001, key=f"c_tare_{p.id}", label_visibility="collapsed")
                    else:
                        st.markdown("<p style='text-align: center; color: gray; margin-top: 8px;'>—</p>", unsafe_allow_html=True)
                        new_tare = 0.0
                
                with col_active:
                    new_active = st.checkbox("Активен", value=bool(p.is_active), key=f"c_active_{p.id}")

                st.session_state.catalog_form_data[p.id] = {
                    "name": new_name,
                    "category": new_cat,
                    "density": new_density if new_cat == "л" else 1.0,
                    "tare_weight": new_tare if new_cat in ["л", "кг"] else 0.0,
                    "is_active": new_active
                }

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(t["save_catalog_btn"], type="primary", use_container_width=True):
            try:
                for p_id, vals in st.session_state.catalog_form_data.items():
                    db_prod = session.query(Product).filter_by(id=p_id).first()
                    if db_prod:
                        db_prod.name = vals["name"].strip()
                        db_prod.category = vals["category"]
                        db_prod.density = vals["density"]
                        db_prod.tare_weight = vals["tare_weight"]
                        db_prod.is_active = vals["is_active"]
                
                session.commit()
                st.success("Все изменения успешно сохранены в базе данных!")
                session.close()
                st.rerun()
            except Exception as e:
                session.rollback()
                session.close()
                st.error(f"Ошибка сохранения: {e}")

    session.close()
