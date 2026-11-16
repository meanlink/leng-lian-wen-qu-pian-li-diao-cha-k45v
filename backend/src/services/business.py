"""两条冷链路线的经验分布与温区暴露复核。"""
import math
import random
import numpy as np
from scipy import stats


def metadata():
    return {"name": "冷链温区偏离调查", "short": "cold-excursion", "tagline": "不只看最高温，核对整条路线的温度分布。",
            "client": "澄源冷运 · 18 名调度员，生物试剂城配线路试运行组", "workflow": "调度把温度记录贴到 Excel，以最高温决定是否调查路线。",
            "pains": ["单个峰值无法说明持续暴露", "不同线路分布不便比较", "阈值调整后需手工重算"], "upstream": "温度记录器导出的 CY_route_temperature.csv", "downstream": "冷运质控经理据分布差异安排包装复核",
            "entities": ["路线温度样本", "温区调查", "质控分发简报"], "dataset_name": "沪东 A / B 路线 · 240 个测温点",
            "columns": [{"key": "sample", "label": "采样点", "type": "string"}, {"key": "route", "label": "路线", "type": "string"}, {"key": "minute", "label": "发车后分钟", "type": "number"}, {"key": "temperature", "label": "温度 °C", "type": "number"}],
            "parameters": [{"key": "upper", "label": "温区上界 °C", "type": "number", "default": 8, "min": 2, "max": 15}, {"key": "alpha", "label": "显著性水平", "type": "select", "default": "0.05", "options": [{"value": "0.01", "label": "0.01"}, {"value": "0.05", "label": "0.05"}, {"value": "0.1", "label": "0.10"}]}],
            "workbench_title": "温度分布比对", "action_label": "执行 KS 与超温复核", "unit": "°C", "accent": "oklch(48% 0.08 184)", "style": "coldroom",
            "seed_story": ["08:00 导入 CY_route_temperature.csv，沪东 A/B 各 120 点。", "08:15 核对采样间隔为 2 分钟。", "08:30 质控将温区上界设为 8°C。", "08:35 执行双样本 KS 比较，打开经验分布曲线。", "08:50 查看两路线超温比例与 P95。", "09:10 将上界设为 7°C，评估更严格口径。", "09:30 导出调查明细，安排 B 线保温包装复核。"],
            "method": "KS 统计量 D=sup|F_A(t)−F_B(t)|，双侧双样本检验；超温率=count(T>上界)/有效采样数；ECDF 按同一温度网格计算。开箱补录区间覆盖的测温点标为事件影响，剔除后单独复核持续偏离。",
            "limitations": ["连续采样点可能自相关，KS p 值仅作筛查参考", "比例是采样点比例，未估算货物核心温度", "不能据统计结果直接判定试剂可用性"]}


def seed_records():
    rng = random.Random(1002)
    rows = []
    for route, offset in [("沪东 A", 0), ("沪东 B", 1.15)]:
        for i in range(120):
            temp = 5.4 + offset + .6 * math.sin(i / 11) + rng.gauss(0, .6)
            if route == "沪东 B" and 56 <= i <= 72:
                temp += 1.8
            rows.append({"sample": f"{route[-1]}-{i+1:03}", "route": route, "minute": i * 2, "temperature": round(temp, 3)})
    return rows


def event_windows(events):
    """把补录区间规范化为闭区间窗口；缺边界或倒置的区间不进入计算。"""
    windows = []
    for e in events or []:
        try:
            s, t = float(e.get("start_minute")), float(e.get("end_minute"))
        except (TypeError, ValueError, AttributeError):
            continue
        if math.isfinite(s) and math.isfinite(t) and s <= t:
            windows.append({"route": str(e.get("route")), "start": s, "end": t, "label": str(e.get("label") or "开箱事件")})
    return windows


def compute_affected(records, events):
    """返回 {路线: [采样点]}：分钟落入任一开箱区间的测温点，标为事件影响。"""
    windows = event_windows(events)
    affected = {}
    for r in records:
        try:
            minute = float(r.get("minute"))
            if not math.isfinite(minute):
                continue
        except (TypeError, ValueError):
            continue
        route = str(r.get("route"))
        if any(w["route"] == route and w["start"] <= minute <= w["end"] for w in windows):
            affected.setdefault(route, []).append(str(r.get("sample")))
    return affected


