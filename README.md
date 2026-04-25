# FastAPI + LLM 智能新闻与对话平台

本人基于黑马程序员的新闻fastapi后端入门课，在此基础上扩展了AI大模型的上下文记忆能力，主要是锻炼自己的实际运用能力，以此文记录自己的学习过程。后续会继续扩展这个项目的能力。本项目适合新手联系fastapi，欢迎大佬提供意见。

这是一个基于 **FastAPI** 开发的现代化、企业级新闻与资讯平台，深度集成了**大语言模型（LLM）**能力。本项目旨在展示如何运用Python 异步 Web 框架构建具备实时流式对话、智能上下文逻辑处理的 AI 应用底座，非常适合作为PromptEngineer以及Fastapi入门的实践参考。

##  核心特性 

本项目将重心放在了后端架构的严谨性与大模型交互的工程实现上：

- ** 高性能异步后端**：基于 FastAPI + 异步 SQLAlchemy 构建，采用完全的异步非阻塞 I/O 设计，为高并发的 LLM API 调用以及实时流式传输提供最佳的性能保障。
- ** 大模型接入 (AI Chat)**：深度集成通义千问提供的 LLM 能力，应用 `Server-Sent Events (SSE)` 技术实现极低延迟的流式 (Streaming) 对话响应，提供如同 ChatGPT 般平滑的打字机交互体验。
## 智能会话与上下文管理**：
  - 构建了完整的持久化会话机制：
    - 支持用户登录与注册。
    - 支持用户登录后创建多个会话，并支持在不同会话间进行切换。
    - 支持会话完整的上下文同步与持久化。
  - 应用会话摘要与对话缓存实现对话历史的自动化摘要与压缩机制，有效管控长对话场景下的 Token 消耗与上下文滑窗。
## 基于 LangChain 架构的检索增强生成（RAG）
  - 构建本地高性能向量知识库，基于 Chroma 实现新闻文本向量化存储与高效相似性检索。
  - 严格从系统数据库中读取真实新闻数据进行检索增强，从源头避免大模型幻觉问题，确保模型回答真实、准确、可溯源。
  - 基于 LangChain 完整封装 RAG 全流程 pipeline，包括文档分块、向量化、向量检索、提示词工程与大模型生成，实现新闻领域精准问答与信息总结。

## 其他
- **严酷的数据契约与安全**：全面使用 Pydantic V2 进行严格的请求与响应 Schema 校验；设计了统一的网关级响应协议，严格隔离 ORM 内部模型与外部 API 暴露的数据，确保敏感信息（如密码哈希等）零泄露。
- **完善的业务闭环**：除了 AI 能力，系统还提供了规范的 RESTful API，涵盖基于 JWT 的用户鉴权、新闻分类获取、阅读历史追踪与文章收藏模块。
- **开箱即用的前端页面**：包含一个使用 Vue 3 + Pinia 构建的直观前端界面（SPA），完整对接了后端的 SSE 接口与各项业务，便于演示真实应用效果。

##  技术栈

### 后端与 LLM 工程层 (核心)
- **Web 框架**: [FastAPI](https://fastapi.tiangolo.com/) - 声明式定义、原生异步支持、自动 OpenAPI 规范生成。
- **ORM 与数据库**: [SQLAlchemy](https://www.sqlalchemy.org/) (AsyncSession) + SQLite（可无缝切换至 PostgreSQL/MySQL）。
- **langchain**: 
- **提示词工程**：[PromptEngineer]通过提示词的设计来达到更符合企业级的专用聊天机器人，从原本随意切无记忆的api调用变成专精新闻类知识的“新闻专家”！

### 前端功能层
- **核心框架**: Vue 3 (Composition API) + Vite
- **状态管理 & 请求**: Pinia + Axios（支持统一请求拦截与 Token 处理）。

##  核心目录结构

```text
├── backend/                # FastAPI 后端应用 
│   ├── config/             # 系统配置 (数据库、缓存等)
│   ├── crud/               # 异步数据库操作层
│   ├── models/             # SQLAlchemy 数据表映射
│   ├── routers/            # 路由层 
│   ├── schemas/            # Pydantic 校验模型 (严格入参出参约束)
│   ├── services/           # 核心业务服务 (包含对话摘要精简 update_summary，RAG服务等)
│   ├── utils/              # 跨模块工具 (JWT 鉴权、全局异常处理)
│   └── main.py             # FastAPI 应用入口与中间件注册
│
└── frontend/               # Vue 3 前端界面
    ├── src/
    │   ├── store/          # Pinia 状态管理 (包含对话历史内存同步)
    │   └── views/          # 页面层 (包含 AI 聊天交互实现)
    └── package.json        
```

##  快速启动

### 1. 后端服务部署

进入后端目录，并配置您的 Python 环境）：

```bash
cd backend

# 安装核心依赖
pip install -r requirements.txt
```

**环境配置**:
在 `backend` 目录下创建或检查环境变量文件 `.env`，并填入你的大模型 API Key（以 DashScope 为例）：
```ini
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DATABASE_URL=mysql+aiomysql://root:yourmysqlpassword@localhost:3306/yourdatabasename?charset=utf8mb4
```
**配置数据库**
```bash
在linux环境配置mysql
sudo apt update
sudo apt install mysql-server  #sudo /etc/init.d/mysql status 查看状态
sudo /etc/init.d/mysql start    #或者/service mysql start   #启动mysql
sudo /etc/init.d/mysql stop      #/service mysql stop    #停止mysql
sudo /etc/init.d/mysql restart    #/service mysql restart #重启mysql
sudo mysql -u root             #登录mysql 默认没有密码,后续需要增加root用户的密码
ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY '你的密码';
FLUSH PRIVILEGES;    #登录mysql后为root增设密码 
#有密码后，登录mysql 命令：
mysql -u root -p
#然后根据外部sql文件创建一个自己的数据集
mysql -u root -p < "/The/Path/To/YourSqlFile.sql"
#在我这里采用的是黑马fastapi课程提供的新闻数据库，理论上让ai随便生成一个测试一下就行
```

**启动服务**:
```bash
uvicorn main:app --reload 
```
*启动后，访问 [http://localhost:8000/docs](http://localhost:8000/docs) 即可查看由 FastAPI 自动生成的交互式 API 接口文档。*

### 2. 前端界面启动

```bash
#下载nodejs
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt-get install -y nodejs
#开启终端
cd frontend
npm install
npm run dev  #需要注意版本，版本冲突问AI重新安装即可
```
运行成功之后终端里会给出目标网址
接下来，在浏览器中打开这个所给网址即可看到前端界面。

