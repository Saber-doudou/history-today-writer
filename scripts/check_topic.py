#!/usr/bin/env python3
"""
check_topic.py — 选题查重脚本（机械性防护网，移植自 Daily Why 同名脚本）

用法：
    python check_topic.py "1999年10月12日 世界第60亿人口日"
    python check_topic.py --topic "万国邮政联盟成立"
    python check_topic.py --angle "辛丑条约签订"          # 角度模式：相似度 0.50 到 0.70 放行并提示
    python check_topic.py --threshold 0.60 "xxx"           # 自定义阈值（默认 0.70）
    python check_topic.py --self-test                      # 全量回归（216 篇互查误杀率 + 已知同事件对漏放率）

退出码：
    0 = 通过（选题未使用过；角度模式下相似度 0.50 到阈值之间放行并提示）
    1 = 重复（选题已存在，精确匹配或语义相似）
    2 = 参数错误

数据源（2026-10-13 移植时确定，三者互补，覆盖缺口见回归报告）：
    1. archive/daily/TOPICS.md        —— 表格行（| MM-DD | 选题名 | 领域 |）+「选题复盘」块标题
    2. archive/daily/YYYY-MM-DD.md    —— 正式文章（标题提取：On This Day 格式 / 老格式 ## 事件行）
    3. archive/daily/YYYY-MM-DD_v2.md —— 优化版文章（同源兜底）

设计原则：
    - 纯机械比对，不依赖 AI 判断力（替代原「LLM 整读 TOPICS.md」模式）
    - 两层检测：精确匹配 + 字符包含率语义相似
    - 不引入 SQLite/第二事实源（防双源漂移铁律），TOPICS.md 仍是人类可读唯一源
    - 角度模式（--angle）：相似度落在 [0.50, 阈值) 区间属「同事件不同角度」，放行并提示人工确认
"""

import re
import sys
import argparse
from pathlib import Path

DEFAULT_WORKSPACE = r"F:\WorkBuddy\history-today"

# 停用单字：无区分度的虚词 + 日期通用字 + 高频泛指字（年/月/日/那/一 在标题中几乎无区分度）
STOP_CHARS = set("的了会是在都就也还和与或有没能人可以年月日那一")
# 核心字符下限：少于此长度的候选只做精确匹配，不做语义检测（短叙事标题判别力不足）
MIN_CORE_CHARS = 6

# 交集比例阈值（核心字符包含率 ≥70% → 判重复）
OVERLAP_THRESHOLD = 0.70

# 角度相关下限：相似度落在 [ANGLE_THRESHOLD, OVERLAP_THRESHOLD) 区间属同事件不同角度
ANGLE_THRESHOLD = 0.50

# 文章文件排除名单（非选题文章）
ARTICLE_EXCLUDE = {"TOPICS.md", "选题索引.md"}


def normalize_topic(text: str) -> str:
    """标准化：去 emoji、去首尾空白"""
    text = re.sub(
        r'[\U0001F000-\U0001FFFF\U00002700-\U000027BF\U0000FE00-\U0000FE0F'
        r'\U0000200D\U00002600-\U000026FF\U00002300-\U000023FF\U00002B50'
        r'\U0000231A\U0000231B\U00002934\U00002935\U000025AA-\U000025FE'
        r'\U00002B05-\U00002B07\U00002B1B\U00002B1C\U00003030\U0000303D'
        r'\U00003297\U00003299\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\U00002702-\U000027B0]+',
        '', text
    )
    return text.strip().replace('\u3000', '')


def extract_core_chars(text: str) -> str:
    """提取核心字符：去前缀、去标点、去停用单字与高频泛指词，用于字符级语义相似度"""
    normalized = normalize_topic(text)
    normalized = re.sub(
        r'[？?！!。，,、；;：:\u201c\u201d\u2018\u2019\u3000\s]+',
        '', normalized
    )
    # 词级去除高频泛指词（先词后字，避免「那个」拆字后残留）
    for word in ("那个", "这个", "一个", "为什么", "怎么", "如何", "第一", "那天", "这天"):
        normalized = normalized.replace(word, '')
    return ''.join(c for c in normalized if c not in STOP_CHARS)


