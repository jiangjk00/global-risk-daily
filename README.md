# 全球风险日报 · 自动生成系统（零基础部署版）

每个**中国工作日早上 11:00** 自动生成一期《全球风险日报》，覆盖：
1. 美西方及盟友（日韩菲印）涉华动向（含正负面，含盟友企业不利动态、中国台湾地区表态行动）
2. 乌克兰危机（**各方表态**：美俄乌三方及欧盟/北约等；**战场动态**：具体打击地点与影响；**经济数据**：港口出口量、黑海航运、通胀汇率等受战争影响指标）
3. 中东局势（伊朗核、巴以、霍尔木兹、涉金融机构制裁）
4. 其他（朝鲜、原油等大宗商品、各国重大政治经济事件）

**新增能力（本版）**
- 🔎 **检索源扩展**：在免费 GDELT 全球新闻库基础上，额外纳入**中文权威/财经源**——
  中国外交部(fmprc.gov.cn)、财联社(cls.cn)、金十数据(jin10.com)、界面新闻(jiemian.com)、
  新华网、央视、参考消息、中国新闻网，并补充中文 RSS。
- 🌍 **海外权威媒体定向检索**：Reuters、AP、BBC、Bloomberg、WSJ、FT、Guardian、
  Al Jazeera、NHK、共同社、韩联社、CNA 等 20+ 海外权威媒体（GDELT 域名索引）。
- ✅ **来源准确性保障**：定向检索结果必须通过**域名白名单校验**（url 主域名命中白名单，
  聚合/转载站自动剔除）；LLM 只允许使用提供的来源链接，不得编造或替换。
- 🔗 **来源内联**：每条事实后附**可点击的来源链接**，直接在正文复查，不再单独列来源表。
- 📲 **自动推送**：报告生成后，自动发到你的**微信 / 邮箱 / 企业微信 / 钉钉 / 飞书 / Telegram**。
- ⏱️ **严格时间窗**：仅取「上一个工作日 12:00 ～ 今日 11:00（北京）」，窗口外旧闻自动剔除。

---

## 你只需要做 3 件事
1. 注册一个 **DeepSeek** 账号，拿到 API Key（约 2 分钟，几块钱可用很久）。
2. 在 GitHub 上**新建一个仓库**，把本项目的几个文件**原样上传**。
3. 在仓库里**填秘钥（Secrets）**，然后点一下"运行"测试。

完成之后，每个工作日 11:00 它就会自己跑、自己把日报推给你，你什么都不用管。

---

## 一步一步（网页操作，不用装任何软件）

### 第 1 步：拿到 DeepSeek API Key
1. 打开 https://platform.deepseek.com 注册并登录。
2. 右上角点 **API Keys** → **Create new key** → 复制生成的 key（形如 `sk-xxxx`）。
3. 首次使用需充值（最低约 10 元），日常跑日报每月不到 1 元。

> 想用别的模型也行（通义、智谱、OpenAI 等），只要兼容 OpenAI 接口，改 `LLM_BASE_URL` / `LLM_MODEL` 即可。

### 第 2 步：新建 GitHub 仓库
1. 打开 https://github.com ，登录你的账号。
2. 点右上角 **+** → **New repository**。
3. Repository name 填 `global-risk-daily`，选 **Public**（公开，Actions 免费且不受限）。
4. 勾选 **Add a README file**，点 **Create repository**。

### 第 3 步：上传项目文件
本文件夹包含：
```
generate_daily_risk_report.py      # 主脚本（必须）
notify.py                          # 推送模块（必须）
requirements.txt                   # 依赖（必须）
.env.example                       # 配置样例（参考用）
.github/workflows/daily_report.yml # 定时任务（必须）
```
在 GitHub 网页上逐个创建（最稳的方式）：
1. 进入你的仓库，点 **Add file** → **Create new file**。
2. 在文件名框输入 `generate_daily_risk_report.py`，把对应文件内容**全部粘贴**进去，点 **Commit new file**。
3. 重复创建 `notify.py`、`requirements.txt`、`.env.example`。
4. 创建定时任务：文件名框输入 **`.github/workflows/daily_report.yml`**（注意前面带点和斜杠，GitHub 会自动建好目录），粘贴内容，提交。

> 嫌一个个建麻烦？也可以在你电脑上把文件夹整理好，直接用仓库页面的 **Add file → Upload files** 把整个文件夹拖进去（`.github` 这种隐藏目录也能一起上传）。

### 第 4 步：填秘钥（Secrets）
1. 进入仓库，点上方 **Settings** → 左侧 **Secrets and variables** → **Actions** → **New repository secret**。
2. 先填 **3 个必填项**（LLM 相关）：
   | Name | Secret 值（填你的） |
   |---|---|
   | `LLM_API_KEY` | 第 1 步复制的 `sk-xxxx` |
   | `LLM_BASE_URL` | `https://api.deepseek.com/v1` |
   | `LLM_MODEL` | `deepseek-chat` |
