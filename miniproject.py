from fastapi import FastAPI, HTTPException, Request, Query, status
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from datetime import datetime
import re

app = FastAPI()

tasks_db = [
    {
        "id": 1,
        "title": "Thiết kế database",
        "description": "Thiết kế CSDL cho dự án",
        "assignee": "QuyDev",
        "priority": 1,
        "status": "todo",
        "created_at": "2026-07-01T09:50:00Z",
        "internal_notes": "Admin only"
    },
    {
        "id": 2,
        "title": "Xây dựng API",
        "description": "Phát triển API bằng FastAPI",
        "assignee": "Nam",
        "priority": 2,
        "status": "in_progress",
        "created_at": "2026-07-01T10:20:00Z",
        "internal_notes": "Admin only"
    }
]


def get_timestamp():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def response_template(status_code, message, data, error, path):
    return {
        "statusCode": status_code,
        "message": message,
        "data": data,
        "error": error,
        "timestamp": get_timestamp(),
        "path": path
    }


class TaskCreateSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str
    assignee: str = Field(..., min_length=2)
    priority: int = Field(..., ge=1, le=5)


class TaskUpdateSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str
    assignee: str = Field(..., min_length=2)
    priority: int = Field(..., ge=1, le=5)
    status: str


class TaskPublicResponse(BaseModel):
    id: int
    title: str
    description: str
    assignee: str
    priority: int
    status: str
    created_at: str


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=response_template(
            422,
            "Lỗi: Dữ liệu đầu vào sai định dạng hoặc thiếu trường bắt buộc!",
            None,
            "ERR-VAL-422: Gateway validation error: Input json parameters datatype hints mismatch or core required fields missing.",
            request.url.path
        )
    )


@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=response_template(
            exc.status_code,
            exc.detail["message"],
            None,
            exc.detail["error"],
            request.url.path
        )
    )


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreateSchema, request: Request):
    for item in tasks_db:
        if item["title"].lower() == task.title.lower():
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Lỗi: Tiêu đề công việc này đã tồn tại trong nhóm!",
                    "error": "ERR-TASK-01: Task conflict: Title field values duplicates an existing record in the temporary database storage."
                }
            )

    new_task = {
        "id": max(i["id"] for i in tasks_db) + 1,
        "title": task.title,
        "description": task.description,
        "assignee": task.assignee,
        "priority": task.priority,
        "status": "todo",
        "created_at": get_timestamp(),
        "internal_notes": "Admin only"
    }

    tasks_db.append(new_task)

    public = TaskPublicResponse(**new_task).model_dump()

    return response_template(
        201,
        "Tạo mới công việc nhóm thành công!",
        public,
        None,
        request.url.path
    )


@app.get("/tasks/search")
def search_tasks(
        request: Request,
        keyword: str = Query(None),
        status: str = Query(None)
):
    result = tasks_db

    if keyword:
        pattern = re.compile(keyword, re.IGNORECASE)
        result = [
            task for task in result
            if pattern.search(task["title"]) or pattern.search(task["assignee"])
        ]

    if status:
        result = [
            task for task in result
            if task["status"] == status
        ]

    public = [TaskPublicResponse(**task).model_dump() for task in result]

    return {
        "total": len(public),
        "data": public
    }


@app.get("/tasks/{task_id}")
def get_task(task_id: int, request: Request):
    task = next((item for item in tasks_db if item["id"] == task_id), None)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!",
                "error": "ERR-TASK-04: Resource missing error: Target task entity parameter [task_id] can not be located within current active database scope."
            }
        )

    public = TaskPublicResponse(**task).model_dump()

    return response_template(
        200,
        "Lấy thông tin công việc thành công!",
        public,
        None,
        request.url.path
    )


@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdateSchema, request: Request):
    index = next((i for i, item in enumerate(tasks_db) if item["id"] == task_id), None)

    if index is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!",
                "error": "ERR-TASK-04: Resource missing error: Target task entity parameter [task_id] can not be located within current active database scope."
            }
        )

    if task.status not in ["todo", "in_progress", "done"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Lỗi: Trạng thái công việc cập nhật không đúng quy định!",
                "error": "ERR-TASK-03: Business logic error: Invalid task status value. Allowed enumerated selection list: ['todo', 'in_progress', 'done']."
            }
        )

    tasks_db[index].update({
        "title": task.title,
        "description": task.description,
        "assignee": task.assignee,
        "priority": task.priority,
        "status": task.status
    })

    public = TaskPublicResponse(**tasks_db[index]).model_dump()

    return response_template(
        200,
        "Cập nhật công việc thành công!",
        public,
        None,
        request.url.path
    )


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    index = next((i for i, item in enumerate(tasks_db) if item["id"] == task_id), None)

    if index is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!",
                "error": "ERR-TASK-04: Resource missing error: Target task entity parameter [task_id] can not be located within current active database scope."
            }
        )

    tasks_db.pop(index)

    return Response(status_code=204)