import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User, UserToken
from schemas.users import UserChangePasswordRequest, UserRequest, UserUpdateRequest
from utils import security


# 根据用户名查询数据库
async def get_user_by_username(db: AsyncSession, username: str):
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    return result.scalar_one_or_none()#返回orm对象


# 创建用户
async def create_user(db: AsyncSession, username: str, password: str):#更推荐将crud与pydantic模型解耦，crud只处理数据库操作，pydantic模型负责数据验证和转换，这样可以提高代码的可维护性和灵活性。后面也有没解耦的例子
    # 先密码加密处理 → add
    hashed_password = security.get_hash_password(password)#加密后的密码
    user = User(username=username, password=hashed_password)#为什么不验证是否重名？因为在数据库层面设置了 username 唯一索引，重复会抛出异常
    db.add(user)
    await db.commit()
    await db.refresh(user)  # 从数据库读回最新的 user
    return user#返回orm对象，路由层再转换成pydantic对象响应给前端


# 生成 Token
async def create_token(db: AsyncSession, user_id: int):
    # 生成 Token + 设置过期时间 → 查询数据库当前用户是否有 Token → 有：更新；没有：添加
    token = str(uuid.uuid4())#生成一个随机的uuid字符串作为token
    # timedelta(days=7, hours=2, minutes=30, seconds=10)
    expires_at = datetime.now() + timedelta(days=7)#设置过期时间为7天后
    query = select(UserToken).where(UserToken.user_id == user_id)
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()

    if user_token:
        user_token.token = token
        user_token.expires_at = expires_at
    else:
        user_token = UserToken(user_id=user_id, token=token, expires_at=expires_at)
        db.add(user_token)
        await db.commit()

    return token

# 验证用户名和密码
async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not security.verify_password(password, user.password):
        return None

    return user


# 根据 Token 查询用户：验证 Token → 查询用户
async def get_user_by_token(db: AsyncSession, token: str):
    query = select(UserToken).where(UserToken.token == token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    if not db_token or db_token.expires_at < datetime.now():
        return None

    query = select(User).where(User.id == db_token.user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# 更新用户信息: update更新 → 检查是否命中 → 获取更新后的用户返回
async def update_user(db: AsyncSession, username: str, user_data: UserUpdateRequest):
    # update(User).where(User.username == username).values(字段=值, 字段=值)
    # user_data 是一个Pydantic类型，得到字典 → ** 解包
    # 没有设置值的不更新
    query = update(User).where(User.username == username).values(**user_data.model_dump(#model_dump 将 Pydantic 模型转换为字典
        exclude_unset=True,
        exclude_none=True
    ))
    result = await db.execute(query)
    await db.commit()

    # 检查更新
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 获取一下更新后的用户
    updated_user = await get_user_by_username(db, username)
    return updated_user


# 修改密码: 验证旧密码 → 新密码加密 → 修改密码
# async def change_password(db: AsyncSession, user: User, old_password: str, new_password: str):
async def change_password(db: AsyncSession, user: User, password_data: UserChangePasswordRequest):
    if not security.verify_password(password_data.old_password, user.password):
        return False

    hashed_new_pwd = security.get_hash_password(password_data.new_password)
    user.password = hashed_new_pwd
    # 更新: 由SQLAlchemy真正接管这个 User 对象，确保可以 commit
    # 规避 session 过期或关闭导致的不能提交的问题
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return True
