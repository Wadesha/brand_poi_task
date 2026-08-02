[🌐 在线演示（GitHub Pages）](https://wadesha.github.io/brand_poi_task/)

# 品牌门店 POI 批量采集系统

基于**腾讯地图 WebService API**，批量采集连锁品牌在全国地级市的门店位置（POI，Point of Interest），内置品牌队列、断点续传、多 Key 轮换、配额监控与每日接力能力。

> ⚠️ **数据保护**：原始采集数据、运行时文件、API Key 配置文件**默认不上传**到仓库（见文末「数据保护说明」）。

---

## 功能特性

- **多品牌队列**：按优先级依次采集多个品牌，自动跳过已完成项
- **三级遍历**：品牌 → 城市 → 分页，逐城市、逐页抓取
- **断点续传**：记录每个品牌已完成城市与当前页码，异常中断后可无缝续跑
- **多 Key 轮换**：自动剔除失效 Key，避免单个 Key 配额耗尽导致整体停滞
- **配额监控 / 每日接力**：配额耗尽自动暂停并落盘，次日重跑即接力
- **进度报告**：自动生成 `采集进度报告.md`，可视化各品牌进度

---

## 目录结构（重构后）

```
brand_poi_task/
├── scrape_brands.py          # 主采集脚本（已做隐私安全化）
├── README.md
├── .gitignore                # 保护原始数据与隐私 Key
├── .env.example              # API Key 配置示例
├── config.example.json       # 品牌队列示例
├── data/                     # 采集数据（默认不上传，见数据保护）
│   ├── brand_poi_data.json       # 合并数据 {品牌:{城市:[poi]}}
│   ├── brand_poi_progress.json   # 断点续传进度
│   ├── brand_queue.json          # 运行时队列状态
│   ├── brand_scrape_log.txt      # 运行日志
│   ├── 采集进度报告.md            # 自动生成的进度报告
│   └── poi_data/                 # 按品牌拆分的数据（蜜雪/菜鸟/瑞幸/星巴克）
└── config/
    └── tencent_keys.txt      # 本地 Key 文件（被 .gitignore 忽略，不入库）
```

---

## 环境准备

1. **Python 3.8+**
2. 安装依赖：
   ```bash
   pip install requests
   ```
3. 配置腾讯地图 API Key（**二选一**）：
   - **方式一（推荐）环境变量**：
     ```bash
     export TENCENT_MAP_KEYS="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX,第二个KEY..."
     ```
   - **方式二 本地文件**：创建 `config/tencent_keys.txt`，每行一个 Key（可参考 `.env.example`）。
   - ⚠️ Key 属于**隐私凭据**，绝不提交到仓库（已被 `.gitignore` 忽略）。

---

## 使用方法

| 场景 | 命令 |
|------|------|
| 全量采集（按队列顺序） | `python scrape_brands.py` |
| 只采集指定品牌 | `python scrape_brands.py --brand 蜜雪冰城` |
| 跳过 Key 健康检查 | `python scrape_brands.py --skip-key-check` |
| 中断后续跑 | 直接重新运行同一命令，自动从断点继续 |

**每日接力**：当某个 Key 配额耗尽，脚本会暂停并写入进度；次日重新运行即可从断点继续，无需手动干预。

---

## 数据格式

### 单条 POI 字段

| 字段 | 说明 |
|------|------|
| `id` | 腾讯地图 POI ID |
| `name` | 门店名称 |
| `address` | 门店地址 |
| `category` | 分类（如「咖啡店」） |
| `lat` / `lng` | 纬度 / 经度（腾讯坐标） |
| `location` | 统一格式 `lng,lat` |
| `city` | 所属城市 |

### 合并数据 `brand_poi_data.json`

```json
{
  "品牌名": {
    "城市名": [ { "id": "...", "name": "...", "address": "...", ... }, ... ]
  }
}
```

---

## 断点续传原理

`brand_poi_progress.json` 为每个品牌记录：
- `completed_cities`：已完成城市列表
- `current_city` / `current_page`：当前城市与页码
- `total_collected`：累计 POI 数

每完成一个城市即落盘。脚本启动时读取该文件，跳过已完成城市，从断点继续。

---

## 数据保护说明

以下文件 / 目录均被 `.gitignore` 忽略，**不会**进入 Git 仓库：

- `data/`（全部原始与采集数据，含 `poi_data/`）
- `brand_poi_data.json`、`brand_poi_progress.json`、`brand_queue.json`、`brand_scrape_log.txt`、`采集进度报告.md`
- `.env`、`config/tencent_keys.txt`（API Key 凭据）

如需共享数据，请先**脱敏**并在**显式确认**后单独处理，切勿直接提交含点位或个人信息的文件。

> 🔒 真实采集数据已隔离存放于私有仓库 [brand_poi_task_private](https://github.com/Wadesha/brand_poi_task_private)（private，仅授权协作者可见），与公开代码仓库分离，互不影响。

---

## 注意事项

- 内置城市列表为 **293 个地级行政区**；进度报告中出现的「338」为含重复 / 区县级计数的口径，二者存在差异，属已知现象。
- 腾讯地图 Key 有每日配额上限，建议使用多个 Key 并错峰运行。
- 采集得到的门店地址为公开信息，但批量导出仍建议遵循平台服务条款与数据合规要求。
