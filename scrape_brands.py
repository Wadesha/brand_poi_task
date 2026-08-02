# -*- coding: utf-8 -*-
"""
4品牌POI批量采集系统（覆盖全国地级市）
支持：品牌队列、页码级断点、配额监控、网络错误重试、每日接力
"""
import os, sys, re, json, time, argparse, requests
from datetime import datetime
from itertools import cycle

sys.stdout.reconfigure(encoding='utf-8')

# ── API Key 加载（隐私安全：不硬编码本地路径，避免泄露用户目录与密钥）──
# 读取优先级：
#   1) 环境变量 TENCENT_MAP_KEYS（多个 key 用逗号或换行分隔）【推荐】
#   2) 本地配置文件 config/tencent_keys.txt（每行一个 key，已被 .gitignore 忽略，不会入库）
# 详见 README 的「环境准备」一节。
def load_api_keys():
    env_keys = os.environ.get("TENCENT_MAP_KEYS", "").strip()
    if env_keys:
        return [k.strip() for k in re.split(r"[\s,]+", env_keys) if k.strip()]
    for p in ("config/tencent_keys.txt", "tencent_keys.txt"):
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            keys = re.findall(r"([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5})", content)
            if keys:
                return keys
    return []
QUEUE_FILE   = "brand_queue.json"
PROGRESS_FILE = "brand_poi_progress.json"
DATA_FILE     = "brand_poi_data.json"
LOG_FILE      = "brand_scrape_log.txt"
REPORT_FILE   = "采集进度报告.md"

# 中国全部地级市列表（293个）
CITIES = [
    "北京","天津","石家庄","唐山","秦皇岛","邯郸","邢台","保定","张家口","承德","沧州","廊坊","衡水",
    "太原","大同","阳泉","长治","晋城","朔州","晋中","运城","忻州","临汾","吕梁",
    "呼和浩特","包头","乌海","赤峰","通辽","鄂尔多斯","呼伦贝尔","巴彦淖尔","乌兰察布","兴安盟","锡林郭勒盟","阿拉善盟",
    "沈阳","大连","鞍山","抚顺","本溪","丹东","锦州","营口","阜新","辽阳","盘锦","铁岭","朝阳","葫芦岛",
    "长春","吉林","四平","辽源","通化","白山","松原","白城","延边朝鲜族自治州",
    "哈尔滨","齐齐哈尔","鸡西","鹤岗","双鸭山","大庆","伊春","佳木斯","七台河","牡丹江","黑河","绥化","大兴安岭地区",
    "上海",
    "南京","无锡","徐州","常州","苏州","南通","连云港","淮安","盐城","扬州","镇江","泰州","宿迁",
    "杭州","宁波","温州","嘉兴","湖州","绍兴","金华","衢州","舟山","台州","丽水",
    "合肥","芜湖","蚌埠","淮南","马鞍山","淮北","铜陵","安庆","黄山","滁州","阜阳","宿州","六安","亳州","池州","宣城",
    "福州","厦门","莆田","三明","泉州","漳州","南平","龙岩","宁德",
    "南昌","景德镇","萍乡","九江","新余","鹰潭","赣州","吉安","宜春","抚州","上饶",
    "济南","青岛","淄博","枣庄","东营","烟台","潍坊","济宁","泰安","威海","日照","临沂","德州","聊城","滨州","菏泽",
    "郑州","开封","洛阳","平顶山","安阳","鹤壁","新乡","焦作","濮阳","许昌","漯河","三门峡","南阳","商丘","信阳","周口","驻马店","济源",
    "武汉","黄石","十堰","宜昌","襄阳","鄂州","荆门","孝感","荆州","黄冈","咸宁","随州","恩施土家族苗族自治州",
    "长沙","株洲","湘潭","衡阳","邵阳","岳阳","常德","张家界","益阳","郴州","永州","怀化","娄底","湘西土家族苗族自治州",
    "广州","韶关","深圳","珠海","汕头","佛山","江门","湛江","茂名","肇庆","惠州","梅州","汕尾","河源","阳江","清远","东莞","中山","潮州","揭阳","云浮",
    "南宁","柳州","桂林","梧州","北海","防城港","钦州","贵港","玉林","百色","贺州","河池","来宾","崇左",
    "海口","三亚","三沙","儋州",
    "重庆",
    "成都","自贡","攀枝花","泸州","德阳","绵阳","广元","遂宁","内江","乐山","南充","眉山","宜宾","广安","达州","雅安","巴中","资阳","阿坝藏族羌族自治州","甘孜藏族自治州","凉山彝族自治州",
    "贵阳","六盘水","遵义","安顺","毕节","铜仁","黔西南布依族苗族自治州","黔东南苗族侗族自治州","黔南布依族苗族自治州",
    "昆明","曲靖","玉溪","保山","昭通","丽江","普洱","临沧","楚雄彝族自治州","红河哈尼族彝族自治州","文山壮族苗族自治州","西双版纳傣族自治州","大理白族自治州","德宏傣族景颇族自治州","怒江傈僳族自治州","迪庆藏族自治州",
    "拉萨","日喀则","昌都","林芝","山南","那曲","阿里地区",
    "西安","铜川","宝鸡","咸阳","渭南","延安","汉中","榆林","安康","商洛",
    "兰州","嘉峪关","金昌","白银","天水","武威","张掖","平凉","酒泉","庆阳","定西","陇南","临夏回族自治州","甘南藏族自治州",
    "西宁","海东","海北藏族自治州","黄南藏族自治州","海南藏族自治州","果洛藏族自治州","玉树藏族自治州","海西蒙古族藏族自治州",
    "银川","石嘴山","吴忠","固原","中卫",
    "乌鲁木齐","克拉玛依","吐鲁番","哈密","昌吉回族自治州","博尔塔拉蒙古自治州","巴音郭楞蒙古自治州","阿克苏地区","克孜勒苏柯尔克孜自治州","喀什地区","和田地区","伊犁哈萨克自治州","塔城地区","阿勒泰地区"
]

