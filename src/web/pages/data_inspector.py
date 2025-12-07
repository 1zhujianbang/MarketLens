import streamlit as st
import pandas as pd
from src.web import utils

def render():
    st.title("🕵️ Data Inspector")
    
    tab1, tab2 = st.tabs(["Entities & Events", "Raw News"])
    
    with tab1:
        st.subheader("Entities")
        entities_data = utils.load_entities()
        
        if entities_data:
            # 转换为 DataFrame
            df_ent = pd.DataFrame.from_dict(entities_data, orient='index')
            df_ent.reset_index(inplace=True)
            df_ent.rename(columns={'index': 'Entity Name'}, inplace=True)
            
            st.dataframe(df_ent, use_container_width=True, hide_index=True)
        else:
            st.info("No entities data found.")
            
        st.subheader("Events")
        events_data = utils.load_events()
        
        if events_data:
            df_evt = pd.DataFrame.from_dict(events_data, orient='index')
            # 展平
            df_evt['abstract'] = df_evt.index
            cols = ['abstract', 'event_summary', 'entities', 'sources', 'first_seen']
            # 过滤存在的列
            cols = [c for c in cols if c in df_evt.columns]
            st.dataframe(df_evt[cols], use_container_width=True, hide_index=True)
        else:
            st.info("No events data found.")

    with tab2:
        st.subheader("Raw News Data")
        
        # 使用缓存获取文件列表
        files = utils.get_raw_news_files()
        
        if files:
            # 排序：最近修改的在前
            files = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
            
            selected_file = st.selectbox("Select File", files, format_func=lambda x: x.name)
            
            if selected_file:
                # 使用缓存加载文件内容
                news_items = utils.load_raw_news_file(selected_file)
                
                if news_items:
                    df_news = pd.DataFrame(news_items)
                    st.dataframe(df_news, use_container_width=True)
                else:
                    st.warning("File is empty or invalid.")
        else:
            st.info("No raw news directory found or no files.")
