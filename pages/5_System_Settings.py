from src.web.framework.page import init_page, PageSpec
from src.web.pages_impl.system_settings import render

# MUST be the first Streamlit command on this page
init_page(PageSpec(title="设置",icon="📰"))

render()
