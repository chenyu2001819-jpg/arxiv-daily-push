# 📚 arXiv 每日文章推送智能体

根据关键词自动抓取 arXiv 论文，每天推送最多30篇相关文章到邮箱。

支持 **本地运行** 和 **GitHub Actions 云端部署** 两种方式！

---

## 🌟 功能特点

- 🔍 **智能搜索**：根据关键词文件自动搜索相关论文，arXiv 原生**按日期/相关性排序**
- 🎯 **关键词过滤**：搜索后自动过滤，只保留标题/摘要中包含核心关键词的文章（无需 LLM）
- 📊 **引用排序**：按引用次数排序，优先推送高影响力文章
- 📊 **引用数据**：可选获取论文引用次数，优先推送高影响力文章
- 🤖 **LLM 智能筛选**：使用大模型（GPT/DeepSeek/Kimi 等）判断论文与关键词的真实相关性，过滤不相关文章
- 🗂️ **自动分组**：按主题（产业组织/航运环境）自动分类
- 🚫 **智能去重**：自动记录已推送文章，避免重复
- ⏰ **定时推送**：支持每天定时自动运行
- 📧 **邮件推送**：支持 SMTP 邮件推送，HTML 格式美观展示
- ☁️ **云端部署**：支持 GitHub Actions 免费云端运行
- 📄 **Markdown 报告**：生成本地 Markdown 格式报告备份
- 🔐 **SSH 支持**：使用 SSH 安全推送代码到 GitHub

---

## 🚀 快速开始（二选一）

### 方式一：GitHub Actions 云端部署（推荐 ⭐）

**零成本、免维护、自动运行！**

```bash
# 1. 在 GitHub 创建仓库（如 arxiv-daily-push）
# 2. 配置 SSH 密钥（如果尚未配置）
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub  # 复制到 GitHub Settings -> SSH keys

# 3. 推送代码（使用 SSH）
git init
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:你的用户名/arxiv-daily-push.git
git push -u origin main

# 4. 在 GitHub 仓库设置 Secrets（邮箱配置）
# 5. 完成！每天自动推送论文到邮箱
```

详细部署步骤见 [GITHUB_DEPLOY.md](GITHUB_DEPLOY.md)

### 方式二：本地运行（适合测试）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置邮箱（编辑 config.yaml）
cp config.example.yaml config.yaml
# 设置 email.enabled: true
# 填写 sender_email 和 sender_password（授权码）

# 3. 运行
python arxiv_agent.py
```

---

## 📁 文件结构

```
.
├── .github/
│   └── workflows/
│       └── arxiv_daily.yml     # GitHub Actions 工作流
├── arxiv_agent.py              # 主程序
├── email_sender.py             # 邮件发送模块
├── scheduler.py                # 本地定时任务调度器
├── test_email.py               # 邮件配置测试工具
├── keywords.txt                # 关键词配置文件
├── config.yaml                 # 配置文件（本地使用，含敏感信息）
├── config.example.yaml         # 配置模板（可安全提交）
├── requirements.txt            # Python 依赖
├── .gitignore                  # Git 忽略文件
├── README.md                   # 本文件
├── GITHUB_DEPLOY.md            # GitHub 部署指南（含 SSH 配置）
├── QUICK_START.md              # 5分钟快速开始
├── run.bat                     # Windows 一键运行脚本
├── setup_windows_task.ps1      # Windows 定时任务设置脚本
├── daily_papers/               # 报告输出目录
└── paper_history.json          # 文章历史（自动创建）
```

---

## 🔑 SSH 配置（推荐）

### 为什么要用 SSH？

| 方式 | 优点 | 缺点 |
|------|------|------|
| **SSH** ✅ | 安全、免密码、配置一次永久使用 | 需要配置密钥 |
| **HTTPS** | 简单、无需配置 | 每次推送需输入 Token/密码 |

### 快速配置 SSH

```bash
# 1. 生成 SSH 密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub

# 3. 添加到 GitHub
# GitHub -> Settings -> SSH and GPG keys -> New SSH key

# 4. 测试连接
ssh -T git@github.com

# 5. 使用 SSH 地址推送
git remote add origin git@github.com:用户名/仓库名.git
```

详细 SSH 配置见 [GITHUB_DEPLOY.md](GITHUB_DEPLOY.md)

---

## 📧 邮件配置指南

### 快速配置

编辑 `config.yaml`（本地运行）或设置 GitHub Secrets（云端部署）：

```yaml
email:
  enabled: true
  sender_email: "your_email@qq.com"
  sender_password: "your_auth_code"  # 授权码，不是登录密码！
  receiver_emails:
    - "receiver@example.com"
```

### 常见邮箱配置

| 邮箱 | SMTP服务器 | 授权码获取 |
|------|-----------|-----------|
| **QQ邮箱** | smtp.qq.com:465 | 设置 → 账户 → 开启SMTP → 获取16位授权码 |
| **163邮箱** | smtp.163.com:465 | 设置 → POP3/SMTP → 开启服务 → 获取授权码 |
| **Gmail** | smtp.gmail.com:587 | 安全性 → 两步验证 → 应用专用密码 |
| **Outlook** | smtp.office365.com:587 | 账户 → 安全性 → 应用密码 |

### 测试邮件配置

```bash
# 本地测试
python test_email.py

