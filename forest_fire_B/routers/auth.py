from fastapi import APIRouter, HTTPException, Depends
# 加入 HTTPBearer
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
import datetime
from typing import Dict, Optional
import traceback

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db, User  # 导入会话依赖和用户模型

# 创建路由器，表示这个文件的接口都会自动加上/auth前缀
router = APIRouter(
    prefix="/auth",
    tags=["认证"]
)

# 配置JWT和登录相关常量
SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"
# Token默认有效期是1天
ACCESS_TOKEN_EXPIRE_DAYS = 1

# 1. 配置密码加密上下文（密码哈希后才保存到数据库中）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 定义请求体模型
class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

# 2. 使用 HTTPBearer，这会让 Swagger UI 显示为一个简单的 Bearer Token 输入框
security = HTTPBearer()

# 验证密码
def verify_password(plain_password, hashed_password):
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.verify(plain_password, hashed_password)

# 用户输入密码转换成哈希密码（注册时使用）
def get_password_hash(password):
    if isinstance(password, str):
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password)

# 生成Token（JWT登录令牌）
def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register")
async def register(user: UserRegister, db: AsyncSession = Depends(get_db)):
    try:
        # 1. 检查用户是否已存在 (异步查询)
        result = await db.execute(select(User).where(User.username == user.username))
        existing_user = result.scalars().first()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        
        # 2. 哈希密码
        hashed_password = get_password_hash(user.password)
        
        # 3. 创建新用户对象
        new_user = User(username=user.username, hashed_password=hashed_password)
        
        # 4. 添加到数据库
        db.add(new_user)
        await db.commit()   # 提交事务
        await db.refresh(new_user) # 刷新对象以获取 ID
        
        return {"msg": "注册成功", "username": new_user.username}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback() # 出错回滚
        print(f"Register Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        # 1. 从数据库查询用户
        result = await db.execute(select(User).where(User.username == user.username))
        db_user = result.scalars().first()
        
        if not db_user:
            raise HTTPException(status_code=401, detail="Incorrect username or password")
        
        # 2. 验证密码
        if not verify_password(user.password, db_user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        # 3. 生成 Token
        access_token_expires = datetime.timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
        access_token = create_access_token(
            data={"sub": db_user.username}, 
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# 3. 更新依赖函数：接收 HTTPAuthorizationCredentials
# 注意：get_current_user 也需要改为从数据库查，这里暂略，逻辑类似 login
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # 从数据库查用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    return user