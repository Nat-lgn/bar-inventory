import streamlit as st
import pandas as pd
from database import Session
from models import Product, InventoryRecord

def render(t):
    st.title(t["tools_title"])
    st.write(t["tools_desc"])
    st.divider()

    session = Session()
    products = session.query(Product).filter_by(is_active=True).all()
    records = session.query(InventoryRecord).order_by(InventoryRecord.checked_at.asc()).all()

    if not products:
        st.info("В справочнике нет активных товаров для анализа.")
    elif not records:
        st.warning(t["no_history_for_analysis"])
    else:
        analysis_data = []
        dead_stock_count = 0

        prod_records_map = {}
        for r in records:
            if r.product_id not in prod_records_map:
                prod_records_map[r.product_id] = []
            prod_records_map[r.product_id].append(r.current_weight)

        for p in products:
            p_history = prod_records_map.get(p.id, [])
            last_stock = p_history[-1] if p_history else 0.0
            
            is_dead = False
            if len(p_history) >= 2:
                if len(set(p_history[-2:])) == 1 and p_history[-1] > 0:
                    is_dead = True
            
            if is_dead:
                dead_stock_count += 1
                status_str = t["status_dead"]
            else:
                status_str = t["status_active"]

            analysis_data.append({
                t["col_product"]: p.name,
                t["col_category"]: p.category,
                t["col_last_stock"]: f"{last_stock:.3f}",
                t["col_status"]: status_str
            })

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(t["stat_total"], len(products))
        with col_m2:
            st.metric(t["stat_dead"], dead_stock_count)

        st.divider()

        df_analysis = pd.DataFrame(analysis_data)
        st.dataframe(df_analysis, use_container_width=True, hide_index=True)

    session.close()
