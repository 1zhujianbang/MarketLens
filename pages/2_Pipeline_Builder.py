from src.web.framework.page import init_page, PageSpec
from src.web.pages_impl.pipeline_builder import render

# MUST be the first Streamlit command on this page
init_page(PageSpec(title="流水线",icon="📰"))

render()
