# Tasks — App Store 黑马雷达集成

## Dependency Graph
T1 → T4, T5, T6
T2 → T4, T7
T3 → T4
T4 → T7
T5 → T7
T6 → T7
T8  (独立)

## Tasks

### T1 — 扩展 models.py
What: 新增 AppProject 和 AppAnalysisResult dataclass
Where: src/models.py
Done when:
  - AppProject 含 app_id, title, region, category, description, price, developer, html_url, filter_trigger ("A"/"B")
  - AppAnalysisResult 含所有 12 个 JSON 字段 + error + success property
  - 与现有 Project/AnalysisResult 共存，无破坏性改动
Status: [ ]

### T2 — 新建 app_store_client.py
What: App Store RSS 抓取 + 快照读写 + 黑马过滤
Where: src/app_store_client.py（新建）
Done when:
  - load_snapshots() / save_snapshots() 读写 app_snapshots.json（仓库根）
  - fetch_new_apps(region, genre_id, limit) 调用 Apple RSS API，返回 AppProject 列表
  - fetch_reviews(region, app_id) 返回最新评论列表
  - filter_black_horses(apps, snapshots) 应用指标 A（7天/10评/90%）和指标 B（12h/15条）
  - 每次请求 time.sleep(2.0)，重试 3 次，超时 10s
  - 返回命中黑马的 AppProject 列表（已更新快照中评论计数）
Status: [ ]

### T3 — 重写 appStore顾问.md prompt
What: 将 Part A/B 叙事式 prompt 改为 JSON 输出格式（复用 prompts.py 解析机制）
Where: appStore顾问.md
Done when:
  - 文件包含 ## APP_SYSTEM_PROMPT 和 ## APP_USER_PROMPT 两个 section
  - SYSTEM_PROMPT 要求只返回合法 JSON，字段与 STATE.md D6 定义一致
  - USER_PROMPT 包含 {title}, {description}, {category}, {region}, {reviews} 占位符
  - 字段说明清晰，防止模型省略字段
Status: [ ]

### T4 — 新建 app_analyzer.py
What: 调用 DeepSeek 分析 AppProject，返回 AppAnalysisResult
Where: src/app_analyzer.py（新建）
Done when:
  - 复用 analyzer.py 的 _call_deepseek 模式（相同 API endpoint + model）
  - 从 appStore顾问.md 加载 APP_SYSTEM_PROMPT / APP_USER_PROMPT
  - 解析 JSON，映射到 AppAnalysisResult 字段，缺失字段默认"推测依据不足"
  - 单个失败返回 AppAnalysisResult(error=...) 不抛异常
Status: [ ]

### T5 — 扩展 reporter.py
What: 在 HTML 报告末尾追加 App Store 区块
Where: src/reporter.py
Done when:
  - _app_card(result: AppAnalysisResult, index: int) 生成卡片 HTML
    卡片含：App 名称链接、区域/分类/触发指标 meta、go_no_go + dark_horse_score badge
    字段行：product_what / pain_point / v0_prompt（截断100字） / flutter_arch / clone_edge / intercept_window
  - _app_section(results) 包裹成 <section>
  - generate_html() 接受新参数 app_results: List[AppAnalysisResult] = []
  - write_report() 接受 app_results 并透传
  - App Store 为空时区块不渲染（不影响现有页面）
Status: [ ]

### T6 — 扩展 notifier.py
What: WeCom 消息末尾追加 App Store 摘要
Where: src/notifier.py
Done when:
  - send_report() 接受新参数 app_results: List[AppAnalysisResult] = []
  - App Store 非空时在消息末尾追加摘要段（格式参考 PRD 八节）
  - top 3 命中条目，显示 AppName、区域、go_no_go、clone_score
Status: [ ]

### T7 — 扩展 main.py
What: 串联 App Store 流水线
Where: src/main.py
Done when:
  - import app_store_client, app_analyzer
  - APP_ANALYZE_N = int(os.getenv("APP_ANALYZE_N", "5"))
  - App Store 整条流水线包裹在 try/except，失败记 warning，app_results = []
  - 快照在流水线结束后 save_snapshots() 写回
  - write_report(results, app_results=app_results)
  - send_report(results, pages_url=..., app_results=app_results)
Status: [ ]

### T8 — 更新 radar.yml
What: 在 "Publish report" step 中加入快照回写
Where: .github/workflows/radar.yml
Done when:
  - 现有 git add docs/ 改为 git add docs/ app_snapshots.json
  - commit message 不变（已有 skip 逻辑）
  - 无需改 permissions（已有 contents: write）
Status: [ ]
