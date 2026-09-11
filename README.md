# 📚 知乎收藏夹爬取分析工具

> 爬取你知乎收藏的所有回答和文章，**智能评分筛选精华**，词频分析，生成交互式HTML报告，帮你快速看完收藏的核心内容，再也不用"收藏即吃灰"。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

## ✨ 核心功能

### 🧠 智能精华筛选（6维度评分）
不再只按点赞排序！综合6个维度给每个收藏内容打分：

| 维度 | 权重 | 说明 |
|------|------|------|
| 👍 赞同数 | 35% | 社区认可度 |
| 💬 评论数 | 15% | 讨论热度 |
| 📏 内容长度 | 15% | 信息量（500-5000字最佳） |
| 🔑 关键词密度 | 15% | 专业度信号（首先、其次、分析、数据等） |
| 👤 作者影响力 | 10% | 作者粉丝数 |
| ⏰ 收藏时效 | 10% | 最近收藏的内容有加成 |

### 📥 数据爬取
- 📁 **所有收藏夹** — 自动获取你的全部收藏夹
- 📝 **收藏内容** — 回答+文章，支持分页爬取
- 👤 **作者信息** — 作者名称、粉丝数、简介
- 📅 **收藏时间** — 每条内容的收藏时间

### 📊 9大分析维度
1. 🏆 **精华收藏TOP15** — 智能评分排序，附6维度得分
2. 🔤 **内容词频** — 关键词TOP30，一眼知道你收藏的都是什么
3. 📝 **标题词频** — 收藏标题关键词TOP20
4. 👤 **作者分布** — 收藏最多的作者TOP15
5. 📅 **收藏时间** — 按月统计收藏趋势
6. 📊 **类型分布** — 回答vs文章占比
7. 👍 **赞同分布** — 赞同数区间统计
8. 📁 **收藏夹列表** — 所有收藏夹详情
9. 📈 **高赞内容** — 按赞同数排序TOP10

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
# 或手动安装
pip install requests jieba beautifulsoup4
```

### 2. 获取知乎Cookie（重要！）

1. 用浏览器登录知乎
2. 按 `F12` → 切换到 `Application`（应用）标签
3. 左侧找到 `Cookies` → `https://www.zhihu.com`
4. 找到 `z_c0`，复制它的 Value

### 3. 运行工具

```bash
# 基本用法（输入你的知乎主页链接）
python zhihu_favorites_analyzer.py https://www.zhihu.com/people/你的ID --cookie "你的z_c0值"

# 只输入用户ID
python zhihu_favorites_analyzer.py 你的ID --cookie "你的z_c0值"

# 把Cookie存到文件，不用每次输入
echo "你的z_c0值" > cookie.txt
python zhihu_favorites_analyzer.py 你的ID --cookie-file cookie.txt

# 限制每个收藏夹爬取数量（收藏多的先用这个测试）
python zhihu_favorites_analyzer.py 你的ID --cookie "xxx" --max-items 100

# 指定输出文件名
python zhihu_favorites_analyzer.py 你的ID --cookie "xxx" -o my_favorites.html
```

### 4. 查看报告

运行完成后，生成 `zhihu_favorites_{你的ID}.html`，用浏览器打开即可。

## 📊 报告预览

报告包含9个分析标签页，每个收藏内容显示：
- 类型标签（回答/文章）
- 标题、作者、赞同数、评论数、字数
- 收藏时间、原文链接
- 6维度评分条（赞同/评论/长度/关键词/作者/时效）
- 内容摘要（前400字）

## 🛠️ 技术栈

| 技术 | 用途 |
|------|------|
| Python 3 | 核心爬取与分析 |
| requests | 调用知乎API |
| jieba | 中文分词 |
| BeautifulSoup | HTML内容清洗 |
| ECharts 5 | 交互式图表 |

## ⚙️ 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `user` | 知乎用户主页链接或ID（必填） | - |
| `--cookie` | 知乎Cookie（z_c0值） | - |
| `--cookie-file` | Cookie文件路径 | - |
| `--max-items` | 每个收藏夹最多爬取内容数 | 500 |
| `--output, -o` | 输出HTML文件路径 | 自动生成 |

## 📂 项目结构

```
zhihu-favorites-analyzer/
├── zhihu_favorites_analyzer.py   # 主程序
├── requirements.txt               # 依赖列表
├── README.md                      # 项目说明
├── LICENSE                        # MIT协议
└── .gitignore
```

## 🎯 使用场景

- 📚 **收藏清理** — 快速看完收藏的精华内容，清理"收藏即吃灰"
- 📖 **主题学习** — 分析某个收藏夹的内容主题和关键词
- 👤 **作者关注** — 发现你收藏最多的作者，关注更多优质内容
- 📈 **收藏趋势** — 看你每个月收藏了多少内容
- ⏱️ **节省时间** — 不用逐条点开看，直接看精华摘要

## ⚠️ 注意事项

1. **Cookie有效期** — 知乎Cookie会过期，失效后重新获取
2. **爬取频率** — 脚本已内置延时，请勿过于频繁
3. **数据量** — 收藏特别多的话可能需要较长时间，建议先用 `--max-items` 限制
4. **内容版权** — 爬取的数据仅供个人学习使用

## 🔧 常见问题

**Q: 提示401未授权？**
A: Cookie无效或已过期，重新获取 z_c0。

**Q: 收藏夹为空？**
A: 可能是Cookie权限不足，确保登录的是你自己的账号。

**Q: 爬取速度很慢？**
A: 为了避免被封IP，脚本内置了延时。收藏多的话可以用 `--max-items` 限制。

**Q: 可以只分析某个收藏夹吗？**
A: 当前版本会分析所有收藏夹。后续版本会支持指定收藏夹。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支
3. 提交修改
4. 推送到分支
5. 开启 Pull Request

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源协议。

## ⚠️ 免责声明

- 本工具仅供学习和研究使用
- 请遵守知乎的用户协议和相关法律法规
- 请勿用于商业用途或大规模爬取
- 使用本工具产生的任何后果由使用者自行承担

---

**如果这个工具帮你解决了"收藏即吃灰"的问题，欢迎给个 ⭐ Star 支持一下！**