3. **推送渠道按需填**（下面选一种即可，没填的自动跳过，不影响出报）：

   #### 🅰 微信推送（最省事，推荐手机端）
   - 打开 https://sct.ftqq.com （或 https://sctapi.ftqq.com），用微信扫码登录。
   - 在「发送消息」页复制你的 **SendKey**（形如 `SCTxxxxxxxxxxxx`）。
   - 新建 Secret：`SERVERCHAN_SENDKEY` = 上面的 SendKey。
   - 之后每天日报会直接推到你的**微信**服务通知里。

   #### 🅱 邮箱推送（QQ/163/Gmail 等）
   - 你需要：邮箱账号 + **授权码**（不是登录密码；QQ/163 在邮箱"设置→账户"里开启 SMTP 并生成授权码）。
   - 新建以下 Secrets：
     | Name | 值示例 |
     |---|---|
     | `EMAIL_USER` | `123456@qq.com`（发件人） |
     | `EMAIL_PASSWORD` | 邮箱授权码（非登录密码） |
     | `EMAIL_TO` | `收件人@xx.com`（可多个，逗号分隔；不填默认发给自己） |
     | `EMAIL_SMTP_HOST` | `smtp.qq.com`（QQ）/ `smtp.163.com`（163）/ `smtp.gmail.com`（Gmail） |
     | `EMAIL_SMTP_PORT` | `465`（SSL，默认）/ `587`（STARTTLS 时设 `EMAIL_USE_SSL=false`） |
     | `EMAIL_USE_SSL` | `true`（465 用）/ `false`（587 用） |
   - 邮件正文为日报全文，并**附件**带上 `.md` 文件。

   #### 🅲 企业微信 / 钉钉 / 飞书 机器人
   - 在对应群聊里添加「自定义机器人」，复制 Webhook 地址。
   - 新建 Secret：`WECOM_WEBHOOK` / `DINGTALK_WEBHOOK` / `FEISHU_WEBHOOK` = 该 Webhook 地址。

   #### 🅳 Telegram
   - 找 @BotFather 创建 Bot 拿到 **Token**；把 Bot 加进频道/私聊，用 @userinfobot 查到 **Chat ID**。
   - 新建 Secret：`TG_BOT_TOKEN` = Token；`TG_CHAT_ID` = Chat ID。

### 第 5 步：开启并测试
1. 点仓库上方 **Actions** 标签 → 左侧看到 **全球风险日报** 工作流。
2. 点 **I understand my workflows, go ahead and enable them**（首次出现时）。
3. 点 **Run workflow** → **Run workflow**（手动触发一次测试）。
4. 等 1–3 分钟，刷新页面看到绿色 ✓ 即成功；进入 `daily_reports/` 能看到生成的日报，手机/邮箱也应收到推送。

### 之后
- **工作日 11:00（北京时间）自动出报并推送**，无需任何操作。
- 在 `daily_reports/` 查看/下载历史日报（Markdown 格式，来源链接已内联正文）。
- 想立即看效果，随时去 Actions 点 **Run workflow**。

---

## 费用
- GitHub Actions：**免费**（Public 仓库无限时长）。
- DeepSeek：`deepseek-chat` 约 ¥1/百万输入 tokens，每期日报成本**不到 1 分钱**，首次充值 ¥10 可用非常久。
- 推送渠道：Server酱/企业微信/钉钉/飞书/Telegram **免费**；邮箱用你自有邮箱，免费。

---

## 自定义
- **改出报时间**：编辑 `.github/workflows/daily_report.yml` 里的 `cron: "0 3 * * 1-5"`。
  GitHub 用 UTC 时间。北京时间 11:00 = UTC 03:00（已设好）。例如 9:00 北京 = 1:00 UTC → `"0 1 * * 1-5"`。
- **改关注板块/关键词**：编辑 `generate_daily_risk_report.py` 顶部的 `SECTIONS` 字典。
- **加减中文源**：编辑同文件顶部的 `CHINESE_DOMAINS`（GDELT 域名过滤）与 `RSS_FEEDS`（RSS 补充）。
  想加别的站点，把域名写进 `CHINESE_DOMAINS` 即可（前提是 GDELT 索引了该站）。
- **加减海外权威媒体**：编辑同文件顶部的 `FOREIGN_MEDIA_DOMAINS` 白名单（如 Reuters/AP/BBC 等）。
  该名单同时用于定向检索与来源校验，不在名单内的来源会被自动剔除。
- **节假日不出报**：脚本已内置中国节假日判断（调用 timor.tech 接口），周末和法定节假日自动跳过。
- **时间窗口**：脚本自动取"上一个工作日 12:00 ～ 今日 11:00"，与你的要求一致，无需改。

---

## 故障排查
- **报告没生成 / Actions 报错**：去 Actions 看红色运行的日志。最常见是 `LLM_API_KEY` 没填对，或 DeepSeek 余额不足。
- **推送没收到**：
  - 微信：检查 `SERVERCHAN_SENDKEY` 是否填对；登录 sct.ftqq.com 看「推送日志」。
  - 邮箱：检查 SMTP 主机/端口/授权码；QQ 邮箱需开启 IMAP/SMTP 且用**授权码**而非密码。
  - 企业微信/钉钉/飞书：检查 Webhook 地址是否完整、群机器人是否被禁用。
- **定时没跑**：GitHub 会在仓库 **60 天无活动**后暂停定时任务。解决：每隔一阵（或自己想看时）手动 Run workflow 一次即可恢复。
- **某天新闻很少/为空**：该窗口全球确实无重大事件，或 GDELT 检索波动。可重试或手动触发。
- **想换新闻源**：当前用免费的 GDELT + 中文 RSS。如需更精准（如 Reuters/BBC 专线），可把 `gdelt_query()` 替换为 NewsAPI / Brave Search API（需各自申请 key）。

---

## 数据来源与免责
- 新闻检索：GDELT Doc 2.0（免费全球新闻数据库）+ 中文权威/财经站点域名索引 + 海外权威媒体白名单（Reuters/AP/BBC/Bloomberg 等）+ 中文 RSS。
- 来源准确性：中文源与海外媒体定向检索均通过**域名白名单校验**，仅保留白名单内媒体的条目；LLM 只使用提供条目的原文链接，并以文内可点击链接标注。
- 内容整理：LLM 基于检索结果生成，可能存在遗漏或时效偏差；来源以正文内可点击链接标注。
- 本报告仅供内部风险研判参考，不构成投资或行动建议；涉及中国台湾地区的事项遵循一个中国原则。
