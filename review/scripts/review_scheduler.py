#!/usr/bin/env python3
"""
历史文章审校调度器 v1.0
借鉴 awesome_proofreading_auto 的架构模式
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 配置
CHUNK_SIZE = 200  # 每段约200字
OVERLAP_SIZE = 50  # 重叠50字
MAX_CONCURRENT_AGENTS = 3  # 最大并行Agent数

# 审校维度
REVIEW_CATEGORIES = [
    {"id": "language", "name": "语言组织", "prompt_file": "01_language.md"},
    {"id": "fact_accuracy", "name": "史实准确", "prompt_file": "02_fact_accuracy.md"},
    {"id": "narrative_logic", "name": "叙事逻辑", "prompt_file": "03_narrative_logic.md"},
    {"id": "terminology", "name": "术语一致", "prompt_file": "04_terminology.md"},
    {"id": "structure", "name": "结构规范", "prompt_file": "05_structure.md"},
    {"id": "expression", "name": "表达润色", "prompt_file": "06_expression.md"},
]


class ReviewScheduler:
    """审校调度器"""
    
    def __init__(self, article_path: str, output_dir: str):
        self.article_path = Path(article_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.article_id = self.article_path.stem
        self.article_title = ""
        self.article_content = ""
        self.chunks: List[str] = []
        
        self.issues: List[Dict] = []
        self.agent_results: List[Dict] = []
        self.start_time = None
        self.end_time = None
    
    def load_article(self) -> bool:
        """加载文章内容"""
        try:
            with open(self.article_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取标题
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                self.article_title = title_match.group(1)
            else:
                self.article_title = self.article_id
            
            # 提取正文（去掉标题和元数据）
            self.article_content = content
            return True
        except Exception as e:
            print(f"加载文章失败: {e}")
            return False
    
    def split_chunks(self) -> List[str]:
        """将文章分段"""
        # 按段落分割
        paragraphs = self.article_content.split('\n\n')
        
        chunks = []
        current_chunk = ""
        current_length = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_length = len(para)
            
            # 如果当前段落加上去会超过CHUNK_SIZE，先保存当前chunk
            if current_length + para_length > CHUNK_SIZE and current_chunk:
                chunks.append(current_chunk)
                # 保留overlap
                overlap_text = current_chunk[-OVERLAP_SIZE:] if len(current_chunk) > OVERLAP_SIZE else current_chunk
                current_chunk = overlap_text + "\n\n" + para
                current_length = len(overlap_text) + para_length
            else:
                current_chunk += "\n\n" + para if current_chunk else para
                current_length += para_length
        
        # 保存最后一个chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        self.chunks = chunks
        return chunks
    
    def generate_review_prompt(self, category: Dict, chunk: str, chunk_index: int) -> str:
        """生成审校Prompt"""
        prompt_file = Path(__file__).parent.parent / "prompts" / category["prompt_file"]
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
        
        user_prompt = f"""请对以下历史文章片段进行{category['name']}校对。

文章标题：{self.article_title}
片段位置：第{chunk_index + 1}段（共{len(self.chunks)}段）
片段内容：

{chunk}

