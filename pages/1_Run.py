from src.web.framework.page import init_page, PageSpec
from src.web.pages_impl.run import render

# MUST be the first Streamlit command on this page
init_page(PageSpec(title="运行流程", icon="🚀"))

render()
