# WebSocket安全

<cite>
**Referenced Files in This Document**   
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py)
- [deps.py](file://freqtrade/rpc/api_server/deps.py)
- [webserver.py](file://freqtrade/rpc/api_server/webserver.py)
</cite>

## Table of Contents
1. [WebSocket身份验证机制](#websocket身份验证机制)
2. [静态令牌与JWT令牌验证](#静态令牌与jwt令牌验证)
3. [多令牌匹配逻辑](#多令牌匹配逻辑)
4. [时序攻击防护](#时序攻击防护)
5. [安全连接关闭策略](#安全连接关闭策略)
6. [配置依赖注入](#配置依赖注入)

## WebSocket身份验证机制

WebSocket连接的身份验证通过`validate_ws_token`函数实现，该函数位于`api_auth.py`文件中，负责验证WebSocket连接的令牌安全性。

**Section sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

## 静态令牌与JWT令牌验证

`validate_ws_token`函数支持两种令牌验证方式：静态令牌和JWT令牌。函数首先检查提供的`ws_token`是否与配置中的`ws_token`匹配，如果匹配则验证通过。如果不匹配，则尝试将`ws_token`作为JWT令牌进行验证。

```mermaid
sequenceDiagram
participant Client as "客户端"
participant Validator as "validate_ws_token"
participant JWT as "JWT验证"
Client->>Validator : 发送WebSocket连接请求
Validator->>Validator : 获取api_config配置
Validator->>Validator : 检查静态令牌
alt 静态令牌匹配
Validator-->>Client : 验证通过
else 静态令牌不匹配
Validator->>JWT : 验证JWT令牌
alt JWT验证成功
JWT-->>Validator : 返回用户信息
Validator-->>Client : 验证通过
else JWT验证失败
Validator->>Client : 关闭连接(WS_1008)
end
end
```

**Diagram sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

**Section sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

## 多令牌匹配逻辑

当`ws_token`配置为字符串列表时，函数实现多令牌匹配逻辑。通过遍历配置中的令牌列表，使用`secrets.compare_digest`函数逐一比较，只要有一个令牌匹配即验证通过。

```mermaid
flowchart TD
Start([开始验证]) --> CheckList{"ws_token是列表?"}
CheckList --> |是| LoopStart[开始遍历列表]
LoopStart --> GetToken["获取列表中的下一个令牌"]
GetToken --> Compare["compare_digest(配置令牌, 请求令牌)"]
Compare --> Match{"匹配?"}
Match --> |是| ReturnValid["返回验证通过"]
Match --> |否| HasNext{"还有下一个?"}
HasNext --> |是| LoopStart
HasNext --> |否| ReturnInvalid["返回验证失败"]
CheckList --> |否| SingleCompare["直接比较单个令牌"]
SingleCompare --> ReturnValid
ReturnValid --> End([验证结束])
ReturnInvalid --> End
```

**Diagram sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

**Section sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

## 时序攻击防护

为防止时序攻击，函数使用`secrets.compare_digest`函数进行令牌比较。该函数以恒定时间执行字符串比较，避免了基于响应时间差异的攻击。

```mermaid
classDiagram
class validate_ws_token {
+ws : WebSocket
+ws_token : str | None
+api_config : dict[str, Any]
+secret_ws_token : str | list[str]
+secret_jwt_key : str
+is_valid_ws_token : bool
}
class secrets {
+compare_digest(a : str, b : str) : bool
}
validate_ws_token --> secrets : "使用"
```

**Diagram sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

**Section sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

## 安全连接关闭策略

当JWT验证失败时，函数会自动关闭WebSocket连接，并返回`WS_1008_POLICY_VIOLATION`状态码。这是一种安全策略，防止未经授权的连接持续存在。

```mermaid
sequenceDiagram
participant WS as "WebSocket"
participant Validator as "验证器"
participant JWT as "JWT解码"
WS->>Validator : 发送令牌
Validator->>JWT : 尝试解码
alt 解码成功
JWT-->>Validator : 返回用户
Validator-->>WS : 维持连接
else 解码失败
JWT--xValidator : 抛出HTTPException
Validator->>WS : close(code=WS_1008)
WS-->>Validator : 连接关闭
end
```

**Diagram sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

**Section sources**
- [api_auth.py](file://freqtrade/rpc/api_server/api_auth.py#L55-L85)

## 配置依赖注入

`get_api_config`函数通过依赖注入提供`ws_token`和`jwt_secret_key`配置参数。该函数从`ApiServer._config`中获取API服务器配置，确保配置的一致性和安全性。

```mermaid
classDiagram
class get_api_config {
+返回 : dict[str, Any]
}
class ApiServer {
+_config : Config
+_rpc : RPC
+_has_rpc : bool
+_message_stream : MessageStream | None
}
get_api_config --> ApiServer : "读取 _config['api_server']"
```

**Diagram sources**
- [deps.py](file://freqtrade/rpc/api_server/deps.py#L42-L43)
- [webserver.py](file://freqtrade/rpc/api_server/webserver.py#L34-L243)

**Section sources**
- [deps.py](file://freqtrade/rpc/api_server/deps.py#L42-L43)
- [webserver.py](file://freqtrade/rpc/api_server/webserver.py#L34-L243)