ALL_BRANDS = ["蜜雪冰城","菜鸟驿站","瑞幸咖啡","星巴克"]
PRIORITY_BRANDS = ["蜜雪冰城","菜鸟驿站","瑞幸咖啡","星巴克"]

# 读取 API Keys（隐私安全方式）
api_keys = load_api_keys()
if not api_keys:
    print("[!] 未找到腾讯地图 API Key。")
    print("    [方法1] 设置环境变量:  export TENCENT_MAP_KEYS='KEY1,KEY2'")
    print("    [方法2] 在 config/tencent_keys.txt 中每行放一个 key（参考 .env.example）")
    sys.exit(1)
print(f"[*] {len(api_keys)} 个腾讯API Key")

key_cycle = cycle(api_keys)
DAILY_LIMIT_PER_KEY = 8000

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def update_report(progress, queue, phase="进行中"):
    """更新采集进度报告（Markdown格式）"""
    try:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report_lines = []
        report_lines.append("# 品牌POI采集进度报告\n")
        report_lines.append(f"**更新时间**: {now}\n")
        report_lines.append(f"**当前状态**: {phase}\n")
        report_lines.append(f"**覆盖城市**: {len(CITIES)} 个地级市\n")
        report_lines.append("\n---\n")
        
        report_lines.append("## 各品牌进度\n")
        report_lines.append("| 品牌 | 状态 | 已完成城市 | 累计POI | 进度 |")
        report_lines.append("|------|------|------------|---------|------|")
        
        total_pois = 0
        total_completed_cities = 0
        
        for item in queue:
            brand = item["brand"]
            status = item["status"]
            if brand in progress:
                info = progress[brand]
                completed_cities = len(info["completed_cities"])
                poi_count = info["total_collected"]
                total_pois += poi_count
                total_completed_cities += completed_cities
                
                percentage = round(completed_cities / len(CITIES) * 100, 1)
                status_emoji = "✅" if status == "done" else "🔄" if status == "running" else "⏳"
                
                report_lines.append(f"| {status_emoji} {brand} | {status} | {completed_cities}/{len(CITIES)} | {poi_count:,} | {percentage}% |")
        
        overall_percentage = round(total_completed_cities / (len(ALL_BRANDS) * len(CITIES)) * 100, 1)
        
        report_lines.append("\n---\n")
        report_lines.append("## 总体统计\n")
        report_lines.append(f"- **总POI数量**: {total_pois:,}\n")
        report_lines.append(f"- **已完成城市**: {total_completed_cities}/{len(ALL_BRANDS) * len(CITIES)}\n")
        report_lines.append(f"- **总体进度**: {overall_percentage}%\n")
        
        report_content = "\n".join(report_lines)
        
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(report_content)
            
    except Exception as e:
        print(f"[!] 更新报告失败: {e}")