请严格按照系统Prompt中的输出格式返回JSON结果。"""
        
        return system_prompt, user_prompt
    
    def merge_results(self, all_results: List[Dict]) -> Dict:
        """合并所有Agent的审校结果"""
        merged = {
            "article_id": self.article_id,
            "title": self.article_title,
            "review_timestamp": datetime.now().isoformat(),
            "review_duration_seconds": int((self.end_time - self.start_time).total_seconds()) if self.start_time and self.end_time else 0,
            "summary": {
                "total_issues": 0,
                "p0_count": 0,
                "p1_count": 0,
                "p2_count": 0,
                "pass": False,
                "pass_reason": ""
            },
            "category_summary": {},
            "issues": [],
            "agent_results": []
        }
        
        # 初始化category_summary
        for cat in REVIEW_CATEGORIES:
            merged["category_summary"][cat["id"]] = {
                "total": 0,
                "p0": 0,
                "p1": 0,
                "p2": 0
            }
        
        # 合并issues
        issue_id = 1
        for result in all_results:
            if "issues" in result:
                for issue in result["issues"]:
                    issue["id"] = issue_id
                    merged["issues"].append(issue)
                    issue_id += 1
                    
                    # 更新统计
                    category = issue.get("category", "unknown")
                    severity = issue.get("severity", "p2")
                    
                    if category in merged["category_summary"]:
                        merged["category_summary"][category]["total"] += 1
                        if severity in merged["category_summary"][category]:
                            merged["category_summary"][category][severity] += 1
                    
                    merged["summary"]["total_issues"] += 1
                    if severity == "p0":
                        merged["summary"]["p0_count"] += 1
                    elif severity == "p1":
                        merged["summary"]["p1_count"] += 1
                    else:
                        merged["summary"]["p2_count"] += 1
        
        # 判断是否通过
        p0_count = merged["summary"]["p0_count"]
        p1_count = merged["summary"]["p1_count"]
        
        if p0_count == 0 and p1_count <= 1:
            merged["summary"]["pass"] = True
            merged["summary"]["pass_reason"] = "P0=0 AND P1≤1，审校通过"
        else:
            merged["summary"]["pass"] = False
            merged["summary"]["pass_reason"] = f"P0={p0_count}, P1={p1_count}，审校未通过"
        
        return merged
    
    def generate_html_report(self, review_data: Dict) -> str:
        """生成HTML报告"""
        template_path = Path(__file__).parent.parent / "templates" / "report.html"
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # 生成带问题标记的文章内容
        article_content = self.article_content
        for issue in review_data["issues"]:
            location = issue.get("location", "")
            current = issue.get("current", "")
            severity = issue.get("severity", "p2")
            issue_id = issue.get("id", 0)
            
            if current and current in article_content:
                # 替换为带标记的版本
                marked_text = f'<span class="issue-marker {severity}" data-id="{issue_id}">{current}<span class="tooltip">{issue.get("reason", "")}</span></span>'
                article_content = article_content.replace(current, marked_text, 1)
        
        # 生成issue cards
        issue_cards = ""
        for issue in review_data["issues"]:
            severity = issue.get("severity", "p2")
            category = issue.get("category", "")
            category_name = next((cat["name"] for cat in REVIEW_CATEGORIES if cat["id"] == category), category)
            
            issue_cards += f'''
            <div class="issue-card {severity}" data-id="{issue.get('id', 0)}" data-category="{category}">
                <div class="issue-header">
                    <span class="issue-category">{category_name}</span>
                    <span class="issue-location">{issue.get('location', '')}</span>
                </div>
                <div class="issue-text">
                    <div class="issue-current">❌ {issue.get('current', '')}</div>
                    <div class="issue-suggested">✅ {issue.get('suggested', '')}</div>
                </div>
                <div class="issue-reason">{issue.get('reason', '')}</div>
                <div class="issue-rule">规则：{issue.get('rule_ref', '')}</div>
            </div>
            '''
        
        # 替换模板变量
        summary = review_data["summary"]
        category_summary = review_data["category_summary"]
        
        html = template.replace("{{article_title}}", self.article_title)
        html = html.replace("{{review_timestamp}}", review_data["review_timestamp"])
        html = html.replace("{{duration_seconds}}", str(review_data["review_duration_seconds"]))
        html = html.replace("{{p0_count}}", str(summary["p0_count"]))
        html = html.replace("{{p1_count}}", str(summary["p1_count"]))
        html = html.replace("{{p2_count}}", str(summary["p2_count"]))
        html = html.replace("{{pass_status}}", "✅ 通过" if summary["pass"] else "❌ 未通过")
        html = html.replace("{{language_count}}", str(category_summary.get("language", {}).get("total", 0)))
        html = html.replace("{{fact_count}}", str(category_summary.get("fact_accuracy", {}).get("total", 0)))
        html = html.replace("{{logic_count}}", str(category_summary.get("narrative_logic", {}).get("total", 0)))
        html = html.replace("{{term_count}}", str(category_summary.get("terminology", {}).get("total", 0)))
        html = html.replace("{{struct_count}}", str(category_summary.get("structure", {}).get("total", 0)))
        html = html.replace("{{expr_count}}", str(category_summary.get("expression", {}).get("total", 0)))
        html = html.replace("{{article_content_with_markers}}", article_content)
        html = html.replace("{{issue_cards}}", issue_cards)
        
        return html
    
    def save_progress(self, status: str, completed_agents: List[str]):
        """保存进度"""
        progress = {
            "article_id": self.article_id,
            "status": status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "completed_agents": completed_agents,
            "pending_agents": [cat["id"] for cat in REVIEW_CATEGORIES if cat["id"] not in completed_agents],
            "issue_count": len(self.issues)
        }
        
        progress_path = self.output_dir / f"{self.article_id}_progress.json"
        with open(progress_path, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    
    def run(self, all_results: Optional[List[Dict]] = None):
        """运行审校流程"""
        print(f"开始审校: {self.article_path}")
        
        # 加载文章
        if not self.load_article():
            return False
        
        # 分段
        chunks = self.split_chunks()
        print(f"文章分段: {len(chunks)} 段")
        
        # 记录开始时间
        self.start_time = datetime.now()
        
        # 如果没有提供结果，则生成Prompt（实际执行由外部Agent完成）
        if all_results is None:
            print("生成审校任务...")
            tasks = []
            for category in REVIEW_CATEGORIES:
                for chunk_index, chunk in enumerate(chunks):
                    system_prompt, user_prompt = self.generate_review_prompt(category, chunk, chunk_index)
                    tasks.append({
                        "category": category["id"],
                        "chunk_index": chunk_index,
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt
                    })
            
            print(f"共 {len(tasks)} 个审校任务")
            print("请将任务分发给Agent执行，然后将结果传入 run(all_results)")
            
            # 保存任务列表
            tasks_path = self.output_dir / f"{self.article_id}_tasks.json"
            with open(tasks_path, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            
            return True
        
        # 记录结束时间
        self.end_time = datetime.now()
        
        # 合并结果
        print("合并审校结果...")
        review_data = self.merge_results(all_results)
        
        # 保存JSON结果
        json_path = self.output_dir / f"{self.article_id}_review.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(review_data, f, ensure_ascii=False, indent=2)
        print(f"JSON报告已保存: {json_path}")
        
        # 生成HTML报告
        print("生成HTML报告...")
        html_content = self.generate_html_report(review_data)
        html_path = self.output_dir / f"{self.article_id}_review.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML报告已保存: {html_path}")
        
        # 输出摘要
        summary = review_data["summary"]
        print("\n" + "="*50)
        print(f"审校完成: {self.article_title}")
        print(f"总问题数: {summary['total_issues']}")
        print(f"P0严重: {summary['p0_count']}")
        print(f"P1重要: {summary['p1_count']}")
        print(f"P2建议: {summary['p2_count']}")
        print(f"审校结果: {'✅ 通过' if summary['pass'] else '❌ 未通过'}")
        print(f"通过原因: {summary['pass_reason']}")
        print("="*50)
        
        return review_data


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python review_scheduler.py <article_path> [output_dir]")
        print("示例: python review_scheduler.py 2026-05-29.md ./output")
        sys.exit(1)
    
    article_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./review_output"
    
    scheduler = ReviewScheduler(article_path, output_dir)
    scheduler.run()


if __name__ == "__main__":
    main()