# 或
python arxiv_agent.py --test-email
```

---

## ☁️ GitHub Actions 部署详解

### 为什么要用 GitHub Actions？

| 特性 | 本地运行 | GitHub Actions |
|------|---------|----------------|
| 成本 | 电费/服务器费用 | **免费** |
| 稳定性 | 依赖电脑开机 | **云端稳定运行** |
| 维护 | 需要维护环境 | **零维护** |
| 访问 | 局域网限制 | **全球可访问** |
| 日志 | 本地查看 | **云端持久化** |

### 部署步骤

#### 1. 创建仓库并推送代码（使用 SSH）

```bash
# 在 GitHub 上创建空仓库（不要初始化 README）

# 本地执行
git init
git add .
git commit -m "Initial commit"

# 使用 SSH 地址（推荐）
git remote add origin git@github.com:你的用户名/arxiv-daily-push.git
git branch -M main
git push -u origin main
```

#### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**

**必需配置：**

| Secret | 值 |
|--------|-----|
| `EMAIL_ENABLED` | `true` |
| `EMAIL_SENDER` | 你的邮箱 |
| `EMAIL_PASSWORD` | 邮箱授权码 |
| `EMAIL_RECEIVERS` | 收件人邮箱（多个用逗号分隔）|

#### 3. 手动触发测试

1. 进入仓库 **Actions** 标签页
2. 选择 **arXiv Daily Paper Push**
3. 点击 **Run workflow**
4. 勾选 `test_email: true`
5. 点击 **Run workflow**

等待几分钟，检查是否收到测试邮件。

#### 4. 自动运行

配置完成后，工作流会：
- **每天北京时间 09:00** 自动运行
- 推送邮件到配置的邮箱
- 保留运行日志和报告

详细部署文档：[GITHUB_DEPLOY.md](GITHUB_DEPLOY.md)

---

## ⚙️ 配置说明

### config.yaml（本地使用）

```yaml
# 基础配置
keywords_file: keywords.txt
max_results_per_query: 50
days_back: 3
output_dir: daily_papers
history_file: paper_history.json

# 分块筛选配置
block_config:
  core_limit: 30       # 每块核心关键词取前N篇
  extended_limit: 10   # 每块扩展关键词取前N篇

# LLM 智能筛选配置（可选）
llm:
  enabled: false
  api_key: "your-llm-api-key"
  model: "gpt-3.5-turbo"  # 支持：gpt-3.5-turbo, deepseek-chat, moonshot-v1-8k
  api_url: "openai"       # 支持：openai, deepseek, moonshot, 或自定义URL
  min_score: 5.0          # 最低相关性分数 (0-10)
  top_n: 30               # 最多选取前N篇

# 邮件配置
email:
  enabled: true
  sender_email: "your_email@example.com"
  sender_password: "your_auth_code"
  receiver_emails:
    - "receiver@example.com"
```

⚠️ **重要**：`config.yaml` 包含敏感信息，已添加到 `.gitignore`，请勿提交到 Git！

### GitHub Secrets（云端使用）

通过 Secrets 配置，更加安全（敏感信息不会暴露在代码中）：

**必需配置：**
```
EMAIL_ENABLED=true
EMAIL_SENDER=your_email@qq.com
EMAIL_PASSWORD=your_auth_code
EMAIL_RECEIVERS=receiver1@qq.com,receiver2@gmail.com
```

**可选配置（LLM 智能筛选 - 如需更精确过滤才配置）：**
```
LLM_API_KEY=sk-xxxxxxxxxx
LLM_MODEL=gpt-3.5-turbo
LLM_API_URL=openai
LLM_MIN_SCORE=5.0
LLM_TOP_N=30
LLM_DELAY=2.0           # 请求间隔（秒），Gemini 建议 2 秒以上
LLM_MAX_RETRIES=3       # 失败重试次数
```

> 💡 **提示**：如果不配置 LLM，系统默认使用 **arXiv 原生相关性排序**，无需 API Key，更简单高效！

**其他可选配置：**
```
DAYS_BACK=3              # 搜索最近几天的文章
SEARCH_SOURCE=multi      # 搜索源: multi(多源), arxiv, semantic_scholar, openalex
SORT_BY=submittedDate    # 排序方式: submittedDate(最新) 或 relevance(相关性)
CORE_LIMIT=30
EXTENDED_LIMIT=10
SEMANTIC_SCHOLAR_KEY=    # Semantic Scholar API Key（可选）
OPENALEX_EMAIL=          # 你的邮箱（建议提供）
```

**搜索源对比：**
| 源 | 限制 | 特点 |
|----|------|------|
| `multi` | 较宽松 | 同时使用多个源，结果最全面，**推荐** |
| `semantic_scholar` | 100/5min | 相关性算法好，包含引用数 |
| `openalex` | 无限制 | 完全免费开源，数据覆盖广 |
| `arxiv` | 有限制 | 原始数据源，但噪声较大 |

**支持的 LLM 服务商：**
- `openai` - OpenAI GPT 系列
- `deepseek` - DeepSeek Chat
- `moonshot` - Moonshot (Kimi)
- `gemini` - Google Gemini
- `claude` - Anthropic Claude
- `zhipu` - 智谱 AI
- `minimax` - MiniMax
- 或直接填写完整 API URL

---

## 📝 关键词格式

`keywords.txt` 已预设两大主题：

```
产业组织经济学相关
空调市场
电动汽车市场 电车市场
市场结构
产品差异化
定价策略
...