def analyze(records, params, events=None):
    try:
        upper, alpha = float(params.get("upper", 8)), float(params.get("alpha", .05))
    except (ValueError, TypeError):
        raise ValueError("温区和显著性水平须为数值")
    if not math.isfinite(upper) or not 2 <= upper <= 15 or alpha not in (.01, .05, .1):
        raise ValueError("上界范围 2–15°C，显著性水平只接受 0.01/0.05/0.1")
    grouped, points = {}, {}
    for r in records:
        try:
            name, val = str(r["route"]), float(r["temperature"])
            if not math.isfinite(val):
                raise ValueError()
            grouped.setdefault(name, []).append(val)
            try:
                minute = float(r.get("minute"))
            except (TypeError, ValueError):
                minute = float("nan")
            points.setdefault(name, []).append((minute, val))
        except (TypeError, ValueError, KeyError):
            raise ValueError("每点须有路线和有限温度数值")
    if len(grouped) != 2 or any(len(v) < 10 for v in grouped.values()):
        raise ValueError("恰需两条路线，每条至少 10 个测温点")
    names = sorted(grouped)
    a, b = [np.array(grouped[n]) for n in names]
    ks = stats.ks_2samp(a, b, alternative="two-sided", method="auto")
    grid = np.linspace(min(float(a.min()), float(b.min())), max(float(a.max()), float(b.max())), 25)
    rows = [{"route": n, "count": len(grouped[n]), "mean": round(float(np.mean(grouped[n])), 3), "p95": round(float(np.quantile(grouped[n], .95)), 3), "over": int(sum(t > upper for t in grouped[n])), "rate": round(sum(t > upper for t in grouped[n]) / len(grouped[n]) * 100, 3)} for n in names]
    verdict = "存在分布差异" if float(ks.pvalue) < alpha else "未检出分布差异"
    result = {"summary": f"{names[0]} 与 {names[1]} 的 KS D={ks.statistic:.3f}，在 α={alpha:g} 下{verdict}。",
            "metrics": [{"label": "KS 距离 D", "value": round(float(ks.statistic), 5)}, {"label": "双侧 p 值", "value": float(f"{ks.pvalue:.6g}")}, {"label": "路线 B 超温率", "value": rows[1]["rate"], "unit": "%"}, {"label": "温区上界", "value": upper, "unit": "°C"}],
            "table": {"columns": [{"key": "route", "label": "路线"}, {"key": "count", "label": "采样点"}, {"key": "mean", "label": "均温 °C"}, {"key": "p95", "label": "P95 °C"}, {"key": "over", "label": "超温点"}, {"key": "rate", "label": "超温率 %"}], "rows": rows},
            "chart": {"type": "line", "labels": [f"{x:.2f}°C" for x in grid], "series": [{"name": n + " 累积比例%", "values": [round(sum(v <= x for v in grouped[n]) / len(grouped[n]) * 100, 3) for x in grid]} for n in names]},
            "findings": [f"{n} 超温点 {r['over']}/{r['count']}，比例 {r['rate']:.2f}%。" for n, r in zip(names, rows)] + ["统计差异仅定位调查对象；请结合门开记录和独立运输批次复核。"],
            "method": metadata()["method"], "warnings": ["同一路线的连续采样存在自相关，不能把 p 值作为独立批次证据。"]}
    windows = event_windows(events)
    if not windows:
        return result
    # 开箱事件影响：覆盖点剔除后单独复核，分开短时升温与持续偏离
    affected_idx = {n: {i for i, (m, _) in enumerate(points[n]) if math.isfinite(m) and any(w["route"] == n and w["start"] <= m <= w["end"] for w in windows)} for n in names}
    cleaned = {n: [t for i, (_, t) in enumerate(points[n]) if i not in affected_idx[n]] for n in names}
    total = sum(len(affected_idx[n]) for n in names)
    result["events"] = [{"route": w["route"], "start_minute": w["start"], "end_minute": w["end"], "label": w["label"],
                         "affected": sum(1 for m, _ in points.get(w["route"], []) if math.isfinite(m) and w["start"] <= m <= w["end"])} for w in windows]
    result["affected_total"] = total
    for row, n in zip(rows, names):
        row["affected"] = len(affected_idx[n])
        row["clean_rate"] = round(sum(t > upper for t in cleaned[n]) / len(cleaned[n]) * 100, 3) if cleaned[n] else None
    result["table"]["columns"] += [{"key": "affected", "label": "事件影响点"}, {"key": "clean_rate", "label": "剔除事件后超温率 %"}]
    result["metrics"].append({"label": "事件影响点", "value": total, "unit": "点"})
    event_line = f"开箱补录 {len(windows)} 段，共 {total} 个测温点标为事件影响，已分开核对短时升温与持续偏离。"
    if all(len(cleaned[n]) >= 10 for n in names):
        ks2 = stats.ks_2samp(np.array(cleaned[names[0]]), np.array(cleaned[names[1]]), alternative="two-sided", method="auto")
        verdict2 = "存在分布差异" if float(ks2.pvalue) < alpha else "未检出分布差异"
        result["summary"] += f" 剔除 {total} 点开箱事件影响后{verdict2}。"
        result["metrics"].append({"label": "剔除事件后 KS D", "value": round(float(ks2.statistic), 5)})
        result["chart"]["series"] += [{"name": n + " 剔除事件 累积比例%", "values": [round(sum(v <= x for v in cleaned[n]) / len(cleaned[n]) * 100, 3) for x in grid]} for n in names]
        result["findings"] = [event_line, f"剔除事件影响后 KS D={ks2.statistic:.3f}，在 α={alpha:g} 下{verdict2}。"] + result["findings"]
    else:
        result["findings"] = [event_line] + result["findings"]
        result["warnings"].append("剔除开箱事件后可用测温点不足 10 个，未重新估计分布差异。")
    return result