def check_semantic_similarity(new_topic: str, existing_topic: str,
                              threshold: float = OVERLAP_THRESHOLD) -> tuple[bool, float, str]:
    """
    字符包含率检测：短的一方做分母，其字符有多少在长的一方中出现。

    返回: (is_similar, score, detail)
        score 落在 [ANGLE_THRESHOLD, threshold) 区间时由调用方决定是否角度放行。
    """
    core_new = extract_core_chars(new_topic)
    core_existing = extract_core_chars(existing_topic)

    if len(core_new) < MIN_CORE_CHARS or len(core_existing) < MIN_CORE_CHARS:
        return False, 0.0, f"核心字符不足（<{MIN_CORE_CHARS}，只做精确匹配）"

    # 纯数字序列（日期型条目）无语义判别力，跳过
    if core_new.isdigit() or core_existing.isdigit():
        return False, 0.0, "纯数字条目，跳过语义检测"

    set_new, set_existing = set(core_new), set(core_existing)

    if len(set_new) <= len(set_existing):
        smaller = set_new
    else:
        smaller = set_existing

    if not smaller:
        return False, 0.0, "无有效字符"

    common = smaller & (set_new & set_existing)
    ratio = len(common) / len(smaller)

    if ratio >= threshold:
        return True, ratio, f"字符包含率 {ratio:.0%}: 「{core_new}」vs「{core_existing}」"

    return False, ratio, f"字符包含率 {ratio:.0%} < {threshold:.0%}"


def strip_title_prefix(title: str) -> str:
    """剥掉标题的容器前缀（On This Day / 历史上的今天 |），只留叙事标题本体"""
    title = title.strip()
    for prefix in ("On This Day", "历史上的今天"):
        title = re.sub(rf'^\s*{re.escape(prefix)}\s*[|｜·]\s*', '', title)
    return title.strip()


