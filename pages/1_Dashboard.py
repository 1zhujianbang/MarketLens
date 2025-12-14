from src.web.framework.page import init_page, PageSpec
from src.web.pages_impl.dashboard import render

# MUST be the first Streamlit command on this page
init_page(PageSpec(title="系统概览",icon="📰"))

render()
