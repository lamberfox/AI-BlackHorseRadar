# GitHub 每日黑马项目 AI 雷达（DeepSeek + 企微）

## 1. 项目目标

本项目用于每天自动抓取 GitHub 近 3 天增长最快的潜力开源项目，调用 DeepSeek 做技术向分析，并一键推送到企业微信机器人。

目标特性：

- 每周一北京时间 09:00 自动运行（GitHub Actions）。
- 输出偏技术投资视角，拒绝营销话术。
- 兼顾稳定性和隐私：限流、降级、截断、密钥全走 Secrets。
- 零服务器运维成本，全部依赖 GitHub 托管执行。

---

## 2. 总体架构

1. **触发层（Trigger）**  
   GitHub Actions 定时任务触发。

2. **采集层（Scraper）**  
   调用 GitHub Search API 拉取近 3 天项目，并抓 README（截断）与基础元数据。

3. **AI 解析层（Analyzer）**  
   将项目信息提交给 DeepSeek，输出结构化分析结果（JSON）。

4. **分发层（Notifier）**  
   将所有项目分析汇总成 Markdown 日报，发送到企微 Webhook。

---

## 3. 推荐项目结构

```text
AI-BlackHorseRadar/
├─ .github/
│  └─ workflows/
│     └─ radar.yml
├─ src/
│  ├─ main.py
│  ├─ scraper.py
│  ├─ analyzer.py
│  ├─ notifier.py
│  ├─ models.py
│  └─ utils.py
├─ requirements.txt
├─ .gitignore
└─ Readme.md
```

说明：

- `main.py`：任务编排入口，负责串联采集 -> 分析 -> 推送。
- `scraper.py`：GitHub 数据抓取与预处理。
- `analyzer.py`：DeepSeek 调用与结果标准化。
- `notifier.py`：企微消息拼装和发送。
- `models.py`：数据结构定义（可选 dataclass / pydantic）。
- `utils.py`：公共工具（重试、日志、时间格式化等）。

---

## 4. 核心执行计划（分阶段）

## 阶段 A：MVP 打通（Day 1）

目标：先跑通“可用链路”。

1. 建立目录和依赖（requests + python-dotenv）。
2. 实现 `scraper.py`：
   - 计算 `3_days_ago`（格式 `%Y-%m-%d`）。
   - 搜索项目：按 stars 倒序，拉前 10。
   - 读取前 5~10 个项目 README。
   - README 强制截断前 2000 字符。
   - 每次详情请求 `time.sleep(2)`。
3. 实现 `analyzer.py`：
   - 使用 `DEEPSEEK_API_KEY`。
   - Prompt 要求返回标准 JSON，字段固定。
4. 实现 `notifier.py`：
   - 汇总 Markdown。
   - POST 到 `WECOM_WEBHOOK_URL`。
5. 配置 `radar.yml`，支持 `schedule + workflow_dispatch`。

## 阶段 B：稳态增强（Day 2~3）

1. 异常降级：
   - 单项目失败不阻断全局。
   - AI 失败时保留“基础信息 + 失败原因”。
2. 超时与重试：
   - GitHub 请求设置超时（如 15s）。
   - Webhook 发送失败重试 2~3 次。
3. 日志可观测：
   - 输出项目数量、成功数、失败数、总耗时。
   - 日志不得打印密钥和完整 webhook。

## 阶段 C：质量优化（Day 4+）

1. 增加“黑马指数”规则（AI + 规则混合评分）。
2. 加入去重（避免连续多天重复推荐）。
3. 增加单元测试（时间计算、Markdown 渲染、异常场景）。

---

## 5. 模块任务拆解（开发清单）

## Task 1：`scraper.py`

输入：无（内部用当前时间和 GitHub API）。  
输出：项目列表（每个项目含基础元数据 + 截断 README）。

关键点：

- 查询语句示例：
  - `q=created:>YYYY-MM-DD`
  - `sort=stars&order=desc`
- 建议抓取字段：
  - `full_name`
  - `html_url`
  - `description`
  - `language`
  - `stargazers_count`
  - `owner.login`
  - `created_at`
- README 接口建议：
  - `GET /repos/{owner}/{repo}/readme`
  - `Accept: application/vnd.github.raw+json`（拿纯文本）

必做防御：

- 每个项目请求后 `sleep(2)`。
- README 截断（2000 字符）。
- 单项目异常 `try/except` 后 `continue`。

## Task 2：`analyzer.py`

输入：单个项目的元数据 + README 摘要。  
输出：结构化分析结果（dict）。

建议输出字段（固定）：