# ── 队列管理 ──
def init_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    completed = set()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            prog = json.load(f)
        for brand, info in prog.items():
            if len(info.get("completed_cities", [])) >= len(CITIES):
                completed.add(brand)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for brand, cities in data.items():
            if len(cities) >= len(CITIES):
                completed.add(brand)
    queue = []
    seen = set()
    for b in PRIORITY_BRANDS:
        if b in ALL_BRANDS and b not in completed:
            queue.append({"brand": b, "status": "pending", "priority": 1})
            seen.add(b)
    for b in ALL_BRANDS:
        if b not in seen and b not in completed:
            queue.append({"brand": b, "status": "pending", "priority": 2})
            seen.add(b)
    save_queue(queue)
    log(f"[*] 队列初始化: {len(queue)} 个待采集 (已跳过 {len(completed)} 个已完成)")
    return queue

def save_queue(queue):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

def get_next_brand(queue):
    """返回第一个未完成的品牌（pending 或 running 均视为需要续采）"""
    for item in queue:
        if item["status"] != "done":
            return item
    return None

def mark_brand_done(queue, brand):
    for item in queue:
        if item["brand"] == brand:
            item["status"] = "done"
            break
    save_queue(queue)

def mark_brand_running(queue, brand):
    for item in queue:
        if item["brand"] == brand:
            item["status"] = "running"
            break
    save_queue(queue)

# ── 进度/数据管理 ──
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            log(f"[!] brand_poi_data.json 损坏，从 poi_data/ 重建...")
            return _rebuild_data_from_poi_files()
    return {}

def _rebuild_data_from_poi_files():
    import glob as _glob
    merged = {}
    for fp in sorted(_glob.glob("poi_data/*.json")):
        brand = os.path.splitext(os.path.basename(fp))[0]
        try:
            with open(fp) as f:
                merged[brand] = json.load(f)
        except:
            pass
    # atomic write
    import tempfile, shutil
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, dir='.', encoding='utf-8')
    json.dump(merged, tmp, ensure_ascii=False)
    tmp.close()
    shutil.move(tmp.name, DATA_FILE)
    log(f"[*] 已从 poi_data/ 重建 {len(merged)} 品牌")
    return merged

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── API调用 ──
# 全局：记录失效的key，避免反复使用
_INVALID_KEYS = set()

