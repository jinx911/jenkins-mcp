---
name: jenkins-deploy
description: Interactive Jenkins deploy — trigger builds with parameter selection
triggers:
  - jenkins-deploy
  - jenkins deploy
  - 部署
  - 发布
---

# /jenkins-deploy — Interactive Deploy

Interactive deploy skill for triggering Jenkins builds. Supports all OA project jobs with smart parameter defaults and interactive parameter selection.

## 使用场景

| 用户输入 | 行为 |
|---------|------|
| `/deploy` | 列出所有 Jenkins job，让用户选择，然后交互式填写参数 |
| `/deploy oa-service` | 获取 oa-service 的参数，交互式填写缺失参数 |
| `/deploy oa-service test_version=kn oa_branch=feat/xxx` | 参数完整时直接触发构建 |
| `/deploy oa-platform-php test_version=stage platform_branch=feat/xxx module_branch=feat/xxx capital_branch=feat/xxx` | 完整参数直接触发 |

## Job 参数映射

| Job | 环境参数 | 分支参数 |
|-----|---------|---------|
| oa-platform-php | test_version (kn/stage/u1) | platform_branch, module_branch, capital_branch |
| oa-service | test_version (kn/stage/u1) | oa_branch |
| oa-gateway | test_version (kn/stage/u1) | oa_branch |
| oa-frontend | DEPLOY_ENV (kn/u1/stage) | GIT_BRANCH |
| oa-integration | environment (kn/stage/u1/kn2) | integration, message, calendar, common, approval, employees, recruitment |
| oa-go | test_version (attendance/clock/user/employee/delivery) | branch |
| oa-web-app-v2 | test_version (kn/kn2/stage/u1) | default_branch |

## 工作流

### 场景 1: 无参数 — 列出所有 Job 让用户选择

1. 调用 `mcp__jenkins__jenkins_list_jobs` 获取所有 job 列表
2. 使用 AskUserQuestion 展示所有 job 名称让用户选择:
   ```
   请选择要部署的 Job:
   - oa-platform-php
   - oa-service
   - oa-gateway
   - oa-frontend
   - oa-integration
   - oa-go
   - oa-web-app-v2
   ```
3. 用户选择后，进入场景 2

### 场景 2: 有 job_name 但参数不完整 — 交互式参数填写

1. 调用 `mcp__jenkins__jenkins_get_job` 获取该 job 的参数定义
2. 从返回结果中解析 `property[0].parameterDefinitions` 获取所有参数
3. 根据上文「Job 参数映射」表为参数设置智能默认值:
   - 环境类参数: 默认值为第一个选项 (通常为 kn)
   - 分支类参数: 默认值为空字符串，需要用户填写
4. 对于用户未提供的每个参数，使用 AskUserQuestion 交互式询问:

   **Choice 参数** (type = "ChoiceParameterDefinition"):
   ```
   使用 AskUserQuestion:
   question: "请选择 {param_name}:"
   options: 从参数定义的 choices 中提取
   ```

   **String 参数** (type = "StringParameterDefinition"):
   ```
   使用 AskUserQuestion:
   question: "请输入 {param_name} (默认: {default_value}):"
   如果有默认值则作为提示展示
   ```

   **Boolean 参数** (type = "BooleanParameterDefinition"):
   ```
   使用 AskUserQuestion:
   question: "{param_name}?"
   options: ["true", "false"]
   ```

   **Password 参数** (type = "PasswordParameterDefinition"):
   ```
   跳过，使用默认值
   不向用户展示密码输入
   ```

5. 所有参数收集完毕后，进入场景 3

### 场景 3: 参数完整 — 触发构建并等待结果

1. 将收集到的参数整理为对象:
   ```json
   {
     "job_name": "oa-service",
     "parameters": {
       "test_version": "kn",
       "oa_branch": "feat/xxx"
     }
   }
   ```

2. 调用 `mcp__jenkins__jenkins_build_and_watch`，传入:
   - `job_name`: job 名称
   - `parameters`: 参数对象 (key-value pairs)

3. 向用户展示构建过程:
   ```
   正在触发构建...
   Job: oa-service
   参数:
     test_version = kn
     oa_branch = feat/xxx

   构建中... 请稍候
   ```

4. 返回最终构建结果:
   ```
   构建完成!
   Build #123
   状态: SUCCESS / FAILURE
   耗时: Xs
   URL: {build_url}
   ```

5. 如果构建失败，提示用户可以使用 `/jenkins-log {job_name} {build_number}` 查看详细日志

## 重要规则

- 所有 Jenkins 操作必须通过 MCP 工具 (`mcp__jenkins__jenkins_*`) 执行，禁止使用 curl/bash 直接调用
- 参数不完整时必须使用 AskUserQuestion 交互式询问，不能自行假设或编造参数值
- Password 类型参数跳过，使用 Jenkins 定义的默认值
- 分支参数如果没有智能默认值，必须让用户手动输入，不能自动生成分支名
- 构建触发前展示完整参数列表让用户最后确认