航运环境相关
北极航道
海运碳排放
绿色航运
碳税
...
```

- 支持中文和英文关键词
- 一行可写多个同义词（空格或顿号分隔）
- 自动将中文翻译为英文搜索 arXiv

---

## 🛠️ 命令行选项

```bash
# 执行并发送邮件
python arxiv_agent.py

# 仅生成本地报告，不发送邮件
python arxiv_agent.py --no-email

# 测试邮件配置
python arxiv_agent.py --test-email

# 按引用次数排序（高引用优先）
python arxiv_agent.py --sort-by-citations --fetch-citations

# 获取引用次数显示（不排序）
python arxiv_agent.py --fetch-citations

# 使用自定义配置文件
python arxiv_agent.py --config my_config.yaml
```

### 本地定时运行

```bash
# 启动定时调度器（每天9点）
python scheduler.py

# 自定义时间（每天8点）
python scheduler.py --time 08:00

# 立即执行一次
python scheduler.py --run-once
```

---

## 🖥️ Windows 用户

### 方式一：一键运行脚本

双击 `run.bat`，选择菜单：
1. 立即执行并发送邮件
2. 仅生成本地报告
3. 测试邮件配置
4. 启动定时调度器

### 方式二：PowerShell 设置定时任务

```powershell
# 以管理员身份运行 PowerShell
.\setup_windows_task.ps1
```

---

## 📨 邮件内容预览

邮件采用精美的 HTML 格式：

- 📊 **彩色标题栏**：日期和文章数量统计
- 🏷️ **分组展示**：按产业组织 / 航运环境分类
- 📝 **论文卡片**：
  - 标题、作者、发表日期
  - arXiv 分类、相关性得分（⭐）
  - 匹配的关键词标签
  - 摘要预览
  - 直达链接（查看详情 + 下载PDF）
- 📎 **附件**：Markdown 格式完整报告

---

## 🎯 相关性评分机制

系统通过 **核心关键词** 和 **扩展关键词** 两级体系来筛选文章：

### 关键词分级

- **核心关键词**：`keywords.txt` 中"扩展"之前的关键词，文章**必须匹配至少一个**才会被收录
- **扩展关键词**：`keywords.txt` 中"扩展"之后的关键词，匹配后额外加分

### 评分规则

| 匹配类型 | 标题匹配 | 摘要匹配 |
|----------|----------|----------|
| 核心关键词 | +5.0 | +2.0 |
| 扩展关键词 | +2.0 | +0.5 |
| 经济学相关分类 | - | +0.5 |
| 1天内发布 | - | +2.0 |
| 3天内发布 | - | +1.0 |

### 过滤机制

- **必须匹配** 至少一个核心关键词，否则直接过滤
- 低于 `min_score_threshold`（默认 2.0）的文章会被过滤

### 排序方式

- **默认**：按相关性得分降序
- **可选**：按引用次数降序（需开启 `sort_by_citations`）

---

## 🐛 故障排查

### SSH 连接问题

```bash
# 测试 SSH 连接
ssh -T git@github.com

# 如果失败，重新添加密钥
ssh-add ~/.ssh/id_ed25519
```

### 邮件发送失败

| 错误 | 解决方案 |
|------|----------|
| 535 认证失败 | 检查授权码是否正确（不是登录密码）|
| 连接超时 | 检查网络或防火墙设置 |
| 邮件进垃圾箱 | 将发件人添加到通讯录 |

### GitHub Actions 问题

| 问题 | 解决方案 |
|------|----------|
| 工作流失败 | 检查 Secrets 是否配置正确 |
| 收不到邮件 | 使用 `test_email: true` 手动测试 |
| 重复推送 | 检查 `paper_history.json` 是否正常提交 |

---

## 📋 更新日志

- **v1.2**: 新增 GitHub Actions 云端部署支持，SSH 配置
- **v1.1**: 新增邮件推送功能，支持 HTML 格式
- **v1.0**: 初始版本，关键词搜索、相关性排序、Markdown 报告

---

## 📄 许可证

MIT License

---

## 💡 建议

- **日常使用**：推荐 GitHub Actions 云端部署，零成本免维护
- **测试调试**：推荐本地运行，快速验证配置
- **关键词调整**：编辑 `keywords.txt` 后 push 到仓库即可生效（云端）
- **代码推送**：使用 SSH 方式，免密码更安全

有任何问题，欢迎提交 Issue！
