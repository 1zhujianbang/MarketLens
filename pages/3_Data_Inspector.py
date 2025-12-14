from src.web.framework.page import init_page, PageSpec
from src.web.pages_impl.data_inspector import render

# MUST be the first Streamlit command on this page
init_page(PageSpec(title="数据浏览器",icon="📰"))

render()