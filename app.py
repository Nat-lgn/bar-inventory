import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime
from database import Session, engine
from models import Base, Product, InventoryRecord, User
from locales import TEXTS

def init_default_user(session):
    existing_user = session.query(User).first()
    if not existing_user:
        default_user = User(username="admin", password="bar123")
        session.add(default_user)
        session.commit()

def evaluate_expression(expr_str):
    if expr_str is None:
        return 0.0
    str_val = str(expr_str).strip().replace(',', '.')
    if not str_val:
        return 0.0
    try:
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in str_val):
            return float(str_val)
        result = eval(str_val, {"__builtins__": {}}, {})
        return float(result)
    except Exception:
        try:
            return float(str_val)
        except ValueError:
            return 0.0

Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="Инвентаризация бара / Облік бару", page_icon="🍹", layout="wide")

session = Session()
init_default_user(session)
session.close()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "lang" not in st.session_state:
    st.session_state.lang = "ru"
if "keep_completed_in_place" not in st.session_state:
    st.session_state.keep_completed_in_place = False

# --- ВЫБОР ЯЗЫКА В БОКОВОМ МЕНЮ ---
selected_lang_label = st.sidebar.selectbox("🌍 Язык / Мова", ["Русский", "Українська"], index=0 if st.session_state.lang == "ru" else 1)
st.session_state.lang = "ru" if selected_lang_label == "Русский" else "uk"
t = TEXTS[st.session_state.lang]

if not st.session_state.authenticated:
    st.title(t["login_title"])
    
    auth_tab1, auth_tab2 = st.tabs([t["tab_login"], t["tab_signup"]])
    
    with auth_tab1:
        with st.form("login_form"):
            username_input = st.text_input("Логин / Логін", key="login_user")
            password_input = st.text_input("Пароль", type="password", key="login_pass")
            submit_login = st.form_submit_button(t["login_btn"])
            
            if submit_login:
                session = Session()
                user = session.query(User).filter_by(username=username_input.strip(), password=password_input).first()
                session.close()
                
                if user:
                    st.session_state.authenticated = True
                    st.session_state.username = user.username
                    st.success(t["success_login"])
                    st.rerun()
                else:
                    st.error(t["error_login"])
                    
    with auth_tab2:
        with st.form("signup_form"):
            new_user_input = st.text_input("Логин / Логін", key="signup_user")
            new_pass_input = st.text_input("Пароль", type="password", key="signup_pass")
            confirm_pass_input = st.text_input("Подтвердите пароль / Підтвердьте пароль", type="password", key="signup_confirm")
            submit_signup = st.form_submit_button(t["signup_btn"])
            
            if submit_signup:
                if not new_user_input.strip() or not new_pass_input.strip():
                    st.warning(t["empty_creds"])
                elif new_pass_input != confirm_pass_input:
                    st.warning(t["pass_mismatch"])
                else:
                    session = Session()
                    existing_user = session.query(User).filter_by(username=new_user_input.strip()).first()
                    if existing_user:
                        st.warning(t["user_exists"])
                    else:
                        new_user = User(username=new_user_input.strip(), password=new_pass_input)
                        session.add(new_user)
                        session.commit()
                        st.session_state.authenticated = True
                        st.session_state.username = new_user.username
                        st.success(t["signup_success"])
                        st.rerun()
                    session.close()
    st.stop()

st.sidebar.title(t["menu_title"])
st.sidebar.caption(f"{t['logged_in']}: **{st.session_state.username}**")
st.sidebar.divider()

# Инициализация текущей страницы
if "current_page" not in st.session_state:
    st.session_state.current_page = t["p1"]

st.sidebar.markdown(f"**{t['nav']}**")

# Навигация с помощью красивых больших кнопок
nav_items = [
    t["p1"],
    t["p2"],
    t["p3"],
    t["p4"]
]

for item in nav_items:
    is_active = (st.session_state.current_page == item)
    btn_type = "primary" if is_active else "secondary"
    if st.sidebar.button(item, key=f"nav_btn_{item}", use_container_width=True, type=btn_type):
        if st.session_state.current_page != item:
            st.session_state.current_page = item
            st.rerun()

page = st.session_state.current_page