def extract_topic_from_article(filepath: Path) -> str | None:
    """
    从文章文件提取选题标题。历史格式：
      新格式（2026-04 下旬起）: 首行 '# On This Day | 叙事标题'
      过渡格式               : 首行 '# 历史上的今天 | 叙事标题'
      老格式（2026-04 及以前）: 首行 '# 历史上的今天 · M月D日'，第二个 '## ' 行是事件标题
    容器前缀一律剥掉，与 l3_publish 的首行策略同口径，兜底取首个非空行。
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return None

    first_nonempty = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if first_nonempty is None:
            first_nonempty = s
        # 新格式 / 过渡格式：# On This Day | X / # 历史上的今天 | X
        m = re.match(r'^#+\s*(?:On This Day|历史上的今天)\s*[|｜·]\s*(.+)$', s)
        if m:
            head = strip_title_prefix(m.group(1))
            # 纯日期主标题（「4月13日」/「1889年4月20日」）只是日期行，跳过继续找 ## 事件行
            if not re.match(r'^(\d{4}年)?\d{1,2}月\d{1,2}日$', head):
                return head
        # 老格式：事件标题在 ## 行（跳过 '# 历史上的今天 · 日期' 主标题）
        if s.startswith('## ') and '历史上的今天' not in s:
            return strip_title_prefix(s.lstrip('#').strip())
    if first_nonempty:
        return strip_title_prefix(first_nonempty.lstrip('#').strip()) or None
    return None


def load_existing_topics(workspace: Path) -> list[tuple[str, str, str]]:
    """
    加载全部已有选题。返回 [(source, topic, meta), ...]
    source: topics_table / topics_review / article
    """
    existing = []

    # 源 1+2: TOPICS.md
    topics_file = workspace / "archive" / "daily" / "TOPICS.md"
    if topics_file.exists():
        text = topics_file.read_text(encoding='utf-8')
        for line in text.splitlines():
            # 表格行: | MM-DD | 选题名 | 领域 |
            m = re.match(r'^\|\s*(\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|', line)
            if m:
                name = m.group(2).strip()
                if name and name != '_(待补充)_':
                    existing.append(("topics_table", name, m.group(1)))
            # 复盘块标题: ## 选题复盘：YYYY-MM-DD | 选题名
            m3 = re.match(r'^##\s*选题复盘[：:]\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+)$', line)
            if m3:
                existing.append(("topics_review", m3.group(2).strip(), m3.group(1)))

    # 源 3: 日更文章（正式版 + v2 优化版）
    daily_dir = workspace / "archive" / "daily"
    if daily_dir.exists():
        for md_file in sorted(daily_dir.glob("20*-*.md")):
            if md_file.name in ARTICLE_EXCLUDE:
                continue
            if "_review" in md_file.name or "_topic_result" in md_file.name:
                continue
            topic = extract_topic_from_article(md_file)
            if topic:
                existing.append(("article", topic, md_file.stem))

    return existing


def check_topic(topic: str, workspace: Path, threshold: float = OVERLAP_THRESHOLD,
                angle_mode: bool = False,
                exclude_date: str | None = None) -> tuple[bool, str]:
    """检查选题是否已使用过（精确匹配 + 语义相似两层）"""
    normalized = normalize_topic(topic)
    if not normalized:
        return False, "选题为空"

    all_existing = load_existing_topics(workspace)

    # 排除当日自身记录（避免「自己匹配自己」）：
    #   article 源 meta 是文件 stem（含完整日期，如 2026-05-21_v2）
    #   topics_review 源 meta 是完整日期；topics_table 源 meta 是 MM-DD 月日
    #   排除时同时匹配完整日期与 MM-DD 两种形态（日更始于 2026-04，无跨年同月日冲突）
    if exclude_date:
        mmdd = exclude_date[5:]  # YYYY-MM-DD -> MM-DD
        all_existing = [
            (src, t, meta) for src, t, meta in all_existing
            if not (meta and (exclude_date in str(meta) or mmdd in str(meta)))
        ]

    # === 检查 1: 精确匹配 ===
    for source, existing_topic, meta in all_existing:
        if normalize_topic(existing_topic) == normalized:
            meta_str = f"（{meta}）" if meta else ""
            return True, f"精确匹配 [{source}]{meta_str}: \"{existing_topic}\""

    # === 检查 2: 语义相似 ===
    angle_matches = []
    for source, existing_topic, meta in all_existing:
        is_sim, score, detail = check_semantic_similarity(topic, existing_topic, threshold)
        if is_sim:
            meta_str = f"（{meta}）" if meta else ""
            return True, f"语义相似 [{source}]{meta_str}: \"{existing_topic}\" — {detail}"
        if score >= ANGLE_THRESHOLD:
            angle_matches.append((source, existing_topic, meta, score))

    if angle_matches:
        angle_matches.sort(key=lambda x: x[3], reverse=True)
        source, existing_topic, meta, score = angle_matches[0]
        meta_str = f"（{meta}）" if meta else ""
        if angle_mode:
            return False, (
                f"⚠️ 角度相关（相似度 {score:.0%}），请确认写作角度与已有选题不同 "
                f"[{source}]{meta_str}: \"{existing_topic}\""
            )
        return True, (
            f"语义相似 [角度相关区间] [{source}]{meta_str}: \"{existing_topic}\" "
            f"— 相似度 {score:.0%}（≥{ANGLE_THRESHOLD:.0%} 且 <{threshold:.0%}），"
            f"若确认角度不同请用 --angle 模式放行"
        )

    return False, "选题未使用过，可以写作"


def run_self_test(workspace: Path, threshold: float) -> int:
    """
    全量回归：
      A. 误杀测试：216 篇标题互查（排除自身），记录判重对数（预期 0，异常需人工核查）
      B. 漏放测试：TOPICS.md 表格选题名作为候选（预期全部 exit 1，因 TOPICS 自身是索引源）
      C. 覆盖口径：报告三源条目数与文章篇数
    """
    daily_dir = workspace / "archive" / "daily"
    articles = sorted(
        p for p in daily_dir.glob("20*-*.md")
        if p.name not in ARTICLE_EXCLUDE
        and "_review" not in p.name and "_topic_result" not in p.name
    )

    print(f"[self-test] 数据源加载中...")
    existing = load_existing_topics(workspace)
    src_count = {}
    for src, _, _ in existing:
        src_count[src] = src_count.get(src, 0) + 1
    print(f"[self-test] 索引条目: {src_count}，合计 {len(existing)} 条")
    print(f"[self-test] 文章文件: {len(articles)} 篇")

    # A. 误杀测试：每篇文章标题作为候选，查全库（排除自身日期）
    # 口径：≥70% 硬误杀才算失败（不同事件被判同一选题）；
    #       50-70% 角度区匹配属「同事件不同角度」候选区，生产端用 --angle 放行+提示，此处只计数
    hard_fp, angle_fp = [], []
    for art in articles:
        topic = extract_topic_from_article(art)
        if not topic:
            continue
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', art.stem)
        exclude = date_match.group(1) if date_match else None
        is_dup, detail = check_topic(topic, workspace, threshold, exclude_date=exclude)
        if not is_dup:
            continue
        if "角度相关区间" in detail:
            angle_fp.append((art.name, topic, detail))
        else:
            hard_fp.append((art.name, topic, detail))
    print(f"[self-test] A 误杀测试: 硬误杀 {len(hard_fp)}/{len(articles)} 篇（预期 0）；"
          f"角度区匹配 {len(angle_fp)} 篇（生产端 --angle 放行，不计失败）")
    for name, topic, detail in hard_fp:
        print(f"    ❌ {name}: 「{topic[:40]}」→ {detail[:110]}")

    # B. 漏放测试：TOPICS 表格选题名应全部判重（精确匹配自身索引）
    topics_file = daily_dir / "TOPICS.md"
    missed = []
    total_topics = 0
    if topics_file.exists():
        for line in topics_file.read_text(encoding='utf-8').splitlines():
            m = re.match(r'^\|\s*(\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|', line)
            if m:
                name = m.group(2).strip()
                if name and name != '_(待补充)_':
                    total_topics += 1
                    is_dup, _ = check_topic(name, workspace, threshold)
                    if not is_dup:
                        missed.append(name)
    print(f"[self-test] B 漏放测试: {len(missed)}/{total_topics} 个 TOPICS 选题名未判重（预期 0）")
    for name in missed:
        print(f"    ❌ 漏放: 「{name}」")

    ok = not hard_fp and not missed
    print(f"[self-test] 结论: {'✅ 全部通过' if ok else '⚠️ 存在硬误杀或漏放，需人工核查'}")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description="选题查重校验（机械性防护网）")
    parser.add_argument("topic_positional", nargs='?', help="要校验的选题（位置参数）")
    parser.add_argument("--topic", "-t", help="要校验的选题")
    parser.add_argument("--threshold", type=float, default=OVERLAP_THRESHOLD,
                        help=f"语义相似重复阈值（默认 {OVERLAP_THRESHOLD}）")
    parser.add_argument("--angle", action="store_true",
                        help="角度模式：相似度 0.50 到阈值之间的同事件不同角度放行并提示")
    parser.add_argument("--workspace", "-w", default=DEFAULT_WORKSPACE,
                        help="工作目录路径")
    parser.add_argument("--exclude-date", default=None,
                        help="排除该日期(YYYY-MM-DD)的自身记录，避免自匹配")
    parser.add_argument("--self-test", action="store_true",
                        help="全量回归：误杀测试 + 漏放测试 + 覆盖口径报告")
    args = parser.parse_args()

    if args.threshold <= 0 or args.threshold > 1:
        print("[check_topic] ❌ 阈值必须在 0 到 1 之间", file=sys.stderr)
        sys.exit(2)
    if args.angle and args.threshold <= ANGLE_THRESHOLD:
        print(f"[check_topic] ⚠️ 阈值 {args.threshold} 不大于角度下限 {ANGLE_THRESHOLD}，"
              f"角度模式将不会放行任何选题", file=sys.stderr)

    workspace = Path(args.workspace)

    if args.self_test:
        sys.exit(run_self_test(workspace, args.threshold))

    topic = args.topic or args.topic_positional
    if not topic:
        print("[check_topic] ❌ 未提供选题。用法: check_topic.py \"1999年10月12日 世界第60亿人口日\"",
              file=sys.stderr)
        sys.exit(2)

    is_dup, detail = check_topic(topic, workspace,
                                 threshold=args.threshold, angle_mode=args.angle,
                                 exclude_date=args.exclude_date)

    if is_dup:
        print(f"[check_topic] ❌ 重复: {detail}")
        sys.exit(1)
    else:
        print(f"[check_topic] ✅ 通过: {detail}")
        sys.exit(0)


if __name__ == "__main__":
    main()
