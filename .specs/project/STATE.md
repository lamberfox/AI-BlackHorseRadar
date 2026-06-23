# STATE.md — Project Memory

## Active Feature
App Store 跨境黑马雷达集成 (appstore-integration)
Started: 2026-06-23

## Decisions

D1: 复用 DeepSeek（DEEPSEEK_API_KEY），不引入 OpenAI 密钥
    — appStore顾问.md 原来引用 OPENAI_API_KEY，统一改为 DeepSeek

D2: App Store 分析输出 JSON（与 GitHub 分析一致），不用 Markdown
    — appStore顾问.md Part A/B 结构改写为 JSON 字段，便于 reporter.py 渲染

D3: prompts.py 扩展支持 app_store prompt 文件（appStore顾问.md）
    — 不新建 app_store_prompts.py，直接在 prompts.py 加第二个加载函数

D4: app_snapshots.json 存仓库根目录，workflow 回写与 docs/ 合并到同一 git push step

D5: Workflow 权限已有 contents: write，无需修改 permissions 块
    — 只需在现有 "Publish report" step 中加 git add app_snapshots.json

D6: 每次运行最多分析 APP_ANALYZE_N=5 个黑马（防止 token 超支）

## App Store JSON 输出字段（确定）
{
  "product_what":     str,   // 产品是什么，一句话
  "go_no_go":         str,   // 强烈跟进 / 观望 / 放弃
  "dark_horse_score": int,   // 1-10（信号强度）
  "clone_score":      int,   // 1-5（v0+Flutter 复制成功率）
  "signal_validity":  str,   // 信号真伪评估
  "intercept_window": str,   // 还剩几周截流窗口
  "pain_point":       str,   // 核心吸金痛点
  "v0_prompt":        str,   // v0.dev 刷图英文指令
  "flutter_arch":     str,   // Flutter MVP 架构拆解
  "clone_edge":       str,   // 截流改进点
  "art_cost":         str,   // low / medium / high
  "flutter_feasibility": int // 1-5
}

## Blockers
None

## Deferred
- 未来可考虑把 App Store 卡片单独分页，当前合并在同一 index.html