st.sidebar.divider()
if st.sidebar.button(t["logout"], key="logout_button_sidebar", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.rerun()

# --- СТРАНИЦА 1: ПЕРЕУЧЕТ ПРОДУКЦИИ ---
if page == t["p1"]:
    st.title(t["p1"])
    
    session = Session()
    all_products = session.query(Product).filter_by(is_active=True).order_by(Product.name.asc()).all()
    session.close()
    
    if not all_products:
        st.warning(t["add_products_warn"])
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

        search_query = st.text_input("🔍 Поиск / Пошук", value="", placeholder="...").strip().lower()
        
        if search_query:
            products = [p for p in all_products if search_query in p.name.lower()]
        else:
            products = all_products

        total_count = len(all_products)
        completed_all = [p for p in all_products if is_completed(p)]
        completed_count = len(completed_all)
        progress_val = completed_count / total_count if total_count > 0 else 0.0

        st.subheader(f"{t['progress_text']}: {completed_count} / {total_count} {t['pos_word']}")
        st.progress(progress_val)
        st.divider()

        if not products:
            st.info("Ничего не найдено / Нічого не знайдено.")
        else:
            if st.session_state.keep_completed_in_place:
                render_products = products
            else:
                uncompleted_products = [p for p in products if not is_completed(p)]
                completed_products = [p for p in products if is_completed(p)]
                render_products = uncompleted_products

            for p in render_products:
                with st.container(border=True):
                    col_info, col_tare, col_weight, col_res = st.columns([2.2, 1, 1.2, 1.2], vertical_alignment="center")
                    
                    with col_info:
                        st.markdown(f"**{p.name}** <span style='font-size:12px; color:gray;'>({p.category})</span>", unsafe_allow_html=True)
                    
                    p_data = st.session_state.inv_data.get(p.id, {})
                    is_075 = "0.75" in p.name or "0,75" in p.name
                    
                    if p.category == "шт":
                        with col_tare:
                            st.empty()
                        with col_weight:
                            val_input = st.text_input(
                                "Кол-во", 
                                value=str(p_data.get("val_str", "")), 
                                key=f"val_str_{p.id}",
                                label_visibility="collapsed",
                                placeholder="Кол-во / формула"
                            )
                        val = evaluate_expression(val_input)
                        with col_res:
                            st.markdown(f"<div style='text-align: right; font-weight: bold; color: #4CAF50;'>{val} шт</div>", unsafe_allow_html=True)
                        
                        if val_input != p_data.get("val_str"):
                            st.session_state.inv_data[p.id] = {"val_str": val_input, "val": val}
                            if p.id in st.session_state.edit_mode:
                                st.session_state.edit_mode.remove(p.id)
                            st.rerun()
                    
                    elif p.category in ["кг", "л"]:
                        with col_tare:
                            tare_input = st.text_input(
                                "Тара", 
                                value=str(p_data.get("tare_str", "")), 
                                key=f"tare_str_{p.id}",
                                label_visibility="collapsed",
                                placeholder="Тара"
                            )
                            tare_count = evaluate_expression(tare_input)
                        with col_weight:
                            weight_input = st.text_input(
                                "Вес", 
                                value=str(p_data.get("weight_str", "")), 
                                key=f"weight_str_{p.id}",
                                label_visibility="collapsed",
                                placeholder="Вес (кг)"
                            )
                            total_weight = evaluate_expression(weight_input)
                        with col_res:
                            total_tare_weight = tare_count * p.tare_weight
                            net_result = 0.0
                            if p.category == "л":
                                if is_075:
                                    open_net = total_weight - total_tare_weight if total_weight > total_tare_weight else 0.0
                                    open_vol = open_net / p.density if p.density > 0 else 0.0
                                    net_result = (0.75 * tare_count) + open_vol
                                else:
                                    net_weight = total_weight - total_tare_weight if total_weight > total_tare_weight else 0.0
                                    net_result = net_weight / p.density if p.density > 0 else 0.0
                            elif p.category == "кг":
                                net_weight = total_weight - total_tare_weight if total_weight > total_tare_weight else total_weight
                                net_result = net_weight if net_weight > 0 else 0.0
                            
                            st.markdown(f"<div style='text-align: right; font-weight: bold; font-size: 15px; color: #4CAF50;'>{net_result:.3f} {p.category}</div>", unsafe_allow_html=True)
                        
                        if tare_input != p_data.get("tare_str") or weight_input != p_data.get("weight_str"):
                            st.session_state.inv_data[p.id] = {
                                "tare_str": tare_input, 
                                "tare": tare_count, 
                                "weight_str": weight_input, 
                                "weight": total_weight
                            }
                            if p.id in st.session_state.edit_mode:
                                st.session_state.edit_mode.remove(p.id)
                            st.rerun()

            if not st.session_state.keep_completed_in_place and completed_products:
                st.markdown(
                    f"""
                    <div style="display: flex; align-items: center; text-align: center; margin: 30px 0 20px 0;">
                        <hr style="flex: 1; border: none; border-top: 2px dashed #f49e92;">
                        <span style="padding: 0 15px; color: #f49e92; font-weight: bold; font-size: 15px;">{t['barrier_title']}</span>
                        <hr style="flex: 1; border: none; border-top: 2px dashed #f49e92;">
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

                for p in completed_products:
                    d = st.session_state.inv_data.get(p.id, {})
                    res_str = ""
                    is_075 = "0.75" in p.name or "0,75" in p.name
                    if p.category == "шт":
                        res_str = f"{d.get('val', 0)} шт"
                    else:
                        t_val = d.get("tare", 0.0) or 0.0
                        w_val = d.get("weight", 0.0) or 0.0
                        total_tare_weight = t_val * p.tare_weight
                        if p.category == "л":
                            if is_075:
                                open_net = (w_val - total_tare_weight) if (w_val - total_tare_weight) > 0 else 0.0
                                open_vol = open_net / p.density if p.density > 0 else 0.0
                                net = (0.75 * t_val) + open_vol
                            else:
                                net_kg = (w_val - total_tare_weight) if (w_val - total_tare_weight) > 0 else 0.0
                                net = net_kg / p.density if p.density > 0 else 0.0
                        else:
                            net = (w_val - total_tare_weight) if total_tare_weight > 0 else w_val
                        res_str = f"{net:.3f} {p.category}"

                    if st.button(f"✅ {p.name} — {res_str}", key=f"edit_btn_{p.id}"):
                        st.session_state.edit_mode.add(p.id)
                        st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(t["save_results"], type="primary"):
            try:
                current_time = datetime.now()
                saved_count = 0
                session = Session()
                
                for p in all_products:
                    data = st.session_state.inv_data.get(p.id, {})
                    if p.category == "шт":
                        val = data.get("val", 0.0)
                        if val is not None and val > 0:
                            session.add(InventoryRecord(product_id=p.id, current_weight=val, checked_at=current_time))
                            saved_count += 1
                    else:
                        w = data.get("weight", 0.0)
                        if w is not None and w > 0:
                            session.add(InventoryRecord(product_id=p.id, current_weight=w, checked_at=current_time))
                            saved_count += 1
                
                session.commit()
                session.close()
                if saved_count > 0:
                    st.success(f"{t['save_success']}: {saved_count}!")
                    st.session_state.inv_data = {}
                    st.session_state.edit_mode = set()
                    st.rerun()
                else:
                    st.warning(t["save_empty"])
            except Exception as e:
                session.rollback()
                session.close()
                st.error(f"Error: {e}")

# --- СТРАНИЦА 2: ИСТОРИЯ ПО ДАТАМ И ЭКСПОРТ В EXCEL ---
elif page == t["p2"]:
    st.title(t["history_title"])
    st.write(t["history_sub"])
    
    session = Session()
    records = session.query(InventoryRecord).order_by(InventoryRecord.checked_at.desc()).all()
    
    if records:
        dates_dict = {}
        for r in records:
            date_str = r.checked_at.strftime("%Y-%m-%d %H:%M")
            if date_str not in dates_dict:
                dates_dict[date_str] = []
            dates_dict[date_str].append(r)
            
        for date_str, session_records in dates_dict.items():
            with st.expander(f"📅 {date_str} (poz: {len(session_records)})"):
                history_data = []
                for r in session_records:
                    prod = session.query(Product).filter_by(id=r.product_id).first()
                    p_name = prod.name if prod else "Deleted"
                    p_cat = prod.category if prod else ""
                    
                    history_data.append({
                        "Товар": p_name,
                        "Тип": p_cat,
                        "Значение": r.current_weight
                    })
                
                df_history = pd.DataFrame(history_data)
                st.dataframe(df_history, use_container_width=True)
                
                col_dl, col_del = st.columns([2, 1])
                with col_dl:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_history.to_excel(writer, index=False, sheet_name='Report')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label=f"📥 {t['download_report']} {date_str} (.xlsx)",
                        data=excel_data,
                        file_name=f"report_{date_str.replace(':', '-')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_{date_str}"
                    )
                with col_del:
                    if st.button(t["delete_btn"], key=f"del_rec_{date_str}", type="secondary"):
                        try:
                            record_ids = [r.id for r in session_records]
                            session.query(InventoryRecord).filter(InventoryRecord.id.in_(record_ids)).delete(synchronize_session=False)
                            session.commit()
                            st.success(t["delete_success"])
                            session.close()
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Error: {e}")
    else:
        st.info(t["history_empty"])
    session.close()

# --- СТРАНИЦА 3: СПРАВОЧНИК ---
elif page == t["p3"]:
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
    
    catalog_search = st.text_input(t["search_catalog"], value="", placeholder="...").strip().lower()
    
    # Сортируем: сначала активные (is_active DESC), затем по имени (name ASC)
    all_products_query = session.query(Product).order_by(Product.is_active.desc(), Product.name.asc()).all()
    
    if catalog_search:
        filtered_products = [p for p in all_products_query if catalog_search in p.name.lower()]
    else:
        filtered_products = all_products_query
    
    df_products = pd.DataFrame([{
        "id": p.id,
        "Название": p.name,
        "Категория": p.category,
        "Плотность": p.density,
        "Вес тары (кг)": p.tare_weight,
        "Активен": p.is_active
    } for p in filtered_products]) if filtered_products else pd.DataFrame(columns=["id", "Название", "Категория", "Плотность", "Вес тары (кг)", "Активен"])
    
    # Функция для визуального оформления: неактивные строки делаем бледными и прозрачными
    def highlight_inactive(row):
        if not row["Активен"]:
            return ['color: #999999; background-color: rgba(200, 200, 200, 0.15);'] * len(row)
        return [''] * len(row)

    styled_df = df_products.style.apply(highlight_inactive, axis=1)

    edited_df = st.data_editor(
        styled_df, 
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "Категория": st.column_config.SelectboxColumn("Категория", options=["шт", "л", "кг"], required=True),
            "Активен": st.column_config.CheckboxColumn("Активен")
        }
    )
    
    if st.button(t["save_catalog_btn"], type="primary"):
        try:
            existing_ids = {p.id for p in all_products_query}
            current_ui_ids = set()
            
            for index, row in edited_df.iterrows():
                row_id = row.get("id")
                name = str(row.get("Название", "")).strip()
                category = str(row.get("Категория", "шт")).strip()
                is_active_val = bool(row.get("Активен", True))
                
                if not name or name == "nan":
                    continue
                
                density = float(row.get("Плотность", 1.0)) if pd.notna(row.get("Плотность")) else 1.0
                tare_weight = float(row.get("Вес тары (кг)", 0.0)) if pd.notna(row.get("Вес тары (кг)")) else 0.0
                
                if pd.notna(row_id) and int(row_id) in existing_ids:
                    db_prod = session.query(Product).filter_by(id=int(row_id)).first()
                    if db_prod:
                        db_prod.name = name
                        db_prod.category = category
                        db_prod.density = density
                        db_prod.tare_weight = tare_weight
                        db_prod.is_active = is_active_val
                        current_ui_ids.add(db_prod.id)
                else:
                    new_prod = Product(
                        name=name,
                        category=category,
                        density=density,
                        tare_weight=tare_weight,
                        is_active=is_active_val
                    )
                    session.add(new_prod)
                    session.flush()
                    current_ui_ids.add(new_prod.id)
            
            for p in all_products_query:
                if catalog_search and catalog_search not in p.name.lower():
                    continue
                if p.id not in current_ui_ids:
                    p.is_active = False
                    
            session.commit()
            st.success("Saved successfully!")
            session.close()
            st.rerun()
            
        except Exception as e:
            session.rollback()
            session.close()
            st.error(f"Error: {e}")

    session.close()
# --- СТРАНИЦА 4: ЛИЧНЫЙ КАБИНЕТ ---
elif page == t["p4"]:
    st.title(t["cabinet_title"])
    st.write(t["cabinet_desc"])

    st.subheader(t["settings_title"])
    st.session_state.keep_completed_in_place = st.checkbox(
        t["keep_in_place_label"],
        value=st.session_state.keep_completed_in_place
    )

    st.divider()
    
    with st.expander("📖 Гайд / Посібник", expanded=False):
        st.markdown(t["guide_text"])
    
    st.divider()
    
    session = Session()
    
    with st.form("change_password_form"):
        st.subheader(t["change_pass_title"])
        new_password = st.text_input(t["new_pass_label"], type="password")
        confirm_password = st.text_input(t["confirm_pass_label"], type="password")
        submit_pass = st.form_submit_button(t["update_pass_btn"])
        
        if submit_pass:
            if new_password and new_password == confirm_password:
                current_user = session.query(User).filter_by(username=st.session_state.username).first()
                if current_user:
                    current_user.password = new_password
                    session.commit()
                    st.success(t["pass_success"])
                else:
                    st.warning("User not found.")
            else:
                st.warning("Passwords do not match or empty.")

    st.divider()

    with st.form("add_user_form"):
        st.subheader(t["add_emp_title"])
        new_username = st.text_input(t["emp_login"])
        new_user_password = st.text_input(t["emp_pass"], type="password")
        submit_user = st.form_submit_button(t["create_emp_btn"])
        
        if submit_user:
            if new_username.strip() and new_user_password.strip():
                try:
                    user_exists = session.query(User).filter_by(username=new_username.strip()).first()
                    if user_exists:
                        st.warning("User already exists.")
                    else:
                        add_user = User(username=new_username.strip(), password=new_user_password.strip())
                        session.add(add_user)
                        session.commit()
                        st.success(t["emp_success"])
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Fill all fields.")

    session.close()