def search_poi(keyword, city, page_index=1, page_size=20, retry_on_invalid=True):
    global key_cycle, api_keys, _INVALID_KEYS

    # 如果所有key都已失效，直接报错
    valid_keys = [k for k in api_keys if k not in _INVALID_KEYS]
    if not valid_keys:
        return {"status": 190, "message": "ALL_KEYS_INVALID"}

    url = "https://apis.map.qq.com/ws/place/v1/search"
    for attempt in range(len(valid_keys)):
        key = next(key_cycle)
        # 跳过已知失效的key
        if key in _INVALID_KEYS:
            continue
        params = {
            "keyword": keyword,
            "boundary": f"region({city},0)",
            "page_size": page_size,
            "page_index": page_index,
            "key": key,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            result = resp.json()
            status = result.get("status", -1)
            # key 失效（190）或无效签名（311）均标记为失效
            if status in (190, 311):
                _INVALID_KEYS.add(key)
                log(f"[!] Key 失效( status={status}): {key[:20]}...，剩余有效key: {len(api_keys)-len(_INVALID_KEYS)}")
                continue  # 换下一个key重试
            return result
        except Exception as e:
            return {"status": -1, "message": str(e)}
    # 所有有效key都试过了
    return {"status": 190, "message": "ALL_KEYS_INVALID"}

# ── 核心采集 ──
def scrape_brand(brand, cities, progress, data, queue):
    log(f"\n{'='*60}")
    log(f"[*] 开始采集: {brand}")
    log(f"{'='*60}")

    mark_brand_running(queue, brand)

    if brand not in progress:
        progress[brand] = {"completed_cities": [], "current_city": None, "current_page": 1, "total_collected": 0}
    if brand not in data:
        data[brand] = {}

    # 如果data中该品牌是list格式（旧格式），转为dict格式 {city: [pois]}
    if isinstance(data[brand], list):
        old_list = data[brand]
        new_dict = {}
        for poi in old_list:
            city = poi.get("city", "未知")
            if city not in new_dict:
                new_dict[city] = []
            new_dict[city].append(poi)
        data[brand] = new_dict
        log(f"[*] {brand} 数据格式转换: list({len(old_list)}) -> dict({len(new_dict)} cities)")

    bp = progress[brand]
    bd = data[brand]

    # 兼容 done_cities / total_records 旧格式
    if "done_cities" in bp:
        bp.setdefault("completed_cities", bp.pop("done_cities"))
    bp.setdefault("completed_cities", [])
    if "total_records" in bp:
        bp.setdefault("total_collected", bp.pop("total_records"))
    bp.setdefault("total_collected", 0)
    bp.setdefault("current_city", None)
    bp.setdefault("current_page", 1)

    # 显示初始进度
    completed_count = len(bp["completed_cities"])
    total_cities = len(cities)
    log(f"[*] 当前进度: 已完成 {completed_count}/{total_cities} 城市, 累计 {bp['total_collected']} 条POI")

    for idx, city in enumerate(cities):
        if city in bp["completed_cities"]:
            continue
        
        current_progress = idx + 1
        log(f"\n[*] [{current_progress}/{total_cities}] 开始采集城市: {city}")

        bp["current_city"] = city
        bp["current_page"] = 1
        city_pois = []
        page = 1
        max_page = 50

        while page <= max_page:
            # 网络错误重试（最多3次）
            result = None
            for attempt in range(3):
                result = search_poi(brand, city, page)
                if result.get("status") == 0:
                    break
                err = result.get("message", "")
                if "配额" in err or "limit" in err.lower() or "上限" in err:
                    log(f"[!] 配额耗尽: {err}")
                    save_progress(progress)
                    save_data(data)
                    save_queue(queue)
                    return False
                if "IP未被授权" in err:
                    time.sleep(0.5)
                    continue
                if attempt < 2:
                    log(f"    [!] 重试 {attempt+1}/3: {err}")
                    time.sleep(1)

            if result is None or result.get("status") != 0:
                err = result.get("message", "未知错误") if result else "请求失败"
                # key 全部失效：等待后重试（给外部更新key的时间）
                if result and result.get("status") in (190, 311):
                    log(f"    [!] 所有Key失效！等待60秒后重试...")
                    save_progress(progress)
                    save_data(data)
                    save_queue(queue)
                    time.sleep(60)
                    continue  # 重新进入while循环，重新调用search_poi
                log(f"    [!] {city} 第{page}页最终失败: {err}")
                break

            pois = result.get("data", [])
            count = result.get("count", 0)

            if not pois:
                break

            for poi in pois:
                loc = poi.get("location", {})
                lat = loc.get("lat")
                lng = loc.get("lng")
                # 腾讯格式：lat,lng；统一转换为高德格式：lng,lat
                location_str = f"{lng},{lat}" if lng and lat else ""
                city_pois.append({
                    "id": poi.get("id"),
                    "name": poi.get("title"),
                    "address": poi.get("address"),
                    "category": poi.get("category"),
                    "lat": lat,
                    "lng": lng,
                    "location": location_str,  # 统一格式：lng,lat
                    "city": city,
                })

            log(f"    [OK] {city} 第{page}页: {len(pois)}条 (总计{count}条)")
            bp["current_page"] = page

            if len(city_pois) >= count or len(pois) < 20:
                break

            page += 1
            time.sleep(0.3)

        bd[city] = city_pois
        bp["completed_cities"].append(city)
        bp["total_collected"] += len(city_pois)
        bp["current_city"] = None
        bp["current_page"] = 1

        new_completed_count = len(bp["completed_cities"])
        log(f"  [DONE] {city}: {len(city_pois)} 条 | 累计: {bp['total_collected']} 条 | 进度: {new_completed_count}/{total_cities} ({round(new_completed_count/total_cities*100, 1)}%)")
        save_progress(progress)
        save_data(data)
        # 每完成一个城市更新一次报告
        update_report(progress, queue, "进行中")

    final_completed = len(bp["completed_cities"])
    log(f"\n{'='*60}")
    log(f"[+] {brand} 采集完成！")
    log(f"    - 完成城市: {final_completed}/{total_cities}")
    log(f"    - 累计POI: {bp['total_collected']} 条")
    log(f"{'='*60}")
    mark_brand_done(queue, brand)
    # 品牌完成时更新报告
    update_report(progress, queue, "进行中")
    return True

# ── Key 健康检查（启动时调用腾讯API验证，剔除失效key）──
def health_check_keys():
    global key_cycle, _INVALID_KEYS, api_keys
    valid = []
    for k in api_keys:
        if k in _INVALID_KEYS:
            continue
        try:
            r = requests.get(
                "https://apis.map.qq.com/ws/place/v1/search",
                params={"key": k, "keyword": "测试", "boundary": "region(北京,0)", "page_size": 1},
                timeout=8
            )
            d = r.json()
            if d.get("status") == 0:
                valid.append(k)
                log(f"  [OK] Key {k[:10]}...")
            else:
                _INVALID_KEYS.add(k)
                log(f"  [INV] Key {k[:10]}... status={d.get('status')}")
        except Exception as e:
            _INVALID_KEYS.add(k)
            log(f"  [ERR] Key {k[:10]}... {e}")
        time.sleep(0.2)
    api_keys[:] = valid
    key_cycle = cycle(api_keys) if valid else None
    log(f"[*] Key健康检查完成：{len(valid)}/{len(valid)+len(_INVALID_KEYS)} 有效")
    return len(valid) > 0


# ── 入口 ──
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", help="只采集指定品牌")
    parser.add_argument("--skip-key-check", action="store_true", help="跳过Key健康检查")
    args = parser.parse_args()

    log(f"\n{'='*60}")
    log(f"[*] 品牌POI采集系统启动")
    log(f"[*] 目标品牌: {', '.join(ALL_BRANDS)}")
    log(f"[*] 覆盖城市: {len(CITIES)} 个地级市")
    log(f"[*] 日志文件: {LOG_FILE}")
    log(f"{'='*60}\n")

    # Key 健康检查
    if not args.skip_key_check:
        log("[*] Key健康检查中...")
        if not health_check_keys():
            log("[!!!] 所有腾讯API Key均失效，请更新 Key 后重新运行（环境变量 TENCENT_MAP_KEYS 或 config/tencent_keys.txt）！")
            return
    else:
        log("[*] 跳过Key健康检查（--skip-key-check）")

    queue = init_queue()
    progress = load_progress()

    # 统计
    done = sum(1 for x in queue if x["status"] == "done")
    pending = sum(1 for x in queue if x["status"] == "pending")
    log(f"[*] 队列状态: {done} 完成 / {pending} 待采集 / {len(queue)} 总计")
    for item in queue:
        if item["brand"] in progress:
            info = progress[item["brand"]]
            log(f"    - {item['brand']}: {item['status']} | {len(info['completed_cities'])}城 | {info['total_collected']}条")
    
    # 更新初始报告
    update_report(progress, queue, "进行中")

    if args.brand:
        # 只跑指定品牌
        brand = args.brand
        # 用progress判断是否完成，而非data（data可能是list格式导致误判）
        if brand in progress:
            bp = progress[brand]
            cc = bp.get("completed_cities", bp.get("done_cities", []))
            if len(cc) >= len(CITIES):
                log(f"[*] {brand} 已完成（{len(cc)}/{len(CITIES)}城，跳过）")
                return
        data = load_data()
        scrape_brand(brand, CITIES, progress, data, queue)
        return

    data = load_data()

    # 自动按队列顺序采集
    while True:
        item = get_next_brand(queue)
        if item is None:
            log(f"\n{'='*60}")
            log("[*] 全部品牌采集完成！")
            log(f"{'='*60}")
            break

        brand = item["brand"]
        ok = scrape_brand(brand, CITIES, progress, data, queue)
        if not ok:
            log(f"\n[!] 采集中断（配额耗尽），请明天继续执行本脚本")
            log(f"[*] 当前中断品牌: {brand}")
            # 中断时更新报告
            update_report(progress, queue, "已中断")
            break

    # 全部完成时更新报告
    if ok:
        update_report(progress, queue, "已完成")

    # 最终统计
    log(f"\n{'='*60}")
    log("最终统计:")
    try:
        for brand in [x["brand"] for x in queue if x["status"] == "done"]:
            bd = data.get(brand, {}) if isinstance(data, dict) else {}
            if isinstance(bd, list):
                total = len(bd)
            elif isinstance(bd, dict):
                total = sum(len(v) if isinstance(v, list) else 0 for v in bd.values())
            else:
                total = 0
            log(f"  [DONE] {brand}: {total} 条")
    except Exception as e:
        log(f"  [WARN] 统计异常({e})，请查看 brand_poi_progress.json")
    running = [x["brand"] for x in queue if x["status"] == "running"]
    if running:
        log(f"  [RUNNING] {running[0]}: 中断中，明天续跑")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()