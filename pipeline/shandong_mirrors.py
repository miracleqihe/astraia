"""Stage a small research index of Shandong local-history mirrors.

The JSON is a researcher's field index, not the source HTML or a transcription.
Stories remain unreviewed and carry no inferred coordinates, dates, or codes.
"""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ACCESS_URL = "https://shandong-chorography.org/about/"


def load_index(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntakeError(f"山东镜像索引无法读取：{error}") from error
    if (not isinstance(data, dict) or data.get("version") != 1
            or data.get("access_url") != ACCESS_URL
            or not all(isinstance(data.get(key), str) and data[key].strip()
                       for key in ("method", "accessed_on", "access_scope", "limits"))
            or not isinstance(data.get("pages"), list) or not data["pages"]):
        raise IntakeError("山东镜像索引结构不符。")
    try:
        if date.fromisoformat(data["accessed_on"]).isoformat() != data["accessed_on"]:
            raise ValueError
    except ValueError as error:
        raise IntakeError("山东镜像索引访问日期无效。") from error
    ids, urls, keys = set(), set(), set()
    for page in data["pages"]:
        if not isinstance(page, dict) or not all(isinstance(page.get(key), str) and page[key].strip()
                                                  for key in ("key", "corpus_id", "book", "section", "county", "url")):
            raise IntakeError("山东镜像页面信息不完整。")
        url = urlsplit(page["url"])
        if (url.scheme != "https" or url.netloc != "shandong-chorography.org" or url.query or url.fragment
                or not re.fullmatch(r"/database/[a-z0-9]+/section/\d+/article/\d+/", url.path)
                or not re.fullmatch(r"[a-z][a-z0-9_]*", page["key"])
                or not re.fullmatch(r"corpus_cn_sd_[a-z0-9_]+_mirror", page["corpus_id"])
                or page["corpus_id"] in ids or page["url"] in urls or page["key"] in keys
                or not isinstance(page.get("stories"), list) or not page["stories"]):
            raise IntakeError("山东镜像页面地址、编号或目录重复。")
        ids.add(page["corpus_id"])
        urls.add(page["url"])
        keys.add(page["key"])
        titles = set()
        for story in page["stories"]:
            if (not isinstance(story, dict)
                    or not re.fullmatch(r"case_cn_sd_[a-z0-9_]+_\d{2}", str(story.get("id", "")))
                    or story["id"] in ids
                    or not all(isinstance(story.get(key), str) and story[key].strip()
                               for key in ("title", "source_category", "role_note"))
                    or story["title"] in titles
                    or any(story.get(key) is not None and (not isinstance(story[key], str) or not story[key].strip())
                           for key in ("prior_source_claim", "author_candidate", "narrator_candidate", "editor_candidate", "narrator_as_displayed", "bibliography_note", "bibliography_url"))
                    or bool(story.get("bibliography_note")) != bool(story.get("bibliography_url"))
                    or (story.get("bibliography_url") and urlsplit(story["bibliography_url"]).scheme != "https")):
                raise IntakeError("山东镜像单篇题名、角色或编号无效。")
            ids.add(story["id"])
            titles.add(story["title"])
    return data


def story_evidence(page: dict, story: dict) -> dict:
    return {
        "镜像书名": page["book"], "镜像章节": page["section"], "镜像题名": story["title"],
        "原页分组": story["source_category"], "镜像方志范围": page["county"],
        "早期刊载线索": story.get("prior_source_claim"), "作者候选": story.get("author_candidate"),
        "讲述人候选": story.get("narrator_candidate"), "讲述人页面字形": story.get("narrator_as_displayed"),
        "整理人候选": story.get("editor_candidate"), "角色与版本备注": story["role_note"],
        "相关书目对照": story.get("bibliography_note"), "相关书目出处": story.get("bibliography_url"),
    }


def evidence_block(page: dict, story: dict) -> str:
    return literal_block(json.dumps(story_evidence(page, story), ensure_ascii=False, indent=2))


def mirror_cards(index_path: Path):
    data = load_index(index_path)
    digest = sha256(index_path.read_bytes()).hexdigest()
    index_name = display_path(index_path)
    for page in data["pages"]:
        spatial = {"precision": "culture_region", "location_name": f"山东{page['county']}（方志范围；非单篇采录点）",
                   "culture_region": "China · Shandong"}
        common = {"genre": "unclassified", "credibility_tier": "C", "is_fictional_quarantine": False,
                  "spatial": spatial, "temporal": None, "standards": {},
                  "audit": {"created_at": date.today(), "reviewed_by_human": False}}

        def source(locator):
            return {"citation": f"《{page['book']}》“{page['section']}”，山东地情档案镜像；本地文件为研究字段索引。",
                    "type": "shandong_mirror_index", "url": page["url"], "locator": locator,
                    "local_path": index_name, "content_sha256": digest}

        root = {**common, "id": page["corpus_id"], "title": f"山东地方志镜像 · 《{page['book']}》",
                "node_type": "myth_corpus", "z_layer": 2,
                "sources": [source(f"{page['section']} / {len(page['stories'])} 条所选题名")]}
        root_body = (f"\n## 资料范围\n\n这是 {page['county']} 的方志镜像中一个章节的研究索引，"
                     f"选取 {len(page['stories'])} 条题名，非该地区全部口述资料。镜像并非原纸书，"
                     "字段索引未保存原网页或故事正文，其哈希不能证明网页内容；请通过来源链接回查。"
                     "该站自称用于学习、研究和检索，全文再利用许可尚未核明。\n")
        yield NodeMetadata.model_validate(root), root_body
        for story in page["stories"]:
            model = {**common, "id": story["id"], "title": f"山东方志镜像 · {story['title']}",
                     "aliases": [story["title"]], "node_type": "case", "z_layer": 1,
                     "relations": [{"type": "PART_OF_MACRO_TREND", "target": page["corpus_id"],
                                    "note": "来自同一方志镜像章节；不表示同一采录点或传播关系。"}],
                     "sources": [source(f"{page['section']} / {story['title']}")]}
            if story.get("bibliography_url"):
                model["sources"].append({"citation": "张廷银，《中国文学的民间阅读与批评》，《文史哲》2015年第3期；所引相近书目不代表已查见本篇。",
                    "type": "shandong_bibliography_index", "url": story["bibliography_url"], "locator": "第91页注⑦",
                    "local_path": index_name, "content_sha256": digest})
            body = ("\n## 镜像书目和署名线索\n\n" + evidence_block(page, story)
                    + "\n\n## 原文、版本与复核\n\n故事正文未复制，请通过出处链接在共享章节中查找题名。"
                      "该页是网站自称的方志镜像转录，不等于已查见纸本原书或早期刊物；"
                      "人物角色、题名和原始出版页码应回查。页面和故事的再利用许可待核。"
                      "方志地区不是单篇采录点，叙事里的地名和事件不能直接当作证实的地点与历史；"
                      "采录时间、坐标、体裁及标准码均未自动推定。\n")
            yield NodeMetadata.model_validate(model), body
