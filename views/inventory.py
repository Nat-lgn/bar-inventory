import streamlit as st
from datetime import datetime
from database import Session
from models import Product, InventoryRecord

def render(t, evaluate_expression):
    st.title(t["p1"])
    
    session = Session()
    all_products = session.query(Product).filter_by(is_active=True).order_by(Product.name.asc()).all()
    session.close()
    
    if not all_products:
        st.warning(t["add_products_warn"])
        return
        
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
    
    products = [p for p in all_products if search_query in p.name.lower()] if search_query else all_products

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
                        val_input = st.text_input("Кол-во", value=str(p_data.get("val_str", "")), key=f"val_str_{p.id}", label_visibility="collapsed", placeholder="Кол-во / формула")
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
                        tare_input = st.text_input("Тара", value=str(p_data.get("tare_str", "")), key=f"tare_str_{p.id}", label_visibility="collapsed", placeholder="Тара")
                        tare_count = evaluate_expression(tare_input)
                    with col_weight:
                        weight_input = st.text_input("Вес", value=str(p_data.get("weight_str", "")), key=f"weight_str_{p.id}", label_visibility="collapsed", placeholder="Вес (кг)")
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
                        st.session_state.inv_data[p.id] = {"tare_str": tare_input, "tare": tare_count, "weight_str": weight_input, "weight": total_weight}
                        if p.id in st.session_state.edit_mode:
                            st.session_state.edit_mode.remove(p.id)
                        st.rerun()

        if not st.session_state.keep_completed_in_place and completed_products:
            st.markdown(f"""
                <div style="display: flex; align-items: center; text-align: center; margin: 30px 0 20px 0;">
                    <hr style="flex: 1; border: none; border-top: 2px dashed #f49e92;">
                    <span style="padding: 0 15px; color: #f49e92; font-weight: bold; font-size: 15px;">{t['barrier_title']}</span>
                    <hr style="flex: 1; border: none; border-top: 2px dashed #f49e92;">
                </div>
            """, unsafe_allow_html=True)

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
