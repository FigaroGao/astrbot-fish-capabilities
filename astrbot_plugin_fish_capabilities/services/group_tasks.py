"""Conservative local task filter: no model calls, no message-content logs."""
import re


def task_reason(text):
    text=str(text or '').strip()
    # URLs, video IDs, dates and game scores alone are not arithmetic tasks.
    scrub=re.sub(r'https?://\S+|BV[A-Za-z0-9]{10}|\b\d{4}-\d{1,2}-\d{1,2}\b', '', text)
    expr=re.search(r'\d+(?:\.\d+)?\s*[+＋×*÷/−-]\s*\d+(?:\.\d+)?',scrub)
    if expr and (re.search(r'多少|等于|怎么算|算一下|算算|计算|[=＝?？]',scrub)
                 or re.fullmatch(r'[\d\s.+＋×*÷/−=＝?？()（）-]+',scrub)):
        return 'arithmetic'
    if re.search(r'(?:帮.{0,8})?(?:解方程|解这道题|解一下.{0,5}题|做这道题|求导|求积分|求极限|算一下|算算|计算一下|算出|算题|做数学题|证明.{0,25}定理)',scrub):
        if not re.search(r'别.{0,4}(?:算|做)|不用.{0,4}(?:算|做)|不要.{0,4}(?:算|做)',scrub):return 'math_task'
    if re.search(r'(?:请|帮我|帮忙|给我|你来|能不能|怎么|如何).{0,20}(?:写.{0,8}(?:程序|代码|算法)|调试|修复.{0,8}(?:代码|程序|bug)|推导|解答.{0,8}(?:物理题|化学题|数学题)|设计.{0,8}(?:数据库|系统架构))',scrub,re.I):
        return 'technical_task'
    return None


def skip_group_task(config,event):
    if not config.get('enabled',False) or not config.get('group_skip_complex_tasks',False):return None
    if event.is_private_chat() or event.unified_msg_origin not in config.get('allowed_group_sessions',[]):return None
    return task_reason(event.get_message_str())
