import streamlit as st
import pandas as pd
import io
from database import Session
from models import Product, InventoryRecord

def render(t):
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