- `pain_point`：核心痛点
- `implementation_guess`：底层实现推测
- `competitors`：主要竞品
- `killer_feature`：绝杀点
- `dark_horse_score`：1~5
- `follow_up`：是否建议跟进（yes/no + 一句话）

Prompt 约束建议：

- 明确“技术 VC 视角，禁止营销词”。
- 必须输出 JSON，不允许额外文本。
- 信息不足时要写“推测依据不足”而不是编造。

密钥要求：

- 仅从环境变量读取 `DEEPSEEK_API_KEY`。
- 不得写入代码、日志、注释。

## Task 3：`notifier.py`

输入：项目分析数组。  
输出：企微发送结果（成功/失败）。

内容组织建议：

- 标题：`# GitHub 黑马技术雷达日报（YYYY-MM-DD）`
- 概览区：采样数、分析成功数、失败数
- 明细区：每个项目一个二级标题，附评分和四维分析
- 结尾区：免责声明（仅技术研判，不构成投资建议）

发送建议：

- 使用企微机器人 markdown 消息格式。
- webhook 从 `WECOM_WEBHOOK_URL` 读取。
- 请求失败重试 + 明确报错日志。

## Task 4：`.github/workflows/radar.yml`

核心要求：

- 定时：`cron: '0 1 * * *'`（UTC 1 点 = 北京时间 9 点）
- 允许手动触发：`workflow_dispatch`
- 最小权限：`permissions: contents: read`
- 环境变量注入：
  - `DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}`
  - `WECOM_WEBHOOK_URL: ${{ secrets.WECOM_WEBHOOK_URL }}`

推荐步骤：

1. Checkout
2. Setup Python
3. Install dependencies
4. Mask secrets（`::add-mask::`）
5. Run `python src/main.py`

---

## 6. 隐私与安全设计（重点）

你关注的“高隐私”按以下方案落地：

1. **Secrets 托管**
   - 所有密钥仅存 GitHub Secrets，不落地仓库。
   - 可选开启 Environment 保护（如 `prod-radar`）。

2. **最小权限**
   - workflow 仅保留 `contents: read`。
   - 不授予写权限，不调用不必要 API。

3. **日志脱敏**
   - 执行前 `add-mask` 敏感值。
   - 严禁打印 request headers 中的 Authorization。

4. **密钥轮换**
   - 建议每月或每季度轮换 `DEEPSEEK_API_KEY` 和 Webhook。

5. **风险隔离**
   - 建议私有仓库存放。
   - 测试/生产分不同 webhook，避免误发生产群。

---

## 7. 配置项与环境变量

必需：

- `DEEPSEEK_API_KEY`
- `WECOM_WEBHOOK_URL`

可选：

- `GITHUB_TOKEN`（默认可用）
- `TOP_N`（默认 10）
- `ANALYZE_N`（默认 5）
- `README_MAX_LEN`（默认 2000）

---

## 8. 质量与容错规范（必须遵守）

1. API 限频保护：项目循环请求必须包含 `sleep(2)`。
2. Token 熔断：README 强制截断，不允许无限喂模型。
3. 零硬编码：密钥仅环境变量读取。
4. 错误降级：单项目失败不影响整批任务。
5. 最终兜底：即便分析全部失败，也要发送“任务执行结果通知”。

---

## 9. 验收标准（Definition of Done）

满足以下条件即视为可上线：

- 手动触发 workflow 可成功执行并推送到企微。
- 定时任务可在 9:00（北京时间）自动执行。
- 至少 5 个项目被抓取并尝试分析。
- 单项目失败时总流程不中断。
- 仓库代码中无明文密钥，日志中无敏感信息泄露。

---

## 10. 后续迭代建议

1. 增加“星标增长速度”指标（结合 created_at 与 stars 归一化）。
2. 对热门语言设置分组（Python/TS/Rust）避免单一生态偏置。
3. 增加历史榜单缓存，支持“首次上榜/连续上榜”标签。
4. 为日报增加“投资关注优先级”（P0/P1/P2）。

---

## 11. 启动说明（开发者）

本地调试建议流程：

1. 配置 `.env`（仅本地，不提交）：
   - `DEEPSEEK_API_KEY=...`
   - `WECOM_WEBHOOK_URL=...`
2. 安装依赖：`pip install -r requirements.txt`
3. 运行：`python src/main.py`
4. 验证企微是否收到日报

上线流程：

1. 在 GitHub 仓库添加两个 Secrets。
2. 提交 workflow 文件到默认分支。
3. 先手动触发一次确认。
4. 次日观察定时任务是否准时推送。

我想确认每一个设计细节。 https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=34fe4d17-338a-4f9d-8d0c-338230cf4cb7 这是我的webHook。然后这个是我的deepseek的key deepseek=sk-563d87303e824bf6bb2501544cc79e51。
