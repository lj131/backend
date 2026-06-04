# AI聊天系统接口文档

## 基本信息

- **框架**: FastAPI
- **语言**: Python
- **AI模型**: Deepseek Chat API
- **文档日期**: 2026/05/29

## 接口列表

### 1. 聊天接口

**接口地址**: `POST /chat`

**请求参数**:
```json
{
    "message": "string"
}
```

**参数说明**:
- `message` (string): 用户发送的消息内容，必填

**响应格式**:
```json
{
    "reply": "string",
    "favorability": "integer"
}
```

**响应说明**:
- `reply` (string): AI回复的内容
- `favorability` (integer): 当前角色的好感度（0-100）

**功能描述**:
1. 接收用户消息
2. 从内存加载历史对话记录
3. 加载角色设定信息
4. 加载用户画像
5. 构建系统提示词（基于好感度）
6. 如果没有系统消息，则添加系统消息到对话历史
7. 更新用户画像信息
8. 执行好感度计算（基于关键词匹配）
9. 发送请求到Deepseek Chat API
10. 保存回复到对话历史
11. 更新角色最后聊天时间
12. 保存角色信息
13. 保存对话历史
14. 返回AI回复和当前好感度

**好感度计算规则**:
- 正面词 +5分: "喜欢"、"爱你"、"谢谢"、"可爱"、"陪我"、"想你"
- 负面词 -5分: "讨厌"、"滚"、"烦"、"傻"、"闭嘴"
- 好感度范围: 0-100，超出范围会自动限制

### 2. 获取好感度接口

**接口地址**: `GET /favorability`

**请求参数**: 无

**响应格式**:
```json
{
    "favorability": "integer"
}
```

**响应说明**:
- `favorability` (integer): 当前角色的好感度（0-100）

**功能描述**:
1. 从角色文件中加载角色信息
2. 返回当前角色的好感度值

### 3. 获取用户画像接口

**接口地址**: `GET /profile`

**请求参数**: 无

**响应格式**:
```json
{
    "profile": "object"
}
```

**响应说明**:
- `profile` (object): 用户画像信息对象

**功能描述**:
1. 从用户画像文件中加载用户画像信息
2. 返回完整的用户画像数据

### 4. 保存用户画像接口

**接口地址**: `POST /profile`

**请求参数**:
```json
{
    "message": "string"
}
```

**参数说明**:
- `message` (string): 要保存的用户画像信息，必填

**响应格式**:
```json
{
    "message": "string"
}
```

**响应说明**:
- `message` (string): 操作结果信息

**功能描述**:
1. 保存用户画像信息到本地文件

### 5. 获取历史记录接口

**接口地址**: `GET /history`

**请求参数**: 无

**响应格式**:
```json
{
    "messages": "array"
}
```

**响应说明**:
- `messages` (array): 历史消息数组，只包含最近10条记录

**功能描述**:
1. 从内存加载历史对话记录
2. 只返回最近10条消息记录

### 6. 获取记忆接口

**接口地址**: `GET /memory`

**请求参数**: 无

**响应格式**:
```json
{
    "memory": "array"
}
```

**响应说明**:
- `memory` (array): 用户消息数组，只包含用户发送的消息内容

**功能描述**:
1. 从内存加载历史对话记录
2. 只提取用户发送的消息内容

### 7. 清空记忆接口

**接口地址**: `POST /clear-memory`

**请求参数**: 无（无需请求体）

**响应格式**:
```json
{}
```

**功能描述**:
1. 清空所有对话历史记录
2. 返回空对象表示操作成功

### 8. 获取历史消息接口

**接口地址**: `GET /messages`

**请求参数**: 无

**响应格式**:
```json
{
    "messages": "array"
}
```

**响应说明**:
- `messages` (array): 完整的历史消息数组，包含所有轮次的对话记录

**功能描述**:
1. 从内存加载所有历史对话记录
2. 返回完整的消息记录，包括系统消息、用户消息和助手消息

### 9. 设置角色名字接口

**接口地址**: `POST /character/name`

**请求参数**:
```json
{
    "name": "string"
}
```

**参数说明**:
- `name` (string): 角色的名字，必填

**响应格式**:
```json
{
    "message": "string"
}
```

**响应说明**:
- `message` (string): 操作结果信息，包含设置的角色名字

**功能描述**:
1. 设置或更新角色的名字
2. 新名字会立即生效，并在后续的聊天中使用

### 10. 获取角色名字接口

**接口地址**: `GET /character/name`

**请求参数**: 无

**响应格式**:
```json
{
    "name": "string"
}
```

**响应说明**:
- `name` (string): 当前角色的名字，如果未设置则返回默认名字"林晚"

**功能描述**:
1. 获取当前角色的名字
2. 如果角色没有设置名字，则返回默认名字"林晚"

## 系统架构

### 依赖模块
1. **memory**: 负责管理对话历史记录的存储和加载
2. **prompt**: 负责构建系统提示词
3. **positive**: 负责管理角色信息，包括好感度和名字
4. **userfile**: 负责管理用户画像信息
5. **utils**: 提供各种工具函数

### 状态管理
- **对话历史**: 存储所有轮次的对话记录
- **角色设定**: 包括好感度、名字、最后聊天时间等信息
- **用户画像**: 记录用户的对话习惯和特征

## API配置

- **OpenAI客户端配置**:
  ```python
  client = OpenAI(
      api_key=os.getenv("DEEPSEEK_API_KEY"),
      base_url="https://api.deepseek.com"
  )
  ```
- **AI模型**: deepseek-chat
- **温度参数**: 0.9

## 使用示例

### 发送聊天消息
```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "你好！"}'
```

示例响应：
```json
{
    "reply": "你好！很高兴见到你！",
    "favorability": 50
}
```

### 获取好感度
```bash
curl -X GET "http://localhost:8000/favorability"
```

示例响应：
```json
{
    "favorability": 50
}
```

### 获取用户画像
```bash
curl -X GET "http://localhost:8000/profile"
```

### 保存用户画像
```bash
curl -X POST "http://localhost:8000/profile" \
     -H "Content-Type: application/json" \
     -d '{"message": "用户画像信息"}'
```

### 获取历史记录
```bash
curl -X GET "http://localhost:8000/history"
```

### 获取记忆（用户消息）
```bash
curl -X GET "http://localhost:8000/memory"
```

### 清空记忆
```bash
curl -X POST "http://localhost:8000/clear-memory"
```

### 获取完整历史消息
```bash
curl -X GET "http://localhost:8000/messages"
```

### 设置角色名字
```bash
curl -X POST "http://localhost:8000/character/name" \
     -H "Content-Type: application/json" \
     -d '{"name": "小美"}'
```

示例响应：
```json
{
    "message": "角色名字已设置为：小美"
}
```

### 获取角色名字
```bash
curl -X GET "http://localhost:8000/character/name"
```

示例响应：
```json
{
    "name": "小美"
}
```

## 注意事项

1. 所有对话历史会自动保存在本地
2. 好感度会根据用户输入的关键词自动调整
3. 系统提示词会根据好感度和角色名字动态生成
4. 角色名字可以自由配置，默认为"林晚"
5. 确保环境变量 `DEEPSEEK_API_KEY` 已正确配置