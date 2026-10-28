"""Combine explicitly linked notes with current read-only Canvas data."""
from .policy import CapabilityError

class CourseContext:
    def __init__(self,canvas,notes):self.canvas,self.notes=canvas,notes
    async def courses(self):
        rows=[]
        for page in range(1,6):
            packet=await self.canvas.query('courses',page=page);rows.extend(packet['items'])
            if not packet['has_more']:return rows
        raise CapabilityError('课程超过100条，请先缩小授权课程范围；本次未猜测关联。')
    async def run(self,operation,alias,course_id,message,page=1):
        if operation=='links':return {'links':self.notes.links()}
        if operation=='unlink':return self.notes.unlink(alias,message)
        if operation not in ('view','bind'):raise CapabilityError('仅支持view、bind、links、unlink。')
        courses=await self.courses()
        if operation=='bind':
            matches=[c for c in courses if str(c.get('id'))==course_id]
            if len(matches)!=1:raise CapabilityError('当前Canvas课程列表不能唯一核验这个ID。')
            return self.notes.bind(alias,matches[0],message)
        key=alias.strip().casefold();links=[x for x in self.notes.links() if x['alias']==key] if key else []
        if course_id:
            if links and links[0]['course_id']!=course_id:raise CapabilityError('简称与指定课程ID冲突，未混合两门课。')
            ident=course_id
        else:ident=links[0]['course_id'] if links else None
        matches=[c for c in courses if str(c.get('id'))==ident] if ident else [c for c in courses if key and key in (str(c.get('name','')).casefold(),str(c.get('course_code','')).casefold())]
        if len(matches)!=1:return {'needs_course_confirmation':True,'candidates':courses,'instruction':'请主人确认简称对应的课程名称或代码，不按相似名字自动绑定，不混合不同学期课程。'}
        course=matches[0];result={'course':course,'owner_progress':self.notes.for_course(course),'canvas':{}}
        for action in ('assignments','announcements'):
            try:result['canvas'][action]=await self.canvas.query(action,str(course['id']),page)
            except CapabilityError as e:result['canvas'][action]={'available':False,'reason':str(e)}
        result['instruction']='owner_progress仅为主人过去明确说的进度；canvas仅为学校本次发布的信息。学校上传课件/布置作业不证明主人学完、掌握或交过作业，不相互覆盖。分清来源，没笔记就说没记过；按问题自然简短回答，不倾倒所有资料。仅主人私聊，不用于公开内容，不自动长期记忆或创建提醒。'
        return result
