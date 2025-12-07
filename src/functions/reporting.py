from typing import List, Dict, Any
from ..core.registry import register_tool

@register_tool(
    name="generate_markdown_report",
    description="根据事件列表生成 Markdown 格式的简报",
    category="Reporting"
)
def generate_markdown_report(events_list: List[Dict[str, Any]], title: str = "Market Analysis Report") -> str:
    """
    生成 Markdown 报告
    """
    if not events_list:
        return f"# {title}\n\nNo events found."
        
    lines = [f"# {title}", ""]
    lines.append(f"**Total Events Extracted:** {len(events_list)}")
    lines.append("")
    
    # 简单的按时间排序
    sorted_events = sorted(events_list, key=lambda x: x.get('published_at') or "", reverse=True)
    
    for i, ev in enumerate(sorted_events, 1):
        abstract = ev.get('abstract', 'No Title')
        summary = ev.get('event_summary', '')
        entities = ', '.join(ev.get('entities', []))
        source = ev.get('source', 'Unknown')
        ts = ev.get('published_at', 'Unknown Time')
        
        lines.append(f"### {i}. {abstract}")
        lines.append(f"- **时间:** {ts}")
        lines.append(f"- **来源:** {source}")
        lines.append(f"- **实体:** {entities}")
        lines.append(f"- **摘要:** {summary}")
        lines.append("---")
        
    return "\n".join(lines)

